const byId = (id) => document.getElementById(id);
const number = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
const percentage = new Intl.NumberFormat("en", { style: "percent" });
const money = new Intl.NumberFormat("en", { style: "currency", currency: "USD", maximumFractionDigits: 6 });
const conditionNames = {
  normal: "Normal",
  "older result first": "Older result first",
  "older source timeout": "Older source timeout",
  "source outage": "Source outage",
};
const exampleCase = "v7-node18";
const exampleAnswers = { supported: "Yes, it works.", contradicted: "No, it needs a newer Node.js version.", unknown: "I don’t know." };
const firstResultAgent = "First-result reader";
const exampleAgents = [firstResultAgent, "Version-aware verifier"];
const exampleConditions = {
  normal: "The Vite 7 guide came first.",
  "older result first": "The Vite 6 guide came first.",
  "source outage": "Neither guide was available.",
};

const conditionSelect = byId("condition");
const trialSelect = byId("trial");
const status = byId("status");
const controls = [byId("run"), byId("recorded"), byId("repeats")];
const overviewButtons = document.querySelectorAll(".overview > .view-toggle button");
const themeButtons = document.querySelectorAll(".theme-toggle button");
const evidenceButtons = document.querySelectorAll(".evidence-toggle button");
const exampleOutput = byId("example-results");
const exampleStatus = byId("example-status");
let report;
let recorded;
let cases = [];
let selectedCase = exampleCase;
let exampleRuns = [];
let inspectionRuns = [];
let inspectionHasRepeats = false;

function showTheme(theme) {
  const light = theme === "light";
  if (light) document.documentElement.dataset.look = "studio";
  else delete document.documentElement.dataset.look;
  document.querySelector('meta[name="theme-color"]').content = light ? "#eef0f3" : "#0a0e16";
  for (const button of themeButtons) {
    const active = button.dataset.theme === theme;
    button.classList.toggle("on", active);
    button.setAttribute("aria-pressed", String(active));
  }
}

function showOverview(view) {
  for (const button of overviewButtons) {
    const panel = button.getAttribute("aria-controls");
    const active = panel === view;
    button.classList.toggle("on", active);
    button.setAttribute("aria-pressed", String(active));
    byId(panel).hidden = !active;
  }
  document.querySelector(".overview").scrollTop = 0;
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content != null) node.textContent = content;
  return node;
}

function format(value, formatter, suffix = "") {
  return value == null ? "Unreported" : formatter.format(value) + suffix;
}

function latency(milliseconds) {
  return milliseconds >= 1000 ? format(milliseconds / 1000, number, " s") : format(milliseconds, number, " ms");
}

function metrics(entries) {
  const list = element("dl", "metrics");
  for (const [label, value] of entries) {
    const pair = element("div");
    pair.append(element("dt", null, label), element("dd", null, value));
    list.append(pair);
  }
  return list;
}

function agentCard(agent) {
  const card = element("article", "agent-card answer");
  const result = element("div");
  const score = element("div", "score-line");
  score.append(element("span", "pass-rate", percentage.format(agent.successRate)),
    element("span", "score-note", `${agent.passed}/${agent.runs} trials passed`));
  const rate = element("progress");
  rate.max = 1;
  rate.value = agent.successRate;
  rate.setAttribute("aria-label", `${agent.agent} pass rate`);
  result.append(element("h3", null, agent.agent), score, rate);
  card.append(result, metrics([
    ["Avg. time", latency(agent.avgLatencyMs)],
    ["Avg. steps", format(agent.avgSteps, number)],
    ["Avg. tool calls", format(agent.avgToolCalls, number)],
    ["Tokens", format(agent.tokens, number)],
    ["Cost", format(agent.costUsd, money)],
    ["Consistency", agent.consistencyRate == null ? "Needs repeats" : percentage.format(agent.consistencyRate)],
  ]));
  return card;
}

