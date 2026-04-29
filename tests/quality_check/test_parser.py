"""Tests for SKILL.md parser."""

from __future__ import annotations

import textwrap

import pytest

from skill_infra.quality_check.parser import parse_skill_md


class TestParseSkillMd:
    """Tests for parse_skill_md."""

    def test_parse_basic_skill_md(self, tmp_path) -> None:
        """Parse a standard SKILL.md with YAML front matter."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            textwrap.dedent("""\
                ---
                name: my-skill
                description: A skill for doing X with Y
                version: 1.0.0
                triggers:
                  - do X
                  - help with Y
                ---

                ## What This Skill Does

                This skill helps users do X with Y.

                ## How to Use

                1. Trigger with "do X"
                2. Follow the steps
            """),
            encoding="utf-8",
        )

        result = parse_skill_md(str(skill_md))

        assert result.meta.name == "my-skill"
        assert result.meta.description == "A skill for doing X with Y"
        assert result.meta.version == "1.0.0"
        assert result.meta.triggers == ["do X", "help with Y"]

    def test_parse_no_frontmatter(self, tmp_path) -> None:
        """When no front matter, use file stem as name."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "## Some Section\n\nSome content here.",
            encoding="utf-8",
        )

        result = parse_skill_md(str(skill_md))

        assert result.meta.name == "SKILL"
        assert result.meta.description == ""
        assert result.meta.version == "0.0.0"
        assert result.sections == [{"title": "Some Section", "body": "Some content here."}]

    def test_parse_sections(self, tmp_path) -> None:
        """Markdown body is split by ## headings into sections."""
        skill_md = tmp_path / "test.md"
        skill_md.write_text(
            textwrap.dedent("""\
                ---
                name: test
                description: test skill
                version: 0.1.0
                ---

                Intro paragraph.

                ## Section One

                Content for section one.

                ## Section Two

                Content for section two.
            """),
            encoding="utf-8",
        )

        result = parse_skill_md(str(skill_md))

        assert len(result.sections) == 2
        assert result.sections[0]["title"] == "Section One"
        assert result.sections[1]["title"] == "Section Two"

    def test_parse_empty_file(self, tmp_path) -> None:
        """Empty file returns minimal ParsedSkill."""
        skill_md = tmp_path / "empty.md"
        skill_md.write_text("", encoding="utf-8")

        result = parse_skill_md(str(skill_md))

        assert result.meta.name == "empty"
        assert result.sections == []
        assert result.total_lines == 0

    def test_parse_partial_frontmatter(self, tmp_path) -> None:
        """Front matter with only some fields, others get defaults."""
        skill_md = tmp_path / "partial.md"
        skill_md.write_text(
            textwrap.dedent("""\
                ---
                name: partial-skill
                ---
            """),
            encoding="utf-8",
        )

        result = parse_skill_md(str(skill_md))

        assert result.meta.name == "partial-skill"
        assert result.meta.description == ""
        assert result.meta.version == "0.0.0"
        assert result.meta.triggers == []

    def test_parse_triggers_not_list(self, tmp_path) -> None:
        """Triggers as string gets wrapped into a list."""
        skill_md = tmp_path / "str_trigger.md"
        skill_md.write_text(
            textwrap.dedent("""\
                ---
                name: str-trigger
                description: test
                triggers: single trigger
                ---
            """),
            encoding="utf-8",
        )

        result = parse_skill_md(str(skill_md))

        assert result.meta.triggers == ["single trigger"]

    def test_file_not_found(self, tmp_path) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_skill_md(str(tmp_path / "nonexistent.md"))

    def test_total_lines_and_token_estimate(self, tmp_path) -> None:
        """total_lines counts actual lines, token_estimate is roughly 4x chars."""
        content = "line1\nline2\nline3\n"
        skill_md = tmp_path / "lines.md"
        skill_md.write_text(content, encoding="utf-8")

        result = parse_skill_md(str(skill_md))

        assert result.total_lines == 3
        # token_estimate should be roughly proportional to character count
        assert result.token_estimate > 0
