# ProcessMiner AI — User guide

## Intended use

A local event-log analysis tool for analysts and operations teams. It reveals observed case paths, directly-follows relations and long inter-event intervals, then proposes repeated activities for investigation.

## Walkthrough

1. Upload or paste event CSV with a unique header and one event per row. Preview it.
2. Map three distinct columns: case identifier, activity name and timestamp. Extra columns are retained only in input exports and ignored by this analysis.
3. Supply ISO 8601 timestamps with a timezone, for example 2026-01-01T09:00:00+03:00 or 2026-01-01T06:00:00Z.
4. Run analysis. Inspect variants, edge frequency and mean elapsed minutes. The chart displays the twelve largest mean intervals; the report retains all edges.
5. Treat repeated activities as an automation investigation shortlist. Ask about rule consistency, exceptions, ownership and missing lifecycle events before proposing automation.
6. Export the complete mapping/input configuration or dated report. Print / save PDF uses the browser print dialog.

## Method and interpretation

Events are sorted chronologically within each case, independent of CSV row order. Timestamp ties preserve original input order and are counted. A trace variant is an exact ordered activity sequence. Directly-follows edges aggregate adjacent event pairs with counts and mean/total elapsed seconds. Case duration spans first to last observed event, including zero for a single event.

The “bottleneck” ranking uses mean inter-event elapsed time, which combines waiting and execution and can be distorted by batching, missing events or incomplete cases. It is not activity service duration, a discovered causal process model, conformance checking or a prediction of cycle time. No model training or actual automation execution occurs.

Duplicate events are retained; loop edges are possible. Mixed timezone offsets are normalized by datetime comparison. Event frequency alone never proves automation feasibility.

## Examples and troubleshooting

The clearly synthetic example has two Start → Review → Complete cases. Start → Review has the largest mean interval: 15 minutes. Review → Complete averages 3.5 minutes. A case with only one event creates no edge.

If no edges appear, check whether the case ID mistakenly identifies individual events. If mapping fails, choose three distinct existing columns. If timestamps lack a timezone, fix the source log or explicitly document an assumed timezone outside the tool; the app does not guess one. If ties are frequent, investigate timestamp precision and lifecycle ordering.

## Resource and privacy limits

The HTTP guard bounds state-changing JSON bodies at 2 MiB and rejects excessive nesting, nonfinite numbers and numeric magnitudes beyond 1e100. CSV imports allow up to 50 unique columns and 10000 data records, with 10000-character cells. FlowPilot additionally caps each node at 10000 rows and conservatively bounds retained workflow outputs at 4 MiB. Browser previews and tables are bounded. Splitting files can change the analytical meaning: do not split event cases or evaluation splits arbitrarily.

The application is stateless and does not persist uploads. Your browser may retain downloads and form content; printed reports and configurations can contain the input data. No external resources or paid APIs are contacted. Requests go to the server you opened: self-host on a trusted machine. Authentication, multi-user access controls, secure ingress, rate limiting and operational backups are deployment responsibilities, not claims of this release.

## API and reuse

Open /docs for the complete schema. POST /analyze remains available for typed JSON inputs. CSV-based tools additionally provide POST /csv/preview and POST /csv/analyze. Configuration exports map directly to the relevant endpoint; readiness uses /analyze, the three CSV tools use /csv/analyze. Report exports contain application/version/date, synthetic provenance, original input and analytical output. They are data files, not executable programs.

All bundled examples are synthetic and are labeled. Editing or importing your own input resets that badge and clears stale results. Controls are locked during analysis; a generation check also prevents a late response replacing changed input results. Error messages identify the failed field or operation; correct it and rerun. Failed analyses never certify completion or preserve an old result as current.

## Local operation

Run docker compose up --build and open http://127.0.0.1:8000. Alternatively install requirements-dev.lock with hashes in a Python 3.12 environment and run uvicorn app.main:app --host 127.0.0.1 --port 8000. Change the host port to run multiple tools. No GPU is needed.
