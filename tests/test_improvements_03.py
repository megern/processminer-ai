from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def event(case, activity, minute):
    return {
        "case_id": case,
        "activity": activity,
        "timestamp": (
            datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute)
        ).isoformat(),
    }


def test_rework_is_within_case_not_global_activity_frequency():
    events = [
        event("a", "Start", 0),
        event("a", "Review", 1),
        event("a", "Review", 2),
        event("b", "Start", 0),
        event("b", "Review", 3),
    ]
    r = client.post("/analyze", json={"events": events}).json()
    assert r["rework"]["cases_with_rework"] == 1
    assert r["rework"]["case_fraction"] == 0.5
    assert r["rework"]["extra_activity_visits"] == 1
    assert r["case_details"][0]["repeated_activities"] == [
        {"activity": "Review", "extra_visits": 1}
    ]
    assert r["case_details"][1]["rework_events"] == 0


def test_known_percentiles_use_all_cases_despite_drilldown_limit():
    events = []
    for i, minutes in enumerate([0, 10, 20, 30]):
        events += [event(str(i), "Start", 0), event(str(i), "End", minutes)]
    r = client.post("/analyze", json={"events": events, "case_limit": 1}).json()
    assert r["case_duration_summary"]["median_seconds"] == 15 * 60
    assert r["case_duration_summary"]["p90_seconds"] == 27 * 60
    assert r["case_duration_summary"]["p95_seconds"] == pytest.approx(28.5 * 60)
    assert len(r["case_details"]) == 1 and r["case_details_truncated"]


def test_long_trace_and_repetition_previews_are_bounded():
    events = [event("only", str(i % 51), i) for i in range(102)]
    r = client.post("/analyze", json={"events": events}).json()
    case = r["case_details"][0]
    assert len(case["variant"]) == 50 and case["variant_truncated"]
    assert (
        len(case["repeated_activities"]) == 50 and case["repeated_activities_truncated"]
    )
    assert case["repeated_activity_count"] == 51 and case["rework_events"] == 51
    assert r["case_duration_summary"]["median_seconds"] == 101 * 60
    assert r["case_duration_summary"]["p90_seconds"] == 101 * 60


def test_case_limit_validation_and_single_event_zero_duration():
    for limit in [0, 201]:
        assert (
            client.post(
                "/analyze",
                json={"events": [event("a", "Only", 0)], "case_limit": limit},
            ).status_code
            == 422
        )
    r = client.post("/analyze", json={"events": [event("a", "Only", 0)]}).json()
    assert r["case_duration_summary"]["p95_seconds"] == 0
    assert r["rework"]["extra_activity_visits"] == 0
