// The seam between Person A's app code and Person B's real SigNoz/OTel package.
// Person A codes against this interface everywhere. Person B's real implementation
// gets registered once via setTelemetry() at app startup — no call-site changes needed
// when the real package lands. See docs/plan/PERSON_B_SIGNOZ_AND_FITNESS.md section 3/4
// for the exact span names and attributes this is standing in for.

export interface SpanAttributes {
  "factory.run_id"?: string;
  "candidate.id"?: string;
  "demo.scenario"?: string;
  "provider.name"?: "catalog" | "pricing" | "availability";
  "provider.version"?: string;
  "provider.status"?: "ok" | "error";
  [key: string]: string | number | boolean | undefined;
}

export interface Telemetry {
  withSpan<T>(name: string, attributes: SpanAttributes, fn: () => Promise<T>): Promise<T>;
  recordLog(fields: {
    severity: "info" | "warn" | "error";
    message: string;
    factoryRunId?: string;
    candidateId?: string;
    scenario?: string;
    stage?: string;
    provider?: string;
  }): void;
}

// Default: console-based, so the app is fully runnable and legible in a terminal before
// Person B's real package exists. Never gets used once setTelemetry() is called with the
// real implementation.
const consoleTelemetry: Telemetry = {
  async withSpan(name, attributes, fn) {
    const start = Date.now();
    try {
      const result = await fn();
      console.log(`[span] ${name} ok ${Date.now() - start}ms`, attributes);
      return result;
    } catch (err) {
      console.error(`[span] ${name} error ${Date.now() - start}ms`, attributes, err);
      throw err;
    }
  },
  recordLog(fields) {
    const line = `[${fields.severity}] ${fields.message}`;
    if (fields.severity === "error") console.error(line, fields);
    else console.log(line, fields);
  },
};

let current: Telemetry = consoleTelemetry;

export function setTelemetry(impl: Telemetry) {
  current = impl;
}

export function getTelemetry(): Telemetry {
  return current;
}
