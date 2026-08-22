#!/usr/bin/env tsx
// Deterministic demo control. Person C drives the demo from here — no hand-editing JSON,
// no service restarts, no env var changes mid-demo (Person A doc, Phase A8).
//
//   npm run demo:reset          -> pricing back to V1
//   npm run demo:break-pricing  -> pricing flips to V2 (the breaking change)
//   tsx scripts/demo-control.ts status

const PROVIDERS_URL = process.env.MOCK_PROVIDERS_URL ?? "http://localhost:4001";

async function setMode(mode: "v1" | "v2") {
  const res = await fetch(`${PROVIDERS_URL}/control/pricing-mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error(`control failed: HTTP ${res.status}`);
  const data = await res.json();
  console.log(`pricing mode is now: ${data.pricingMode}`);
}

async function status() {
  const res = await fetch(`${PROVIDERS_URL}/health`);
  const data = await res.json();
  console.log(JSON.stringify(data, null, 2));
}

const command = process.argv[2];

try {
  switch (command) {
    case "reset":
      await setMode("v1");
      break;
    case "pricing-v2":
      await setMode("v2");
      break;
    case "status":
      await status();
      break;
    default:
      console.error("usage: demo-control.ts <reset|pricing-v2|status>");
      process.exit(1);
  }
} catch (err) {
  console.error(`error: ${String(err)}`);
  console.error(`is mock-providers running at ${PROVIDERS_URL}? (npm run dev:providers)`);
  process.exit(1);
}
