"""The demo page and the defect registry are generated from committed data and stay in sync with it."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "review"))
import build_site as site_build  # noqa: E402
import defects as registry  # noqa: E402

from docsdrift.targets import TARGETS  # noqa: E402

PAGE = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
PRS = json.loads((ROOT / "review" / "upstream_prs.json").read_text(encoding="utf-8"))
REG = json.loads((ROOT / "review" / "defects.json").read_text(encoding="utf-8"))
LABELS = json.loads((ROOT / "review" / "labels_v2.json").read_text(encoding="utf-8"))


def test_page_on_disk_is_what_the_build_script_produces():
    assert site_build.build() == PAGE


def test_registry_file_is_what_the_registry_script_produces():
    assert json.loads(json.dumps({"upstream_search": registry.UPSTREAM_SEARCH, "defects": registry.entries()})) == REG


def test_page_shows_every_defect_with_pinned_links():
    assert len(REG["defects"]) == 16
    for d in REG["defects"]:
        assert f'id="{d["id"]}"' in PAGE
        for side in ("a", "b"):
            assert d[side]["url"] in PAGE
            assert TARGETS[d["project"]]["commit"] in d[side]["url"]


def test_defects_cover_at_least_four_projects_and_each_names_evidence():
    projects = {d["project"] for d in REG["defects"]}
    assert len(projects) >= 4
    for d in REG["defects"]:
        assert d["source"] and d["found_by"]
        assert d["wrong"] in ("a", "b", None)
        for fid in d["findings"]:
            assert LABELS[fid]["label"] == "true" and LABELS[fid]["defect"] == d["id"]


def test_every_true_verdict_belongs_to_a_registered_defect():
    registered = {d["id"] for d in REG["defects"]}
    assert {l["defect"] for l in LABELS.values() if l["label"] == "true"} <= registered


def test_every_patch_has_a_pr_draft_and_is_referenced():
    patches = sorted(p.relative_to(ROOT / "upstream-patches").as_posix() for p in (ROOT / "upstream-patches").glob("*/*.patch"))
    referenced = {d[k] for d in REG["defects"] for k in ("patch", "extra_patch") if d.get(k)}
    assert set(patches) == referenced
    for p in patches:
        draft = (ROOT / "upstream-patches" / p.replace(".patch", ".md")).read_text(encoding="utf-8")
        assert "DRAFT" in draft and "## Why" in draft
        diff = (ROOT / "upstream-patches" / p).read_text(encoding="utf-8")
        assert diff.startswith("diff --git ") and "\r" not in diff


def test_patches_are_small():
    for p in (ROOT / "upstream-patches").glob("*/*.patch"):
        changed = [l for l in p.read_text(encoding="utf-8").split("\n")
                   if re.match(r"^[+-](?![+-]{2} )", l)]
        assert 2 <= len(changed) <= 20, p.name


def test_page_wording_about_who_decides():
    assert "The final word belongs to the upstream maintainers" in PAGE
    assert "human" not in PAGE.lower()
    assert "0 of 8" in PAGE            # the validation result is on the page, not hidden


def test_page_content_does_not_depend_on_scripts_and_loads_no_remote_assets():
    # one local script, for the "Try it live" block only, plus its inline example data
    scripts = re.findall(r"<script\b[^>]*>", PAGE)
    assert scripts == ['<script type="application/json" id="live-examples">', '<script src="live.js" defer>']
    assert (ROOT / "docs" / "live.js").exists()
    static = re.sub(r"<script\b.*?</script>", "", PAGE, flags=re.S)
    for d in REG["defects"]:                                # every defect is in the static HTML
        assert f'id="{d["id"]}"' in static
    assert "<noscript>" in static and "The numbers, including the bad ones" in static
    assert re.findall(r'(?:src|href)="(https?://[^"]+)"', PAGE) == [u for u in re.findall(r'href="(https?://[^"]+)"', PAGE)]
    assert all(u.startswith("https://github.com/") for u in re.findall(r'href="(https?://[^"]+)"', PAGE))
    assert 'href="style.css"' in PAGE and (ROOT / "docs" / "style.css").exists()
    assert (ROOT / "docs" / ".nojekyll").exists()      # GitHub Pages serves docs/ as it is


def test_readme_numbers_match_the_recount():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    s = json.loads((ROOT / "review" / "summary.json").read_text(encoding="utf-8"))

    def row(part, num, den):
        a = s[part]
        return f"| {a[den]} | {a[num]} | {round(100 * a[num] / a[den])}% |"
    assert row("all", "raw_true", "raw") in readme
    assert row("all", "reported_true", "reported") in readme
    assert row("tuning", "reported_true", "reported") in readme
    assert row("validation", "reported_true", "reported") in readme
    assert f"{s['all']['pairs_compared']:,} pairs" in readme
    assert "**16 defects in 6 of" in readme and "**15 open-source projects**" in readme
    n_tests = sum(len(re.findall(r"^def test_", p.read_text(encoding="utf-8"), re.M)) for p in (ROOT / "tests").glob("test_*.py"))
    declared = int(re.search(r"# (\d+) tests, no network", readme).group(1))
    assert declared >= n_tests      # parametrized tests add to the count pytest reports


def test_upstream_pr_table_is_on_the_page_and_in_the_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    registered = {d["id"] for d in REG["defects"]}
    covered = []
    for pr in PRS["pull_requests"]:
        assert pr["status"] in ("open", "merged", "closed")
        assert pr["url"] == f"https://github.com/{pr['repo']}/pull/{pr['number']}"
        assert pr["url"] in PAGE and pr["url"] in readme
        row = readme[readme.index(pr["url"]):].splitlines()[0]
        assert f"| {pr['status']} |" in row
        covered += pr["defects"]
    for p in PRS["not_opened_yet"]:
        covered += p["defects"]
    assert sorted(covered) == sorted(registered)        # every defect is in exactly one row


def test_page_does_not_claim_merges_that_have_not_happened():
    merged = [p for p in PRS["pull_requests"] if p["status"] == "merged"]
    if not merged:
        assert "merged" not in PAGE.lower()


def test_first_screen_states_what_it_is_and_how_often_it_is_wrong():
    top = PAGE[:PAGE.index('<section class="hero"')]
    assert "not a verdict" in top
    assert "0 of 8" in top and "11 of 21" in top
