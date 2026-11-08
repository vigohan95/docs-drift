# Docs Drift

Docs Drift gives maintainers a short list of places where their documentation contradicts itself, with the evidence.

It reads a project's docs, pairs the passages that restate each other, and uses the
[Clocked API](https://clocked.rezolve.ai/docs) to pick the pairs worth a person's time. Every item on the list shows
both passages with file and line. It is a list to review, not a verdict: about half of it is real.

Built for the Clocked Build Challenge (October 21 to November 10, 2026) on `/compare`, `/grounding` and `/rerank`.

Demo page: https://vigohan95.github.io/docs-drift/ (the results, plus a live trial on your own passages or a public repository). Judges: a three-minute path is in [`JUDGES.md`](JUDGES.md).

## Results

It was run on the documentation of **15 open-source projects** at pinned commits and surfaced **16 defects in 6 of
them**. Each one was checked against both passages and the project's source code, with file and line recorded in
[`review/defects.json`](review/defects.json). The final word on each belongs to the upstream maintainers.

### Upstream pull requests

| Pull request | Status | Defects | What it fixes |
|---|---|---|---|
| https://github.com/reduxjs/redux-toolkit/pull/5592 | open | 2 | `pending/resolved/rejected` in the README; `refetchOnMount` in three summaries of `setupListeners()` |
| https://github.com/typeorm/typeorm/pull/13040 | open | 2 | ES2021 in getting-started; an `update()` example that uses a call form the code does not have |
| https://github.com/mikro-orm/mikro-orm/pull/8617 | merged | 4 | what `em.flush()` checks; how to load SQLite extensions; the default of `Type.toJSON()`; whether `raw()` can be serialized |
| https://github.com/rollup/rollup/pull/6643 | merged | 1 | the introduction still says ES modules are not finalised in Node.js |
| https://github.com/fastify/fastify/pull/7193 | open | 5 | `request.body` in two hooks; the `HTTPMethods` list; `ReadableStream` and `Response` payloads |
| https://github.com/prometheus/prometheus/pull/20388 | open | 1 | the XOR2 chunk format page: the start-timestamp header byte, the 128th sample, and a stray `>` |
| fastify/fastify | not opened yet | 1 | notes for 1 issue are in `upstream-patches/fastify/` |

Status as of 2026-11-08. The source of this table is [`review/upstream_prs.json`](review/upstream_prs.json).

### Three of the sixteen

| Project | One place says | Another place says | The code |
|---|---|---|---|
| fastify | `Hooks.md:73` in `onRequest`, `request.body` is always `undefined` | `TypeScript.md:1540` it is always `null` | `lib/request.js:40` sets `this.body = undefined` |
| typeorm | `repository-api.md:154` an array passed to `update()` is a list of conditions OR-ed into one query | `entity-manager-api.md:189` shows `update(User, [{ criteria, data }, ...])` running three queries | `EntityManager.ts:897` has no such call form |
| redux-toolkit | `setupListeners.mdx:14` enables `refetchOnFocus` | `getting-started.md:184` enables `refetchOnMount` | `setupListeners.ts` handles focus and online events only |

The demo page shows all sixteen side by side, with links to the pinned commits.

### How often the list is right

Standard run: up to 150 passage pairs per project, 1,878 pairs in total.

| | Items | Real contradictions | |
|---|---|---|---|
| Everything `/compare` flagged | 52 | 13 | 25% |
| Listed for a person after the checks | 21 | 11 | 52% |
| ... on the 11 projects the listing rule was tuned on | 13 | 11 | 85% |
| ... on the 4 projects scanned after the rule was fixed | 8 | 0 | 0% |

Read the last two rows together. The rule that decides what makes the list was chosen on findings from eleven
projects, then run unchanged on four more (rollup, fiber, pydantic, svelte). There it listed eight items and none was
real. The one real contradiction in those four (rollup) was flagged by `/compare` and then dropped by the rule.

So this tool saves a maintainer from reading 1,878 pairs. It cannot be trusted to be right. Expect about half of the
list to be real, expect that to vary a lot between projects, and expect many projects to produce nothing: nine of the
fifteen did (vite, jest, mongoose, eslint, vitest, got, fiber, pydantic, svelte).

Of the 16 defects, 10 were on the standard run's list. 3 came from reading more pairs in mikro-orm, redux-toolkit and
typeorm. 3 surfaced in other runs without making the standard list. Each entry in `review/defects.json` says which.

All ten wrong items are listed with the reason in `review/labels_v2.json`. Most are sibling documents: two pages
written from one template about different things (two middlewares, two functions, two releases).

## Try it in three minutes, without a key

Python 3.10 or newer and git. No dependencies, no API key, no credits: every API answer behind the numbers above is
recorded in `recordings/`, and a scan of a project at its pinned commit replays from them.

```bash
git clone https://github.com/vigohan95/docs-drift && cd docs-drift
python scripts/fetch_targets.py fastify                   # clones fastify at the pinned commit into ../targets/fastify
python -m docsdrift scan ../targets/fastify --offline     # 149 pairs read, 6 flagged, 5 listed
python -m pytest -q                                       # 178 tests, no network
```

Open `docs/index.html` in a browser for the page with all sixteen defects.

`python scripts/fetch_targets.py` without a name fetches all 15 projects. With them in place the test suite also
replays every project and checks that the result matches the stored report.

## Run it on your own repository

```bash
export CLOCKED_API_KEY=...            # or put CLOCKED_API_KEY=... in ../.env, outside the repository
python -m docsdrift scan /path/to/a/repo
```

It prints the list and writes a JSON report to `reports/<name>.json`. On the projects measured, one scan cost 166 to
1,045 credits, 576 on average.

```
--max-pairs N         near-duplicate passage pairs to read (default 120)
--max-key-pairs N     pairs that share an option name (default 30)
--both-orders         compare every pair in both orders; finds more, costs twice as much
--no-gate / --no-swap / --no-elsewhere    switch a stage off
--all                 also print items that did not make the list
--offline             replay recorded answers only: no network, no key, no credits
--budget N            stop when the local ledger reaches N credits
--out FILE            where to write the JSON report
```

`pip install -e .` adds a `docsdrift` command that does the same as `python -m docsdrift`.

## Live trial service

`live/` is a small HTTP service for the demo page. Given two pasted passages it runs `/compare` in both orders and
`/grounding`, and answers whether the pair would be listed, with the conflict kind, the confidence, each endpoint's
own conclusion and the credits used. Given a public GitHub repository it reads the documentation Markdown from the
archive (nothing is unpacked or executed), sends up to 24 candidate pairs through the same pipeline, and reports
progress while it works.

It has hard limits: a total credit budget, a cap per request, a rate limit per address, one job at a time, input
size limits, and a plain "budget is used up" answer when the credits run out. The limits and what it keeps of a
visitor's input are listed in [`live/README.md`](live/README.md). Offline tests cover all of them.

**It is running.** The block at the top of the [demo page](https://vigohan95.github.io/docs-drift/) calls it, and it
shows the credits left. A live scan reads only 24 candidate pairs, so it can list nothing in a project where the full
tool finds something: a scan of redux-toolkit read 24 of 243 candidates and listed nothing, though two of the sixteen
defects are in that project. The page says so. If the service cannot be reached, or the trial budget is used up, the
three examples fall back to the answers recorded in `docs/live-examples.json`, and the page says that too.

## How it works

1. **Candidates, locally and free.** The docs are split at headings. Sentences from different sections that are worded
   almost alike but not identically become candidate pairs. So do passages that mention the same option name. Pairs of
   per-version guides (`migrating_to_6.md` against `migrating_to_7.md`) are skipped.
2. **`/compare`, one request per pair.** It decides which pairs conflict and where.
3. **`/grounding` and a swapped `/compare`** decide which conflicts make the list.
4. **`/rerank` and `/grounding`** find where else the fact is stated and which side is probably stale.

### What each Clocked endpoint's output changes

| Endpoint | What comes back | What the program does with it | Measured effect |
|---|---|---|---|
| **Compare** `/compare` | For a pair of passages: conflict findings, each with a span in both passages and a kind | The spans become the two quoted passages and their line numbers. The kind routes the finding: value, version and rule conflicts go on to the checks; scope and name differences are dropped. A pair with no finding is never shown. | Without it there is only the candidate list, 99% noise. With it alone, 13 of 52 flagged items are real. The kind filter, with the skip for per-version guides, took the tuning findings from 21% to 55% real. |
| **Verify** `/grounding` | For one side's sentence against the other passage: supported, contradicted or not stated | A finding is listed only if `/grounding` says "contradicted" for one side, or the swapped `/compare` repeats the conflict. Both agreeing is shown as "both checks agree". Neither: the finding stays off the list. | On the tuning findings: 55% to 85% real (11 of 13). On the four later projects: no help, all 8 listed items had passed a check. |
| **Rerank** `/rerank` | Which of 12 shortlisted passages actually state the disputed fact (`use`) | Only those passages are sent to `/grounding` to see which side they support. The side with fewer supporters is printed as "probably the stale one", and the other places are printed so they can be fixed together. | 14 of 31 picked passages stated the fact, against 11 of 48 for a word-overlap pick. The side named was the same either way (4 of 7, all correct). It helps the reader more than the result. |

### How they work together

`/compare` is asked first because it is the only one that can find a conflict and point at the two spans. Its answer
is not trusted alone, for two measured reasons: it changes with the order of the two passages, and it reads sibling
pages as conflicts. So the same pair is sent again swapped, and the sentence `/compare` pointed at is handed to
`/grounding` as a claim against the other passage. Only then is `/rerank` used, on the findings that survived, to pull
in the rest of the docs: it filters a cheap local shortlist down to the passages that state the fact, and `/grounding`
turns those into a vote. Each stage consumes the previous stage's output; switch one off with `--no-gate`,
`--no-swap` or `--no-elsewhere` and the list changes.

### Uncertain results, missing information, failed requests

- **Uncertain results are kept off the list, not guessed.** An item where neither check agrees is not listed (`--all`
  shows it). The list says for every item whether both checks agreed or only one.
- **Missing information stays missing.** When `/compare` returns a span too wide to be one sentence, that side is not
  sent to `/grounding` and no stale side is named. When no other passage states the fact, none is invented.
- **Failed requests.** A network failure or a 429/5xx is retried with the same `Idempotency-Key` and identical body,
  with bounded backoff. A 422 (for example a table too long for the engine) is recorded, counted in the report as an
  error, and the pair is skipped. A hard credit budget stops the scan before a request is sent.
- **Replay never invents an answer.** With `--offline`, a request that was never recorded fails the run with a clear
  message instead of returning something.

## What we learned about the API

- An identical request gives an identical answer (18 of 18 re-sent). That makes recordings a valid replay.
- `/compare` depends on the order of the two documents. For 7 of 15 checked pairs it reports a conflict in one order
  and none in the other.
- It also depends on which other documents share the request. One pair scored 0.85 "conflicting" in a three-document
  request and 0.01 in a four-document one. Hence one pair per request.
- Custom instructions move the result in both directions. They removed some false conflicts and some real ones.
- About 2% of returned spans are a few characters off: `text[start:end]` is not the quote. The quote itself is always
  verbatim, so the tool looks it up.
- A single block that cannot be split, such as a large table, is refused with a 422 above roughly 2,048 tokens. It is
  not charged.
- One pair of passages costs about 5 credits on `/compare`. `/rerank` and `/grounding` calls cost about 3 and 4.
- Comparing in both orders doubled the cost on fastify and gave five more findings: four second sightings of defects
  already listed, and one defect the standard run had missed, which still came out below the listing bar.
- Telling `/grounding` which file and section each passage comes from did not stop it from reading sibling pages as
  contradictions (30% to 36% real).

The scripts behind these numbers are in `experiments/`.

## Limits

- It only sees contradictions between passages that restate each other. A page that is simply wrong, with nothing to
  compare it to, is invisible.
- How much it misses is not measured. A spot check of about 50 unlisted pairs found no clear miss.
- Sibling pages still confuse it, as the numbers above show.
- The listing rule was tuned on a small set (57 findings). The 0 of 8 on later projects is the fairer guide.
- Two real contradictions were flagged by `/compare` as scope differences and so were not listed.
- The verdicts in `review/` were reached by reading both passages and the source code. They are not a ruling;
  maintainers decide.

## Layout

```
docsdrift/           the tool: sections, candidates, scan pipeline, replay client, CLI
recordings/          every API request and response (no Authorization header), plus ledger.jsonl
reports/             one JSON report per project; extended/ and both-orders/ hold the extra runs; v2.0/ an earlier rule
review/              verdict for every finding, the defect registry, upstream PR status, the scoring script
experiments/         ablations and rule search
upstream-patches/    one small patch per defect, with a draft of the pull request text
docs/                the static demo page (GitHub Pages serves this folder)
live/                the live trial service behind the page, and the files that deploy it
scripts/             fetch the pinned targets, build the page, render it for a visual check
video/               storyboard and scripts for the demo video
tests/               178 tests
day1/                the first day's probes and scripts, kept for the record
```

Quoted documentation in `recordings/`, `reports/` and `docs/` belongs to its projects and is included under their
licenses. The code in this repository is MIT licensed.
