import {
  type PricingV1Payload,
  ProviderSchemaError,
  ProviderUnavailableError,
} from "@api-guardian/domain-contracts";

export interface PricingResult {
  productId: string;
  amount: number;
  currency: string;
  providerVersion: string;
}

// THE REPAIR SURFACE. This adapter currently understands Pricing V1 only.
//
// When the provider flips to V2 (nested pricing.amount / pricing.currency), this MUST
// throw ProviderSchemaError rather than coercing or guessing — a silent wrong price is
// invisible to the factory, and the whole demo depends on the failure being loud,
// typed, and localized to `pricing`. See CLAUDE.md rule 4.
export function normalizePricing(payload: unknown): PricingResult {
  const p = payload as Partial<PricingV1Payload> & { pricing?: unknown };

  if (typeof p?.product_id !== "string") {
    throw new ProviderSchemaError(
      "pricing",
      "v1",
      String(p?.api_version ?? "unknown"),
      "Pricing payload missing product_id"
    );
  }

  if (typeof p.price !== "number" || typeof p.currency !== "string") {
    throw new ProviderSchemaError(
      "pricing",
      "v1",
      String(p?.api_version ?? "unknown"),
      `Pricing adapter expected root-level 'price' (number) and 'currency' (string), got neither. Received keys: ${Object.keys(p ?? {}).join(", ")}`
    );
  }

  return {
    productId: p.product_id,
    amount: p.price,
    currency: p.currency,
    providerVersion: p.api_version ?? "v1",
  };
}

export async function fetchPricing(baseUrl: string, productId: string): Promise<PricingResult> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl}/pricing/${encodeURIComponent(productId)}`);
  } catch (err) {
    throw new ProviderUnavailableError("pricing", `Pricing request failed: ${String(err)}`);
  }
  if (!res.ok) {
    throw new ProviderUnavailableError("pricing", `Pricing returned HTTP ${res.status}`);
  }
  return normalizePricing(await res.json());
}
