export { AuditEvent, SCHEMA_VERSION } from "./event.js";
export type { AuditEventJSON } from "./event.js";
export { MemorySink, NullSink, StdoutSink, FanoutSink } from "./sinks/memory.js";
export type { AuditSink } from "./sinks/memory.js";
export { JsonlFileSink } from "./sinks/jsonl.js";
export { WebhookSink } from "./sinks/webhook.js";
export type { WebhookSinkOptions } from "./sinks/webhook.js";

// SIEM sinks
export { SplunkHECSink, splunkHECPayload } from "./sinks/splunk.js";
export type { SplunkHECOptions } from "./sinks/splunk.js";
export { DatadogLogsSink, datadogLogsPayload } from "./sinks/datadog.js";
export type { DatadogLogsOptions } from "./sinks/datadog.js";
export { LokiSink, lokiPayload } from "./sinks/loki.js";
export type { LokiOptions } from "./sinks/loki.js";
export { ElasticECSSink, elasticECSPayload } from "./sinks/elastic.js";
export type { ElasticECSOptions } from "./sinks/elastic.js";
export { SumoLogicSink, sumoLogicPayload } from "./sinks/sumo.js";
export type { SumoLogicOptions } from "./sinks/sumo.js";
export { NewRelicLogsSink, newRelicLogsPayload } from "./sinks/newrelic.js";
export type { NewRelicLogsOptions } from "./sinks/newrelic.js";
