"""Pure helpers of the v2 pipeline (no API involved)."""
from docsdrift.scan import statement_of, finding_id, tier_of, side_info, compare_payload, gate_payload, WIDE_QUOTE
from docsdrift.sections import Chunk


def mk(text, path="docs/a.md", start_line=10, n=0):
    offs, pos = [], 0
    for ln in text.split("\n"):
        offs.append(pos)
        pos += len(ln) + 1
    return Chunk("p", path, "Top > Sub", start_line, start_line + len(offs) - 1, text, cid=f"p:{path}#{n}", line_offsets=offs)


def test_statement_grows_a_first_line_quote_to_the_whole_sentence():
    text = ("A custom logger instance. The logger must be a Pino instance or conform to the\n"
            "Pino interface by having the following methods: `info`, `error`, `child`. For example:")
    c = mk(text)
    start = text.index("The logger")
    end = text.index("\n")           # the API returned only the first line
    s = statement_of(c, start, end)
    assert s.startswith("The logger must be a Pino instance")
    assert s.endswith("`child`.")
    assert "\n" not in s


def test_statement_strips_blockquote_markers():
    text = "> In the hook, `request.body` will always be\n> `undefined`, because parsing happens later.\n"
    c = mk(text)
    s = statement_of(c, 2, text.index("\n"))
    assert s == "In the hook, `request.body` will always be `undefined`, because parsing happens later."


def test_statement_keeps_a_complete_sentence_unchanged():
    text = "Requests time out after 30 seconds. Something else follows here."
    c = mk(text)
    assert statement_of(c, 0, 35) == "Requests time out after 30 seconds."


def test_wide_quote_has_no_single_statement():
    text = "word " * 200
    c = mk(text)
    assert statement_of(c, 0, WIDE_QUOTE + 50) is None
    assert statement_of(c, None, None) is None


def test_finding_id_is_stable_and_order_sensitive():
    a, b = mk("x" * 50, "a.md", n=0), mk("y" * 50, "b.md", n=1)
    f1 = finding_id("p", a, b, {"start": 0, "end": 10}, {"start": 5, "end": 9})
    f2 = finding_id("p", a, b, {"start": 0, "end": 10}, {"start": 5, "end": 9})
    f3 = finding_id("p", b, a, {"start": 5, "end": 9}, {"start": 0, "end": 10})
    assert f1 == f2 and f1 != f3 and len(f1) == 10


def test_side_info_lines_and_github_link():
    text = "line one\nline two has the quote in it\nline three"
    c = mk(text, "docs/Reference/X.md", start_line=100)
    start = text.index("the quote")
    info = side_info("owner/repo", "abc123", c, {"start": start, "end": start + 9, "quote": "the quote"})
    assert (info["line_start"], info["line_end"]) == (101, 101)
    assert info["url"] == "https://github.com/owner/repo/blob/abc123/docs/Reference/X.md#L101-L101"
    assert info["chunk_lines"] == [100, 102]


def test_side_info_multi_line_quote_range():
    text = "first\nsecond\nthird\nfourth"
    c = mk(text, start_line=1)
    info = side_info("o/r", "c", c, {"start": text.index("second"), "end": text.index("fourth") - 1, "quote": "second\nthird"})
    assert (info["line_start"], info["line_end"]) == (2, 3)


def test_tiers():
    assert tier_of({}) == "ungated"
    assert tier_of({"gate": {"any_contradicted": False}, "swap": {"confirmed": True}}) == "filtered"
    assert tier_of({"gate": {"any_contradicted": True}, "swap": {"confirmed": False}}) == "likely"
    assert tier_of({"gate": {"any_contradicted": True}}) == "likely"
    assert tier_of({"gate": {"any_contradicted": True}, "swap": {"confirmed": True}}) == "confirmed"


def test_compare_payload_is_two_documents_and_keeps_order():
    a, b = mk("alpha " * 10, "a.md", n=0), mk("beta " * 10, "b.md", n=1)
    p = compare_payload(a, b)
    assert [d["id"] for d in p["documents"]] == [a.cid, b.cid]
    assert p["evidence"] == "flagged" and "instructions" in p
    assert [d["id"] for d in compare_payload(b, a)["documents"]] == [b.cid, a.cid]
    assert "instructions" not in compare_payload(a, b, instructions=None)


def test_gate_payload_checks_one_claim_against_one_passage():
    src = mk("source text " * 5, "b.md", n=1)
    p = gate_payload("The default is 30.", src)
    assert p["claims"] == ["The default is 30."] and p["answer"] == "The default is 30."
    assert [d["id"] for d in p["documents"]] == [src.cid]
