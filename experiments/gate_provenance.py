"""Day 2, experiment 3 (after seeing the v2.0 results): does the /grounding gate get
better when it is told where each passage comes from?

v2.0 gate : claim text vs bare passage text.
gate2     : the passage carries a "[File | Section]" header and the instructions say
            which file and section the claim comes from, and that passages about a
            different package, framework, class, hook, option, file format or released
            version are "not stated".

Scored against review/labels_v2.json on all 57 v2.0 findings. This is tuning on seen
data; the held-out check is experiments/validate_v21.py on projects scanned afterwards.
"""
import glob
import json
import sys
from collections import Counter

sys.path.insert(0, ".")
from docsdrift.client import Clocked
from docsdrift.scan import gate2_payload
from docsdrift.targets import TARGETS, load

L = json.load(open("review/labels_v2.json", encoding="utf-8"))
client = Clocked()
rows = []
for f in sorted(glob.glob("reports/v2.0/*.json")):
    rep = json.load(open(f, encoding="utf-8"))
    if not rep["findings"]:
        continue
    by = {c.cid: c for c in load(rep["project"])}
    for x in rep["findings"]:
        res = {}
        for side, other in (("a", "b"), ("b", "a")):
            claim = x[side]["statement"]
            if not claim:
                continue
            g = client.call("grounding", gate2_payload(claim, by[x[side]["cid"]], by[x[other]["cid"]]))
            res[side] = (g.get("claims") or [{}])[0].get("verdict")
        any2 = any(v == "contradicted" for v in res.values())
        rows.append({"id": x["id"], "project": rep["project"], "label": L[x["id"]]["label"], "tier_v20": x["tier"],
                     "swap": (x.get("swap") or {}).get("confirmed", False), "kind": x["kind"],
                     "gate_v20": (x.get("gate") or {}).get("any_contradicted", False), "gate2": any2, "gate2_sides": res})
        print(rep["project"], x["id"], L[x["id"]]["label"], "v2.0 gate:", rows[-1]["gate_v20"], "| gate2:", any2, res, flush=True)
client.save_index()
json.dump(rows, open("runs/gate-provenance.json", "w", encoding="utf-8"), indent=1)


def score(name, pred):
    sel = [r for r in rows if pred(r)]
    t = sum(1 for r in sel if r["label"] == "true")
    all_true = sum(1 for r in rows if r["label"] == "true")
    print(f"{name:42s} reported {len(sel):2d}  true {t:2d}  precision {t / len(sel) if sel else 0:.1%}  kept {t}/{all_true} true findings")


score("compare only", lambda r: True)
score("v2.0 gate", lambda r: r["gate_v20"])
score("gate2 (with provenance)", lambda r: r["gate2"])
score("gate2 and swap-confirmed", lambda r: r["gate2"] and r["swap"])
score("gate2, no pair_level", lambda r: r["gate2"] and r["kind"] != "pair_level")
print("live", client.live_calls, "credits", client.live_credits)
