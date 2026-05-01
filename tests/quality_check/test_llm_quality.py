"""Tests for LLMQualityChecker: fallback, API mock, response parsing."""

from __future__ import annotations

import json

from skill_infra.quality_check.llm_quality import LLMQualityChecker
from skill_infra.quality_check.parser import ParsedSkill, SkillMeta


def _make_parsed(name: str = "test-skill", description: str = "A test skill") -> ParsedSkill:
    return ParsedSkill(
        meta=SkillMeta(
            name=name,
            description=description,
            version="0.1.0",
            triggers=["test"],
        ),
        sections=[],
        raw_body=(
            "# Test\n\nThis is a test skill.\n\n"
            "## Output\n\nOutput format.\n\n"
            "## Example\n\n```\nexample\n```"
        ),
        total_lines=10,
        token_estimate=50,
    )


class TestLLMQualityChecker:
    def test_fallback_when_no_api_key(self) -> None:
        """Without API key, falls back to keyword-based checker."""
        checker = LLMQualityChecker(api_key="")
        parsed = _make_parsed()

        result = checker.check(parsed)
        assert result.name == "helloandy_8dim"  # fallback renames it
        assert "keyword-based fallback" in result.findings[0]
        assert 0.0 <= result.score <= 1.0

    def test_is_available_false_without_key(self) -> None:
        checker = LLMQualityChecker(api_key="")
        assert checker.is_available() is False

    def test_is_available_true_with_key(self) -> None:
        checker = LLMQualityChecker(api_key="sk-test")
        assert checker.is_available() is True

    def test_parse_valid_response(self) -> None:
        """_parse_response handles valid JSON with 8 dimensions."""
        response = json.dumps(
            {
                "dimensions": [
                    {"name": "trigger_precision", "score": 0.9, "findings": ["Clear triggers"]},
                    {
                        "name": "output_completeness",
                        "score": 0.8,
                        "findings": ["Has output format"],
                    },
                    {"name": "rule_specificity", "score": 0.7, "findings": ["Has rules"]},
                    {"name": "error_recovery", "score": 0.6, "findings": ["Some fallback"]},
                    {"name": "example_quality", "score": 0.8, "findings": ["Has examples"]},
                    {"name": "conciseness", "score": 0.7, "findings": ["Compact"]},
                    {"name": "consistency", "score": 0.9, "findings": ["Consistent"]},
                    {"name": "edge_cases", "score": 0.5, "findings": ["Few edge cases"]},
                ],
                "overall_score": 0.7375,
            }
        )

        result = LLMQualityChecker._parse_response(response)
        assert result.name == "helloandy_8dim_llm"
        assert abs(result.score - 0.7375) < 0.01
        assert len(result.findings) == 8

    def test_parse_response_with_markdown_fence(self) -> None:
        resp = (
            '```json\n{"dimensions":[{"name":"t","score":0.5,"findings":["x"]}]'
            ',"overall_score":0.5}\n```'
        )
        result = LLMQualityChecker._parse_response(resp)
        assert result.score == 0.5

    def test_parse_invalid_json_returns_graceful(self) -> None:
        result = LLMQualityChecker._parse_response("not json at all")
        assert result.score == 0.5
        assert "invalid JSON" in result.findings[0]

    def test_parse_empty_response(self) -> None:
        result = LLMQualityChecker._parse_response("")
        assert result.score == 0.5

    def test_scores_clamped_to_range(self) -> None:
        """Scores are clamped to 0.0-1.0."""
        response = json.dumps(
            {
                "dimensions": [
                    {"name": "a", "score": 1.5, "findings": []},
                    {"name": "b", "score": -0.5, "findings": []},
                ],
                "overall_score": 0.5,
            }
        )
        result = LLMQualityChecker._parse_response(response)
        assert 0.0 <= result.score <= 1.0

    def test_cjk_skill_score_is_reasonable(self) -> None:
        """Ensure CJK (Chinese) description doesn't break fallback."""
        checker = LLMQualityChecker(api_key="")
        parsed = _make_parsed(
            name="nuwa-skill",
            description="女娲造人: 输入人名自动深度调研",
        )
        result = checker.check(parsed)
        # Fallback should work regardless of language
        assert result.name in ("helloandy_8dim", "helloandy_8dim_llm")
        assert 0.0 <= result.score <= 1.0

    def test_no_api_key_checked_correctly(self) -> None:
        """is_available is False for None API key."""
        checker = LLMQualityChecker(api_key=None)
        assert checker.is_available() is False
