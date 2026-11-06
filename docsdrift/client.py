"""Minimal Clocked API client (stdlib only) with a replay cache.

- Reads CLOCKED_API_KEY from the environment, or from a .env file located
  OUTSIDE this repository (default: ../.env relative to the repo root).
- Every request/response pair is recorded under recordings/ WITHOUT the
  Authorization header. recordings/ledger.jsonl has one line per live call
  with the credits reported by the X-Clocked-Credits response header.
- Replay cache: a request whose (endpoint, payload) was recorded before is
  answered from the recording, costs nothing and needs no key. The API is
  deterministic for identical requests (checked on day 1 and day 2), so a
  replay is the same answer a live call would give.
- offline=True never touches the network: a cache miss raises CacheMiss.
- Enforces a hard credit budget across runs (sum of the ledger).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE_URL = "https://clocked.rezolve.ai/clocked"
REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = REPO_ROOT / "recordings"
LEDGER = RECORDINGS / "ledger.jsonl"
INDEX = RECORDINGS / "index.json"

# Account has 20,000 credits; 4,000 are reserved for the final demo recording
# and for judges trying the tool. Never spend past this.
DEFAULT_BUDGET = 15400.0

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

_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


class CacheMiss(RuntimeError):
    pass


class ClockedError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def request_hash(endpoint: str, payload: dict) -> str:
    blob = endpoint + "\n" + json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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


def build_index(recordings: Path = RECORDINGS) -> dict:
    """Map request hash -> recording path (relative) for every successful recording."""
    index = {}
    for f in sorted(recordings.rglob("*.json")):
        if f.name == "index.json":
            continue
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # 200 answers are replayable. So is a 422: the engine refuses the same request every
        # time (for example a table too long to read in one pass) and never charges for it.
        if not isinstance(rec, dict) or rec.get("status") not in (200, 422) or "request" not in rec:
            continue
        index[request_hash(rec["endpoint"], rec["request"])] = f.relative_to(recordings).as_posix()
    return index


def load_index(recordings: Path = RECORDINGS, rebuild: bool = False) -> dict:
    idx_file = recordings / "index.json"
    if idx_file.exists() and not rebuild:
        return json.loads(idx_file.read_text(encoding="utf-8"))
    index = build_index(recordings)
    idx_file.write_text(json.dumps(index, indent=0, sort_keys=True), encoding="utf-8")
    return index


class Clocked:
    def __init__(self, budget: float = DEFAULT_BUDGET, timeout: float = 130.0,
                 offline: bool = False, use_cache: bool = True, recordings: Path = RECORDINGS,
                 reserve: float = 0.0):  # `reserve` is accepted for the day-1 scripts and ignored
        self.offline = offline
        self.use_cache = use_cache
        self.budget = budget
        self.timeout = timeout
        self.recordings = recordings
        self._key = None
        self._spent = None
        self.live_calls = 0
        self.cache_hits = 0
        self.live_credits = 0.0
        recordings.mkdir(exist_ok=True)
        self._index = load_index(recordings) if (use_cache or offline) else {}

    # ------------------------------------------------------------------ cache
    def cached(self, endpoint: str, payload: dict):
        h = request_hash(endpoint, payload)
        rel = self._index.get(h)
        if rel and (self.recordings / rel).exists():
            return json.loads((self.recordings / rel).read_text(encoding="utf-8"))
        return None

    def cached_credits(self, endpoint: str, payload: dict) -> float:
        rec = self.cached(endpoint, payload)
        if not rec:
            return 0.0
        return float(rec.get("response_headers", {}).get("x-clocked-credits") or 0)

    # ------------------------------------------------------------------- call
    def call(self, endpoint: str, payload: dict, tag: str | None = None, max_retries: int = 4,
             force_live: bool = False) -> dict:
        """Like call_cost() but returns only the parsed JSON body."""
        return self.call_cost(endpoint, payload, tag, max_retries, force_live)[0]

    def call_cost(self, endpoint: str, payload: dict, tag: str | None = None, max_retries: int = 4,
                  force_live: bool = False) -> tuple[dict, float]:
        """POST payload to /clocked/<endpoint>; return (parsed JSON body, credits).

        `credits` is what the request cost when it was made live (the
        X-Clocked-Credits header), also when the answer comes from the cache.

        Answers from the replay cache when the same request was recorded
        before (unless force_live). New recordings are content-addressed:
        recordings/v2/<endpoint>/<hash prefix>.json, or recordings/<tag>.json
        when a tag is given.
        """
        h = request_hash(endpoint, payload)
        if (self.use_cache or self.offline) and not force_live:
            rec = self.cached(endpoint, payload)
            if rec is not None:
                with _lock:
                    self.cache_hits += 1
                if rec.get("status") != 200:
                    raise ClockedError(rec["status"], json.dumps(rec.get("response")))
                return rec["response"], float(rec.get("response_headers", {}).get("x-clocked-credits") or 0)
        if self.offline:
            raise CacheMiss(f"no recording for {endpoint} request {h[:16]}")

        with _lock:
            if self._key is None:
                self._key = _load_key()
            if self._spent is None:
                self._spent = credits_used()
            if self._spent >= self.budget:
                raise BudgetExceeded(f"spent {self._spent:.0f} of {self.budget:.0f} credits")

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
            req.add_header("User-Agent", "docs-drift/0.2")
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
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
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
            credits = 0.0  # a server-side replay is not charged again
        rel = f"{tag}.json" if tag else f"v2/{endpoint}/{h[:2]}/{h[:20]}.json"
        record = {
            "endpoint": endpoint,
            "tag": tag or rel[:-5],
            "request_hash": h,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "attempts": attempt,
            "round_trip_ms": elapsed_ms,
            "response_headers": kept,
            "request": payload,
            "response": parsed,
        }
        out = self.recordings / rel
        with _lock:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            with (self.recordings / "ledger.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "tag": record["tag"], "endpoint": endpoint, "status": status,
                    "credits": credits,
                    "model_ms": kept.get("x-clocked-model-ms"),
                    "round_trip_ms": elapsed_ms,
                    "request_chars": len(body),
                    "at": record["recorded_at"],
                }) + "\n")
            self._spent += credits
            self.live_calls += 1
            self.live_credits += credits
            if status in (200, 422) and not force_live:
                self._index[h] = rel
        if status != 200:
            raise ClockedError(status, raw)
        return parsed, credits

    def save_index(self):
        with _lock:
            idx_file = self.recordings / "index.json"
            merged = {}
            if idx_file.exists():  # another process may have added entries meanwhile
                try:
                    merged = json.loads(idx_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    merged = {}
            merged.update(self._index)
            self._index = merged
            idx_file.write_text(json.dumps(merged, indent=0, sort_keys=True), encoding="utf-8")
