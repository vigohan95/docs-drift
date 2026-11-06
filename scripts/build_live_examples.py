"""Write docs/live-examples.json: the three real passage pairs offered in the "Try it live" block.

    python -X utf8 scripts/build_live_examples.py

Each example is the pair of passages exactly as the tool read them in the measured run (so it needs
the pinned clones), plus the answer the live service gives for that pair, replayed from recordings.
The page prefills the passages from this file and, when the live service cannot be reached or its
budget is used up, shows the recorded answer instead and says so.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from docsdrift.client import Clocked  # noqa: E402
from docsdrift.targets import TARGETS, load  # noqa: E402
from live.service import Limits, LiveService  # noqa: E402

EXAMPLES = [("fastify", "2f2b5d9048", "reports/fastify.json", "fastify: request.body in onRequest"),
            ("typeorm", "e0951255dd", "reports/typeorm.json", "typeorm: update() with an array"),
            ("redux-toolkit", "b76f4539ff", "reports/extended/redux-toolkit.json", "redux-toolkit: setupListeners()")]


def main() -> None:
    svc = LiveService(Clocked(offline=True), Path(tempfile.mkdtemp()), Limits(pair_per_ip_hour=100), run_async=False)
    out = []
    for project, fid, report, label in EXAMPLES:
        f = next(x for x in json.loads((ROOT / report).read_text(encoding="utf-8"))["findings"] if x["id"] == fid)
        by = {c.cid: c for c in load(project)}
        a, b = by[f["a"]["cid"]], by[f["b"]["cid"]]
        t = TARGETS[project]
        recorded = svc.check_pair("build", a.text, b.text)
        recorded.pop("budget", None)
        recorded.pop("seconds", None)
        recorded["credits"] = {"list_price": recorded["credits"]["list_price"]}

        def side(c):
            return {"text": c.text, "path": c.path, "lines": [c.start_line, c.end_line],
                    "url": f"https://github.com/{t['repo']}/blob/{t['commit']}/{c.path}#L{c.start_line}-L{c.end_line}"}
        out.append({"id": fid, "label": label, "repo": t["repo"], "a": side(a), "b": side(b), "recorded": recorded})
    path = ROOT / "docs" / "live-examples.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print("wrote", path, [(e["label"], e["recorded"]["listed"], e["recorded"]["tier_words"]) for e in out])


if __name__ == "__main__":
    main()
