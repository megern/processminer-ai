from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app


def test_independent_duration_quantiles_rework_and_case_limit_denominator():
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    traces = {
        "a": [("A", 0), ("B", 5), ("A", 10)],
        "b": [("A", 0), ("B", 20)],
        "c": [("A", 0), ("A", 0)],
        "d": [("C", 0), ("D", 30)],
    }
    events = [
        {
            "case_id": case,
            "activity": activity,
            "timestamp": (origin + timedelta(minutes=minute)).isoformat(),
        }
        for case, trace in traces.items()
        for activity, minute in trace
    ]
    response = TestClient(app).post(
        "/analyze", json={"events": events, "case_limit": 1}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["case_count"] == 4 and result["event_count"] == 9
    assert result["case_duration_summary"]["median_seconds"] == 900
    assert abs(result["case_duration_summary"]["p90_seconds"] - 1620) < 1e-8
    assert abs(result["case_duration_summary"]["p95_seconds"] - 1710) < 1e-8
    assert result["rework"]["cases_with_rework"] == 2
    assert result["rework"]["case_fraction"] == 0.5
    assert result["rework"]["extra_activity_visits"] == 2
    assert result["tied_timestamp_pairs"] == 1
    assert result["case_details_truncated"] and len(result["case_details"]) == 1
    assert result["case_details"][0]["rework_events"] == 1


def test_independent_long_trace_details_are_bounded_and_summary_exact():
    events = [
        {"case_id": "one", "activity": "A", "timestamp": "2026-01-01T00:00:00Z"}
        for _ in range(120)
    ]
    response = TestClient(app).post("/analyze", json={"events": events})
    assert response.status_code == 200
    result = response.json()
    assert result["rework"]["extra_activity_visits"] == 119
    detail = result["case_details"][0]
    assert len(detail["variant"]) == 50 and detail["variant_truncated"]
    assert detail["repeated_activities"] == [{"activity": "A", "extra_visits": 119}]
    assert result["case_duration_summary"]["p95_seconds"] == 0
