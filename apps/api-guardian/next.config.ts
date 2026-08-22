import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The workspace packages ship raw TypeScript (no build step) so the repair surface
  // stays readable and editable by the coding agent during the demo.
  transpilePackages: [
    "@api-guardian/domain-contracts",
    "@api-guardian/provider-clients",
    "@api-guardian/telemetry-interface",
  ],
};

export default nextConfig;
