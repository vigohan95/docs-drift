"""Day 2, experiment 1: re-test the 15 labeled chunk pairs from day 1 as
two-document /compare requests (a,b), with the order swapped (b,a), and
re-sent unchanged to check that an identical request gives an identical answer."""
import glob, json, sys
sys.path.insert(0, ".")
from docsdrift.client import Clocked
from docsdrift.scan import compare_payload
from docsdrift.targets import TARGETS, load

labels = json.load(open("review/labels.json", encoding="utf-8"))["main_pipeline"]
by_rec = {}
for x in labels:
    by_rec.setdefault((x["project"], x["recording"]), []).append(x)

# recover the chunk ids of every labeled finding from the day-1 run files
found = {}
for p in ["fastify", "prometheus", "vite", "jest", "typeorm"]:
    for f in glob.glob(f"runs/{p}/findings-*.json"):
        if "norerank" in f:
            continue
        for x in json.load(open(f, encoding="utf-8")):
            found.setdefault((p, x["recording"], x["a"]["cid"], x["b"]["cid"]), []).append(x)

client = Clocked()
chunks = {p: {c.cid: c for c in load(p)} for p in ["fastify", "prometheus", "vite", "jest", "typeorm"]}
rows = []
for (p, rec, ca, cb), fs in sorted(found.items()):
    labs = [l["label"] for l in by_rec[(p, rec)]]
    a, b = chunks[p][ca], chunks[p][cb]
    def sig(r):
        pr = r["pairs"][0]
        return (pr["relation"], pr["probabilities"]["conflicting"], len(pr["conflicts"]),
                [(f.get("kind"), (f.get("a") or {}).get("start"), (f.get("b") or {}).get("start")) for f in pr["conflicts"]])
    ab = client.call("compare", compare_payload(a, b))
    ba = client.call("compare", compare_payload(b, a))
    again = client.call("compare", compare_payload(a, b), tag=f"stability/{p}-{len(rows):02d}", force_live=True)
    row = {"project": p, "day1_recording": rec, "a": ca, "b": cb, "day1_labels": labs, "day1_findings": len(fs),
           "ab": sig(ab), "ba": sig(ba), "resend_identical": sig(ab) == sig(again)}
    rows.append(row)
    print(p, rec, labs, "| ab:", row["ab"][:3], "| ba:", row["ba"][:3], "| resend identical:", row["resend_identical"], flush=True)
client.save_index()
json.dump(rows, open("runs/pairwise-labeled.json", "w", encoding="utf-8"), indent=1)
print("live calls", client.live_calls, "credits", client.live_credits, "cache hits", client.cache_hits)
