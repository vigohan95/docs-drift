"""Compute precision from review/labels.json and summarise credits from the ledger."""
import json
from collections import Counter

L = json.load(open("review/labels.json", encoding="utf-8"))
main = L["main_pipeline"]
c = Counter(x["label"] for x in main)
print(f"main pipeline findings: {len(main)}  {dict(c)}  precision(true/all) = {c['true']/len(main):.1%}")
pairs = {}
for x in main:
    pairs.setdefault((x["recording"], x["a"].split(":")[0], x["b"].split(":")[0]), []).append(x["label"])
pt = sum(1 for v in pairs.values() if "true" in v)
print(f"unique flagged chunk pairs: {len(pairs)}  with a true contradiction: {pt}  pair precision = {pt/len(pairs):.1%}")
defects = sorted({x["defect"] for x in main if x["label"] == "true"})
print("distinct true defects:", len(defects), defects)
by_proj = Counter(x["project"] for x in main)
true_proj = Counter(x["project"] for x in main if x["label"] == "true")
for p in by_proj:
    print(f"  {p}: findings {by_proj[p]}, true {true_proj[p]}")
abl = L["ablation_no_rerank_extra"]
print("ablation extras:", dict(Counter(x["label"] for x in abl)))
allf = main + abl
ca = Counter(x["label"] for x in allf)
print(f"all runs incl. ablation extras: {len(allf)} findings, precision {ca['true']/len(allf):.1%}")

rows = [json.loads(l) for l in open("recordings/ledger.jsonl", encoding="utf-8")]
tot = sum(r["credits"] for r in rows)
ep = Counter(); n = Counter()
for r in rows:
    ep[r["endpoint"]] += r["credits"]; n[r["endpoint"]] += 1
print(f"credits total {tot:.0f} over {len(rows)} calls:", {k: (n[k], ep[k]) for k in ep})
