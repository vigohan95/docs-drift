"""Build the static demo page: site/index.html (no JavaScript needed, no network).

    python -X utf8 site/build.py

Everything on the page comes from files in this repository:
review/defects.json, review/labels_v2.json, review/summary.json, reports/*.json, runs/*.json.
"""
from __future__ import annotations

import difflib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from docsdrift.targets import TARGETS, VALIDATION  # noqa: E402

E = html.escape
REG = json.loads((ROOT / "review" / "defects.json").read_text(encoding="utf-8"))
LABELS = json.loads((ROOT / "review" / "labels_v2.json").read_text(encoding="utf-8"))
SUMMARY = json.loads((ROOT / "review" / "summary.json").read_text(encoding="utf-8"))
REPORTS = {n: json.loads((ROOT / "reports" / f"{n}.json").read_text(encoding="utf-8"))
           for n in TARGETS if (ROOT / "reports" / f"{n}.json").exists()}
RERANK = json.loads((ROOT / "runs" / "rerank-ablation.json").read_text(encoding="utf-8"))
HERO = ["fastify-onrequest-body-null", "rtk-asyncthunk-resolved", "prometheus-st-header-hex"]
TOKEN = re.compile(r"\s+|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


WORD = re.compile(r"[A-Za-z0-9_]+")


def marked(text: str, other: str) -> str:
    """Escape `text` and wrap in <mark> the words that the other passage replaces with different words.

    Only words count (markdown punctuation is ignored, case is ignored), only replacements are
    marked (not words one side simply adds), and long replaced runs are left unmarked.
    """
    a = [(m.group(0).lower(), m.start(), m.end()) for m in WORD.finditer(text)]
    b = [m.group(0).lower() for m in WORD.finditer(other)]
    sm = difflib.SequenceMatcher(None, [w for w, _, _ in a], b, autojunk=False)
    spans = []
    if sm.ratio() >= 0.5:
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "replace" and i2 - i1 <= 4 and j2 - j1 <= 4:
                spans.append((a[i1][1], a[i2 - 1][2]))
    out, pos = [], 0
    for lo, hi in spans:
        out.append(E(text[pos:lo]) + "<mark>" + E(text[lo:hi]) + "</mark>")
        pos = hi
    out.append(E(text[pos:]))
    return "".join(out)


def pane(d: dict, side: str) -> str:
    s, o = d[side], d["b" if side == "a" else "a"]
    wrong = d["wrong"]
    if wrong is None:
        cls, verdict = "undecided", "the code backs part of each"
    elif wrong == side:
        cls, verdict = "wrong", "the code disagrees" if not d["source"].startswith("No source file") else "older wording"
    else:
        cls, verdict = "right", "the code agrees" if not d["source"].startswith("No source file") else "newer wording"
    body = marked(s["quote"], o["quote"]).split("\n")
    rows = "".join(f'<span class="ln">{s["lines"][0] + i}</span><span class="src">{line or " "}</span>'
                   for i, line in enumerate(body))
    return (f'<div class="pane {cls}">'
            f'<p class="where"><a href="{E(s["url"])}">{E(s["path"])}<span class="colon">:</span>{s["lines"][0]}</a>'
            f'<span class="verdict">{verdict}</span></p>'
            f'<div class="quote" role="group" aria-label="quoted lines">{rows}</div></div>')


def contradiction(d: dict, heading: str = "h3", extra: str = "") -> str:
    t = TARGETS[d["project"]]
    patch = ""
    if d.get("patch"):
        patch = f'<span class="meta-item">Fix prepared as a patch: <code>upstream-patches/{E(d["patch"])}</code></span>'
    elif d.get("patch_note"):
        patch = f'<span class="meta-item">{E(d["patch_note"])}</span>'
    return f"""
<article class="contradiction" id="{E(d['id'])}">
  <{heading}>{E(d['title'])} <span class="project">in {E(t['repo'])}</span></{heading}>
  <div class="pair">
    {pane(d, 'a')}
    <div class="seam" aria-hidden="true"><span>≠</span></div>
    {pane(d, 'b')}
  </div>
  <p class="evidence">{E(d['source'])}</p>
  <p class="meta"><span class="meta-item">How it surfaced: {E(d['found_by'])}</span>{patch}{extra}</p>
</article>"""


def pct(n, d):
    return f"{n} of {d}" + (f" ({round(100 * n / d)}%)" if d else "")


def project_rows() -> str:
    rows = []
    for name, p in SUMMARY["projects"].items():
        defects = [d for d in REG["defects"] if d["project"] == name]
        group = "after the rule was fixed" if p["group"] == "validation" else "rule tuned here"
        rows.append(
            f"<tr><td><a href=\"https://github.com/{E(p['repo'])}/tree/{E(p['commit'])}\">{E(p['repo'])}</a>"
            f"<span class=\"commit\">{E(p['commit'][:8])}</span></td>"
            f"<td class=\"num\">{p['passages']}</td><td class=\"num\">{p['pairs_compared']}</td>"
            f"<td class=\"num\">{p['raw']}</td><td class=\"num\">{p['reported']}</td>"
            f"<td class=\"num strong\">{p['reported_true']}</td><td class=\"num\">{len(defects)}</td>"
            f"<td class=\"num\">{p['credits']:.0f}</td><td>{group}</td></tr>")
    return "\n".join(rows)


def false_positive_rows() -> str:
    rows = []
    for name, rep in REPORTS.items():
        for f in rep["findings"]:
            lab = LABELS[f["id"]]
            if f["tier"] in ("confirmed", "likely") and lab["label"] == "false":
                rows.append(
                    f"<li><p class=\"fp-where\"><span class=\"tier\">{f['tier']}</span> in {E(TARGETS[name]['repo'])}: "
                    f"<a href=\"{E(f['a']['url'])}\">{E(f['a']['path'])}:{f['a']['line_start']}</a> against "
                    f"<a href=\"{E(f['b']['url'])}\">{E(f['b']['path'])}:{f['b']['line_start']}</a></p>"
                    f"<p class=\"fp-why\">{E(lab['reason'])}</p></li>")
    return "\n".join(rows)


def build() -> str:
    s = SUMMARY
    by_id = {d["id"]: d for d in REG["defects"]}
    defects = REG["defects"]
    projects_with = sorted({d["project"] for d in defects})
    none = [n for n in s["projects"] if n not in projects_with]
    n_patches = len(list((ROOT / "upstream-patches").glob("*/*.patch")))
    std = sum(1 for d in defects if d["found_by"].startswith("standard run, c") or d["found_by"].startswith("standard run, l"))
    ext = sum(1 for d in defects if d["found_by"].startswith("extended run"))
    other = len(defects) - std - ext
    rr = {m: {"picked": sum(r[m]["picked"] for r in RERANK if not r[m]["skipped"]),
              "stating": sum(r[m]["stating"] for r in RERANK if not r[m]["skipped"]),
              "credits": sum(r[m]["credits"] for r in RERANK if not r[m]["skipped"])} for m in ("rerank", "lexical")}
    judged = [r for r in RERANK if r["truth_outlier"] and not r["rerank"]["skipped"]]
    rr_right = sum(1 for r in judged if r["rerank"]["outlier"] == r["truth_outlier"])
    lx_right = sum(1 for r in judged if r["lexical"]["outlier"] == r["truth_outlier"])
    total_credits = sum(p["credits"] for p in s["projects"].values())
    noise = round(100 * (1 - s["all"]["raw_true"] / s["all"]["pairs_compared"]))
    n_fp = s["all"]["reported"] - s["all"]["reported_true"]
    hero = "\n".join(contradiction(by_id[i], "h2") for i in HERO)
    rest = "\n".join(contradiction(d) for d in defects if d["id"] not in HERO)
    none_list = ", ".join(E(TARGETS[n]["repo"]) for n in none)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Docs Drift: documentation that contradicts itself</title>
<meta name="description" content="Docs Drift finds places where an open-source project's documentation contradicts itself, using the Clocked API. {len(defects)} defects in {len(projects_with)} real projects, each checked against the source code.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<main>
<header class="top">
  <h1>Docs Drift finds the places where a project's documentation contradicts itself.</h1>
  <p class="lede">It read the docs of {s['all']['projects']} open-source projects at pinned commits and surfaced {len(defects)} contradictions in {len(projects_with)} of them. Each one below was checked against both passages and the project's source code, with file and line. The final word belongs to the upstream maintainers. Here are three.</p>
</header>

<section class="hero" aria-label="Three contradictions">
{hero}
</section>

<section id="numbers">
  <h2>The numbers, including the bad ones</h2>
  <div class="figures">
    <p><b>{s['all']['pairs_compared']:,}</b> pairs of passages compared across {s['all']['projects']} projects, one Clocked <code>/compare</code> request per pair.</p>
    <p><b>{pct(s['all']['reported_true'], s['all']['reported'])}</b> findings the standard run reported are real contradictions.</p>
    <p><b>{pct(s['tuning']['reported_true'], s['tuning']['reported'])}</b> on the {s['tuning']['projects']} projects the reporting rule was tuned on.</p>
    <p><b>{pct(s['validation']['reported_true'], s['validation']['reported'])}</b> on the {s['validation']['projects']} projects scanned after the rule was fixed.</p>
  </div>
  <p class="plain">Read the last two together. The rule that decides what to report was chosen on findings from eleven projects and then tried, unchanged, on four more. On those four it reported eight findings and none was real. So the honest summary is: about half of what it reports is a real contradiction, the rate varies a lot between projects, and {len(none)} of {s['all']['projects']} projects produced nothing real at all.</p>
  <p class="plain">Of the {len(defects)} contradictions, {std} were reported by the standard run, {ext} came from scanning more pairs in three projects, and {other} surfaced in other runs without being reported by the standard one. Each card says which.</p>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Project and commit</th><th class="num">Passages</th><th class="num">Pairs compared</th><th class="num">Raw findings</th><th class="num">Reported</th><th class="num">Reported and real</th><th class="num">Contradictions in the list below</th><th class="num">Credits</th><th>Role</th></tr></thead>
    <tbody>
{project_rows()}
    </tbody>
    <tfoot><tr><td>All {s['all']['projects']}</td><td></td><td class="num">{s['all']['pairs_compared']:,}</td><td class="num">{s['all']['raw']}</td><td class="num">{s['all']['reported']}</td><td class="num strong">{s['all']['reported_true']}</td><td class="num">{len(defects)}</td><td class="num">{total_credits:,.0f}</td><td></td></tr></tfoot>
  </table>
  </div>
  <p class="note">Nothing real was found in {none_list}.</p>
</section>

<section id="how">
  <h2>How it works, and what each Clocked endpoint added</h2>
  <ol class="steps">
    <li><h3>Find passages that restate each other</h3>
      <p>Runs locally and costs nothing. The docs are split at headings. Sentences from different sections that are worded almost alike but not identically become candidate pairs, and so do passages that mention the same option name. Every contradiction on this page came from these candidates. Reported unjudged, the list would be {noise}% noise.</p></li>
    <li><h3>Compare: is this pair a conflict?</h3>
      <p>One <code>/compare</code> request per pair. It returns the two conflicting spans and a kind (value, version, rule, scope or name). On its own, {pct(s['all']['raw_true'], s['all']['raw'])} of its findings were real. Two things mattered: the answer changes with the order of the two passages, and with which other passages share the request, so every pair gets its own request and identical requests are replayed from recordings.</p></li>
    <li><h3>Verify: a second opinion</h3>
      <p><code>/grounding</code> checks each side's sentence against the other passage, and <code>/compare</code> is asked again with the passages swapped. A finding is reported when it is a value, version or rule conflict and one of the two checks agrees. On the findings the rule was tuned on, this took precision from 55% to 85%. On the four later projects it did not help: all eight reported findings passed a check and were wrong.</p></li>
    <li><h3>Rerank: where else is this said?</h3>
      <p><code>/rerank</code> picks other passages that state the disputed fact, and <code>/grounding</code> checks which side they agree with, to name the outlier. With <code>/rerank</code>, {rr['rerank']['stating']} of {rr['rerank']['picked']} picked passages stated the fact; taking the top three of a plain word-overlap list gave {rr['lexical']['stating']} of {rr['lexical']['picked']}. The outlier vote came out the same either way ({rr_right} of {len(judged)} named correctly with it, {lx_right} without), so this step is a convenience, not a requirement.</p></li>
  </ol>
</section>

<section id="all">
  <h2>The other {len(defects) - len(HERO)} contradictions</h2>
  <p class="plain">Marked words differ between the two passages. Line numbers link to the pinned commit on GitHub. {n_patches} minimal patches are prepared for upstream, one per contradiction; none has been sent. {E(REG['upstream_search'])}</p>
{rest}
</section>

<section id="wrong">
  <h2>What it reported and got wrong</h2>
  <p class="plain">These {n_fp} findings were reported by the standard run and are not contradictions. Most are two documents written from one template about different things: two releases, two middlewares, two functions.</p>
  <ul class="fps">
{false_positive_rows()}
  </ul>
  <p class="plain">Two real contradictions were found by <code>/compare</code> but not reported, because it labelled them scope differences: the rollup one above, and a second sighting of the MikroORM flush one.</p>
</section>

<section id="limits">
  <h2>Limits</h2>
  <ul class="limits">
    <li>It only sees contradictions between passages that restate each other. A page that is simply wrong, with nothing else to compare it to, is invisible.</li>
    <li>Recall is not measured. A spot check of about 50 unreported pairs found no clear miss.</li>
    <li>Sibling pages confuse it: per-version migration guides, the React and the Vue page of one API, READMEs of two packages. Pairs of per-version guides are skipped by file name; the rest still slips through.</li>
    <li>Every verdict here was reached by reading both passages and the source code, with the tool's help in finding them. Upstream maintainers decide what is actually a bug.</li>
  </ul>
</section>

<section id="replay">
  <h2>Replay it without a key</h2>
  <p class="plain">Every API answer behind this page is recorded in the repository. With the target repositories cloned at the pinned commits, a scan replays offline and spends no credits.</p>
  <pre class="cmd"><code>python scripts/fetch_targets.py fastify
python -m docsdrift target fastify --offline
python -m pytest -q</code></pre>
</section>
</main>
<footer>
  <p>Built for the Clocked Build Challenge on <code>/compare</code>, <code>/grounding</code> and <code>/rerank</code>. Quoted documentation belongs to its projects and is shown under their licenses.</p>
</footer>
</body>
</html>
"""


if __name__ == "__main__":
    out = ROOT / "site" / "index.html"
    out.write_text(build(), encoding="utf-8")
    print("wrote", out, out.stat().st_size, "bytes")
