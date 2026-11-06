"""Day-1 pipeline: local key index -> /rerank -> /compare.

Usage: python -X utf8 -m docsdrift.pipeline <project> --credits 1200 [--max-keys 60]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .client import Clocked, credits_used, BudgetExceeded, ClockedError, REPO_ROOT
from .local import rank_keys, FAMILIES
from .targets import load

RUNS = REPO_ROOT / "runs"

COMPARE_INSTRUCTIONS = (
    "The documents are sections of the documentation of ONE open-source project at one commit. "
    "Report a conflict only when two sections make incompatible statements about the SAME option, "
    "flag, default value, limit, version requirement, or behavior, for the same product version and scope. "
    "These are NOT conflicts: values of different options; example values in code samples that merely "
    "override a default; statements explicitly scoped to an older version or to migration history; "
    "one section giving more detail than the other; different defaults that the text ties to different "
    "contexts (per-route vs global, dev vs build, agent mode vs server mode)."
)

FAMILY_TOPIC = {
    "@node-version": "the Node.js version that is required or supported",
    "@go-version": "the Go version that is required or supported",
}


def _own_spent(project: str, label: str) -> float:
    """Credits spent under this run's tag prefix (safe with parallel runs)."""
    from .pairrun import spent_under
    return spent_under(f"{project}{label}/")


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:60] or "key"


def rerank_query(key: str) -> tuple[str, str]:
    if key in FAMILIES:
        topic = FAMILY_TOPIC[key]
        return (f"What is {topic}?",
                "A passage answers only if it itself states a concrete version number as a requirement or support statement.")
    return (f"What is the default value, limit, requirement, or documented behavior of `{key}`?",
            f"A passage answers only if it itself states a concrete value, limit, version, or rule for `{key}`. "
            "A passage that only mentions the name, or only uses it in an example without stating a rule, does not answer.")


def run(project: str, credit_cap: float, max_keys: int, max_group: int = 5, use_rerank: bool = True,
        offset: int = 0, instructions: str | None = COMPARE_INSTRUCTIONS, label: str = ""):
    chunks = load(project)
    by_cid = {c.cid: c for c in chunks}
    ranked = rank_keys(chunks)
    client = Clocked(budget=5000, reserve=150)
    start_credits = _own_spent(project, label)
    out_dir = RUNS / project
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_pairs: set[tuple[str, str]] = set()
    findings, pair_rows, key_rows = [], [], []

    for score, key, bearing in ranked[offset:offset + max_keys]:
        spent = _own_spent(project, label) - start_credits
        if spent >= credit_cap:
            print(f"[{project}] credit cap reached ({spent:.0f}/{credit_cap})")
            break
        tag_base = f"{project}{label}/{slug(key)}"
        row = {"key": key, "score": round(score, 2), "local_candidates": [c.cid for c in bearing]}
        kept = bearing
        try:
            if use_rerank:
                q, instr = rerank_query(key)
                rr = client.call("rerank", {
                    "query": q, "instructions": instr,
                    "documents": [{"id": c.cid, "title": f"{c.path} > {c.heading}"[:480], "text": c.text} for c in bearing],
                }, f"{tag_base}.rerank")
                row["rerank"] = [{"id": r["id"], "action": r["action"], "reason": r.get("reason"),
                                  "relevance": r["relevance_score"]} for r in rr["results"]]
                kept = [by_cid[r["id"]] for r in rr["results"] if r["action"] == "use"][:max_group]
            else:
                kept = bearing[:max_group]
            row["kept"] = [c.cid for c in kept]
            new_pairs = {tuple(sorted((a.cid, b.cid))) for i, a in enumerate(kept) for b in kept[i + 1:]} - seen_pairs
            if len(kept) < 2 or not new_pairs:
                row["compare"] = "skipped (fewer than 2 passages state a rule, or pairs already compared)"
                key_rows.append(row)
                continue
            payload = {"documents": [{"id": c.cid, "text": c.text} for c in kept], "evidence": "flagged"}
            if instructions:
                payload["instructions"] = instructions
            cmp = client.call("compare", payload, f"{tag_base}.compare")
        except BudgetExceeded as e:
            print("budget:", e)
            break
        except ClockedError as e:
            row["error"] = str(e)[:300]
            key_rows.append(row)
            print(f"[{project}] {key}: {e}")
            continue

        row["compare"] = {"verdict": cmp.get("verdict"), "pairs": len(cmp["pairs"])}
        for p in cmp["pairs"]:
            pk = tuple(sorted((p["a"], p["b"])))
            first_time = pk not in seen_pairs
            seen_pairs.add(pk)
            pair_rows.append({"key": key, "a": p["a"], "b": p["b"], "relation": p["relation"],
                              "probabilities": p["probabilities"], "conflicts": len(p.get("conflicts", [])),
                              "duplicates": len(p.get("duplicates", [])), "first_time": first_time})
            if not first_time:
                continue
            for f in p.get("conflicts", []):
                fa, fb = f.get("a") or {}, f.get("b") or {}
                ca, cb = by_cid[p["a"]], by_cid[p["b"]]
                findings.append({
                    "project": project, "key": key, "recording": f"{tag_base}.compare",
                    "kind": f.get("kind"), "confidence": f.get("confidence"),
                    "pair_relation": p["relation"], "pair_conflicting_prob": p["probabilities"].get("conflicting"),
                    "a": {"cid": ca.cid, "path": ca.path, "heading": ca.heading,
                          "line": ca.line_of(fa["start"]) if "start" in fa else ca.start_line,
                          "chunk_lines": [ca.start_line, ca.end_line], "quote": fa.get("quote")},
                    "b": {"cid": cb.cid, "path": cb.path, "heading": cb.heading,
                          "line": cb.line_of(fb["start"]) if "start" in fb else cb.start_line,
                          "chunk_lines": [cb.start_line, cb.end_line], "quote": fb.get("quote")},
                })
        key_rows.append(row)
        print(f"[{project}] {key}: local {len(bearing)} -> kept {len(kept)} -> {cmp.get('verdict')} "
              f"(spent {_own_spent(project, label) - start_credits:.0f})")

    # dedupe findings by (chunk pair, quotes)
    uniq, seen = [], set()
    for f in findings:
        sig = (tuple(sorted((f["a"]["cid"], f["b"]["cid"]))), f["a"]["quote"], f["b"]["quote"])
        if sig not in seen:
            seen.add(sig)
            uniq.append(f)
    suffix = f"{label}-k{offset}"
    (out_dir / f"findings{suffix}.json").write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"pairs{suffix}.json").write_text(json.dumps(pair_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"keys{suffix}.json").write_text(json.dumps(key_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{project}] keys processed {len(key_rows)}, pairs compared {len(seen_pairs)}, "
          f"conflict findings {len(uniq)}, credits {_own_spent(project, label) - start_credits:.0f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--credits", type=float, default=300)
    ap.add_argument("--max-keys", type=int, default=40)
    ap.add_argument("--max-group", type=int, default=5)
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--default-instructions", action="store_true")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    run(a.project, a.credits, a.max_keys, a.max_group, use_rerank=not a.no_rerank, offset=a.offset,
        instructions=None if a.default_instructions else COMPARE_INSTRUCTIONS, label=a.label)
