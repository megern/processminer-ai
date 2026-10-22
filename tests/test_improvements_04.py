import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core import Request, analyze

client = TestClient(app)
REFERENCE = {
    "allowed_starts": ["A"],
    "allowed_ends": ["C"],
    "allowed_edges": [{"source": "A", "target": "B"}, {"source": "B", "target": "C"}],
}


def events():
    return [
        {"case_id": name, "activity": activity, "timestamp": f"2026-01-01T00:0{i}:00Z"}
        for name, path in [
            ("one", ["A", "B", "C"]),
            ("two", ["A", "C"]),
            ("three", ["B"]),
        ]
        for i, activity in enumerate(path)
    ]


def test_descriptive_conformance_counts_all_cases_bounded_drilldown():
    r = analyze(Request(events=events(), reference=REFERENCE, case_limit=1))[
        "conformance"
    ]
    assert (
        r["conforming_cases"] == 1
        and r["violating_cases"] == 2
        and r["conformance_ratio"] == pytest.approx(1 / 3)
    )
    assert r["violation_counts"] == {
        "disallowed_start": 1,
        "disallowed_end": 1,
        "disallowed_edge": 1,
    }
    assert (
        r["violation_count"] == 3
        and r["case_details_truncated"]
        and len(r["case_details"]) == 1
    )


def test_no_reference_preserves_legacy_and_ties_use_input_order():
    assert "conformance" not in analyze(Request(events=events()))
    e = [
        {"case_id": "a", "activity": a, "timestamp": "2026-01-01T00:00:00Z"}
        for a in ["A", "B", "C"]
    ]
    assert (
        analyze(Request(events=e, reference=REFERENCE))["conformance"][
            "conformance_ratio"
        ]
        == 1
    )
    assert (
        analyze(Request(events=list(reversed(e)), reference=REFERENCE))["conformance"][
            "conformance_ratio"
        ]
        == 0
    )


def test_violation_details_bounded_but_total_exact():
    e = [
        {"case_id": "a", "activity": "X", "timestamp": "2026-01-01T00:00:00Z"}
        for _ in range(100)
    ]
    r = analyze(Request(events=e, reference=REFERENCE))["conformance"]
    assert r["violation_count"] == 101
    assert (
        len(r["case_details"][0]["violations"]) == 50
        and r["case_details"][0]["violations_truncated"]
    )


@pytest.mark.parametrize(
    "reference",
    [
        {**REFERENCE, "allowed_starts": []},
        {**REFERENCE, "allowed_ends": [" "]},
        {**REFERENCE, "allowed_edges": [{"source": "", "target": "C"}]},
        {**REFERENCE, "allowed_edges": REFERENCE["allowed_edges"] * 2},
        {**REFERENCE, "allowed_starts": ["A", "A"]},
    ],
)
def test_invalid_reference_returns_422(reference):
    assert (
        client.post(
            "/analyze", json={"events": events(), "reference": reference}
        ).status_code
        == 422
    )


def test_reference_csv_mapping_real_events():
    r = client.post(
        "/csv/analyze",
        json={
            "csv_text": "case,act,time\n1,A,2026-01-01T00:00:00Z\n1,C,2026-01-01T00:01:00Z",
            "case_column": "case",
            "activity_column": "act",
            "timestamp_column": "time",
            "reference": REFERENCE,
        },
    )
    assert (
        r.status_code == 200
        and r.json()["conformance"]["violation_counts"]["disallowed_edge"] == 1
    )
