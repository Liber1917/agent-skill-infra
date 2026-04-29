"""Tests for shared data types."""

from __future__ import annotations

import pytest

from skill_infra.shared.types import EvalCase, EvalReport, EvalResult, SkillMeta


class TestSkillMeta:
    def test_from_dict(self) -> None:
        raw = {"name": "quality-check", "description": "Checks skill quality", "version": "1.2.0"}
        meta = SkillMeta(
            name=raw["name"],
            description=raw["description"],
            version=raw["version"],
            raw=raw,
        )
        assert meta.name == "quality-check"
        assert meta.version == "1.2.0"
        assert meta.raw == raw

    def test_default_version(self) -> None:
        meta = SkillMeta(name="test", description="desc")
        assert meta.version == "0.0.0"

    def test_default_triggers_empty(self) -> None:
        meta = SkillMeta(name="test", description="desc")
        assert meta.triggers == []


class TestEvalCase:
    def test_default_timeout(self) -> None:
        case = EvalCase(
            id="tc-001",
            prompt="hello",
            expected={"keywords": ["hi"]},
            judge_type="keyword",
        )
        assert case.timeout == 30

    def test_default_tags_empty(self) -> None:
        case = EvalCase(
            id="tc-001",
            prompt="hello",
            expected={},
            judge_type="keyword",
        )
        assert case.tags == []

    def test_custom_timeout(self) -> None:
        case = EvalCase(
            id="tc-002",
            prompt="complex",
            expected={},
            judge_type="llm",
            timeout=60,
        )
        assert case.timeout == 60


class TestEvalResult:
    def test_basic_fields(self) -> None:
        result = EvalResult(
            case_id="tc-001",
            passed=True,
            actual_output="hello world",
            score=1.0,
            reason="all keywords matched",
            elapsed_ms=42,
        )
        assert result.case_id == "tc-001"
        assert result.passed is True
        assert result.error is None

    def test_failed_result_with_error(self) -> None:
        result = EvalResult(
            case_id="tc-err",
            passed=False,
            actual_output="",
            score=0.0,
            reason="timeout",
            elapsed_ms=30000,
            error="TimeoutError",
        )
        assert result.passed is False
        assert result.error == "TimeoutError"


class TestEvalReport:
    def test_pass_rate_calculation(self) -> None:
        results = [
            EvalResult("tc-001", True, "ok", 1.0, "matched", 10),
            EvalResult("tc-002", True, "ok", 1.0, "matched", 12),
            EvalResult("tc-003", False, "bad", 0.0, "no match", 15),
        ]
        report = EvalReport(
            skill_name="quality-check",
            total=3,
            passed=2,
            failed=1,
            pass_rate=2 / 3,
            results=results,
            started_at="2026-04-29T13:00:00",
            elapsed_ms=37,
        )
        assert pytest.approx(report.pass_rate, abs=0.001) == 0.667

    def test_perfect_pass_rate(self) -> None:
        results = [EvalResult("tc-001", True, "ok", 1.0, "ok", 5)]
        report = EvalReport(
            skill_name="test",
            total=1,
            passed=1,
            failed=0,
            pass_rate=1.0,
            results=results,
            started_at="2026-04-29T13:00:00",
            elapsed_ms=5,
        )
        assert report.pass_rate == 1.0
