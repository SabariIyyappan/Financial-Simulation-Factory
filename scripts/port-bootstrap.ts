#!/usr/bin/env tsx
// Creates the six blueprints, the release-readiness scorecard, and seeds the Service +
// three ExternalAPI entities in a Port workspace.
//
//   npm run port:bootstrap
//
// Needs PORT_CLIENT_ID and PORT_CLIENT_SECRET (Port -> Settings -> Credentials).
// Safe to re-run: blueprints that already exist are reported and skipped, entities are
// upserted.

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { PortClient } from "../integrations/port/src/client.ts";

const client = PortClient.fromEnv();
const blueprintDir = path.join(process.cwd(), "port", "blueprints");
const scorecardDir = path.join(process.cwd(), "port", "scorecards");

// Filenames are numbered because relation targets must exist before the blueprint that
// references them.
const files = readdirSync(blueprintDir).filter((f) => f.endsWith(".json")).sort();

console.log(`Creating ${files.length} blueprints...\n`);

for (const file of files) {
  const definition = JSON.parse(readFileSync(path.join(blueprintDir, file), "utf-8"));
  try {
    await client.createBlueprint(definition);
    console.log(`  created  ${definition.identifier}`);
  } catch (err) {
    const message = String(err);
    if (message.includes("409") || message.toLowerCase().includes("already exists")) {
      console.log(`  exists   ${definition.identifier} (skipped)`);
    } else {
      console.error(`  FAILED   ${definition.identifier}`);
      console.error(`           ${message}`);
      process.exitCode = 1;
    }
  }
}

console.log(`\nCreating scorecards...\n`);

for (const file of readdirSync(scorecardDir).filter((f) => f.endsWith(".json"))) {
  const definition = JSON.parse(readFileSync(path.join(scorecardDir, file), "utf-8"));
  try {
    await client.createScorecard(definition.blueprint, definition);
    console.log(`  created  ${definition.identifier} on ${definition.blueprint}`);
  } catch (err) {
    const message = String(err);
    if (message.includes("409") || message.toLowerCase().includes("already exists")) {
      console.log(`  exists   ${definition.identifier} (skipped)`);
    } else {
      console.error(`  FAILED   ${definition.identifier}: ${message}`);
      process.exitCode = 1;
    }
  }
}

console.log(`\nSeeding entities...\n`);

const providers = [
  {
    identifier: "catalog-api",
    title: "Catalog API",
    baseUrl: "http://localhost:4001/catalog",
    currentVersion: "v1",
  },
  {
    identifier: "pricing-api",
    title: "Pricing API",
    baseUrl: "http://localhost:4001/pricing",
    currentVersion: "v1",
  },
  {
    identifier: "availability-api",
    title: "Availability API",
    baseUrl: "http://localhost:4001/availability",
    currentVersion: "v1",
  },
];

for (const p of providers) {
  await client.upsertEntity("externalApi", {
    identifier: p.identifier,
    title: p.title,
    properties: {
      baseUrl: p.baseUrl,
      currentVersion: p.currentVersion,
      provider: "mock-providers (deterministic demo environment)",
      health: "healthy",
    },
  });
  console.log(`  seeded   ${p.identifier}`);
}

await client.upsertEntity("service", {
  identifier: "api-guardian",
  title: "API Guardian",
  properties: {
    repository: "https://github.com/SabariIyyappan/Financial-Simulation-Factory",
    owner: "Zero Downtime Hackathon team",
    health: "healthy",
  },
  relations: { dependsOn: providers.map((p) => p.identifier) },
});
console.log(`  seeded   api-guardian (depends on all three providers)`);

console.log(`\nDone. Open your Port workspace — the catalog should show API Guardian`);
console.log(`and its three external dependencies.`);
