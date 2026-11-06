"""Second candidate path: near-duplicate sentence pairs -> /compare as judge.

Usage: python -X utf8 -m docsdrift.pairrun <project> --pairs 60 --credits 700
"""
from __future__ import annotations

import argparse
import glob
import json

from .client import Clocked, BudgetExceeded, ClockedError, REPO_ROOT, LEDGER
from .neardup import chunk_pairs
from .pipeline import COMPARE_INSTRUCTIONS, RUNS
from .targets import load


def spent_under(prefix: str) -> float:
    total = 0.0
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            if d["tag"].startswith(prefix):
                total += d["credits"]
    return total


def already_compared(project: str) -> set:
    seen = set()
    for f in glob.glob(str(RUNS / project / "pairs-*.json")):
        for p in json.load(open(f, encoding="utf-8")):
            seen.add(tuple(sorted((p["a"], p["b"]))))
    return seen


def select(project: str, chunks, n: int):
    seen = already_compared(project)
    texts = set()
    cross, same = [], []
    for p in chunk_pairs(chunks):
        key = tuple(sorted((p["a"].chunk.cid, p["b"].chunk.cid)))
        tkey = tuple(sorted((p["a"].text.lower(), p["b"].text.lower())))
        if key in seen or tkey in texts:
            continue
        texts.add(tkey)
        (cross if p["a"].chunk.path != p["b"].chunk.path else same).append(p)
    # cross-file restatements first; same-file template siblings last
    return (cross + same)[:n], len(cross), len(same)


def run(project: str, n_pairs: int, credit_cap: float):
    chunks = load(project)
    by_cid = {c.cid: c for c in chunks}
    picked, n_cross, n_same = select(project, chunks, n_pairs)
    print(f"[{project}] near-dup candidates: cross-file {n_cross}, same-file {n_same}; sending {len(picked)}", flush=True)
    client = Clocked(budget=5000, reserve=150)
    prefix = f"{project}-nd/"
    findings, rows = [], []
    for i, p in enumerate(picked):
        if spent_under(prefix) >= credit_cap:
            print(f"[{project}] credit cap reached", flush=True)
            break
        a, b = p["a"].chunk, p["b"].chunk
        tag = f"{prefix}{i:03d}"
        try:
            cmp = client.call("compare", {
                "documents": [{"id": a.cid, "text": a.text}, {"id": b.cid, "text": b.text}],
                "instructions": COMPARE_INSTRUCTIONS, "evidence": "flagged",
            }, tag)
        except BudgetExceeded as e:
            print("budget:", e, flush=True)
            break
        except ClockedError as e:
            rows.append({"i": i, "a": a.cid, "b": b.cid, "error": str(e)[:200]})
            continue
        pr = cmp["pairs"][0]
        rows.append({
            "i": i, "key": "(near-dup)", "a": pr["a"], "b": pr["b"], "relation": pr["relation"],
            "probabilities": pr["probabilities"], "conflicts": len(pr.get("conflicts", [])),
            "duplicates": len(pr.get("duplicates", [])),
            "local": {"sim": p["sim"], "fact_diff": p["fact_diff"],
                      "a_line": p["a"].line, "a_text": p["a"].text[:300],
                      "b_line": p["b"].line, "b_text": p["b"].text[:300],
                      "only_a": p["only_a"][:12], "only_b": p["only_b"][:12]},
        })
        for f in pr.get("conflicts", []):
            fa, fb = f.get("a") or {}, f.get("b") or {}
            ca, cb = by_cid[pr["a"]], by_cid[pr["b"]]
            findings.append({
                "project": project, "key": "(near-dup)", "recording": tag,
                "kind": f.get("kind"), "confidence": f.get("confidence"),
                "pair_relation": pr["relation"], "pair_conflicting_prob": pr["probabilities"].get("conflicting"),
                "a": {"cid": ca.cid, "path": ca.path, "heading": ca.heading,
                      "line": ca.line_of(fa["start"]) if "start" in fa else ca.start_line,
                      "chunk_lines": [ca.start_line, ca.end_line], "quote": fa.get("quote")},
                "b": {"cid": cb.cid, "path": cb.path, "heading": cb.heading,
                      "line": cb.line_of(fb["start"]) if "start" in fb else cb.start_line,
                      "chunk_lines": [cb.start_line, cb.end_line], "quote": fb.get("quote")},
            })
    out = RUNS / project
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings-neardup.json").write_text(json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "pairs-neardup.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{project}] pairs sent {len(rows)}, conflict findings {len(findings)}, credits {spent_under(prefix):.0f}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--pairs", type=int, default=60)
    ap.add_argument("--credits", type=float, default=700)
    a = ap.parse_args()
    run(a.project, a.pairs, a.credits)
