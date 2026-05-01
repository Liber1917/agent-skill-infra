"""Tests for GitHubModelQualityChecker: fallback, parsing, availability."""

from __future__ import annotations

import json

from skill_infra.quality_check.gh_model_quality import GitHubModelQualityChecker
from skill_infra.quality_check.parser import ParsedSkill, SkillMeta


def _make_parsed(name: str = "test", description: str = "A test skill") -> ParsedSkill:
    return ParsedSkill(
        meta=SkillMeta(name=name, description=description, version="0.1.0", triggers=["test"]),
        sections=[],
        raw_body="# Test\n\nQuality test skill.\n\n## Example\n```\nexample\n```",
        total_lines=10,
        token_estimate=50,
    )


class TestGitHubModelQualityChecker:
    def test_fallback_when_no_token(self) -> None:
        checker = GitHubModelQualityChecker(github_token="")
        parsed = _make_parsed()
        result = checker.check(parsed)
        assert result.name == "helloandy_8dim"
        assert "keyword-based fallback" in result.findings[0]

    def test_is_available_false_without_token(self) -> None:
        checker = GitHubModelQualityChecker(github_token="")
        assert checker.is_available() is False

    def test_is_available_true_with_token(self) -> None:
        checker = GitHubModelQualityChecker(github_token="gh_test")
        assert checker.is_available() is True

    def test_parse_valid_response(self) -> None:
        response = json.dumps(
            {
                "dimensions": [
                    {"name": "trigger_precision", "score": 0.9, "findings": ["Clear triggers"]},
                    {"name": "output_completeness", "score": 0.8, "findings": ["Has output"]},
                    {"name": "rule_specificity", "score": 0.7, "findings": ["Has rules"]},
                    {"name": "error_recovery", "score": 0.6, "findings": ["Fallback exists"]},
                    {"name": "example_quality", "score": 0.8, "findings": ["Has examples"]},
                    {"name": "conciseness", "score": 0.7, "findings": ["Compact"]},
                    {"name": "consistency", "score": 0.9, "findings": ["Consistent"]},
                    {"name": "edge_cases", "score": 0.5, "findings": ["Few edge cases"]},
                ],
                "overall_score": 0.7375,
            }
        )
        result = GitHubModelQualityChecker._parse_response(response)
        assert abs(result.score - 0.7375) < 0.01
        assert len(result.findings) == 8

    def test_parse_markdown_fence(self) -> None:
        resp = '```json\n{"dimensions":[],"overall_score":0.6}\n```'
        result = GitHubModelQualityChecker._parse_response(resp)
        assert result.score == 0.6

    def test_invalid_json_graceful(self) -> None:
        result = GitHubModelQualityChecker._parse_response("not json")
        assert result.score == 0.5

    def test_env_token_detection(self) -> None:
        import os

        os.environ["GITHUB_TOKEN"] = "test-token"
        try:
            checker = GitHubModelQualityChecker()
            assert checker.is_available() is True
        finally:
            del os.environ["GITHUB_TOKEN"]
