"use strict";

const byId = (id) => document.getElementById(id);
const answer = byId("answer");
const example = answer.defaultValue;
const importKey = "quorum-freshness-import";
const onDevice = /\/lab\/(?:index\.html)?$/.test(location.pathname);
let imported = false;
let importEdited = false;
const citationViews = new Map();
let needsNewText = false;
let liveAvailable = false;
let modelAvailable = false;
let verifyRevision = 0;
let verifyResult;
let benchmarkResult;
const modeNames = {replay: "Local replay", public: "Official docs", live: "Tavily search"};

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content != null) node.textContent = content;
  if (className) node.className = className;
  return node;
}
function readable(value) {
  return value == null ? "Unreported" : typeof value === "object" ? JSON.stringify(value) : String(value);
}
function plural(count, word) { return count + " " + word + (count === 1 ? "" : "s"); }
function labeledLine(label, value, className) {
  const p = element("p", null, className);
  p.append(element("strong", label + " "), document.createTextNode(readable(value)));
  return p;
}
function feedback(id, message, error = false) {
  const node = byId(id);
  node.textContent = message;
  node.classList.toggle("error", error);
}
async function api(path, payload) {
  return request("api/" + path, payload);
}
async function request(path, payload) {
  const options = payload ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)} : {};
  const response = await fetch(path, options);
  const result = await response.json().catch(() => null);
  if (!response.ok || !result) throw new Error(result?.error || "The lab server could not complete this request. Try again.");
  return result;
}
function download(data, filename) {
  if (!data) return;
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const link = element("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function route() {
  const bench = location.hash === "#benchmark";
  byId("verifier").hidden = bench;
  byId("benchmark").hidden = !bench;
  byId("verify-link").toggleAttribute("aria-current", !bench);
  byId("bench-link").toggleAttribute("aria-current", bench);
  byId(bench ? "bench-link" : "verify-link").setAttribute("aria-current", "page");
  document.title = (bench ? "Agent benchmark" : "Freshness verifier") + " · Quorum";
}
function updateMode() {
  const live = byId("live-mode");
  const direct = byId("public-mode");
  const replay = document.querySelector('[name="mode"][value="replay"]');
  const publicTarget = byId("public-target");
  publicTarget.disabled = !(liveAvailable && modelAvailable) || imported || needsNewText;
  if (publicTarget.disabled && publicTarget.selected) byId("target").value = "Vite 7";
  const general = publicTarget.selected;
  live.disabled = !liveAvailable || imported || needsNewText;
  replay.disabled = general;
  direct.disabled = general || imported || needsNewText;
  if (general) live.checked = true;
  else if ((live.disabled && live.checked) || (direct.disabled && direct.checked)) replay.checked = true;
  byId("target-hint").textContent = general ? "Check public claims about other topics using search and a model."
    : imported || needsNewText ? "Imported answers can use local Vite documentation."
    : publicTarget.disabled ? "Public web checks require Tavily and a configured model." : "Choose Public web to check other topics.";
  const hint = imported ? "Imported memory uses saved excerpts on this device."
    : needsNewText ? "Enter a new public claim to enable network sources."
    : general ? "Search the public web and evaluate the retrieved evidence with the configured model."
    : live.checked ? "Search and extract official documentation with Tavily."
    : direct.checked ? "Fetch the selected version’s public sources directly."
    : !liveAvailable ? "Replay works offline. Official docs fetches live sources. Tavily requires a server-side key."
    : "Use saved public documentation excerpts on this device.";
  byId("mode-hint").textContent = hint;
  const notice = byId("live-notice");
  notice.hidden = !live.checked && !direct.checked;
  notice.textContent = general ? "Use public material only. The configured model receives your answer and source passages. Tavily receives public search queries and selected URLs."
    : live.checked ? "Use public technical claims only. Tavily receives the public version and topic queries."
    : "Use public technical claims only. This mode requests official source pages over the network.";
}
function loadImport() {
  try {
    const data = JSON.parse(sessionStorage.getItem(importKey));
    if (!data || typeof data.text !== "string" || !data.text.trim()) return;
    imported = true;
    answer.value = data.text;
    byId("use-example").hidden = true;
    byId("import-panel").hidden = false;
    const citations = Array.isArray(data.citations) ? data.citations : [];
    byId("cite-count").textContent = "(" + citations.length + ")";
    const list = byId("citations");
    for (const item of citations) {
      if (!item) continue;
      const li = element("li");
      if (typeof item === "string") li.textContent = item;
      else {
        const title = [item.kind, item.author, item.at].filter(Boolean).join(" · ") || item.title || item.claim_id || "Local citation";
        li.append(element("strong", title));
        if (item.excerpt) li.append(element("p", item.excerpt));
        if (onDevice && typeof item.claim_id === "string" && item.claim_id) {
          const node = element("div", "Looking for saved checks…", "saved-check");
          li.append(node);
          if (!citationViews.has(item.claim_id)) citationViews.set(item.claim_id, {nodes: [], reviews: []});
          citationViews.get(item.claim_id).nodes.push(node);
        }
      }
      list.append(li);
    }
    if (!list.children.length) list.append(element("li", "No local citations accompanied this answer."));
    if (onDevice) refreshSavedChecks();
  } catch { /* Storage may be unavailable in a private browsing context. */ }
}
function showSavedChecks() {
  for (const view of citationViews.values()) {
    const matches = view.reviews.filter(review => review.target === byId("target").value && (review.as_of || "") === byId("as-of").value);
    const latest = matches.sort((a, b) => String(b.checked_at).localeCompare(String(a.checked_at)))[0];
    const verdicts = latest?.claims?.map(claim => claim.verdict).filter(Boolean).join(", ");
    const note = view.error ? "Saved checks unavailable." : latest ? ["Last saved check", latest.checked_at, verdicts].filter(Boolean).join(" · ") : "No saved check for this target and date.";
    for (const node of view.nodes) {
      node.replaceChildren(element("p", note));
      if (view.error || !latest?.claims?.length) continue;
      const details = element("details");
      details.append(element("summary", "Saved evidence"));
      for (const claim of latest.claims) {
        const section = element("div", null, "saved-claim");
        section.append(element("strong", claim.text), element("p", [claim.verdict, claim.reason].filter(Boolean).join(" · ")));
        for (const source of claim.evidence || []) section.append(sourceCard(source));
        details.append(section);
      }
      node.append(details);
    }
  }
}
async function refreshSavedChecks() {
  await Promise.all([...citationViews.entries()].map(async ([id, view]) => {
    try {
      const response = await request("../api/freshness-reviews/" + encodeURIComponent(id));
      view.reviews = response.reviews || [];
      view.error = false;
    } catch { view.error = true; }
  }));
  showSavedChecks();
}
function canSaveChecks() {
  return onDevice && imported && !importEdited && citationViews.size > 0 && verifyResult?.mode === "replay";
}
async function saveChecks() {
  if (!canSaveChecks()) return;
  const revision = verifyRevision;
  const btn = byId("save-checks");
  btn.disabled = true;
  feedback("save-status", "Checking the stored claims on this device…");
  try {
    await request("../api/freshness-reviews", {claim_ids: [...citationViews.keys()], target: byId("target").value, as_of: byId("as-of").value || null});
    await refreshSavedChecks();
    if (revision === verifyRevision) feedback("save-status", "Checks saved to the cited claims on this device.");
  } catch (error) {
    if (revision === verifyRevision) feedback("save-status", error.message, true);
  } finally { btn.disabled = false; }
}
function invalidateVerification() {
  verifyRevision++;
  verifyResult = null;
  byId("verify-export").disabled = true;
  byId("verify-meta").textContent = "";
  byId("receipts").replaceChildren(element("p", "Verify this answer to see its claims and sources here.", "empty"));
  byId("verify-trace").replaceChildren();
  feedback("verify-status", "");
  byId("save-checks").hidden = true;
  feedback("save-status", "");
  showSavedChecks();
}
function publicSource(url) {
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol) ? parsed : null;
  } catch { return null; }
}
function sourceCard(source) {
  const card = element("div", null, "source");
  const url = publicSource(source.url);
  const title = source.title || (url && url.hostname) || "Source excerpt";
  if (url) {
    const link = element("a", title + " ↗");
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    card.append(link);
  } else card.append(element("strong", title));
  if (source.excerpt) card.append(element("blockquote", source.excerpt));
  const manifest = publicSource(source.engine_manifest);
  if (manifest) {
    const p = element("p", null, "engine");
    const anchor = element("a", "Tagged package manifest ↗");
    anchor.href = manifest.href;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    p.append(anchor);
    if (source.engine_excerpt) p.append(document.createTextNode(" · " + source.engine_excerpt));
    card.append(p);
  }
  const meta = [source.target, source.published_at && "Published " + source.published_at,
    source.retrieved_at && "Retrieved " + source.retrieved_at].filter(Boolean);
  if (meta.length) card.append(element("small", meta.join(" · ")));
  return card;
}
function traceList(trace) {
  const ol = element("ol");
  for (const entry of trace) {
    const li = element("li");
    if (typeof entry === "object" && entry !== null) {
      const title = entry.action || entry.event || entry.stage || entry.operation;
      if (title) li.append(element("strong", title + " "));
      const statusDetail = [entry.status, entry.query, Number.isInteger(entry.sources) && plural(entry.sources, "source"), Number.isInteger(entry.matched) && (entry.matched + " matched")].filter(Boolean).join(" · ");
      li.append(document.createTextNode(readable(entry.detail ?? entry.message ?? (statusDetail || (title ? "" : entry)))));
      const links = [entry.url, ...(Array.isArray(entry.sources) ? entry.sources : []), ...(Array.isArray(entry.evidence) ? entry.evidence : [])];
      for (const item of new Set(links.map(item => typeof item === "string" ? item : item?.url))) {
        const url = publicSource(item);
        if (!url) continue;
        const source = element("a", url.hostname + url.pathname);
        source.href = url.href;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        li.append(document.createTextNode(" · "), source);
      }
      if (entry.requestId) li.append(document.createTextNode(" · Request " + entry.requestId));
    } else li.textContent = readable(entry);
    ol.append(li);
  }
  return ol;
}
function verdictBadge(value) {
  const name = String(value || "unknown");
  const badge = element("span", name.charAt(0).toUpperCase() + name.slice(1), "verdict");
  if (["supported", "superseded", "contradicted", "passed", "failed"].includes(name)) badge.classList.add(name);
  return badge;
}
function receipt(claim, index) {
  const article = element("article", null, "receipt");
  const head = element("div", null, "receipt-head");
  head.append(element("h3", claim.text), verdictBadge(claim.verdict));
  article.append(head);
  const conciseReason = claim.correction && claim.reason?.endsWith(claim.correction) ? claim.reason.slice(0, -claim.correction.length).trim() : claim.reason;
  if (conciseReason) article.append(element("p", conciseReason, "reason"));
  if (claim.correction) article.append(labeledLine("Correction", claim.correction, "correction"));
  const foot = element("div", null, "receipt-foot");
  const sources = claim.evidence || [];
  if (sources.length) {
    const details = element("details", null, "sources");
    if (index === 0 && sources[0].excerpt) article.append(element("blockquote", sources[0].excerpt));
    details.append(element("summary", plural(sources.length, "source")));
    for (const source of sources) details.append(sourceCard(source));
    foot.append(details);
  } else foot.append(element("span", "No matching source", "score"));
  foot.append(element("span", claim.score == null ? "Support score unavailable" : "Support score " + claim.score + "/100", "score"));
  article.append(foot);
  return article;
}
function showVerification(result) {
  verifyResult = result;
  const claims = result.claims || [];
  byId("verify-meta").textContent = [plural(claims.length, "claim"), result.truncated && "Limited to four claims", result.target, modeNames[result.mode], result.as_of && "As of " + result.as_of].filter(Boolean).join(" · ");
  byId("receipts").replaceChildren(...claims.map(receipt));
  if (!claims.length) byId("receipts").append(element("p", "No claims were extracted. Enter a complete technical statement and try again.", "empty"));
  const tracePanel = byId("verify-trace");
  tracePanel.replaceChildren();
  if (result.trace?.length) {
    const details = element("details", null, "trace-panel");
    details.append(element("summary", "Verification trace"), traceList(result.trace));
    tracePanel.append(details);
  }
  byId("verify-export").disabled = false;
  byId("save-checks").hidden = !canSaveChecks();
}
async function verify() {
  const text = answer.value.trim();
  if (!text || text.length > 6000) {
    feedback("verify-status", "Enter between 1 and 6,000 characters.", true);
    answer.focus();
    return;
  }
  const revision = ++verifyRevision;
  const selected = document.querySelector('[name="mode"]:checked');
  const mode = selected && !selected.disabled && !imported && !needsNewText ? selected.value : "replay";
  const btn = byId("verify-submit");
  btn.disabled = true;
  feedback("verify-status", "Checking claims…");
  try {
    const payload = {text, target: byId("target").value, mode};
    if (byId("as-of").value) payload.as_of = byId("as-of").value;
    const result = await api("verify", payload);
    if (revision !== verifyRevision) return;
    showVerification(result);
    feedback("verify-status", plural(result.claims.length, "claim") + " checked.");
  } catch (error) {
    if (revision === verifyRevision) feedback("verify-status", error.message, true);
  } finally { btn.disabled = false; }
}
function number(value) {
  return Number.isFinite(value) ? new Intl.NumberFormat(undefined, {maximumFractionDigits: 3}).format(value) : "Unreported";
}
function rate(value) { return Number.isFinite(value) ? Math.round(value * 100) + "%" : "—"; }
function cost(value) {
  return Number.isFinite(value) ? new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", maximumFractionDigits: 6}).format(value) : "Unreported";
}
function summaryTable(rows) {
  const wrap = element("div", null, "table-wrap");
  wrap.tabIndex = 0;
  wrap.setAttribute("role", "region");
  wrap.setAttribute("aria-label", "Scrollable agent comparison");
  const table = element("table");
  const header = table.createTHead().insertRow();
  for (const title of ["Agent", "Passed", "Success", "Consistency", "Avg. ms", "Avg. steps", "Avg. calls", "Tokens", "Cost"]) {
    const cell = element("th", title);
    cell.scope = "col";
    header.append(cell);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    const leader = element("th", row.agent);
    leader.scope = "row";
    tr.append(leader);
    for (const value of [row.passed + "/" + row.runs, rate(row.successRate), rate(row.consistencyRate), number(row.avgLatencyMs), number(row.avgSteps), number(row.avgToolCalls), number(row.tokens), cost(row.costUsd)]) {
      tr.insertCell().textContent = value;
    }
  }
  wrap.append(table);
  return wrap;
}
function runDetail(run) {
  const details = element("details", null, "run");
  const summary = element("summary");
  summary.append(verdictBadge(run.success ? "passed" : "failed"), document.createTextNode([run.agent, run.caseId, "Repeat " + run.repeat].join(" · ")));
  const info = element("div", null, "run-info");
  info.append(labeledLine("Task", run.task), labeledLine("Target", run.target), labeledLine("Condition", run.condition),
    labeledLine("Expected", run.expected), labeledLine("Answer", run.answer));
  info.append(element("p", [number(run.latencyMs) + " ms", plural(run.steps, "step"), plural(run.toolCalls, "tool call"),
    "Tokens " + number(run.tokens), "Cost " + cost(run.costUsd)].join(" · ")));
  if (run.error) info.append(labeledLine("Error", run.error));
  if (run.trace?.length) info.append(element("strong", "Trace"), traceList(run.trace));
  details.append(summary, info);
  return details;
}
function filterSelect(label, options) {
  const field = element("label", label);
  const select = element("select");
  options.forEach(([value, name]) => select.add(new Option(name, value)));
  field.append(select);
  return {field, select};
}
function runInspector(runs) {
  const section = element("section", null, "bench-section");
  section.append(element("h3", "Run inspector"));
  const controls = element("div", null, "run-controls");
  const agents = [...new Set(runs.map(run => run.agent))];
  const agent = filterSelect("Agent", [["", "All agents"], ...agents.map(name => [name, name])]);
  const outcome = filterSelect("Outcome", [["", "All outcomes"], ["pass", "Passed"], ["fail", "Failed"]]);
  controls.append(agent.field, outcome.field);
  const list = element("div");
  const pager = element("div", null, "pager");
  let page = 0;
  function refresh() {
    const filtered = runs.filter(run => (!agent.select.value || run.agent === agent.select.value)
      && (!outcome.select.value || run.success === (outcome.select.value === "pass")));
    const start = page * 8;
    list.replaceChildren(...filtered.slice(start, start + 8).map(runDetail));
    pager.replaceChildren(element("span", filtered.length ? (start + 1) + "–" + Math.min(start + 8, filtered.length) + " of " + plural(filtered.length, "run") : "No runs match these filters."));
    if (filtered.length <= 8) return;
    for (const [label, delta, disabled] of [["Previous", -1, page === 0], ["Next", 1, start + 8 >= filtered.length]]) {
      const btn = element("button", label);
      btn.type = "button";
      btn.disabled = disabled;
      btn.onclick = () => {
        page += delta;
        refresh();
        list.querySelector("summary")?.focus();
      };
      pager.append(btn);
    }
  }
  controls.onchange = () => { page = 0; refresh(); };
  refresh();
  section.append(controls, list, pager);
  return section;
}
function showBenchmark(result, recorded = false) {
  benchmarkResult = result;
  const runs = result.runs || [];
  const agents = result.summary || [];
  const stats = element("section", null, "bench-section");
  stats.append(element("h3", "Agent comparison"), summaryTable(agents));
  const provenance = recorded ? ["Recorded local model run", result.provenance?.model, result.provenance?.finishedAt] : ["Current run"];
  byId("bench-meta").textContent = [...provenance, plural(agents.length, "agent"), plural(result.caseCount, "case"), plural(runs.length, "run")].filter(Boolean).join(" · ");
  const results = byId("bench-results");
  results.replaceChildren(stats, runInspector(runs));
  if (result.protocol) {
    const details = element("details", null, "trace-panel");
    details.append(element("summary", "Benchmark protocol"));
    if (typeof result.protocol === "object") {
      for (const [key, value] of Object.entries(result.protocol)) details.append(labeledLine(key.replace(/([a-z])([A-Z])/g, "$1 $2"), value, "reason"));
    } else details.append(element("p", result.protocol, "reason"));
    results.append(details);
  }
  byId("bench-export").disabled = false;
}
async function benchmark(event, recorded = false) {
  event.preventDefault();
  const btn = byId("bench-submit");
  btn.disabled = true;
  byId("load-recorded").disabled = true;
  byId("repeats").disabled = true;
  feedback("bench-status", recorded ? "Loading recorded run…" : "Running benchmark…");
  try {
    const result = recorded ? await api("recorded-benchmark") : await api("benchmark", {repeats: Number(byId("repeats").value)});
    showBenchmark(result, recorded);
    feedback("bench-status", recorded ? "Recorded local model run loaded." : plural(result.runs.length, "run") + " completed.");
  } catch (error) { feedback("bench-status", error.message, true); }
  finally { btn.disabled = false; byId("load-recorded").disabled = false; byId("repeats").disabled = false; }
}
loadImport();
route();
updateMode();
if (onDevice) byId("back-link").hidden = false;
window.addEventListener("hashchange", route);
document.querySelector(".skip").onclick = event => { event.preventDefault(); byId("main").focus(); };
answer.oninput = () => {
  if (imported) importEdited = true;
  if (needsNewText && answer.value.trim()) needsNewText = false;
  updateMode();
  invalidateVerification();
};
byId("target").onchange = () => { updateMode(); invalidateVerification(); };
byId("as-of").oninput = invalidateVerification;
for (const control of document.querySelectorAll('[name="mode"]')) control.onchange = () => { updateMode(); invalidateVerification(); };
byId("verify-form").onsubmit = event => { event.preventDefault(); verify(); };
byId("bench-form").onsubmit = benchmark;
byId("load-recorded").onclick = event => benchmark(event, true);
byId("use-example").onclick = () => {
  answer.value = example;
  needsNewText = false;
  updateMode();
  invalidateVerification();
  answer.focus();
};
byId("clear-import").onclick = () => {
  try { sessionStorage.removeItem(importKey); } catch { /* This tab can still clear its in-memory copy. */ }
  imported = false;
  citationViews.clear();
  needsNewText = true;
  answer.value = "";
  byId("citations").replaceChildren();
  byId("import-panel").hidden = true;
  byId("use-example").hidden = false;
  invalidateVerification();
  updateMode();
  answer.focus();
};
byId("verify-export").onclick = () => download(verifyResult, "quorum-evidence.json");
byId("save-checks").onclick = saveChecks;
byId("bench-export").onclick = () => download(benchmarkResult, "quorum-benchmark.json");
api("status").then(status => {
  liveAvailable = Boolean(status.live_available);
  modelAvailable = Boolean(status.bifrost_available);
  const endpoints = [status.bifrost_available && "Bifrost", status.external_agent_available && "HTTP agent"].filter(Boolean);
  byId("bifrost").textContent = endpoints.length ? "Configured endpoints receive the public benchmark tasks and excerpts: " + endpoints.join(", ") + "." : "Two local agents run without credentials.";
  updateMode();
}).catch(() => { byId("mode-hint").textContent = "Server status unavailable. Live search is disabled."; });
if (!imported && location.hash !== "#benchmark") verify();
