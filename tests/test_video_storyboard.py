"""The video storyboard carries no hand-typed numbers and stays within the allowed length."""
import json
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = re.compile("[{][a-z_]+[}]")
SB = json.loads((ROOT / "video" / "storyboard.json").read_text(encoding="utf-8"))


def captions():
    for sc in SB["scenes"]:
        for c in sc.get("captions") or [{"text": sc.get("caption", "")}]:
            yield sc["id"], c["text"]
        for line in sc.get("lines", []):
            yield sc["id"], line


def test_video_is_between_60_and_90_seconds():
    total = sum(sc["seconds"] for sc in SB["scenes"])
    assert 60 <= total <= 90


def test_captions_contain_no_typed_numbers():
    for sid, text in captions():
        if text.startswith("github.com/"):
            continue                       # the repository address, not a measurement
        bare = PLACEHOLDER.sub("", text)
        assert not re.search(r"\d", bare), (sid, text)


def test_every_placeholder_is_a_fact_computed_from_the_review_files():
    pytest = __import__("pytest")
    pytest.importorskip("PIL")
    sys.path.insert(0, str(ROOT / "video"))
    import build as video_build
    fx = video_build.facts()
    for sid, text in captions():
        for _, name, _, _ in string.Formatter().parse(text):
            if name:
                assert name in fx, (sid, name)
    s = json.loads((ROOT / "review" / "summary.json").read_text(encoding="utf-8"))
    assert fx["listed"] == s["all"]["reported"] and fx["real"] == s["all"]["reported_true"]
    assert (fx["val_real"], fx["val_listed"]) == (s["validation"]["reported_true"], s["validation"]["reported"])


def test_terminal_scene_runs_the_documented_replay_command():
    t = SB["terminal"]
    assert t["show"] == "python -m docsdrift scan ../targets/fastify --offline"
    assert t["run"][1:] == t["show"].split()[1:] and "--offline" in t["run"]
    assert t["show"] in (ROOT / "README.md").read_text(encoding="utf-8")


def test_page_scenes_point_at_elements_that_exist_on_the_page():
    page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    for sc in SB["scenes"]:
        for key in ("at", "box"):
            sel = sc.get(key)
            if sel and sel.startswith("#"):
                assert f'id="{sel[1:].split()[0]}"' in page, sel
