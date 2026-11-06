"""Docs Drift pipeline v2.

  local candidates (free)
    -> /compare, one request per pair of passages      (finds conflicts)
    -> /grounding, each side's statement vs the other  (second opinion gate)
    -> /rerank + /grounding over the rest of the docs  (where else is this said,
                                                         which side is the outlier)

Every request goes through the replay cache in client.py, so a scan of a
repository at a pinned commit can be replayed offline at zero cost.
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .client import Clocked, ClockedError, BudgetExceeded
from .filters import REPORTABLE_KINDS, version_scoped_pair
from .local import rank_keys
from .neardup import chunk_pairs, TOKEN, STOP
from .sections import Chunk, load_project

# Same text as day 1 so that day-1 recordings stay valid cache entries.
COMPARE_INSTRUCTIONS = (
    "The documents are sections of the documentation of ONE open-source project at one commit. "
    "Report a conflict only when two sections make incompatible statements about the SAME option, "
    "flag, default value, limit, version requirement, or behavior, for the same product version and scope. "
    "These are NOT conflicts: values of different options; example values in code samples that merely "
    "override a default; statements explicitly scoped to an older version or to migration history; "
    "one section giving more detail than the other; different defaults that the text ties to different "
    "contexts (per-route vs global, dev vs build, agent mode vs server mode)."
)

GATE_INSTRUCTIONS = (
    "The statement and the source are two sections of the same project's documentation at the same version. "
    "Mark the statement contradicted only when the source states an incompatible value, version, limit, name "
    "or rule for the same thing in the same scope. If the source is about a different option, hook, function, "
    "package or version, the statement is not stated, not contradicted. An example value in a code sample "
    "that overrides a default does not contradict the default."
)

RERANK_INSTRUCTIONS = (
    "A passage answers only if it itself states the fact that the two statements disagree about: a value, "
    "version, limit, name, list or rule for the same thing. A passage that only mentions the topic does not answer."
)

WIDE_QUOTE = 450      # a quote longer than this cannot be reduced to one statement
MAX_STATEMENT = 420


# ----------------------------------------------------------------- candidates

def build_candidates(chunks: list[Chunk], max_neardup: int = 120, max_key: int = 30):
    """Ordered list of passage pairs to compare. Purely local, no API."""
    texts, cross, same = set(), [], []
    skipped_versioned = 0
    for p in chunk_pairs(chunks):
        tkey = tuple(sorted((p["a"].text.lower(), p["b"].text.lower())))
        if tkey in texts:
            continue
        texts.add(tkey)
        if version_scoped_pair(p["a"].chunk.path, p["b"].chunk.path):
            skipped_versioned += 1
            continue
        (cross if p["a"].chunk.path != p["b"].chunk.path else same).append(p)
    picked = (cross + same)[:max_neardup]
    out, seen = [], set()
    for p in picked:
        a, b = p["a"].chunk, p["b"].chunk
        seen.add(frozenset((a.cid, b.cid)))
        out.append({"a": a, "b": b, "source": "near-dup", "sim": p["sim"],
                    "sent_a": (p["a"].line, p["a"].text), "sent_b": (p["b"].line, p["b"].text)})
    n_key = 0
    for score, key, bearing in rank_keys(chunks):
        if n_key >= max_key:
            break
        per_key = 0
        for i, a in enumerate(bearing):
            for b in bearing[i + 1:]:
                if a.path == b.path or frozenset((a.cid, b.cid)) in seen or per_key >= 2 or n_key >= max_key:
                    continue
                if version_scoped_pair(a.path, b.path):
                    continue
                seen.add(frozenset((a.cid, b.cid)))
                out.append({"a": a, "b": b, "source": "shared-key", "key": key})
                per_key += 1
                n_key += 1
    stats = {"near_dup_cross_file": len(cross), "near_dup_same_file": len(same),
             "near_dup_sent": len(picked), "shared_key_sent": n_key,
             "skipped_version_scoped": skipped_versioned}
    return out, stats


# ------------------------------------------------------------------ helpers

def finding_id(project: str, a: Chunk, b: Chunk, fa: dict, fb: dict) -> str:
    sig = f"{project}|{a.cid}|{b.cid}|{fa.get('start')}|{fa.get('end')}|{fb.get('start')}|{fb.get('end')}"
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()[:10]


_SENT_END = re.compile(r"[.!?](?=\s|$)|\n[ \t]*\n")


def statement_of(chunk: Chunk, start: int | None, end: int | None) -> str | None:
    """The quoted span grown to the end of its sentence, as one clean line.

    The API often returns only the first line of a sentence; the statement
    handed to /grounding must be the whole sentence. Returns None when the
    quote is too wide to be a single statement.
    """
    if start is None or end is None or end - start > WIDE_QUOTE:
        return None
    text = chunk.text
    m = _SENT_END.search(text, max(end - 1, start))
    stop = m.end() if m else len(text)
    stop = min(stop, start + MAX_STATEMENT)
    s = text[start:stop]
    s = re.sub(r"\n\s*>\s?", " ", s)          # blockquote continuation
    s = re.sub(r"^\s*>\s?", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) >= 12 else None


def exact_span(text: str, f: dict) -> tuple[int | None, int | None]:
    """Offsets of the quoted span in `text`.

    In about 2% of the spans /compare returned, text[start:end] is the quote shifted by a
    few characters. When that happens, use the occurrence of the quote nearest to `start`.
    """
    start, end, quote = f.get("start"), f.get("end"), f.get("quote")
    if start is None or end is None or not quote or text[start:end] == quote:
        return start, end
    best, pos = None, text.find(quote)
    while pos != -1:
        if best is None or abs(pos - start) < abs(best - start):
            best = pos
        pos = text.find(quote, pos + 1)
    if best is None:
        return start, end
    return best, best + len(quote)


def side_info(repo: str, commit: str, chunk: Chunk, f: dict) -> dict:
    start, end = exact_span(chunk.text, f)
    l0 = chunk.line_of(start) if start is not None else chunk.start_line
    l1 = chunk.line_of(max(end - 1, start)) if end is not None else l0
    return {
        "cid": chunk.cid, "path": chunk.path, "heading": chunk.heading,
        "line_start": l0, "line_end": l1, "chunk_lines": [chunk.start_line, chunk.end_line],
        "quote": f.get("quote"), "statement": statement_of(chunk, start, end),
        "url": f"https://github.com/{repo}/blob/{commit}/{chunk.path}#L{l0}-L{l1}",
    }


class Shortlist:
    """IDF-weighted token overlap between a query and every chunk (free)."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.toks = [set(t.lower() for t in TOKEN.findall(c.text)) - STOP for c in chunks]
        df = Counter()
        for t in self.toks:
            df.update(t)
        n = len(chunks)
        self.idf = {t: math.log(1 + n / c) for t, c in df.items()}

    def top(self, query: str, exclude: set, k: int):
        q = set(t.lower() for t in TOKEN.findall(query)) - STOP
        scored = []
        for c, toks in zip(self.chunks, self.toks):
            if c.cid in exclude:
                continue
            s = sum(self.idf.get(t, 0) for t in q if t in toks)
            if s > 0:
                scored.append((s / math.sqrt(len(toks) + 20), c))
        scored.sort(key=lambda t: -t[0])
        return [c for _, c in scored[:k]]


