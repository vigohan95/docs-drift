# Live trial service

A small HTTP service that lets a visitor of the demo page run the real pipeline on their own input:

- `POST /api/pair` with two passages of documentation: `/compare` in both orders, then `/grounding`. The answer says
  whether the pair would be listed, the conflict kind and confidence, each endpoint's own conclusion, and the credits used.
- `POST /api/scan` with a public GitHub repository (`owner/name`): reads its documentation Markdown, picks candidate
  pairs locally, sends up to 24 pairs through the pipeline, and returns the list with evidence. `GET /api/scan/<job>`
  reports progress and then the result.
- `GET /api/status`: the remaining trial budget and the limits.

Standard library only. The logic and the limits are in `service.py`, the GitHub reader in `github.py`, the HTTP front
in `server.py`. All of it is tested offline (`tests/test_live_service.py`).

**Status: running** at `https://108-61-82-7.sslip.io` (`/api/status` shows the budget), called by the demo page.
`review/live.json` holds the address; with an empty address the page shows only the recorded answers of its examples.

This is the third instance. The first one (`45-76-12-121.sslip.io`, started 2026-11-07) was removed from the hosting
account on 2026-11-09 at 17:19 UTC. The second (built 2026-11-10 at 16:36 UTC with the same files) was removed on
2026-11-11 at 00:28 UTC by a cleanup job of another project in the same hosting account, which deleted servers it did
not own; that job has been fixed. This one was built with the same files on 2026-11-11 at 01:05 UTC, and the page
showed recorded answers only in each gap. Both ledgers went with their disks. The Clocked account balance shows what
they spent: 444 credits together (427 known for the first at its last reading, 17 for the second). This instance runs
with `LIVE_BUDGET=1500`, which stays inside the 4,650 credits the account had left when it was started.

## Limits

| What | Limit |
|---|---|
| Total credits the service may spend | 3,500 (`LIVE_BUDGET`) by default, 1,500 on the running instance; read from its own ledger before every request |
| One pair check | at most 60 credits |
| One repository scan | at most 300 credits, 24 pairs, 150 seconds |
| Per address | 10 pair checks and 2 scans per hour |
| All addresses | 15 scans per hour |
| In flight | one job at a time, two Clocked requests |
| A passage | 20 to 2,400 characters |
| A request body | 16 KB |
| A repository | 400 Markdown files, 3 MB of Markdown, 40 MB archive |

When the budget is used up, every request is answered with HTTP 402 and the sentence "The live trial budget is used
up…"; `/api/status` says the same and the page shows it. Nothing fails silently.

The budget is read from a ledger on disk, so it survives a restart. The rate limits are kept in memory and start
again after a restart; the budget and the per-request caps still hold.

A cap is checked before each Clocked request, so with two requests in flight a job can pass its cap by the price of
those requests (a few credits).

## What it does with a visitor's input

- Pasted text is sent to Clocked and kept in memory for caching. It is not written to disk.
- The access log has the time, the IP address, sizes, the outcome and the credits. Nothing else.
- For a repository, only GitHub is contacted (`api.github.com` for the commit, `codeload.github.com` for the archive),
  with a validated `owner/name`. The archive is read as a stream; only documentation Markdown is kept, as text.
  Nothing from the repository is unpacked to disk or executed.
- The Clocked key is read from the environment and is never logged or returned.

## Run it locally

```bash
export CLOCKED_API_KEY=...
LIVE_ALLOWED_ORIGINS=http://127.0.0.1:8000 python -m live.server      # listens on 127.0.0.1:8787
curl -s http://127.0.0.1:8787/api/status
```

`python scripts/e2e_live_page.py <out dir>` drives the page against a local service in headless Chrome, using
recorded Clocked answers (no key, no credits).

## Deploy

`deploy/` has what the running instance was built with:

- `provision_vultr.py`: one instance, its own firewall group (80 and 443 open, 22 from one address) and SSH key, all
  named `docsdrift-live`. Without `--create` it only reads. It creates and never modifies or deletes, and it stops if
  the account's credit does not cover a month.
- `setup.sh <ip-with-dashes>.sslip.io`: swap, Caddy (which gets the certificate), the service under systemd as an
  unprivileged user.
- Then add `CLOCKED_API_KEY=...` to `/etc/docsdrift-live.env` (mode 600), set `LIVE_BUDGET` there if it should differ
  from the default, restart, put the address in `review/live.json`
  and run `python scripts/build_site.py`.

The instance is the cheapest plan with an IPv4 address (`vc2-1c-0.5gb`, 1 CPU, 512 MB). That plan cannot take Ubuntu
24.04, so it runs Debian 12. Vultr's image keeps `ufw` on with only SSH open, which `setup.sh` handles.

`python scripts/e2e_live_page.py <out dir> --deployed` clicks through the published page at 1280 and 390 pixels. It
spends real credits.

Running it for real found two bugs the offline tests had missed, both now covered by tests: with two workers a scan's
credits were counted up to twice in the per-request figure (the ledger and the budget were right), and candidate
selection depended on the Python hash seed for tokens of equal weight (the published results were not affected: all
15 projects replay with the same numbers).
