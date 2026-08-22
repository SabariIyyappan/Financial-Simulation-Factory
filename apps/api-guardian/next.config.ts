import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The workspace packages ship raw TypeScript (no build step) so the repair surface
  // stays readable and editable by the coding agent during the demo.
  // Only our raw-TypeScript packages need transpiling. @api-guardian/telemetry is a
  // built ESM package (dist/) with its own exports map, so it resolves normally.
  transpilePackages: ["@api-guardian/domain-contracts", "@api-guardian/provider-clients"],

  // The OTel SDK does filesystem/async-hooks work that must not be bundled into the
  // server build.
  serverExternalPackages: ["@api-guardian/telemetry"],
};

export default nextConfig;
