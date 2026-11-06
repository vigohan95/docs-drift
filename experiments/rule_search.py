"""Day 2, experiment 4 (free, offline): which reporting rule works on the 57 labeled
v2.0 findings? Every rule below uses only data already recorded.

This is tuning on seen data and is reported as such. The rule chosen here (v2.1) is
then checked on projects scanned afterwards (experiments/validate_v21.py).
"""
import glob
import json
import re
import sys

sys.path.insert(0, ".")
from docsdrift.filters import version_scoped_pair

L = json.load(open("review/labels_v2.json", encoding="utf-8"))
G2 = {r["id"]: r for r in json.load(open("runs/gate-provenance.json", encoding="utf-8"))}
rows = []
for f in sorted(glob.glob("reports/v2.0/*.json")):
    rep = json.load(open(f, encoding="utf-8"))
    for x in rep["findings"]:
        rows.append({
            "id": x["id"], "project": rep["project"], "label": L[x["id"]]["label"], "defect": L[x["id"]]["defect"],
            "kind": x["kind"], "swap": (x.get("swap") or {}).get("confirmed", False),
            "gate": (x.get("gate") or {}).get("any_contradicted", False), "gate2": G2[x["id"]]["gate2"],
            "version_scoped": version_scoped_pair(x["a"]["path"], x["b"]["path"]),
        })
all_true = sum(1 for r in rows if r["label"] == "true")
all_defects = {r["defect"] for r in rows if r["label"] == "true"}


def score(name, pred):
    sel = [r for r in rows if pred(r)]
    t = sum(1 for r in sel if r["label"] == "true")
    d = {r["defect"] for r in sel if r["label"] == "true"}
    print(f"{name:58s} reported {len(sel):2d}  true {t:2d}  precision {t / len(sel) if sel else 0:6.1%}  "
          f"defects kept {len(d)}/{len(all_defects)}")


VALUE_KINDS = {"value", "date_or_version", "rule_or_condition"}
score("R0 compare only", lambda r: True)
score("R1 value/version/rule kinds only", lambda r: r["kind"] in VALUE_KINDS)
score("R2 R1 + not two version-scoped guides", lambda r: r["kind"] in VALUE_KINDS and not r["version_scoped"])
score("R3 R2 + v2.0 gate", lambda r: r["kind"] in VALUE_KINDS and not r["version_scoped"] and r["gate"])
score("R4 R2 + gate2", lambda r: r["kind"] in VALUE_KINDS and not r["version_scoped"] and r["gate2"])
score("R5 R2 + (gate or swap)", lambda r: r["kind"] in VALUE_KINDS and not r["version_scoped"] and (r["gate"] or r["swap"]))
score("R6 R2 + gate + swap", lambda r: r["kind"] in VALUE_KINDS and not r["version_scoped"] and r["gate"] and r["swap"])
score("   v2.0 gate alone", lambda r: r["gate"])
score("   gate2 alone", lambda r: r["gate2"])
score("   not version-scoped alone", lambda r: not r["version_scoped"])
print()
for r in rows:
    if r["kind"] in VALUE_KINDS and not r["version_scoped"]:
        print(f"  R2 keeps {r['project']:13s} {r['id']} {r['label']:5s} {r['kind']:17s} gate={r['gate']} gate2={r['gate2']} swap={r['swap']}")
