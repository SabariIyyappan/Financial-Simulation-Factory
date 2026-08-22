import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { PricingMode } from "@api-guardian/domain-contracts";
import { PRODUCTS, PROVIDER_DELAYS, delay } from "./data.ts";

const PORT = Number(process.env.MOCK_PROVIDERS_PORT ?? 4001);

// The single piece of mutable state in this service: which Pricing schema is live.
// Flipping this IS the "external provider made a breaking change" event that the whole
// second half of the demo hangs on. Controlled via POST /control/pricing-mode so the
// demo never requires editing code or restarting anything.
let pricingMode: PricingMode = "v1";

function json(res: ServerResponse, status: number, body: unknown) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  if (chunks.length === 0) return null;
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf-8"));
  } catch {
    return null;
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://localhost:${PORT}`);
  const path = url.pathname;

  if (path === "/health") {
    return json(res, 200, { status: "ok", pricingMode });
  }

  // --- Demo control plane ---

  if (path === "/control/pricing-mode" && req.method === "GET") {
    return json(res, 200, { pricingMode });
  }

  if (path === "/control/pricing-mode" && req.method === "POST") {
    const body = (await readBody(req)) as { mode?: string } | null;
    if (body?.mode !== "v1" && body?.mode !== "v2") {
      return json(res, 400, { error: "mode must be 'v1' or 'v2'" });
    }
    pricingMode = body.mode;
    console.log(`[control] pricing mode -> ${pricingMode}`);
    return json(res, 200, { pricingMode });
  }

  if (path === "/control/reset" && req.method === "POST") {
    pricingMode = "v1";
    console.log("[control] reset -> pricing mode v1");
    return json(res, 200, { pricingMode });
  }

  // --- Provider endpoints ---

  const catalogMatch = path.match(/^\/catalog\/(.+)$/);
  if (catalogMatch) {
    const product = PRODUCTS[decodeURIComponent(catalogMatch[1])];
    await delay(PROVIDER_DELAYS.catalog);
    if (!product) return json(res, 404, { error: "product not found" });
    return json(res, 200, {
      product_id: product.productId,
      name: product.name,
      category: product.category,
      description: product.description,
      api_version: "v1",
    });
  }

  const pricingMatch = path.match(/^\/pricing\/(.+)$/);
  if (pricingMatch) {
    const product = PRODUCTS[decodeURIComponent(pricingMatch[1])];
    await delay(PROVIDER_DELAYS.pricing);
    if (!product) return json(res, 404, { error: "product not found" });
    if (pricingMode === "v2") {
      return json(res, 200, {
        product_id: product.productId,
        pricing: { amount: product.price, currency: product.currency },
        api_version: "v2",
      });
    }
    return json(res, 200, {
      product_id: product.productId,
      price: product.price,
      currency: product.currency,
      api_version: "v1",
    });
  }

  const availabilityMatch = path.match(/^\/availability\/(.+)$/);
  if (availabilityMatch) {
    const product = PRODUCTS[decodeURIComponent(availabilityMatch[1])];
    await delay(PROVIDER_DELAYS.availability);
    if (!product) return json(res, 404, { error: "product not found" });
    return json(res, 200, {
      product_id: product.productId,
      in_stock: product.inStock,
      quantity: product.quantity,
      estimated_ship_days: product.estimatedShipDays,
      api_version: "v1",
    });
  }

  return json(res, 404, { error: "not found" });
});

server.listen(PORT, () => {
  console.log(`mock-providers listening on http://localhost:${PORT}`);
  console.log(`  catalog      ~${PROVIDER_DELAYS.catalog}ms`);
  console.log(`  pricing      ~${PROVIDER_DELAYS.pricing}ms  (mode: ${pricingMode})`);
  console.log(`  availability ~${PROVIDER_DELAYS.availability}ms`);
});
