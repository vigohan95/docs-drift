"""Markdown splitting: exact line ranges, code fences, long sections."""
from docsdrift.sections import split_file, load_project, MAX_CHUNK_CHARS


def write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return name


def test_heading_sections_have_exact_line_ranges(tmp_path):
    text = ("# Title\n\nIntro paragraph that is long enough to be kept as a chunk.\n\n"
            "## Second\n\nBody of the second section, also long enough to keep.\n")
    rel = write(tmp_path, "a.md", text)
    chunks = split_file("p", tmp_path, rel)
    assert [c.heading for c in chunks] == ["Title", "Title > Second"]
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 3)
    assert (chunks[1].start_line, chunks[1].end_line) == (5, 7)
    lines = text.split("\n")
    for c in chunks:
        assert c.text == "\n".join(lines[c.start_line - 1:c.end_line])


def test_hash_inside_code_fence_is_not_a_heading(tmp_path):
    text = ("# Config\n\n```yaml\n# How often to scrape targets by default.\nscrape_interval: 1m\n```\n\n"
            "More prose here so the section is long enough.\n")
    chunks = split_file("p", tmp_path, write(tmp_path, "b.md", text))
    assert len(chunks) == 1
    assert "scrape_interval" in chunks[0].text


def test_line_of_maps_offsets_to_file_lines(tmp_path):
    text = "# T\n\nfirst line of text here\nsecond line with the needle inside\nthird line\n"
    c = split_file("p", tmp_path, write(tmp_path, "c.md", text))[0]
    off = c.text.index("needle")
    assert c.line_of(off) == 4
    assert c.line_of(0) == 1


def test_long_section_is_split_and_ranges_stay_contiguous(tmp_path):
    paras = [f"Paragraph number {i} " + "word " * 60 for i in range(30)]
    text = "# Long\n\n" + "\n\n".join(paras) + "\n"
    chunks = split_file("p", tmp_path, write(tmp_path, "d.md", text))
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHUNK_CHARS * 1.7 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.start_line > prev.end_line
    lines = text.split("\n")
    for c in chunks:
        assert c.text == "\n".join(lines[c.start_line - 1:c.end_line])


def test_table_without_blank_lines_is_hard_split(tmp_path):
    rows = "\n".join(f"| `option{i}` | `number` | `{i}` | description of option {i} goes here |" for i in range(120))
    text = "# Options\n\n| key | type | default | description |\n| --- | --- | --- | --- |\n" + rows + "\n"
    chunks = split_file("p", tmp_path, write(tmp_path, "e.md", text))
    assert len(chunks) >= 2
    assert max(len(c.text) for c in chunks) <= MAX_CHUNK_CHARS * 1.7


def test_short_sections_are_dropped(tmp_path):
    text = "# A\n\nhi\n\n# B\n\nThis one is long enough to be kept in the output.\n"
    chunks = split_file("p", tmp_path, write(tmp_path, "f.md", text))
    assert [c.heading for c in chunks] == ["B"]


def test_chunk_ids_are_stable_and_unique(tmp_path):
    text = "# A\n\n" + "Sentence about something or other. " * 3 + "\n\n## B\n\n" + "Another sentence about it. " * 3 + "\n"
    rel = write(tmp_path, "g.md", text)
    one = [c.cid for c in split_file("proj", tmp_path, rel)]
    two = [c.cid for c in split_file("proj", tmp_path, rel)]
    assert one == two == ["proj:g.md#0", "proj:g.md#1"]


def test_load_project_respects_excludes_and_loads_each_file_once(tmp_path):
    write(tmp_path, "README.md", "# R\n\nReadme text that is long enough to be kept as a chunk.\n")
    write(tmp_path, "docs/x.md", "# X\n\nDoc text that is long enough to be kept as a chunk too.\n")
    write(tmp_path, "docs/CHANGELOG.md", "# C\n\nChangelog text that is long enough to be a chunk as well.\n")
    chunks = load_project("p", tmp_path, ["README.md", "readme.md", "docs/**/*.md"], [r"CHANGELOG"])
    paths = [c.path for c in chunks]
    assert sorted(p.lower() for p in paths) == ["docs/x.md", "readme.md"]