def tier_of(f: dict) -> str:
    """Reporting rule v2.1 (2026-11-07, chosen on the 57 labeled v2.0 findings and then
    checked on four projects scanned afterwards).

    out_of_scope : /compare calls the conflict a "scope" or "name" difference; that is
                   what sibling pages about different things look like. Not reported.
    confirmed    : /grounding says one side's statement is contradicted by the other
                   passage AND /compare repeats the conflict with the passages swapped
    likely       : one of those two checks agrees
    weak         : neither check agrees. Not reported by default.
    """
    if f.get("kind") not in REPORTABLE_KINDS:
        return "out_of_scope"
    if "gate" not in f and "swap" not in f:
        return "unchecked"
    gate = bool((f.get("gate") or {}).get("any_contradicted"))
    swap = bool((f.get("swap") or {}).get("confirmed"))
    if gate and swap:
        return "confirmed"
    return "likely" if (gate or swap) else "weak"


REPORTED_TIERS = ("confirmed", "likely")


# -------------------------------------------------------------------- stages

def compare_payload(a: Chunk, b: Chunk, instructions: str | None = COMPARE_INSTRUCTIONS) -> dict:
    payload = {"documents": [{"id": a.cid, "text": a.text}, {"id": b.cid, "text": b.text}], "evidence": "flagged"}
    if instructions:
        payload["instructions"] = instructions
    return payload


