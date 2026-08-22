import {
  initTelemetry,
  shutdownTelemetry,
  withProductSnapshot,
  withProviderCall,
  logProviderError,
  type FactoryContext,
} from "@api-guardian/telemetry";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type ScenarioConfig = {
  name: string;
  ctx: FactoryContext;
  run: (ctx: FactoryContext) => Promise<void>;
  iterations: number;
};

async function sequentialBaseline(ctx: FactoryContext): Promise<void> {
  await withProductSnapshot(ctx, async () => {
    await withProviderCall(ctx, "catalog", { version: "v1" }, () => sleep(700));
    await withProviderCall(ctx, "pricing", { version: "v1" }, () => sleep(900));
    await withProviderCall(ctx, "availability", { version: "v1" }, () => sleep(1100));
  });
}

async function parallelOptimized(ctx: FactoryContext): Promise<void> {
  await withProductSnapshot(ctx, async () => {
    await Promise.all([
      withProviderCall(ctx, "catalog", { version: "v1" }, () => sleep(700)),
      withProviderCall(ctx, "pricing", { version: "v1" }, () => sleep(900)),
      withProviderCall(ctx, "availability", { version: "v1" }, () => sleep(1100)),
    ]);
  });
}

async function pricingV2Break(ctx: FactoryContext): Promise<void> {
  await withProductSnapshot(ctx, async () => {
    await Promise.all([
      withProviderCall(ctx, "catalog", { version: "v1" }, () => sleep(700)),
      withProviderCall(ctx, "availability", { version: "v1" }, () => sleep(1100)),
      withProviderCall(ctx, "pricing", { version: "v2" }, async () => {
        await sleep(900);
        const err = new Error("Expected root field 'price' not found in V2 response");
        logProviderError(ctx, "pricing", "SCHEMA_FIELD_MISSING", err.message);
        throw err;
      }),
    ]);
  }).catch(() => {
    // Expected failure for pricing-v2-break scenario
  });
}

async function pricingV2Repaired(ctx: FactoryContext): Promise<void> {
  await withProductSnapshot(ctx, async () => {
    await Promise.all([
      withProviderCall(ctx, "catalog", { version: "v1" }, () => sleep(700)),
      withProviderCall(ctx, "pricing", { version: "v2" }, () => sleep(900)),
      withProviderCall(ctx, "availability", { version: "v1" }, () => sleep(1100)),
    ]);
  });
}

const scenarios: ScenarioConfig[] = [
  {
    name: "baseline-v1 (sequential, slow)",
    ctx: {
      factoryRunId: "RUN-001",
      candidateId: "BASELINE",
      scenario: "baseline-v1",
      releaseVersion: "v0-baseline",
    },
    run: (ctx) => sequentialBaseline(ctx),
    iterations: 3,
  },
  {
    name: "optimized-v1 (parallel)",
    ctx: {
      factoryRunId: "RUN-002",
      candidateId: "CANDIDATE-PARALLEL",
      scenario: "optimized-v1",
      releaseVersion: "v1-optimized",
    },
    run: (ctx) => parallelOptimized(ctx),
    iterations: 3,
  },
  {
    name: "pricing-v2-break",
    ctx: {
      factoryRunId: "RUN-003",
      candidateId: "BASELINE",
      scenario: "pricing-v2-break",
      releaseVersion: "v1-optimized",
    },
    run: (ctx) => pricingV2Break(ctx),
    iterations: 3,
  },
  {
    name: "pricing-v2-repaired",
    ctx: {
      factoryRunId: "RUN-004",
      candidateId: "CANDIDATE-PRICING-V2",
      scenario: "pricing-v2-repaired",
      releaseVersion: "v2-pricing-compatible",
    },
    run: (ctx) => pricingV2Repaired(ctx),
    iterations: 3,
  },
];

async function main(): Promise<void> {
  initTelemetry();

  for (const scenario of scenarios) {
    console.log(`\n=== ${scenario.name} ===`);
    for (let i = 0; i < scenario.iterations; i++) {
      await scenario.run(scenario.ctx);
      console.log(`  iteration ${i + 1}/${scenario.iterations}`);
    }
  }

  await sleep(8_000);
  await shutdownTelemetry();

  console.log("\nTelemetry emitted for all scenarios.");
  console.log("Run evaluator verification:");
  console.log("  npm run evaluator:start");
  console.log("  curl -X POST http://localhost:8090/evaluate/scenarios");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
