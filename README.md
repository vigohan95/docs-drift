# Docs Drift

Docs Drift finds places where a project's documentation contradicts itself.

It pairs passages that restate each other, asks the [Clocked API](https://clocked.rezolve.ai/docs) whether each pair
conflicts, and reports the conflicts with file and line on both sides.

Built for the Clocked Build Challenge (October 21 to November 10, 2026) on three endpoints: `/compare`, `/grounding`
and `/rerank`.

## What it found

It was run on the documentation of 15 open-source projects at pinned commits. It surfaced **16 contradictions in 6
projects**. Every one was checked against both passages and the project's source code, with file and line recorded in
[`review/defects.json`](review/defects.json). The final word on each belongs to the upstream maintainers.

Three of them:

| Project | One place says | Another place says | The code |
|---|---|---|---|
| fastify | `Hooks.md:73` in `onRequest`, `request.body` is always `undefined` | `TypeScript.md:1540` it is always `null` | `lib/request.js:40` sets `this.body = undefined` |
| redux-toolkit | `getting-started.md:157` createAsyncThunk dispatches `pending/fulfilled/rejected` | `packages/toolkit/README.md:78` `pending/resolved/rejected` | `createAsyncThunk.ts:544` builds `'/fulfilled'` |
| prometheus | `chunks.md:302` `st_changed_on` is set to 127 (0x7F) | `chunks.md:150` 127 (0xEF) | `tsdb/chunkenc/st.go:19` `maxFirstSTChangeOn = 0x7F` |

The other thirteen are in fastify (5 more), mikro-orm (4), typeorm (2), redux-toolkit (1 more) and rollup (1). The demo
page [`site/index.html`](site/index.html) shows all sixteen side by side, with links to the pinned commits.

Nine projects produced nothing real: vite, jest, mongoose, eslint, vitest, got, fiber, pydantic and svelte.

## How often it is right

These are the numbers for the standard run (up to 150 passage pairs per project, 1,878 pairs in total).

| | Findings | Real contradictions | |
|---|---|---|---|
| Everything `/compare` flagged | 52 | 13 | 25% |
| Reported after the checks below | 21 | 11 | 52% |
| ... on the 11 projects the reporting rule was tuned on | 13 | 11 | 85% |
| ... on the 4 projects scanned after the rule was fixed | 8 | 0 | 0% |

The last two rows matter most. The rule that decides what to report was chosen on findings from eleven projects. It was
then run unchanged on four more (rollup, fiber, pydantic, svelte). There it reported eight findings and none was real.
The one real contradiction in those four (rollup) was flagged by `/compare` but dropped by the rule.

So: expect about half of what it reports to be real, expect that to vary a lot between projects, and expect many
projects to produce nothing. It is a triage list for a person to read, not a verdict.

Of the 16 contradictions, 10 were reported by the standard run. 3 came from scanning more pairs in mikro-orm,
redux-toolkit and typeorm. 3 surfaced in other runs without being reported by the standard one. Each entry in
`review/defects.json` says which.

All ten false reports are listed with the reason in `review/labels_v2.json` and on the demo page. Most are sibling
documents: two pages written from one template about different things (two middlewares, two functions, two releases).

## Run it

Python 3.10 or newer. No dependencies.

```bash
export CLOCKED_API_KEY=...            # or put CLOCKED_API_KEY=... in ../.env, outside the repository
python -m docsdrift scan /path/to/a/repo
```

It prints the reported findings and writes a JSON report to `reports/<name>.json`. A scan of one project costs 166 to
1,045 credits on the projects measured, 576 on average.

Useful options:

```
--max-pairs N         near-duplicate passage pairs to compare (default 120)
--max-key-pairs N     pairs that share an option name (default 30)
--both-orders         compare every pair in both orders; finds more, costs twice as much
--no-gate / --no-swap / --no-elsewhere    switch a stage off
--all                 also print findings that are not reported by default
--offline             replay recorded answers only: no network, no key, no credits
--budget N            stop when the local ledger reaches N credits
```

`pip install -e .` adds a `docsdrift` command that does the same as `python -m docsdrift`.

### Replay the measured runs without a key

Every API answer behind the numbers above is in `recordings/`. With a target cloned at its pinned commit, the scan
replays offline and gives the same report.

```bash
python scripts/fetch_targets.py fastify      # git clone at the pinned commit into ../targets/fastify
python -m docsdrift target fastify --offline
```

### Tests

```bash
python -m pytest -q        # 95 tests, no network, no key
```

The tests replay recordings. They check the reports against the recorded verdicts, the numbers in this README against
a fresh recount, and, when the clones are present, that an offline scan of each of the 15 projects reproduces its
stored report.

## How it works

1. **Candidates, locally.** The docs are split at headings. Sentences from different sections that are worded almost
   alike but not identically become candidate pairs. So do passages that mention the same option name. Pairs of
   per-version guides (`migrating_to_6.md` against `migrating_to_7.md`) are skipped. This costs nothing.
2. **`/compare`, one request per pair.** It returns the conflicting spans and a kind. Only value, version and rule
   conflicts go on; scope and name differences are dropped.
3. **Two checks.** `/grounding` checks each side's sentence against the other passage. `/compare` is asked again with
   the two passages swapped. A finding is *confirmed* when both checks agree, *likely* when one does, and not reported
   when neither does.
4. **`/rerank`, where else is this said.** For a reported finding, `/rerank` picks other passages that state the same
   fact and `/grounding` checks which side they agree with. The side with fewer supporters is named as the outlier.

## What each endpoint contributed

Measured, not assumed. The scripts are in `experiments/`.

**`/compare` is the core.** Without it there is only the candidate list, which is 99% noise. With it alone, 25% of
findings are real. Restricting to value, version and rule kinds and skipping per-version guides gave 55% on the tuning
findings (11 of 20).

**`/grounding` helped on the tuning set and not on the later projects.** As the only check it gave 30% (11 of 37).
Together with the kind filter it gave 91% (10 of 11), and with "either check agrees" 85% (11 of 13). On the four later
projects all eight reported findings had passed a check and were wrong. Telling `/grounding` which file and section each
passage comes from did not fix that (36%, 10 of 28).

**`/rerank` is a convenience.** It picked better evidence: 14 of 31 picked passages stated the disputed fact, against
11 of 48 for the top three of a word-overlap list. The outlier it led to was the same either way: named for 4 of the 7
real findings where the code settles which side is wrong, and correct all 4 times, with or without `/rerank`.

**Comparing in both orders** doubled the cost on fastify and gave five more findings: four second sightings of
defects already reported, and one defect the standard run had missed, which still came out below the reporting bar.

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

## Limits

- It only sees contradictions between passages that restate each other. A page that is simply wrong, with nothing to
  compare it to, is invisible.
- Recall is not measured. A spot check of about 50 unreported pairs found no clear miss.
- Sibling pages still confuse it, as the numbers above show.
- The reporting rule was tuned on a small set (57 findings). The 0 of 8 on later projects is the fairer guide.
- Two real contradictions were flagged by `/compare` as scope differences and so were not reported.
- The verdicts were reached by reading both passages and the source code. They are not a ruling; maintainers decide.

## Upstream

`upstream-patches/` holds 16 minimal patches, one per contradiction, each with a draft of the pull request text, plus
notes for one issue. None has been sent. Each upstream repository's issues and pull requests were searched on
2026-11-07 and nothing about these defects was found. The contribution rules of each project are noted at the top of
each draft; fastify, for example, requires that a person opens the pull request.

## Layout

```
docsdrift/           the tool: sections, candidates, scan pipeline, replay client, CLI
recordings/          every API request and response (no Authorization header), plus ledger.jsonl
reports/             one JSON report per project; extended/ and both-orders/ hold the extra runs; v2.0/ an earlier rule
review/              verdict for every finding, the defect registry, the scoring script
experiments/         ablations and rule search
upstream-patches/    patches and PR text drafts
site/                the static demo page
tests/               95 tests
day1/                the first day's probes and scripts, kept for the record
```

Quoted documentation in `recordings/`, `reports/` and `site/` belongs to its projects and is included under their
licenses. The code in this repository is MIT licensed.
