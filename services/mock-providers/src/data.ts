// Fixed catalogue. Same input always yields the same output in the same mode —
// no randomness anywhere in this service (CLAUDE.md rule 5).

export interface ProductFixture {
  productId: string;
  name: string;
  category: string;
  description: string;
  price: number;
  currency: string;
  inStock: boolean;
  quantity: number;
  estimatedShipDays: number;
}

export const PRODUCTS: Record<string, ProductFixture> = {
  "sku-123": {
    productId: "sku-123",
    name: "Zero Downtime Router",
    category: "networking",
    description: "Eight-port managed router with redundant failover.",
    price: 129.99,
    currency: "USD",
    inStock: true,
    quantity: 42,
    estimatedShipDays: 2,
  },
  "sku-456": {
    productId: "sku-456",
    name: "Observability Rack Kit",
    category: "infrastructure",
    description: "Rack-mount kit with pre-wired telemetry taps.",
    price: 549.0,
    currency: "USD",
    inStock: true,
    quantity: 7,
    estimatedShipDays: 5,
  },
  "sku-789": {
    productId: "sku-789",
    name: "Edge Cache Node",
    category: "compute",
    description: "Low-power edge node for regional caching.",
    price: 899.5,
    currency: "USD",
    inStock: false,
    quantity: 0,
    estimatedShipDays: 21,
  },
};

// Fixed artificial latencies, frozen in Phase A0. These create the sequential-vs-parallel
// gap the first AVO-lite repair closes: ~2.7s serialized vs ~1.1s parallel.
export const PROVIDER_DELAYS = {
  catalog: 700,
  pricing: 900,
  availability: 1100,
} as const;

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
