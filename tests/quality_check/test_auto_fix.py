"""Tests for AutoFixSuggester: response parsing, file application, availability."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skill_infra.quality_check.auto_fix import AutoFixResult, AutoFixSuggester, SuggestResult
from skill_infra.quality_check.cli import app
from skill_infra.quality_check.parser import ParsedSkill, SkillMeta
from skill_infra.quality_check.scorecard import DimensionScore, QualityReport

runner = CliRunner()


def _make_parsed(name: str = "test", description: str = "A test skill") -> ParsedSkill:
    return ParsedSkill(
        meta=SkillMeta(name=name, description=description, version="0.1.0", triggers=["test"]),
        sections=[],
        raw_body="# Test\n\n## Description\nA test skill for quality checks.\n\n## Usage\nRun it.",
        total_lines=10,
        token_estimate=50,
    )


def _make_report(
    parsed: ParsedSkill,
    dimensions: list[DimensionScore] | None = None,
) -> QualityReport:
    if dimensions is None:
        dimensions = [
            DimensionScore(name="trigger_precision", score=0.3, findings=["No clear triggers"]),
            DimensionScore(name="output_completeness", score=0.8, findings=["Has output examples"]),
            DimensionScore(name="rule_specificity", score=0.6, findings=["Some rules"]),
            DimensionScore(name="error_recovery", score=0.2, findings=["No error handling"]),
            DimensionScore(name="example_quality", score=0.7, findings=["Has examples"]),
            DimensionScore(name="conciseness", score=0.9, findings=["Concise"]),
            DimensionScore(name="consistency", score=0.8, findings=["Consistent"]),
            DimensionScore(name="edge_cases", score=0.4, findings=["Few edge cases"]),
        ]
    return QualityReport.from_dimensions(
        skill_name=parsed.meta.name,
        dimensions=dimensions,
        file_path="/fake/path/SKILL.md",
        total_lines=parsed.total_lines,
        token_estimate=parsed.token_estimate,
    )


def _valid_suggestions_json() -> str:
    suggestions = [
        {
            "dimension": "trigger_precision",
            "score": 0.3,
            "suggestion": "Add more specific trigger phrases to the description.",
            "replace": "description: A test skill",
            "replace_with": "description: Triggered by 'analyze' and 'profile' keywords",
        },
        {
            "dimension": "error_recovery",
            "score": 0.2,
            "suggestion": "Add error recovery section with retry logic.",
            "replace": "## Usage",
            "replace_with": "## Error Handling\nRetry 3 times on failure.\n\n## Usage",
        },
        {
            "dimension": "edge_cases",
            "score": 0.4,
            "suggestion": "Document null input behavior.",
            "replace": "Run it.",
            "replace_with": "Run it. Returns empty list for null input.",
        },
    ]
    return json.dumps(suggestions)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class TestAutoFixSuggesterAvailability:
    def test_not_available_without_token(self) -> None:
        suggester = AutoFixSuggester(github_token="")
        assert suggester.is_available() is False

    def test_available_with_token(self) -> None:
        suggester = AutoFixSuggester(github_token="gh_test")
        assert suggester.is_available() is True

    def test_suggest_without_token_returns_empty(self) -> None:
        parsed = _make_parsed()
        report = _make_report(parsed)
        suggester = AutoFixSuggester(github_token="")
        result = suggester.suggest(report, parsed)
        assert len(result.suggestions) == 0
        assert "No GITHUB_TOKEN" in result.apply_error


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestAutoFixSuggesterParsing:
    def test_parse_valid_response(self) -> None:
        response = _valid_suggestions_json()
        results = AutoFixSuggester._parse_response(response)
        assert len(results) == 3
        assert results[0].dimension == "trigger_precision"
        assert results[0].score == 0.3
        assert results[0].replace == "description: A test skill"
        assert results[0].replace_with == (
            "description: Triggered by 'analyze' and 'profile' keywords"
        )

    def test_parse_with_markdown_fence(self) -> None:
        response = "```json\n" + _valid_suggestions_json() + "\n```"
        results = AutoFixSuggester._parse_response(response)
        assert len(results) == 3

    def test_parse_empty_array(self) -> None:
        results = AutoFixSuggester._parse_response("[]")
        assert len(results) == 0

    def test_parse_invalid_json(self) -> None:
        results = AutoFixSuggester._parse_response("not json")
        assert len(results) == 0

    def test_parse_not_a_list(self) -> None:
        results = AutoFixSuggester._parse_response('{"dimension":"test"}')
        assert len(results) == 0

    def test_parse_skips_missing_fields(self) -> None:
        data = [
            {"dimension": "trigger_precision", "suggestion": "fix it"},
            {
                "dimension": "error_recovery",
                "score": 0.2,
                "suggestion": "Add error recovery",
                "replace": "old",
                "replace_with": "new",
            },
        ]
        response = json.dumps(data)
        results = AutoFixSuggester._parse_response(response)
        assert len(results) == 1  # only the complete entry

    def test_parse_ignores_extra_fields(self) -> None:
        data = [
            {
                "dimension": "test_dim",
                "score": 0.5,
                "suggestion": "Improve it",
                "replace": "old text",
                "replace_with": "new text",
                "extra": "ignored",
            }
        ]
        results = AutoFixSuggester._parse_response(json.dumps(data))
        assert len(results) == 1
        assert results[0].dimension == "test_dim"

    def test_parse_clamps_score(self) -> None:
        data = [
            {
                "dimension": "test",
                "score": 5.0,
                "suggestion": "Fix it",
                "replace": "old",
                "replace_with": "new",
            }
        ]
        results = AutoFixSuggester._parse_response(json.dumps(data))
        assert results[0].score == 1.0  # clamped

        data2 = [
            {
                "dimension": "test",
                "score": -1.0,
                "suggestion": "Fix it",
                "replace": "old",
                "replace_with": "new",
            }
        ]
        results2 = AutoFixSuggester._parse_response(json.dumps(data2))
        assert results2[0].score == 0.0  # clamped


# ---------------------------------------------------------------------------
# Apply suggestions
# ---------------------------------------------------------------------------


class TestAutoFixSuggesterApply:
    def test_apply_suggestion_to_file(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "SKILL.md"
        content = "description: A test skill\n\n## Usage\nRun it."
        skill_file.write_text(content, encoding="utf-8")

        suggestions = [
            SuggestResult(
                dimension="trigger_precision",
                score=0.3,
                suggestion="Add better description",
                replace="description: A test skill",
                replace_with="description: Better description",
            ),
            SuggestResult(
                dimension="error_recovery",
                score=0.2,
                suggestion="Add error handling",
                replace="## Usage",
                replace_with="## Error Handling\nRetry on failure.\n\n## Usage",
            ),
        ]

        result = AutoFixResult(skill_name="test", suggestions=suggestions)
        AutoFixSuggester._apply_suggestions(result, skill_file)

        assert result.applied_count == 2
        assert result.failed_count == 0
        assert result.backup_path != ""
        assert Path(result.backup_path).exists()

        updated = skill_file.read_text(encoding="utf-8")
        assert "Better description" in updated
        assert "Error Handling" in updated

    def test_apply_suggestion_not_found(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("description: A test skill\n", encoding="utf-8")

        suggestions = [
            SuggestResult(
                dimension="trigger_precision",
                score=0.3,
                suggestion="Fix description",
                replace="text that does not exist in file",
                replace_with="replacement text",
            ),
        ]

        result = AutoFixResult(skill_name="test", suggestions=suggestions)
        AutoFixSuggester._apply_suggestions(result, skill_file)

        assert result.applied_count == 0
        assert result.failed_count == 1
        assert "not found" in suggestions[0].error

    def test_apply_creates_backup(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "SKILL.md"
        original = "description: Original content"
        skill_file.write_text(original, encoding="utf-8")

        suggestions = [
            SuggestResult(
                dimension="test",
                score=0.5,
                suggestion="Change",
                replace="description: Original content",
                replace_with="description: Changed content",
            ),
        ]

        result = AutoFixResult(skill_name="test", suggestions=suggestions)
        AutoFixSuggester._apply_suggestions(result, skill_file)

        backup_path = Path(result.backup_path)
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == original

    def test_apply_nonexistent_file(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "nonexistent.md"
        suggestions = [
            SuggestResult(
                dimension="test",
                score=0.5,
                suggestion="Fix",
                replace="old",
                replace_with="new",
            ),
        ]

        result = AutoFixResult(skill_name="test", suggestions=suggestions)
        AutoFixSuggester._apply_suggestions(result, skill_file)

        assert result.apply_error != ""
        assert "not found" in result.apply_error.lower()

    def test_apply_single_suggestion(self, tmp_path: Path) -> None:
        skill_file = tmp_path / "SKILL.md"
        skill_file.write_text("old text here\n", encoding="utf-8")

        suggestions = [
            SuggestResult(
                dimension="test",
                score=0.5,
                suggestion="Replace old text",
                replace="old text here",
                replace_with="new text here",
            ),
        ]

        result = AutoFixResult(skill_name="test", suggestions=suggestions)
        AutoFixSuggester._apply_suggestions(result, skill_file)

        assert result.applied_count == 1
        assert skill_file.read_text(encoding="utf-8") == "new text here\n"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestAutoFixCLI:
    def _create_skill_md(self, tmp_path: Path, description: str = "test skill") -> Path:
        skill_file = tmp_path / "SKILL.md"
        parts = [
            "---",
            f"description: {description}",
            "name: test-skill",
            "version: 1.0.0",
            "triggers:",
            "  - test trigger",
            "---",
            "",
            "## Description",
            "A basic test skill.",
            "",
            "## Usage",
            "Run the tool.",
        ]
        skill_file.write_text("\n".join(parts), encoding="utf-8")
        return skill_file

    def test_suggest_no_token(self, tmp_path: Path) -> None:
        skill_file = self._create_skill_md(tmp_path)
        result = runner.invoke(app, ["suggest", str(skill_file)])
        assert result.exit_code != 0
        # Should report missing GITHUB_TOKEN
        assert "GITHUB_TOKEN" in result.output

    def test_suggest_nonexistent_file(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["suggest", str(tmp_path / "nonexistent.md")])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_suggest_requires_token_for_suggestions(self, tmp_path: Path) -> None:
        """Without GITHUB_TOKEN, suggest command exits with error."""
        skill_file = self._create_skill_md(tmp_path)
        result = runner.invoke(app, ["suggest", str(skill_file)])
        assert result.exit_code != 0
        assert result.output.strip() != ""

    def test_suggest_help_shown(self) -> None:
        result = runner.invoke(app, ["suggest", "--help"])
        assert result.exit_code == 0
        assert "suggest" in result.output.lower()
        assert "apply" in result.output.lower()
