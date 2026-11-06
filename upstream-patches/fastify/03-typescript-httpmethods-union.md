<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- fastify CONTRIBUTING.md: pull requests must be opened by a human, and pure-AI contributions with no human in the loop are not welcome. Read the change and the source lines yourself first. Docs are wrapped at 80 columns. -->
<!-- Patch: upstream-patches/fastify/03-typescript-httpmethods-union.patch  (apply with `git apply` on top of fastify/fastify@6c14896e67) -->

**Title:** docs(typescript): list all members of fastify.HTTPMethods

## What

The TypeScript reference listed seven methods for `fastify.HTTPMethods`. The type has nineteen, in either case, and also accepts any other string. The list now matches `types/utils.d.ts`.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/Reference/Server.md` line 1667](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/Server.md#L1667-L1668)

> Fastify supports the `GET`, `HEAD`, `TRACE`, `DELETE`, `OPTIONS`,
> `PATCH`, `PUT`, `POST` and `QUERY` HTTP methods by default.

This one does not: [`docs/Reference/TypeScript.md` line 1103](https://github.com/fastify/fastify/blob/6c14896e67dd299ce277d667f220ceb23b20d277/docs/Reference/TypeScript.md#L1103-L1104)

> Union type of: `'DELETE' | 'GET' | 'HEAD' | 'PATCH' | 'POST' | 'PUT' |
> 'OPTIONS'`

Code: types/utils.d.ts:17-18 defines the union with 'QUERY', 'TRACE' and twelve more members. docs/Reference/Routes.md:34-35 repeats the Server.md list.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