function sourceLink(url, label) {
  const parsed = URL.parse(url);
  if (parsed?.protocol !== "https:" && parsed?.protocol !== "http:") return null;
  const link = element("a", null, label || parsed.hostname);
  link.href = parsed.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function exampleCard(run, evidence) {
  const orderedSources = run.trace.find((step) => step.sources)?.sources || [];
  const readsFirst = run.agent === firstResultAgent;
  const baseline = exampleAgents.includes(run.agent);
  const source = baseline ? evidence.find((entry) => readsFirst ? entry.url === orderedSources[0] : entry.target === run.target) : undefined;
  let explanation = "No guides were available, so it left the question unanswered.";
  if (run.error) explanation = "The assistant hit an error. Open the trace for details.";
  else if (!baseline) explanation = orderedSources.length
    ? `It received ${orderedSources.length} guides in the same search order.`
    : "It answered without any guides.";
  else if (source) explanation = readsFirst
    ? `It stopped at the first result, which covers ${source.target}.`
    : `It checked the guide for ${run.target}, the version in the question.`;
  else if (orderedSources.length) explanation = "The run returned no matching citation.";

  const card = element("article", run.success ? "example-card answer correct" : "example-card answer disputed");
  const header = element("div", "trace-title-row");
  const verdict = run.error ? "Error" : run.success ? "Correct" : "Incorrect";
  header.append(element("h3", null, run.agent), element("span", run.success ? "pill passed" : "pill failed", verdict));
  card.append(header, element("p", "example-answer", exampleAnswers[run.answer] || "No answer"),
    element("p", "example-reason", explanation));
  if (source) {
    const index = orderedSources.indexOf(source.url);
    const label = index === -1 ? `${source.target} guide` : `Result ${index + 1} · ${source.target} guide`;
    const citation = element("div", "example-source");
    const link = sourceLink(source.url, label);
    if (link) citation.append(link);
    citation.append(element("blockquote", null, `“${source.excerpt}”`));
    card.append(citation);
  }
  if (!baseline && !run.error) {
    const usage = run.tokens == null ? "Token usage unreported" : `${number.format(run.tokens)} tokens`;
    card.append(element("p", "example-source model-usage", `Live response · ${latency(run.latencyMs)} · ${usage}`));
  }
  return card;
}

function showExample(runs, label) {
  exampleRuns = runs.filter((run) => run.caseId === exampleCase && run.repeat === 1);
  byId("inspect-example").disabled = !exampleRuns.length;
  if (!exampleRuns.length) return;
  const evidence = exampleRuns.flatMap((run) => run.trace.flatMap((step) => step.evidence || []));
  exampleOutput.replaceChildren(...exampleRuns.map((run) => exampleCard(run, evidence)));
  const condition = exampleRuns[0].condition;
  for (const button of evidenceButtons) {
    const active = button.dataset.condition === condition;
    button.classList.toggle("on", active);
    button.setAttribute("aria-pressed", String(active));
  }
  exampleStatus.classList.remove("error");
  exampleStatus.textContent = `${label} · ${exampleConditions[condition]}`;
}

async function replayExample(condition) {
  if (exampleOutput.getAttribute("aria-busy") === "true") return;
  exampleOutput.setAttribute("aria-busy", "true");
  exampleStatus.classList.remove("error");
  exampleStatus.textContent = "Running the assistants…";
  for (const button of evidenceButtons) button.setAttribute("aria-disabled", "true");
  try {
    const response = await fetch("../api/example", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ condition }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to run the example.");
    showExample(result.runs, `${result.runs.length} trials complete`);
    showExampleInspection();
  } catch (error) {
    exampleStatus.textContent = error.message;
    exampleStatus.classList.add("error");
  } finally {
    exampleOutput.setAttribute("aria-busy", "false");
    for (const button of evidenceButtons) button.removeAttribute("aria-disabled");
  }
}

function traceStep(step) {
  const row = element("li");
  const detail = element("div", "trace-step");
  detail.append(element("strong", null, step.action), element("p", null, step.detail));
  if (step.requestId) detail.append(element("p", "request-id", step.requestId));
  const sources = (step.sources || []).map((url, index) => sourceLink(url, `Source ${index + 1}`));
  if (step.url) sources.push(sourceLink(step.url, "Open source"));
  sources.push(...(step.evidence || []).map((entry) => sourceLink(entry.url, entry.title)));
  detail.append(...sources.filter(Boolean));
  row.append(element("span", null, step.step), detail);
  return row;
}

function traceCard(run) {
  const card = element("article", "trace-card");
  const header = element("div", "trace-title-row");
  header.append(element("h3", null, run.agent), element("span", run.success ? "pill passed" : "pill failed", run.success ? "Passed" : "Failed"));
  const verdict = run.answer ? `Verdict · ${run.answer}` : "No verdict";
  const trace = element("ol", "trace feed");
  trace.append(...run.trace.map(traceStep));
  card.append(header, element("p", "trace-answer", verdict), metrics([
    ["Time", latency(run.latencyMs)], ["Steps", run.steps], ["Tool calls", run.toolCalls],
    ["Tokens", format(run.tokens, number)], ["Cost", format(run.costUsd, money)],
  ]), trace);
  return card;
}

function showTraces() {
  const repeat = inspectionHasRepeats ? Number(trialSelect.value) : 1;
  const runs = inspectionRuns.filter((run) => run.repeat === repeat);
  byId("traces").replaceChildren(...runs.map(traceCard));
}

function markCase(caseId) {
  for (const button of byId("case-list").querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.caseId === caseId));
  }
}

