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
    # Added later on day 1 (see report): two of the first three targets
    # produced no confirmed contradictions, so two more were added to test
    # whether the method generalises.
    "jest": {
        "repo": "jestjs/jest",
        "commit": "72614448ecb9d16c58d6474b3091247c14a5c090",
        "includes": ["README.md", "docs/*.md", "packages/*/README.md"],
        "excludes": [r"CHANGELOG"],
        "readme": "README.md",
    },
    "typeorm": {
        "repo": "typeorm/typeorm",
        "commit": "5bdc67882dee5a02d975d5ed140c9c3f91661116",
        "includes": ["README.md", "docs/docs/**/*.md"],
        "excludes": [r"CHANGELOG"],
        "readme": "README.md",
    },
    # Day 2: six more targets, picked because reference docs, TypeScript/API
    # docs and migration guides restate the same facts.
    "mongoose": {
        "repo": "Automattic/mongoose",
        "commit": "bff9821f41a8bbe2add28fc912a68ba2fff02177",
        "includes": ["README.md", "docs/*.md", "docs/tutorials/*.md", "docs/typescript/*.md"],
        "excludes": [r"CHANGELOG"],
        "readme": "README.md",
    },
    "mikro-orm": {
        "repo": "mikro-orm/mikro-orm",
        "commit": "35fe690bf45ce72c4b86acb15d6de06fdbd09e8a",
        "includes": ["README.md", "docs/docs/**/*.md"],
        "excludes": [r"CHANGELOG", r"versioned_docs"],
        "readme": "README.md",
    },
    "eslint": {
        "repo": "eslint/eslint",
        "commit": "17f17cd7a248c532cfce61b7f915760608ca7121",
        # the 312 per-rule pages are excluded: each documents a different rule
        "includes": ["README.md", "docs/src/use/**/*.md", "docs/src/extend/**/*.md",
                     "docs/src/integrate/**/*.md", "docs/src/contribute/**/*.md",
                     "docs/src/maintain/**/*.md", "packages/js/README.md"],
        "excludes": [r"CHANGELOG"],
        "readme": "README.md",
    },
    "redux-toolkit": {
        "repo": "reduxjs/redux-toolkit",
        "commit": "c03783eb0242272841e7d8d9dccb1c7bc4f5aef6",
        "includes": ["README.md", "docs/**/*.md", "docs/**/*.mdx", "packages/toolkit/README.md"],
        "excludes": [r"CHANGELOG"],
        "readme": "README.md",
    },
    "vitest": {
        "repo": "vitest-dev/vitest",
        "commit": "c0346ba216dc3c6a7ba5f9c7723da5c0d951a2ca",
        "includes": ["README.md", "docs/*.md", "docs/config/**/*.md", "docs/guide/**/*.md", "docs/api/**/*.md"],
        "excludes": [r"CHANGELOG", r"^docs/blog"],
        "readme": "README.md",
    },
    "got": {
        "repo": "sindresorhus/got",
        "commit": "6b5aafc1cd538998728be6f45c65b0f80bae01b2",
        "includes": ["readme.md", "documentation/**/*.md"],
        "excludes": [r"CHANGELOG"],
        "readme": "readme.md",
    },
}


def load(project: str):
    from .sections import load_project
    t = TARGETS[project]
    return load_project(project, TARGETS_ROOT / project, t["includes"], t["excludes"])
