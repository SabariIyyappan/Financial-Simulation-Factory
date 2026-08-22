import { NextRequest, NextResponse } from "next/server";
import type { DemoScenario } from "@api-guardian/domain-contracts";
import { buildProductSnapshot } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const productId = params.get("productId") ?? "sku-123";

  // Run identity comes from Person C's orchestration (Contract A). Defaults keep the
  // endpoint usable standalone during development.
  const ctx = {
    factoryRunId: params.get("factoryRunId") ?? "RUN-LOCAL",
    candidateId: params.get("candidateId") ?? "CANDIDATE-LOCAL",
    scenario: (params.get("scenario") ?? "baseline-v1") as DemoScenario,
  };

  const startedAt = Date.now();
  const outcome = await buildProductSnapshot(productId, ctx);
  const durationMs = Date.now() - startedAt;

  if (!outcome.ok) {
    return NextResponse.json(
      { ok: false, failure: outcome.failure, durationMs, context: ctx },
      { status: 502 }
    );
  }

  return NextResponse.json({ ok: true, snapshot: outcome.snapshot, durationMs, context: ctx });
}
