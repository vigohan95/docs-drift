"""Build the demo video from the real page render and the real terminal run.

    python video/capture.py <work dir>
    python video/build.py <work dir> <out dir>

Every frame is 1920x1080: the top 930 pixels show the source (the demo page as Chrome rendered it, or the
terminal text exactly as the run printed it), the bottom 150 pixels are a caption bar. Captions never cover
the source. Numbers in captions are filled from review/summary.json, review/defects.json and
review/upstream_prs.json; none is typed into the storyboard.

There is no narration: the video is meant to be understood with the sound off.
Requires ffmpeg on PATH, `pip install pillow`, and the Windows fonts named below.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
W, H = 1920, 1080
BAR = 150                      # caption bar height
VIEW = H - BAR                 # height of the source area
FONT_DIR = Path(os.environ.get("FONT_DIR", "C:/Windows/Fonts"))
UI_B = str(FONT_DIR / "segoeuib.ttf")
UI = str(FONT_DIR / "segoeui.ttf")
MONO = str(FONT_DIR / "consola.ttf")
MONO_B = str(FONT_DIR / "consolab.ttf")
INK, PAGE_BG = (20, 24, 31), (246, 247, 249)
TERM_BG, TERM_FG, TERM_DIM, TERM_HI = (15, 19, 24), (214, 220, 228), (125, 135, 150), (255, 255, 255)
ACCENT = (179, 33, 79)         # the page's "clash" colour, used for highlight boxes
AGREE = (87, 201, 174)


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


def ease(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def facts() -> dict:
    s = json.loads((ROOT / "review" / "summary.json").read_text(encoding="utf-8"))
    reg = json.loads((ROOT / "review" / "defects.json").read_text(encoding="utf-8"))["defects"]
    prs = json.loads((ROOT / "review" / "upstream_prs.json").read_text(encoding="utf-8"))
    open_prs = [p for p in prs["pull_requests"] if p["status"] == "open"]
    return {
        "projects": s["all"]["projects"], "pairs": f"{s['all']['pairs_compared']:,}",
        "listed": s["all"]["reported"], "real": s["all"]["reported_true"],
        "val_projects": s["validation"]["projects"], "val_listed": s["validation"]["reported"],
        "val_real": s["validation"]["reported_true"],
        "defects": len(reg), "defect_projects": len({d["project"] for d in reg}),
        "prs_open": len(open_prs), "prs_defects": sum(len(p["defects"]) for p in open_prs),
        "not_sent": sum(len(p["defects"]) for p in prs["not_opened_yet"]),
    }


# ------------------------------------------------------------------ captions

def caption_bar(text: str) -> Image.Image:
    bar = Image.new("RGB", (W, BAR), INK)
    d = ImageDraw.Draw(bar)
    lines = text.split("\n")
    size = 40
    f = font(UI_B, size)
    while max(d.textlength(l, font=f) for l in lines) > W - 120 and size > 26:
        size -= 2
        f = font(UI_B, size)
    if max(d.textlength(l, font=f) for l in lines) > W - 120:
        sys.exit(f"caption does not fit: {text!r}")
    line_h = int(size * 1.32)
    y = (BAR - line_h * len(lines)) // 2
    for i, l in enumerate(lines):
        col = (255, 255, 255) if i == 0 else (205, 212, 222)
        d.text(((W - d.textlength(l, font=f)) // 2, y + i * line_h), l, font=f, fill=col)
    return bar


# -------------------------------------------------------------------- scenes

class PageScenes:
    def __init__(self, work: Path):
        self.img = Image.open(work / "page.png").convert("RGB")
        meta = json.loads((work / "page.json").read_text(encoding="utf-8"))
        self.rects = meta["rects"]
        assert self.img.width == W, self.img.width
        self.max_y = max(0, self.img.height - VIEW)

    def y_for(self, scene: dict) -> int:
        r = self.rects[scene["at"]]
        return max(0, min(self.max_y, r["y"] - scene.get("top", 34)))

    def frame(self, y: float, scene: dict | None = None, t: float = 0.0) -> Image.Image:
        y = int(round(max(0, min(self.max_y, y))))
        view = self.img.crop((0, y, W, y + VIEW))
        if scene and scene.get("box") and t >= 1.4:
            r = self.rects[scene["box"]]
            d = ImageDraw.Draw(view)
            pad = 10
            box = (r["x"] - pad, r["y"] - y - pad, r["x"] + r["w"] + pad, r["y"] + r["h"] - y + pad)
            alpha = ease((t - 1.4) / 0.4)
            col = tuple(int(PAGE_BG[i] + (ACCENT[i] - PAGE_BG[i]) * alpha) for i in range(3))
            d.rounded_rectangle(box, radius=12, outline=col, width=5)
        return view


class Terminal:
    """Draws the recorded run. The text is term.json; only the pacing of the picture is chosen here."""
    SIZE, LINE_H, LEFT, TOP = 21, 30, 44, 34

    def __init__(self, work: Path, seconds: float):
        self.data = json.loads((work / "term.json").read_text(encoding="utf-8"))
        self.f, self.fb = font(MONO, self.SIZE), font(MONO_B, self.SIZE)
        self.seconds = seconds
        self.lines = [l["text"] for l in self.data["lines"]]
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        self.char_w = probe.textlength("M", font=self.f)
        cols = int((W - 2 * self.LEFT) / self.char_w)
        too_long = [l for l in self.lines if len(l) > cols]
        if too_long:
            sys.exit(f"{len(too_long)} terminal lines are wider than {cols} columns, e.g. {too_long[0][:80]!r}")
        self.rows = (VIEW - self.TOP - 20) // self.LINE_H
        real = self.data["seconds"]
        self.t_type = 1.6                                   # typing the command
        self.t_wait = min(real, 2.4)                        # the run itself, shown at most this long
        self.t_out = self.t_type + self.t_wait + 0.3
        self.t_hold_top = self.t_out + 6.2
        self.t_scroll = 4.0
        self.sped = real / self.t_wait if real > self.t_wait else 1.0

    def frame(self, t: float) -> Image.Image:
        im = Image.new("RGB", (W, VIEW), TERM_BG)
        d = ImageDraw.Draw(im)
        cmd = self.data["show"]
        typed = cmd[: int(len(cmd) * min(1.0, t / self.t_type))]
        prompt = "docs-drift $ "
        d.text((self.LEFT, self.TOP), prompt, font=self.fb, fill=AGREE)
        d.text((self.LEFT + self.char_w * len(prompt), self.TOP), typed, font=self.fb, fill=TERM_HI)
        if t < self.t_type or (t < self.t_out and int(t * 2.5) % 2 == 0):
            x = self.LEFT + self.char_w * (len(prompt) + len(typed))
            d.rectangle((x + 2, self.TOP + 3, x + 2 + self.char_w * 0.9, self.TOP + self.SIZE + 5), fill=TERM_FG)
        if t >= self.t_out:
            total = len(self.lines)
            first = 0
            overflow = max(0, total - (self.rows - 1))
            if t > self.t_hold_top and overflow:
                first = int(round(overflow * ease((t - self.t_hold_top) / self.t_scroll)))
            for i, line in enumerate(self.lines[first: first + self.rows - 1]):
                y = self.TOP + (i + 1) * self.LINE_H
                head = line.strip().startswith(("fastify/fastify @", "This is a list")) or "listed for review" in line \
                    or "pairs of passages read" in line or "flagged by /compare" in line or "passages in" in line
                item = len(line) > 4 and line[:3].strip().rstrip(".").isdigit() and line[3] == "."
                col = TERM_HI if (head or item) else (TERM_DIM if line.strip().startswith("https://") else TERM_FG)
                d.text((self.LEFT, y), line, font=self.fb if (head or item) else self.f, fill=col)
        label = f"real run, offline replay, {self.data['seconds']:.1f} s"
        if self.sped > 1.05 and self.t_type <= t < self.t_out:
            label += f" (shown {self.sped:.1f}x faster)"
        lf = font(UI, 22)
        tw = d.textlength(label, font=lf)
        d.rounded_rectangle((W - tw - 60, VIEW - 54, W - 24, VIEW - 14), radius=8, fill=(32, 38, 47))
        d.text((W - tw - 42, VIEW - 49), label, font=lf, fill=TERM_DIM)
        return im


def card(scene: dict, fx: dict) -> Image.Image:
    im = Image.new("RGB", (W, VIEW), PAGE_BG)
    d = ImageDraw.Draw(im)
    ft, fl, fm = font(UI_B, 96), font(UI, 44), font(MONO_B, 40)
    title = scene["title"]
    mark = 86
    tw = d.textlength(title, font=ft)
    x0 = (W - (mark + 34 + tw)) // 2
    y = 230
    d.rounded_rectangle((x0, y + 22, x0 + mark, y + 22 + mark), radius=14, fill=INK)
    neq = "≠"
    nf = font(UI_B, 64)
    d.text((x0 + (mark - d.textlength(neq, font=nf)) / 2, y + 22 + 2), neq, font=nf, fill=PAGE_BG)
    d.text((x0 + mark + 34, y), title, font=ft, fill=INK)
    y += 190
    for line in scene["lines"]:
        text = line.format(**fx)
        f = fm if text.startswith("github.com") else fl
        d.text(((W - d.textlength(text, font=f)) // 2, y), text, font=f, fill=INK if f is fm else (60, 70, 85))
        y += 64
    return im


# --------------------------------------------------------------------- build

def build(work: Path, out_dir: Path) -> None:
    sb = json.loads((HERE / "storyboard.json").read_text(encoding="utf-8"))
    fps = sb["fps"]
    fx = facts()
    pages = PageScenes(work)
    scenes = sb["scenes"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / sb["output"]
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
         "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         str(out)], stdin=subprocess.PIPE)
    prev_y, prev_tail = None, None
    plan = []
    t_total = 0.0
    for sc in scenes:
        n = int(round(sc["seconds"] * fps))
        term = Terminal(work, sc["seconds"]) if sc["kind"] == "terminal" else None
        caps = sc.get("captions") or [{"from": 0, "text": sc.get("caption", "")}]
        bars = [(c["from"], caption_bar(c["text"].format(**fx))) for c in caps]
        target = pages.y_for(sc) if sc["kind"] == "page" else None
        for i in range(n):
            t = i / fps
            if sc["kind"] == "page":
                y = target if prev_y is None else prev_y + (target - prev_y) * ease(t / 1.1)
                view = pages.frame(y, sc, t)
            elif sc["kind"] == "terminal":
                view = term.frame(t)
            else:
                view = card(sc, fx)
            if prev_tail is not None and sc["kind"] != "page" and t < 0.3:      # short dissolve on a cut
                view = Image.blend(prev_tail, view, ease(t / 0.3))
            elif prev_tail is not None and sc["kind"] == "page" and prev_y is None and t < 0.3:
                view = Image.blend(prev_tail, view, ease(t / 0.3))
            bar = [b for f0, b in bars if f0 <= t][-1]
            frame = Image.new("RGB", (W, H), INK)
            frame.paste(view, (0, 0))
            frame.paste(bar, (0, VIEW))
            ff.stdin.write(frame.tobytes())
            last_view = view
        plan.append({"id": sc["id"], "start": round(t_total, 2), "seconds": sc["seconds"],
                     "captions": [c["text"].format(**fx) for c in caps]})
        t_total += sc["seconds"]
        prev_tail = last_view
        prev_y = target if sc["kind"] == "page" else None
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg failed")
    small = out_dir / sb["output_small"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-vf", "scale=1280:720:flags=lanczos",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(small)], check=True)
    (out_dir / "video-plan.json").write_text(json.dumps({"seconds": t_total, "facts": fx, "scenes": plan}, indent=1),
                                             encoding="utf-8")
    for p in (out, small):
        print(f"{p.name}: {p.stat().st_size / 1e6:.2f} MB")
    print(f"length {t_total:.0f} s, {len(scenes)} scenes")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
