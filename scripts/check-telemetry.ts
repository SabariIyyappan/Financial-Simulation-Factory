#!/usr/bin/env tsx
// Proves this machine can reach a SigNoz OTLP collector — Person B's, or any other —
// before you spend time wondering why traces aren't showing up.
//
//   tsx scripts/check-telemetry.ts                        # uses OTEL_EXPORTER_OTLP_ENDPOINT
//   tsx scripts/check-telemetry.ts http://192.168.1.42:4318
//
// Sends one real span. If it succeeds, look for service `api-guardian-connectivity-check`
// in SigNoz — that is end-to-end proof, not just an open port.

const endpointArg = process.argv[2];
const base = (
  endpointArg ??
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT ??
  "http://localhost:4318"
).replace(/\/$/, "");
const url = base.endsWith("/v1/traces") ? base : `${base}/v1/traces`;

const now = Date.now();
const nanos = (ms: number) => String(ms * 1_000_000);

// 16-byte trace id / 8-byte span id, hex encoded, per the OTLP JSON encoding.
const traceId = [...crypto.getRandomValues(new Uint8Array(16))]
  .map((b) => b.toString(16).padStart(2, "0"))
  .join("");
const spanId = [...crypto.getRandomValues(new Uint8Array(8))]
  .map((b) => b.toString(16).padStart(2, "0"))
  .join("");

const payload = {
  resourceSpans: [
    {
      resource: {
        attributes: [
          { key: "service.name", value: { stringValue: "api-guardian-connectivity-check" } },
        ],
      },
      scopeSpans: [
        {
          scope: { name: "check-telemetry" },
          spans: [
            {
              traceId,
              spanId,
              name: "connectivity.check",
              kind: 1,
              startTimeUnixNano: nanos(now),
              endTimeUnixNano: nanos(now + 1),
              attributes: [
                { key: "check.source", value: { stringValue: "person-a" } },
                { key: "check.host", value: { stringValue: process.env.COMPUTERNAME ?? "unknown" } },
              ],
              status: { code: 1 },
            },
          ],
        },
      ],
    },
  ],
};

console.log(`POST ${url}`);

const controller = new AbortController();
// Without a timeout an unreachable host hangs on TCP retries for over a minute, which
// looks identical to "still working" — fail fast instead.
const timeout = setTimeout(() => controller.abort(), 8000);

try {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: controller.signal,
  });
  clearTimeout(timeout);

  const body = await res.text();
  if (res.ok) {
    console.log(`\n  reachable — HTTP ${res.status}`);
    console.log(`  response: ${body || "(empty)"}`);
    console.log(`\n  trace id: ${traceId}`);
    console.log(`  Look for service "api-guardian-connectivity-check" in SigNoz.`);
    console.log(`  If it appears there, this machine can ship traces to that collector.`);
  } else {
    console.log(`\n  endpoint answered but rejected the payload — HTTP ${res.status}`);
    console.log(`  response: ${body}`);
    console.log(`  The collector is reachable; the payload or its config is the problem.`);
    process.exit(1);
  }
} catch (err) {
  clearTimeout(timeout);
  const aborted = err instanceof Error && err.name === "AbortError";
  console.error(`\n  NOT reachable — ${aborted ? "timed out after 8s" : String(err)}`);
  console.error(`\n  Things to check, in order:`);
  console.error(`   1. Is SigNoz actually up on that host?  npm run signoz:up`);
  console.error(`   2. Right IP? Ask them for their LAN IP (ipconfig / ifconfig), not localhost.`);
  console.error(`   3. Host firewall allowing inbound 4318? Windows blocks it by default.`);
  console.error(`   4. Venue WiFi with client isolation blocks machine-to-machine traffic`);
  console.error(`      entirely — if so, use SigNoz Cloud or a tunnel instead of the LAN.`);
  process.exit(1);
}
