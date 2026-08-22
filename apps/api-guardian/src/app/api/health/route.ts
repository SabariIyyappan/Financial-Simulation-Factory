import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PROVIDERS_URL = process.env.MOCK_PROVIDERS_URL ?? "http://localhost:4001";

export async function GET() {
  try {
    const res = await fetch(`${PROVIDERS_URL}/health`, { cache: "no-store" });
    const providers = await res.json();
    return NextResponse.json({ ok: true, providers });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: `mock-providers unreachable at ${PROVIDERS_URL}: ${String(err)}` },
      { status: 503 }
    );
  }
}
