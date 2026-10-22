# ProcessMiner AI · 0.4.0

**Event-log exploration and automation discovery.** A local event-log analysis tool for analysts and operations teams. It reveals observed case paths, directly-follows relations and long inter-event intervals, then proposes repeated activities for investigation.

The interface is a task-specific workbench, with labeled forms or CSV imports, previews, understandable diagnostics, charts/tables, actionable errors and reusable exports. It is a self-hosted engineering tool, not a claim of certified enterprise production readiness. Methods are deterministic and transparent; no paid service or GPU is required.

## Quickstart

```sh
docker compose up --build
```

Open http://127.0.0.1:8000. Click **Load synthetic example**, then **Run analysis**. Bundled data are explicitly synthetic. The full user guide is linked in the application at `/guide` and saved in [docs/USER_GUIDE.md](docs/USER_GUIDE.md). API schemas and examples are at `/docs`.

Run without Docker (Python 3.12):

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements-dev.lock
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For several apps, change the compose host port; each container listens on 8000. Stateless imports are processed in memory. Reports/configurations can contain your data and should be handled accordingly.

## Real functionality

Events are sorted chronologically within each case, independent of CSV row order. Timestamp ties preserve original input order and are counted. A trace variant is an exact ordered activity sequence. Directly-follows edges aggregate adjacent event pairs with counts and mean/total elapsed seconds. Case duration spans first to last observed event, including zero for a single event.

The “bottleneck” ranking uses mean inter-event elapsed time, which combines waiting and execution and can be distorted by batching, missing events or incomplete cases. It is not activity service duration, a discovered causal process model or a prediction of cycle time. Optional reference allowlist conformance is a separate explicit check described below. No model training or actual automation execution occurs.

Duplicate events are retained; loop edges are possible. Mixed timezone offsets are normalized by datetime comparison. Event frequency alone never proves automation feasibility.

## Workflow and examples

1. Upload or paste event CSV with a unique header and one event per row. Preview it.
2. Map three distinct columns: case identifier, activity name and timestamp. Extra columns are retained only in input exports and ignored by this analysis.
3. Supply ISO 8601 timestamps with a timezone, for example 2026-01-01T09:00:00+03:00 or 2026-01-01T06:00:00Z.
4. Run analysis. Inspect variants, edge frequency and mean elapsed minutes. The chart displays the twelve largest mean intervals; the report retains all edges.
5. Treat repeated activities as an automation investigation shortlist. Ask about rule consistency, exceptions, ownership and missing lifecycle events before proposing automation.
6. Export the complete mapping/input configuration or dated report. Print / save PDF uses the browser print dialog.

The typed JSON API remains supported:

```sh
curl --fail-with-body http://127.0.0.1:8000/analyze -H 'Content-Type: application/json' --data-binary @examples/synthetic.json
```

CSV-based applications also expose `/csv/preview` and `/csv/analyze`, documented in `/docs`. `examples/synthetic-builder.json` is a complete CSV endpoint request; use it with `/csv/analyze`. Importing CSV never executes spreadsheet formulas. Exported CSV from FlowPilot neutralizes formula-like text. Report/configuration export is JSON; browser print can save the result to PDF. No report is represented as an independent audit certification.

## Validation and evidence

```sh
python -m pytest -q
node --test tests/ui.test.mjs
python -m bandit -r app -ll
python -m pip_audit --disable-pip --no-deps --require-hashes -r requirements.lock
```

Historical 0.2 validation is retained under `evidence/rebuild/`; current 0.3 checks are recorded under `evidence/improvements-0.3/`. Older evidence documents the earlier implementation and must not be treated as proof of this interface. Meaningful existing arithmetic/security tests are retained. CI checks Python and frontend tests, dependency vulnerabilities, secret patterns, container vulnerabilities and real HTTP smoke operation. Require the `quality` check in repository branch protection to prevent merging failing revisions; a workflow alone cannot enforce that policy.

## Limits and troubleshooting

The clearly synthetic example has two Start → Review → Complete cases. Start → Review has the largest mean interval: 15 minutes. Review → Complete averages 3.5 minutes. A case with only one event creates no edge.

If no edges appear, check whether the case ID mistakenly identifies individual events. If mapping fails, choose three distinct existing columns. If timestamps lack a timezone, fix the source log or explicitly document an assumed timezone outside the tool; the app does not guess one. If ties are frequent, investigate timestamp precision and lifecycle ordering.

HTTP JSON requests are bounded at 2 MiB; CSV parsing is bounded at 50 columns/10000 rows. Requests are local CPU work, no outside actions. Authentication and HTTPS are required when deploying beyond a trusted localhost environment. See the user guide for detailed method/resource limitations. This release provides optional shared-key API access and per-process compute admission. It does not provide durable history or multi-user access management; see docs/OPERATIONS.md.

