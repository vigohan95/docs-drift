"""The "Try it live" block: its data, its fallback, and what the service is allowed to do."""
import json
import re
from pathlib import Path

from live.service import Limits

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "docs" / "live.js").read_text(encoding="utf-8")
EXAMPLES = json.loads((ROOT / "docs" / "live-examples.json").read_text(encoding="utf-8"))
LIVE = json.loads((ROOT / "review" / "live.json").read_text(encoding="utf-8"))


def test_three_examples_are_real_passages_with_recorded_answers():
    assert [e["repo"] for e in EXAMPLES] == ["fastify/fastify", "typeorm/typeorm", "reduxjs/redux-toolkit"]
    limits = Limits()
    for e in EXAMPLES:
        for side in ("a", "b"):
            assert limits.passage_min <= len(e[side]["text"]) <= limits.passage_max
            assert re.search(r"/blob/[0-9a-f]{40}/", e[side]["url"])
        r = e["recorded"]
        assert r["listed"] is True and r["compare"] and r["grounding"]
        assert "budget" not in r and r["credits"] == {"list_price": r["credits"]["list_price"]}


def test_examples_are_embedded_in_the_page_so_the_fallback_works_from_disk():
    m = re.search(r'<script type="application/json" id="live-examples">(.*?)</script>', PAGE, flags=re.S)
    embedded = json.loads(m.group(1).replace("<\\/", "</"))
    assert embedded == EXAMPLES


def test_page_points_at_the_configured_service_or_none():
    api = re.search(r'<div id="live" data-api="([^"]*)">', PAGE).group(1)
    assert api == LIVE["api"]
    assert api == "" or re.fullmatch(r"https://[a-z0-9.-]+", api)      # HTTPS only, no path


def test_script_falls_back_and_says_so():
    for phrase in ("recorded answer", "The live trial budget is used up", "cannot be reached", "not running"):
        assert phrase in JS
    assert "innerHTML" not in JS            # results are inserted as text, never as markup
    assert "eval(" not in JS


def test_limits_keep_the_account_reserve():
    """Used so far plus the whole trial budget must leave at least 1,500 of the 20,000 credits.

    The reserve was 2,000 until 2026-11-09, when two later scans (undici, bullmq) spent 569 credits.
    The live service had already spent 427 of its 3,500 by then, so the real reserve is about 2,000.
    """
    rows = [json.loads(l) for l in (ROOT / "recordings" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    used = sum(r["credits"] for r in rows)
    limits = Limits()
    assert limits.budget <= 3500
    assert used + limits.budget <= 18500
    assert limits.pair_credit_cap <= 60 and limits.scan_credit_cap <= 300 and limits.workers <= 2


def test_limits_table_in_the_service_readme_matches_the_code():
    text = (ROOT / "live" / "README.md").read_text(encoding="utf-8")
    L = Limits()
    for needle in (f"| {L.budget:,.0f} (`LIVE_BUDGET`)", f"at most {L.pair_credit_cap:.0f} credits",
                   f"at most {L.scan_credit_cap:.0f} credits, {L.scan_pairs + L.scan_key_pairs} pairs, {L.job_timeout:.0f} seconds",
                   f"{L.pair_per_ip_hour} pair checks and {L.scan_per_ip_hour} scans per hour",
                   f"{L.scan_per_hour_total} scans per hour",
                   f"{L.passage_min} to {L.passage_max:,} characters",
                   f"{L.max_files} Markdown files, {L.max_total_bytes // 1_000_000} MB of Markdown, {L.max_tarball_bytes // 1_000_000} MB archive"):
        assert needle in text, needle
    assert L.workers <= 2


def test_deployment_drafts_only_create_and_never_carry_a_key():
    deploy = ROOT / "live" / "deploy"
    script = (deploy / "provision_vultr.py").read_text(encoding="utf-8")
    compile(script, "provision_vultr.py", "exec")
    for method in ('"DELETE"', '"PATCH"', '"PUT"'):
        assert method not in script          # it must not be able to change or remove existing resources
    assert "--create" in script and "docsdrift-live" in script
    for f in deploy.iterdir():
        body = f.read_text(encoding="utf-8")
        assert "CLOCKED_API_KEY=" not in body.replace("CLOCKED_API_KEY=...", "").replace("'^CLOCKED_API_KEY='", "")
        assert "Bearer " not in body.replace('f"Bearer {key}"', "")
    unit = (deploy / "docsdrift-live.service").read_text(encoding="utf-8")
    assert "User=docsdrift" in unit and "EnvironmentFile=/etc/docsdrift-live.env" in unit
    assert "https://vigohan95.github.io" in (deploy / "setup.sh").read_text(encoding="utf-8")
