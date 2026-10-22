import {
  getRevision,
  isStale,
  assertCurrent,
  $,
  el,
  replace,
  table,
  previewRows,
  bars,
  metrics,
  api,
  action,
  status,
  newReport,
  setupExports,
  invalidate,
  bindFile,
  readFile,
  setOptions,
  format,
  download,
} from "./common.js";
let columns = [],
  synthetic = false,
  report = null;
function dirty() {
  synthetic = false;
  report = null;
  $("data-origin").textContent = "Your input · changed";
  $("technical").textContent = "Inputs changed. Run again.";
  invalidate();
}
$("csv").oninput = dirty;
$("case-limit").oninput = dirty;
for (const id of [
  "case-column",
  "activity-column",
  "timestamp-column",
  "case-limit",
])
  $(id).onchange = dirty;
async function preview() {
  report = null;
  invalidate();
  const generation = getRevision();
  const r = await api("/csv/preview", { csv_text: $("csv").value });
  assertCurrent(generation);
  columns = r.columns;
  replace(
    $("preview-data"),
    el(
      "p",
      `${r.row_count} event rows · first ${r.preview.length} shown`,
      "hint",
    ),
    previewRows(columns, r.preview),
  );
  setOptions(
    $("case-column"),
    columns,
    columns.find((c) => /case/i.test(c)) || columns[0],
  );
  setOptions(
    $("activity-column"),
    columns,
    columns.find((c) => /activity|event/i.test(c)) || columns[1],
  );
  setOptions(
    $("timestamp-column"),
    columns,
    columns.find((c) => /time|date/i.test(c)) || columns[2],
  );
  return { ...r, generation };
}
$("preview").onclick = async () => {
  try {
    dirty();
    const prepared = await preview();
    assertCurrent(prepared.generation);
    status(
      "CSV parsed. Map three distinct columns and check the timezone in your timestamps.",
    );
  } catch (e) {
    if (isStale(e)) return;
    status(e.message, true);
  }
};
bindFile(
  "csv-file",
  "csv",
  async () => {
    dirty();
    const prepared = await preview();
    assertCurrent(prepared.generation);
    status("Event CSV loaded. Review the mapping.");
  },
  dirty,
);
function config() {
  return {
    csv_text: $("csv").value,
    case_column: $("case-column").value,
    activity_column: $("activity-column").value,
    timestamp_column: $("timestamp-column").value,
    case_limit: Number($("case-limit").value || 50),
    ...($("reference-enable").checked
      ? { reference: referenceConfiguration() }
      : {}),
  };
}
$("example").onclick = async () => {
  try {
    dirty();
    $("csv").value =
      "case,activity,time\n1,Start,2026-01-01T00:00:00Z\n1,Review,2026-01-01T00:10:00Z\n1,Complete,2026-01-01T00:12:00Z\n2,Start,2026-01-01T01:00:00Z\n2,Review,2026-01-01T01:20:00Z\n2,Complete,2026-01-01T01:25:00Z";
    const prepared = await preview();
    assertCurrent(prepared.generation);
    $("case-limit").value = 50;
    $("reference-enable").checked = false;
    synthetic = true;
    $("data-origin").textContent = "Synthetic example · not a real process log";
    status(
      "Synthetic three-activity paths loaded. Start → Review has the largest mean observed interval.",
    );
  } catch (e) {
    if (isStale(e)) return;
    status(e.message, true);
  }
};
$("config-file").onchange = async () => {
  try {
    dirty();
    const generation = getRevision();
    const text = await readFile($("config-file"));
    assertCurrent(generation);
    if (text === null) return;
    const data = JSON.parse(text);
    if (typeof data.csv_text !== "string")
      throw new Error("Use a mapping configuration exported by this tool.");
    $("csv").value = data.csv_text;
    dirty();
    const prepared = await preview();
    assertCurrent(prepared.generation);
    for (const [id, key] of [
      ["case-column", "case_column"],
      ["activity-column", "activity_column"],
      ["timestamp-column", "timestamp_column"],
    ]) {
      if (!columns.includes(data[key]))
        throw new Error("Mapped column " + key + " is not present in the CSV.");
      $(id).value = data[key];
    }
    $("case-limit").value = data.case_limit ?? 50;
    if (data.reference) loadReference(data.reference);
    $("reference-enable").checked = Boolean(data.reference);
    status("Mapping imported. Review events before analysis.");
  } catch (e) {
    if (isStale(e)) return;
    dirty();
    status("Cannot import mapping: " + e.message, true);
  }
};
$("run").onclick = () =>
  action(async () => {
    report = null;
    const input = config();
    if (!columns.length)
      throw new Error("Preview the event log and map its columns first.");
    const generation = getRevision(),
      result = await api("/csv/analyze", input);
    assertCurrent(generation);
    report = newReport("ProcessMiner AI", input, result, synthetic);
    replace(
      $("results"),
      metrics([
        ["Cases", result.case_count],
        ["Events", result.event_count],
        ["Mean case minutes", result.mean_case_seconds / 60],
      ]),
    );
    const summary = result.case_duration_summary;
    $("results").append(
      el("h3", "Case duration distribution"),
      metrics([
        ["Median minutes", summary.median_seconds / 60],
        ["P90 minutes", summary.p90_seconds / 60],
        ["P95 minutes", summary.p95_seconds / 60],
      ]),
      el(
        "p",
        summary.method +
          " Durations are observed first-to-last spans, not predictions.",
        "hint",
      ),
      el("h3", "Repeated activity within a case"),
      metrics([
        ["Cases with repetition", result.rework.cases_with_rework],
        ["Extra visits", result.rework.extra_activity_visits],
      ]),
      el("p", result.rework.definition, "notice"),
      el("h3", "Case drill-down"),
      table(
        [
          "Case",
          "Events",
          "Duration minutes",
          "Path preview",
          "Extra visits",
          "Repeated activities",
        ],
        result.case_details.map((c) => [
          c.case_id,
          c.event_count,
          format(c.duration_seconds / 60),
          c.variant.join(" → ") + (c.variant_truncated ? " … (truncated)" : ""),
          c.rework_events,
          c.repeated_activities
            .map((a) => a.activity + " (+" + a.extra_visits + ")")
            .join("; ") +
            (c.repeated_activities_truncated ? " … (truncated)" : ""),
        ]),
      ),
      el(
        "p",
        result.case_details_truncated
          ? `Showing the first ${result.case_details.length} cases by ID. All cases contribute to summaries.`
          : "All cases shown.",
        "hint",
      ),
    );
    $("results").append(
      el("h3", "Observed paths"),
      table(
        ["Ordered activities", "Cases"],
        result.variants.map((v) => [v.activities.join(" → "), v.case_count]),
      ),
    );
    if (result.directly_follows.length) {
      $("results").append(
        el("h3", "Directly-follows intervals"),
        el(
          "p",
          "These intervals include both waiting and execution time. They are not measured service durations.",
          "hint",
        ),
        bars(
          result.bottlenecks
            .slice(0, 12)
            .map((e) => [e.from + " → " + e.to, e.mean_seconds / 60]),
          Math.max(...result.bottlenecks.map((e) => e.mean_seconds / 60)),
        ),
        table(
          ["From", "To", "Frequency", "Mean minutes", "Total minutes"],
          result.directly_follows.map((e) => [
            e.from,
            e.to,
            e.count,
            format(e.mean_seconds / 60),
            format(e.total_seconds / 60),
          ]),
        ),
      );
      const top = result.bottlenecks[0];
      $("results").append(
        el(
          "p",
          `Investigate ${top.from} → ${top.to} first: mean observed interval ${format(top.mean_seconds / 60)} minutes across ${top.count} transitions. Ask whether this reflects queues, batching, missing events or actual execution time.`,
          "notice",
        ),
      );
    } else
      $("results").append(
        el(
          "p",
          "No consecutive events within a case. Check whether case identifiers accidentally identify individual events.",
          "notice",
        ),
      );
    $("results").append(el("h3", "Automation discovery shortlist"));
    if (!result.automation_candidates.length)
      $("results").append(
        el(
          "p",
          "No activity repeated in this log. More complete cases may be needed.",
        ),
      );
    else
      $("results").append(
        table(
          ["Repeated activity", "Occurrences", "Investigation"],
          result.automation_candidates.map((c) => [
            c.activity,
            c.event_count,
            "Check rule consistency, exception rate and ownership before automating.",
          ]),
        ),
      );
    if (result.tied_timestamp_pairs)
      $("results").append(
        el(
          "p",
          `${result.tied_timestamp_pairs} adjacent pairs share a timestamp. Their order follows the original CSV; verify timestamp precision.`,
          "notice",
        ),
      );
    if (result.conformance) {
      const c = result.conformance;
      $("results").append(
        el("h3", "Reference process conformance"),
        metrics([
          ["Conforming cases", c.conforming_cases],
          ["Violating cases", c.violating_cases],
          ["Descriptive conformance ratio", c.conformance_ratio],
          ["Violations", c.violation_count],
        ]),
        el("p", c.method, "notice"),
        table(
          ["Case", "Conforms", "Violations", "Details"],
          c.case_details.map((d) => [
            d.case_id,
            d.conforming ? "Yes" : "No",
            d.violation_count,
            d.violations
              .map(
                (v) =>
                  v.kind + ": " + (v.activity ?? `${v.source} → ${v.target}`),
              )
              .join("; ") + (d.violations_truncated ? " … (truncated)" : ""),
          ]),
        ),
        el(
          "p",
          c.case_details_truncated
            ? "Drilldown limited; summary includes all cases."
            : "All cases included in drilldown.",
          "hint",
        ),
      );
    }
    $("results").append(el("p", result.limitations, "hint"));
    $("technical").textContent = JSON.stringify(result, null, 2);
    $("export-report").disabled = false;
    $("print").disabled = false;
  });
