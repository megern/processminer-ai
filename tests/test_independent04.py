from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def events(traces, tied=False):
    return [
        {
            "case_id": case,
            "activity": activity,
            "timestamp": f"2026-01-01T00:{0 if tied else index:02}:00Z",
        }
        for case, trace in traces.items()
        for index, activity in enumerate(trace)
    ]


def reference():
    return {
        "allowed_starts": ["Start"],
        "allowed_ends": ["Complete"],
        "allowed_edges": [
            {"source": "Start", "target": "Review"},
            {"source": "Review", "target": "Complete"},
        ],
    }


def test_reference_case_denominator_violation_totals_and_truncated_case_details():
    payload = {
        "events": events(
            {
                "a": ["Start", "Review", "Complete"],
                "b": ["Start", "Complete"],
                "c": ["X", "Review", "End"],
                "d": ["Start"],
            }
        ),
        "reference": reference(),
        "case_limit": 1,
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    result = response.json()["conformance"]
    assert (
        result["case_count"] == 4
        and result["conforming_cases"] == 1
        and result["conformance_ratio"] == 0.25
    )
    assert result["violation_count"] == 6
    assert result["violation_counts"] == {
        "disallowed_start": 1,
        "disallowed_end": 2,
        "disallowed_edge": 3,
    }
    assert result["case_details_truncated"] and len(result["case_details"]) == 1
    assert result["case_details"][0]["conforming"]


def test_ties_preserve_input_order_and_single_event_checks_start_and_end():
    ref = {
        "allowed_starts": ["A"],
        "allowed_ends": ["B"],
        "allowed_edges": [{"source": "A", "target": "B"}],
    }
    data = events({"one": ["A", "B"]}, tied=True)
    assert (
        client.post("/analyze", json={"events": data, "reference": ref}).json()[
            "conformance"
        ]["conformance_ratio"]
        == 1
    )
    result = client.post(
        "/analyze", json={"events": list(reversed(data)), "reference": ref}
    ).json()["conformance"]
    assert result["violation_count"] == 3 and result["conformance_ratio"] == 0
    ref = {"allowed_starts": ["A"], "allowed_ends": ["A"], "allowed_edges": []}
    assert (
        client.post(
            "/analyze", json={"events": events({"one": ["A"]}), "reference": ref}
        ).json()["conformance"]["conformance_ratio"]
        == 1
    )


def test_long_violation_detail_is_capped_without_changing_counts_and_duplicate_edges_rejected():
    ref = {"allowed_starts": ["A"], "allowed_ends": ["A"], "allowed_edges": []}
    result = client.post(
        "/analyze",
        json={"events": events({"one": ["A"] * 60}, tied=True), "reference": ref},
    ).json()["conformance"]
    assert result["violation_count"] == 59
    assert (
        len(result["case_details"][0]["violations"]) == 50
        and result["case_details"][0]["violations_truncated"]
    )
    ref = reference()
    ref["allowed_edges"].append({"source": " Start ", "target": "Review"})
    assert (
        client.post(
            "/analyze",
            json={
                "events": events({"one": ["Start", "Review", "Complete"]}),
                "reference": ref,
            },
        ).status_code
        == 422
    )
