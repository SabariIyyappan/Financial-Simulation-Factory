"use client";

import { useState } from "react";
import type { ProductSnapshot } from "@api-guardian/domain-contracts";

interface SnapshotResponse {
  ok: boolean;
  snapshot?: ProductSnapshot;
  failure?: { provider: string; errorType: string; message: string };
  durationMs: number;
}

export default function Dashboard() {
  const [productId, setProductId] = useState("sku-123");
  const [result, setResult] = useState<SnapshotResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [pricingMode, setPricingMode] = useState<string>("unknown");

  async function runSnapshot() {
    setLoading(true);
    try {
      const res = await fetch(`/api/snapshot?productId=${encodeURIComponent(productId)}`);
      setResult(await res.json());
    } finally {
      setLoading(false);
    }
  }

  async function refreshMode() {
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      setPricingMode(data.providers?.pricingMode ?? "unreachable");
    } catch {
      setPricingMode("unreachable");
    }
  }

  const providerStatus = (name: "catalog" | "pricing" | "availability") => {
    if (!result) return { cls: "idle", label: "not run" };
    if (result.ok) return { cls: "ok", label: "healthy" };
    if (result.failure?.provider === name) return { cls: "err", label: "failing" };
    return { cls: "idle", label: "not reached" };
  };

  return (
    <div className="wrap">
      <div className="eyebrow">API Guardian</div>
      <h1>Product Snapshot</h1>
      <p className="sub">
        Composes one normalized snapshot from three independent third-party providers.
        The factory watches this operation and repairs it when it degrades or breaks.
      </p>

      <div className="grid">
        {(["catalog", "pricing", "availability"] as const).map((name) => {
          const s = providerStatus(name);
          return (
            <div className="card" key={name}>
              <h3>{name}</h3>
              <span className={`status ${s.cls}`}>{s.label}</span>
              {name === "pricing" && (
                <div className="hint" style={{ marginTop: 8 }}>
                  schema mode: {pricingMode}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="row">
        <input
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
          placeholder="product id"
          style={{ width: 160 }}
        />
        <button className="primary" onClick={runSnapshot} disabled={loading}>
          {loading ? "Building snapshot…" : "Build Product Snapshot"}
        </button>
        <button onClick={refreshMode}>Check provider mode</button>
      </div>

      {result && (
        <>
          <div className="row">
            <div className="card" style={{ flex: 1 }}>
              <h3>Upstream duration</h3>
              <div className="metric">
                {result.durationMs}
                <small> ms</small>
              </div>
              <div className="hint" style={{ marginTop: 4 }}>
                p95 target for release: 1600 ms
              </div>
            </div>
          </div>

          {result.ok && result.snapshot ? (
            <pre>{JSON.stringify(result.snapshot, null, 2)}</pre>
          ) : (
            <div className="fail-box">
              <strong>Snapshot failed</strong>
              <div style={{ marginTop: 6 }}>
                provider <code>{result.failure?.provider}</code> &middot;{" "}
                <code>{result.failure?.errorType}</code>
              </div>
              <div style={{ marginTop: 6, color: "var(--text-dim)" }}>
                {result.failure?.message}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
