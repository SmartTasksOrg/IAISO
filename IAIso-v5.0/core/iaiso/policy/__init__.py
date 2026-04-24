"""Policy-as-code: load IAIso configuration from YAML or JSON files.

Ops teams push back on "config is a Python file" for good reasons: the
config needs version control, peer review, template rendering, secret
injection, and sometimes GitOps-style deployment. A file format they can
parse independently solves all of that.

This module defines a schema, a loader, and a validator for IAIso's main
configuration objects. It deliberately stays narrower than Python's full
expressivity — you can't compute thresholds at load time, for example.
Trade complexity for auditability.

Example policy file (`policy.yaml`):

    version: "1"
    pressure:
      token_coefficient: 0.015
      tool_coefficient: 0.08
      depth_coefficient: 0.05
      dissipation_per_step: 0.02
      escalation_threshold: 0.85
      release_threshold: 0.95
    coordinator:
      escalation_threshold: 5.0
      release_threshold: 8.0
      notify_cooldown_seconds: 1.0
      aggregator: sum
    consent:
      default_ttl_seconds: 3600
      issuer: "my-org"
      required_scopes: []

Load with:

    from iaiso.policy import load_policy
    policy = load_policy("./policy.yaml")
    engine = PressureEngine(policy.pressure)
    coordinator = SharedPressureCoordinator(
        config=policy.coordinator,
        aggregator=policy.aggregator,
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from iaiso.coordination import (
    CoordinatorConfig,
    MaxAggregator,
    MeanAggregator,
    SumAggregator,
    WeightedSumAggregator,
)
from iaiso.core import PressureConfig


class PolicyError(ValueError):
    """Raised when a policy file fails validation."""


@dataclass
class ConsentPolicy:
    """Policy settings for consent issuing / verification."""

    issuer: str | None = None
    default_ttl_seconds: float = 3600.0
    required_scopes: list[str] = field(default_factory=list)
    allowed_algorithms: list[str] = field(default_factory=lambda: ["HS256", "RS256"])


@dataclass
class Policy:
    """Top-level policy bundle."""

    version: str
    pressure: PressureConfig
    coordinator: CoordinatorConfig
    consent: ConsentPolicy
    aggregator: Any  # an Aggregator instance
    metadata: dict[str, Any] = field(default_factory=dict)


# JSON Schema for the policy file format. Kept inline so IAIso has no
# jsonschema dependency; validation is done by hand in `_validate()`.
POLICY_SCHEMA = {
    "type": "object",
    "required": ["version"],
    "properties": {
        "version": {"type": "string", "enum": ["1"]},
        "pressure": {
            "type": "object",
            "properties": {
                "token_coefficient": {"type": "number", "minimum": 0},
                "tool_coefficient": {"type": "number", "minimum": 0},
                "depth_coefficient": {"type": "number", "minimum": 0},
                "dissipation_per_step": {"type": "number", "minimum": 0},
                "dissipation_per_second": {"type": "number", "minimum": 0},
                "escalation_threshold": {"type": "number",
                                         "minimum": 0, "maximum": 1},
                "release_threshold": {"type": "number",
                                      "minimum": 0, "maximum": 1},
                "post_release_lock": {"type": "boolean"},
            },
        },
        "coordinator": {
            "type": "object",
            "properties": {
                "escalation_threshold": {"type": "number", "minimum": 0},
                "release_threshold": {"type": "number", "minimum": 0},
                "notify_cooldown_seconds": {"type": "number", "minimum": 0},
                "aggregator": {"type": "string",
                               "enum": ["sum", "mean", "max", "weighted_sum"]},
                "weights": {"type": "object"},
                "default_weight": {"type": "number"},
            },
        },
        "consent": {
            "type": "object",
            "properties": {
                "issuer": {"type": "string"},
                "default_ttl_seconds": {"type": "number", "minimum": 0},
                "required_scopes": {"type": "array",
                                     "items": {"type": "string"}},
                "allowed_algorithms": {"type": "array",
                                         "items": {"type": "string"}},
            },
        },
        "metadata": {"type": "object"},
    },
}


def _check_type(value: Any, spec: dict[str, Any], path: str) -> None:
    t = spec.get("type")
    if t == "object":
        if not isinstance(value, dict):
            raise PolicyError(f"{path}: expected object, got {type(value).__name__}")
    elif t == "array":
        if not isinstance(value, list):
            raise PolicyError(f"{path}: expected array, got {type(value).__name__}")
    elif t == "string":
        if not isinstance(value, str):
            raise PolicyError(f"{path}: expected string, got {type(value).__name__}")
    elif t == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PolicyError(f"{path}: expected number, got {type(value).__name__}")
        if "minimum" in spec and value < spec["minimum"]:
            raise PolicyError(f"{path}: {value} < minimum {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise PolicyError(f"{path}: {value} > maximum {spec['maximum']}")
    elif t == "boolean":
        if not isinstance(value, bool):
            raise PolicyError(f"{path}: expected boolean, got {type(value).__name__}")
    if "enum" in spec and value not in spec["enum"]:
        raise PolicyError(f"{path}: {value!r} not in {spec['enum']}")


_SCOPE_PATTERN = __import__("re").compile(r"^[a-z0-9_-]+(\.[a-z0-9_-]+)*$")


def _validate(doc: Any) -> None:
    """Minimal JSON-Schema-like validation. Does not implement full spec.

    Enforces the normative rules from spec/policy/README.md §7:
    - required top-level keys (version)
    - per-section property types and bounds
    - cross-field rules: release > escalation (pressure), coordinator
      requires thresholds when present
    - scope grammar for consent.required_scopes items
    """
    _check_type(doc, POLICY_SCHEMA, "$")
    for key in POLICY_SCHEMA.get("required", []):
        if key not in doc:
            raise PolicyError(f"$: required property '{key}' missing")
    for key, subspec in POLICY_SCHEMA["properties"].items():
        if key not in doc:
            continue
        _check_type(doc[key], subspec, f"$.{key}")
        if subspec.get("type") == "object":
            for subkey, subsubspec in subspec.get("properties", {}).items():
                if subkey in doc[key]:
                    _check_type(doc[key][subkey], subsubspec, f"$.{key}.{subkey}")
        elif subspec.get("type") == "array":
            items_spec = subspec.get("items")
            if items_spec:
                for i, item in enumerate(doc[key]):
                    _check_type(item, items_spec, f"$.{key}[{i}]")

    # Cross-field: release > escalation in pressure
    pressure = doc.get("pressure", {})
    if "escalation_threshold" in pressure and "release_threshold" in pressure:
        if pressure["release_threshold"] <= pressure["escalation_threshold"]:
            raise PolicyError(
                f"$.pressure.release_threshold: must exceed escalation_threshold "
                f"({pressure['release_threshold']} <= {pressure['escalation_threshold']})"
            )

    # Coordinator section: cross-field validation only when both present.
    # Thresholds default to CoordinatorConfig defaults (5.0 / 8.0) if omitted.
    if "coordinator" in doc:
        coord = doc["coordinator"]
        if "escalation_threshold" in coord and "release_threshold" in coord:
            if coord["release_threshold"] <= coord["escalation_threshold"]:
                raise PolicyError(
                    f"$.coordinator.release_threshold: must exceed escalation_threshold "
                    f"({coord['release_threshold']} <= {coord['escalation_threshold']})"
                )

    # Consent: scope grammar
    consent = doc.get("consent", {})
    for i, scope in enumerate(consent.get("required_scopes", [])):
        if isinstance(scope, str) and not _SCOPE_PATTERN.match(scope):
            raise PolicyError(
                f"$.consent.required_scopes[{i}]: {scope!r} is not a valid scope "
                f"(must match [a-z0-9_-]+(\\.[a-z0-9_-]+)*)"
            )


def _load_file(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as e:
            raise PolicyError(
                "Loading YAML policy files requires PyYAML. "
                "Install with: pip install iaiso[policy]"
            ) from e
        loaded = yaml.safe_load(text)
    elif path.suffix == ".json":
        loaded = json.loads(text)
    else:
        raise PolicyError(
            f"Unsupported policy file extension: {path.suffix}. "
            "Use .yaml, .yml, or .json."
        )
    if not isinstance(loaded, dict):
        raise PolicyError("Policy file must contain a top-level mapping")
    return loaded


def _build_aggregator(coord_cfg: dict[str, Any]) -> Any:
    name = coord_cfg.get("aggregator", "sum")
    if name == "sum":
        return SumAggregator()
    if name == "mean":
        return MeanAggregator()
    if name == "max":
        return MaxAggregator()
    if name == "weighted_sum":
        return WeightedSumAggregator(
            weights=coord_cfg.get("weights", {}),
            default_weight=float(coord_cfg.get("default_weight", 1.0)),
        )
    raise PolicyError(f"unknown aggregator: {name}")


def load_policy(path: str | Path) -> Policy:
    """Load and validate a policy file. Returns a `Policy` bundle.

    Raises `PolicyError` with a path-like pointer to the failing field
    if the document is malformed.
    """
    doc = _load_file(path)
    _validate(doc)

    pressure = _instantiate_known(PressureConfig, doc.get("pressure", {}))
    coord_doc = doc.get("coordinator", {})
    coord_fields = {k: v for k, v in coord_doc.items()
                    if k in ("escalation_threshold", "release_threshold",
                             "notify_cooldown_seconds")}
    coordinator = CoordinatorConfig(**coord_fields)
    aggregator = _build_aggregator(coord_doc)
    consent = _instantiate_known(ConsentPolicy, doc.get("consent", {}))

    return Policy(
        version=doc["version"],
        pressure=pressure,
        coordinator=coordinator,
        consent=consent,
        aggregator=aggregator,
        metadata=doc.get("metadata", {}),
    )


def _instantiate_known(cls, fields: dict[str, Any]):
    """Build a dataclass, silently dropping unknown keys for forward compat.

    Policy files are written by humans, often generated from templates, and
    SHOULD forward-compat with future IAIso versions that add new fields.
    The spec (spec/policy/README.md §2) requires unknown keys to be ignored.
    """
    import dataclasses as _dc
    known = {f.name for f in _dc.fields(cls)}
    filtered = {k: v for k, v in fields.items() if k in known}
    return cls(**filtered)


def dump_policy_template(path: str | Path) -> None:
    """Write a fully-populated policy template to `path`.

    Useful as a starting point: generate once, commit to your repo,
    tune the values, run in shadow mode, promote to enforcing.
    """
    template = """# IAIso policy v1
