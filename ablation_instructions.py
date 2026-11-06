"""Ablation: re-run /compare with DEFAULT instructions on (a) every chunk pair
that produced a conflict finding with our custom instructions and (b) a fixed
sample of near-dup pairs that produced none. Shows what the instructions change."""
import glob, json, random
from docsdrift.client import Clocked
from docsdrift.targets import TARGETS, load

client = Clocked(budget=5000, reserve=150)
rows = []
for p in TARGETS:
    by_cid = {c.cid: c for c in load(p)}
    flagged = set()
    for f in glob.glob(f"runs/{p}/findings-*.json"):
        for x in json.load(open(f, encoding="utf-8")):
            flagged.add(tuple(sorted((x["a"]["cid"], x["b"]["cid"]))))
    unflagged = []
    for x in json.load(open(f"runs/{p}/pairs-neardup.json", encoding="utf-8")):
        if x.get("conflicts") == 0 and tuple(sorted((x["a"], x["b"]))) not in flagged:
            unflagged.append(tuple(sorted((x["a"], x["b"]))))
    random.Random(7).shuffle(unflagged)
    for kind, pairs in (("flagged", sorted(flagged)), ("unflagged", unflagged[:4])):
        for i, (a, b) in enumerate(pairs):
            r = client.call("compare", {"documents": [{"id": a, "text": by_cid[a].text}, {"id": b, "text": by_cid[b].text}],
                                        "evidence": "flagged"}, f"ablate-default/{p}-{kind}-{i:02d}")
            pr = r["pairs"][0]
            rows.append({"project": p, "set": kind, "a": a, "b": b, "relation": pr["relation"],
                         "conflicting": pr["probabilities"]["conflicting"], "conflicts": len(pr["conflicts"]),
                         "quotes": [[(f.get("a") or {}).get("quote", "")[:120], (f.get("b") or {}).get("quote", "")[:120], f.get("kind")] for f in pr["conflicts"]]})
            print(p, kind, a.split(":", 1)[1], b.split(":", 1)[1], pr["relation"], len(pr["conflicts"]), flush=True)
json.dump(rows, open("runs/ablation-default-instructions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
