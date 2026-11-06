<!-- DRAFT for a human to rewrite in their own words. Do not paste as is. -->
<!-- mikro-orm CONTRIBUTING.md has no rule about AI assistance. Commit titles follow Conventional Commits (docs: ...). -->
<!-- Patch: upstream-patches/mikro-orm/01-unit-of-work-flush-managed-entities.patch  (apply with `git apply` on top of mikro-orm/mikro-orm@35fe690bf4) -->

**Title:** docs: flush checks all managed entities, not only persisted ones

## What

One sentence in the Unit of Work page said `em.flush()` iterates over the entities marked via `em.persist()`.

## Why

Two places in the docs disagree.

This one matches the code: [`docs/docs/guide/01-first-entity.md` line 389](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/guide/01-first-entity.md#L389-L389)

> Whenever you call [`em.flush()`](/api/core/class/EntityManager#flush), the ORM will iterate over the Identity Map, and for each entity it compares the original state with the values that are currently set on the entity.

This one does not: [`docs/docs/unit-of-work.md` line 85](https://github.com/mikro-orm/mikro-orm/blob/35fe690bf45ce72c4b86acb15d6de06fdbd09e8a/docs/docs/unit-of-work.md#L85-L85)

> Now whenever you call `em.flush()` MikroORM will iterate over all entities you previously marked for persisting via `em.persist()`.

Code: packages/core/src/unit-of-work/UnitOfWork.ts computeChangeSets walks the identity map (line 769) and then the persist stack (775). unit-of-work.md:34 itself says managed entities need no persist call.

## How I found it

I ran a small script over the docs that pairs passages which restate each other and asks the Clocked API whether they conflict. It flagged this pair. I then read both passages and the source lines above before preparing this change. The patch touches only the lines shown.

## Duplicates

I searched the issues and pull requests of this repository on 2026-11-07 for the file name and the key terms and found nothing about this.
