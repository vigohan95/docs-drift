"""The live trial service: every limit and every failure path, offline.

Clocked answers come from the repository's recordings (offline client); GitHub is a fake opener.
"""
import io
import json
import tarfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from docsdrift.client import BudgetExceeded, Clocked
from live.github import GitHubError, fetch_markdown, wanted
from live.server import MAX_BODY, make_handler
from live.service import EXHAUSTED, CappedClient, Limits, LiveError, LiveService

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = json.loads((ROOT / "docs" / "live-examples.json").read_text(encoding="utf-8"))
FIX = Path(__file__).parent / "fixtures" / "mini"
SHA = "0" * 40
LONG_A = "The server listens on port 8080 by default and nothing else is said here."
LONG_B = "The server listens on port 9090 by default and nothing else is said here."


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def mini_files():
    return {p.relative_to(FIX).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(FIX.rglob("*.md"))}


def fake_fetcher(repo, limits):
    return "0000000", mini_files()


def service(tmp_path, clock=None, fetcher=fake_fetcher, **limits):
    return LiveService(Clocked(offline=True), tmp_path / "data", Limits(**limits), fetcher=fetcher,
                       now=clock or Clock(), run_async=False)


# ------------------------------------------------------------------ one pair

@pytest.mark.parametrize("ex", EXAMPLES, ids=[e["label"].split(":")[0] for e in EXAMPLES])
def test_the_three_prefilled_examples_are_listed(tmp_path, ex):
    r = service(tmp_path).check_pair("1.2.3.4", ex["a"]["text"], ex["b"]["text"])
    assert r["ok"] and r["listed"] is True
    assert r["tier"] == ex["recorded"]["tier"] and r["kind"] == ex["recorded"]["kind"]
    assert set(r["compare"]) == {"a_then_b", "b_then_a"}            # both raw /compare answers are returned
    assert r["grounding"] is not None                                 # and the raw /grounding verdicts
    assert r["credits"]["spent_now"] == 0 and r["credits"]["answers_replayed"] == r["credits"]["calls"]
    assert r["credits"]["list_price"] > 0


def test_pair_result_reports_each_endpoints_own_conclusion(tmp_path):
    ex = EXAMPLES[0]
    r = service(tmp_path).check_pair("1.2.3.4", ex["a"]["text"], ex["b"]["text"])
    for order in r["compare"].values():
        assert order["relation"] in ("same", "overlapping", "conflicting", "unrelated")
        assert 0 <= order["conflicting"] <= 1
        assert "_raw" not in order
    verdicts = [v["verdict"] for v in r["grounding"].values() if v]
    assert "contradicted" in verdicts
    assert "undefined" in r["a"]["statement"] and "null" in r["b"]["statement"]


def test_two_short_statements_compare_flags_without_a_span_are_checked_whole(tmp_path):
    a = "A utility used to enable `refetchOnFocus` and `refetchOnReconnect` behaviors."
    b = "A utility used to enable `refetchOnMount` and `refetchOnReconnect` behaviors."
    r = service(tmp_path).check_pair("1.2.3.4", a, b)
    assert r["kind"] == "whole_passage" and r["listed"] is True
    assert "without pointing at a span" in r["note"]


@pytest.mark.parametrize("a,b,needle", [
    ("short", LONG_B, "too short"),
    (LONG_A, "x" * 2401, "too long"),
    (LONG_A, LONG_A + "\n", "identical"),
    (None, LONG_B, "must be text"),
    (LONG_A, 12345, "must be text"),
])
def test_pair_input_is_validated_before_any_api_call(tmp_path, a, b, needle):
    svc = service(tmp_path)
    with pytest.raises(LiveError) as e:
        svc.check_pair("1.2.3.4", a, b)
    assert e.value.status == 400 and needle in e.value.message
    assert svc.client.cache_hits == 0 and svc.client.live_calls == 0


