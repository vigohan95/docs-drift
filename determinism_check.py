"""Re-send two recorded requests unchanged (new Idempotency-Key) and diff the verdicts."""
import json
from docsdrift.client import Clocked
c = Clocked(budget=5000, reserve=100)
for tag in ["fastify/loggerInstance.compare", "typeorm-nd/011", "jest-nd/052"]:
    rec = json.load(open(f"recordings/{tag}.json", encoding="utf-8"))
    new = c.call(rec["endpoint"], rec["request"], f"determinism/{tag.replace('/', '_')}")
    def sig(r):
        return [(p["a"].split(":", 1)[1], p["b"].split(":", 1)[1], p["relation"], p["probabilities"]["conflicting"], len(p["conflicts"])) for p in r["pairs"]]
    print(tag, "\n  old:", sig(rec["response"]), "\n  new:", sig(new), "\n  identical:", sig(rec["response"]) == sig(new))
