// Frozen in Phase A0 (see docs/plan/MASTER_PLAN.md section 7, Contract A/B).
// Changing shapes here is a cross-team contract change — don't do it casually.

export type DemoScenario =
  | "baseline-v1"
  | "optimized-v1"
  | "pricing-v2-break"
  | "pricing-v2-repaired";

export type PricingMode = "v1" | "v2";

export interface RunContext {
  factoryRunId: string;
  candidateId: string;
  scenario: DemoScenario;
}

// --- Raw provider payload shapes (what the mock services actually return) ---

export interface CatalogV1Payload {
  product_id: string;
  name: string;
  category: string;
  description: string;
  api_version: "v1";
}

export interface PricingV1Payload {
  product_id: string;
  price: number;
  currency: string;
  api_version: "v1";
}

export interface PricingV2Payload {
  product_id: string;
  pricing: { amount: number; currency: string };
  api_version: "v2";
}

export type PricingPayload = PricingV1Payload | PricingV2Payload;

export interface AvailabilityV1Payload {
  product_id: string;
  in_stock: boolean;
  quantity: number;
  estimated_ship_days: number;
  api_version: "v1";
}

// --- Normalized application-facing shape ---

export interface ProductSnapshot {
  productId: string;
  name: string;
  category: string;
  description: string;
  price: { amount: number; currency: string };
  inStock: boolean;
  quantity: number;
  estimatedShipDays: number;
  providerVersions: { catalog: string; pricing: string; availability: string };
  generatedAt: string;
}

// --- Errors: must be typed and clearly diagnosable, never a silent bad value ---

export class ProviderSchemaError extends Error {
  constructor(
    public readonly provider: "catalog" | "pricing" | "availability",
    public readonly expectedVersion: string,
    public readonly receivedVersion: string,
    message: string
  ) {
    super(message);
    this.name = "ProviderSchemaError";
  }
}

export class ProviderUnavailableError extends Error {
  constructor(public readonly provider: "catalog" | "pricing" | "availability", message: string) {
    super(message);
    this.name = "ProviderUnavailableError";
  }
}