def test_pair_checks_are_rate_limited_per_address(tmp_path):
    clock = Clock()
    svc = service(tmp_path, clock, pair_per_ip_hour=3)
    ex = EXAMPLES[0]
    for _ in range(3):
        svc.check_pair("9.9.9.9", ex["a"]["text"], ex["b"]["text"])
    with pytest.raises(LiveError) as e:
        svc.check_pair("9.9.9.9", ex["a"]["text"], ex["b"]["text"])
    assert e.value.status == 429 and e.value.code == "rate_limited" and e.value.extra["retry_after"] > 0
    svc.check_pair("8.8.8.8", ex["a"]["text"], ex["b"]["text"])       # another address is not affected
    clock.t += 3601
    svc.check_pair("9.9.9.9", ex["a"]["text"], ex["b"]["text"])       # and the window moves on


def spend(svc, credits):
    with svc.ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"endpoint": "compare", "credits": credits}) + "\n")


def test_exhausted_budget_is_said_in_plain_words_not_hidden(tmp_path):
    svc = service(tmp_path, budget=100, pair_credit_cap=60)
    spend(svc, 70)
    assert svc.status()["exhausted"] is True and svc.status()["message"] == EXHAUSTED
    with pytest.raises(LiveError) as e:
        svc.check_pair("1.2.3.4", LONG_A, LONG_B)
    assert e.value.status == 402 and e.value.code == "trial_budget_exhausted"
    assert "replay" in e.value.message and e.value.extra["budget"]["remaining"] == 30
    with pytest.raises(LiveError) as e:
        svc.start_scan("1.2.3.4", "example/mini")
    assert e.value.code == "trial_budget_exhausted"


def test_status_reports_budget_and_limits(tmp_path):
    svc = service(tmp_path, budget=3500)
    spend(svc, 120.5)
    s = svc.status()
    assert s["budget"] == {"total": 3500, "spent": 120.5, "remaining": 3379.5}
    assert s["exhausted"] is False and s["limits"]["passage_chars"] == [20, 2400]


class Meter:
    """A stand-in client that charges 10 credits per call."""

    def __init__(self):
        self.live_credits, self.cache_hits, self.live_calls = 0.0, 0, 0

    def call_cost(self, endpoint, payload, *a, **kw):
        self.live_credits += 10
        self.live_calls += 1
        return {}, 10.0


def test_a_request_cannot_spend_more_than_its_cap():
    capped = CappedClient(Meter(), cap=25, remaining=1000)
    for _ in range(3):                       # 0, 10, 20 spent before each call: allowed
        capped.call_cost("compare", {})
    with pytest.raises(BudgetExceeded):      # 30 spent: over the cap, no fourth call
        capped.call_cost("compare", {})
    assert capped.spent == 30 and capped.inner.live_calls == 3


def test_a_request_stops_when_the_trial_budget_runs_out_midway():
    capped = CappedClient(Meter(), cap=1000, remaining=15)
    capped.call_cost("compare", {})
    capped.call_cost("compare", {})
    with pytest.raises(BudgetExceeded) as e:
        capped.call_cost("compare", {})
    assert "budget is used up" in str(e.value)


