import {
  type ProductSnapshot,
  type RunContext,
  ProviderSchemaError,
  ProviderUnavailableError,
} from "@api-guardian/domain-contracts";
import { fetchCatalog, fetchPricing, fetchAvailability } from "@api-guardian/provider-clients";
import { getTelemetry } from "@api-guardian/telemetry-interface";

const PROVIDERS_URL = process.env.MOCK_PROVIDERS_URL ?? "http://localhost:4001";

export interface SnapshotFailure {
  provider: "catalog" | "pricing" | "availability" | "unknown";
  errorType: string;
  message: string;
}

export type SnapshotOutcome =
  | { ok: true; snapshot: ProductSnapshot }
  | { ok: false; failure: SnapshotFailure };

function describeError(err: unknown): SnapshotFailure {
  if (err instanceof ProviderSchemaError) {
    return { provider: err.provider, errorType: "ProviderSchemaError", message: err.message };
  }
  if (err instanceof ProviderUnavailableError) {
    return { provider: err.provider, errorType: "ProviderUnavailableError", message: err.message };
  }
  return { provider: "unknown", errorType: "UnknownError", message: String(err) };
}

// AVO-LITE REPAIR SURFACE #1.
//
// Catalog, Pricing, and Availability are independent — nothing here needs the previous
// result — yet they run one after another, costing ~2.7s instead of ~1.1s. This is
// deliberate and must NOT be pre-optimized (CLAUDE.md rule 3). The factory's first
// candidate change is to parallelize these three calls, and SigNoz's p95 measurement is
// what proves the improvement objectively.
export async function buildProductSnapshot(
  productId: string,
  ctx: RunContext
): Promise<SnapshotOutcome> {
  const telemetry = getTelemetry();

  const baseAttrs = {
    "factory.run_id": ctx.factoryRunId,
    "candidate.id": ctx.candidateId,
    "demo.scenario": ctx.scenario,
  };

  return telemetry.withSpan("api_guardian.product_snapshot", baseAttrs, async () => {
    try {
      const catalog = await telemetry.withSpan(
        "provider.catalog",
        { ...baseAttrs, "provider.name": "catalog" },
        () => fetchCatalog(PROVIDERS_URL, productId)
      );

      const pricing = await telemetry.withSpan(
        "provider.pricing",
        { ...baseAttrs, "provider.name": "pricing" },
        () => fetchPricing(PROVIDERS_URL, productId)
      );

      const availability = await telemetry.withSpan(
        "provider.availability",
        { ...baseAttrs, "provider.name": "availability" },
        () => fetchAvailability(PROVIDERS_URL, productId)
      );

      const snapshot: ProductSnapshot = {
        productId: catalog.productId,
        name: catalog.name,
        category: catalog.category,
        description: catalog.description,
        price: { amount: pricing.amount, currency: pricing.currency },
        inStock: availability.inStock,
        quantity: availability.quantity,
        estimatedShipDays: availability.estimatedShipDays,
        providerVersions: {
          catalog: catalog.providerVersion,
          pricing: pricing.providerVersion,
          availability: availability.providerVersion,
        },
        generatedAt: new Date().toISOString(),
      };

      if (!validateSnapshot(snapshot)) {
        const failure: SnapshotFailure = {
          provider: "unknown",
          errorType: "SnapshotValidationError",
          message: "Assembled snapshot failed normalized schema validation",
        };
        telemetry.recordLog({
          severity: "error",
          message: failure.message,
          factoryRunId: ctx.factoryRunId,
          candidateId: ctx.candidateId,
          scenario: ctx.scenario,
          stage: "validate",
        });
        return { ok: false, failure };
      }

      return { ok: true, snapshot };
    } catch (err) {
      const failure = describeError(err);
      telemetry.recordLog({
        severity: "error",
        message: failure.message,
        factoryRunId: ctx.factoryRunId,
        candidateId: ctx.candidateId,
        scenario: ctx.scenario,
        stage: "provider_call",
        provider: failure.provider,
      });
      return { ok: false, failure };
    }
  });
}

export function validateSnapshot(snapshot: ProductSnapshot): boolean {
  return (
    typeof snapshot.productId === "string" &&
    snapshot.productId.length > 0 &&
    typeof snapshot.name === "string" &&
    typeof snapshot.category === "string" &&
    typeof snapshot.description === "string" &&
    typeof snapshot.price?.amount === "number" &&
    Number.isFinite(snapshot.price.amount) &&
    typeof snapshot.price?.currency === "string" &&
    snapshot.price.currency.length === 3 &&
    typeof snapshot.inStock === "boolean" &&
    typeof snapshot.quantity === "number" &&
    typeof snapshot.estimatedShipDays === "number" &&
    typeof snapshot.generatedAt === "string"
  );
}
