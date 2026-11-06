"""Control experiment (no API calls): what the local-only methods report."""
import glob, json
from docsdrift.targets import TARGETS, load
from docsdrift.local import baseline_flags, rank_keys
from docsdrift.neardup import chunk_pairs

TRUE = {  # chunk pairs manually confirmed as true contradictions (see REVIEW.md)
    "fastify": [("docs/Reference/Server.md", 366, "docs/Reference/Logging.md", 223),
                ("docs/Reference/TypeScript.md", 1550, "docs/Reference/Hooks.md", 104),
                ("docs/Reference/Hooks.md", 240, "docs/Reference/TypeScript.md", 1588),
                ("docs/Reference/Hooks.md", 73, "docs/Reference/TypeScript.md", 1540),
                ("docs/Reference/Server.md", 1667, "docs/Reference/TypeScript.md", 1103),
                ("docs/Reference/Routes.md", 34, "docs/Reference/TypeScript.md", 1103)],
    "typeorm": [("docs/docs/working-with-entity-manager/5-entity-manager-api.md", 190,
                 "docs/docs/working-with-entity-manager/6-repository-api.md", 154),
                ("README.md", 19, "docs/docs/getting-started.md", 5)],
}

def chunk_at(chunks, path, line):
    for c in chunks:
        if c.path == path and c.start_line <= line <= c.end_line:
            return c.cid

out = {}
for p in TARGETS:
    chunks = load(p)
    flags = baseline_flags(chunks)
    cp = chunk_pairs(chunks)
    nd_rank = {tuple(sorted((x["a"].chunk.cid, x["b"].chunk.cid))): i for i, x in enumerate(cp)}
    cross = [x for x in cp if x["a"].chunk.path != x["b"].chunk.path]
    keyrows = []
    for f in glob.glob(f"runs/{p}/keys-*.json"):
        keyrows += json.load(open(f, encoding="utf-8"))
    n_local = sum(len(r["local_candidates"]) for r in keyrows)
    n_kept = sum(len(r.get("kept", [])) for r in keyrows)
    pairs_local = sum(len(r["local_candidates"]) * (len(r["local_candidates"]) - 1) // 2 for r in keyrows)
    pairs_kept = sum(len(r.get("kept", [])) * (len(r.get("kept", [])) - 1) // 2 for r in keyrows)
    print(f"== {p}: default-extractor flags {len(flags)}; near-dup sentence pairs {len(cp)} (cross-file {len(cross)})")
    print(f"   key path: {len(keyrows)} keys, local candidate passages {n_local} -> rerank kept {n_kept}; "
          f"pairs if all compared {pairs_local} -> pairs after rerank {pairs_kept}")
    for fl in flags:
        print("     flag", fl["key"], fl["values"][:5], [(s["path"], s["line"], s["value"]) for s in fl["sites"][:4]])
    for (pa, la, pb, lb) in TRUE.get(p, []):
        a, b = chunk_at(chunks, pa, la), chunk_at(chunks, pb, lb)
        k = tuple(sorted((a, b)))
        in_flags = [fl["key"] for fl in flags if {a, b} <= {s["cid"] for s in fl["sites"]}]
        keys_both = [r["key"] for r in keyrows if a in r["local_candidates"] and b in r["local_candidates"]]
        keys_kept = [r["key"] for r in keyrows if a in r.get("kept", []) and b in r.get("kept", [])]
        print(f"   TRUE {pa}:{la} <> {pb}:{lb}: near-dup rank {nd_rank.get(k)}; default-extractor {in_flags}; "
              f"key-path local {keys_both}; kept by rerank {keys_kept}")