def test_access_log_has_no_pasted_text_and_no_key(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOCKED_API_KEY", "sk-test-not-a-real-key-000000000000")
    svc = service(tmp_path)
    secret = "The launch code is 4471 and the default timeout is 30 seconds for every request."
    try:
        svc.check_pair("5.6.7.8", secret, secret.replace("30", "60"))
    except Exception:
        pass                                 # no recording for this pair offline; the log line is what matters
    svc.check_pair("5.6.7.8", EXAMPLES[0]["a"]["text"], EXAMPLES[0]["b"]["text"])
    log = svc.access_log.read_text(encoding="utf-8")
    assert "5.6.7.8" in log and "4471" not in log and "request.body" not in log and "sk-test" not in log
    for path in (tmp_path / "data").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "4471" not in text and "sk-test" not in text


# -------------------------------------------------------------- a repository

def test_scan_of_a_repository_returns_the_list_with_evidence(tmp_path):
    svc = service(tmp_path)
    job = svc.start_scan("1.2.3.4", "example/mini")
    assert job["status"] == "done" and job["ok"]
    r = job["result"]
    assert r["commit"] == "0000000" and r["stats"]["pairs_read"] == 2 and r["stats"]["listed"] == 1
    item = r["items"][0]
    assert item["tier"] == "confirmed" and item["kind"] == "value"
    assert (item["a"]["path"], item["a"]["line_start"]) == ("README.md", 9)
    assert item["b"]["url"] == "https://github.com/example/mini/blob/0000000/docs/configuration.md#L5-L6"
    assert r["credits"]["spent_now"] == 0 and r["credits"]["list_price"] > 0
    assert svc.job(job["job"])["status"] == "done"


@pytest.mark.parametrize("repo", ["", "fastify", "a/b/c", "../etc/passwd", "owner/na me", "http://evil/x", 7, None,
                                  "-bad/name", "owner/" + "x" * 101])
def test_repository_name_is_validated(tmp_path, repo):
    svc = service(tmp_path, fetcher=lambda *a: pytest.fail("must not fetch"))
    with pytest.raises(LiveError) as e:
        svc.start_scan("1.2.3.4", repo)
    assert e.value.status == 400


def test_scans_are_rate_limited_per_address_and_in_total(tmp_path):
    svc = service(tmp_path, scan_per_ip_hour=1, scan_per_hour_total=2)
    svc.start_scan("1.1.1.1", "example/mini")
    with pytest.raises(LiveError) as e:
        svc.start_scan("1.1.1.1", "example/mini")
    assert e.value.code == "rate_limited"
    svc.start_scan("2.2.2.2", "example/mini")
    with pytest.raises(LiveError) as e:
        svc.start_scan("3.3.3.3", "example/mini")      # the global hourly limit
    assert e.value.code == "rate_limited"


@pytest.mark.parametrize("code,needle", [("not_found", "no public repository"), ("github_rate_limited", "rate-limiting"),
                                         ("too_large", "larger than"), ("no_markdown", "No documentation Markdown"),
                                         ("github_unreachable", "could not be reached")])
def test_github_failures_end_the_job_with_a_clear_message(tmp_path, code, needle):
    messages = {"not_found": "GitHub has no public repository with that name.",
                "github_rate_limited": "GitHub is rate-limiting this service right now.",
                "too_large": "The repository archive is larger than 40 MB.",
                "no_markdown": "No documentation Markdown was found.",
                "github_unreachable": "GitHub could not be reached from this service."}

    def failing(repo, limits):
        raise GitHubError(code, messages[code])
    job = service(tmp_path, fetcher=failing).start_scan("1.2.3.4", "example/mini")
    assert job["status"] == "failed" and job["ok"] is False and job["error"] == code and needle in job["message"]


def test_scan_that_runs_out_of_time_says_so_and_keeps_what_it_finished(tmp_path):
    clock = Clock()

    def slow_fetcher(repo, limits):
        clock.t += 500                           # the download alone takes longer than the limit
        return "0000000", mini_files()
    job = service(tmp_path, clock, fetcher=slow_fetcher, job_timeout=150).start_scan("1.2.3.4", "example/mini")
    assert job["status"] == "timed_out" and job["error"] == "timed_out"
    assert "stopped after 150 seconds" in job["message"]
    assert job["result"]["stats"]["pairs_read"] == 0 and job["result"]["items"] == []


def test_an_unexpected_failure_never_leaves_a_job_hanging(tmp_path):
    def broken(repo, limits):
        raise RuntimeError("boom")
    svc = service(tmp_path, fetcher=broken)
    job = svc.start_scan("1.2.3.4", "example/mini")
    assert job["status"] == "failed" and job["error"] == "internal_error" and "boom" not in job["message"]
    svc.fetcher = fake_fetcher
    assert svc.start_scan("4.4.4.4", "example/mini")["status"] == "done"      # the slot was released


def test_queue_is_short_and_says_when_it_is_full(tmp_path):
    svc = service(tmp_path, queue_max=1)
    svc._queued = 1
    with pytest.raises(LiveError) as e:
        svc.start_scan("1.2.3.4", "example/mini")
    assert e.value.status == 429 and e.value.code == "busy"


def test_unknown_job(tmp_path):
    with pytest.raises(LiveError) as e:
        service(tmp_path).job("nope")
    assert e.value.status == 404


# ------------------------------------------------------------------- GitHub

def tarball(files: dict, links=(), top="mini-" + SHA) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            raw = data if isinstance(data, bytes) else data.encode("utf-8")
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
        for name in links:
            info = tarfile.TarInfo(f"{top}/{name}")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
    return buf.getvalue()


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(archive: bytes, sha: str = SHA, seen=None):
    def opener(req, timeout=None):
        url = req.full_url
        if seen is not None:
            seen.append(url)
        if url.startswith("https://api.github.com/repos/"):
            return Resp(sha.encode())
        if url.startswith("https://codeload.github.com/"):
            return Resp(archive)
        raise AssertionError("unexpected host: " + url)
    return opener


def test_fetch_reads_only_documentation_markdown_from_fixed_github_hosts():
    seen = []
    arch = tarball({"README.md": "# Hi\n", "docs/a.md": "A", "docs/guide/b.mdx": "B", "src/index.js": "x",
                    "docs/zh/a.md": "translated", "docs/CHANGELOG.md": "log", "notes.md": "not docs",
                    "docs/img.png": b"\x89PNG", "../escape.md": "x"}, links=["docs/link.md"])
    sha, files = fetch_markdown("owner/mini", Limits(), opener_for(arch, seen=seen))
    assert sha == SHA and sorted(files) == ["README.md", "docs/a.md", "docs/guide/b.mdx"]
    assert seen == ["https://api.github.com/repos/owner/mini/commits/HEAD",
                    f"https://codeload.github.com/owner/mini/tar.gz/{SHA}"]


def test_fetch_applies_file_count_and_size_limits():
    arch = tarball({"README.md": "r" * 50, **{f"docs/{i:03d}.md": "x" * 100 for i in range(30)}, "docs/big.md": "y" * 5000})
    _, files = fetch_markdown("o/r", Limits(max_files=10, max_file_bytes=1000), opener_for(arch))
    assert len(files) == 10 and "docs/big.md" not in files
    _, files = fetch_markdown("o/r", Limits(max_total_bytes=450, max_file_bytes=1000), opener_for(arch))
    assert sum(len(v) for v in files.values()) <= 450


def test_fetch_stops_downloading_an_archive_that_is_too_large():
    arch = tarball({"docs/a.md": "A"}) + b"\0" * 10
    big = tarball({f"src/{i}.bin": bytes([i % 251]) * 20000 for i in range(60)} | {"docs/z.md": "Z"})
    with pytest.raises(GitHubError) as e:
        fetch_markdown("o/r", Limits(max_tarball_bytes=2000), opener_for(big))
    assert e.value.code == "too_large"
    assert fetch_markdown("o/r", Limits(), opener_for(arch))[1] == {"docs/a.md": "A"}


def test_fetch_reports_no_markdown_and_bad_commit_answers():
    with pytest.raises(GitHubError) as e:
        fetch_markdown("o/r", Limits(), opener_for(tarball({"src/a.py": "x"})))
    assert e.value.code == "no_markdown"
    with pytest.raises(GitHubError) as e:
        fetch_markdown("o/r", Limits(), opener_for(b"", sha="<html>not a sha</html>"))
    assert e.value.code == "github_error"


@pytest.mark.parametrize("status,code", [(404, "not_found"), (403, "github_rate_limited"), (429, "github_rate_limited"),
                                         (500, "github_error")])
def test_fetch_maps_github_http_errors(status, code):
    def opener(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, status, "x", {}, None)
    with pytest.raises(GitHubError) as e:
        fetch_markdown("o/r", Limits(), opener)
    assert e.value.code == code


def test_fetch_maps_network_failures():
    def opener(req, timeout=None):
        raise urllib.error.URLError("no route")
    with pytest.raises(GitHubError) as e:
        fetch_markdown("o/r", Limits(), opener)
    assert e.value.code == "github_unreachable"


def test_fetch_refuses_names_that_are_not_owner_slash_repo():
    with pytest.raises(GitHubError):
        fetch_markdown("o/r/../../x", Limits(), lambda *a, **k: pytest.fail("must not open"))


def test_wanted_paths():
    assert wanted("README.md") and wanted("readme.mdx") and wanted("docs/x/y.md") and wanted("website/docs/a.md")
    assert not wanted("CONTRIBUTING.md") and not wanted("src/readme.md") and not wanted("docs/a.txt")
    assert not wanted("docs/../secret.md") and not wanted("docs/i18n/fr/a.md") and not wanted("docs/blog/post.md")


# --------------------------------------------------------------------- HTTP

@pytest.fixture
def http(tmp_path):
    svc = service(tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc, {"https://vigohan95.github.io"}, trust_proxy=True))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", svc
    httpd.shutdown()