function showInspection(runs, hasRepeats, label = "") {
  const test = runs[0];
  inspectionRuns = runs;
  inspectionHasRepeats = Boolean(test && hasRepeats);
  byId("case-condition").textContent = label || (test ? conditionNames[test.condition] : "Execution trace");
  byId("case-title").textContent = test?.task || "No matching case";
  byId("case-expected").textContent = test ? `${test.target} · Expected verdict: ${test.expected}` : "";
  byId("repeat-picker").hidden = !inspectionHasRepeats;
  showTraces();
  byId("trace-output").scrollTop = 0;
}

function showCase(caseId) {
  selectedCase = caseId;
  markCase(caseId);
  showInspection(report.runs.filter((run) => run.caseId === caseId), report.repeats > 1);
}

function showExampleInspection() {
  markCase();
  showInspection(exampleRuns, false, `Example · ${conditionNames[exampleRuns[0].condition]}`);
}

function caseRow(test) {
  const row = element("button", "case-row mail");
  row.type = "button";
  row.dataset.caseId = test.caseId;
  const meta = element("span", "case-meta");
  meta.append(element("span", null, test.target), element("span", test.condition === "normal" ? null : "condition", conditionNames[test.condition]));
  row.append(element("span", "case-name", test.task), meta);
  row.addEventListener("click", () => showCase(test.caseId));
  return row;
}

function showCases() {
  const condition = conditionSelect.value;
  const visible = cases.filter((test) => condition === "all" || test.condition === condition);
  const selected = visible.find((test) => test.caseId === selectedCase) || visible[0];
  byId("case-count").textContent = `${visible.length} of ${cases.length}`;
  byId("case-list").replaceChildren(...(visible.length ? visible.map(caseRow) : [element("p", "case-empty", "No cases match this condition.")]));
  showCase(selected?.caseId);
}

