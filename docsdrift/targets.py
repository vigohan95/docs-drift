"""Target projects for the day-1 feasibility run (commit hashes pinned)."""
from pathlib import Path

TARGETS_ROOT = Path(__file__).resolve().parent.parent.parent / "targets"

TARGETS = {
    "fastify": {
        "repo": "fastify/fastify",
        "commit": "6c14896e67dd299ce277d667f220ceb23b20d277",
        "includes": ["README.md", "docs/**/*.md", "SECURITY.md", "GOVERNANCE.md", "CONTRIBUTING.md"],
        "excludes": [],
        "readme": "README.md",
    },
    "prometheus": {
        "repo": "prometheus/prometheus",
        "commit": "0e62286556b1cb798d0afdde11f11689b6cfcd7a",
        "includes": ["README.md", "docs/**/*.md", "tsdb/docs/**/*.md", "RELEASE.md",
                     "documentation/**/*.md", "storage/remote/*.md", "discovery/README.md"],
        "excludes": [],
        "readme": "README.md",
    },
    "vite": {
        "repo": "vitejs/vite",
        "commit": "a579e352a66fbdce6a51d4e1f67006ccf4f91343",
        "includes": ["README.md", "docs/guide/*.md", "docs/config/*.md", "docs/changes/*.md",
                     "docs/*.md", "docs/plugins/*.md", "packages/vite/README.md",
                     "packages/create-vite/README.md", "packages/plugin-legacy/README.md"],
        # blog posts and changelogs are historical statements, not current docs
        "excludes": [r"^docs/blog/", r"CHANGELOG", r"LICENSE"],
        "readme": "packages/vite/README.md",
    },
}


def load(project: str):
    from .sections import load_project
    t = TARGETS[project]
    return load_project(project, TARGETS_ROOT / project, t["includes"], t["excludes"])
