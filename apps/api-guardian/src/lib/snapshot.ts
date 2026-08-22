import {
  type ProductSnapshot,
  ProviderSchemaError,
  ProviderUnavailableError,
  SnapshotValidationError,
} from "@api-guardian/domain-contracts";
import { fetchCatalog, fetchPricing, fetchAvailability } from "@api-guardian/provider-clients";
import {
  withProductSnapshot,
  withProviderCall,
  logProviderError,
  type FactoryContext,
  type ProviderName,
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
  if (err instanceof SnapshotValidationError) {
    return {
      provider: "unknown",
      errorCode: "SNAPSHOT_VALIDATION_FAILED",
      errorType: "SnapshotValidationError",
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

// Logs the failure from inside the provider's own span, so the error log carries that
// span's id rather than the root's. That is what lets an operator click a red
// provider.pricing span in SigNoz and land on the exact error — logging in an outer
// catch would attach it to api_guardian.product_snapshot instead, because
// withProviderCall ends its span in a finally block before the error propagates.
async function callProvider<T>(
  ctx: FactoryContext,
  provider: ProviderName,
  version: string,
  fn: () => Promise<T>
): Promise<T> {
  return withProviderCall(ctx, provider, { version }, async () => {
    try {
      return await fn();
    } catch (err) {
      const failure = describeError(err);
      logProviderError(ctx, provider, failure.errorCode, failure.message);
      throw err;
    }
  });
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
      const catalog = await callProvider(ctx, "catalog", "v1", () =>
        fetchCatalog(PROVIDERS_URL, productId)
      );

      const pricing = await callProvider(ctx, "pricing", "v1", () =>
        fetchPricing(PROVIDERS_URL, productId)
      );

      const availability = await callProvider(ctx, "availability", "v1", () =>
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
        const message = "Assembled snapshot failed normalized schema validation";
        // Every provider succeeded, so this genuinely belongs on the root span — there
        // is no provider at fault to attribute it to.
        logProviderError(ctx, "snapshot", "SNAPSHOT_VALIDATION_FAILED", message, "snapshot.validate");
        throw new SnapshotValidationError(message);
      }

      return assembled;
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
