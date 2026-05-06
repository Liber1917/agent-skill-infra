"""Tests for CapabilityDiscoverer: fallback, parsing, API response handling."""

from __future__ import annotations

import json

from skill_infra.quality_check.capability_discovery import (
    Capability,
    CapabilityDiscoverer,
    CapabilityReport,
)
from skill_infra.quality_check.parser import ParsedSkill, SkillMeta


def _make_parsed(
    name: str = "test",
    description: str = "A test skill",
    triggers: list[str] | None = None,
    body: str = "",
) -> ParsedSkill:
    body = body or "# Test\n\nQuality test skill.\n\n## Example\n```\nexample\n```"
    return ParsedSkill(
        meta=SkillMeta(
            name=name,
            description=description,
            version="0.1.0",
            triggers=triggers or ["test"],
        ),
        sections=[],
        raw_body=body,
        total_lines=10,
        token_estimate=50,
    )


class TestCapabilityDiscoverer:
    def test_fallback_when_no_token(self) -> None:
        discoverer = CapabilityDiscoverer(github_token="")
        parsed = _make_parsed()
        report = discoverer.discover(parsed)
        assert report.skill_name == "test"
        assert "keyword-based fallback" in report.summary.lower()

    def test_is_available_false_without_token(self) -> None:
        discoverer = CapabilityDiscoverer(github_token="")
        assert discoverer.is_available() is False

    def test_is_available_true_with_token(self) -> None:
        discoverer = CapabilityDiscoverer(github_token="gh_test")
        assert discoverer.is_available() is True

    def test_env_token_detection(self) -> None:
        import os

        os.environ["GITHUB_TOKEN"] = "test-token"
        try:
            discoverer = CapabilityDiscoverer()
            assert discoverer.is_available() is True
        finally:
            del os.environ["GITHUB_TOKEN"]

    def test_parse_valid_response(self) -> None:
        response = json.dumps(
            {
                "summary": "Skill handles code analysis and review",
                "capabilities": [
                    {
                        "name": "code_review",
                        "description": "Review code for bugs and style issues",
                        "is_current": True,
                        "confidence": 0.9,
                        "evidence": ["Has review workflow section"],
                        "expansion_suggestion": "Add automated fix suggestions",
                    },
                    {
                        "name": "performance_analysis",
                        "description": "Analyze code performance patterns",
                        "is_current": False,
                        "confidence": 0.6,
                        "evidence": ["Mentions profiling tools"],
                        "expansion_suggestion": "Add performance benchmarks",
                    },
                ],
            }
        )
        data = CapabilityDiscoverer._parse_response(response)
        report = CapabilityReport.from_api_response(data, skill_name="test")
        assert len(report.capabilities) == 2
        assert report.total_current == 1
        assert report.total_potential == 1
        assert report.capabilities[0].name == "code_review"
        assert report.capabilities[0].is_current is True
        assert report.capabilities[0].confidence == 0.9
        assert report.capabilities[1].name == "performance_analysis"
        assert report.capabilities[1].is_current is False

    def test_parse_markdown_fence(self) -> None:
        resp = '```json\n{"summary":"test","capabilities":[]}\n```'
        data = CapabilityDiscoverer._parse_response(resp)
        assert data["summary"] == "test"
        assert data["capabilities"] == []

    def test_invalid_json_graceful(self) -> None:
        data = CapabilityDiscoverer._parse_response("not json")
        assert "Failed to parse" in data["summary"]
        assert data["capabilities"] == []

    def test_confidence_clamping(self) -> None:
        response = json.dumps(
            {
                "summary": "Test clamping",
                "capabilities": [
                    {
                        "name": "high_confidence",
                        "description": "Over 1.0",
                        "is_current": True,
                        "confidence": 1.5,
                        "evidence": [],
                        "expansion_suggestion": "",
                    },
                    {
                        "name": "low_confidence",
                        "description": "Below 0.0",
                        "is_current": False,
                        "confidence": -0.5,
                        "evidence": [],
                        "expansion_suggestion": "",
                    },
                ],
            }
        )
        data = CapabilityDiscoverer._parse_response(response)
        report = CapabilityReport.from_api_response(data)
        assert abs(report.capabilities[0].confidence - 1.0) < 0.01
        assert abs(report.capabilities[1].confidence - 0.0) < 0.01