## License

MIT. See LICENSE. Review transitive dependency licenses for your distribution. Contributors and review evidence are automated engineering work; no human reviewer is invented.

## Rework and case durations in 0.3

Rework diagnostics count occurrences after the first of the same activity within the same case. A case A→B→B has one extra visit; A→B→A has one extra visit too. Two different cases each visiting A once have no rework even though A is frequent globally. The output reports cases with repetition, their fraction and extra activity visits. Repetition may be legitimate process behavior, not an error, waste or automation opportunity by itself. Existing global frequency candidates remain only an investigation shortlist.

Duration summaries now include median, P90 and P95 across all observed cases. Percentiles use linear interpolation at sorted position (n−1)×p. Durations [0,10,20,30] minutes have median 15, P90 27 and P95 28.5 minutes. A single case has the same value for all three; a single-event case has duration zero. Values are descriptive observed first-to-last spans, not forecasts or service-level guarantees. Incomplete cases, timestamp ties, missing events and mixed business calendars can distort interpretation.

Set the case drill-down limit from 1 to 200 (default 50). Cases are shown in lexicographic case-ID order. All cases still contribute to summaries regardless of that limit. Each row gives event count, observed duration, a path preview, extra visits and repeated activities. Each path and repeated-activity list is capped at 50 entries and marks truncation. Full original events remain in input exports; the bounded drill-down intentionally does not duplicate every event.

API /analyze and /csv/analyze accept case_limit. Outputs add case_duration_summary, rework and bounded case_details, with explicit limit/truncation fields. CSV configurations retain the selected limit and report exports retain the diagnostics. Existing timezone, explicit-empty-record and event-order validation is unchanged.

Fresh 0.3 validation is saved in `evidence/improvements-0.3/`; older reports describe earlier versions and are not proof of these additions. This is automated developer work with separate release-manager and independent QA gates; no human review or enterprise certification is claimed.

The new synthetic request `examples/synthetic-improvements-03.json` demonstrates this version. POST it to `/csv/analyze`; all data are synthetic.

## Reference process conformance in 0.4

Enable the optional reference process panel, enter allowed start/end activities one per line, and add allowed transitions using the From/To fields. Names are exact and case-sensitive after reference/CSV trimming. Load synthetic reference provides Start → Review → Complete; your current event log is retained and conservatively treated as user input. You can import/export a reference JSON containing allowed_starts, allowed_ends and allowed_edges, each edge having source and target fields. Normal configuration/report exports also preserve the reference.

Run analysis with the usual mapped event CSV. A case conforms if and only if its first activity belongs to allowed_starts, its last activity belongs to allowed_ends, and every adjacent chronological activity pair belongs to allowed_edges. A single-event case has no transitions, so only start/end membership matters. Empty edge allowlists can be used for such processes. Cases are sorted chronologically; equal timestamps retain original input order, which can affect a result and should be reviewed.

Conformance ratio is conforming observed cases divided by all observed cases. Each disallowed first activity counts one start violation; each disallowed last activity counts one end violation; every disallowed adjacent pair counts one edge violation. A case may have several violations but counts once as a violating case. All cases enter totals even when the case drilldown is truncated. Case rows are ordered by ID and limited by case_limit (1–200, default 50), with at most 50 detailed violations per shown case and explicit truncation markers. Correct the event log, reference or timestamp precision only with domain justification; do not add edges merely to inflate the ratio.

This is descriptive allowlist conformance, not Petri-net token replay, optimal alignment, missing-event reconstruction, compliance certification or causal process analysis. The reference cannot express concurrency, optional hidden tasks, loops beyond explicitly allowed adjacent edges, global sequence constraints or business-calendar semantics. Incomplete traces can fail starts/ends legitimately. Activity frequency and reference violations do not prove automation feasibility or operational waste.

Both POST /analyze and POST /csv/analyze accept optional reference; omitting it preserves existing mining results without conformance. Up to 200 distinct allowed starts/ends and 2,000 unique edges are accepted; blank names, duplicate edges and duplicate start/end entries are rejected. Existing event/CSV/body limits still apply. See examples/synthetic-conformance.json, which includes one conforming and one skipping case: expected ratio 0.5. If a name mismatch is unexpected, inspect case, whitespace, mapped columns and chronological ties before revising the reference.

Developer validation for 0.4 is saved in `evidence/improvements-0.4/`. Prior evidence describes prior versions. Local developer tests do not establish independent acceptance, hosted CI success or deployment readiness.

## Server access and operating limits

See [Operations](docs/OPERATIONS.md) for optional shared-key API access, per-process request admission, platform notes and the additional work needed for public multi-user hosting.
