"""Policy vector runner.

For each vector, invokes the policy validator/loader on the provided
document and compares the outcome against expectations.

The runner does NOT go through a file — it calls `_validate` + the
dataclass builders directly. This avoids tmpfile juggling and is
equivalent for conformance purposes (file loading is a separate concern
covered in `tests/test_policy.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from iaiso.conformance import VectorResult, load_vectors


def run_policy_vectors(spec_root: Path) -> list[VectorResult]:
    from iaiso.policy import (
        ConsentPolicy,
        Policy,
        PolicyError,
        _build_aggregator,
        _validate,
    )
    from iaiso.coordination import CoordinatorConfig
    from iaiso.core import PressureConfig

    data = load_vectors(spec_root, "policy")
    tolerance = float(data.get("tolerance", 1e-9))
    results: list[VectorResult] = []

    # Valid vectors
    for vec in data.get("valid", []):
        name = vec["name"]
        try:
            policy = _build_policy(
                vec["document"], _validate, PressureConfig,
                CoordinatorConfig, ConsentPolicy, _build_aggregator,
            )
        except Exception as exc:  # noqa: BLE001
            results.append(VectorResult(
                section="policy", name=f"valid/{name}", passed=False,
                message=f"expected success but got {type(exc).__name__}: {exc}",
            ))
            continue

        msg = _check_valid_expectations(vec, policy, tolerance)
        if msg is None:
            results.append(VectorResult(section="policy", name=f"valid/{name}", passed=True))
        else:
            results.append(VectorResult(
                section="policy", name=f"valid/{name}", passed=False, message=msg,
            ))

    # Invalid vectors
    for vec in data.get("invalid", []):
        name = vec["name"]
        try:
            _build_policy(
                vec["document"], _validate, PressureConfig,
                CoordinatorConfig, ConsentPolicy, _build_aggregator,
            )
            results.append(VectorResult(
                section="policy", name=f"invalid/{name}", passed=False,
                message="expected PolicyError but loading succeeded",
            ))
        except PolicyError as exc:
            # Accept either the explicit JSON-Pointer-style path messages
            # emitted by the validator OR the dataclass-level ValueError
            # messages that mention the field name.
            expected_path = vec["expect_error_path"]
            if expected_path in str(exc):
                results.append(VectorResult(
                    section="policy", name=f"invalid/{name}", passed=True,
                ))
            else:
                results.append(VectorResult(
                    section="policy", name=f"invalid/{name}", passed=False,
                    message=f"got error {exc!s} but expected path substring {expected_path!r}",
                ))
        except (ValueError, TypeError) as exc:
            # Dataclass-level validation error (e.g. PressureConfig post_init)
            expected_path = vec["expect_error_path"]
            if expected_path in str(exc):
                results.append(VectorResult(
                    section="policy", name=f"invalid/{name}", passed=True,
                ))
            else:
                results.append(VectorResult(
                    section="policy", name=f"invalid/{name}", passed=False,
                    message=f"got {type(exc).__name__}: {exc} but expected path {expected_path!r}",
                ))

    return results


def _build_policy(
    doc, _validate, PressureConfig, CoordinatorConfig, ConsentPolicy, _build_aggregator,
):
    """Mirror of iaiso.policy.load_policy, but taking a dict directly."""
    import dataclasses as _dc
    from iaiso.policy import Policy

    _validate(doc)

    def _known(cls, fields):
        known = {f.name for f in _dc.fields(cls)}
        return {k: v for k, v in fields.items() if k in known}

    pressure = PressureConfig(**_known(PressureConfig, doc.get("pressure", {})))
    coord_doc = doc.get("coordinator", {})
    coord_fields = {k: v for k, v in coord_doc.items()
                    if k in ("escalation_threshold", "release_threshold",
                             "notify_cooldown_seconds")}
    coordinator = CoordinatorConfig(**coord_fields)
    aggregator = _build_aggregator(coord_doc)
    consent = ConsentPolicy(**_known(ConsentPolicy, doc.get("consent", {})))

    return Policy(
        version=doc["version"],
        pressure=pressure,
        coordinator=coordinator,
        consent=consent,
        aggregator=aggregator,
        metadata=doc.get("metadata", {}),
    )


def _check_valid_expectations(vec: dict, policy, tolerance: float) -> str | None:
    # Check pressure fields
    for key, expected in (vec.get("expected_pressure") or {}).items():
        actual = getattr(policy.pressure, key)
        if not _approx_equal(actual, expected, tolerance):
            return f"pressure.{key}: expected {expected!r}, got {actual!r}"

    # Check coordinator fields
    for key, expected in (vec.get("expected_coordinator") or {}).items():
        actual = getattr(policy.coordinator, key)
        if not _approx_equal(actual, expected, tolerance):
            return f"coordinator.{key}: expected {expected!r}, got {actual!r}"

    # Check consent fields
    for key, expected in (vec.get("expected_consent") or {}).items():
        actual = getattr(policy.consent, key)
        if actual != expected:
            return f"consent.{key}: expected {expected!r}, got {actual!r}"

    # Check aggregator name
    if "expected_aggregator_name" in vec:
        if policy.aggregator.name != vec["expected_aggregator_name"]:
            return f"aggregator.name: expected {vec['expected_aggregator_name']!r}, got {policy.aggregator.name!r}"

    # Check metadata
    if "expected_metadata" in vec:
        if policy.metadata != vec["expected_metadata"]:
            return f"metadata: expected {vec['expected_metadata']!r}, got {policy.metadata!r}"

    return None


def _approx_equal(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(float(actual) - float(expected)) <= tolerance
    return actual == expected
