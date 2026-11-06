"""Print the findings of reports/<project>.json for manual review."""
import json, sys
for p in sys.argv[1:]:
    rep = json.load(open(f"reports/{p}.json", encoding="utf-8"))
    st = rep["stats"]
    print(f"===== {p}: pairs {st['pairs_compared']} findings {st['findings']} errors {st['errors']} credits {st['credits_total']:.0f} live {st['live_credits']:.0f} cands {st['candidates']}")
    for f in rep["findings"]:
        g = f.get("gate") or {}
        sw = f.get("swap") or {}
        print(f"--- {f['id']} [{f['tier']}] {f['kind']} conf={f['confidence']} src={f['source']} swap={sw.get('confirmed')} gate a={(g.get('a') or {}).get('verdict')} b={(g.get('b') or {}).get('verdict')}")
        for s in "ab":
            x = f[s]
            print(f"   {s.upper()} {x['path']}:{x['line_start']}-{x['line_end']} | {(x['statement'] or ('[wide] ' + (x['quote'] or '')[:260]))[:330]}")
        e = f.get("elsewhere") or {}
        for pl in e.get("places", []):
            print(f"      else {pl['path']}:{pl['line']} a={pl['a']} b={pl['b']} agrees={pl['agrees_with']}")
        if e.get("outlier"): print("      outlier:", e["outlier"], e["votes"])
