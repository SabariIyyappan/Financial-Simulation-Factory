import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { ProviderSchemaError } from "@api-guardian/domain-contracts";
import { normalizePricing } from "./pricing.ts";

describe("normalizePricing", () => {
  test("normalizes a valid V1 payload", () => {
    const result = normalizePricing({
      product_id: "sku-123",
      price: 129.99,
      currency: "USD",
      api_version: "v1",
    });
    assert.deepEqual(result, {
      productId: "sku-123",
      amount: 129.99,
      currency: "USD",
      providerVersion: "v1",
    });
  });

  // This is the failure the second AVO-lite repair exists to fix. If this test ever
  // starts passing without a code change, the adapter silently coerced V2 — which would
  // hide the incident from the factory entirely.
  test("throws ProviderSchemaError on a V2 nested payload", () => {
    assert.throws(
      () =>
        normalizePricing({
          product_id: "sku-123",
          pricing: { amount: 129.99, currency: "USD" },
          api_version: "v2",
        }),
      (err: unknown) => {
        assert.ok(err instanceof ProviderSchemaError);
        assert.equal(err.provider, "pricing");
        assert.equal(err.receivedVersion, "v2");
        return true;
      }
    );
  });

  test("throws on a payload missing product_id", () => {
    assert.throws(
      () => normalizePricing({ price: 10, currency: "USD" }),
      ProviderSchemaError
    );
  });

  test("throws on a payload with a string price instead of a number", () => {
    assert.throws(
      () => normalizePricing({ product_id: "sku-123", price: "129.99", currency: "USD" }),
      ProviderSchemaError
    );
  });
});
