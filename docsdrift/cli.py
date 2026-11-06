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


def print_report(rep: dict, show_all: bool = False, out=sys.stdout):
    st = rep["stats"]
    w = out.write
    w(f"\n{rep['project']}  {rep.get('repo', '')}@{(rep.get('commit') or '')[:10]}\n")
    w(f"  {st['files']} files, {st['passages']} passages, {st['pairs_compared']} pairs compared, "
      f"{st['findings']} raw conflict findings\n")
    tiers = Counter(f["tier"] for f in rep["findings"])
    w(f"  reported: {tiers.get('confirmed', 0)} confirmed, {tiers.get('likely', 0)} likely; "
      f"filtered out by the /grounding gate: {tiers.get('filtered', 0)}\n")
    w(f"  credits: {st['credits_total']:.0f} at list price ({st['live_credits']:.0f} spent now, "
      f"{st['cache_hits']} answers replayed from recordings)\n")
    order = {"confirmed": 0, "likely": 1, "ungated": 2, "filtered": 3}
    for f in sorted(rep["findings"], key=lambda f: (order.get(f["tier"], 9), -(f.get("confidence") or 0))):
        if f["tier"] == "filtered" and not show_all:
            continue
        w(f"\n  [{f['tier'].upper()}] {f['kind']}  (id {f['id']})\n")
        for side in ("a", "b"):
            s = f[side]
            text = s["statement"] or (s["quote"] or "")[:300]
            w(f"    {s['path']}:{s['line_start']}\n      {text}\n")
        e = f.get("elsewhere") or {}
        for pl in e.get("places", []):
            if pl["agrees_with"]:
                w(f"    also stated at {pl['path']}:{pl['line']} (agrees with side {pl['agrees_with'].upper()})\n")
        if e.get("outlier"):
            w(f"    -> side {e['outlier'].upper()} is the outlier ({e['votes']['a']} vs {e['votes']['b']} places)\n")
    w("\n")


def _run(args, project, root, includes, excludes, repo, commit):
    from .scan import scan
    client = Clocked(offline=args.offline, budget=args.budget)
    try:
        rep = scan(project, root, includes, excludes, repo=repo, commit=commit, client=client,
                   max_neardup=args.max_pairs, max_key=args.max_key_pairs, swap=not args.no_swap,
                   gate=not args.no_gate, elsewhere=not args.no_elsewhere,
                   log=(lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr)))
    except CacheMiss as e:
        print(f"offline replay failed: {e}\nThis tree (or these options) was never scanned live.", file=sys.stderr)
        return 2
    rep["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = Path(args.out) if args.out else REPORTS / f"{project}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if not args.quiet:
        print_report(rep, args.all)
        print(f"report written to {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="docsdrift", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--max-pairs", type=int, default=120, help="near-duplicate passage pairs to compare")
        p.add_argument("--max-key-pairs", type=int, default=30, help="shared-option passage pairs to compare")
        p.add_argument("--no-swap", action="store_true", help="skip the swapped-order /compare check")
        p.add_argument("--no-gate", action="store_true", help="skip the /grounding second opinion")
        p.add_argument("--no-elsewhere", action="store_true", help="skip the /rerank search for other places")
        p.add_argument("--offline", action="store_true", help="replay recordings only; no network, no key")
        p.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="stop when the ledger reaches this many credits")
        p.add_argument("--out", help="where to write the JSON report")
        p.add_argument("--all", action="store_true", help="also print findings the gate filtered out")
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
    return _run(args, args.name or root.resolve().name, root, args.include or DEFAULT_INCLUDES,
                args.exclude or DEFAULT_EXCLUDES, args.repo or repo, args.commit or commit)


if __name__ == "__main__":
    sys.exit(main())
