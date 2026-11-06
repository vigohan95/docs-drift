"""Minimal Clocked API client (stdlib only).

- Reads CLOCKED_API_KEY from the environment, or from a .env file located
  OUTSIDE this repository (default: ../.env relative to the repo root).
- Sends a fresh Idempotency-Key per logical request; retries of the same
  request reuse the key.
- Records every request/response pair under recordings/ WITHOUT the
  Authorization header, and appends a line to recordings/ledger.jsonl with
  the credits reported by the X-Clocked-Credits response header.
- Enforces a hard credit budget across runs (sum of the ledger).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE_URL = "https://clocked.rezolve.ai/clocked"
REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = REPO_ROOT / "recordings"
LEDGER = RECORDINGS / "ledger.jsonl"

# Response headers worth keeping. Never record request headers.
KEEP_HEADERS = (
    "x-clocked-credits",
    "x-clocked-model-ms",
    "x-clocked-cost-usd",
    "x-clocked-cost-basis",
    "x-clocked-transport",
    "server-timing",
    "retry-after",
)


class BudgetExceeded(RuntimeError):
    pass


class ClockedError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def _load_key() -> str:
    key = os.environ.get("CLOCKED_API_KEY")
    if key:
        return key.strip()
    env_path = Path(os.environ.get("CLOCKED_ENV_FILE", REPO_ROOT.parent / ".env"))
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("CLOCKED_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("CLOCKED_API_KEY not found in environment or ../.env")


def credits_used() -> float:
    """Total credits spent so far according to the local ledger."""
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            total += float(json.loads(line).get("credits") or 0)
    return total


class Clocked:
    def __init__(self, budget: float = 5000.0, reserve: float = 0.0, timeout: float = 130.0):
        self._key = _load_key()
        self.budget = budget
        self.reserve = reserve
        self.timeout = timeout
        RECORDINGS.mkdir(exist_ok=True)

    def call(self, endpoint: str, payload: dict, tag: str, max_retries: int = 4) -> dict:
        """POST payload to /clocked/<endpoint>; return the parsed JSON body.

        `tag` names the recording file: recordings/<tag>.json
        """
        spent = credits_used()
        if spent + self.reserve >= self.budget:
            raise BudgetExceeded(f"spent {spent} of {self.budget} credits")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        idem = str(uuid.uuid4())
        url = f"{BASE_URL}/{endpoint}"
        attempt = 0
        while True:
            attempt += 1
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {self._key}")
            req.add_header("Content-Type", "application/json")
            req.add_header("Idempotency-Key", idem)
            req.add_header("User-Agent", "docs-drift/0.1")
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    status = resp.status
                    headers = {k.lower(): v for k, v in resp.headers.items()}
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", errors="replace")
                status = e.code
                headers = {k.lower(): v for k, v in e.headers.items()}
            except (urllib.error.URLError, TimeoutError) as e:
                # Unknown outcome: retry the SAME key with the identical payload.
                if attempt <= max_retries:
                    time.sleep(min(2 ** attempt, 20))
                    continue
                raise ClockedError(0, f"network error: {e}")
            elapsed_ms = round((time.perf_counter() - t0) * 1000)

            retry_as_new = False
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    retry_as_new = bool(parsed.get("retryAsNew"))
            except json.JSONDecodeError:
                parsed = {"_raw": raw}

            if status in (429, 500, 502, 503, 504) and attempt <= max_retries and not retry_as_new:
                time.sleep(min(2 ** attempt, 20))
                continue
            break

        kept = {k: headers[k] for k in KEEP_HEADERS if k in headers}
        credits = float(kept.get("x-clocked-credits") or 0) if status == 200 else 0.0
        if kept.get("x-clocked-transport") == "replay":
            credits = 0.0  # a replay is not charged again
        record = {
            "endpoint": endpoint,
            "tag": tag,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "attempts": attempt,
            "round_trip_ms": elapsed_ms,
            "response_headers": kept,
            "request": payload,
            "response": parsed,
        }
        out = RECORDINGS / f"{tag}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "tag": tag, "endpoint": endpoint, "status": status,
                "credits": credits,
                "model_ms": kept.get("x-clocked-model-ms"),
                "round_trip_ms": elapsed_ms,
                "request_chars": len(body),
                "at": record["recorded_at"],
            }) + "\n")
        if status != 200:
            raise ClockedError(status, raw)
        return parsed
