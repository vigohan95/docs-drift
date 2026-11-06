"""Ablation of /rerank in the "where else is this said" stage.

For every reported v2.1 finding the stage shortlists 12 passages locally and then either
  (a) lets /rerank pick the passages that state the disputed fact (up to 3), or
  (b) takes the top 3 of the local shortlist as they are (no /rerank).
Each picked passage is then checked with /grounding against both statements.

Measured: how many picked passages really state the fact (agree with one side),
how often the outlier vote matches the side the source code disagrees with, and credits.
"""
import json
import sys
from collections import Counter

sys.path.insert(0, ".")
from docsdrift.client import Clocked
from docsdrift.scan import run_elsewhere, Shortlist, REPORTED_TIERS
from docsdrift.targets import TARGETS, load

L = json.load(open("review/labels_v2.json", encoding="utf-8"))
client = Clocked()
rows = []
for name in TARGETS:
    try:
        rep = json.load(open(f"reports/{name}.json", encoding="utf-8"))
    except FileNotFoundError:
        continue
    todo = [f for f in rep["findings"] if f["tier"] in REPORTED_TIERS]
    if not todo:
        continue
    chunks = load(name)
    by, sl = {c.cid: c for c in chunks}, Shortlist(chunks)
    for f in todo:
        res = {}
        for mode, use in (("rerank", True), ("lexical", False)):
            e = run_elsewhere(client, f, by, sl, use_rerank=use)
            res[mode] = e
        lab = L[f["id"]]
        row = {"id": f["id"], "project": name, "label": lab["label"], "truth_outlier": None}
        if lab["label"] == "true" and lab["source_agrees_with"]:
            row["truth_outlier"] = "b" if lab["source_agrees_with"] == "a" else "a"
        for mode, e in res.items():
            places = e.get("places", [])
            row[mode] = {"skipped": e.get("skipped"), "picked": len(places),
                         "stating": sum(1 for p in places if p["agrees_with"]),
                         "outlier": e.get("outlier"), "credits": sum((e.get("credits") or {}).values()),
                         "rerank_use": sum(1 for r in e.get("rerank", []) if r["action"] == "use")}
        rows.append(row)
        print(name, f["id"], lab["label"], "truth outlier:", row["truth_outlier"], "| rerank:", row["rerank"], "| lexical:", row["lexical"], flush=True)
client.save_index()
json.dump(rows, open("runs/rerank-ablation.json", "w", encoding="utf-8"), indent=1)

for mode in ("rerank", "lexical"):
    ok = [r for r in rows if not r[mode]["skipped"]]
    picked = sum(r[mode]["picked"] for r in ok)
    stating = sum(r[mode]["stating"] for r in ok)
    credits = sum(r[mode]["credits"] for r in ok)
    judged = [r for r in ok if r["truth_outlier"]]
    voted = [r for r in judged if r[mode]["outlier"]]
    right = [r for r in voted if r[mode]["outlier"] == r["truth_outlier"]]
    false_votes = [r for r in ok if r["label"] == "false" and r[mode]["outlier"]]
    print(f"{mode:8s} findings {len(ok)}  passages picked {picked}  of which state the fact {stating}  credits {credits:.0f}  "
          f"| true findings with known right side {len(judged)}: outlier named {len(voted)}, correct {len(right)}  "
          f"| outlier named on false findings {len(false_votes)}")
print("live", client.live_calls, "credits", client.live_credits)
