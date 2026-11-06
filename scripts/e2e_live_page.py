"""Click through the "Try it live" block in a real browser.

    python scripts/e2e_live_page.py <out dir>                 # local: page and service on 127.0.0.1, recorded answers
    python scripts/e2e_live_page.py <out dir> --deployed      # the published page against the deployed service

Local mode starts the live service with the offline client (recorded Clocked answers, no credits) and a
stand-in GitHub fetcher that serves the fixture tree, serves docs/ over HTTP, and drives headless Chrome:
  1. the status line says the service is live and shows the budget,
  2. "Check this pair" on the prefilled example shows a listed result with both endpoints' raw conclusions,
  3. a repository scan shows progress and then the list,
  4. with the service unreachable, the example falls back to its recorded answer and the block says so.
It also takes screenshots at 1280 and 390 pixels wide and reports horizontal overflow.

Deployed mode does steps 1 and 2 on the real page (one real request). Needs `pip install playwright` and Chrome.
"""
from __future__ import annotations

import functools
import json
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PAGES = "https://vigohan95.github.io/docs-drift/"


def serve(handler) -> tuple[ThreadingHTTPServer, str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def local_stack():
    from docsdrift.client import Clocked
    from live.server import make_handler
    from live.service import Limits, LiveService

    fix = ROOT / "tests" / "fixtures" / "mini"

    def fetcher(repo, limits):
        return "0000000", {p.relative_to(fix).as_posix(): p.read_text(encoding="utf-8") for p in sorted(fix.rglob("*.md"))}

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    docs, docs_url = serve(functools.partial(Quiet, directory=str(ROOT / "docs")))
    svc = LiveService(Clocked(offline=True), Path(tempfile.mkdtemp()), Limits(), fetcher=fetcher)
    api, api_url = serve(make_handler(svc, {docs_url}, trust_proxy=False))
    return docs_url, api_url, (docs, api)


def with_api(page, docs_url: str, api_url: str):
    """Serve the built page with its data-api attribute pointed at `api_url`."""
    def rewrite(route):
        resp = route.fetch()
        body = resp.text()
        import re
        body = re.sub(r'data-api="[^"]*"', f'data-api="{api_url}"', body, count=1)
        route.fulfill(response=resp, body=body)
    page.route(docs_url + "/index.html", rewrite)
    page.goto(docs_url + "/index.html", wait_until="load")


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ROOT / "shots"
    out.mkdir(parents=True, exist_ok=True)
    deployed = "--deployed" in sys.argv
    problems = []

    def check(cond, what):
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            problems.append(what)

    with sync_playwright() as pw:
        # Local mode fetches from one loopback port to another; current Chrome asks for a permission
        # before that, which a headless run cannot grant. The deployed page is public-to-public.
        args = [] if deployed else ["--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests"]
        browser = pw.chromium.launch(channel="chrome", headless=True, args=args)
        if deployed:
            page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
            page.goto(PAGES, wait_until="load")
            page.wait_for_function("!document.querySelector('.live-status').textContent.includes('Checking')", timeout=15000)
            status = page.locator(".live-status").inner_text()
            check(status.startswith("Live."), f"deployed page reaches the service: {status!r}")
            page.locator("text=Check this pair").click()
            page.wait_for_selector(".live-verdict", timeout=90000)
            verdict = page.locator(".live-verdict").inner_text()
            check("Listed for review" in verdict, f"deployed pair check: {verdict!r}")
            print("raw:", page.locator(".live-raw").inner_text().replace("\n", " | ")[:600])
            page.locator("#try").screenshot(path=str(out / "deployed-try.png"))
            browser.close()
            return 1 if problems else 0

        docs_url, api_url, servers = local_stack()
        for name, width, height in (("desktop-1280", 1280, 900), ("phone-390", 390, 844)):
            ctx = browser.new_context(viewport={"width": width, "height": height})
            page = ctx.new_page()
            with_api(page, docs_url, api_url)
            page.wait_for_function("document.querySelector('.live-status').textContent.startsWith('Live.')", timeout=10000)
            check("3,500 of 3,500" in page.locator(".live-status").inner_text(), f"{name}: status shows the budget")
            check(len(page.locator(".live-example").all()) == 3, f"{name}: three example buttons")
            page.locator("text=Check this pair").click()
            page.wait_for_selector(".live-verdict", timeout=20000)
            check("Listed for review: both checks agree" in page.locator(".live-verdict").first.inner_text(), f"{name}: prefilled pair is listed")
            raw = page.locator(".live-raw").inner_text()
            check("/compare, first then second" in raw and "/grounding" in raw and "Credits" in raw, f"{name}: raw conclusions of both endpoints shown")
            page.locator(".live-example").nth(1).click()
            page.locator("text=Check this pair").click()
            page.wait_for_function("document.querySelector('.live-verdict') && document.querySelector('.live-verdict').textContent.includes('one check agrees')", timeout=20000)
            check(True, f"{name}: second example gives its own answer")
            page.locator("#live-repo").fill("example/mini")
            page.locator("text=Scan this repository").click()
            page.wait_for_selector(".live-item", timeout=30000)
            scan = page.locator("#live .live-out").nth(1).inner_text()
            check("2 pairs read" in scan and "1 listed for review" in scan and "README.md:9" in scan, f"{name}: repository scan shows the list")
            page.locator("#live-repo").fill("not a repo")
            page.locator("text=Scan this repository").click()
            page.wait_for_function("document.querySelectorAll('#live .live-out')[1].textContent.includes('owner/name')", timeout=10000)
            check(True, f"{name}: a bad repository name gets a clear message")
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(overflow == 0, f"{name}: no horizontal overflow ({overflow} px)")
            page.screenshot(path=str(out / f"live-{name}.png"), full_page=True)
            page.locator("#try").screenshot(path=str(out / f"live-block-{name}.png"))
            ctx.close()

        # the service goes away: the example falls back to its recording and says so
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        with_api(page, docs_url, "http://127.0.0.1:9")
        page.wait_for_function("document.querySelector('.live-status').textContent.includes('cannot be reached')", timeout=15000)
        check(page.locator("#live-repo").is_disabled(), "unreachable: the repository box is disabled")
        page.locator("text=Check this pair").click()
        page.wait_for_selector(".live-verdict", timeout=10000)
        note = page.locator(".live-note").first.inner_text()
        check("recorded answer" in note, f"unreachable: falls back to the recording and says so: {note!r}")
        page.locator("#try").screenshot(path=str(out / "live-block-unreachable.png"))

        # as built, with no service configured
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.goto(docs_url + "/index.html", wait_until="load")
        built_api = page.locator("#live").get_attribute("data-api")
        text = page.locator(".live-status").inner_text()
        check(bool(built_api) or "not running" in text, f"as built (data-api={built_api!r}): {text[:70]!r}")
        if not built_api:
            check(page.locator("#live-repo").count() == 0, "as built without a service: no repository box is offered")
            page.locator(".live-btn").first.click()
            page.wait_for_selector(".live-verdict", timeout=10000)
            check("recorded answer" in page.locator(".live-note").first.inner_text(), "as built without a service: the example shows its recording")
            page.locator("#try").screenshot(path=str(out / "live-block-as-built.png"))

        # JavaScript off: the rest of the page is intact
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, java_script_enabled=False)
        page = ctx.new_page()
        page.goto(docs_url + "/index.html", wait_until="load")
        check(page.locator("article.contradiction").count() == 16, "no JavaScript: all sixteen defects are still on the page")
        check("needs JavaScript" in page.locator("#try").inner_text(), "no JavaScript: the block says it needs it")
        browser.close()
        for s in servers:
            s.shutdown()
    print("RESULT:", "all checks passed" if not problems else f"{len(problems)} failed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
