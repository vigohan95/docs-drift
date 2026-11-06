<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- rollup CONTRIBUTING.md: using AI to create a pull request is fine, but you must allow maintainer edits. -->
<!-- Patch: upstream-patches/rollup/01-introduction-es-modules-support.patch  (apply with `git apply` on top of rollup/rollup@82bef03ce4) -->

**Title:** docs: update the ES module support sentence in the introduction

## What

The introduction said ES modules are not finalised in Node.js. This replaces that sentence with the wording the README already uses for the same paragraph.

## Why

Two places in the docs disagree.

This is the newer wording: [`README.md` line 71](https://github.com/rollup/rollup/blob/82bef03ce41b38810d375f2b302379b97d8e9468/README.md#L71-L71)

> Most browsers and Node.js support ES modules.

This is the older wording: [`docs/introduction/index.md` line 52](https://github.com/rollup/rollup/blob/82bef03ce41b38810d375f2b302379b97d8e9468/docs/introduction/index.md#L52-L52)

> The specification is now fixed, but it is only implemented in modern browsers and not finalised in Node.js.

Note: No source file settles this; the README paragraph is the newer wording of the same paragraph and matches Node.js since 12.17.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
