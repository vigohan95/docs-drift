"""Command line interface.

  docsdrift scan <path-to-repo>            scan any documentation tree
  docsdrift target <name>                  scan one of the pinned demo targets
  docsdrift cost                           credits spent so far (local ledger)

Add --offline to replay recorded API answers only (no network, no key, no credits).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from .client import Clocked, CacheMiss, DEFAULT_BUDGET, LEDGER, REPO_ROOT

DEFAULT_INCLUDES = ["README.md", "readme.md", "README.mdx", "docs/**/*.md", "docs/**/*.mdx", "doc/**/*.md",
                    "documentation/**/*.md", "website/docs/**/*.md", "website/docs/**/*.mdx"]
DEFAULT_EXCLUDES = [r"CHANGELOG", r"versioned_docs", r"node_modules", r"/i18n/", r"(^|/)blog/"]
REPORTS = REPO_ROOT / "reports"


def _git(path: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def detect_repo(path: Path) -> tuple[str, str]:
    commit = _git(path, "rev-parse", "HEAD")
    url = _git(path, "config", "--get", "remote.origin.url")
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return (m.group(1) if m else ""), commit


TIER_WORDS = {
    "confirmed": "both checks agree",
    "likely": "one check agrees",
    "unchecked": "not checked",
    "weak": "not listed: neither check agrees",
    "out_of_scope": "not listed: /compare calls it a scope or name difference",
}
KIND_WORDS = {"value": "a value", "date_or_version": "a version", "rule_or_condition": "a rule",
              "scope": "scope", "name": "a name"}
LISTED = ("confirmed", "likely", "unchecked")


def _short(text: str, limit: int = 140) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def print_report(rep: dict, show_all: bool = False, out=None):
    """The list a maintainer reads: what was read, what was kept, and each item with both passages."""
    st = rep["stats"]
    w = (out or sys.stdout).write
    tiers = Counter(f["tier"] for f in rep["findings"])
    listed = sum(tiers.get(t, 0) for t in LISTED)
    where = f"{rep.get('repo') or rep['project']} @ {(rep.get('commit') or '')[:10]}".rstrip(" @")
    w(f"\n{where}\n")
    w(f"  {st['passages']:>5} passages in {st['files']} files\n")
    w(f"  {st['pairs_compared']:>5} pairs of passages read\n")
    w(f"  {st['findings']:>5} flagged by /compare\n")
    detail = f"  ({tiers.get('confirmed', 0)} where both checks agree, {tiers.get('likely', 0)} where one does)" if listed else ""
    w(f"  {listed:>5} listed for review{detail}\n")
    w(f"  credits: {st['credits_total']:.0f} at list price, {st['live_credits']:.0f} spent now "
      f"({st['cache_hits']} answers replayed from recordings)\n")
    order = {"confirmed": 0, "likely": 1, "unchecked": 2, "weak": 3, "out_of_scope": 4}
    n = 0
    for f in sorted(rep["findings"], key=lambda f: (order.get(f["tier"], 9), -(f.get("confidence") or 0))):
        if f["tier"] not in LISTED and not show_all:
            continue
        n += 1
        w(f"\n{n:>3}. The two passages disagree on {KIND_WORDS.get(f['kind'], f['kind'])}"
          f"   [{TIER_WORDS.get(f['tier'], f['tier'])}]\n")
        for side in ("a", "b"):
            s = f[side]
            w(f"     {s['path']}:{s['line_start']}\n         {_short(s['statement'] or s['quote'] or '')}\n")
        e = f.get("elsewhere") or {}
        names = {"a": "the first passage", "b": "the second passage"}
        for pl in e.get("places", []):
            if pl["agrees_with"]:
                w(f"     also stated at {pl['path']}:{pl['line']}, which agrees with {names[pl['agrees_with']]}\n")
        if e.get("outlier"):
            w(f"     {names[e['outlier']]} is probably the stale one "
              f"({e['votes'][e['outlier']]} place for it, {e['votes']['b' if e['outlier'] == 'a' else 'a']} for the other)\n")
        if rep.get("repo"):
            w(f"     {f['a']['url']}\n     {f['b']['url']}\n")
    if listed:
        w("\nThis is a list to review, not a verdict. Read both passages and the code before changing anything.\n")
    else:
        w("\nNothing listed. That means no pair passed the checks, not that the docs are free of contradictions.\n")


def _run(args, project, root, includes, excludes, repo, commit):
    from .scan import scan
    client = Clocked(offline=args.offline, budget=args.budget)
    try:
        rep = scan(project, root, includes, excludes, repo=repo, commit=commit, client=client,
                   max_neardup=args.max_pairs, max_key=args.max_key_pairs, both_orders=args.both_orders,
                   swap=not args.no_swap,
                   gate=not args.no_gate, elsewhere=not args.no_elsewhere,
                   log=(lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr)))
    except CacheMiss as e:
        print(f"offline replay failed: {e}\nThis tree (or these options) was never scanned live.", file=sys.stderr)
        return 2
    rep["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # A replay reproduces a report that is already in reports/, so it only writes a file when asked to.
    out = Path(args.out) if args.out else (None if args.offline else REPORTS / f"{project}.json")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    if not args.quiet:
        print_report(rep, args.all)
        print(f"JSON report: {out}" if out else "Replay only: nothing written. Add --out FILE to save the JSON report.")
    return 0


def main(argv=None) -> int:
    # Quoted documentation contains characters a legacy console code page cannot encode.
    # Print a replacement character instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="docsdrift", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--max-pairs", type=int, default=120, help="near-duplicate passage pairs to compare")
        p.add_argument("--max-key-pairs", type=int, default=30, help="shared-option passage pairs to compare")
        p.add_argument("--both-orders", action="store_true",
                       help="compare every pair in both orders (finds more, costs twice as much)")
        p.add_argument("--no-swap", action="store_true", help="skip the swapped-order /compare check")
        p.add_argument("--no-gate", action="store_true", help="skip the /grounding second opinion")
        p.add_argument("--no-elsewhere", action="store_true", help="skip the /rerank search for other places")
        p.add_argument("--offline", action="store_true", help="replay recordings only; no network, no key")
        p.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="stop when the ledger reaches this many credits")
        p.add_argument("--out", help="where to write the JSON report")
        p.add_argument("--all", action="store_true", help="also print findings that are not reported by default")
        p.add_argument("--quiet", action="store_true")

    s = sub.add_parser("scan", help="scan a documentation tree")
    s.add_argument("path")
    s.add_argument("--name", help="project name used in ids (default: directory name)")
    s.add_argument("--include", action="append", help="glob relative to path (repeatable)")
    s.add_argument("--exclude", action="append", help="regex on the relative path (repeatable)")
    s.add_argument("--repo", help="owner/name on GitHub, for line links")
    s.add_argument("--commit", help="commit hash, for line links")
    common(s)

    t = sub.add_parser("target", help="scan a pinned demo target from docsdrift/targets.py")
    t.add_argument("name")
    common(t)

    sub.add_parser("cost", help="credits spent so far")

    args = ap.parse_args(argv)
    if args.cmd == "cost":
        rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()] if LEDGER.exists() else []
        by = Counter()
        for r in rows:
            by[r["endpoint"]] += r["credits"]
        print(f"{len(rows)} live calls, {sum(by.values()):.0f} credits", dict(by))
        return 0
    if args.cmd == "target":
        from .targets import TARGETS, TARGETS_ROOT
        if args.name not in TARGETS:
            print(f"unknown target {args.name}; known: {', '.join(TARGETS)}", file=sys.stderr)
            return 2
        t = TARGETS[args.name]
        return _run(args, args.name, TARGETS_ROOT / args.name, t["includes"], t["excludes"], t["repo"], t["commit"])
    root = Path(args.path)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    repo, commit = detect_repo(root)
    repo, commit = args.repo or repo, args.commit or commit
    if not (args.include or args.exclude or args.name):
        # A clone of one of the pinned demo targets: use the file selection it was measured with,
        # so that `scan <clone> --offline` replays the recorded run.
        from .targets import TARGETS
        for name, t in TARGETS.items():
            if t["repo"] == repo and t["commit"] == commit:
                return _run(args, name, root, t["includes"], t["excludes"], repo, commit)
    return _run(args, args.name or root.resolve().name, root, args.include or DEFAULT_INCLUDES,
                args.exclude or DEFAULT_EXCLUDES, repo, commit)


if __name__ == "__main__":
    sys.exit(main())