def gate_payload(claim: str, source: Chunk) -> dict:
    return {"documents": [{"id": source.cid, "text": source.text}], "answer": claim, "claims": [claim],
            "evidence": "all", "instructions": GATE_INSTRUCTIONS}


GATE2_RULES = (
    "Statement and source are sections of the documentation of one project at one commit. "
    "First decide whether they describe the SAME thing. If they are about different packages, frameworks, "
    "classes, hooks, options, functions, file formats, or about different released versions (for example two "
    "migration guides for different versions), the statement is NOT STATED, never contradicted. "
    "Mark it contradicted only when the source gives an incompatible value, version, limit, name, list or rule "
    "for that same thing in the same scope. An example value in a code sample that overrides a default does "
    "not contradict the default."
)


def with_provenance(chunk: Chunk) -> str:
    return f"[File: {chunk.path} | Section: {chunk.heading}]\n{chunk.text}"


def gate2_payload(claim: str, claim_chunk: Chunk, source: Chunk) -> dict:
    """Gate request that tells /grounding where the statement and the source come from."""
    where = f"The statement is taken from file {claim_chunk.path}, section \"{claim_chunk.heading}\". "
    return {"documents": [{"id": source.cid, "text": with_provenance(source)}], "answer": claim, "claims": [claim],
            "evidence": "all", "instructions": where + GATE2_RULES}


def run_gate(client: Clocked, finding: dict, by_cid: dict) -> dict:
    """Second opinion from /grounding: is each side's statement contradicted by the other passage?"""
    out = {}
    cost = 0.0
    for side, other in (("a", "b"), ("b", "a")):
        claim = finding[side]["statement"]
        if not claim:
            out[side] = None
            continue
        g, cr = client.call_cost("grounding", gate_payload(claim, by_cid[finding[other]["cid"]]))
        cost += cr
        c0 = (g.get("claims") or [{}])[0]
        out[side] = {"verdict": c0.get("verdict"), "contradicted": c0.get("contradicted"),
                     "supported": c0.get("supported"), "not_stated": c0.get("not_stated")}
    tested = [v for v in out.values() if v]
    out["tested"] = len(tested)
    out["any_contradicted"] = any(v["verdict"] == "contradicted" for v in tested)
    out["all_contradicted"] = bool(tested) and all(v["verdict"] == "contradicted" for v in tested)
    out["credits"] = cost
    return out


