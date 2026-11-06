"""Build the static demo page: docs/index.html (no JavaScript, no remote assets).

    python -X utf8 scripts/build_site.py

docs/ is what GitHub Pages serves ("Deploy from a branch", folder /docs).
Everything on the page comes from files in this repository:
review/defects.json, review/upstream_prs.json, review/labels_v2.json, review/summary.json,
reports/*.json and runs/rerank-ablation.json.
"""
from __future__ import annotations

import difflib
import html
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from docsdrift.targets import TARGETS  # noqa: E402

E = html.escape
HERO = ["fastify-onrequest-body-null", "typeorm-update-bulk-overload", "rtk-setuplisteners-refetchonmount"]
FP_EXAMPLES = ["c1357a057d", "c95bfd8b98", "207557013c", "ba9111191c"]   # one per kind of mistake
VIDEO = "media/docs-drift-demo.mp4"
WORD = re.compile(r"[A-Za-z0-9_]+")


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


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
    no_code = d["source"].startswith("No source file")
    if d["wrong"] is None:
        cls, verdict = "undecided", "the code backs part of each"
    elif d["wrong"] == side:
        cls, verdict = "wrong", "older wording" if no_code else "the code disagrees"
    else:
        cls, verdict = "right", "newer wording" if no_code else "the code agrees"
    body = marked(s["quote"], o["quote"]).split("\n")
    rows = "".join(f'<span class="ln">{s["lines"][0] + i}</span><span class="src">{line or " "}</span>'
                   for i, line in enumerate(body))
    return (f'<div class="pane {cls}">'
            f'<p class="where"><a href="{E(s["url"])}">{E(s["path"])}<span class="colon">:</span>{s["lines"][0]}</a>'
            f'<span class="verdict">{verdict}</span></p>'
            f'<div class="quote" role="group" aria-label="quoted lines">{rows}</div></div>')


def upstream_note(d: dict, prs: dict) -> str:
    for pr in prs["pull_requests"]:
        if d["id"] in pr["defects"]:
            return (f'<span class="meta-item">Upstream: <a href="{E(pr["url"])}">{E(pr["repo"])} #{pr["number"]}</a>, '
                    f'{E(pr["status"])}</span>')
    if d.get("patch"):
        return f'<span class="meta-item">Upstream: patch prepared, not opened yet (<code>upstream-patches/{E(d["patch"])}</code>)</span>'
    return f'<span class="meta-item">{E(d.get("patch_note", ""))}</span>'


def contradiction(d: dict, prs: dict, heading: str = "h3") -> str:
    t = TARGETS[d["project"]]
    return f"""
<article class="contradiction" id="{E(d['id'])}">
  <{heading}>{E(d['title'])} <span class="project">in {E(t['repo'])}</span></{heading}>
  <div class="pair">
    {pane(d, 'a')}
    <div class="seam" aria-hidden="true"><span>≠</span></div>
    {pane(d, 'b')}
  </div>
  <p class="evidence">{E(d['source'])}</p>
  <p class="meta"><span class="meta-item">How it surfaced: {E(d['found_by'])}</span>{upstream_note(d, prs)}</p>
</article>"""


def pct(n: int, d: int) -> str:
    return f"{n} of {d}" + (f" ({round(100 * n / d)}%)" if d else "")


def pr_table(prs: dict, by_id: dict) -> str:
    rows = []
    for pr in prs["pull_requests"]:
        covers = "; ".join(E(by_id[i]["title"]) for i in pr["defects"])
        rows.append(f'<tr><td><a href="{E(pr["url"])}">{E(pr["repo"])} #{pr["number"]}</a></td>'
                    f'<td><span class="status status-{E(pr["status"])}">{E(pr["status"])}</span></td>'
                    f'<td class="num">{len(pr["defects"])}</td><td>{covers}</td></tr>')
    for p in prs["not_opened_yet"]:
        covers = "; ".join(E(by_id[i]["title"]) for i in p["defects"])
        rows.append(f'<tr><td>{E(p["repo"])}</td><td><span class="status status-pending">not opened yet</span></td>'
                    f'<td class="num">{len(p["defects"])}</td><td>{E(p["prepared"])} ready: {covers}</td></tr>')
    return "\n".join(rows)


