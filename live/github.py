"""Read the Markdown documentation of a public GitHub repository, in memory.

Two requests, both to fixed GitHub hosts built from a validated owner/name:
  1. api.github.com/repos/<owner>/<name>/commits/HEAD      -> the commit hash
  2. codeload.github.com/<owner>/<name>/tar.gz/<hash>      -> the source tarball, streamed

The tarball is read as a stream and never unpacked to disk. Only regular files that look like
documentation Markdown are kept, as text. Nothing from the repository is executed, imported or
written anywhere. Size, file-count and download limits stop a huge or hostile archive early.
"""
from __future__ import annotations

import re
import tarfile
import urllib.error
import urllib.request

OWNER_REPO = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
DOC_DIRS = ("docs/", "doc/", "documentation/", "website/docs/")
SKIP = re.compile(r"CHANGELOG|versioned_docs|node_modules|(^|/)i18n/|(^|/)blog/|(^|/)(zh|zh-cn|ja|ko|es|pt|pt-br|fr|de|ru|it)/", re.I)
UA = "docs-drift-live/0.1 (+https://github.com/vigohan95/docs-drift)"


class GitHubError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class _Capped:
    """A file object that refuses to read more than `limit` bytes."""

    def __init__(self, raw, limit: int):
        self.raw, self.limit, self.seen = raw, limit, 0

    def read(self, n: int = -1) -> bytes:
        data = self.raw.read(n if n and n > 0 else 65536)
        self.seen += len(data)
        if self.seen > self.limit:
            raise GitHubError("too_large", f"The repository archive is larger than {self.limit // 1_000_000} MB, "
                              "which is more than the live trial downloads. The full tool has no such limit.")
        return data


def wanted(path: str) -> bool:
    """Documentation Markdown: a root README, or anything under a docs directory."""
    low = path.lower()
    if not low.endswith((".md", ".mdx")) or ".." in path.split("/") or SKIP.search(path):
        return False
    if "/" not in path:
        return low.startswith("readme")
    return low.startswith(DOC_DIRS)


def _open(url: str, opener, accept: str | None = None, timeout: float = 30.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Accept": accept} if accept else {})})
    try:
        return opener(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise GitHubError("not_found", "GitHub has no public repository with that name.")
        if e.code in (403, 429):
            raise GitHubError("github_rate_limited", "GitHub is rate-limiting this service right now. Try again in a "
                              "few minutes, or see the recorded scans on this page.")
        raise GitHubError("github_error", f"GitHub answered HTTP {e.code}.")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        raise GitHubError("github_unreachable", "GitHub could not be reached from this service. Try again shortly.")


def fetch_markdown(repo: str, limits, opener=urllib.request.urlopen) -> tuple[str, dict[str, str]]:
    """Return (commit hash, {path: text}) for the documentation Markdown of owner/name at HEAD."""
    if not OWNER_REPO.match(repo):
        raise GitHubError("bad_input", "Give a repository as owner/name.")
    with _open(f"https://api.github.com/repos/{repo}/commits/HEAD", opener, "application/vnd.github.sha") as resp:
        sha = resp.read(200).decode("ascii", "replace").strip()
    if not SHA.match(sha):
        raise GitHubError("github_error", "GitHub did not return a commit hash for that repository.")
    files: dict[str, str] = {}
    total = 0
    with _open(f"https://codeload.github.com/{repo}/tar.gz/{sha}", opener, timeout=60.0) as resp:
        try:
            with tarfile.open(fileobj=_Capped(resp, limits.max_tarball_bytes), mode="r|gz") as tar:
                for member in tar:
                    if not member.isfile():
                        continue                                  # no directories, links or devices
                    path = member.name.split("/", 1)[1] if "/" in member.name else member.name
                    if not wanted(path) or member.size > limits.max_file_bytes:
                        continue
                    if len(files) >= limits.max_files or total + member.size > limits.max_total_bytes:
                        break                                     # enough to work with; stop downloading
                    fh = tar.extractfile(member)                  # reads from the stream; nothing is written
                    if fh is None:
                        continue
                    files[path] = fh.read().decode("utf-8", errors="replace")
                    total += member.size
        except tarfile.TarError:
            raise GitHubError("github_error", "The archive GitHub returned could not be read.")
        except (TimeoutError, ConnectionError, OSError) as e:
            if isinstance(e, GitHubError):
                raise
            raise GitHubError("github_unreachable", "The download from GitHub was interrupted. Try again shortly.")
    if not files:
        raise GitHubError("no_markdown", "No documentation Markdown was found: the live trial looks for a root README "
                          "and for .md or .mdx files under docs/, doc/, documentation/ or website/docs/.")
    return sha, files