def run_elsewhere(client: Clocked, finding: dict, by_cid: dict, shortlist: Shortlist,
                  use_rerank: bool = True, k_short: int = 12, k_keep: int = 3) -> dict:
    """Where else do the docs state this fact, and which side do those places agree with?"""
    sa, sb = finding["a"]["statement"], finding["b"]["statement"]
    if not sa or not sb:
        return {"skipped": "one side has no single statement"}
    exclude = {finding["a"]["cid"], finding["b"]["cid"]}
    cands = shortlist.top(sa + " " + sb, exclude, k_short)
    out = {"shortlist": [c.cid for c in cands], "use_rerank": use_rerank, "credits": {"rerank": 0.0, "grounding": 0.0}}
    if not cands:
        out.update({"places": [], "votes": {"a": 1, "b": 1}, "outlier": None})
        return out
    if use_rerank:
        rr, cr = client.call_cost("rerank", {
            "query": f"Which passages state the same fact as either of these two statements? (1) {sa} (2) {sb}"[:3900],
            "instructions": RERANK_INSTRUCTIONS,
            "documents": [{"id": c.cid, "title": f"{c.path} > {c.heading}"[:480], "text": c.text} for c in cands],
        })
        out["credits"]["rerank"] += cr
        out["rerank"] = [{"id": r["id"], "action": r["action"], "relevance": r["relevance_score"]} for r in rr["results"]]
        kept = [by_cid[r["id"]] for r in rr["results"] if r["action"] == "use"][:k_keep]
    else:
        kept = cands[:k_keep]
    places = []
    for c in kept:
        g, cr = client.call_cost("grounding", {"documents": [{"id": c.cid, "text": c.text}], "answer": sa + " " + sb,
                                               "claims": [sa, sb], "evidence": "all", "instructions": GATE_INSTRUCTIONS})
        out["credits"]["grounding"] += cr
        ca, cb = (g.get("claims") or [{}, {}])[:2]
        agrees = None
        if ca.get("verdict") == "supported" and cb.get("verdict") != "supported":
            agrees = "a"
        elif cb.get("verdict") == "supported" and ca.get("verdict") != "supported":
            agrees = "b"
        ev = (ca if agrees == "a" else cb).get("evidence") or {}
        line = c.line_of(ev["start"]) if "start" in ev else c.start_line
        places.append({"cid": c.cid, "path": c.path, "heading": c.heading, "line": line,
                       "a": ca.get("verdict"), "b": cb.get("verdict"), "agrees_with": agrees,
                       "quote": ev.get("quote")})
    votes = {"a": 1 + sum(1 for p in places if p["agrees_with"] == "a"),
             "b": 1 + sum(1 for p in places if p["agrees_with"] == "b")}
    outlier = None if votes["a"] == votes["b"] else ("a" if votes["a"] < votes["b"] else "b")
    out.update({"places": places, "votes": votes, "outlier": outlier})
    return out


def scan(project: str, root: Path, includes: list[str], excludes: list[str] = (), repo: str = "", commit: str = "",
         client: Clocked | None = None, max_neardup: int = 120, max_key: int = 30,
         both_orders: bool = False, **kw) -> dict:
    """Scan a documentation tree: build candidates locally, then analyze them."""
    chunks = load_project(project, Path(root), includes, list(excludes))
    cands, cstats = build_candidates(chunks, max_neardup, max_key)
    if both_orders:
        # /compare is order-sensitive: also ask every pair the other way round (doubles the cost)
        cands = cands + [{**c, "a": c["b"], "b": c["a"], "source": c["source"] + "-reversed"} for c in cands]
        cstats["both_orders"] = True
    return analyze(project, chunks, cands, cstats, repo=repo, commit=commit, client=client, **kw)


