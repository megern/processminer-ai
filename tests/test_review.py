from fastapi.testclient import TestClient
from app.main import app


def test_review_chronological_timezone_edges():
    events = [
        {
            "case_id": "a",
            "activity": "finish",
            "timestamp": "2026-01-01T01:00:00+00:00",
        },
        {"case_id": "a", "activity": "start", "timestamp": "2026-01-01T03:00:00+03:00"},
        {"case_id": "b", "activity": "start", "timestamp": "2026-01-01T00:00:00Z"},
        {"case_id": "b", "activity": "finish", "timestamp": "2026-01-01T00:30:00Z"},
    ]
    response = TestClient(app).post("/analyze", json={"events": events})
    assert response.status_code == 200
    result = response.json()
    assert result["mean_case_seconds"] == 2700
    assert result["directly_follows"] == [
        {
            "from": "start",
            "to": "finish",
            "count": 2,
            "mean_seconds": 2700,
            "total_seconds": 5400,
        }
    ]
    assert result["variants"] == [{"activities": ["start", "finish"], "case_count": 2}]


def test_review_timezone_required():
    response = TestClient(app).post(
        "/analyze",
        json={
            "events": [
                {
                    "case_id": "a",
                    "activity": "start",
                    "timestamp": "2026-01-01T00:00:00",
                }
            ]
        },
    )
    assert response.status_code == 422


def test_review_singleton_is_zero_duration():
    response = TestClient(app).post(
        "/analyze",
        json={
            "events": [
                {
                    "case_id": "a",
                    "activity": "start",
                    "timestamp": "2026-01-01T00:00:00Z",
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["mean_case_seconds"] == 0
    assert response.json()["directly_follows"] == []
