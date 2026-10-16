"""Independent regression for observed missing-record loss in CSV import."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.mark.parametrize("csv_text, expected", [
    ('id,value\n,\na,1', [{"id":"", "value":""}, {"id":"a", "value":"1"}]),
    ('id,value\n"",""\na,1', [{"id":"", "value":""}, {"id":"a", "value":"1"}]),
    ('id,value\n\na,1\n\n', [{"id":"a", "value":"1"}]),
    ('value\n""\n1', [{"value":""}, {"value":"1"}]),
])
def test_independent_preserve_explicit_empty_records(csv_text, expected):
    response=TestClient(app).post('/csv/preview', json={"csv_text":csv_text})
    assert response.status_code==200, response.text
    assert response.json()['row_count']==len(expected)
    assert response.json()['preview']==expected

def test_independent_missing_event_is_not_silently_dropped():
    response=TestClient(app).post('/csv/analyze', json={"csv_text":"case,activity,time\n,,\na,Start,2026-01-01T00:00:00Z", "case_column":"case", "activity_column":"activity", "timestamp_column":"time"})
    assert response.status_code==422, response.text
    assert "timestamp" in response.json()['detail'].lower()
