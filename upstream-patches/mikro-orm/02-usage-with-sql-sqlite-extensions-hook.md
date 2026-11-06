<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- mikro-orm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...). -->
<!-- Patch: upstream-patches/mikro-orm/02-usage-with-sql-sqlite-extensions-hook.patch  (apply with `git apply` on top of mikro-orm/mikro-orm@35fe690bf4) -->

**Title:** docs: load SQLite extensions via onCreateConnection in usage-with-sql

## What

The SQL usage page loaded SQLite extensions through `pool.afterCreate`. The SQLite page uses the `onCreateConnection` hook; this makes the SQL page use the same hook.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/docs/usage-with-sqlite.md` line 229](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/usage-with-sqlite.md#L229-L229)

> Once you've downloaded the binaries for the extensions you wish to use, they can be added via the `onCreateConnection` hook:

This one does not: [`docs/docs/usage-with-sql.md` line 162](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/usage-with-sql.md#L162-L162)

> Load them via `pool.afterCreate`:

Code: packages/core/src/utils/Configuration.ts:639 defines `onCreateConnection`; PoolConfig (lines 805-812) has only min, max and idleTimeoutMillis.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
