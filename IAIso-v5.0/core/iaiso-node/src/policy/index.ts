/**
 * Policy-as-code loader.
 *
 * Port of iaiso.policy from the Python reference. See
 * spec/policy/README.md for the normative format and
 * spec/policy/vectors.json for the 17 conformance vectors.
 *
 * Supports JSON. YAML can be parsed by the caller (e.g. with `js-yaml`) and
 * passed as a plain object to `buildPolicy()`.
 */

import { readFileSync } from "node:fs";
import { PressureConfig } from "../core/engine.js";

export class PolicyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PolicyError";
  }
}

export type AggregatorName = "sum" | "mean" | "max" | "weighted_sum";

export interface CoordinatorConfigFields {
  escalation_threshold?: number;
  release_threshold?: number;
  notify_cooldown_seconds?: number;
}

export class CoordinatorConfig {
  readonly escalation_threshold: number;
  readonly release_threshold: number;
  readonly notify_cooldown_seconds: number;

  constructor(fields: CoordinatorConfigFields = {}) {
    this.escalation_threshold = fields.escalation_threshold ?? 5.0;
    this.release_threshold = fields.release_threshold ?? 8.0;
    this.notify_cooldown_seconds = fields.notify_cooldown_seconds ?? 1.0;
  }
}

export interface ConsentPolicyFields {
  issuer?: string | null;
  default_ttl_seconds?: number;
  required_scopes?: string[];
  allowed_algorithms?: string[];
}

export class ConsentPolicy {
  readonly issuer: string | null;
  readonly default_ttl_seconds: number;
  readonly required_scopes: string[];
  readonly allowed_algorithms: string[];

  constructor(fields: ConsentPolicyFields = {}) {
    this.issuer = fields.issuer ?? null;
    this.default_ttl_seconds = fields.default_ttl_seconds ?? 3600.0;
    this.required_scopes = fields.required_scopes
      ? [...fields.required_scopes]
      : [];
    this.allowed_algorithms = fields.allowed_algorithms
      ? [...fields.allowed_algorithms]
      : ["HS256", "RS256"];
  }
}

export interface Aggregator {
  readonly name: AggregatorName;
  aggregate(values: Map<string, number>): number;
}

export class SumAggregator implements Aggregator {
  readonly name = "sum" as const;
  aggregate(values: Map<string, number>): number {
    let total = 0;
    for (const v of values.values()) total += v;
    return total;
  }
}

export class MeanAggregator implements Aggregator {
  readonly name = "mean" as const;
  aggregate(values: Map<string, number>): number {
    if (values.size === 0) return 0;
    let total = 0;
    for (const v of values.values()) total += v;
    return total / values.size;
  }
}

export class MaxAggregator implements Aggregator {
  readonly name = "max" as const;
  aggregate(values: Map<string, number>): number {
    let max = 0;
    for (const v of values.values()) {
      if (v > max) max = v;
    }
    return max;
  }
}

export class WeightedSumAggregator implements Aggregator {
  readonly name = "weighted_sum" as const;
  readonly weights: Map<string, number>;
  readonly default_weight: number;

  constructor(weights: Record<string, number> = {}, default_weight = 1.0) {
    this.weights = new Map(Object.entries(weights));
    this.default_weight = default_weight;
  }

  aggregate(values: Map<string, number>): number {
    let total = 0;
    for (const [k, v] of values) {
      const w = this.weights.get(k) ?? this.default_weight;
      total += w * v;
    }
    return total;
  }
}

export class Policy {
  readonly version: string;
  readonly pressure: PressureConfig;
  readonly coordinator: CoordinatorConfig;
  readonly consent: ConsentPolicy;
  readonly aggregator: Aggregator;
  readonly metadata: Record<string, unknown>;

  constructor(params: {
    version: string;
    pressure: PressureConfig;
    coordinator: CoordinatorConfig;
    consent: ConsentPolicy;
    aggregator: Aggregator;
    metadata?: Record<string, unknown>;
  }) {
    this.version = params.version;
    this.pressure = params.pressure;
    this.coordinator = params.coordinator;
    this.consent = params.consent;
    this.aggregator = params.aggregator;
    this.metadata = params.metadata ?? {};
  }
}

const SCOPE_PATTERN = /^[a-z0-9_-]+(\.[a-z0-9_-]+)*$/;

