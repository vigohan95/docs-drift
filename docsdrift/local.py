"""Cheap local analysis: shared identifiers, claim markers, and a
local-only baseline that flags differing default values without any API call.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from .sections import Chunk

CODE_SPAN = re.compile(r"`([^`\n]{2,60})`")
CLAIM_MARK = re.compile(
    r"\d|default|require|must|only|deprecat|removed|since|minimum|maximum|limit|at least|at most|no longer|support",
    re.I,
)
STOP_KEYS = {
    "true", "false", "null", "undefined", "npm", "yarn", "pnpm", "node", "string", "number",
    "boolean", "object", "function", "array", "0", "1", "GET", "POST", "PUT", "DELETE", "HEAD",
    "async", "await", "this", "done", "err", "error", "req", "res", "request", "reply", "next",
    "promise", "callback", "json", "yaml", "http", "https", "localhost",
}

# Pseudo-keys for runtime version requirements that are not written as code spans.
FAMILIES = {
    "@node-version": re.compile(r"Node(?:\.js)?\s*(?:v|versions?\s*)?(\d+(?:\.\d+)*\+?)", re.I),
    "@go-version": re.compile(r"\bGo\s+(?:versions?\s+)?(1\.\d+(?:\.\d+)?\+?)"),
}


FLAG = re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+")
YAML_KEY = re.compile(r"^\s*(?:#\s*)?\[?\s*([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\s*:", re.M)


def norm_key(raw: str) -> str | None:
    k = raw.strip().strip("'\"")
    if len(k) < 3 or len(k) > 50 or " " in k.strip() and len(k.split()) > 2:
        return None
    if not re.search(r"[A-Za-z]", k):
        return None
    k = re.sub(r"\(.*\)$", "", k)          # foo(bar) -> foo
    k = re.sub(r"[=:].*$", "", k).strip()  # --flag=value -> --flag ; key: v -> key
    if len(k) < 3 or k.lower() in STOP_KEYS:
        return None
    return k


def chunk_keys(ch: Chunk) -> set[str]:
    keys = set()
    for m in CODE_SPAN.finditer(ch.text):
        k = norm_key(m.group(1))
        if k:
            keys.add(k)
    # CLI flags and YAML-style option names also count when they are not in
    # a code span (reference docs often put them inside fenced blocks).
    for m in FLAG.finditer(ch.text):
        keys.add(m.group(0))
    for m in YAML_KEY.finditer(ch.text):
        keys.add(m.group(1))
    for fam, rx in FAMILIES.items():
        if rx.search(ch.text):
            keys.add(fam)
    return keys


def key_lines(ch: Chunk, key: str) -> list[int]:
    """Indexes (within the chunk) of lines mentioning the key."""
    rx = FAMILIES.get(key)
    out = []
    for i, ln in enumerate(ch.text.split("\n")):
        if (rx.search(ln) if rx else key in ln):
            out.append(i)
    return out


def is_claim_bearing(ch: Chunk, key: str) -> bool:
    lines = ch.text.split("\n")
    idxs = key_lines(ch, key)
    if not idxs:
        return False
    if key in lines[0] and lines[0].lstrip().startswith("#"):
        return True  # the section is about this key
    for i in idxs:
        window = " ".join(lines[max(0, i - 1): i + 3])
        window = window.replace(key, " ")
        if CLAIM_MARK.search(window):
            return True
    return False


def build_index(chunks: list[Chunk]):
    by_key = defaultdict(list)
    for ch in chunks:
        for k in chunk_keys(ch):
            by_key[k].append(ch)
    return by_key


OPTION_LIKE = re.compile(r"^--?[a-z]|[a-z][A-Z]|[A-Za-z0-9]_[A-Za-z0-9]|[A-Za-z]\.[A-Za-z]|^[A-Z][A-Z0-9_]{3,}$|/[a-z]")


def looks_like_option(key: str) -> bool:
    """Config options, CLI flags, env vars, dotted paths, API routes."""
    return key in FAMILIES or bool(OPTION_LIKE.search(key))


def rank_keys(chunks: list[Chunk], max_df: int = 14):
    """Neutral prioritisation of keys worth sending to the API.

    Does NOT look at whether local value extraction disagrees, so that the
    local-only baseline stays an independent control.
    """
    by_key = build_index(chunks)
    n = len(chunks)
    ranked = []
    for k, chs in by_key.items():
        if len(chs) < 2 or len(chs) > max_df or not looks_like_option(k):
            continue
        bearing = [c for c in chs if is_claim_bearing(c, k)]
        if len(bearing) < 2 or len({c.path for c in bearing}) < 2:
            continue
        files = {c.path for c in bearing}
        defined = any(k in c.text.splitlines()[0] and c.text.lstrip().startswith("#") for c in chs)
        idf = math.log(n / len(chs))
        score = 2.0 * defined + min(len(files), 4) + 0.5 * idf + (3 if k in FAMILIES else 0)
        ranked.append((score, k, bearing))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return ranked


# ---------------------------------------------------------------- baseline

VALUE = r"(`[^`\n]{1,40}`|\"[^\"\n]{1,30}\"|'[^'\n]{1,30}'|-?\d[\d_.,]*\s?(?:ms|s|m|h|d|seconds?|minutes?|hours?|days?|[KMG]i?B|bytes|%)?\b|true|false|null|undefined)"
DEFAULT_PATTERNS = [
    re.compile(r"default(?:s|ed)?(?:\s+value)?(?:\s+(?:is|to|of|being))?\s*[:=]?\s*" + VALUE, re.I),
    re.compile(VALUE + r"\s+(?:by default|is the default)", re.I),
    re.compile(r"default\s*=\s*([^\s\]|]+)", re.I),
]


def _norm_value(v: str) -> str:
    v = v.strip().strip("`'\"").strip().rstrip(".,;")
    v = v.replace("_", "").replace(",", "")
    return v.lower()


def default_values(ch: Chunk, key: str) -> list[tuple[str, int]]:
    """(normalised default value, file line) pairs stated for `key` in a chunk.

    A value counts when it is on a line mentioning the key, or anywhere in a
    section whose heading is the key (reference-style docs).
    """
    lines = ch.text.split("\n")
    idxs = set(key_lines(ch, key))
    heading_is_key = bool(lines) and lines[0].lstrip().startswith("#") and key in lines[0]
    out = []
    for i, ln in enumerate(lines):
        if not (i in idxs or heading_is_key):
            continue
        if heading_is_key and i not in idxs:
            # only take explicit "Default: x" lines in a key-titled section
            if not re.match(r"\s*[-+*]?\s*\**default", ln, re.I):
                continue
        probe = ln.replace(f"`{key}`", " KEY ")
        for rx in DEFAULT_PATTERNS:
            for m in rx.finditer(probe):
                val = _norm_value(m.group(1))
                if val and val != "key":
                    out.append((val, ch.start_line + i))
    return out


def baseline_flags(chunks: list[Chunk], max_df: int = 40):
    """Local-only control: keys whose extracted default values disagree
    between two different chunks. No API involved."""
    by_key = build_index(chunks)
    flags = []
    for k, chs in sorted(by_key.items()):
        if k in FAMILIES or len(chs) < 2 or len(chs) > max_df:
            continue
        seen = []
        for c in chs:
            for val, line in default_values(c, k):
                seen.append((val, c, line))
        values = {v for v, _, _ in seen}
        if len(values) >= 2 and len({c.cid for _, c, _ in seen}) >= 2:
            flags.append({
                "key": k,
                "values": sorted(values),
                "sites": [{"value": v, "cid": c.cid, "path": c.path, "line": line} for v, c, line in seen],
            })
    return flags


def family_flags(chunks: list[Chunk]):
    """Local-only control for version families: all distinct versions seen."""
    out = {}
    for fam, rx in FAMILIES.items():
        sites = []
        for c in chunks:
            for i, ln in enumerate(c.text.split("\n")):
                for m in rx.finditer(ln):
                    sites.append({"value": m.group(1), "path": c.path, "line": c.start_line + i, "cid": c.cid})
        out[fam] = sites
    return out
