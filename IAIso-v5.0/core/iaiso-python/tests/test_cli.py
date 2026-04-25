"""Tests for the admin CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from iaiso.cli import main


def run_cli(*args: str, capsys_pair) -> tuple[int, str, str]:
    capsys_pair.readouterr()  # clear
    try:
        rc = main(list(args))
    except SystemExit as e:
        rc = int(e.code) if e.code is not None else 0
    out, err = capsys_pair.readouterr()
    return rc, out, err


def test_policy_template_and_validate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    try:
        import yaml  # noqa: F401
    except ImportError:
        pytest.skip("PyYAML not installed")

    path = tmp_path / "p.yaml"
    rc, out, err = run_cli("policy", "template", str(path),
                           capsys_pair=capsys)
    assert rc == 0
    assert path.exists()

    rc, out, err = run_cli("policy", "validate", str(path),
                           capsys_pair=capsys)
    assert rc == 0
    assert "OK" in out


def test_policy_validate_rejects_bad_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": "999"}))
    rc, out, err = run_cli("policy", "validate", str(bad),
                           capsys_pair=capsys)
    assert rc == 1
    assert "INVALID" in err


def test_consent_issue_and_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key_file = tmp_path / "key"
    key_file.write_bytes(b"x" * 32)

    rc, out, err = run_cli(
        "consent", "issue", "alice",
        "--scope", "tools.search",
        "--ttl", "60",
        "--issuer", "test",
        "--key", str(key_file),
        capsys_pair=capsys,
    )
    assert rc == 0
    token = out.strip()
    assert token.count(".") == 2  # JWT format

    rc, out, err = run_cli(
        "consent", "verify", token,
        "--key", str(key_file),
        "--issuer", "test",
        capsys_pair=capsys,
    )
    assert rc == 0
    assert "alice" in out
    assert "tools.search" in out


def test_consent_verify_rejects_bad_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key_file = tmp_path / "key"
    key_file.write_bytes(b"y" * 32)
    rc, out, err = run_cli(
        "consent", "verify", "not.a.token",
        "--key", str(key_file),
        capsys_pair=capsys,
    )
    assert rc == 1
    assert "INVALID" in err


def test_audit_stats_summarizes_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "audit.jsonl"
    lines = [
        json.dumps({"execution_id": "e1", "kind": "engine.step",
                    "timestamp": 1.0, "data": {}}),
        json.dumps({"execution_id": "e1", "kind": "engine.step",
                    "timestamp": 2.0, "data": {}}),
        json.dumps({"execution_id": "e2", "kind": "engine.escalation",
                    "timestamp": 3.0, "data": {}}),
    ]
    log.write_text("\n".join(lines) + "\n")

    rc, out, err = run_cli("audit", "stats", str(log), capsys_pair=capsys)
    assert rc == 0
    assert "Total events:        3" in out
    assert "Unique executions:   2" in out
    assert "engine.step" in out


def test_audit_tail_prints_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "audit.jsonl"
    log.write_text(json.dumps({
        "execution_id": "e1",
        "kind": "engine.step",
        "timestamp": 123.456,
        "data": {"pressure": 0.42, "tokens": 500},
    }) + "\n")
    rc, out, err = run_cli("audit", "tail", str(log), capsys_pair=capsys)
    assert rc == 0
    assert "engine.step" in out
    assert "pressure=0.42" in out


def test_coordinator_demo_runs(capsys: pytest.CaptureFixture[str]) -> None:
    rc, out, err = run_cli("coordinator", "demo", capsys_pair=capsys)
    assert rc == 0
    assert "[ESCALATION]" in out


def test_python_m_iaiso_entry(tmp_path: Path) -> None:
    """Make sure `python -m iaiso --help` works."""
    result = subprocess.run(
        [sys.executable, "-m", "iaiso", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "usage: iaiso" in result.stdout
