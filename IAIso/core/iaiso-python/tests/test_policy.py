"""Tests for the policy-as-code loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iaiso.coordination import (
    MaxAggregator,
    MeanAggregator,
    SumAggregator,
    WeightedSumAggregator,
)
from iaiso.policy import (
    Policy,
    PolicyError,
    dump_policy_template,
    load_policy,
)


def test_minimal_policy(tmp_path: Path) -> None:
    policy_file = tmp_path / "p.json"
    policy_file.write_text(json.dumps({"version": "1"}))
    policy = load_policy(policy_file)
    assert policy.version == "1"
    assert isinstance(policy.aggregator, SumAggregator)


def test_json_policy(tmp_path: Path) -> None:
    data = {
        "version": "1",
        "pressure": {
            "token_coefficient": 0.02,
            "escalation_threshold": 0.7,
            "release_threshold": 0.9,
        },
        "coordinator": {
            "escalation_threshold": 3.0,
            "release_threshold": 6.0,
            "aggregator": "mean",
        },
        "consent": {
            "issuer": "acme",
            "default_ttl_seconds": 7200,
        },
        "metadata": {"team": "platform"},
    }
    path = tmp_path / "p.json"
    path.write_text(json.dumps(data))
    policy = load_policy(path)
    assert policy.pressure.token_coefficient == 0.02
    assert policy.pressure.escalation_threshold == 0.7
    assert policy.coordinator.escalation_threshold == 3.0
    assert isinstance(policy.aggregator, MeanAggregator)
    assert policy.consent.issuer == "acme"
    assert policy.metadata == {"team": "platform"}


def test_yaml_policy(tmp_path: Path) -> None:
    try:
        import yaml  # noqa: F401
    except ImportError:
        pytest.skip("PyYAML not installed")
    yaml_content = """
version: "1"
pressure:
  token_coefficient: 0.01
coordinator:
  aggregator: max
"""
    path = tmp_path / "p.yaml"
    path.write_text(yaml_content)
    policy = load_policy(path)
    assert policy.pressure.token_coefficient == 0.01
    assert isinstance(policy.aggregator, MaxAggregator)


def test_weighted_sum_with_weights(tmp_path: Path) -> None:
    data = {
        "version": "1",
        "coordinator": {
            "aggregator": "weighted_sum",
            "weights": {"heavy": 5.0, "light": 0.2},
            "default_weight": 1.0,
        },
    }
    path = tmp_path / "p.json"
    path.write_text(json.dumps(data))
    policy = load_policy(path)
    assert isinstance(policy.aggregator, WeightedSumAggregator)
    assert policy.aggregator.weights == {"heavy": 5.0, "light": 0.2}


def test_invalid_version_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"version": "999"}))
    with pytest.raises(PolicyError, match="version"):
        load_policy(path)


def test_out_of_range_threshold_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "version": "1",
        "pressure": {"escalation_threshold": 1.5},  # > 1.0
    }))
    with pytest.raises(PolicyError, match="escalation_threshold"):
        load_policy(path)


def test_wrong_type_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "version": "1",
        "pressure": {"token_coefficient": "not a number"},
    }))
    with pytest.raises(PolicyError, match="token_coefficient"):
        load_policy(path)


def test_unknown_aggregator_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps({
        "version": "1",
        "coordinator": {"aggregator": "clever_aggregator"},
    }))
    with pytest.raises(PolicyError, match="aggregator"):
        load_policy(path)


def test_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "policy.toml"
    path.write_text("version = '1'")
    with pytest.raises(PolicyError, match="extension"):
        load_policy(path)


def test_non_object_root_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps(["not", "a", "dict"]))
    with pytest.raises(PolicyError, match="top-level"):
        load_policy(path)


def test_template_produces_valid_policy(tmp_path: Path) -> None:
    """The built-in template must be loadable."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        pytest.skip("PyYAML not installed")
    path = tmp_path / "template.yaml"
    dump_policy_template(path)
    policy = load_policy(path)
    assert isinstance(policy, Policy)
    assert policy.version == "1"
