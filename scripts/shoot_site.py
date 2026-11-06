"""Render docs/index.html in headless Chrome at desktop and phone width and save full-page screenshots.

    python scripts/shoot_site.py <out dir>

Used to check the layout by eye before publishing. Needs `pip install playwright` and Google Chrome.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "docs" / "index.html").as_uri()


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        for name, width, height, scale in (("desktop-1280", 1280, 900, 1), ("phone-390", 390, 844, 2)):
            ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=scale)
            page = ctx.new_page()
            page.goto(PAGE, wait_until="load")
            overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            page.screenshot(path=str(out / f"{name}.png"), full_page=True)
            print(f"{name}: page height {page.evaluate('document.documentElement.scrollHeight')} px, "
                  f"horizontal overflow {overflow} px")
            ctx.close()
        browser.close()


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "shots")