function showReport(result, isRecorded) {
  report = result;
  recorded = isRecorded;
  cases = [...new Map(result.runs.map((run) => [run.caseId, run])).values()];
  if (!exampleRuns.length) {
    showExample(result.runs.filter((run) => exampleAgents.includes(run.agent)), isRecorded ? "Recorded example" : "Benchmark example");
  }
  const source = isRecorded ? "Recorded Bifrost run" : "Fresh local run";
  const runKind = byId("run-kind");
  runKind.textContent = isRecorded ? "Recorded suite" : "Fresh suite";
  runKind.classList.remove("connecting", "offline");
  byId("total-cases").textContent = result.caseCount;
  byId("total-trials").textContent = result.runs.length;
  byId("report-meta").textContent = `${source} · ${result.caseCount} cases · ${result.runs.length} trials`;
  byId("agents").replaceChildren(...result.summary.map(agentCard));
  const previousTrial = Number(trialSelect.value) || 1;
  trialSelect.replaceChildren(...Array.from({ length: result.repeats }, (_, index) => {
    const option = element("option", null, `Repeat ${index + 1}`);
    option.value = index + 1;
    return option;
  }));
  trialSelect.value = Math.min(previousTrial, result.repeats);
  showCases();
  const protocol = Object.entries(result.protocol || {}).flatMap(([key, value]) => [
    element("dt", null, key[0].toUpperCase() + key.slice(1)), element("dd", null, value),
  ]);
  if (result.provenance?.model) {
    protocol.push(element("dt", null, "Recorded gateway"), element("dd", null,
      `${result.provenance.model} · ${result.provenance.gateway} · ${result.provenance.inference}`));
  }
  byId("protocol").replaceChildren(...protocol);
  byId("export").disabled = false;
  conditionSelect.disabled = false;
}

async function loadReport(useRecording, revealResults = false) {
  controls.forEach((control) => { control.disabled = true; });
  status.classList.remove("error");
  status.textContent = useRecording ? "Loading recorded Bifrost run…" : "Running the suite. Model inference may take a few minutes if configured.";
  try {
    const response = useRecording ? await fetch("../api/recorded-benchmark") : await fetch("../api/benchmark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repeats: Number(byId("repeats").value) }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to load the benchmark report.");
    showReport(result, useRecording);
    if (revealResults) showOverview("comparison");
    status.textContent = "";
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
    if (!exampleRuns.length && exampleOutput.getAttribute("aria-busy") !== "true") {
      exampleStatus.textContent = "Choose a condition to run the example.";
    }
    if (!report) {
      const runKind = byId("run-kind");
      runKind.textContent = "Unavailable";
      runKind.classList.add("offline");
    }
  } finally {
    controls.forEach((control) => { control.disabled = false; });
  }
}

byId("run-form").addEventListener("submit", (event) => {
  event.preventDefault();
  loadReport(false, true);
});
byId("recorded").addEventListener("click", () => loadReport(true, true));
for (const button of overviewButtons) {
  button.addEventListener("click", () => showOverview(button.getAttribute("aria-controls")));
}
for (const button of themeButtons) {
  button.addEventListener("click", () => {
    const theme = button.dataset.theme;
    showTheme(theme);
    try {
      localStorage.setItem("release-bench-theme", theme);
    } catch {
      // Theme switching still works for the current page.
    }
  });
}
conditionSelect.addEventListener("change", showCases);
trialSelect.addEventListener("change", showTraces);
for (const button of evidenceButtons) {
  button.addEventListener("click", () => replayExample(button.dataset.condition));
}
byId("inspect-example").addEventListener("click", () => {
  showExampleInspection();
  const inspector = byId("inspector");
  inspector.focus({ preventScroll: true });
  inspector.scrollIntoView({ block: "start" });
});
byId("export").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = element("a");
  link.href = url;
  link.download = recorded ? "release-bench-bifrost-recording.json" : "release-bench-results.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

showTheme(document.documentElement.dataset.look === "studio" ? "light" : "dark");
fetch("../api/status")
  .then((response) => response.ok ? response.json() : null)
  .then((config) => {
    if (config?.bifrost_available) byId("model-status").textContent = "Bifrost configured";
    else if (config?.external_agent_available) byId("model-status").textContent = "External agent configured";
  })
  .catch(() => {});
loadReport(true);
