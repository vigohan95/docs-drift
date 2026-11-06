"""Clone the demo targets at their pinned commits into ../targets/<name>.

    python scripts/fetch_targets.py            # all targets
    python scripts/fetch_targets.py fastify    # one target

Only `git` is run. Nothing from the cloned repositories is executed; the tool reads
their Markdown files as text. With the clones in place, a scan can be replayed offline:

    python -m docsdrift target fastify --offline
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docsdrift.targets import TARGETS, TARGETS_ROOT  # noqa: E402


def run(*args: str, cwd: Path | None = None) -> int:
    return subprocess.run(list(args), cwd=cwd).returncode


def fetch(name: str) -> bool:
    t = TARGETS[name]
    dest = TARGETS_ROOT / name
    if (dest / ".git").exists():
        head = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if head == t["commit"]:
            print(f"{name}: already at {head[:10]}")
            return True
        print(f"{name}: exists at {head[:10]}, expected {t['commit'][:10]}; leaving it alone")
        return False
    dest.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{t['repo']}.git"
    ok = (run("git", "init", "-q", str(dest)) == 0
          and run("git", "-C", str(dest), "remote", "add", "origin", url) == 0
          and run("git", "-C", str(dest), "-c", "core.symlinks=false", "fetch", "-q", "--depth", "1", "origin", t["commit"]) == 0
          and run("git", "-C", str(dest), "-c", "core.symlinks=false", "-c", "core.longpaths=true", "checkout", "-q", "FETCH_HEAD") == 0)
    print(f"{name}: {'fetched ' + t['commit'][:10] if ok else 'FAILED'}")
    return ok


if __name__ == "__main__":
    names = sys.argv[1:] or list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        sys.exit(f"unknown target(s): {', '.join(unknown)}; known: {', '.join(TARGETS)}")
    results = [fetch(n) for n in names]
    sys.exit(0 if all(results) else 1)
