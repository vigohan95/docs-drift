"""Local, free filters added in v2.1 after the v2.0 run on eleven projects.

The v2.0 false positives were dominated by sibling documents: pages that are
written from one template but describe different things (two migration guides
for different versions, the React and the Vue page of one API, ...). /compare
and /grounding both read such pairs as conflicts.
"""
from __future__ import annotations

import re

_GUIDE = re.compile(r"migrat|upgrad|whats?[-_ ]?new|release[-_ ]?notes?", re.I)
_VERSION = re.compile(r"\d+(?:[._]\d+)*")

# /compare labels every conflict with a kind. "scope" and "name" are how it
# describes sibling pages; a contradiction worth reporting is one of these:
REPORTABLE_KINDS = {"value", "date_or_version", "rule_or_condition"}


def guide_version(path: str) -> str | None:
    """Version a per-version guide is about, e.g. docs/migrating_to_7.md -> '7'."""
    name = path.rsplit("/", 1)[-1]
    if not _GUIDE.search(path):
        return None
    versions = _VERSION.findall(name)
    return "-".join(versions) if versions else None


def version_scoped_pair(path_a: str, path_b: str) -> bool:
    """True when both files are per-version guides for different versions.

    Each of them is right for its own version, so a difference between them
    is history, not a contradiction.
    """
    va, vb = guide_version(path_a), guide_version(path_b)
    return va is not None and vb is not None and va != vb
