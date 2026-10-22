from .access import AccessControl
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .core import Request, analyze
from .conformance import Reference
from .guard import InputGuard

app = FastAPI(title="ProcessMiner AI", version="0.4.0")
app.add_middleware(InputGuard)
STATIC = Path(__file__).with_name("static")
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/analyze")
def run(request: Request):
    try:
        return analyze(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


from .csv_import import CSVPreview, parse_csv, convert_rows
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


@app.post("/csv/preview")
def preview_csv(request: CSVPreview):
    try:
        headers, rows = parse_csv(request.csv_text)
        return {"columns": headers, "row_count": len(rows), "preview": rows[:8]}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CSVEvents(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(min_length=1, max_length=2097152)
    case_column: str
    activity_column: str
    timestamp_column: str
    case_limit: int = Field(default=50, ge=1, le=200)
    reference: Reference | None = None


@app.post("/csv/analyze")
def mine_csv(request: CSVEvents):
    try:
        headers, rows = parse_csv(request.csv_text)
        mapping = [
            request.case_column,
            request.activity_column,
            request.timestamp_column,
        ]
        if len(set(mapping)) != 3 or any(column not in headers for column in mapping):
            raise ValueError(
                "Map three different existing columns to case, activity and timestamp."
            )
        from datetime import datetime

        for index, row in enumerate(rows, start=1):
            try:
                parsed = datetime.fromisoformat(
                    row[request.timestamp_column].strip().replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError(
                    f"Event row {index} needs an ISO 8601 timestamp with timezone."
                ) from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError(
                    f"Event row {index} needs an explicit timestamp timezone."
                )
        events = [
            {
                "case_id": row[request.case_column].strip(),
                "activity": row[request.activity_column].strip(),
                "timestamp": row[request.timestamp_column].strip(),
            }
            for row in rows
        ]
        return analyze(
            Request(
                events=events,
                case_limit=request.case_limit,
                reference=request.reference,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/guide")
def user_guide():
    return FileResponse(STATIC / "guide.html")


app.add_middleware(AccessControl)
