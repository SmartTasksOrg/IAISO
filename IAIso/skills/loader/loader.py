"""
Minimal IAIso skill loader.

Reads ./skills/<name>/SKILL.md files and exposes them as a
queryable registry. No external dependencies.

Usage:
    from skills.loader.loader import SkillRegistry
    reg = SkillRegistry.load("./skills")
    skill = reg["iaiso-runtime-governed-agent"]
    print(skill.body)
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str = ""
    version: str = ""
    tier: str = ""
    category: str = ""
    framework: str = ""
    license: str = ""
    body: str = ""
    metadata: dict = field(default_factory=dict)
    path: str = ""

    @classmethod
    def from_file(cls, path: str | os.PathLike) -> "Skill":
        text = Path(path).read_text(encoding="utf-8")
        m = _FRONTMATTER_RE.match(text)
        if not m:
            raise ValueError(f"{path}: missing or malformed frontmatter")
        fm_text, body = m.group(1), m.group(2)
        meta: dict = {}
        for line in fm_text.splitlines():
            if not line.strip() or ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
        return cls(
            name=meta.pop("name", Path(path).parent.name),
            description=meta.pop("description", ""),
            version=meta.pop("version", ""),
            tier=meta.pop("tier", ""),
            category=meta.pop("category", ""),
            framework=meta.pop("framework", ""),
            license=meta.pop("license", ""),
            body=body.lstrip(),
            metadata=meta,
            path=str(path),
        )


class SkillRegistry:
    def __init__(self, skills: list[Skill]):
        self._by_name: dict[str, Skill] = {s.name: s for s in skills}

    @classmethod
    def load(cls, root: str | os.PathLike) -> "SkillRegistry":
        root_p = Path(root)
        skills: list[Skill] = []
        for skill_md in root_p.glob("*/SKILL.md"):
            try:
                skills.append(Skill.from_file(skill_md))
            except ValueError as e:
                # Skip malformed; surface as a warning in real use.
                print(f"warn: {e}")
        return cls(skills)

    def __getitem__(self, name: str) -> Skill:
        return self._by_name[name]

    def get(self, name: str, default=None):
        return self._by_name.get(name, default)

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def __iter__(self) -> Iterator[Skill]:
        return iter(self._by_name.values())

    def __len__(self) -> int:
        return len(self._by_name)

    def tier(self, t: str) -> list[Skill]:
        return [s for s in self if s.tier == t]

    def category(self, c: str) -> list[Skill]:
        return [s for s in self if s.category == c]

    def names(self) -> list[str]:
        return sorted(self._by_name)


if __name__ == "__main__":
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    reg = SkillRegistry.load(root)
    print(f"loaded {len(reg)} skills from {root}")
    by_tier = {}
    for s in reg:
        by_tier.setdefault(s.tier, 0)
        by_tier[s.tier] += 1
    for t in sorted(by_tier):
        print(f"  {t}: {by_tier[t]}")
