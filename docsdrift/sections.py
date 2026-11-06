"""Split Markdown files into heading-delimited chunks with exact line ranges.

Only reads files as text. Never imports or executes anything from the target.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")

MAX_CHUNK_CHARS = 2200
MIN_BODY_CHARS = 40


@dataclass
class Chunk:
    project: str
    path: str            # repo-relative, forward slashes
    heading: str         # "A > B > C"
    start_line: int      # 1-based, inclusive
    end_line: int        # 1-based, inclusive
    text: str            # exact source lines joined with "\n"
    cid: str = ""
    line_offsets: list = field(default_factory=list)  # char offset of each line in text

    def line_of(self, offset: int) -> int:
        """Map a char offset inside self.text to a 1-based file line."""
        line = self.start_line
        for i, off in enumerate(self.line_offsets):
            if off > offset:
                break
            line = self.start_line + i
        return line


def _finish(project, path, heading, start, lines):
    # strip trailing blank lines but keep the line range exact
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    if not lines:
        return None
    text = "\n".join(lines)
    offs, pos = [], 0
    for ln in lines:
        offs.append(pos)
        pos += len(ln) + 1
    return Chunk(project, path, heading, start, start + len(lines) - 1, text, line_offsets=offs)


def split_file(project: str, root: Path, rel: str) -> list[Chunk]:
    return split_text(project, rel, (root / rel).read_text(encoding="utf-8", errors="replace"))


def split_text(project: str, rel: str, raw: str) -> list[Chunk]:
    """Split Markdown given as text (used for files that are only held in memory)."""
    lines = raw.split("\n")
    lines = [ln.rstrip("\r") for ln in lines]
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    in_fence = False
    cur: list[str] = []
    cur_start = 1
    cur_heading = "(preamble)"

    def flush():
        nonlocal cur
        if not cur:
            return
        body = "\n".join(cur)
        if len(body.strip()) >= MIN_BODY_CHARS:
            for piece_start, piece in _split_long(cur, cur_start):
                ch = _finish(project, rel, cur_heading, piece_start, piece)
                if ch and len(ch.text.strip()) >= MIN_BODY_CHARS:
                    chunks.append(ch)
        cur = []

    for i, ln in enumerate(lines, start=1):
        if FENCE.match(ln):
            in_fence = not in_fence
        m = None if in_fence else HEADING.match(ln)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            cur_heading = " > ".join(t for _, t in stack)
            cur_start = i
            cur = [ln]
        else:
            if not cur:
                cur_start = i
            cur.append(ln)
    flush()
    for n, ch in enumerate(chunks):
        ch.cid = f"{project}:{rel}#{n}"
    return chunks


def _split_long(lines: list[str], start: int):
    """Split an over-long section at blank lines outside code fences/tables."""
    total = sum(len(l) + 1 for l in lines)
    if total <= MAX_CHUNK_CHARS:
        yield start, lines
        return
    piece: list[str] = []
    piece_start = start
    size = 0
    in_fence = False
    for idx, ln in enumerate(lines):
        if FENCE.match(ln):
            in_fence = not in_fence
        piece.append(ln)
        size += len(ln) + 1
        blank = not ln.strip()
        boundary = (
            (blank and not in_fence and size >= MAX_CHUNK_CHARS * 0.6)
            # long code fences (YAML references) : split at blank lines inside them
            or (blank and size >= MAX_CHUNK_CHARS)
            # tables / fences without blank lines: hard split at a line boundary
            or size >= MAX_CHUNK_CHARS * 1.6
        )
        if boundary:
            yield piece_start, piece
            piece_start = start + idx + 1
            piece, size = [], 0
    if piece:
        yield piece_start, piece


def load_project(project: str, root: Path, includes: list[str], excludes: list[str] = ()) -> list[Chunk]:
    out: list[Chunk] = []
    seen = set()
    for pattern in includes:
        for p in sorted(root.glob(pattern)):
            if not p.is_file() or p.suffix.lower() not in (".md", ".mdx"):
                continue
            try:  # resolve() gives the on-disk spelling, which the GitHub links need
                rel = p.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                rel = p.relative_to(root).as_posix()
            # case-insensitive filesystems return README.md for a "readme.md" pattern too
            key = rel.lower()
            if key in seen or any(re.search(x, rel) for x in excludes):
                continue
            seen.add(key)
            out.extend(split_file(project, root, rel))
    return out
