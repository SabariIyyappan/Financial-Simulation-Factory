import { metrics, trace, context, SpanStatusCode } from "@opentelemetry/api";
import { logs, SeverityNumber } from "@opentelemetry/api-logs";
import type { FactoryContext, ProviderName } from "./types.js";
import { ATTR, SPAN_NAMES } from "./types.js";

const tracer = trace.getTracer("api-guardian");
const meter = metrics.getMeter("api-guardian");
const logger = logs.getLogger("api-guardian");

const snapshotDuration = meter.createHistogram("api_guardian.product_snapshot.duration", {
  description: "Product Snapshot end-to-end duration in milliseconds",
  unit: "ms",
});

const snapshotErrors = meter.createCounter("api_guardian.product_snapshot.errors", {
  description: "Product Snapshot request errors",
});

const providerDuration = meter.createHistogram("api_guardian.provider.duration", {
  description: "Provider call duration in milliseconds",
  unit: "ms",
});

const providerErrors = meter.createCounter("api_guardian.provider.errors", {
  description: "Provider call errors",
});

function baseAttributes(ctx: FactoryContext): Record<string, string> {
  const attrs: Record<string, string> = {
    [ATTR.factoryRunId]: ctx.factoryRunId,
    [ATTR.candidateId]: ctx.candidateId,
    [ATTR.demoScenario]: ctx.scenario,
  };
  if (ctx.releaseVersion) {
    attrs[ATTR.releaseVersion] = ctx.releaseVersion;
  }
  return attrs;
}

function spanNameForProvider(provider: ProviderName): string {
  switch (provider) {
    case "catalog":
      return SPAN_NAMES.catalog;
    case "pricing":
      return SPAN_NAMES.pricing;
    case "availability":
      return SPAN_NAMES.availability;
  }
}

export async function withProductSnapshot<T>(
  ctx: FactoryContext,
  fn: () => Promise<T>
): Promise<T> {
  const attrs = baseAttributes(ctx);
  const start = Date.now();

  return tracer.startActiveSpan(SPAN_NAMES.productSnapshot, { attributes: attrs }, async (span) => {
    try {
      const result = await fn();
      span.setAttribute(ATTR.providerStatus, "ok");
      span.setStatus({ code: SpanStatusCode.OK });
      snapshotDuration.record(Date.now() - start, attrs);
      return result;
    } catch (error) {
      span.setAttribute(ATTR.providerStatus, "error");
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: error instanceof Error ? error.message : String(error),
      });
      snapshotDuration.record(Date.now() - start, attrs);
      snapshotErrors.add(1, attrs);
      throw error;
    } finally {
      span.end();
    }
  });
}

export async function withProviderCall<T>(
  ctx: FactoryContext,
  provider: ProviderName,
  meta: { version: string },
  fn: () => Promise<T>
): Promise<T> {
  const attrs = {
    ...baseAttributes(ctx),
    [ATTR.providerName]: provider,
    [ATTR.providerVersion]: meta.version,
  };
  const start = Date.now();

  return tracer.startActiveSpan(spanNameForProvider(provider), { attributes: attrs }, async (span) => {
    try {
      const result = await fn();
      span.setAttribute(ATTR.providerStatus, "ok");
      span.setStatus({ code: SpanStatusCode.OK });
      providerDuration.record(Date.now() - start, {
        [ATTR.providerName]: provider,
        [ATTR.providerVersion]: meta.version,
      });
      return result;
    } catch (error) {
      span.setAttribute(ATTR.providerStatus, "error");
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: error instanceof Error ? error.message : String(error),
      });
      providerDuration.record(Date.now() - start, {
        [ATTR.providerName]: provider,
        [ATTR.providerVersion]: meta.version,
      });
      providerErrors.add(1, { [ATTR.providerName]: provider });
      throw error;
    } finally {
      span.end();
    }
  });
}

export function logProviderError(
  ctx: FactoryContext,
  provider: string,
  code: string,
  message: string,
  stage = "adapter.parse"
): void {
  const span = trace.getActiveSpan();
  const spanContext = span?.spanContext();

  logger.emit({
    severityNumber: SeverityNumber.ERROR,
    severityText: "ERROR",
    body: message,
    attributes: {
      ...baseAttributes(ctx),
      scenario: ctx.scenario,
      stage,
      provider,
      "error.code": code,
      "error.message": message,
      ...(spanContext
        ? {
            trace_id: spanContext.traceId,
            span_id: spanContext.spanId,
          }
        : {}),
    },
  });
}

export { context, trace };