def analyze(project: str, chunks: list[Chunk], cands: list[dict], cstats: dict | None = None, repo: str = "",
            commit: str = "", client: Clocked | None = None, swap: bool = True, gate: bool = True,
            elsewhere: bool = True, workers: int = 3, log=print) -> dict:
    client = client or Clocked()
    by_cid = {c.cid: c for c in chunks}
    cstats = cstats or {}
    log(f"[{project}] {len({c.path for c in chunks})} files, {len(chunks)} passages, {len(cands)} candidate pairs")
    t0 = time.time()
    hits0, live0, cred0 = client.cache_hits, client.live_calls, client.live_credits
    credits = {"compare": 0.0, "grounding": 0.0, "rerank": 0.0}

    def do_compare(c):
        payload = compare_payload(c["a"], c["b"])
        try:
            r, cr = client.call_cost("compare", payload)
        except ClockedError as e:
            return c, None, str(e)[:200], 0.0
        return c, r, None, cr

    findings, pair_rows, errors = [], [], []
    stopped = None
    with ThreadPoolExecutor(max_workers=workers) as ex:
        try:
            for c, r, err, cr in ex.map(do_compare, cands):
                credits["compare"] += cr
                if err:
                    errors.append({"a": c["a"].cid, "b": c["b"].cid, "error": err})
                    continue
                pr = r["pairs"][0]
                pair_rows.append({"a": c["a"].cid, "b": c["b"].cid, "source": c["source"], "relation": pr["relation"],
                                  "conflicting": pr["probabilities"]["conflicting"], "conflicts": len(pr.get("conflicts", []))})
                for f in pr.get("conflicts", []):
                    fa, fb = f.get("a") or {}, f.get("b") or {}
                    findings.append({
                        "id": finding_id(project, c["a"], c["b"], fa, fb),
                        "project": project, "source": c["source"], "key": c.get("key"),
                        "kind": f.get("kind"), "confidence": f.get("confidence"),
                        "pair_relation": pr["relation"], "pair_conflicting": pr["probabilities"]["conflicting"],
                        "a": side_info(repo, commit, c["a"], fa), "b": side_info(repo, commit, c["b"], fb),
                    })
        except BudgetExceeded as e:
            stopped = str(e)
            log(f"[{project}] stopped: {e}")
    log(f"[{project}] compared {len(pair_rows)} pairs -> {len(findings)} conflict findings")

    # Swap check: /compare is order-sensitive, so ask again with the two
    # passages swapped. A conflict reported in both orders is "confirmed".
    if swap and not stopped:
        flagged = {}
        for f in findings:
            if f["kind"] in REPORTABLE_KINDS:
                flagged.setdefault((f["a"]["cid"], f["b"]["cid"]), []).append(f)

        def do_swap(key):
            a, b = by_cid[key[0]], by_cid[key[1]]
            try:
                r, cr = client.call_cost("compare", compare_payload(b, a))
            except (ClockedError, BudgetExceeded) as e:
                return key, None, 0.0
            return key, r["pairs"][0], cr
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for key, pr, cr in ex.map(do_swap, list(flagged)):
                credits["compare"] += cr
                for f in flagged[key]:
                    if pr is None:
                        f["swap"] = {"error": True, "confirmed": False}
                        continue
                    # in the swapped request our A is the API's b and vice versa
                    hits = []
                    for g in pr.get("conflicts", []):
                        ga, gb = g.get("b") or {}, g.get("a") or {}
                        hits.append({"kind": g.get("kind"), "a_start": ga.get("start"), "b_start": gb.get("start")})
                    f["swap"] = {"relation": pr["relation"], "conflicting": pr["probabilities"]["conflicting"],
                                 "conflicts": len(hits), "confirmed": len(hits) > 0}

    if gate and not stopped:
        def do_gate(f):
            try:
                return f, run_gate(client, f, by_cid)
            except (ClockedError, BudgetExceeded) as e:
                return f, {"error": str(e)[:200], "tested": 0, "any_contradicted": False,
                           "all_contradicted": False, "credits": 0.0}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for f, g in ex.map(do_gate, [f for f in findings if f["kind"] in REPORTABLE_KINDS]):
                f["gate"] = g
                credits["grounding"] += g.get("credits", 0.0)

    if elsewhere and not stopped:
        shortlist = Shortlist(chunks)
        todo = [f for f in findings if tier_of(f) in REPORTED_TIERS]

        def do_else(f):
            try:
                return f, run_elsewhere(client, f, by_cid, shortlist)
            except (ClockedError, BudgetExceeded) as e:
                return f, {"error": str(e)[:200]}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for f, e in ex.map(do_else, todo):
                f["elsewhere"] = e
                credits["rerank"] += e.get("credits", {}).get("rerank", 0.0)
                credits["grounding"] += e.get("credits", {}).get("grounding", 0.0)

    for f in findings:
        f["tier"] = tier_of(f)
    client.save_index()
    return {
        "project": project, "repo": repo, "commit": commit, "pipeline": "v2.1",
        "stats": {
            "files": len({c.path for c in chunks}), "passages": len(chunks), "candidates": cstats,
            "pairs_compared": len(pair_rows), "pair_relations": dict(Counter(p["relation"] for p in pair_rows)),
            "errors": len(errors), "findings": len(findings),
            "cache_hits": client.cache_hits - hits0, "live_calls": client.live_calls - live0,
            "live_credits": client.live_credits - cred0, "credits_by_endpoint": credits,
            "credits_total": sum(credits.values()),
            "seconds": round(time.time() - t0, 1), "stopped": stopped,
        },
        "findings": findings, "pairs": pair_rows, "errors": errors,
    }
