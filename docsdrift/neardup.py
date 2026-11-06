"""Local, free candidate generator: restated sentences that differ.

Drift hides where one document restates another. This finds pairs of
sentences from different sections whose wording is close but not identical,
and ranks the pairs by how "factual" the differing tokens are (numbers,
code identifiers, modal words). It decides nothing about whether the
difference is a contradiction - that is left to /compare (and to the
local-only control, which reports every such pair unjudged).
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .sections import Chunk

TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-/]*[A-Za-z0-9_]|[A-Za-z]|\d+(?:\.\d+)*")
SENT_SPLIT = re.compile(r"(?<=[.!?:])\s+(?=[A-Z`\[*>])")
FACT_WORDS = {
    "must", "only", "always", "never", "cannot", "not", "no", "null", "undefined", "true", "false",
    "default", "defaults", "required", "optional", "deprecated", "removed", "before", "after",
    "all", "any", "none", "minimum", "maximum", "least", "most", "first", "last", "second", "third",
    "fourth", "fifth", "sixth", "seventh", "eighth", "enabled", "disabled",
}
STOP = set("the a an of to in on for and or is are be it this that with as by at from will can if you your "
           "we our they their its which when then than so but also use used using".split())


@dataclass
class Sentence:
    chunk: Chunk
    line: int          # 1-based file line where the sentence starts
    text: str
    tokens: tuple


def sentences(ch: Chunk) -> list[Sentence]:
    """Prose sentences of a chunk (code fences are skipped, comments included)."""
    out = []
    in_fence = False
    buf, buf_line = [], None

    def flush():
        nonlocal buf, buf_line
        if buf:
            para = " ".join(s.strip() for s in buf)
            para = re.sub(r"^[>\-+*\s]+", "", para)
            for s in SENT_SPLIT.split(para):
                toks = tuple(t.lower() for t in TOKEN.findall(s))
                if len(toks) >= 6:
                    out.append(Sentence(ch, buf_line, s.strip(), toks))
        buf, buf_line = [], None

    for i, ln in enumerate(ch.text.split("\n")):
        if re.match(r"^\s*(```|~~~)", ln):
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            m = re.match(r"^\s*(?:#|//)\s*(.{25,})$", ln)   # config comments carry facts too
            if m:
                toks = tuple(t.lower() for t in TOKEN.findall(m.group(1)))
                if len(toks) >= 6:
                    out.append(Sentence(ch, ch.start_line + i, m.group(1).strip(), toks))
            continue
        if not ln.strip() or ln.lstrip().startswith("#") or ln.lstrip().startswith("|"):
            flush()
            if ln.lstrip().startswith("|"):
                toks = tuple(t.lower() for t in TOKEN.findall(ln))
                if len(toks) >= 6:
                    out.append(Sentence(ch, ch.start_line + i, ln.strip(), toks))
            continue
        if re.match(r"^\s*([-+*]|\d+\.)\s", ln):
            flush()
        if buf_line is None:
            buf_line = ch.start_line + i
        buf.append(ln)
    flush()
    return out


def candidates(chunks: list[Chunk], min_sim: float = 0.55, max_sim: float = 0.985):
    sents = [s for ch in chunks for s in sentences(ch)]
    df = Counter()
    for s in sents:
        df.update(set(s.tokens))
    n = len(sents)
    idf = {t: math.log(1 + n / c) for t, c in df.items()}

    def weight(tokens):
        return {t: idf[t] for t in set(tokens) if t not in STOP}

    weights = [weight(s.tokens) for s in sents]
    norms = [sum(w.values()) for w in weights]
    index = defaultdict(list)
    for i, w in enumerate(weights):
        # index on the 6 rarest tokens of each sentence
        for t in sorted(w, key=lambda t: -w[t])[:6]:
            if df[t] <= 60:
                index[t].append(i)

    seen = set()
    pairs = []
    for i, w in enumerate(weights):
        cand = set()
        for t in sorted(w, key=lambda t: -w[t])[:6]:
            cand.update(index.get(t, ()))
        for j in cand:
            if j <= i or (i, j) in seen:
                continue
            seen.add((i, j))
            a, b = sents[i], sents[j]
            if a.chunk.cid == b.chunk.cid:
                continue
            if a.chunk.path == b.chunk.path and abs(a.line - b.line) < 12:
                continue
            wb = weights[j]
            inter = sum(w[t] for t in w if t in wb)
            union = norms[i] + norms[j] - inter
            sim = inter / union if union else 0
            if not (min_sim <= sim <= max_sim):
                continue
            only_a = [t for t in w if t not in wb]
            only_b = [t for t in wb if t not in w]
            if not only_a and not only_b:
                continue
            fact = sum(1 for t in only_a + only_b if t in FACT_WORDS or re.match(r"^\d", t) or re.search(r"[_.]|[a-z][A-Z]", t))
            pairs.append({
                "sim": round(sim, 3), "fact_diff": fact,
                "a": a, "b": b, "only_a": sorted(only_a), "only_b": sorted(only_b),
            })
    # rank: factual difference first, then similarity
    pairs.sort(key=lambda p: (-(p["fact_diff"] > 0), -p["sim"]))
    return pairs


def chunk_pairs(chunks: list[Chunk], **kw):
    """Collapse sentence pairs into unique chunk pairs, best sentence pair first."""
    out, seen = [], set()
    for p in candidates(chunks, **kw):
        key = tuple(sorted((p["a"].chunk.cid, p["b"].chunk.cid)))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out
