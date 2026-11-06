"""Cost-scaling probes with real fastify chunks."""
import json, sys
from docsdrift.client import Clocked, credits_used
from docsdrift.targets import load, TARGETS_ROOT

c = Clocked(budget=5000)
ch = load("fastify")

def hdr(tag):
    rec = json.load(open(f"recordings/{tag}.json", encoding="utf-8"))
    return rec["round_trip_ms"], rec["response_headers"].get("x-clocked-credits"), rec["response_headers"].get("x-clocked-model-ms")

def summarize(r):
    for p in r["pairs"]:
        if p["relation"] != "unrelated":
            print("  ", p["a"], "|", p["b"], p["relation"], round(p["related"], 3), "conf", len(p["conflicts"]), "dup", len(p["duplicates"]))
            for f in p["conflicts"]:
                qa = (f.get("a") or {}).get("quote"); qb = (f.get("b") or {}).get("quote")
                print("      CONFLICT", f.get("kind"), f.get("confidence"), "\n        A:", repr(qa)[:200], "\n        B:", repr(qb)[:200])

def key_chunks(key, n):
    return [x for x in ch if key in x.text][:n]

def run(tag, docs, **kw):
    payload = {"documents": [{"id": d.cid, "text": d.text} for d in docs], **kw}
    r = c.call("compare", payload, tag)
    print(tag, "docs", len(docs), "chars", sum(len(d.text) for d in docs), "-> round_trip_ms, credits, model_ms:", hdr(tag))
    summarize(r)
    return r

which = sys.argv[1]
if which == "k2":
    run("probe/compare-bodyLimit-2", key_chunks("bodyLimit", 2))
elif which == "k8":
    run("probe/compare-bodyLimit-8", key_chunks("bodyLimit", 8))
elif which == "k20":
    run("probe/compare-bodyLimit-20", key_chunks("bodyLimit", 20))
elif which == "files2":
    a = (TARGETS_ROOT / "fastify/README.md").read_text(encoding="utf-8")
    b = (TARGETS_ROOT / "fastify/docs/Reference/LTS.md").read_text(encoding="utf-8")
    payload = {"documents": [{"id": "README.md", "text": a}, {"id": "docs/Reference/LTS.md", "text": b}]}
    r = c.call("compare", payload, "probe/compare-wholefiles-readme-lts")
    print("chars", len(a) + len(b), hdr("probe/compare-wholefiles-readme-lts"))
    summarize(r)
print("credits used so far:", credits_used())
