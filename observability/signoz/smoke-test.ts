import {
  initTelemetry,
  shutdownTelemetry,
  withProductSnapshot,
  withProviderCall,
  type FactoryContext,
} from "@api-guardian/telemetry";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function runSequentialBaseline(ctx: FactoryContext): Promise<void> {
  await withProductSnapshot(ctx, async () => {
    await withProviderCall(ctx, "catalog", { version: "v1" }, () => sleep(700));
    await withProviderCall(ctx, "pricing", { version: "v1" }, () => sleep(900));
    await withProviderCall(ctx, "availability", { version: "v1" }, () => sleep(1100));
  });
}

async function main(): Promise<void> {
  initTelemetry();

  const ctx: FactoryContext = {
    factoryRunId: "RUN-SMOKE",
    candidateId: "BASELINE",
    scenario: "baseline-v1",
    releaseVersion: "v0-baseline",
  };

  console.log("Emitting sequential Product Snapshot smoke trace...");
  await runSequentialBaseline(ctx);

  // Allow OTLP export batch to flush
  await sleep(6_000);
  await shutdownTelemetry();

  console.log("Done. Open SigNoz → Traces → service.name = api-guardian");
  console.log("Expected: api_guardian.product_snapshot with 3 sequential child spans (~2.7s total)");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
