"""Write one PR description draft next to every patch, from review/defects.json.

    python -X utf8 upstream-patches/make_pr_drafts.py

The drafts are starting points for a person to rewrite. Nothing here talks to GitHub.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = json.loads((HERE.parent / "review" / "defects.json").read_text(encoding="utf-8"))

RULES = {
    "fastify": "fastify CONTRIBUTING.md: pull requests must be opened by a human, and pure-AI contributions with no "
               "human in the loop are not welcome. Read the change and the source lines yourself first. Docs are wrapped at 80 columns.",
    "typeorm": "typeorm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...).",
    "prometheus": "prometheus CONTRIBUTING.md has no rule about AI assistance. Commits need a DCO sign-off: git commit -s.",
    "mikro-orm": "mikro-orm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...).",
    "redux-toolkit": "redux-toolkit CONTRIBUTING.md has no rule about AI assistance.",
    "rollup": "rollup CONTRIBUTING.md: using AI to create a pull request is fine, but you must allow maintainer edits.",
}

TEXT = {
    "fastify/01-typescript-onrequest-body-undefined.patch": (
        "docs(typescript): request.body is undefined, not null, in onRequest",
        "In the TypeScript reference, the note under `onRequestHookHandler` now says `undefined` and names `preValidation` "
        "as the hook that body parsing precedes, as the Hooks reference does."),
    "fastify/02-typescript-preparsing-body-undefined.patch": (
        "docs(typescript): request.body is undefined, not null, in preParsing",
        "In the TypeScript reference, the note under `preParsingHookHandler` now says `undefined`, as the Hooks reference does."),
    "fastify/03-typescript-httpmethods-union.patch": (
        "docs(typescript): list all members of fastify.HTTPMethods",
        "The TypeScript reference listed seven methods for `fastify.HTTPMethods`. The type has nineteen, in either case, "
        "and also accepts any other string. The list now matches `types/utils.d.ts`."),
    "fastify/04-typescript-onsend-payload-types.patch": (
        "docs(typescript): onSend may change the payload to a ReadableStream or Response",
        "The note under `onSendHookHandler` now lists the same payload types as the Hooks reference."),
    "fastify/05-reply-final-payload-types.patch": (
        "docs(reply): add ReadableStream and Response to the final payload types",
        "The list under \"Type of the final payload\" said any other type throws. Web streams and `Response` objects are "
        "accepted, as the Hooks reference already says, so they are added to the list."),
    "typeorm/01-getting-started-es2023.patch": (
        "docs: say ES2023 in getting-started, as the README does",
        "One word: the intro sentence in `docs/docs/getting-started.md` still said ES2021."),
    "typeorm/02-entity-manager-update-bulk-example.patch": (
        "docs: remove the update() example that uses a {criteria, data} array",
        "Removes one example from the EntityManager API page. It shows `manager.update(User, [{ criteria, data }, ...])` "
        "running three UPDATE statements; `update()` has no such form."),
    "typeorm/03-delete-softdelete-single-query.patch": (
        "docs: delete() and softDelete() with a condition array run one query",
        "Two example comments said an array of condition objects runs three separate queries. The conditions are OR-ed "
        "into one query, as the paragraph right below the delete example says."),
    "prometheus/01-chunks-st-changed-on-hex.patch": (
        "docs(tsdb): 127 is 0x7F in the chunk format description",
        "One character: the XOR chunk section wrote 127 as 0xEF. The histogram chunk section of the same file has 0x7F."),
    "mikro-orm/01-unit-of-work-flush-managed-entities.patch": (
        "docs: flush checks all managed entities, not only persisted ones",
        "One sentence in the Unit of Work page said `em.flush()` iterates over the entities marked via `em.persist()`."),
    "mikro-orm/02-usage-with-sql-sqlite-extensions-hook.patch": (
        "docs: load SQLite extensions via onCreateConnection in usage-with-sql",
        "The SQL usage page loaded SQLite extensions through `pool.afterCreate`. The SQLite page uses the "
        "`onCreateConnection` hook; this makes the SQL page use the same hook."),
    "mikro-orm/03-defining-entities-tojson-default.patch": (
        "docs: Type.toJSON uses the runtime value by default",
        "One sentence in the Defining Entities page said the default converts to the database value."),
    "mikro-orm/04-entity-manager-raw-tojson.patch": (
        "docs: raw() fragments can be serialized with toJSON",
        "One sentence in the EntityManager page said a `raw()` fragment disallows serialization via `toJSON`."),
    "redux-toolkit/01-readme-createasyncthunk-fulfilled.patch": (
        "docs: createAsyncThunk dispatches pending/fulfilled/rejected",
        "One word in `packages/toolkit/README.md`: `resolved` becomes `fulfilled`."),
    "redux-toolkit/02-setuplisteners-refetchonfocus.patch": (
        "docs: setupListeners enables refetchOnFocus, not refetchOnMount",
        "Three summaries of `setupListeners()` said it enables `refetchOnMount`. The API page says `refetchOnFocus`."),
    "rollup/01-introduction-es-modules-support.patch": (
        "docs: update the ES module support sentence in the introduction",
        "The introduction said ES modules are not finalised in Node.js. This replaces that sentence with the wording the "
        "README already uses for the same paragraph."),
}

EXTRA_FOR = {"typeorm/03-delete-softdelete-single-query.patch": "typeorm-update-bulk-overload"}


def quote_block(text: str) -> str:
    return "\n".join("> " + line for line in text.split("\n"))


def draft(patch: str, d: dict) -> str:
    title, what = TEXT[patch]
    right, wrong = ("a", "b") if d["wrong"] == "b" else ("b", "a")
    lines = [
        "<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->",
        f"<!-- {RULES[d['project']]} -->",
        f"<!-- Patch: upstream-patches/{patch}  (apply with `git apply` on top of {d['repo']}@{d['commit'][:10]}) -->",
        "",
        f"**Title:** {title}",
        "",
        "## What",
        "",
        what,
        "",
        "## Why",
        "",
        "Two places in the docs disagree.",
        "",
    ]
    no_code = d["source"].startswith("No source file")
    words = ("This is the newer wording", "This is the older wording") if no_code else \
            ("This one matches the code", "This one does not")
    for side, word in ((right, words[0]), (wrong, words[1])):
        s = d[side]
        lines += [f"{word}: [`{s['path']}` line {s['lines'][0]}]({s['url']})", "", quote_block(s["quote"]), ""]
    lines += [("Note: " if no_code else "Code: ") + d["source"], ""]
    if patch in EXTRA_FOR:
        lines += ["This patch covers the delete and softDelete comments from the same docs PR. I noticed them while "
                  "checking the update example; the tool did not flag them.", ""]
    lines += [
        "## How I found it",
        "",
        "I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API "
        "whether they conflict. It flagged this pair. I then read both passages and the source lines above before "
        "preparing this change. The patch touches only the lines shown.",
        "",
        "## Duplicates",
        "",
        f"I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms "
        f"and found nothing about this.",
        "",
    ]
    return "\n".join(lines)


def main():
    by_patch = {}
    for d in REG["defects"]:
        if d.get("patch"):
            by_patch[d["patch"]] = d
        if d.get("extra_patch"):
            by_patch[d["extra_patch"]] = d
    assert set(by_patch) == set(TEXT), set(by_patch) ^ set(TEXT)
    for patch, d in sorted(by_patch.items()):
        assert (HERE / patch).exists(), patch
        (HERE / patch.replace(".patch", ".md")).write_text(draft(patch, d), encoding="utf-8")
    print(len(by_patch), "drafts written")


if __name__ == "__main__":
    main()