setupExports("processminer", () => report, config);

const referencePanel = el("fieldset");
referencePanel.id = "reference-panel";
referencePanel.append(el("legend", "Optional reference process"));
const referenceEnable = el("input"),
  referenceLabel = el("label", "Check observed events against reference");
referenceEnable.id = "reference-enable";
referenceEnable.type = "checkbox";
referenceLabel.htmlFor = referenceEnable.id;
referencePanel.append(referenceLabel, referenceEnable);
for (const [id, label, type] of [
  ["reference-starts", "Allowed start activities (one per line)", "textarea"],
  ["reference-ends", "Allowed end activities (one per line)", "textarea"],
  ["reference-file", "Import reference JSON", "file"],
]) {
  const l = el("label", label),
    c = el(type === "textarea" ? "textarea" : "input");
  c.id = id;
  l.htmlFor = id;
  if (type === "file") {
    c.type = "file";
    c.accept = ".json,application/json";
  } else c.maxLength = 50000;
  referencePanel.append(l, c);
}
let referenceEdges = [];
const edgeRows = el("div"),
  addEdge = el("button", "Add allowed transition"),
  referenceExample = el("button", "Load synthetic reference"),
  referenceExport = el("button", "Export reference JSON");
referenceExample.id = "reference-example";
referenceExport.id = "reference-export";
addEdge.id = "reference-add";
referencePanel.append(
  el(
    "p",
    "Allowed adjacent transitions: exact, case-sensitive activity names. All observed cases enter the ratio; there is no Petri-net alignment.",
  ),
  edgeRows,
  addEdge,
  referenceExample,
  referenceExport,
);
document.querySelector(".input-panel").append(referencePanel);
function renderReferenceEdges() {
  replace(edgeRows);
  referenceEdges.forEach((edge, i) => {
    const row = el("div", "", "row");
    for (const key of ["source", "target"]) {
      const l = el("label", key === "source" ? "From activity" : "To activity"),
        c = el("input");
      c.id = `reference-edge-${i}-${key}`;
      l.htmlFor = c.id;
      c.maxLength = 200;
      c.value = edge[key];
      c.oninput = () => {
        edge[key] = c.value;
        dirty();
      };
      row.append(l, c);
    }
    const remove = el("button", "Remove transition");
    remove.onclick = () => {
      referenceEdges.splice(i, 1);
      dirty();
      renderReferenceEdges();
    };
    row.append(remove);
    edgeRows.append(row);
  });
}
function referenceConfiguration() {
  return {
    allowed_starts: $("reference-starts")
      .value.split("\n")
      .map((v) => v.trim())
      .filter(Boolean),
    allowed_ends: $("reference-ends")
      .value.split("\n")
      .map((v) => v.trim())
      .filter(Boolean),
    allowed_edges: referenceEdges.map((e) => ({ ...e })),
  };
}
function loadReference(data) {
  if (
    !Array.isArray(data.allowed_starts) ||
    !Array.isArray(data.allowed_ends) ||
    !Array.isArray(data.allowed_edges) ||
    data.allowed_edges.length > 2000 ||
    data.allowed_starts.length > 200 ||
    data.allowed_ends.length > 200 ||
    [...data.allowed_starts, ...data.allowed_ends].some(
      (v) => typeof v !== "string",
    ) ||
    data.allowed_edges.some(
      (e) => typeof e.source !== "string" || typeof e.target !== "string",
    )
  )
    throw new Error(
      "Reference requires text start/end lists and up to 2,000 source/target transitions.",
    );
  $("reference-starts").value = data.allowed_starts.join("\n");
  $("reference-ends").value = data.allowed_ends.join("\n");
  referenceEdges = data.allowed_edges.map((e) => ({
    source: e.source,
    target: e.target,
  }));
  renderReferenceEdges();
}
referencePanel.addEventListener("input", (event) => {
  if (event?.target?.type !== "file") dirty();
});
referencePanel.addEventListener("change", (event) => {
  if (event?.target?.type !== "file") dirty();
});
addEdge.onclick = () => {
  if (referenceEdges.length >= 2000) {
    status("Maximum 2,000 reference transitions.", true);
    return;
  }
  dirty();
  referenceEdges.push({ source: "", target: "" });
  renderReferenceEdges();
};
referenceExample.onclick = () => {
  dirty();
  loadReference({
    allowed_starts: ["Start"],
    allowed_ends: ["Complete"],
    allowed_edges: [
      { source: "Start", target: "Review" },
      { source: "Review", target: "Complete" },
    ],
  });
  $("reference-enable").checked = true;
  status(
    "Synthetic reference loaded; the event log remains your current input. Reference checks run with the normal analysis button.",
  );
};
referenceExport.onclick = () =>
  download("process-reference.json", referenceConfiguration());
$("reference-file").onchange = async () => {
  try {
    dirty();
    const generation = getRevision(),
      text = await readFile($("reference-file"));
    assertCurrent(generation);
    if (text === null) return;
    loadReference(JSON.parse(text));
    $("reference-enable").checked = true;
    status("Reference imported. Inspect it before checking observed events.");
  } catch (e) {
    if (!isStale(e)) status("Cannot import reference: " + e.message, true);
  }
};