def call(url, method="GET", body=None, headers=None):
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, dict(r.headers), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read() or b"{}")


def test_http_status_and_cors_for_the_pages_origin_only(http):
    base, _ = http
    status, headers, body = call(base + "/api/status", headers={"Origin": "https://vigohan95.github.io"})
    assert status == 200 and body["ok"] and headers["Access-Control-Allow-Origin"] == "https://vigohan95.github.io"
    status, headers, _ = call(base + "/api/status", headers={"Origin": "https://evil.example"})
    assert status == 200 and "Access-Control-Allow-Origin" not in headers


def test_http_preflight(http):
    base, _ = http
    status, headers, _ = call(base + "/api/pair", "OPTIONS", headers={"Origin": "https://vigohan95.github.io"})
    assert status == 204 and "POST" in headers["Access-Control-Allow-Methods"]
    status, headers, _ = call(base + "/api/pair", "OPTIONS", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in headers


def test_http_pair_end_to_end_and_client_address_from_the_proxy_header(http):
    base, svc = http
    ex = EXAMPLES[0]
    status, _, body = call(base + "/api/pair", "POST", {"a": ex["a"]["text"], "b": ex["b"]["text"]},
                           {"X-Forwarded-For": "203.0.113.7"})
    assert status == 200 and body["listed"] is True and body["budget"]["total"] == 3500
    assert '"ip": "203.0.113.7"' in svc.access_log.read_text(encoding="utf-8")


def test_http_scan_end_to_end(http):
    base, svc = http
    svc.fetcher = fake_fetcher
    status, _, body = call(base + "/api/scan", "POST", {"repo": "example/mini"})
    assert status == 200 and body["status"] == "done"
    status, _, again = call(base + "/api/scan/" + body["job"])
    assert status == 200 and again["result"]["stats"]["listed"] == 1


@pytest.mark.parametrize("method,path,body,expect", [
    ("POST", "/api/pair", b"not json", 400),
    ("POST", "/api/pair", b"[1,2]", 400),
    ("POST", "/api/pair", {"a": "x", "b": "y"}, 400),
    ("POST", "/api/scan", {"repo": "nope"}, 400),
    ("POST", "/api/nothing", {}, 404),
    ("GET", "/api/scan/unknown", None, 404),
    ("GET", "/", None, 404),
])
def test_http_bad_requests_get_json_errors(http, method, path, body, expect):
    status, _, out = call(http[0] + path, method, body)
    assert status == expect and out["ok"] is False and out["message"]


def test_http_rejects_a_body_that_is_too_large(http):
    status, _, out = call(http[0] + "/api/pair", "POST", b"x" * (MAX_BODY + 1))
    assert status == 413 and out["error"] == "too_large"


def test_http_rate_limit_sets_retry_after(http):
    base, svc = http
    svc.limits.pair_per_ip_hour = 1
    ex = EXAMPLES[0]
    call(base + "/api/pair", "POST", {"a": ex["a"]["text"], "b": ex["b"]["text"]})
    status, headers, out = call(base + "/api/pair", "POST", {"a": ex["a"]["text"], "b": ex["b"]["text"]})
    assert status == 429 and out["error"] == "rate_limited" and int(headers["Retry-After"]) > 0


def test_http_budget_exhausted_is_a_clear_402(http):
    base, svc = http
    spend(svc, 3490)
    status, _, out = call(base + "/api/pair", "POST", {"a": LONG_A, "b": LONG_B})
    assert status == 402 and out["error"] == "trial_budget_exhausted" and "replay" in out["message"]
    _, _, st = call(base + "/api/status")
    assert st["exhausted"] is True and st["budget"]["remaining"] == 10
