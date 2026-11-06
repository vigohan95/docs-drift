"""Day 2, experiment 2: run the v2 stages (compare a,b -> swap check -> /grounding gate)
on the 15 labeled day-1 pairs and tabulate which decision rule gives which precision."""
import glob, json, sys
sys.path.insert(0, ".")
from docsdrift.client import Clocked
from docsdrift.scan import analyze
from docsdrift.targets import TARGETS, load

rows = json.load(open("runs/pairwise-labeled.json", encoding="utf-8"))
client = Clocked()
out = []
for p in ["fastify", "prometheus", "vite", "jest", "typeorm"]:
    chunks = load(p)
    by = {c.cid: c for c in chunks}
    cands = [{"a": by[r["a"]], "b": by[r["b"]], "source": "labeled", "day1": r} for r in rows if r["project"] == p]
    rep = analyze(p, chunks, cands, repo=TARGETS[p]["repo"], commit=TARGETS[p]["commit"], client=client, elsewhere=False)
    for f in rep["findings"]:
        out.append(f)
        g = f["gate"]
        print(f["id"], p, f["a"]["path"].split("/")[-1], f["a"]["line_start"], "<>", f["b"]["path"].split("/")[-1], f["b"]["line_start"],
              "| swap", f["swap"]["confirmed"], "| gate a:", (g.get("a") or {}).get("verdict"), "b:", (g.get("b") or {}).get("verdict"))
        print("     A:", f["a"]["statement"]); print("     B:", f["b"]["statement"])
json.dump(out, open("runs/labeled-v2-findings.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("live calls", client.live_calls, "credits", client.live_credits)
