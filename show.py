"""Print merged findings and near-miss pairs for manual review."""
import json, glob, sys
from collections import Counter
proj = sys.argv[1:] or ["fastify", "prometheus", "vite"]
for p in proj:
    fs, ps = [], []
    for f in sorted(glob.glob(f"runs/{p}/findings-*.json")):
        fs += json.load(open(f, encoding="utf-8"))
    for f in sorted(glob.glob(f"runs/{p}/pairs-*.json")):
        ps += json.load(open(f, encoding="utf-8"))
    print(f"===== {p}: findings {len(fs)}; pairs {len(ps)}", dict(Counter(x['relation'] for x in ps)))
    for f in fs:
        print('---', f['key'], '|', f['kind'], f['confidence'], '| pair', f['pair_relation'], f['pair_conflicting_prob'], '|', f['recording'])
        for s in 'ab':
            print('  ', s, f[s]['path'], 'L', f[s]['line'], f[s]['chunk_lines'], '|', repr(f[s]['quote'])[:500])
    print('  near-miss pairs (conflicting prob >= 0.15, no finding):')
    for x in ps:
        if x['probabilities']['conflicting'] >= 0.15 and x['conflicts'] == 0:
            print('    ', x['key'], x['a'].split(':',1)[1], x['b'].split(':',1)[1], x['relation'], x['probabilities']['conflicting'])
