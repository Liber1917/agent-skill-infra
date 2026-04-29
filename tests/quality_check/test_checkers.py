"""Tests for quality check sub-checkers."""

from __future__ import annotations

import textwrap

from skill_infra.quality_check.checkers import (
    HelloAndyChecker,
    OutputChecker,
    TokenChecker,
    ToleranceChecker,
    TriggerChecker,
)
from skill_infra.quality_check.parser import ParsedSkill
from skill_infra.quality_check.scorecard import DimensionScore
from skill_infra.shared.types import SkillMeta


def _parsed(name: str = "test", description: str = "", body: str = "") -> ParsedSkill:
    return ParsedSkill(
        meta=SkillMeta(name=name, description=description),
        sections=[],
        raw_body=body,
        total_lines=len(body.splitlines()) if body else 0,
        token_estimate=len(body) // 4,
    )


class TestTriggerChecker:
    def test_good_description(self) -> None:
        ps = _parsed(description="Analyze code performance using rte_memcpy and Neon intrinsics")
        result = TriggerChecker().check(ps)
        assert result.score >= 0.5
        assert isinstance(result, DimensionScore)

    def test_empty_description(self) -> None:
        ps = _parsed(description="")
        result = TriggerChecker().check(ps)
        assert result.score == 0.0
        assert any("empty" in f.lower() for f in result.findings)

    def test_vague_description(self) -> None:
        ps = _parsed(description="A helpful tool")
        result = TriggerChecker().check(ps)
        assert result.score < 0.5


class TestOutputChecker:
    def test_has_output_section(self) -> None:
        ps = _parsed(body="## Output Format\n\nJSON with fields: score, reason, details")
        result = OutputChecker().check(ps)
        assert result.score >= 0.3
        assert any("format" in f.lower() for f in result.findings)

    def test_no_output_section(self) -> None:
        ps = _parsed(body="## Introduction\n\nSome intro text")
        result = OutputChecker().check(ps)
        assert result.score == 0.0
        assert any("output" in f.lower() for f in result.findings)

    def test_has_examples(self) -> None:
        ps = _parsed(body='## Examples\n\nExample output:\n```json\n{"score": 0.9}\n```')
        result = OutputChecker().check(ps)
        assert result.score >= 0.7


class TestToleranceChecker:
    def test_has_error_handling(self) -> None:
        body = "## Error Handling\n\nIf the tool is not available, skip and continue."
        ps = _parsed(body=body)
        result = ToleranceChecker().check(ps)
        assert result.score >= 0.5

    def test_no_error_handling(self) -> None:
        ps = _parsed(body="## Steps\n\n1. Do this\n2. Do that")
        result = ToleranceChecker().check(ps)
        assert result.score == 0.0

    def test_has_try_catch_keywords(self) -> None:
        body = textwrap.dedent("""\
            ## Error Recovery

            If the API call fails, retry up to 3 times with exponential backoff.
            If the file is not found, return a helpful error message.
        """)
        ps = _parsed(body=body)
        result = ToleranceChecker().check(ps)
        assert result.score >= 0.7


class TestTokenChecker:
    def test_short_content(self) -> None:
        ps = _parsed(body="short content" * 10)
        result = TokenChecker().check(ps)
        assert result.score >= 0.5

    def test_long_content(self) -> None:
        ps = _parsed(body="long line\n" * 600)
        assert ps.total_lines >= 500
        result = TokenChecker().check(ps)
        assert result.score < 1.0
        assert any("long" in f.lower() or "split" in f.lower() for f in result.findings)

    def test_empty_content(self) -> None:
        ps = _parsed(body="")
        result = TokenChecker().check(ps)
        assert result.score == 1.0  # empty is trivially within limits


class TestHelloAndyChecker:
    def test_good_skill(self) -> None:
        body = textwrap.dedent("""\
            ## What This Skill Does

            Analyzes code performance using rte_memcpy.

            ## Triggers

            When user asks about performance optimization, memcpy, or Neon.

            ## Output Format

            JSON with fields: analysis, recommendation, benchmark.

            ## Error Handling

            If file not found, return error message. If analysis fails, provide partial results.

            ## Examples

            Example: analyze rte_memcpy performance on ARM.

            ## Constraints

            Must use objdump for verification.
        """)
        ps = _parsed(description="Analyze code performance using rte_memcpy", body=body)
        result = HelloAndyChecker().check(ps)
        assert result.score >= 0.5
        assert len(result.findings) > 0

    def test_minimal_skill(self) -> None:
        ps = _parsed(description="A tool", body="## Intro\nMinimal")
        result = HelloAndyChecker().check(ps)
        assert result.score < 0.5