function isObject(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

/**
 * Validate a parsed policy document against the normative rules in
 * spec/policy/README.md. Throws PolicyError with a JSON-Pointer-like path.
 */
export function validatePolicy(doc: unknown): asserts doc is Record<string, unknown> {
  if (!isObject(doc)) {
    throw new PolicyError("$: policy document must be a mapping");
  }
  if (doc["version"] === undefined) {
    throw new PolicyError("$: required property 'version' missing");
  }
  if (doc["version"] !== "1") {
    throw new PolicyError(
      `$.version: must be exactly "1", got ${JSON.stringify(doc["version"])}`,
    );
  }

  // pressure section
  const pressure = doc["pressure"];
  if (pressure !== undefined) {
    if (!isObject(pressure)) {
      throw new PolicyError("$.pressure: must be a mapping");
    }
    const numberFields = [
      "token_coefficient",
      "tool_coefficient",
      "depth_coefficient",
      "dissipation_per_step",
      "dissipation_per_second",
    ] as const;
    for (const f of numberFields) {
      if (f in pressure) {
        const v = pressure[f];
        if (typeof v !== "number" || Number.isNaN(v)) {
          throw new PolicyError(
            `$.pressure.${f}: expected number, got ${typeof v}`,
          );
        }
        if (v < 0) {
          throw new PolicyError(
            `$.pressure.${f}: must be non-negative (got ${v})`,
          );
        }
      }
    }
    const thresholdFields = [
      "escalation_threshold",
      "release_threshold",
    ] as const;
    for (const f of thresholdFields) {
      if (f in pressure) {
        const v = pressure[f];
        if (typeof v !== "number" || Number.isNaN(v)) {
          throw new PolicyError(
            `$.pressure.${f}: expected number, got ${typeof v}`,
          );
        }
        if (v < 0 || v > 1) {
          throw new PolicyError(
            `$.pressure.${f}: must be in [0, 1] (got ${v})`,
          );
        }
      }
    }
    if ("post_release_lock" in pressure) {
      if (typeof pressure["post_release_lock"] !== "boolean") {
        throw new PolicyError(
          "$.pressure.post_release_lock: expected boolean",
        );
      }
    }
    // cross-field
    if ("escalation_threshold" in pressure && "release_threshold" in pressure) {
      const esc = pressure["escalation_threshold"] as number;
      const rel = pressure["release_threshold"] as number;
      if (rel <= esc) {
        throw new PolicyError(
          `$.pressure.release_threshold: must exceed escalation_threshold (${rel} <= ${esc})`,
        );
      }
    }
  }

  // coordinator section
  const coord = doc["coordinator"];
  if (coord !== undefined) {
    if (!isObject(coord)) {
      throw new PolicyError("$.coordinator: must be a mapping");
    }
    if ("aggregator" in coord) {
      const v = coord["aggregator"];
      if (
        typeof v !== "string" ||
        !["sum", "mean", "max", "weighted_sum"].includes(v)
      ) {
        throw new PolicyError(
          `$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got ${JSON.stringify(v)})`,
        );
      }
    }
    if ("escalation_threshold" in coord && "release_threshold" in coord) {
      const esc = coord["escalation_threshold"] as number;
      const rel = coord["release_threshold"] as number;
      if (rel <= esc) {
        throw new PolicyError(
          `$.coordinator.release_threshold: must exceed escalation_threshold (${rel} <= ${esc})`,
        );
      }
    }
  }

  // consent: scope grammar
  const consent = doc["consent"];
  if (consent !== undefined) {
    if (!isObject(consent)) {
      throw new PolicyError("$.consent: must be a mapping");
    }
    const scopes = consent["required_scopes"];
    if (Array.isArray(scopes)) {
      scopes.forEach((scope, i) => {
        if (typeof scope !== "string" || !SCOPE_PATTERN.test(scope)) {
          throw new PolicyError(
            `$.consent.required_scopes[${i}]: ${JSON.stringify(scope)} is not a valid scope`,
          );
        }
      });
    }
  }
}

function pickKnown<T>(
  fields: Record<string, unknown> | undefined,
  known: readonly string[],
): Partial<T> {
  const out: Record<string, unknown> = {};
  if (!fields) return out as Partial<T>;
  for (const k of known) {
    if (k in fields) out[k] = fields[k];
  }
  return out as Partial<T>;
}

function buildAggregator(coord: Record<string, unknown>): Aggregator {
  const name = (coord["aggregator"] as string | undefined) ?? "sum";
  switch (name) {
    case "sum":
      return new SumAggregator();
    case "mean":
      return new MeanAggregator();
    case "max":
      return new MaxAggregator();
    case "weighted_sum":
      return new WeightedSumAggregator(
        (coord["weights"] as Record<string, number> | undefined) ?? {},
        (coord["default_weight"] as number | undefined) ?? 1.0,
      );
    default:
      throw new PolicyError(`unknown aggregator: ${name}`);
  }
}

/** Build a Policy from a pre-parsed document (dict). */
export function buildPolicy(doc: unknown): Policy {
  validatePolicy(doc);

  const pressureFields = pickKnown<ConstructorParameters<typeof PressureConfig>[0]>(
    doc["pressure"] as Record<string, unknown>,
    [
      "escalation_threshold",
      "release_threshold",
      "dissipation_per_step",
      "dissipation_per_second",
      "token_coefficient",
      "tool_coefficient",
      "depth_coefficient",
      "post_release_lock",
    ],
  );
  const pressure = new PressureConfig(pressureFields);

  const coordDoc = (doc["coordinator"] ?? {}) as Record<string, unknown>;
  const coordFields = pickKnown<CoordinatorConfigFields>(coordDoc, [
    "escalation_threshold",
    "release_threshold",
    "notify_cooldown_seconds",
  ]);
  const coordinator = new CoordinatorConfig(coordFields);
  const aggregator = buildAggregator(coordDoc);

  const consentFields = pickKnown<ConsentPolicyFields>(
    (doc["consent"] ?? {}) as Record<string, unknown>,
    ["issuer", "default_ttl_seconds", "required_scopes", "allowed_algorithms"],
  );
  const consent = new ConsentPolicy(consentFields);

  const metadata = (doc["metadata"] ?? {}) as Record<string, unknown>;

  return new Policy({
    version: doc["version"] as string,
    pressure,
    coordinator,
    consent,
    aggregator,
    metadata,
  });
}

/** Load a policy from a JSON file on disk. */
export function loadPolicy(path: string): Policy {
  const raw = readFileSync(path, "utf8");
  const doc = JSON.parse(raw) as unknown;
  return buildPolicy(doc);
}
