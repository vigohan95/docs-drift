"""Free, local candidate generation."""
from pathlib import Path

from docsdrift.local import chunk_keys, norm_key, looks_like_option, baseline_flags
from docsdrift.neardup import sentences, chunk_pairs
from docsdrift.scan import build_candidates
from docsdrift.sections import Chunk, load_project

FIX = Path(__file__).parent / "fixtures" / "mini"


def mk(path, text, n=0):
    offs, pos = [], 0
    for ln in text.split("\n"):
        offs.append(pos)
        pos += len(ln) + 1
    return Chunk("p", path, "H", 1, len(offs), text, cid=f"p:{path}#{n}", line_offsets=offs)


def test_norm_key_strips_calls_and_values():
    assert norm_key("fastify.listen()") == "fastify.listen"
    assert norm_key("--web.listen-address=:9090") == "--web.listen-address"
    assert norm_key("true") is None
    assert norm_key("x") is None


def test_keys_from_code_spans_flags_and_yaml():
    c = mk("a.md", "Set `bodyLimit` or pass --storage.tsdb.path on the command line.\n"
                   "```yaml\n  scrape_interval: 1m\n```\nNeeds Node.js 20 or newer.")
    keys = chunk_keys(c)
    assert {"bodyLimit", "--storage.tsdb.path", "scrape_interval", "@node-version"} <= keys


def test_option_like_filter():
    assert looks_like_option("bodyLimit") and looks_like_option("--flag-name") and looks_like_option("server.port")
    assert not looks_like_option("response")


def test_sentences_skip_code_but_keep_config_comments():
    c = mk("a.md", "Prose sentence number one is here for the test.\n\n```yaml\n"
                   "# How frequently to scrape targets by default.\nscrape_interval: 1m\n```\n")
    texts = [s.text for s in sentences(c)]
    assert any("Prose sentence" in t for t in texts)
    assert any("How frequently to scrape" in t for t in texts)
    assert not any(t == "scrape_interval: 1m" for t in texts)


def test_sentence_line_numbers():
    c = mk("a.md", "# H\n\nFirst sentence sits on line three of this chunk.\n\n"
                   "Second sentence sits on line five of this chunk.")
    lines = {s.text[:5]: s.line for s in sentences(c)}
    assert lines["First"] == 3 and lines["Secon"] == 5


def test_near_duplicate_sentences_with_a_difference_are_paired():
    a = mk("a.md", "In the onRequest hook, request.body will always be undefined, because parsing happens later.", 0)
    b = mk("b.md", "In the onRequest hook, request.body will always be null, because parsing happens later.", 1)
    c = mk("c.md", "Completely unrelated sentence about installing packages with a package manager today.", 2)
    pairs = chunk_pairs([a, b, c])
    assert len(pairs) == 1
    p = pairs[0]
    assert {p["a"].chunk.path, p["b"].chunk.path} == {"a.md", "b.md"}
    diff = p["only_a"] + p["only_b"]
    assert "undefined" in diff and "null" in diff


def test_identical_sentences_are_not_candidates():
    a = mk("a.md", "The server listens on port 8080 by default unless configured otherwise.", 0)
    b = mk("b.md", "The server listens on port 8080 by default unless configured otherwise.", 1)
    assert chunk_pairs([a, b]) == []


def test_baseline_default_extractor_flags_differing_defaults():
    a = mk("a.md", "`timeout` defaults to `30`.", 0)
    b = mk("b.md", "`timeout` defaults to `60`.", 1)
    flags = baseline_flags([a, b])
    assert [f["key"] for f in flags] == ["timeout"] and flags[0]["values"] == ["30", "60"]


def test_fixture_candidates_are_deterministic():
    chunks = load_project("mini", FIX, ["README.md", "docs/**/*.md"])
    one, st1 = build_candidates(chunks)
    two, st2 = build_candidates(chunks)

    def sig(cs):
        return [(c["a"].cid, c["b"].cid, c["source"]) for c in cs]
    assert sig(one) == sig(two) and st1 == st2
    assert ("mini:README.md#1", "mini:docs/configuration.md#0", "near-dup") in sig(one)


def test_candidate_caps_are_respected():
    chunks = load_project("mini", FIX, ["README.md", "docs/**/*.md"])
    cands, st = build_candidates(chunks, max_neardup=1, max_key=0)
    assert len(cands) == 1 and st["shared_key_sent"] == 0
