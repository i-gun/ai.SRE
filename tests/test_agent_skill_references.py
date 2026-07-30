"""Guard tests: every `skills:` entry in an agent file must resolve to a real SKILL.md.

These are static checks over ``.github/agents/*.agent.md`` — no agent execution.
They prevent regression of broken skill references in agent frontmatter.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = PROJECT_ROOT / ".github" / "agents"
SKILLS_DIR = PROJECT_ROOT / ".github" / "skills"

_SKILLS_LINE = re.compile(r"^skills:\s*\[(?P<items>.*?)\]\s*$", re.MULTILINE)


def _extract_frontmatter(content: str) -> str:
    """Return the YAML frontmatter block (between the first two '---' fences)."""
    if not content.startswith("---"):
        return ""
    end = content.find("\n---", 3)
    return content[3:end] if end != -1 else ""


def _parse_skill_names(content: str) -> list[str]:
    """Parse the inline ``skills: [a, b, c]`` list from an agent's frontmatter."""
    frontmatter = _extract_frontmatter(content)
    match = _SKILLS_LINE.search(frontmatter)
    if not match:
        return []
    raw = match.group("items")
    return [name.strip().strip("'\"") for name in raw.split(",") if name.strip()]


def _agent_files() -> list[Path]:
    return sorted(AGENTS_DIR.glob("*.agent.md"))


class TestAgentSkillReferences(unittest.TestCase):
    """Validate skill references declared in agent frontmatter."""

    def test_agents_directory_exists(self) -> None:
        self.assertTrue(AGENTS_DIR.is_dir(), f"Expected {AGENTS_DIR} to exist")

    def test_agent_files_present(self) -> None:
        self.assertTrue(_agent_files(), "Expected at least one *.agent.md file")

    def test_declared_skills_resolve_to_skill_md(self) -> None:
        """Each declared skill must map to .github/skills/<name>/SKILL.md."""
        missing: list[str] = []
        for agent_file in _agent_files():
            content = agent_file.read_text(encoding="utf-8")
            for skill_name in _parse_skill_names(content):
                skill_md = SKILLS_DIR / skill_name / "SKILL.md"
                if not skill_md.is_file():
                    missing.append(f"{agent_file.name}: '{skill_name}' -> {skill_md}")
        self.assertEqual(
            missing,
            [],
            "Agent files reference skills without a matching SKILL.md:\n"
            + "\n".join(missing),
        )

    def test_skills_line_is_wellformed_when_present(self) -> None:
        """A `skills:` key, if present, must use a non-empty inline list."""
        malformed: list[str] = []
        for agent_file in _agent_files():
            frontmatter = _extract_frontmatter(agent_file.read_text(encoding="utf-8"))
            for line in frontmatter.splitlines():
                if line.strip().startswith("skills:"):
                    if not _SKILLS_LINE.match(line.strip()):
                        malformed.append(f"{agent_file.name}: {line.strip()!r}")
                    elif not _parse_skill_names(agent_file.read_text(encoding="utf-8")):
                        malformed.append(f"{agent_file.name}: empty skills list")
        self.assertEqual(
            malformed,
            [],
            "Agent files have malformed/empty `skills:` declarations:\n"
            + "\n".join(malformed),
        )


if __name__ == "__main__":
    unittest.main()
