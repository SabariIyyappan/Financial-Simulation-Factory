// Next.js runs this once at server startup. Boots Person B's OTel SDK so every span
// opened by withProductSnapshot / withProviderCall actually exports to SigNoz.
// https://nextjs.org/docs/app/guides/open-telemetry

export async function register() {
  // The OTel Node SDK needs real Node APIs — skip it on the edge runtime.
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const { initTelemetry } = await import("@api-guardian/telemetry");
  initTelemetry(process.env.OTEL_SERVICE_NAME ?? "api-guardian");
  console.log("[telemetry] OTel SDK initialised, exporting to", process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://localhost:4318");
}
