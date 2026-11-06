# For judges

Docs Drift gives maintainers a short list of places where their documentation contradicts itself. It is entered for
**Best Use of Verify, Compare, or Rerank**.

## Three minutes

1. Open the demo page (`docs/index.html`, or the GitHub Pages link). The first screen says what the tool is and how
   often it is wrong; the three pairs under it are real contradictions in fastify, typeorm and redux-toolkit, each
   linking to the exact lines at a pinned commit.
2. Run it. No key is needed: the scan replays recorded Clocked answers and gives the same result as the live run.

   ```bash
   python scripts/fetch_targets.py fastify
   python -m docsdrift scan ../targets/fastify --offline
   ```

   149 pairs read, 6 flagged by `/compare`, 5 listed. Add `--no-gate`, `--no-swap` or `--no-elsewhere` to see what
   each stage changes, and `--all` to see what was kept off the list.
3. Run the tests: `python -m pytest -q` (176 tests, no network).

With a key (`CLOCKED_API_KEY`), `python -m docsdrift scan /path/to/any/repo` runs it live. A scan cost 166 to 1,045
credits on the projects measured.

The block at the top of the demo page shows three real pairs with what `/compare` (both orders) and `/grounding`
answered for each. Those are recordings. The service that would check pasted passages and scan a repository on
request is in `live/`, with its limits and 62 offline tests; it is not deployed, because the cloud provider's API
refused the build machine's address. To try your own input, run the command line tool or `python -m live.server`
with a key.

## What each endpoint's output changes

| Endpoint | Its output | What the tool does with it | Where to see it |
|---|---|---|---|
| Compare | conflict spans and a conflict kind for a pair of passages | spans become the two quoted lines; the kind decides whether the finding goes on (value, version, rule) or is dropped (scope, name) | `docsdrift/scan.py`: `analyze`, `tier_of` |
| Verify (grounding) | supported / contradicted / not stated for one side's sentence against the other passage | together with a swapped Compare it decides whether the finding is listed, and how it is labelled ("both checks agree", "one check agrees") | `run_gate` |
| Rerank | which shortlisted passages state the disputed fact | only those are checked by Verify to name the side that is probably stale and to list the other places to fix | `run_elsewhere` |

How they depend on each other, and the measured effect of removing each, is in the README under
"What each Clocked endpoint's output changes" and in `experiments/`.

## Against the criteria

Group award (Verify, Compare, or Rerank):

- **Depth (40).** The three endpoints are the pipeline: Compare finds and locates, Verify and a swapped Compare gate,
  Rerank and Verify find the other places. Each was ablated and the numbers are published, including where an
  endpoint did not help.
- **Breadth (30).** All three are used, and each one's output changes what is listed or printed.
- **Usefulness and execution (20).** 16 documentation defects in 6 real projects, each with file, line and source
  code. Three pull requests are open upstream (see the table in the README); none is merged yet. Precision is
  modest and stated plainly: 11 of 21 listed items were real, and 0 of 8 on projects scanned after the listing rule
  was fixed.
- **Explanation and reproducibility (10).** Every request and response is recorded; scans replay offline; the numbers
  in the README are recomputed by the tests.

Best Overall App: the tool uses three of the nine endpoints and is a command-line tool with a static report page
(the live trial service is written and tested but not hosted), so it is not built to score on "additional
endpoints" or on interface polish.

## What it does not do

- It does not judge whether docs are correct, only whether two passages disagree.
- It does not decide who is right. The verdicts in `review/` were reached by reading both passages and the source
  code; the upstream maintainers have the final word.
- It is wrong about half the time on what it lists, and it found nothing real in 9 of 15 projects.
