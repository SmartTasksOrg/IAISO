"""Conformance suite wrapper for pytest.

Runs every spec/*/vectors.json vector as a parametrized pytest case so
failures identify the exact vector rather than a batched summary. The
actual runners live in `iaiso.conformance`; this file just adapts them.

Run with:
    pytest tests/test_conformance.py -v

Filter to one subsystem:
    pytest tests/test_conformance.py -v -k pressure
    pytest tests/test_conformance.py -v -k consent
"""

from __future__ import annotations

from pathlib import Path

import pytest

from iaiso.conformance import (
    VectorResult,
    run_consent_vectors,
    run_events_vectors,
    run_policy_vectors,
    run_pressure_vectors,
)

SPEC_ROOT = Path(__file__).resolve().parent.parent.parent / "spec"


# Runners are imported lazily via parametrize ID expansion so the
# vector file is read exactly once per section.

_PRESSURE_RESULTS = run_pressure_vectors(SPEC_ROOT)
_CONSENT_RESULTS = run_consent_vectors(SPEC_ROOT)
_EVENTS_RESULTS = run_events_vectors(SPEC_ROOT)
_POLICY_RESULTS = run_policy_vectors(SPEC_ROOT)


def _ids(results: list[VectorResult]) -> list[str]:
    return [r.name for r in results]


@pytest.mark.parametrize("result", _PRESSURE_RESULTS, ids=_ids(_PRESSURE_RESULTS))
def test_pressure_vector(result: VectorResult) -> None:
    assert result.passed, result.message


@pytest.mark.parametrize("result", _CONSENT_RESULTS, ids=_ids(_CONSENT_RESULTS))
def test_consent_vector(result: VectorResult) -> None:
    assert result.passed, result.message


@pytest.mark.parametrize("result", _EVENTS_RESULTS, ids=_ids(_EVENTS_RESULTS))
def test_events_vector(result: VectorResult) -> None:
    assert result.passed, result.message


@pytest.mark.parametrize("result", _POLICY_RESULTS, ids=_ids(_POLICY_RESULTS))
def test_policy_vector(result: VectorResult) -> None:
    assert result.passed, result.message


# Bumped 1.0 -> 1.1 when `enforcement_mode` and its five policy vectors landed.
# Additive change, so MINOR per spec/README.md. Pinned deliberately: a silent
# spec drift is exactly what this test exists to catch.
SPEC_VERSION = "1.1"


def test_spec_has_version_file() -> None:
    version_path = SPEC_ROOT / "VERSION"
    assert version_path.exists(), f"spec/VERSION missing at {version_path}"
    version = version_path.read_text().strip()
    assert version == SPEC_VERSION, (
        f"spec/VERSION should be {SPEC_VERSION}, got {version!r}"
    )


def test_vendored_specs_match_the_canonical_spec() -> None:
    """Every port vendors a copy of core/spec. Ports that have adopted 1.1 must
    match it byte for byte; ports still on 1.0 have not adopted it yet."""
    import hashlib

    canonical = (SPEC_ROOT / "policy" / "vectors.json").read_bytes()
    digest = hashlib.sha256(canonical).hexdigest()
    repo_root = SPEC_ROOT.parent.parent

    for port in ("iaiso-go", "iaiso-node"):
        vendored = repo_root / "core" / port / "spec" / "policy" / "vectors.json"
        if not vendored.exists():
            continue
        assert hashlib.sha256(vendored.read_bytes()).hexdigest() == digest, (
            f"{port} vendors a stale copy of spec/policy/vectors.json"
        )


def test_every_subsystem_has_a_readme() -> None:
    for subsystem in ("pressure", "consent", "events", "policy", "coordinator"):
        readme = SPEC_ROOT / subsystem / "README.md"
        assert readme.exists(), f"{subsystem} missing README.md"


def test_every_subsystem_with_vectors_has_them() -> None:
    for subsystem in ("pressure", "consent", "events", "policy"):
        vectors = SPEC_ROOT / subsystem / "vectors.json"
        assert vectors.exists(), f"{subsystem} missing vectors.json"