# Generated template — tune and commit.

version: "1"

# Pressure engine coefficients. Start with these defaults; after
# collecting real trajectories, run the calibration harness
# (see docs/calibration.md) to tune.
pressure:
  token_coefficient: 0.015         # pressure per 1000 tokens
  tool_coefficient: 0.08           # pressure per tool call
  depth_coefficient: 0.05          # pressure per planning-depth level
  dissipation_per_step: 0.02       # pressure subtracted each step
  dissipation_per_second: 0.0      # pressure subtracted per wall-clock second
  escalation_threshold: 0.85       # fire escalation at this pressure
  release_threshold: 0.95          # force state reset at this pressure
  post_release_lock: true          # refuse further work after release

# Fleet-level coordinator. Unused if you're running single-agent.
coordinator:
  escalation_threshold: 5.0
  release_threshold: 8.0
  notify_cooldown_seconds: 1.0
  aggregator: sum                   # sum | mean | max | weighted_sum
  # For weighted_sum, specify per-execution weights:
  # weights:
  #   high-cost-agent: 3.0
  #   cheap-agent: 0.5
  # default_weight: 1.0

# Consent token settings.
consent:
  issuer: "my-org"
  default_ttl_seconds: 3600
  required_scopes: []
  allowed_algorithms: ["HS256", "RS256"]

# Free-form operator metadata. Not interpreted by IAIso.
metadata:
  owner: "platform-team"
  environment: "production"
"""
    Path(path).write_text(template, encoding="utf-8")
