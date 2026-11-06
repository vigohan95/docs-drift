<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- mikro-orm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...). -->
<!-- Patch: upstream-patches/mikro-orm/03-defining-entities-tojson-default.patch  (apply with `git apply` on top of mikro-orm/mikro-orm@35fe690bf4) -->

**Title:** docs: Type.toJSON uses the runtime value by default

## What

One sentence in the Defining Entities page said the default converts to the database value.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/docs/custom-types.md` line 20](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/custom-types.md#L20-L20)

> Converts a value from its JS representation to its serialized JSON form of this type. By default, uses the runtime value.

This one does not: [`docs/docs/defining-entities.md` line 1616](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/defining-entities.md#L1616-L1616)

> Converts a value from its JS representation to its serialized JSON form of this type. By default, converts to the database value.

Code: packages/core/src/types/Type.ts:90-92: `toJSON(value) { return value; }`.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
