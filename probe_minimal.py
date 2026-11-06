"""Day-1 probes: smallest possible calls to each endpoint to learn the real
request/response shape and the credit cost. Run: python -X utf8 probe_minimal.py <name>"""
import json
import sys

from docsdrift.client import Clocked, credits_used

c = Clocked(budget=5000)


def show(tag):
    rec = json.load(open(f"recordings/{tag}.json", encoding="utf-8"))
    print(tag, "status", rec["status"], "round_trip_ms", rec["round_trip_ms"], rec["response_headers"])


def compare_min():
    r = c.call("compare", {"documents": [
        {"id": "a", "text": "The default request timeout is 30 seconds."},
        {"id": "b", "text": "Requests time out after 60 seconds by default."},
    ]}, "probe/compare-min-conflict")
    show("probe/compare-min-conflict")
    print(json.dumps(r, indent=1)[:3000])


def compare_number_scope():
    # What does it count as a conflict? Same key, different scope / version.
    docs = [
        {"id": "a", "text": "## Requirements\n\nThis tool requires Python 3.8 or newer. Install it with pip."},
        {"id": "b", "text": "## Installation\n\nPython 3.10+ is required. Use `pip install tool`."},
        {"id": "c", "text": "## Changelog\n\n### 2.0.0\n\nDropped support for Python 3.8 and 3.9."},
        {"id": "d", "text": "## Windows notes\n\nOn Windows, the default cache directory is %LOCALAPPDATA%\\tool."},
    ]
    r = c.call("compare", {"documents": docs, "evidence": "all"}, "probe/compare-4docs")
    show("probe/compare-4docs")
    for p in r["pairs"]:
        print(p["a"], p["b"], p["relation"], p["probabilities"], "conf:", len(p.get("conflicts", [])), "dup:", len(p.get("duplicates", [])))
        for f in p.get("conflicts", []):
            print("   CONFLICT", f.get("kind"), f.get("confidence"), "|", f["a"].get("quote") if f.get("a") else None, "<>", f["b"].get("quote") if f.get("b") else None)


def rerank_min():
    r = c.call("rerank", {
        "query": "What is the default request timeout?",
        "documents": [
            {"id": "a", "text": "The default request timeout is 30 seconds."},
            {"id": "b", "text": "Install the package with pip."},
            {"id": "c", "title": "Configuration", "text": "timeout: how long to wait for a response. See the defaults table."},
        ],
    }, "probe/rerank-min")
    show("probe/rerank-min")
    print(json.dumps(r, indent=1)[:2500])


def grounding_min():
    r = c.call("grounding", {
        "documents": [{"id": "config", "text": "## Configuration\n\n`timeout` (default: 60): seconds to wait for a response.\n`retries` (default: 3): number of retry attempts."}],
        "answer": "The default timeout is 30 seconds. Requests are retried 3 times. TLS 1.3 is required.",
        "evidence": "all",
    }, "probe/grounding-min")
    show("probe/grounding-min")
    print(json.dumps(r, indent=1)[:4000])


if __name__ == "__main__":
    for name in sys.argv[1:]:
        globals()[name]()
    print("credits used so far:", credits_used())
