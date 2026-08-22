import type { EvaluationInput, TelemetryEvidence } from "./types.js";
import { spansPresentInTrace } from "./score.js";

export class SigNozQueryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SigNozQueryError";
  }
}

type SigNozSpan = {
  traceID: string;
  spanID: string;
  operationName: string;
  durationNano: number;
  tags?: Array<{ key: string; value: string }>;
  statusCode?: string;
};

type SigNozTrace = {
  traceID: string;
  spans: SigNozSpan[];
};

type RawRow = {
  data?: Record<string, unknown>;
};

type QueryRangeResponse = {
  data?: {
    results?: Array<{
      queryName?: string;
      rows?: RawRow[];
    }>;
    data?: {
      results?: Array<{
        queryName?: string;
        rows?: RawRow[];
      }>;
    };
  };
  status?: string;
  error?: { message?: string };
};

function extractQueryRows(body: QueryRangeResponse): RawRow[] {
  const direct = body.data?.results;
  if (direct) {
    return direct.flatMap((r) => r.rows ?? []);
  }
  const nested = body.data?.data?.results;
  if (nested) {
    return nested.flatMap((r) => r.rows ?? []);
  }
  return [];
}

const ROW_META_KEYS = new Set([
  "trace_id",
  "span_id",
  "name",
  "duration_nano",
  "parent_span_id",
  "timestamp",
  "service.name",
  "status_code",
  "status_message",
  "has_error",
]);

function escFilterValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function tagValue(span: SigNozSpan, key: string): string | undefined {
  return span.tags?.find((t) => t.key === key)?.value;
}

function percentile(values: number[], p: number): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, index)] ?? 0;
}

function rowToSpan(row: Record<string, unknown>): SigNozSpan | null {
  const traceID = row.trace_id ?? row.traceID;
  const spanID = row.span_id ?? row.spanID;
  const name = row.name ?? row.operationName;
  const duration = row.duration_nano ?? row.durationNano;

  if (traceID == null || spanID == null || name == null || duration == null) {
    return null;
  }

  const tags: Array<{ key: string; value: string }> = [];
  for (const [key, value] of Object.entries(row)) {
    if (ROW_META_KEYS.has(key)) continue;
    if (value === null || value === undefined) continue;
    tags.push({ key, value: String(value) });
  }

  const statusRaw = row.status_code ?? row.statusCode;
  let statusCode: string | undefined;
  if (statusRaw === "Error" || statusRaw === 2 || statusRaw === "STATUS_CODE_ERROR") {
    statusCode = "ERROR";
  } else if (row.has_error === true || row.has_error === "true") {
    statusCode = "ERROR";
  }

  return {
    traceID: String(traceID),
    spanID: String(spanID),
    operationName: String(name),
    durationNano: Number(duration),
    statusCode,
    tags,
  };
}

function groupRowsIntoTraces(rows: RawRow[]): SigNozTrace[] {
  const byTrace = new Map<string, SigNozSpan[]>();

  for (const row of rows) {
    if (!row.data) continue;
    const span = rowToSpan(row.data);
    if (!span) continue;
    const list = byTrace.get(span.traceID) ?? [];
    list.push(span);
    byTrace.set(span.traceID, list);
  }

  return [...byTrace.entries()].map(([traceID, spans]) => ({ traceID, spans }));
}

export class SigNozClient {
  constructor(
    private readonly baseUrl = process.env.SIGNOZ_QUERY_URL ?? "http://localhost:8080",
    private readonly serviceName = process.env.OTEL_SERVICE_NAME ?? "api-guardian"
  ) {}

