"""SKILL.md parser: extracts metadata and sections from SKILL.md files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from skill_infra.shared.types import SkillMeta

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ParsedSkill:
    """Result of parsing a SKILL.md file."""

    meta: SkillMeta
    sections: list[dict[str, str]] = field(default_factory=list)
    raw_body: str = ""
    total_lines: int = 0
    token_estimate: int = 0


# ---------------------------------------------------------------------------
# Parsing logic
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)",
    re.DOTALL,
)

_SECTION_RE = re.compile(
    r"^##\s+(.+?)$\n(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)


def parse_skill_md(path: str | Path) -> ParsedSkill:
    """Parse a SKILL.md file into structured data.

    Extracts YAML front matter (name, description, version, triggers)
    and splits the Markdown body into sections by ``##`` headings.

    Args:
        path: Path to the SKILL.md file.

    Returns:
        ParsedSkill with metadata, sections, and stats.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Skill file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    total_lines = len(content.strip().splitlines()) if content.strip() else 0

    # Token estimate: ~4 chars per token (rough heuristic for English)
    token_estimate = len(content) // 4

    # Try to extract YAML front matter
    match = _FRONTMATTER_RE.match(content)
    front_matter_raw = ""
    body = content

    if match:
        front_matter_raw = match.group(1)
        body = match.group(2)

    # Parse front matter fields (simple line-by-line, not full YAML parser)
    meta = _parse_front_matter(front_matter_raw, file_path.stem)

    # Split body into sections by ## headings
    sections = _parse_sections(body)

    return ParsedSkill(
        meta=meta,
        sections=sections,
        raw_body=body.strip(),
        total_lines=total_lines,
        token_estimate=token_estimate,
    )


def _parse_front_matter(raw: str, fallback_name: str) -> SkillMeta:
    """Parse simple YAML-like front matter into SkillMeta.

    Only handles flat key-value pairs and simple lists. Not a full YAML parser.
    """
    name: str = fallback_name
    description: str = ""
    version: str = "0.0.0"
    triggers: list[str] = []

    if not raw.strip():
        return SkillMeta(
            name=name,
            description=description,
            version=version,
            triggers=triggers,
        )

    current_list_key: str | None = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            current_list_key = None
            continue

        # List item (e.g., "  - trigger phrase")
        if stripped.startswith("- "):
            if current_list_key == "triggers":
                triggers.append(stripped[2:].strip())
            continue

        # Key-value pair
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "name" and value:
                name = value
                current_list_key = None
            elif key == "description" and value:
                description = value
                current_list_key = None
            elif key == "version" and value:
                version = value
                current_list_key = None
            elif key == "triggers":
                if value:
                    # Inline triggers: "triggers: single trigger"
                    triggers.append(value)
                else:
                    # List follows
                    current_list_key = "triggers"
            else:
                current_list_key = None

    return SkillMeta(
        name=name,
        description=description,
        version=version,
        triggers=triggers,
    )


def _parse_sections(body: str) -> list[dict[str, str]]:
    """Split Markdown body by ## headings into a list of {title, body} dicts."""
    if not body.strip():
        return []

    sections: list[dict[str, str]] = []
    for m in _SECTION_RE.finditer(body):
        title = m.group(1).strip()
        section_body = m.group(2).strip()
        sections.append({"title": title, "body": section_body})

    return sections
