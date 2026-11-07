"""The live trial: check one pair of passages, or scan a public GitHub repository's docs.

This module holds the logic and every limit. It knows nothing about HTTP (see server.py), and
everything it depends on is passed in (the Clocked client, the GitHub fetcher, the clock), so
all of it is tested offline against recorded answers.

What protects the API key's credits:
  - a global credit budget, read from this service's own ledger before every request;
  - a credit cap per request, enforced between Clocked calls;
  - a rate limit per IP address, a short queue, and one job at a time (two Clocked requests in flight);
  - length limits on everything a visitor can send.
When the budget is used up the service says so in plain words; it never fails silently.

Text pasted by visitors is not written to disk: the client keeps answers in memory only, and
the access log holds the time, the IP address, sizes and outcomes.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from docsdrift.client import BudgetExceeded, ClockedError, credits_used
from docsdrift.filters import REPORTABLE_KINDS
from docsdrift.scan import (REPORTED_TIERS, WIDE_QUOTE, analyze, build_candidates, compare_payload, run_gate,
                            side_info, tier_of)
from docsdrift.sections import Chunk, split_text

from .github import GitHubError, OWNER_REPO, fetch_markdown

TIER_WORDS = {"confirmed": "both checks agree", "likely": "one check agrees",
              "weak": "neither check agrees", "out_of_scope": "a scope or name difference, not listed",
              "unchecked": "not checked"}
EXHAUSTED = ("The live trial budget is used up. Everything else on this page is a replay of recorded "
             "runs and still works; the same scan can be replayed offline from the repository.")


@dataclass
class Limits:
    budget: float = 3500.0            # credits this service may spend in total
    pair_credit_cap: float = 60.0     # one pair check never spends more than this
    scan_credit_cap: float = 300.0    # one repository scan never spends more than this
    passage_min: int = 20
    passage_max: int = 2400           # one section of documentation
    pair_per_ip_hour: int = 10
    scan_per_ip_hour: int = 2
    scan_per_hour_total: int = 15
    scan_pairs: int = 20              # near-duplicate pairs sent to /compare per scan
    scan_key_pairs: int = 4           # shared-option pairs sent to /compare per scan
    max_files: int = 400
    max_file_bytes: int = 300_000
    max_total_bytes: int = 3_000_000
    max_tarball_bytes: int = 40_000_000
    job_timeout: float = 150.0        # seconds before a scan is stopped and says so
    queue_max: int = 3
    wait_for_slot: float = 25.0       # how long a pair check waits for a running scan
    workers: int = 2                  # Clocked requests in flight


class LiveError(Exception):
    """An answer the visitor should see: an HTTP status, a short code and a sentence."""

    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def body(self) -> dict:
        return {"ok": False, "error": self.code, "message": self.message, **self.extra}


class CappedClient:
    """Stops a request from spending more than its cap, and counts what it really spent."""

    def __init__(self, inner, cap: float, remaining: float):
        self.inner, self.cap, self.remaining = inner, cap, remaining
        self.spent = 0.0          # credits charged now
        self.list_price = 0.0     # what the answers cost when they were first made
        self.replayed = 0
        self.calls = 0
        self._lock = threading.Lock()

    def call_cost(self, endpoint: str, payload: dict, *a, **kw):
        with self._lock:
            if self.spent >= self.cap:
                raise BudgetExceeded("the credit cap for one request was reached")
            if self.spent >= self.remaining:
                raise BudgetExceeded("the live trial budget is used up")
        body, price = self.inner.call_cost(endpoint, payload, *a, **kw)
        charged, from_cache = self.inner.last_call()
        with self._lock:
            self.calls += 1
            self.list_price += price
            self.spent += charged
            self.replayed += from_cache
        return body, price

    def call(self, endpoint: str, payload: dict, *a, **kw):
        return self.call_cost(endpoint, payload, *a, **kw)[0]

    def save_index(self):
        pass

    def cached_credits(self, endpoint, payload):
        return self.inner.cached_credits(endpoint, payload)

    @property
    def cache_hits(self):
        return self.inner.cache_hits

    @property
    def live_calls(self):
        return self.inner.live_calls

    @property
    def live_credits(self):
        return self.inner.live_credits


@dataclass
class Job:
    id: str
    ip: str
    repo: str
    status: str = "queued"            # queued, running, done, failed, timed_out
    stage: str = "waiting for a free slot"
    done: int = 0
    total: int = 0
    created: float = 0.0
    started: float = 0.0
    finished: float = 0.0
    result: dict | None = None
    error: dict | None = None

    def public(self, now: float) -> dict:
        out = {"ok": True, "job": self.id, "repo": self.repo, "status": self.status, "stage": self.stage,
               "progress": {"done": self.done, "total": self.total},
               "seconds": round((self.finished or now) - (self.started or self.created), 1)}
        if self.result is not None:
            out["result"] = self.result
        if self.error is not None:
            out.update(self.error)
            out["ok"] = False
        return out


class LiveService:
    def __init__(self, client, data_dir: Path, limits: Limits | None = None, fetcher=fetch_markdown,
                 now=time.time, run_async: bool = True):
        self.client, self.data, self.limits = client, Path(data_dir), limits or Limits()
        self.fetcher, self.now, self.run_async = fetcher, now, run_async
        self.data.mkdir(parents=True, exist_ok=True)
        self.ledger = self.data / "ledger.jsonl"
        self.access_log = self.data / "access.jsonl"
        self._hits: dict = defaultdict(deque)
        self._slot = threading.Semaphore(1)
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._queued = 0

    # ------------------------------------------------------------- bookkeeping
    def spent(self) -> float:
        return credits_used(self.ledger)

    def remaining(self) -> float:
        return max(0.0, self.limits.budget - self.spent())

    def status(self) -> dict:
        L = self.limits
        remaining = self.remaining()
        return {"ok": True, "budget": {"total": L.budget, "spent": round(L.budget - remaining, 1), "remaining": round(remaining, 1)},
                "exhausted": remaining < L.pair_credit_cap,
                "message": EXHAUSTED if remaining < L.pair_credit_cap else "",
                "busy": self._queued > 0,
                "limits": {"passage_chars": [L.passage_min, L.passage_max], "pair_checks_per_hour": L.pair_per_ip_hour,
                           "scans_per_hour": L.scan_per_ip_hour, "pairs_per_scan": L.scan_pairs + L.scan_key_pairs,
                           "pair_credit_cap": L.pair_credit_cap, "scan_credit_cap": L.scan_credit_cap,
                           "scan_timeout_seconds": L.job_timeout, "markdown_files": L.max_files,
                           "markdown_bytes": L.max_total_bytes}}

    def _log(self, ip: str, endpoint: str, outcome: str, **facts):
        row = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.now())), "ip": ip,
               "endpoint": endpoint, "outcome": outcome, **facts}
        with self._lock, self.access_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def _rate(self, ip: str, kind: str, per_hour: int):
        q = self._hits[(ip, kind)]
        now = self.now()
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= per_hour:
            wait = int(3600 - (now - q[0])) + 1
            raise LiveError(429, "rate_limited", f"Too many requests from this address. Try again in about "
                            f"{max(1, wait // 60)} minutes. The rest of the page is a replay and needs no requests.",
                            retry_after=wait)
        q.append(now)

    def _need(self, credits: float):
        if self.remaining() < credits:
            raise LiveError(402, "trial_budget_exhausted", EXHAUSTED, budget=self.status()["budget"])

    # --------------------------------------------------------------- one pair
    def check_pair(self, ip: str, a, b) -> dict:
        L = self.limits
        for name, text in (("first", a), ("second", b)):
            if not isinstance(text, str):
                raise LiveError(400, "bad_input", f"The {name} passage must be text.")
            n = len(text.strip())
            if n < L.passage_min:
                raise LiveError(400, "bad_input", f"The {name} passage is too short: at least {L.passage_min} characters.")
            if len(text) > L.passage_max:
                raise LiveError(400, "bad_input", f"The {name} passage is too long: at most {L.passage_max} characters "
                                                  f"(it has {len(text)}).")
        a, b = a.strip("\n"), b.strip("\n")
        if a.strip() == b.strip():
            raise LiveError(400, "bad_input", "The two passages are identical, so there is nothing to compare.")
        self._rate(ip, "pair", L.pair_per_ip_hour)
        self._need(L.pair_credit_cap)
        if not self._slot.acquire(timeout=L.wait_for_slot):
            raise LiveError(429, "busy", "A repository scan is running. Try again in a minute.", retry_after=60)
        t0 = self.now()
        capped = CappedClient(self.client, L.pair_credit_cap, self.remaining())
        try:
            result = self._pair(capped, a, b)
        except BudgetExceeded as e:
            self._log(ip, "pair", "stopped_by_cap", credits=capped.spent)
            raise LiveError(402, "trial_budget_exhausted", EXHAUSTED + f" ({e})", budget=self.status()["budget"])
        except ClockedError as e:
            self._log(ip, "pair", f"clocked_error_{e.status}", credits=capped.spent)
            raise LiveError(502, "clocked_error", "The Clocked API did not answer this request "
                            f"(HTTP {e.status}). Nothing was listed. Try again, or use the replay below.")
        finally:
            self._slot.release()
        result.update({"ok": True, "seconds": round(self.now() - t0, 1),
                       "credits": {"spent_now": capped.spent, "list_price": capped.list_price,
                                   "answers_replayed": capped.replayed, "calls": capped.calls},
                       "budget": self.status()["budget"]})
        self._log(ip, "pair", "listed" if result["listed"] else "not_listed", chars=[len(a), len(b)],
                  credits=capped.spent, calls=capped.calls)
        return result

    @staticmethod
    def _chunk(side: str, text: str) -> Chunk:
        offs, pos = [], 0
        for line in text.split("\n"):
            offs.append(pos)
            pos += len(line) + 1
        return Chunk("pair", f"passage-{side}", "", 1, len(offs), text, cid=f"pair:{side}#0", line_offsets=offs)

    def _pair(self, client, a: str, b: str) -> dict:
        ca, cb = self._chunk("a", a), self._chunk("b", b)
        by = {ca.cid: ca, cb.cid: cb}
        orders = {}
        for name, first, second in (("a_then_b", ca, cb), ("b_then_a", cb, ca)):
            r = client.call("compare", compare_payload(first, second))
            pr = r["pairs"][0]
            orders[name] = {
                "relation": pr["relation"], "conflicting": pr["probabilities"]["conflicting"],
                "conflicts": [{"kind": f.get("kind"), "confidence": f.get("confidence"),
                               "first": (f.get("a") or {}).get("quote"), "second": (f.get("b") or {}).get("quote")}
                              for f in pr.get("conflicts", [])],
                "_raw": pr, "_first": first, "_second": second,
            }
        # the finding to show: the strongest reportable one, taken from whichever order found it
        best = None
        for name in ("a_then_b", "b_then_a"):
            o = orders[name]
            for f in o["_raw"].get("conflicts", []):
                key = (f.get("kind") in REPORTABLE_KINDS, f.get("confidence") or 0)
                if best is None or key > best[0]:
                    best = (key, name, f)
        out = {"listed": False, "tier": None, "tier_words": "no conflict found", "kind": None, "confidence": None,
               "compare": {n: {k: v for k, v in o.items() if not k.startswith("_")} for n, o in orders.items()},
               "grounding": None, "a": None, "b": None}
        if best is None:
            # /compare sometimes calls a pair conflicting without pointing at a span. For two short
            # pasted statements, hand them to /grounding whole and say that this is what happened.
            conflicting = [n for n, o in orders.items() if o["relation"] == "conflicting"]
            if conflicting and len(a) <= WIDE_QUOTE and len(b) <= WIDE_QUOTE:
                whole = {"a": {"cid": ca.cid, "statement": " ".join(a.split())},
                         "b": {"cid": cb.cid, "statement": " ".join(b.split())}}
                gate = run_gate(client, whole, by)
                agrees = gate["any_contradicted"]
                tier = ("confirmed" if len(conflicting) == 2 else "likely") if agrees else "weak"
                out.update({
                    "listed": agrees, "tier": tier, "tier_words": TIER_WORDS[tier], "kind": "whole_passage",
                    "confidence": max(orders[n]["conflicting"] for n in conflicting),
                    "swap_repeats_it": len(conflicting) == 2,
                    "note": "/compare called the pair conflicting without pointing at a span, so the two passages "
                            "were checked whole.",
                    "grounding": {"first_passage_checked_against_second": gate.get("a"),
                                  "second_passage_checked_against_first": gate.get("b")},
                    "a": {"statement": whole["a"]["statement"], "quote": a, "line": 1},
                    "b": {"statement": whole["b"]["statement"], "quote": b, "line": 1},
                })
            return out
        _, name, f = best
        first, second = orders[name]["_first"], orders[name]["_second"]
        other = orders["b_then_a" if name == "a_then_b" else "a_then_b"]
        finding = {"kind": f.get("kind"), "confidence": f.get("confidence"),
                   "a": side_info("", "", first, f.get("a") or {}), "b": side_info("", "", second, f.get("b") or {}),
                   "swap": {"confirmed": len(other["conflicts"]) > 0}}
        if finding["kind"] in REPORTABLE_KINDS:
            finding["gate"] = run_gate(client, finding, by)
        tier = tier_of(finding)
        # `first`/`second` are the order /compare saw; map back to the visitor's first and second passage
        first_is_a = name == "a_then_b"
        mine = {"a": finding["a" if first_is_a else "b"], "b": finding["b" if first_is_a else "a"]}
        gate = finding.get("gate") or {}
        grounding = None
        if gate:
            grounding = {"first_passage_checked_against_second": gate.get("a" if first_is_a else "b"),
                         "second_passage_checked_against_first": gate.get("b" if first_is_a else "a")}
        out.update({
            "listed": tier in REPORTED_TIERS, "tier": tier, "tier_words": TIER_WORDS.get(tier, tier),
            "kind": finding["kind"], "confidence": finding["confidence"], "found_in_order": name,
            "swap_repeats_it": finding["swap"]["confirmed"], "grounding": grounding,
            "a": {"statement": mine["a"]["statement"], "quote": mine["a"]["quote"], "line": mine["a"]["line_start"]},
            "b": {"statement": mine["b"]["statement"], "quote": mine["b"]["quote"], "line": mine["b"]["line_start"]},
        })
        return out

    # ------------------------------------------------------------ a repository
    def start_scan(self, ip: str, repo) -> dict:
        L = self.limits
        if not isinstance(repo, str) or not OWNER_REPO.match(repo.strip()):
            raise LiveError(400, "bad_input", "Give a public GitHub repository as owner/name, for example fastify/fastify.")
        repo = repo.strip()
        self._rate(ip, "scan", L.scan_per_ip_hour)
        self._rate("*", "scan", L.scan_per_hour_total)
        self._need(L.scan_credit_cap)
        with self._lock:
            self._purge()
            if self._queued >= L.queue_max:
                raise LiveError(429, "busy", "Several scans are already waiting. Try again in a few minutes.", retry_after=120)
            job = Job(id=secrets.token_urlsafe(9), ip=ip, repo=repo, created=self.now())
            self._jobs[job.id] = job
            self._queued += 1
        if self.run_async:
            threading.Thread(target=self._run_scan, args=(job,), daemon=True).start()
        else:
            self._run_scan(job)
        return job.public(self.now())

    def job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if job is None:
            raise LiveError(404, "no_such_job", "No such scan. Results are kept for 30 minutes.")
        return job.public(self.now())

    def _purge(self):
        cutoff = self.now() - 1800
        for jid in [j for j, job in self._jobs.items() if job.finished and job.finished < cutoff]:
            del self._jobs[jid]

    def _run_scan(self, job: Job):
        L = self.limits
        self._slot.acquire()
        job.status, job.started, job.stage = "running", self.now(), "reading the repository from GitHub"
        capped = CappedClient(self.client, L.scan_credit_cap, self.remaining())
        outcome = "done"
        try:
            commit, files = self.fetcher(job.repo, L)
            project = job.repo.split("/", 1)[1]
            chunks = []
            for rel in sorted(files):
                chunks.extend(split_text(project, rel, files[rel]))
            cands, cstats = build_candidates(chunks, L.scan_pairs, L.scan_key_pairs)
            job.total, job.stage = len(cands), "comparing pairs of passages"

            def progress(stage, done, total):
                job.stage = {"compare": "comparing pairs of passages", "verify": "second opinion on what was flagged",
                             "elsewhere": "looking for other places that state the same fact"}.get(stage, stage)
                if stage == "compare":
                    job.done, job.total = done, total

            def should_stop():
                return "timeout" if self.now() - job.started > L.job_timeout else None

            rep = analyze(project, chunks, cands, cstats, repo=job.repo, commit=commit, client=capped,
                          workers=L.workers, log=lambda *a: None, progress=progress, should_stop=should_stop)
            stopped = rep["stats"]["stopped"]
            items = []
            for f in rep["findings"]:
                if f["tier"] not in REPORTED_TIERS:
                    continue
                e = f.get("elsewhere") or {}
                items.append({
                    "tier": f["tier"], "tier_words": TIER_WORDS[f["tier"]], "kind": f["kind"], "confidence": f["confidence"],
                    "a": {k: f["a"][k] for k in ("path", "line_start", "line_end", "statement", "url")},
                    "b": {k: f["b"][k] for k in ("path", "line_start", "line_end", "statement", "url")},
                    "elsewhere": [{"path": p["path"], "line": p["line"], "agrees_with": p["agrees_with"]}
                                  for p in e.get("places", []) if p.get("agrees_with")],
                    "probably_stale": e.get("outlier"),
                })
            job.result = {
                "repo": job.repo, "commit": commit,
                "stats": {"files": rep["stats"]["files"], "passages": rep["stats"]["passages"],
                          "pairs_read": rep["stats"]["pairs_compared"], "flagged": rep["stats"]["findings"],
                          "listed": len(items), "errors": rep["stats"]["errors"],
                          "candidate_pairs_found": cstats["near_dup_cross_file"] + cstats["near_dup_same_file"],
                          "pairs_limit": L.scan_pairs + L.scan_key_pairs},
                "items": items,
                "credits": {"spent_now": capped.spent, "list_price": capped.list_price,
                            "answers_replayed": capped.replayed, "calls": capped.calls},
                "note": "The live trial reads at most "
                        f"{L.scan_pairs + L.scan_key_pairs} pairs per repository; the full tool reads 150 by default.",
            }
            if stopped:
                if "timeout" in str(stopped):
                    job.status = outcome = "timed_out"
                    job.error = {"error": "timed_out", "message": f"The scan was stopped after {int(L.job_timeout)} seconds. "
                                 "What was finished by then is shown; pairs not reached were not judged."}
                else:
                    outcome = "stopped_by_cap"
                    job.error = {"error": "stopped_by_cap", "message": "The scan reached the credit cap for one request "
                                 "or the trial budget. What was finished by then is shown."}
                    job.status = "done"
            else:
                job.status = "done"
            job.stage = "finished"
        except GitHubError as e:
            job.status, outcome = "failed", f"github_{e.code}"
            job.error = {"error": e.code, "message": e.message}
            job.stage = "stopped"
        except Exception as e:                                     # never leave a job hanging
            job.status, outcome = "failed", "internal_error"
            job.error = {"error": "internal_error", "message": "The scan failed on our side. Nothing was listed. "
                                                               "The replay on this page is not affected."}
            job.stage = "stopped"
            self._log(job.ip, "scan", "exception", kind=type(e).__name__)
        finally:
            job.finished = self.now()
            if job.result is not None:
                job.result["budget"] = self.status()["budget"]
            with self._lock:
                self._queued -= 1
            self._slot.release()
            self._log(job.ip, "scan", outcome, repo=job.repo, credits=capped.spent, calls=capped.calls,
                      seconds=round(job.finished - job.started, 1))