def project_rows(summary: dict, defects: list) -> str:
    rows = []
    for name, p in summary["projects"].items():
        n_def = sum(1 for d in defects if d["project"] == name)
        role = "scanned after the rule was fixed" if p["group"] == "validation" else "rule tuned here"
        rows.append(
            f"<tr><td><a href=\"https://github.com/{E(p['repo'])}/tree/{E(p['commit'])}\">{E(p['repo'])}</a>"
            f"<span class=\"commit\">{E(p['commit'][:8])}</span></td>"
            f"<td class=\"num\">{p['passages']:,}</td><td class=\"num\">{p['pairs_compared']}</td>"
            f"<td class=\"num\">{p['raw']}</td><td class=\"num\">{p['reported']}</td>"
            f"<td class=\"num strong\">{p['reported_true']}</td><td class=\"num\">{n_def}</td>"
            f"<td class=\"num\">{p['credits']:.0f}</td><td>{role}</td></tr>")
    return "\n".join(rows)


def funnel(steps: list) -> str:
    top = math.log10(steps[0][0])
    cells = []
    for n, label in steps:
        width = max(6, round(100 * math.log10(max(n, 1.5)) / top))
        cells.append(f'<li><b>{n:,}</b><span class="bar" style="width:{width}%"></span><span>{label}</span></li>')
    return '<ol class="funnel">' + "".join(cells) + "</ol>"


def false_positive_items(reports: dict, labels: dict) -> str:
    by_id = {f["id"]: (name, f) for name, rep in reports.items() for f in rep["findings"]}
    out = []
    for fid in FP_EXAMPLES:
        name, f = by_id[fid]
        out.append(
            f"<li><p class=\"fp-where\">{E(TARGETS[name]['repo'])}: "
            f"<a href=\"{E(f['a']['url'])}\">{E(f['a']['path'])}:{f['a']['line_start']}</a> against "
            f"<a href=\"{E(f['b']['url'])}\">{E(f['b']['path'])}:{f['b']['line_start']}</a></p>"
            f"<p class=\"fp-why\">{E(labels[fid]['reason'])}</p></li>")
    return "\n".join(out)


