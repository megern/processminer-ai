from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_task_workbench_and_bundled_assets():
    page = client.get('/')
    assert page.status_code == 200
    assert 'Load synthetic example' in page.text
    assert 'Export report' in page.text
    for path in ['/assets/app.js', '/assets/common.js', '/assets/styles.css', '/guide']:
        assert client.get(path).status_code == 200
    assert 'Intended use' in client.get('/guide').text
    assert app.version == '0.2.0'

from app.csv_import import parse_csv
import pytest

def test_quoted_csv_and_bom_preserve_text():
    headers, rows = parse_csv('\ufeffid,note\r\n001,"comma, and ""quoted"" text"\r\n')
    assert headers == ['id', 'note']
    assert rows == [{'id': '001', 'note': 'comma, and "quoted" text'}]

def test_csv_rejects_duplicate_headers_ragged_records_and_invalid_quotes():
    for text in ['a, a\n1,2', 'a,b\n1', 'a,b\n"unterminated,2', 'a,b\n']:
        assert client.post('/csv/preview', json={'csv_text': text}).status_code == 422

def test_csv_limits_and_inert_text_preview():
    assert client.post('/csv/preview', json={'csv_text': 'a\n'+('x'*10001)}).status_code == 422
    assert client.post('/csv/preview', json={'csv_text': 'a\n'+'1\n'*10001}).status_code == 422
    result = client.post('/csv/preview', json={'csv_text': 'value\n<script>alert(1)</script>\n=SUM(A1:A2)'}).json()
    assert result['preview'][0]['value'] == '<script>alert(1)</script>'
    assert result['preview'][1]['value'] == '=SUM(A1:A2)'
    assert result['row_count'] == 2

def test_csv_event_mapping_sorts_traces_and_measures_intervals():
    payload={'csv_text':'ticket,task,when\nA,Review,2026-01-01T00:10:00Z\nA,Start,2026-01-01T00:00:00Z\nB,Start,2026-01-01T01:00:00Z\nB,Review,2026-01-01T01:20:00Z','case_column':'ticket','activity_column':'task','timestamp_column':'when'}
    response=client.post('/csv/analyze',json=payload)
    assert response.status_code==200
    result=response.json()
    assert result['directly_follows']==[{'from':'Start','to':'Review','count':2,'mean_seconds':900,'total_seconds':1800}]
    assert result['variants'][0]=={'activities':['Start','Review'],'case_count':2}

def test_csv_rejects_duplicate_mapping_and_guessing_timezones():
    payload={'csv_text':'case,activity,time\nA,Start,2026-01-01T00:00:00','case_column':'case','activity_column':'activity','timestamp_column':'time'}
    result=client.post('/csv/analyze',json=payload)
    assert result.status_code==422 and 'timezone' in result.json()['detail']
    payload['timestamp_column']='activity'
    assert client.post('/csv/analyze',json=payload).status_code==422
    payload['timestamp_column']='time';payload['csv_text']='case,activity,time\nA,Start,12345'
    assert client.post('/csv/analyze',json=payload).status_code==422
