# Live trial service

A small HTTP service that lets a visitor of the demo page run the real pipeline on their own input:

- `POST /api/pair` with two passages of documentation: `/compare` in both orders, then `/grounding`. The answer says
  whether the pair would be listed, the conflict kind and confidence, each endpoint's own conclusion, and the credits used.
- `POST /api/scan` with a public GitHub repository (`owner/name`): reads its documentation Markdown, picks candidate
  pairs locally, sends up to 24 pairs through the pipeline, and returns the list with evidence. `GET /api/scan/<job>`
  reports progress and then the result.
- `GET /api/status`: the remaining trial budget and the limits.

Standard library only. The logic and the limits are in `service.py`, the GitHub reader in `github.py`, the HTTP front
in `server.py`. All of it is tested offline (`tests/test_live_service.py`, 62 tests).

**Status: built and tested, not deployed.** The Vultr API refused this machine's address when deployment was
attempted (its access list did not include it), so no server was created. Until a service address is set in
`review/live.json`, the demo page shows the recorded answers for its three examples and says so.

## Limits

| What | Limit |
|---|---|
| Total credits the service may spend | 3,500 (`LIVE_BUDGET`), read from its own ledger before every request |
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

## Deploy (draft, not run yet)

`deploy/` has what a deployment needs: `provision_vultr.py` (one small instance, its own firewall group and SSH key,
all named `docsdrift-live`; it only creates, never modifies or deletes), `setup.sh` (Caddy with a
`<ip-with-dashes>.sslip.io` name, the service under systemd as an unprivileged user), the unit file and the
Caddyfile. The key goes in `/etc/docsdrift-live.env` with mode 600. After deployment, put the service address in
`review/live.json` and run `python scripts/build_site.py`. These files have not been run; expect to fix details.
