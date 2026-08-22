import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";
import { OTLPLogExporter } from "@opentelemetry/exporter-logs-otlp-http";
import { PeriodicExportingMetricReader } from "@opentelemetry/sdk-metrics";
import { BatchLogRecordProcessor, LoggerProvider } from "@opentelemetry/sdk-logs";
import { Resource } from "@opentelemetry/resources";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";
import { logs } from "@opentelemetry/api-logs";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";

let sdk: NodeSDK | null = null;
let loggerProvider: LoggerProvider | null = null;

function resolveOtlpEndpoint(): string {
  const configured = process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://localhost:4318";
  // HTTP OTLP uses port 4318; map legacy gRPC 4317 configs automatically.
  return configured.replace(":4317", ":4318");
}

function traceEndpoint(base: string): string {
  return base.endsWith("/v1/traces") ? base : `${base.replace(/\/$/, "")}/v1/traces`;
}

function metricsEndpoint(base: string): string {
  return base.endsWith("/v1/metrics") ? base : `${base.replace(/\/$/, "")}/v1/metrics`;
}

function logsEndpoint(base: string): string {
  return base.endsWith("/v1/logs") ? base : `${base.replace(/\/$/, "")}/v1/logs`;
}

export function initTelemetry(serviceName = process.env.OTEL_SERVICE_NAME ?? "api-guardian"): void {
  if (sdk) {
    return;
  }

  const baseEndpoint = resolveOtlpEndpoint();
  const resource = new Resource({
    [ATTR_SERVICE_NAME]: serviceName,
  });

  loggerProvider = new LoggerProvider({ resource });
  loggerProvider.addLogRecordProcessor(
    new BatchLogRecordProcessor(new OTLPLogExporter({ url: logsEndpoint(baseEndpoint) }))
  );
  logs.setGlobalLoggerProvider(loggerProvider);

  sdk = new NodeSDK({
    resource,
    traceExporter: new OTLPTraceExporter({ url: traceEndpoint(baseEndpoint) }),
    metricReader: new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({ url: metricsEndpoint(baseEndpoint) }),
      exportIntervalMillis: 5_000,
    }),
    instrumentations: [new HttpInstrumentation()],
  });

  sdk.start();

  const shutdown = async () => {
    await sdk?.shutdown();
    await loggerProvider?.shutdown();
  };

  process.once("SIGTERM", shutdown);
  process.once("SIGINT", shutdown);
}

export async function shutdownTelemetry(): Promise<void> {
  await sdk?.shutdown();
  await loggerProvider?.shutdown();
  sdk = null;
  loggerProvider = null;
}
