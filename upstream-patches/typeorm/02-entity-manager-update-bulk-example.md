<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- typeorm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...). -->
<!-- Patch: upstream-patches/typeorm/02-entity-manager-update-bulk-example.patch  (apply with `git apply` on top of typeorm/typeorm@5bdc67882d) -->

**Title:** docs: remove the update() example that uses a {criteria, data} array

## What

Removes one example from the EntityManager API page. It shows `manager.update(User, [{ criteria, data }, ...])` running three UPDATE statements; `update()` has no such form.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/docs/working-with-entity-manager/6-repository-api.md` line 154](https://github.com/typeorm/typeorm/blob/5bdc67882dee5a02d975d5ed140c9c3f91661116/docs/docs/working-with-entity-manager/6-repository-api.md#L154-L160)

> You can pass an **array of condition objects** to match multiple distinct sets of rows in a single call (conditions are OR'd together):

This one does not: [`docs/docs/working-with-entity-manager/5-entity-manager-api.md` line 189](https://github.com/typeorm/typeorm/blob/5bdc67882dee5a02d975d5ed140c9c3f91661116/docs/docs/working-with-entity-manager/5-entity-manager-api.md#L189-L198)

> // Bulk updates with different conditions for each operation
> await manager.update(User, [
>     { criteria: { id: 1 }, data: { firstName: "Rizzrak" } },
>     { criteria: { id: 2 }, data: { firstName: "Karzzir" } },
>     { criteria: { age: 18 }, data: { category: "ADULT" } },
> ])
> // executes three separate UPDATE queries:

Code: packages/typeorm/src/entity-manager/EntityManager.ts:897-927 has only update(target, criteria, partialEntity, options); no {criteria, data} form exists in src or test. The example came in with docs PR #12025; the feature PR #10910 implemented OR-ed condition arrays. The same PR added 'three separate queries' comments to the delete and softDelete examples, which the code also runs as one query.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
