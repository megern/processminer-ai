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
  format
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
for (const id of ["case-column", "activity-column", "timestamp-column"])
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
      "hint"
    ),
    previewRows(columns, r.preview)
  );
  setOptions(
    $("case-column"),
    columns,
    columns.find((c) => /case/i.test(c)) || columns[0]
  );
  setOptions(
    $("activity-column"),
    columns,
    columns.find((c) => /activity|event/i.test(c)) || columns[1]
  );
  setOptions(
    $("timestamp-column"),
    columns,
    columns.find((c) => /time|date/i.test(c)) || columns[2]
  );
  return { ...r, generation };
}
$("preview").onclick = async () => {
  try {
    dirty();
    const prepared = await preview();
    assertCurrent(prepared.generation);
    status(
      "CSV parsed. Map three distinct columns and check the timezone in your timestamps."
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
  dirty
);
function config() {
  return {
    csv_text: $("csv").value,
    case_column: $("case-column").value,
    activity_column: $("activity-column").value,
    timestamp_column: $("timestamp-column").value
  };
}
$("example").onclick = async () => {
  try {
    dirty();
    $("csv").value =
      "case,activity,time\n1,Start,2026-01-01T00:00:00Z\n1,Review,2026-01-01T00:10:00Z\n1,Complete,2026-01-01T00:12:00Z\n2,Start,2026-01-01T01:00:00Z\n2,Review,2026-01-01T01:20:00Z\n2,Complete,2026-01-01T01:25:00Z";
    const prepared = await preview();
    assertCurrent(prepared.generation);
    synthetic = true;
    $("data-origin").textContent = "Synthetic example · not a real process log";
    status(
      "Synthetic three-activity paths loaded. Start → Review has the largest mean observed interval."
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
      ["timestamp-column", "timestamp_column"]
    ]) {
      if (!columns.includes(data[key]))
        throw new Error("Mapped column " + key + " is not present in the CSV.");
      $(id).value = data[key];
    }
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
        ["Mean case minutes", result.mean_case_seconds / 60]
      ])
    );
    $("results").append(
      el("h3", "Observed paths"),
      table(
        ["Ordered activities", "Cases"],
        result.variants.map((v) => [v.activities.join(" → "), v.case_count])
      )
    );
    if (result.directly_follows.length) {
      $("results").append(
        el("h3", "Directly-follows intervals"),
        el(
          "p",
          "These intervals include both waiting and execution time. They are not measured service durations.",
          "hint"
        ),
        bars(
          result.bottlenecks
            .slice(0, 12)
            .map((e) => [e.from + " → " + e.to, e.mean_seconds / 60]),
          Math.max(...result.bottlenecks.map((e) => e.mean_seconds / 60))
        ),
        table(
          ["From", "To", "Frequency", "Mean minutes", "Total minutes"],
          result.directly_follows.map((e) => [
            e.from,
            e.to,
            e.count,
            format(e.mean_seconds / 60),
            format(e.total_seconds / 60)
          ])
        )
      );
      const top = result.bottlenecks[0];
      $("results").append(
        el(
          "p",
          `Investigate ${top.from} → ${top.to} first: mean observed interval ${format(top.mean_seconds / 60)} minutes across ${top.count} transitions. Ask whether this reflects queues, batching, missing events or actual execution time.`,
          "notice"
        )
      );
    } else
      $("results").append(
        el(
          "p",
          "No consecutive events within a case. Check whether case identifiers accidentally identify individual events.",
          "notice"
        )
      );
    $("results").append(el("h3", "Automation discovery shortlist"));
    if (!result.automation_candidates.length)
      $("results").append(
        el(
          "p",
          "No activity repeated in this log. More complete cases may be needed."
        )
      );
    else
      $("results").append(
        table(
          ["Repeated activity", "Occurrences", "Investigation"],
          result.automation_candidates.map((c) => [
            c.activity,
            c.event_count,
            "Check rule consistency, exception rate and ownership before automating."
          ])
        )
      );
    if (result.tied_timestamp_pairs)
      $("results").append(
        el(
          "p",
          `${result.tied_timestamp_pairs} adjacent pairs share a timestamp. Their order follows the original CSV; verify timestamp precision.`,
          "notice"
        )
      );
    $("results").append(el("p", result.limitations, "hint"));
    $("technical").textContent = JSON.stringify(result, null, 2);
    $("export-report").disabled = false;
    $("print").disabled = false;
  });
setupExports("processminer", () => report, config);
