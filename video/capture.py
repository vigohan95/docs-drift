"""Capture the two real sources of the demo video.

    python video/capture.py <work dir>

1. page.png + page.json: docs/index.html rendered by headless Chrome at 1280 CSS pixels wide and a device scale
   factor of 1.5, so the full-page screenshot is 1920 pixels wide. page.json holds the on-page rectangle of every
   element the storyboard refers to, so scenes are tied to elements, not to pixel numbers.
2. term.json: the command in the storyboard, run for real in the repository, with its output and timing. The
   terminal picture in the video is drawn from this text and nothing else.

Needs `pip install playwright` and Google Chrome. The scan in step 2 is an offline replay: no key, no credits.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCALE = 1.5
CSS_WIDTH = 1280


def capture_page(work: Path, selectors: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": CSS_WIDTH, "height": 800}, device_scale_factor=SCALE,
                                  color_scheme="light")
        page = ctx.new_page()
        page.goto((ROOT / "docs" / "index.html").as_uri(), wait_until="load")
        rects = {}
        for sel in selectors:
            box = page.locator(sel).first.bounding_box()
            if box is None:
                sys.exit(f"storyboard refers to {sel!r}, which is not on the page")
            y = page.evaluate("window.scrollY")
            rects[sel] = {k: round(v * SCALE) for k, v in
                          {"x": box["x"], "y": box["y"] + y, "w": box["width"], "h": box["height"]}.items()}
        height = page.evaluate("document.documentElement.scrollHeight")
        page.screenshot(path=str(work / "page.png"), full_page=True)
        browser.close()
    (work / "page.json").write_text(json.dumps({"scale": SCALE, "css_width": CSS_WIDTH,
                                                "height": round(height * SCALE), "rects": rects}, indent=1),
                                    encoding="utf-8")
    print(f"page.png: 1920 x {round(height * SCALE)}; {len(rects)} elements located")


def capture_terminal(work: Path, show: str, argv: list[str]) -> None:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env.pop("CLOCKED_API_KEY", None)                       # a replay needs no key; make sure none is used
    env["CLOCKED_ENV_FILE"] = str(work / "no-such.env")
    cmd = [sys.executable if a == "{python}" else a for a in argv]
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", bufsize=1)
    lines = []
    for line in proc.stdout:
        lines.append({"t": round(time.time() - t0, 3), "text": line.rstrip("\n")})
    code = proc.wait()
    data = {"show": show, "argv": argv, "exit": code, "seconds": round(time.time() - t0, 2),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "lines": lines}
    (work / "term.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"term.json: exit {code}, {len(lines)} lines, {data['seconds']} s")
    if code != 0:
        sys.exit("the command failed; fetch the target first: python scripts/fetch_targets.py fastify")


def main() -> None:
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "video" / "work"
    work.mkdir(parents=True, exist_ok=True)
    sb = json.loads((HERE / "storyboard.json").read_text(encoding="utf-8"))
    selectors = []
    for scene in sb["scenes"]:
        for key in ("at", "box", "to"):
            if scene.get(key) and scene[key] not in selectors:
                selectors.append(scene[key])
    capture_page(work, selectors)
    capture_terminal(work, sb["terminal"]["show"], sb["terminal"]["run"])


if __name__ == "__main__":
    main()
