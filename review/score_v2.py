"""Score the v2.1 reports against review/labels_v2.json and write review/summary.json.

The numbers in the README, the demo page and the tests all come from this file.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from docsdrift.targets import TARGETS, VALIDATION  # noqa: E402

REPORTED = ("confirmed", "likely")
DAY1 = ("fastify", "prometheus", "vite", "jest", "typeorm")


def load():
    labels = json.loads((ROOT / "review" / "labels_v2.json").read_text(encoding="utf-8"))
    reports = {}
    for name in TARGETS:
        f = ROOT / "reports" / f"{name}.json"
        if f.exists():
            reports[name] = json.loads(f.read_text(encoding="utf-8"))
    return labels, reports


def group_of(project: str) -> str:
    return "validation" if project in VALIDATION else "tuning"


def summarize(labels, reports) -> dict:
    per_project, missing = {}, []
    for name, rep in reports.items():
        c = Counter()
        defects, reported_defects = set(), set()
        for f in rep["findings"]:
            lab = labels.get(f["id"])
            if lab is None:
                missing.append((name, f["id"]))
                continue
            c[(f["tier"], lab["label"])] += 1
            if lab["label"] == "true":
                defects.add(lab["defect"])
                if f["tier"] in REPORTED:
                    reported_defects.add(lab["defect"])
        st = rep["stats"]
        per_project[name] = {
            "group": group_of(name), "repo": rep["repo"], "commit": rep["commit"],
            "files": st["files"], "passages": st["passages"], "pairs_compared": st["pairs_compared"],
            "raw": sum(c.values()), "raw_true": sum(n for (t, l), n in c.items() if l == "true"),
            "reported": sum(n for (t, l), n in c.items() if t in REPORTED),
            "reported_true": sum(n for (t, l), n in c.items() if t in REPORTED and l == "true"),
            "confirmed": sum(n for (t, l), n in c.items() if t == "confirmed"),
            "confirmed_true": c[("confirmed", "true")],
            "defects": sorted(defects), "reported_defects": sorted(reported_defects),
            "credits": st["credits_total"],
        }

    def agg(names):
        rows = [per_project[n] for n in names if n in per_project]
        out = {k: sum(r[k] for r in rows) for k in ("pairs_compared", "raw", "raw_true", "reported", "reported_true",
                                                      "confirmed", "confirmed_true", "credits")}
        out["projects"] = len(rows)
        out["projects_with_a_true_finding"] = sum(1 for r in rows if r["raw_true"])
        out["defects"] = sorted({d for r in rows for d in r["defects"]})
        out["reported_defects"] = sorted({d for r in rows for d in r["reported_defects"]})
        for k, num, den in (("precision_raw", "raw_true", "raw"), ("precision_reported", "reported_true", "reported"),
                            ("precision_confirmed", "confirmed_true", "confirmed")):
            out[k] = round(out[num] / out[den], 4) if out[den] else None
        return out

    names = list(per_project)
    return {
        "pipeline": "v2.1",
        "projects": per_project,
        "all": agg(names),
        "tuning": agg([n for n in names if group_of(n) == "tuning"]),
        "validation": agg([n for n in names if group_of(n) == "validation"]),
        "unlabeled": missing,
    }


if __name__ == "__main__":
    labels, reports = load()
    s = summarize(labels, reports)
    (ROOT / "review" / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    for g in ("tuning", "validation", "all"):
        a = s[g]
        print(f"{g:10s} projects {a['projects']:2d} (with a true finding: {a['projects_with_a_true_finding']})  pairs {a['pairs_compared']:4d}  "
              f"raw {a['raw_true']}/{a['raw']} ({a['precision_raw']})  reported {a['reported_true']}/{a['reported']} ({a['precision_reported']})  "
              f"confirmed {a['confirmed_true']}/{a['confirmed']} ({a['precision_confirmed']})  defects {len(a['defects'])} (reported {len(a['reported_defects'])})")
    for n, p in s["projects"].items():
        print(f"  {n:14s} {p['group']:10s} pairs {p['pairs_compared']:3d} raw {p['raw_true']}/{p['raw']} reported {p['reported_true']}/{p['reported']} confirmed {p['confirmed_true']}/{p['confirmed']} credits {p['credits']:.0f}")
    if s["unlabeled"]:
        print("UNLABELED:", s["unlabeled"])