def build() -> str:
    reg, prs = load("review/defects.json"), load("review/upstream_prs.json")
    labels, s = load("review/labels_v2.json"), load("review/summary.json")
    rerank = load("runs/rerank-ablation.json")
    reports = {n: load(f"reports/{n}.json") for n in TARGETS if (ROOT / "reports" / f"{n}.json").exists()}
    defects = reg["defects"]
    by_id = {d["id"]: d for d in defects}
    with_defects = sorted({d["project"] for d in defects})
    none = [n for n in s["projects"] if n not in with_defects]
    a = s["all"]
    n_open = sum(1 for p in prs["pull_requests"] if p["status"] == "open")
    n_merged = sum(1 for p in prs["pull_requests"] if p["status"] == "merged")
    pr_words = f"{n_open} pull request{'s' if n_open != 1 else ''} open upstream" + (f", {n_merged} merged" if n_merged else "")
    listed_std = sum(1 for d in defects if d["found_by"].startswith("standard run"))
    listed_ext = sum(1 for d in defects if d["found_by"].startswith("extended run"))
    rr = {m: {"picked": sum(r[m]["picked"] for r in rerank if not r[m]["skipped"]),
              "stating": sum(r[m]["stating"] for r in rerank if not r[m]["skipped"])} for m in ("rerank", "lexical")}
    judged = [r for r in rerank if r["truth_outlier"] and not r["rerank"]["skipped"]]
    rr_right = sum(1 for r in judged if r["rerank"]["outlier"] == r["truth_outlier"])
    lx_right = sum(1 for r in judged if r["lexical"]["outlier"] == r["truth_outlier"])
    total_credits = sum(p["credits"] for p in s["projects"].values())
    n_fp = a["reported"] - a["reported_true"]
    hero = "\n".join(contradiction(by_id[i], prs, "h2") for i in HERO)
    rest = "\n".join(contradiction(d, prs) for d in defects if d["id"] not in HERO)
    none_list = ", ".join(E(TARGETS[n]["repo"]) for n in none)
    video = ""
    if (ROOT / "docs" / VIDEO).exists():
        video = f"""
<section id="video">
  <h2>Watch it run</h2>
  <video controls preload="metadata" src="{VIDEO}"></video>
</section>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Docs Drift: a review list for documentation that contradicts itself</title>
<meta name="description" content="Docs Drift gives maintainers a short list of places where their documentation contradicts itself, with both passages and line numbers. {len(defects)} defects in {len(with_defects)} real projects, backed by source code. Built on the Clocked API.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<main>
<header class="top">
  <p class="wordmark">Docs Drift</p>
  <h1>A short list of places where a project's documentation contradicts itself, with the evidence.</h1>
  <p class="lede">For maintainers. It reads a project's docs, pairs the passages that restate each other, and uses the Clocked API to pick the pairs worth a person's time. Every item shows both passages with file and line. It is a list to review, not a verdict: about half of it is real ({a['reported_true']} of {a['reported']}, {round(100 * a['reported_true'] / a['reported'])}%), and on four projects it had not seen before, none of its {s['validation']['reported']} items was ({s['validation']['reported_true']} of {s['validation']['reported']}).</p>
  <p class="score">{a['projects']} real projects. {len(defects)} defects backed by source code. {pr_words}.</p>
</header>

<section class="hero" aria-label="Three contradictions">
{hero}
</section>
{video}
<section id="upstream">
  <h2>Where the fixes are</h2>
  <p class="plain">Each contradiction was checked against both passages and the project's source code before a fix was written. The final word belongs to the upstream maintainers. Status as of {E(prs['checked'])}.</p>
  <div class="table-wrap">
  <table class="prs">
    <thead><tr><th>Pull request</th><th>Status</th><th class="num">Defects</th><th>Covers</th></tr></thead>
    <tbody>
{pr_table(prs, by_id)}
    </tbody>
  </table>
  </div>
</section>

<section id="numbers">
  <h2>The numbers, including the bad ones</h2>
  {funnel([(a['pairs_compared'], 'pairs of passages read across ' + str(a['projects']) + ' projects'),
           (a['raw'], 'flagged by <code>/compare</code>'),
           (a['reported'], 'kept for a person to read'),
           (a['reported_true'], 'real contradictions')])}
  <div class="split">
    <p><b>{pct(s['tuning']['reported_true'], s['tuning']['reported'])}</b> on the {s['tuning']['projects']} projects the listing rule was tuned on.</p>
    <p><b>{pct(s['validation']['reported_true'], s['validation']['reported'])}</b> on the {s['validation']['projects']} projects scanned after the rule was fixed.</p>
  </div>
  <p class="plain">Read those two together. The rule that decides what makes the list was chosen on findings from eleven projects and then run unchanged on four more. There it listed eight items and none was real. So this is a tool that saves a maintainer from reading {a['pairs_compared']:,} pairs, not one that can be trusted to be right: about half of what it lists is real, the rate varies a lot between projects, and {len(none)} of {a['projects']} projects produced nothing real.</p>
  <p class="plain">Of the {len(defects)} defects, {listed_std} were on the standard run's list, {listed_ext} came from reading more pairs in three projects, and {len(defects) - listed_std - listed_ext} surfaced in other runs without making the standard list. Each card says which.</p>
  <div class="table-wrap">
  <table>
    <thead><tr><th>Project and commit</th><th class="num">Passages</th><th class="num">Pairs read</th><th class="num">Flagged</th><th class="num">Listed</th><th class="num">Listed and real</th><th class="num">Defects on this page</th><th class="num">Credits</th><th>Role</th></tr></thead>
    <tbody>
{project_rows(s, defects)}
    </tbody>
    <tfoot><tr><td>All {a['projects']}</td><td></td><td class="num">{a['pairs_compared']:,}</td><td class="num">{a['raw']}</td><td class="num">{a['reported']}</td><td class="num strong">{a['reported_true']}</td><td class="num">{len(defects)}</td><td class="num">{total_credits:,.0f}</td><td></td></tr></tfoot>
  </table>
  </div>
</section>

<section id="nothing">
  <h2>Projects where it found nothing real</h2>
  <p class="plain">{len(none)} of {a['projects']}: {none_list}. In most of them it listed nothing. In jest, fiber and pydantic it listed items that turned out not to be contradictions.</p>
</section>

<section id="wrong">
  <h2>What it listed and got wrong</h2>
  <p class="plain">{n_fp} of the {a['reported']} listed items are not contradictions. Four examples, one for each kind of mistake. All {n_fp} are in <code>review/labels_v2.json</code> with the reason.</p>
  <ul class="fps">
{false_positive_items(reports, labels)}
  </ul>
  <p class="plain">It also dropped two real contradictions, because <code>/compare</code> labelled them scope differences: the rollup one on this page, and a second sighting of the MikroORM flush one.</p>
</section>

<section id="how">
  <h2>How it works, and what each Clocked endpoint changes</h2>
  <ol class="steps">
    <li><h3>Find passages that restate each other</h3>
      <p>Local, free. The docs are split at headings. Sentences from different sections that are worded almost alike but not identically become candidate pairs, and so do passages that mention the same option name.</p></li>
    <li><h3>Compare decides which pairs conflict</h3>
      <p>One <code>/compare</code> request per pair. Its conflict spans become the two quoted passages and their line numbers. Its conflict kind decides what happens next: value, version and rule conflicts go on, scope and name differences are dropped. On its own, {pct(a['raw_true'], a['raw'])} of what it flags is real.</p></li>
    <li><h3>Verify and a swapped Compare decide what makes the list</h3>
      <p><code>/grounding</code> checks each side's sentence against the other passage, and <code>/compare</code> is asked again with the passages swapped, because its answer depends on their order. An item is listed only when one of the two agrees. On the tuning findings this took precision from 55% to 85%. On the four later projects it did not help.</p></li>
    <li><h3>Rerank finds where else the fact is stated</h3>
      <p><code>/rerank</code> picks other passages that state the disputed fact, and <code>/grounding</code> checks which side they support, which names the side that is probably stale. With <code>/rerank</code>, {rr['rerank']['stating']} of {rr['rerank']['picked']} picked passages stated the fact, against {rr['lexical']['stating']} of {rr['lexical']['picked']} for a plain word-overlap pick. The side it named came out the same either way: of {len(judged)} real findings where the code settles which side is wrong, {rr_right} were named with <code>/rerank</code> and {lx_right} without, all correctly. So this step helps the reader more than it changes the result.</p></li>
  </ol>
</section>

<section id="all">
  <h2>The other {len(defects) - len(HERO)} defects</h2>
  <p class="plain">Marked words differ between the two passages. Line numbers link to the pinned commit on GitHub.</p>
{rest}
</section>

<section id="limits">
  <h2>Limits</h2>
  <ul class="limits">
    <li>It only sees contradictions between passages that restate each other. A page that is simply wrong, with nothing else to compare it to, is invisible.</li>
    <li>How much it misses is not measured. A spot check of about 50 unlisted pairs found no clear miss.</li>
    <li>Sibling pages confuse it: two releases, two middlewares, the React and the Vue page of one API. Pairs of per-version guides are skipped by file name; the rest still gets through.</li>
    <li>The listing rule was tuned on a small set. The 0 of 8 on later projects is the fairer guide to what to expect.</li>
  </ul>
</section>

<section id="replay">
  <h2>Run it yourself, without a key</h2>
  <p class="plain">Every API answer behind this page is recorded in the repository, so a scan of a project at its pinned commit replays offline and spends no credits.</p>
  <pre class="cmd"><code>python scripts/fetch_targets.py fastify
python -m docsdrift scan ../targets/fastify --offline
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
    out = ROOT / "docs" / "index.html"
    out.write_text(build(), encoding="utf-8", newline="\n")
    print("wrote", out, out.stat().st_size, "bytes")
