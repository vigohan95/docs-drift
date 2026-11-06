"""Claim path: concrete statements from README / guides, checked against the
rest of the docs.  local shortlist -> /rerank picks evidence -> /grounding judges.

Usage: python -X utf8 -m docsdrift.claims <project> --readme 15 --guides 15 --credits 350
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter

from .client import Clocked, BudgetExceeded, ClockedError
from .neardup import sentences, TOKEN, STOP
from .pairrun import spent_under
from .pipeline import RUNS
from .targets import load, TARGETS

FACT = re.compile(
    r"\b\d+(?:\.\d+)*\s?(?:ms|s|seconds?|minutes?|hours?|days?|[KMG]i?B|bytes|%|x|\+)?\b|default|require[sd]?\b|"
    r"\bmust\b|\bonly\b|\bnever\b|\balways\b|deprecated|removed|no longer|supports?\b|at least|at most|maximum|minimum",
    re.I,
)
VAGUE_START = re.compile(r"^(this|that|it|these|those|they|here|see|note|for example|e\.g\.)\b", re.I)


def fact_score(text: str) -> int:
    nums = len(re.findall(r"\b\d+(?:\.\d+)*", text))
    code = len(re.findall(r"`[^`]+`", text))
    words = len(FACT.findall(text))
    return 2 * min(nums, 3) + min(code, 3) + words


VERB = re.compile(r"\b(is|are|was|were|will|must|can|cannot|requires?|supports?|defaults?|uses?|binds|targets|"
                  r"provides?|returns?|receives?|has|have|limits?|allows?|sets?|runs?)\b", re.I)


def looks_like_prose_claim(text: str) -> bool:
    t = text.strip()
    if t.startswith(("|", "<", "{", "`", "[", ".", "#", "!")) or "{{" in t or "```" in t:
        return False
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)      # drop link targets
    plain = re.sub(r"https?://\S+", "", plain)
    if len(plain) < 40:
        return False
    letters = sum(ch.isalpha() or ch.isspace() for ch in plain)
    if letters / len(plain) < 0.72:
        return False
    return bool(VERB.search(plain))


def pick_claims(chunks, readme_path: str, n_readme: int, n_guides: int):
    readme, others = [], []
    for ch in chunks:
        for s in sentences(ch):
            if len(s.text) < 40 or len(s.text) > 420 or not FACT.search(s.text):
                continue
            if not looks_like_prose_claim(s.text):
                continue
            sc = fact_score(s.text)
            (readme if ch.path == readme_path else others).append((sc, s))
    readme.sort(key=lambda t: -t[0])
    picked = [s for _, s in readme[:n_readme]]
    per_file = Counter()
    others.sort(key=lambda t: -t[0])
    for sc, s in others:
        if len(picked) >= n_readme + n_guides:
            break
        if VAGUE_START.match(s.text) or per_file[s.chunk.path] >= 2:
            continue
        per_file[s.chunk.path] += 1
        picked.append(s)
    return picked


class Shortlist:
    """IDF-weighted token overlap between a claim and every chunk."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.toks = [set(t.lower() for t in TOKEN.findall(c.text)) - STOP for c in chunks]
        df = Counter()
        for t in self.toks:
            df.update(t)
        n = len(chunks)
        self.idf = {t: math.log(1 + n / c) for t, c in df.items()}

    def top(self, claim: str, exclude_path: str, k: int):
        q = set(t.lower() for t in TOKEN.findall(claim)) - STOP
        scored = []
        for c, toks in zip(self.chunks, self.toks):
            if c.path == exclude_path:
                continue
            s = sum(self.idf.get(t, 0) for t in q if t in toks)
            if s > 0:
                scored.append((s / math.sqrt(len(toks) + 20), c))
        scored.sort(key=lambda t: -t[0])
        return [c for _, c in scored[:k]]


def run(project: str, n_readme: int, n_guides: int, credit_cap: float, shortlist_k: int = 10):
    chunks = load(project)
    by_cid = {c.cid: c for c in chunks}
    claims = pick_claims(chunks, TARGETS[project]["readme"], n_readme, n_guides)
    sl = Shortlist(chunks)
    client = Clocked(budget=5000, reserve=150)
    prefix = f"{project}-claims/"
    rows = []
    for i, s in enumerate(claims):
        if spent_under(prefix) >= credit_cap:
            print(f"[{project}] credit cap reached", flush=True)
            break
        cands = sl.top(s.text, s.chunk.path, shortlist_k)
        row = {"i": i, "claim": s.text, "path": s.chunk.path, "line": s.line, "heading": s.chunk.heading,
               "shortlist": [c.cid for c in cands]}
        try:
            rr = client.call("rerank", {
                "query": f"Which passages state the facts needed to check this statement: {s.text}"[:3900],
                "instructions": "A passage answers only if it states the same fact, value, limit, version or rule "
                                "that the statement is about, whether it agrees or disagrees with the statement.",
                "documents": [{"id": c.cid, "title": f"{c.path} > {c.heading}"[:480], "text": c.text} for c in cands],
            }, f"{prefix}{i:03d}.rerank")
            row["rerank"] = [{"id": r["id"], "action": r["action"], "relevance": r["relevance_score"]} for r in rr["results"]]
            kept = [by_cid[r["id"]] for r in rr["results"] if r["action"] == "use"][:4]
            row["kept"] = [c.cid for c in kept]
            if not kept:
                row["verdict"] = "no evidence passage selected by rerank"
                rows.append(row)
                continue
            g = client.call("grounding", {
                "documents": [{"id": c.cid, "text": c.text} for c in kept],
                "answer": s.text, "claims": [s.text], "evidence": "all",
                "instructions": f"The statement comes from the section '{s.chunk.heading}' of {s.chunk.path} in the "
                                f"documentation of the {project} project; the sources are other sections of the same "
                                "documentation. Mark it contradicted only when a source states an incompatible value, "
                                "version, limit or rule for the same thing in the same scope. Example values in code "
                                "samples are not contradictions.",
            }, f"{prefix}{i:03d}.grounding")
        except BudgetExceeded as e:
            print("budget:", e, flush=True)
            break
        except ClockedError as e:
            row["error"] = str(e)[:200]
            rows.append(row)
            continue
        c0 = g["claims"][0] if g.get("claims") else {}
        ev = c0.get("evidence") or {}
        row.update({
            "verdict": c0.get("verdict"), "supported": c0.get("supported"), "contradicted": c0.get("contradicted"),
            "not_stated": c0.get("not_stated"), "source": c0.get("source"),
            "evidence": None if not ev else {
                "cid": ev.get("document"), "quote": ev.get("quote"),
                "path": by_cid[ev["document"]].path if ev.get("document") in by_cid else None,
                "line": by_cid[ev["document"]].line_of(ev["start"]) if ev.get("document") in by_cid and "start" in ev else None,
            },
        })
        rows.append(row)
        print(f"[{project}] claim {i}: {row['verdict']}", flush=True)
    out = RUNS / project
    out.mkdir(parents=True, exist_ok=True)
    (out / "claims.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{project}] claims {len(rows)}; verdicts {dict(Counter(r.get('verdict') for r in rows))}; "
          f"credits {spent_under(prefix):.0f}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--readme", type=int, default=15)
    ap.add_argument("--guides", type=int, default=15)
    ap.add_argument("--credits", type=float, default=350)
    a = ap.parse_args()
    run(a.project, a.readme, a.guides, a.credits)
