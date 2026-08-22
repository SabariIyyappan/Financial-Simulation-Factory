import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { ProviderSchemaError } from "@api-guardian/domain-contracts";
import { normalizeCatalog } from "./catalog.ts";

describe("normalizeCatalog", () => {
  test("normalizes a valid V1 payload", () => {
    const result = normalizeCatalog({
      product_id: "sku-123",
      name: "Zero Downtime Router",
      category: "networking",
      description: "A router that does not go down.",
      api_version: "v1",
    });
    assert.equal(result.productId, "sku-123");
    assert.equal(result.name, "Zero Downtime Router");
    assert.equal(result.category, "networking");
    assert.equal(result.providerVersion, "v1");
  });

  test("throws when a required field is missing", () => {
    assert.throws(
      () => normalizeCatalog({ product_id: "sku-123", name: "x", category: "y" }),
      ProviderSchemaError
    );
  });
});