class TestCapabilityReport:
    def test_empty_report(self) -> None:
        report = CapabilityReport()
        assert report.capabilities == []
        assert report.total_current == 0
        assert report.total_potential == 0

    def test_from_empty_api_response(self) -> None:
        report = CapabilityReport.from_api_response({"capabilities": []}, skill_name="test")
        assert report.total_current == 0
        assert report.total_potential == 0
        assert report.skill_name == "test"

    def test_from_api_with_dimension_fallback(self) -> None:
        data = {
            "dimensions": [
                {
                    "name": "my_cap",
                    "description": "A cap",
                    "is_current": True,
                    "confidence": 0.8,
                    "evidence": ["line 1"],
                    "expansion_suggestion": "improve",
                },
            ],
        }
        report = CapabilityReport.from_api_response(data)
        assert len(report.capabilities) == 1
        assert report.capabilities[0].name == "my_cap"


class TestFallbackDiscovery:
    def test_fallback_extracts_section_headings(self) -> None:
        body = "## Code Review\nReview code.\n\n## Testing\nTest the code."
        parsed = ParsedSkill(
            meta=SkillMeta(name="test", description="A review skill", triggers=[]),
            sections=[
                {"title": "Code Review", "body": "Review code."},
                {"title": "Testing", "body": "Test the code."},
            ],
            raw_body=body,
        )
        report = CapabilityDiscoverer._fallback_discover(parsed)
        assert report.total_current >= 2
        current_names = [c.name for c in report.capabilities if c.is_current]
        assert "code_review" in current_names
        assert "testing" in current_names

    def test_fallback_analyze_keyword(self) -> None:
        parsed = ParsedSkill(
            meta=SkillMeta(name="test", description="Analyze data patterns", triggers=[]),
            sections=[],
            raw_body="# Test\n\nSimple skill.",
        )
        report = CapabilityDiscoverer._fallback_discover(parsed)
        potential_names = [c.name for c in report.capabilities if not c.is_current]
        assert "data_analysis" in potential_names

    def test_fallback_generate_keyword(self) -> None:
        parsed = ParsedSkill(
            meta=SkillMeta(name="test", description="Create and generate content", triggers=[]),
            sections=[],
            raw_body="# Test\n\nSimple skill.",
        )
        report = CapabilityDiscoverer._fallback_discover(parsed)
        potential_names = [c.name for c in report.capabilities if not c.is_current]
        assert "content_generation" in potential_names

    def test_fallback_catchall_when_no_potential(self) -> None:
        parsed = ParsedSkill(
            meta=SkillMeta(
                name="test",
                description="A simple tool",
                triggers=[],
            ),
            sections=[],
            raw_body="# Test\n\nJust a simple tool.",
        )
        report = CapabilityDiscoverer._fallback_discover(parsed)
        potential_names = [c.name for c in report.capabilities if not c.is_current]
        assert "domain_expansion" in potential_names


class TestCapabilityDataclass:
    def test_default_fields(self) -> None:
        cap = Capability(
            name="test_cap",
            description="A capability",
            is_current=True,
            confidence=0.8,
        )
        assert cap.evidence == []
        assert cap.expansion_suggestion == ""

    def test_all_fields(self) -> None:
        cap = Capability(
            name="code_review",
            description="Review code",
            is_current=True,
            confidence=0.9,
            evidence=["Has review section", "Uses linter"],
            expansion_suggestion="Add automated fixing",
        )
        assert cap.name == "code_review"
        assert len(cap.evidence) == 2
        assert cap.expansion_suggestion == "Add automated fixing"
