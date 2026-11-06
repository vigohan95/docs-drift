"""Cross-check reports/*.json against review/labels_v2.json and print per-tier counts."""
import glob
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
L = json.loads((ROOT / "review" / "labels_v2.json").read_text(encoding="utf-8"))
seen, total = set(), 0
grand = Counter()
for f in sorted(glob.glob(str(ROOT / "reports" / "*.json"))):
    rep = json.loads(Path(f).read_text(encoding="utf-8"))
    c = Counter()
    for x in rep["findings"]:
        total += 1
        seen.add(x["id"])
        if x["id"] not in L:
            print("UNLABELED", rep["project"], x["id"], x["tier"], x["a"]["path"], x["a"]["line_start"])
        else:
            c[(x["tier"], L[x["id"]]["label"])] += 1
            grand[(x["tier"], L[x["id"]]["label"])] += 1
    print(f"{rep['project']:14s}", {f"{t}/{l}": n for (t, l), n in sorted(c.items())})
print("findings", total, "| labels not in any report:", sorted(set(L) - seen))
print("all:", {f"{t}/{l}": n for (t, l), n in sorted(grand.items())})
