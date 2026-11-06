<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- mikro-orm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...). -->
<!-- Patch: upstream-patches/mikro-orm/04-entity-manager-raw-tojson.patch  (apply with `git apply` on top of mikro-orm/mikro-orm@35fe690bf4) -->

**Title:** docs: raw() fragments can be serialized with toJSON

## What

One sentence in the EntityManager page said a `raw()` fragment disallows serialization via `toJSON`.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/docs/raw-queries.md` line 7](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/raw-queries.md#L7-L7)

> This fragment is represented by `RawQueryFragment` class instance that can be serialized to a string, so it can be used both as an object value and key.

This one does not: [`docs/docs/entity-manager.md` line 681](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/entity-manager.md#L681-L681)

> It disallows serialization (via `toJSON`) as well as working with the value

Code: packages/core/src/utils/RawQueryFragment.ts:100-102: `toJSON()` returns the string `raw('...')`; only conversion to a non-string primitive throws (lines 86-94).

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
