<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- typeorm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...). -->
<!-- Patch: upstream-patches/typeorm/01-getting-started-es2023.patch  (apply with `git apply` on top of typeorm/typeorm@5bdc67882d) -->

**Title:** docs: say ES2023 in getting-started, as the README does

## What

One word: the intro sentence in `docs/docs/getting-started.md` still said ES2021.

## Why

Two places in the docs disagree.

This one matches the code: [`README.md` line 19](https://github.com/typeorm/typeorm/blob/5bdc67882dee5a02d975d5ed140c9c3f91661116/README.md#L19-L19)

> and can be used with TypeScript and JavaScript (ES2023).

This one does not: [`docs/docs/getting-started.md` line 5](https://github.com/typeorm/typeorm/blob/5bdc67882dee5a02d975d5ed140c9c3f91661116/docs/docs/getting-started.md#L5-L5)

> and can be used with TypeScript and JavaScript (ES2021).

Code: PR #11382 (drop Node 16 and 18) changed the README from ES2021 to ES2023 and moved tsconfig.json to @tsconfig/node20; getting-started.md was not touched.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
