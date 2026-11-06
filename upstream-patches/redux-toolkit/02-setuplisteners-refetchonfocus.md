<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- redux-toolkit CONTRIBUTING.md has no rule about AI assistance. -->
<!-- Patch: upstream-patches/redux-toolkit/02-setuplisteners-refetchonfocus.patch  (apply with `git apply` on top of reduxjs/redux-toolkit@c03783eb02) -->

**Title:** docs: setupListeners enables refetchOnFocus, not refetchOnMount

## What

Three summaries of `setupListeners()` said it enables `refetchOnMount`. The API page says `refetchOnFocus`.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/rtk-query/api/setupListeners.mdx` line 14](https://github.com/reduxjs/redux-toolkit/blob/c03783eb0242272841e7d8d9dccb1c7bc4f5aef6/docs/rtk-query/api/setupListeners.mdx#L14-L14)

> A utility used to enable `refetchOnFocus` and `refetchOnReconnect` behaviors.

This one does not: [`docs/introduction/getting-started.md` line 184](https://github.com/reduxjs/redux-toolkit/blob/c03783eb0242272841e7d8d9dccb1c7bc4f5aef6/docs/introduction/getting-started.md#L184-L184)

> A utility used to enable `refetchOnMount` and `refetchOnReconnect` behaviors.

Code: packages/toolkit/src/query/core/setupListeners.ts dispatches onFocus, onFocusLost, onOnline and onOffline; nothing in it concerns mounting. The same wording is at docs/rtk-query/overview.md:85 and packages/toolkit/README.md:107.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
