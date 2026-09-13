"""Structure checks for the methodology skills shipped under `agentic_evals/skills/`.

These are documentation/guidance cards (Trigger/Do/Avoid/Check/Risk), not
runnable code -- this test verifies the format is intact, not the content.
"""

from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).parent.parent / "src" / "agentic_evals" / "skills"
REQUIRED_SECTIONS = ["## Trigger", "## Do", "## Avoid", "## Check", "## Risk"]


def _skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())


def test_at_least_one_skill_is_shipped() -> None:
    assert _skill_dirs(), "expected at least one skill directory under agentic_evals/skills/"


def test_every_skill_has_a_well_formed_skill_md() -> None:
    for skill_dir in _skill_dirs():
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.is_file(), f"{skill_dir} is missing SKILL.md"

        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---\n"), f"{skill_md} must start with YAML frontmatter"

        _, frontmatter_raw, body = text.split("---\n", 2)
        frontmatter = yaml.safe_load(frontmatter_raw)

        assert frontmatter.get("name") == skill_dir.name, (
            f"{skill_md}'s frontmatter name must match its directory name"
        )
        assert frontmatter.get("description"), f"{skill_md} must set a non-empty description"

        for section in REQUIRED_SECTIONS:
            assert section in body, f"{skill_md} is missing the {section!r} section"
