"""The skill corpus is documentation that an LLM executes.

A stale skill is worse than a stale doc: an agent reads it and emits code that
does not run, or wires up a safety gate that does not exist. These tests bind
`skills/` to the SDK so the two cannot drift apart silently.

Run from the repository root, or from `core/iaiso-python`; the corpus is located
relative to this file.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

import iaiso
from iaiso import BoundedExecution, PressureConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = REPO_ROOT / "skills"

REQUIRED_FRONTMATTER = {
    "name", "description", "version", "tier", "category", "framework", "license",
}

# Skills are markdown; the frontmatter is a YAML block delimited by ---.
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _skill_files() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        pytest.skip(f"skill corpus not found at {SKILLS_ROOT}")
    return sorted(SKILLS_ROOT.glob("*/SKILL.md"))


def _frontmatter(path: Path) -> dict[str, str]:
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match, f"{path.name}: no YAML frontmatter block"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields


SKILLS = _skill_files()
IDS = [p.parent.name for p in SKILLS]


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_frontmatter_is_complete(path: Path) -> None:
    fields = _frontmatter(path)
    missing = REQUIRED_FRONTMATTER - set(fields)
    assert not missing, f"{path.parent.name}: missing frontmatter {sorted(missing)}"


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_name_matches_directory(path: Path) -> None:
    assert _frontmatter(path)["name"] == path.parent.name


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_description_fits_the_strictest_platform_limit(path: Path) -> None:
    # The Skills API caps `description` at 1024 characters and rejects
    # angle brackets, since frontmatter lands directly in a system prompt.
    description = _frontmatter(path)["description"]
    assert len(description) <= 1024, f"{path.parent.name}: description too long"
    assert "<" not in description and ">" not in description, (
        f"{path.parent.name}: angle brackets in description"
    )


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_no_stale_conformance_vector_count(path: Path) -> None:
    """The suite is 72 vectors at spec 1.1. A skill that says 67 will have an
    agent 'fix' a passing conformance run."""
    text = path.read_text(encoding="utf-8")
    stale = re.findall(r"\b67\b\s*(?:conformance\s*)?vectors?", text)
    assert not stale, f"{path.parent.name}: stale vector count {stale}"


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_python_examples_do_not_invent_boundedexecution_methods(path: Path) -> None:
    """Node and Go expose `run`/`Run`; Python does not. A skill that shows
    `BoundedExecution.run(...)` in a Python block teaches an AttributeError."""
    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```python\n(.*?)```", text, re.DOTALL):
        for attr in re.findall(r"BoundedExecution\.(\w+)", block):
            assert hasattr(BoundedExecution, attr), (
                f"{path.parent.name}: Python example calls "
                f"BoundedExecution.{attr}(), which does not exist"
            )


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_python_examples_reference_real_config_fields(path: Path) -> None:
    fields = {f.name for f in dataclasses.fields(PressureConfig)}
    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```python\n(.*?)```", text, re.DOTALL):
        for match in re.finditer(r"PressureConfig\((.*?)\)", block, re.DOTALL):
            for kwarg in re.findall(r"(\w+)\s*=", match.group(1)):
                assert kwarg in fields, (
                    f"{path.parent.name}: PressureConfig({kwarg}=...) "
                    f"is not a real field"
                )


@pytest.mark.parametrize("path", SKILLS, ids=IDS)
def test_python_examples_import_real_symbols(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for block in re.findall(r"```python\n(.*?)```", text, re.DOTALL):
        for match in re.finditer(r"^from iaiso import (.+)$", block, re.MULTILINE):
            for symbol in (s.strip() for s in match.group(1).split(",")):
                if symbol and symbol.isidentifier():
                    assert hasattr(iaiso, symbol), (
                        f"{path.parent.name}: `from iaiso import {symbol}` "
                        f"but iaiso exports no such name"
                    )


def test_the_boot_guard_is_documented_somewhere() -> None:
    """`enforcement_mode` is the difference between a gate and a suggestion.
    If no skill mentions it, every agent reading this corpus will ship
    permissive."""
    mentions = [p.parent.name for p in SKILLS
                if "enforcement_mode" in p.read_text(encoding="utf-8")]
    assert mentions, "no skill documents enforcement_mode"


def test_the_trust_boundary_is_stated_somewhere() -> None:
    """An agent that reads this corpus must learn that IAIso does not contain
    an agent which can execute arbitrary code. Silence here is how a framework
    starts producing confidence it has not earned."""
    mentions = [p.parent.name for p in SKILLS
                if "not contained" in p.read_text(encoding="utf-8").lower()]
    assert mentions, "no skill states what IAIso does not contain"

# ---------------------------------------------------------------------------
# The plugin marketplace manifest must not drift from the corpus on disk.
# A skill that exists but is unlisted is invisible to anyone who installs via
# `/plugin install`; a listed path that does not exist breaks the install.
# ---------------------------------------------------------------------------

MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

RESERVED_MARKETPLACE_NAMES = {
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace",
    "anthropic-plugins", "agent-skills", "anthropic-agent-skills",
    "knowledge-work-plugins", "life-sciences", "claude-for-legal",
    "claude-for-financial-services", "financial-services-plugins",
}


def _marketplace() -> dict:
    if not MARKETPLACE.exists():
        pytest.skip("no .claude-plugin/marketplace.json")
    import json

    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))


def test_marketplace_name_is_not_reserved() -> None:
    name = _marketplace()["name"]
    assert name not in RESERVED_MARKETPLACE_NAMES, (
        f"{name!r} is reserved for official Anthropic use"
    )


def test_marketplace_lists_every_skill_and_nothing_else() -> None:
    plugin = _marketplace()["plugins"][0]
    listed = {path.removeprefix("./skills/") for path in plugin["skills"]}
    on_disk = {p.parent.name for p in SKILLS}

    unlisted = on_disk - listed
    dangling = listed - on_disk
    assert not unlisted, f"skills on disk but not in marketplace.json: {sorted(unlisted)}"
    assert not dangling, f"marketplace.json lists missing skills: {sorted(dangling)}"


def test_marketplace_skill_paths_resolve() -> None:
    plugin = _marketplace()["plugins"][0]
    # `source: "./"` anchors each skill path at the repository root.
    assert plugin["source"] == "./", "skill paths are resolved against source"
    assert plugin.get("strict") is False, (
        "a corpus without plugin.json needs strict: false to declare skills"
    )
    for path in plugin["skills"]:
        assert (REPO_ROOT / path.removeprefix("./") / "SKILL.md").is_file(), path
