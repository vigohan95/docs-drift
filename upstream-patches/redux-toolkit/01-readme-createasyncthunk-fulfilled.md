<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- redux-toolkit CONTRIBUTING.md has no rule about AI assistance. -->
<!-- Patch: upstream-patches/redux-toolkit/01-readme-createasyncthunk-fulfilled.patch  (apply with `git apply` on top of reduxjs/redux-toolkit@c03783eb02) -->

**Title:** docs: createAsyncThunk dispatches pending/fulfilled/rejected

## What

One word in `packages/toolkit/README.md`: `resolved` becomes `fulfilled`.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/introduction/getting-started.md` line 157](https://github.com/reduxjs/redux-toolkit/blob/c03783eb0242272841e7d8d9dccb1c7bc4f5aef6/docs/introduction/getting-started.md#L157-L157)

> generates a thunk that dispatches `pending/fulfilled/rejected` action types based on that promise

This one does not: [`packages/toolkit/README.md` line 78](https://github.com/reduxjs/redux-toolkit/blob/c03783eb0242272841e7d8d9dccb1c7bc4f5aef6/packages/toolkit/README.md#L78-L78)

> generates a thunk that dispatches `pending/resolved/rejected` action types based on that promise

Code: packages/toolkit/src/createAsyncThunk.ts:544 builds `typePrefix + '/fulfilled'`.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
