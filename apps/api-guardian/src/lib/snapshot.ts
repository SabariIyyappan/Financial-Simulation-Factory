import {
  type ProductSnapshot,
  ProviderSchemaError,
  ProviderUnavailableError,
} from "@api-guardian/domain-contracts";
import { fetchCatalog, fetchPricing, fetchAvailability } from "@api-guardian/provider-clients";
import {
  withProductSnapshot,
  withProviderCall,
  logProviderError,
  type FactoryContext,
} from "@api-guardian/telemetry";

const PROVIDERS_URL = process.env.MOCK_PROVIDERS_URL ?? "http://localhost:4001";

export interface SnapshotFailure {
  provider: "catalog" | "pricing" | "availability" | "unknown";
  errorCode: string;
  errorType: string;
  message: string;
}

export type SnapshotOutcome =
  | { ok: true; snapshot: ProductSnapshot }
  | { ok: false; failure: SnapshotFailure };

function describeError(err: unknown): SnapshotFailure {
  if (err instanceof ProviderSchemaError) {
    return {
      provider: err.provider,
      errorCode: "SCHEMA_FIELD_MISSING",
      errorType: "ProviderSchemaError",
      message: err.message,
    };
  }
  if (err instanceof ProviderUnavailableError) {
    return {
      provider: err.provider,
      errorCode: "PROVIDER_UNAVAILABLE",
      errorType: "ProviderUnavailableError",
      message: err.message,
    };
  }
  return {
    provider: "unknown",
    errorCode: "UNKNOWN_ERROR",
    errorType: "UnknownError",
    message: String(err),
  };
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
  ctx: FactoryContext
): Promise<SnapshotOutcome> {
  try {
    const snapshot = await withProductSnapshot(ctx, async () => {
      try {
        const catalog = await withProviderCall(ctx, "catalog", { version: "v1" }, () =>
          fetchCatalog(PROVIDERS_URL, productId)
        );

        const pricing = await withProviderCall(ctx, "pricing", { version: "v1" }, () =>
          fetchPricing(PROVIDERS_URL, productId)
        );

        const availability = await withProviderCall(ctx, "availability", { version: "v1" }, () =>
          fetchAvailability(PROVIDERS_URL, productId)
        );

        const assembled: ProductSnapshot = {
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

        if (!validateSnapshot(assembled)) {
          throw new ProviderSchemaError(
            "pricing",
            "normalized",
            "invalid",
            "Assembled snapshot failed normalized schema validation"
          );
        }

        return assembled;
      } catch (err) {
        // Logged here, not in the outer catch: withProductSnapshot ends its span in a
        // finally block, so by the time the outer catch runs there is no active span for
        // logProviderError to pull trace_id/span_id from. Re-thrown so the wrapper still
        // marks the span errored and increments the error counter.
        const failure = describeError(err);
        logProviderError(ctx, failure.provider, failure.errorCode, failure.message);
        throw err;
      }
    });
    return { ok: true, snapshot };
  } catch (err) {
    return { ok: false, failure: describeError(err) };
  }
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
