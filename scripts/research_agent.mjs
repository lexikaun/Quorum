// Standalone release research agent. No imports from the benchmark harness.
import { createServer } from "node:http";

function version(text) {
  const parts = text.split(".").map(Number);
  return { floor: [...parts, 0, 0].slice(0, 3), precision: parts.length };
}

function compare(a, b) {
  for (let part = 0; part < 3; part++) {
    if (a[part] !== b[part]) return Math.sign(a[part] - b[part]);
  }
  return 0;
}

function runtimeVerdict(requested, constraints) {
  if (typeof constraints !== "string") return "unknown";
  const { floor, precision } = version(requested);
  const ceiling = floor.slice();
  ceiling[precision - 1]++;
  let intersects = false;
  for (const clause of constraints.split("||")) {
    const range = /^(\^|>=)\s*(\d+\.\d+\.\d+)$/.exec(clause.trim());
    if (!range) return "unknown";
    const lower = version(range[2]).floor;
    const upper = range[1] === "^" ? [lower[0] + 1, 0, 0] : null;
    if (compare(floor, lower) >= 0 && (!upper || compare(ceiling, upper) <= 0)) return "supported";
    if (compare(ceiling, lower) > 0 && (!upper || compare(floor, upper) < 0)) intersects = true;
  }
  return intersects ? "unknown" : "contradicted";
}

function research({ task, target, sources }) {
  const reply = (answer, guides = []) => ({ answer, citations: guides.map((guide) => guide.url), tokens: 0, costUsd: 0 });
  const current = sources.find((guide) => guide?.target === target);
  if (!current) return reply("unknown");

  const build = /\bdefault build\.target is '([^']+)'/.exec(task);
  if (build && typeof current.default === "string") {
    return reply(build[1] === current.default ? "supported" : "contradicted", [current]);
  }

  const runtime = /\bNode\.js (\d+(?:\.\d+){0,2})\b/.exec(task);
  if (!runtime) return reply("unknown");
  const verdict = runtimeVerdict(runtime[1], current.engine);
  if (!task.includes("dropped support")) return reply(verdict, [current]);

  const release = /^(.* )([1-9]\d*)$/.exec(target);
  const previous = release && sources.find((guide) => guide?.target === `${release[1]}${Number(release[2]) - 1}`);
  if (!previous) return reply("unknown", [current]);
  const prior = runtimeVerdict(runtime[1], previous.engine);
  if (prior === "unknown" || verdict === "unknown") return reply("unknown", [current, previous]);
  return reply(prior === "supported" && verdict === "contradicted" ? "supported" : "contradicted", [current, previous]);
}

function send(response, status, payload) {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(JSON.stringify(payload));
}

const port = Number(process.argv[2] ?? 18763);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("Choose a valid port.");

createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") return send(response, 200, { ready: true });
  if (request.method !== "POST" || request.url !== "/research") return send(response, 404, { error: "Not found" });
  try {
    const chunks = [];
    let size = 0;
    for await (const chunk of request) {
      size += chunk.length;
      if (size > 64_000) return send(response, 413, { error: "Request too large" });
      chunks.push(chunk);
    }
    const packet = JSON.parse(Buffer.concat(chunks));
    if (typeof packet?.task !== "string" || typeof packet.target !== "string" || !Array.isArray(packet.sources)) {
      return send(response, 400, { error: "Expected a task, target release, and source list" });
    }
    return send(response, 200, research(packet));
  } catch {
    return send(response, 400, { error: "Invalid request" });
  }
}).listen(port, "127.0.0.1", () => console.log(`Research agent listening on 127.0.0.1:${port}`));
