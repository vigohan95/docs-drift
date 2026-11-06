<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- fastify CONTRIBUTING.md: pull requests must be opened by a human, and pure-AI contributions with no human in the loop are not welcome. Read the change and the source lines yourself first. Docs are wrapped at 80 columns. -->
<!-- Patch: upstream-patches/fastify/04-typescript-onsend-payload-types.patch  (apply with `git apply` on top of fastify/fastify@6c14896e67) -->

**Title:** docs(typescript): onSend may change the payload to a ReadableStream or Response

## What

The note under `onSendHookHandler` now lists the same payload types as the Hooks reference.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/Reference/Hooks.md` line 240](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/Hooks.md#L240-L241)

> > If you change the payload, you may only change it to a `string`, a
> > `Buffer`, a `stream`, a `ReadableStream`, a `Response`, or `null`.

This one does not: [`docs/Reference/TypeScript.md` line 1592](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/TypeScript.md#L1592-L1593)

> >  If you change the payload, you may only change it to a string,
> > a Buffer, a stream, or null.

Code: lib/reply.js:183-188 accepts web streams (`getReader`) and `Response` objects.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
