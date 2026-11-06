"""End-to-end replay through the CLI: no network, no key, no credits."""
import json
import shutil
from pathlib import Path

import pytest

from docsdrift import cli
from docsdrift.client import Clocked
from docsdrift.scan import scan
from docsdrift.targets import TARGETS, TARGETS_ROOT

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures" / "mini"
STORED = json.loads((Path(__file__).parent / "fixtures" / "mini-report.json").read_text(encoding="utf-8"))
ARGS = ["--name", "mini", "--repo", "example/mini", "--commit", "0000000",
        "--include", "README.md", "--include", "docs/**/*.md", "--offline", "--quiet"]


@pytest.fixture(autouse=True)
def no_key(monkeypatch, tmp_path):
    """A replay must work without any API key."""
    monkeypatch.delenv("CLOCKED_API_KEY", raising=False)
    monkeypatch.setenv("CLOCKED_ENV_FILE", str(tmp_path / "missing.env"))


def test_cli_offline_scan_of_the_fixture_reproduces_the_stored_report(tmp_path):
    out = tmp_path / "report.json"
    assert cli.main(["scan", str(FIX), *ARGS, "--out", str(out)]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["stats"]["live_calls"] == 0 and rep["stats"]["live_credits"] == 0
    assert [(f["id"], f["tier"], f["kind"]) for f in rep["findings"]] == \
           [(f["id"], f["tier"], f["kind"]) for f in STORED["findings"]]


def test_fixture_finding_points_at_the_two_conflicting_lines(tmp_path):
    out = tmp_path / "report.json"
    cli.main(["scan", str(FIX), *ARGS, "--out", str(out)])
    f = json.loads(out.read_text(encoding="utf-8"))["findings"][0]
    assert f["tier"] == "confirmed" and f["kind"] == "value"
    assert (f["a"]["path"], f["a"]["line_start"]) == ("README.md", 9)
    assert (f["b"]["path"], f["b"]["line_start"]) == ("docs/configuration.md", 5)
    assert "30 seconds" in f["a"]["statement"] and "60 seconds" in f["b"]["statement"]
    assert f["a"]["url"] == "https://github.com/example/mini/blob/0000000/README.md#L9-L9"


def test_replay_credits_are_reported_at_list_price(tmp_path):
    out = tmp_path / "report.json"
    cli.main(["scan", str(FIX), *ARGS, "--out", str(out)])
    st = json.loads(out.read_text(encoding="utf-8"))["stats"]
    assert st["credits_total"] == STORED["stats"]["credits_total"] > 0
    assert st["cache_hits"] > 0


def test_offline_scan_of_changed_docs_fails_instead_of_inventing_an_answer(tmp_path, capsys):
    tree = tmp_path / "mini"
    shutil.copytree(FIX, tree)
    cfg = tree / "docs" / "configuration.md"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("60 seconds", "90 seconds"), encoding="utf-8")
    assert cli.main(["scan", str(tree), *ARGS, "--out", str(tmp_path / "r.json")]) == 2
    assert "offline replay failed" in capsys.readouterr().err
    assert not (tmp_path / "r.json").exists()


def test_cli_rejects_a_missing_directory(tmp_path):
    assert cli.main(["scan", str(tmp_path / "nope"), "--offline", "--quiet"]) == 2


def test_cli_rejects_an_unknown_target():
    assert cli.main(["target", "not-a-target", "--offline", "--quiet"]) == 2


def test_stages_can_be_switched_off(tmp_path):
    out = tmp_path / "report.json"
    assert cli.main(["scan", str(FIX), *ARGS, "--no-gate", "--no-swap", "--no-elsewhere", "--out", str(out)]) == 0
    f = json.loads(out.read_text(encoding="utf-8"))["findings"][0]
    assert f["tier"] == "unchecked" and "gate" not in f and "swap" not in f


def _have(name):
    return (TARGETS_ROOT / name / ".git").exists() and (ROOT / "reports" / f"{name}.json").exists()


@pytest.mark.parametrize("name", list(TARGETS))
def test_offline_replay_of_each_real_target_matches_its_stored_report(name):
    """Needs the pinned clones (scripts/fetch_targets.py); skipped when they are absent."""
    if not _have(name):
        pytest.skip(f"targets/{name} is not cloned")
    t = TARGETS[name]
    stored = json.loads((ROOT / "reports" / f"{name}.json").read_text(encoding="utf-8"))
    client = Clocked(offline=True)
    rep = scan(name, TARGETS_ROOT / name, t["includes"], t["excludes"], repo=t["repo"], commit=t["commit"],
               client=client, log=lambda *a: None)
    assert client.live_calls == 0
    assert sorted((f["id"], f["tier"]) for f in rep["findings"]) == sorted((f["id"], f["tier"]) for f in stored["findings"])
    assert rep["stats"]["pairs_compared"] == stored["stats"]["pairs_compared"]
