import {
  type CatalogV1Payload,
  ProviderSchemaError,
  ProviderUnavailableError,
} from "@api-guardian/domain-contracts";

export interface CatalogResult {
  productId: string;
  name: string;
  category: string;
  description: string;
  providerVersion: string;
}

export function normalizeCatalog(payload: unknown): CatalogResult {
  const p = payload as Partial<CatalogV1Payload>;
  if (
    typeof p?.product_id !== "string" ||
    typeof p?.name !== "string" ||
    typeof p?.category !== "string" ||
    typeof p?.description !== "string"
  ) {
    throw new ProviderSchemaError(
      "catalog",
      "v1",
      String(p?.api_version ?? "unknown"),
      "Catalog payload missing one or more required fields (product_id, name, category, description)"
    );
  }
  return {
    productId: p.product_id,
    name: p.name,
    category: p.category,
    description: p.description,
    providerVersion: p.api_version ?? "v1",
  };
}

export async function fetchCatalog(baseUrl: string, productId: string): Promise<CatalogResult> {
  let res: Response;
  try {
    res = await fetch(`${baseUrl}/catalog/${encodeURIComponent(productId)}`);
  } catch (err) {
    throw new ProviderUnavailableError("catalog", `Catalog request failed: ${String(err)}`);
  }
  if (!res.ok) {
    throw new ProviderUnavailableError("catalog", `Catalog returned HTTP ${res.status}`);
  }
  return normalizeCatalog(await res.json());
}
