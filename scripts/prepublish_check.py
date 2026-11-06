"""Checks to run before making the repository public.

    python scripts/prepublish_check.py [extra strings to look for ...]

Looks through the working tree AND every revision in the history for:
  - the Clocked API key (read from CLOCKED_API_KEY or ../.env; never printed),
  - key-shaped assignments,
  - local filesystem paths and any extra strings given on the command line (user names, e-mail addresses),
and prints the commit authors. Exits 1 if anything is found.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BS = chr(92)
PATH_NEEDLES = ["C:" + BS + "Users", "C:/Users", "/c/Users", "D:" + BS, "/d/", "AppData" + BS, "AppData/", "/home/", "/Users/"]
KEY_SHAPE = re.compile(r"(api[_-]?key|authorization|bearer)\s*[:=]\s*[\"']?[A-Za-z0-9_\-]{24,}", re.I)


def git(*args: str) -> str:
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def load_key() -> str | None:
    key = os.environ.get("CLOCKED_API_KEY")
    env = ROOT.parent / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("CLOCKED_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key or None


def files_with(needle: str, rev: str) -> set[str]:
    out = git("grep", "-I", "-l", "-i", "-F", needle, rev, "--", ".")
    return {l.split(":", 1)[1] for l in out.splitlines() if ":" in l}


def main() -> int:
    extra = sys.argv[1:]
    revs = git("rev-list", "--all").split()
    problems = 0
    print(f"{len(revs)} revisions; authors and committers:")
    for line in sorted(set(git("log", "--all", "--format=%an <%ae> | %cn <%ce>").splitlines())):
        print("   ", line)

    key = load_key()
    if key:
        hits = set()
        for rev in revs:
            hits |= files_with(key, rev)
        tree = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
                if p.is_file() and ".git" not in p.parts and key.encode() in p.read_bytes()]
        print(f"API key: in {len(hits)} files across history, in {len(tree)} files in the working tree")
        problems += len(hits) + len(tree)
    else:
        print("API key: not available to compare against (set CLOCKED_API_KEY to check)")

    shaped = [l for l in git("grep", "-I", "-n", "-E", KEY_SHAPE.pattern, "--", ".", ":!recordings").splitlines()]
    print(f"key-shaped assignments outside recordings: {len(shaped)}")
    for l in shaped[:5]:
        print("   ", l[:160])
    problems += len(shaped)

    for needle in PATH_NEEDLES + extra:
        found = set()
        for rev in revs:
            found |= files_with(needle, rev)
        # upstream documentation quoted in recordings and reports may legitimately mention /home/ or /Users/
        ours = sorted(f for f in found if not f.startswith(("recordings/", "reports/", "runs/")))
        quoted = len(found) - len(ours)
        note = f" (plus {quoted} files of quoted upstream docs)" if quoted else ""
        print(f"{needle!r:14} in {len(ours)} of our files across history{note}", ours[:5])
        problems += len(ours)

    msgs = git("log", "--all", "--format=%B")
    in_msgs = [n for n in PATH_NEEDLES + extra if n.lower() in msgs.lower()]
    print("in commit messages:", in_msgs or "nothing")
    problems += len(in_msgs)
    print("RESULT:", "clean" if problems == 0 else f"{problems} thing(s) to look at")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
