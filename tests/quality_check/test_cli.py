"""Tests for quality check CLI."""

from __future__ import annotations

import json
import textwrap

from typer.testing import CliRunner

from skill_infra.quality_check.cli import app

runner = CliRunner()


def _create_skill_md(tmp_path, description: str = "desc", body: str = ""):
    skill_md = tmp_path / "SKILL.md"
    parts = [
        "---",
        "name: test-skill",
        f"description: {description}",
        "version: 1.0.0",
        "triggers:",
        "  - test trigger",
        "---",
        "",
        body,
    ]
    content = "\n".join(parts)
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


class TestQualityCheckCLI:
    def test_check_basic(self, tmp_path) -> None:
        skill_md = _create_skill_md(
            tmp_path,
            description="Analyze code performance using rte_memcpy",
            body=textwrap.dedent("""\
                ## Output Format

                JSON with fields: score, reason.

                ## Error Handling

                If tool not available, skip and continue.

                ## Examples

                Example: analyze rte_memcpy on ARM.
            """),
        )
        result = runner.invoke(app, [str(skill_md)])
        # Only check output content, not exit_code (depends on score threshold)
        assert "test-skill" in result.output
        assert "trigger" in result.output.lower()

    def test_check_json_output(self, tmp_path) -> None:
        skill_md = _create_skill_md(tmp_path)
        result = runner.invoke(app, [str(skill_md), "--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["skill_name"] == "test-skill"
        assert "overall_score" in data
        assert "dimensions" in data

    def test_check_nonexistent_file(self, tmp_path) -> None:
        result = runner.invoke(app, [str(tmp_path / "nonexistent.md")])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()
