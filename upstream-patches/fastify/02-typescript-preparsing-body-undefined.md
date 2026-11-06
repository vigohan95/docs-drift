<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- fastify CONTRIBUTING.md: pull requests must be opened by a human, and pure-AI contributions with no human in the loop are not welcome. Read the change and the source lines yourself first. Docs are wrapped at 80 columns. -->
<!-- Patch: upstream-patches/fastify/02-typescript-preparsing-body-undefined.patch  (apply with `git apply` on top of fastify/fastify@6c14896e67) -->

**Title:** docs(typescript): request.body is undefined, not null, in preParsing

## What

In the TypeScript reference, the note under `preParsingHookHandler` now says `undefined`, as the Hooks reference does.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/Reference/Hooks.md` line 104](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/Hooks.md#L104-L106)

> > In the [preParsing](#preparsing) hook, `request.body` will always be
> > `undefined`, because the body parsing happens before the
> > [preValidation](#prevalidation) hook.

This one does not: [`docs/Reference/TypeScript.md` line 1550](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/TypeScript.md#L1550-L1551)

> Notice: in the `preParsing` hook, request.body will always be null, because the
> body parsing happens before the `preValidation` hook.

Code: lib/request.js:40 sets `this.body = undefined`.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
