/**
 * Probe OTLP HTTP reachability from another machine (Person A → Person B SigNoz).
 *
 * Usage:
 *   npx tsx scripts/check-telemetry.ts 172.30.30.213:4318
 *   npx tsx scripts/check-telemetry.ts localhost:4318
 */

const raw = process.argv[2] ?? "localhost:4318";
const hostPort = raw.replace(/^https?:\/\//, "");
const url = `http://${hostPort}/v1/traces`;

async function main(): Promise<void> {
  console.log(`Checking OTLP HTTP endpoint: ${url}`);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      signal: AbortSignal.timeout(5000),
    });

    const body = await response.text();

    if (!response.ok) {
      console.error(`FAIL: HTTP ${response.status} ${response.statusText}`);
      console.error(body.slice(0, 200));
      process.exit(1);
    }

    console.log(`OK: reachable (HTTP ${response.status})`);
    console.log(`Response: ${body.slice(0, 120)}`);
    console.log(`Set OTEL_EXPORTER_OTLP_ENDPOINT=http://${hostPort}`);
    process.exit(0);
  } catch (error) {
    console.error("FAIL: not reachable");
    console.error(error instanceof Error ? error.message : error);
    console.error("Check Docker is running, npm run signoz:up, and firewall allows port 4318.");
    process.exit(1);
  }
}

main();
