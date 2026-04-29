"""Tests for SkillTestRunner core."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from skill_infra.shared.types import EvalCase, EvalReport, EvalResult
from skill_infra.test_runner.adapters.mock import MockAdapter
from skill_infra.test_runner.runner import SkillTestRunner


class TestSkillTestRunner:
    def _make_runner(self, responses: dict[str, str] | None = None) -> SkillTestRunner:
        adapter = MockAdapter(responses=responses, default="generic response")
        return SkillTestRunner(adapter=adapter)

    @pytest.mark.asyncio
    async def test_run_case_keyword_passes(self) -> None:
        runner = self._make_runner({"hello": "hi keyword match"})
        case = EvalCase(
            id="tc-001",
            prompt="hello",
            expected={"keywords": ["keyword"]},
            judge_type="keyword",
        )
        result = await runner.run_case(case)
        assert isinstance(result, EvalResult)
        assert result.case_id == "tc-001"
        assert result.passed is True
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_run_case_keyword_fails(self) -> None:
        runner = self._make_runner({"hello": "no match at all"})
        case = EvalCase(
            id="tc-002",
            prompt="hello",
            expected={"keywords": ["specific_missing_keyword"]},
            judge_type="keyword",
        )
        result = await runner.run_case(case)
        assert result.passed is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_run_case_records_elapsed_ms(self) -> None:
        runner = self._make_runner()
        case = EvalCase(id="tc-003", prompt="p", expected={"keywords": []}, judge_type="keyword")
        result = await runner.run_case(case)
        assert result.elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_run_all_summary(self) -> None:
        responses = {
            "prompt1": "keyword1 present",
            "prompt2": "keyword2 present",
            "prompt3": "nothing here",
        }
        runner = self._make_runner(responses)
        cases = [
            EvalCase(
                id="tc-001",
                prompt="prompt1",
                expected={"keywords": ["keyword1"]},
                judge_type="keyword",
            ),
            EvalCase(
                id="tc-002",
                prompt="prompt2",
                expected={"keywords": ["keyword2"]},
                judge_type="keyword",
            ),
            EvalCase(
                id="tc-003",
                prompt="prompt3",
                expected={"keywords": ["missing"]},
                judge_type="keyword",
            ),
        ]
        report = await runner.run_all(cases, skill_name="test-skill")
        assert isinstance(report, EvalReport)
        assert report.total == 3
        assert report.passed == 2
        assert report.failed == 1
        assert pytest.approx(report.pass_rate, abs=0.001) == 2 / 3

    @pytest.mark.asyncio
    async def test_from_evals_file(self) -> None:
        evals_data = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "check quality",
                    "expected": {"keywords": ["quality"]},
                    "judge_type": "keyword",
                    "tags": ["smoke"],
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(evals_data, f)
            tmp_path = f.name

        adapter = MockAdapter(responses={"check quality": "quality result"})
        runner = SkillTestRunner.from_evals_file(tmp_path, adapter)
        assert len(runner.cases) == 1
        assert runner.cases[0].id == "tc-001"
        assert runner.cases[0].tags == ["smoke"]

        # Also run it end-to-end
        report = await runner.run_all(runner.cases, skill_name="test-skill")
        assert report.passed == 1

        Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_run_all_empty(self) -> None:
        runner = self._make_runner()
        report = await runner.run_all([], skill_name="empty")
        assert report.total == 0
        assert report.pass_rate == 1.0  # vacuously true
