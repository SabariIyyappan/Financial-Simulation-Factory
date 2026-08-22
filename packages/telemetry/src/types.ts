export type FactoryContext = {
  factoryRunId: string;
  candidateId: string;
  scenario: string;
  releaseVersion?: string;
};

export type ProviderName = "catalog" | "pricing" | "availability";

export const SPAN_NAMES = {
  productSnapshot: "api_guardian.product_snapshot",
  catalog: "provider.catalog",
  pricing: "provider.pricing",
  availability: "provider.availability",
} as const;

export const ATTR = {
  factoryRunId: "factory.run_id",
  candidateId: "candidate.id",
  demoScenario: "demo.scenario",
  releaseVersion: "release.version",
  providerName: "provider.name",
  providerVersion: "provider.version",
  providerStatus: "provider.status",
} as const;
