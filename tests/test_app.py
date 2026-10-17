from fastapi.testclient import TestClient
from app.main import app
from app.core import analyze, Request

client = TestClient(app)


def event(case, activity, time):
    return {"case_id": case, "activity": activity, "timestamp": time}


def test_sort_traces_variants_and_durations():
    events = [
        event("1", "B", "2026-01-01T00:10:00Z"),
        event("1", "A", "2026-01-01T00:00:00Z"),
        event("2", "A", "2026-01-01T01:00:00Z"),
        event("2", "B", "2026-01-01T01:20:00Z"),
    ]
    result = analyze(Request(events=events))
    assert result["case_count"] == 2
    assert result["mean_case_seconds"] == 900
    assert result["directly_follows"] == [
        {"from": "A", "to": "B", "count": 2, "mean_seconds": 900, "total_seconds": 1800}
    ]
    assert result["variants"] == [{"activities": ["A", "B"], "case_count": 2}]
    assert len(result["automation_candidates"]) == 2


def test_timezone_equivalence_and_ties():
    events = [
        event("1", "A", "2026-01-01T03:00:00+03:00"),
        event("1", "B", "2026-01-01T00:00:00Z"),
    ]
    r = client.post("/analyze", json={"events": events})
    assert r.status_code == 200
    assert r.json()["tied_timestamp_pairs"] == 1
    assert r.json()["directly_follows"][0]["mean_seconds"] == 0


def test_reject_naive_invalid_empty():
    for events in [
        [],
        [event("1", "A", "bad")],
        [event("1", "A", "2026-01-01T00:00:00")],
    ]:
        assert client.post("/analyze", json={"events": events}).status_code == 422


def test_single_event_has_no_relations():
    r = client.post(
        "/analyze", json={"events": [event("1", "A", "2026-01-01T00:00:00Z")]}
    ).json()
    assert r["directly_follows"] == []
    assert r["mean_case_seconds"] == 0
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_loops_are_preserved():
    events = [
        event("1", "A", "2026-01-01T00:00:00Z"),
        event("1", "A", "2026-01-01T00:01:00Z"),
    ]
    result = client.post("/analyze", json={"events": events}).json()
    assert result["directly_follows"][0]["from"] == "A"
    assert result["directly_follows"][0]["to"] == "A"
    assert result["directly_follows"][0]["mean_seconds"] == 60