  private headers(): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      "Content-Type": "application/json",
    };
    const apiKey = process.env.SIGNOZ_API_KEY;
    if (apiKey) {
      headers["SIGNOZ-API-KEY"] = apiKey;
    }
    return headers;
  }

  private buildRawQueryPayload(input: EvaluationInput): Record<string, unknown> {
    const startMs = new Date(input.evaluation_window_start).getTime();
    const endMs = new Date(input.evaluation_window_end).getTime();

    // Filter by service only in SigNoz; match factory/candidate/scenario client-side.
    // Composite filters on dotted span attributes are unreliable across SigNoz versions.
    const expression = `service.name = '${escFilterValue(this.serviceName)}'`;

    return {
      start: startMs,
      end: endMs,
      requestType: "raw",
      variables: {},
      compositeQuery: {
        queries: [
          {
            type: "builder_query",
            spec: {
              name: "A",
              signal: "traces",
              filter: { expression },
              selectFields: [
                { name: "trace_id", fieldContext: "span" },
                { name: "span_id", fieldContext: "span" },
                { name: "name", fieldContext: "span" },
                { name: "duration_nano", fieldContext: "span" },
                { name: "parent_span_id", fieldContext: "span" },
                { name: "status_code", fieldContext: "span" },
                { name: "factory.run_id", fieldContext: "span" },
                { name: "candidate.id", fieldContext: "span" },
                { name: "demo.scenario", fieldContext: "span" },
                { name: "provider.name", fieldContext: "span" },
                { name: "provider.status", fieldContext: "span" },
              ],
              order: [{ key: { name: "timestamp", fieldContext: "span" }, direction: "desc" }],
              limit: 500,
              offset: 0,
              disabled: false,
            },
          },
        ],
      },
    };
  }

  private async queryRange(input: EvaluationInput): Promise<RawRow[]> {
    const payload = this.buildRawQueryPayload(input);
    const versions = ["v5", "v4", "v3"];

    for (const version of versions) {
      const url = `${this.baseUrl.replace(/\/$/, "")}/api/${version}/query_range`;
      const response = await fetch(url, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(payload),
      });

      const bodyText = await response.text();
      let body: QueryRangeResponse = {};
      try {
        body = JSON.parse(bodyText) as QueryRangeResponse;
      } catch {
        if (response.ok) {
          throw new SigNozQueryError(
            `SigNoz ${version} query_range returned non-JSON (endpoint may be wrong). First bytes: ${bodyText.slice(0, 80)}`
          );
        }
      }

      if (response.status === 401 || response.status === 403) {
        throw new SigNozQueryError(
          `SigNoz query_range requires authentication. Set SIGNOZ_API_KEY (SigNoz UI → Settings → Service Accounts). HTTP ${response.status}: ${body.error?.message ?? bodyText.slice(0, 120)}`
        );
      }

      if (response.status === 404) {
        continue;
      }

      if (!response.ok) {
        throw new SigNozQueryError(
          `SigNoz ${version} query_range failed: HTTP ${response.status} ${body.error?.message ?? bodyText.slice(0, 200)}`
        );
      }

      const rows = extractQueryRows(body);
      return rows;
    }

    throw new SigNozQueryError(
      "SigNoz query_range not available (tried v5, v4, v3). Check SIGNOZ_QUERY_URL."
    );
  }

  private traceMatchesInput(trace: SigNozTrace, input: EvaluationInput): boolean {
    const root = trace.spans.find((s) => s.operationName === "api_guardian.product_snapshot");
    if (!root) return false;
    // Match run + candidate; scenario label comes from Port input, spans may use demo.scenario.
    return (
      tagValue(root, "factory.run_id") === input.factory_run_id &&
      tagValue(root, "candidate.id") === input.candidate_id
    );
  }

  async fetchTraces(input: EvaluationInput): Promise<SigNozTrace[]> {
    const rows = await this.queryRange(input);
    const traces = groupRowsIntoTraces(rows);
    return traces.filter((trace) => this.traceMatchesInput(trace, input));
  }

  async collectEvidence(input: EvaluationInput): Promise<TelemetryEvidence> {
    const traces = await this.fetchTraces(input);

    if (traces.length === 0) {
      throw new SigNozQueryError(
        `No traces in SigNoz for factory.run_id=${input.factory_run_id}, candidate.id=${input.candidate_id}, demo.scenario=${input.scenario} between ${input.evaluation_window_start} and ${input.evaluation_window_end}.`
      );
    }

    const evidence = this.computeEvidence(traces);

    const rootsFound = traces.some((t) =>
      t.spans.some((s) => s.operationName === "api_guardian.product_snapshot")
    );
    if (!rootsFound) {
      throw new SigNozQueryError(
        `Traces found (${traces.length}) but none contain api_guardian.product_snapshot for the evaluation window.`
      );
    }

    return evidence;
  }

  computeEvidence(traces: SigNozTrace[]): TelemetryEvidence {
    const rootDurations: number[] = [];
    let totalRoots = 0;
    let errorRoots = 0;
    const providerErrors: Record<string, number> = {};
    let adapterExceptions = 0;
    let representativeTraceId: string | null = null;
    let spansPresent = false;
    let correlationPresent = false;

    for (const trace of traces) {
      const spanNames = new Set(trace.spans.map((s) => s.operationName));
      const root = trace.spans.find((s) => s.operationName === "api_guardian.product_snapshot");
      if (!root) continue;

      totalRoots += 1;
      const durationMs = root.durationNano / 1_000_000;
      rootDurations.push(durationMs);

      const hasCorrelation =
        Boolean(tagValue(root, "factory.run_id")) &&
        Boolean(tagValue(root, "candidate.id")) &&
        Boolean(tagValue(root, "demo.scenario"));

      if (hasCorrelation) correlationPresent = true;
      if (spansPresentInTrace(spanNames)) spansPresent = true;

      const rootErrored =
        root.statusCode === "ERROR" ||
        trace.spans.some(
          (s) =>
            s.operationName.startsWith("provider.") &&
            (s.statusCode === "ERROR" || tagValue(s, "provider.status") === "error")
        );

      if (rootErrored) {
        errorRoots += 1;
        if (!representativeTraceId) representativeTraceId = trace.traceID;
      }

      for (const span of trace.spans) {
        if (!span.operationName.startsWith("provider.")) continue;
        const provider = tagValue(span, "provider.name");
        const errored =
          span.statusCode === "ERROR" || tagValue(span, "provider.status") === "error";
        if (errored && provider) {
          providerErrors[provider] = (providerErrors[provider] ?? 0) + 1;
          adapterExceptions += 1;
          if (!representativeTraceId) representativeTraceId = trace.traceID;
        }
      }
    }

    const failedProvider =
      Object.entries(providerErrors).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

    if (!representativeTraceId) {
      const slowest = traces
        .map((t) => {
          const root = t.spans.find((s) => s.operationName === "api_guardian.product_snapshot");
          return root ? { traceID: t.traceID, ms: root.durationNano / 1_000_000 } : null;
        })
        .filter(Boolean)
        .sort((a, b) => b!.ms - a!.ms)[0];
      if (slowest) representativeTraceId = slowest.traceID;
    }

    return {
      p50_latency_ms: percentile(rootDurations, 50),
      p95_latency_ms: percentile(rootDurations, 95),
      error_rate: totalRoots > 0 ? errorRoots / totalRoots : 0,
      failed_provider: failedProvider,
      representative_trace_id: representativeTraceId,
      observability_complete: spansPresent && correlationPresent,
      provider_errors: providerErrors,
      adapter_exceptions: adapterExceptions,
      spans_present: spansPresent,
      correlation_present: correlationPresent,
    };
  }
}
