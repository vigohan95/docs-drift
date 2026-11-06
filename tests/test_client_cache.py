"""Replay cache: no network, no key, no credits."""
import json

import pytest

from docsdrift.client import Clocked, CacheMiss, request_hash, build_index


def record(tmp_path, endpoint, payload, response, credits="5", name="one.json", status=200):
    rec = {"endpoint": endpoint, "status": status, "request": payload, "response": response,
           "response_headers": {"x-clocked-credits": credits}}
    (tmp_path / name).write_text(json.dumps(rec), encoding="utf-8")


def test_request_hash_ignores_key_order_but_not_content():
    a = {"documents": [{"id": "x", "text": "t"}], "evidence": "flagged"}
    b = {"evidence": "flagged", "documents": [{"text": "t", "id": "x"}]}
    c = {"documents": [{"id": "x", "text": "t2"}], "evidence": "flagged"}
    assert request_hash("compare", a) == request_hash("compare", b)
    assert request_hash("compare", a) != request_hash("compare", c)
    assert request_hash("compare", a) != request_hash("grounding", a)


def test_document_order_changes_the_hash():
    a = {"documents": [{"id": "x", "text": "1"}, {"id": "y", "text": "2"}]}
    b = {"documents": [{"id": "y", "text": "2"}, {"id": "x", "text": "1"}]}
    assert request_hash("compare", a) != request_hash("compare", b)


def test_offline_client_replays_a_recording_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CLOCKED_API_KEY", raising=False)
    monkeypatch.setenv("CLOCKED_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    payload = {"documents": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]}
    record(tmp_path, "compare", payload, {"verdict": "clean", "pairs": []})
    c = Clocked(offline=True, recordings=tmp_path)
    body, credits = c.call_cost("compare", payload)
    assert body == {"verdict": "clean", "pairs": []}
    assert credits == 5.0
    assert c.cache_hits == 1 and c.live_calls == 0 and c.live_credits == 0


def test_offline_client_raises_on_a_cache_miss(tmp_path):
    c = Clocked(offline=True, recordings=tmp_path)
    with pytest.raises(CacheMiss):
        c.call("compare", {"documents": []})


def test_server_errors_are_not_indexed(tmp_path):
    payload = {"documents": [{"id": "a", "text": "x"}]}
    record(tmp_path, "compare", payload, {"error": "nope"}, name="bad.json", status=503)
    assert build_index(tmp_path) == {}


def test_a_recorded_refusal_is_replayed_as_the_same_error(tmp_path):
    from docsdrift.client import ClockedError
    payload = {"documents": [{"id": "a", "text": "x"}]}
    record(tmp_path, "compare", payload, {"error": "a suffix of 3124 tokens exceeds one forward"}, name="r.json", status=422)
    c = Clocked(offline=True, recordings=tmp_path)
    with pytest.raises(ClockedError) as e:
        c.call("compare", payload)
    assert e.value.status == 422 and c.live_calls == 0


def test_index_is_written_and_reused(tmp_path):
    payload = {"query": "q", "documents": ["d"]}
    record(tmp_path, "rerank", payload, {"results": []})
    Clocked(offline=True, recordings=tmp_path)
    idx = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert idx == {request_hash("rerank", payload): "one.json"}


def test_save_index_merges_with_entries_written_by_another_process(tmp_path):
    c = Clocked(offline=True, recordings=tmp_path)
    (tmp_path / "index.json").write_text(json.dumps({"other-hash": "other.json"}), encoding="utf-8")
    c._index["mine"] = "mine.json"
    c.save_index()
    idx = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert idx == {"other-hash": "other.json", "mine": "mine.json"}
