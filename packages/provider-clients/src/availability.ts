import {
  type AvailabilityV1Payload,
  ProviderSchemaError,
  ProviderUnavailableError,
} from "@api-guardian/domain-contracts";

export interface AvailabilityResult {
  productId: string;
  inStock: boolean;
  quantity: number;
  estimatedShipDays: number;
  providerVersion: string;
}

export function normalizeAvailability(payload: unknown): AvailabilityResult {
  const p = payload as Partial<AvailabilityV1Payload>;
  if (
    typeof p?.product_id !== "string" ||
    typeof p?.in_stock !== "boolean" ||
    typeof p?.quantity !== "number" ||
    typeof p?.estimated_ship_days !== "number"
  ) {
    throw new ProviderSchemaError(
      "availability",
      "v1",
      String(p?.api_version ?? "unknown"),
      "Availability payload missing one or more required fields (product_id, in_stock, quantity, estimated_ship_days)"
    );
  }
  return {
    productId: p.product_id,
    inStock: p.in_stock,
    quantity: p.quantity,
    estimatedShipDays: p.estimated_ship_days,
    providerVersion: p.api_version ?? "v1",
  };
}

export async function fetchAvailability(
  baseUrl: string,
  productId: string
): Promise<AvailabilityResult> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl}/availability/${encodeURIComponent(productId)}`);
  } catch (err) {
    throw new ProviderUnavailableError("availability", `Availability request failed: ${String(err)}`);
  }
  if (!res.ok) {
    throw new ProviderUnavailableError("availability", `Availability returned HTTP ${res.status}`);
  }
  return normalizeAvailability(await res.json());
}
