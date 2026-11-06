"""Checks over the committed recordings, reports and verdicts. No network, no clones needed."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "review"))
import score_v2  # noqa: E402

from docsdrift.client import KEEP_HEADERS, request_hash  # noqa: E402
from docsdrift.targets import TARGETS, VALIDATION  # noqa: E402

RECORDINGS = ROOT / "recordings"
LABELS = json.loads((ROOT / "review" / "labels_v2.json").read_text(encoding="utf-8"))
REPORT_FILES = sorted((ROOT / "reports").glob("*.json")) + sorted((ROOT / "reports" / "extended").glob("*.json")) \
    + sorted((ROOT / "reports" / "both-orders").glob("*.json"))
REPORTS = {str(f.relative_to(ROOT / "reports")).replace("\\", "/"): json.loads(f.read_text(encoding="utf-8")) for f in REPORT_FILES}
ALL_FINDINGS = [(name, f) for name, rep in REPORTS.items() for f in rep["findings"]]


def recordings():
    for f in RECORDINGS.rglob("*.json"):
        if f.name != "index.json":
            yield f, json.loads(f.read_text(encoding="utf-8"))


RECS = list(recordings())


def test_recordings_hold_no_request_headers_and_no_key():
    allowed = {"endpoint", "tag", "request_hash", "recorded_at", "status", "attempts", "round_trip_ms",
               "response_headers", "request", "response"}
    for f, rec in RECS:
        assert set(rec) <= allowed, f
        assert set(rec["response_headers"]) <= set(KEEP_HEADERS), f
        assert "authorization" not in {k.lower() for k in rec["response_headers"]}, f


def test_index_points_at_recordings_with_matching_requests():
    index = json.loads((RECORDINGS / "index.json").read_text(encoding="utf-8"))
    assert len(index) > 2000
    for h, rel in list(index.items())[::25]:
        rec = json.loads((RECORDINGS / rel).read_text(encoding="utf-8"))
        assert request_hash(rec["endpoint"], rec["request"]) == h
        assert rec["status"] in (200, 422)


def test_compare_quotes_are_found_in_the_submitted_passages():
    """Every quote /compare returns is verbatim text of the passage we sent, so line numbers can be exact.
    The offsets themselves are a few characters off in about 2% of the spans; exact_span() corrects that."""
    from docsdrift.scan import exact_span
    checked = shifted = 0
    for f, rec in RECS:
        if rec["endpoint"] != "compare" or rec["status"] != 200:
            continue
        docs = {d["id"]: d["text"] for d in rec["request"]["documents"]}
        for pair in rec["response"].get("pairs", []):
            for finding in pair.get("conflicts", []):
                for side in ("a", "b"):
                    s = finding.get(side) or {}
                    if "start" not in s:
                        continue
                    text = docs[s["document"]]
                    assert s["quote"] in text, f
                    start, end = exact_span(text, s)
                    assert text[start:end] == s["quote"], f
                    checked += 1
                    shifted += text[s["start"]:s["end"]] != s["quote"]
    assert checked > 100
    assert shifted / checked < 0.05


def test_ledger_total_matches_recorded_headers_and_respects_the_reserve():
    rows = [json.loads(l) for l in (RECORDINGS / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    total = sum(r["credits"] for r in rows)
    assert all(r["credits"] >= 0 for r in rows)
    assert total <= 16000          # 20,000 on the account, 4,000 kept for the demo and for judges
    assert {r["endpoint"] for r in rows} == {"compare", "rerank", "grounding"}


def test_failed_calls_were_not_charged():
    rows = [json.loads(l) for l in (RECORDINGS / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert all(r["credits"] == 0 for r in rows if r["status"] != 200)


def test_every_finding_in_every_report_has_a_verdict():
    missing = [(name, f["id"]) for name, f in ALL_FINDINGS if f["id"] not in LABELS]
    assert missing == []


def test_every_verdict_is_used_or_belongs_to_the_v20_snapshot():
    used = {f["id"] for _, f in ALL_FINDINGS}
    v20 = {f["id"] for p in (ROOT / "reports" / "v2.0").glob("*.json")
           for f in json.loads(p.read_text(encoding="utf-8"))["findings"]}
    assert set(LABELS) <= used | v20


def test_true_verdicts_name_a_defect_and_cite_file_lines():
    by_defect = {}
    for fid, lab in LABELS.items():
        assert lab["label"] in ("true", "false")
        if lab["label"] == "true":
            assert lab["defect"], fid
            by_defect.setdefault(lab["defect"], []).append(lab["reason"])
        else:
            assert lab["defect"] is None, fid
    # every defect has at least one verdict that cites file:line on the docs side
    for defect, reasons in by_defect.items():
        assert any(re.search(r"\.(md|mdx):\d+", r) for r in reasons), defect


def test_every_defect_has_source_code_or_history_evidence():
    by_defect = {}
    for lab in LABELS.values():
        if lab["label"] == "true":
            by_defect.setdefault(lab["defect"], []).append(lab["reason"])
    for defect, reasons in by_defect.items():
        text = " ".join(reasons)
        assert re.search(r"\.(js|ts|go|json)\b", text) or defect == "rollup-esm-node-support", defect


def test_finding_links_use_the_pinned_commit_and_lines_inside_the_passage():
    for name, f in ALL_FINDINGS:
        project = f["project"]
        t = TARGETS[project]
        for side in ("a", "b"):
            s = f[side]
            assert s["url"].startswith(f"https://github.com/{t['repo']}/blob/{t['commit']}/{s['path']}#L"), (name, f["id"])
            lo, hi = s["chunk_lines"]
            assert lo <= s["line_start"] <= s["line_end"] <= hi, (name, f["id"])


def test_summary_file_matches_a_fresh_recount():
    labels, reports = score_v2.load()
    fresh = score_v2.summarize(labels, reports)
    stored = json.loads((ROOT / "review" / "summary.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(fresh)) == stored
    assert fresh["unlabeled"] == []


def test_headline_numbers():
    s = json.loads((ROOT / "review" / "summary.json").read_text(encoding="utf-8"))
    assert s["all"]["projects"] == 15
    assert (s["tuning"]["reported_true"], s["tuning"]["reported"]) == (11, 13)
    assert (s["validation"]["reported_true"], s["validation"]["reported"]) == (0, 8)
    assert (s["all"]["reported_true"], s["all"]["reported"]) == (11, 21)
    assert (s["all"]["raw_true"], s["all"]["raw"]) == (13, 52)
    assert set(s["projects"]) - set(VALIDATION) == {n for n in s["projects"] if s["projects"][n]["group"] == "tuning"}


@pytest.mark.parametrize("fid,project,tier", [
    ("2f2b5d9048", "fastify", "confirmed"),
    ("3359c8962b", "fastify", "confirmed"),
    ("ba8d973e45", "fastify", "confirmed"),
    ("c4c048a190", "fastify", "likely"),
    ("29817c707f", "typeorm", "confirmed"),
    ("e0951255dd", "typeorm", "likely"),
    ("d5d9babda2", "prometheus", "confirmed"),
    ("86618b3172", "redux-toolkit", "confirmed"),
    ("0ec974ef3b", "mikro-orm", "likely"),
    ("1a81142d07", "mikro-orm", "likely"),
])
def test_known_true_findings_are_reported(fid, project, tier):
    rep = REPORTS[f"{project}.json"]
    f = next(x for x in rep["findings"] if x["id"] == fid)
    assert LABELS[fid]["label"] == "true"
    assert f["tier"] == tier


@pytest.mark.parametrize("fid,project", [("c4746c62b4", "rollup"), ("8bbae9fd13", "mikro-orm")])
def test_true_findings_the_rule_drops_stay_visible_as_such(fid, project):
    """Two real contradictions are labelled 'scope' by /compare; v2.1 does not report them. Keep that on record."""
    f = next(x for x in REPORTS[f"{project}.json"]["findings"] if x["id"] == fid)
    assert LABELS[fid]["label"] == "true" and f["tier"] == "out_of_scope"


def test_sibling_page_false_positives_are_not_reported():
    vitest = REPORTS["vitest.json"]
    assert len(vitest["findings"]) >= 10
    assert all(f["tier"] in ("out_of_scope", "weak") for f in vitest["findings"])
    assert all(LABELS[f["id"]]["label"] == "false" for f in vitest["findings"])
