import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { ProviderSchemaError } from "@api-guardian/domain-contracts";
import { normalizeAvailability } from "./availability.ts";

describe("normalizeAvailability", () => {
  test("normalizes a valid V1 payload", () => {
    const result = normalizeAvailability({
      product_id: "sku-123",
      in_stock: true,
      quantity: 42,
      estimated_ship_days: 2,
      api_version: "v1",
    });
    assert.deepEqual(result, {
      productId: "sku-123",
      inStock: true,
      quantity: 42,
      estimatedShipDays: 2,
      providerVersion: "v1",
    });
  });

  test("throws when in_stock is not a boolean", () => {
    assert.throws(
      () =>
        normalizeAvailability({
          product_id: "sku-123",
          in_stock: "yes",
          quantity: 42,
          estimated_ship_days: 2,
        }),
      ProviderSchemaError
    );
  });
});
