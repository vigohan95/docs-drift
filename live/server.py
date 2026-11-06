"""HTTP front for the live trial. Standard library only.

    CLOCKED_API_KEY=... python -m live.server

Listens on 127.0.0.1 (a reverse proxy terminates TLS in front of it). Routes:

    GET  /api/status            remaining trial budget and the limits
    POST /api/pair              {"a": "...", "b": "..."}        check one pair of passages
    POST /api/scan              {"repo": "owner/name"}          start a scan, returns a job id
    GET  /api/scan/<job>        progress, then the result

Configuration, all from the environment:
    CLOCKED_API_KEY        the key (never logged, never returned)
    LIVE_DATA_DIR          where the credit ledger and the access log go     (default ./live-data)
    LIVE_BUDGET            total credits this service may spend              (default 3500)
    LIVE_ALLOWED_ORIGINS   comma-separated origins allowed by CORS           (default https://vigohan95.github.io)
    LIVE_BIND, LIVE_PORT   listening address                                 (default 127.0.0.1:8787)
    LIVE_TRUST_PROXY       "1" to take the client address from X-Forwarded-For (set behind the reverse proxy)
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .service import Limits, LiveError, LiveService

MAX_BODY = 16 * 1024


def make_handler(service: LiveService, allowed_origins: set[str], trust_proxy: bool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "docs-drift-live"
        timeout = 30                              # drop connections that send nothing
        sys_version = ""

        def log_message(self, *args):          # the service keeps its own access log
            pass

        def _ip(self) -> str:
            if trust_proxy:
                fwd = self.headers.get("X-Forwarded-For", "")
                if fwd:
                    return fwd.split(",")[-1].strip()[:64]
            return self.client_address[0]

        def _send(self, status: int, body: dict, extra: dict | None = None):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            origin = self.headers.get("Origin")
            if origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _fail(self, e: LiveError):
            extra = {"Retry-After": str(e.extra["retry_after"])} if "retry_after" in e.extra else None
            self._send(e.status, e.body(), extra)

        def do_OPTIONS(self):
            origin = self.headers.get("Origin")
            self.send_response(204)
            if origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Vary", "Origin")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            try:
                if path == "/api/status":
                    return self._send(200, service.status())
                if path.startswith("/api/scan/"):
                    return self._send(200, service.job(path.rsplit("/", 1)[1][:40]))
            except LiveError as e:
                return self._fail(e)
            self._send(404, {"ok": False, "error": "not_found", "message": "No such route."})

        def do_POST(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            if path not in ("/api/pair", "/api/scan"):
                return self._send(404, {"ok": False, "error": "not_found", "message": "No such route."})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                return self._send(413, {"ok": False, "error": "too_large",
                                        "message": f"The request is larger than {MAX_BODY // 1024} KB."})
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return self._send(400, {"ok": False, "error": "bad_input", "message": "The request body must be a JSON object."})
            try:
                if path == "/api/pair":
                    return self._send(200, service.check_pair(self._ip(), body.get("a"), body.get("b")))
                out = service.start_scan(self._ip(), body.get("repo"))
                return self._send(202 if out.get("status") in ("queued", "running") else 200, out)
            except LiveError as e:
                return self._fail(e)
            except Exception:
                return self._send(500, {"ok": False, "error": "internal_error",
                                        "message": "The request failed on our side. The replay on the page is not affected."})

    return Handler


def main() -> int:
    from docsdrift.client import Clocked

    if not os.environ.get("CLOCKED_API_KEY"):
        print("CLOCKED_API_KEY is not set", file=sys.stderr)
        return 2
    data = Path(os.environ.get("LIVE_DATA_DIR", "live-data"))
    limits = Limits(budget=float(os.environ.get("LIVE_BUDGET", Limits.budget)))
    # Answers stay in memory only, so pasted text never reaches the disk; the ledger of credits does.
    client = Clocked(budget=limits.budget, recordings=data, keep_on_disk=False, timeout=60.0)
    service = LiveService(client, data, limits)
    origins = {o.strip() for o in os.environ.get("LIVE_ALLOWED_ORIGINS", "https://vigohan95.github.io").split(",") if o.strip()}
    bind, port = os.environ.get("LIVE_BIND", "127.0.0.1"), int(os.environ.get("LIVE_PORT", "8787"))
    httpd = ThreadingHTTPServer((bind, port), make_handler(service, origins, os.environ.get("LIVE_TRUST_PROXY") == "1"))
    httpd.daemon_threads = True
    print(f"docs-drift live trial on {bind}:{port}; budget {limits.budget:.0f} credits, "
          f"{service.remaining():.0f} remaining; CORS for {sorted(origins)}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
