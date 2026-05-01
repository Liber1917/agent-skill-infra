"""Tests for LLMJudge - real LLM-as-Judge implementation."""

from __future__ import annotations

import json
from unittest.mock import patch


class TestLLMJudge:
    """Tests for the LLM Judge implementation."""

    def test_no_api_key_falls_back_to_stub(self) -> None:
        """Without API key, should fall back to stub behavior."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        judge = LLMJudge(api_key=None)
        passed, score, reason = judge.judge("any output", {"keywords": ["test"]})
        assert passed is True
        assert score == 1.0
        assert "not configured" in reason.lower() or "stub" in reason.lower()

    def test_judge_type_returns_llm(self) -> None:
        """LLMJudge should report judge_type as 'llm'."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        judge = LLMJudge(api_key="test-key")
        assert judge.judge_type == "llm"

    def test_semantic_equivalence_passes(self) -> None:
        """LLM returns passed=True for semantically equivalent outputs."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        mock_response = {
            "passed": True,
            "score": 0.95,
            "reason": "Outputs are semantically equivalent.",
        }

        judge = LLMJudge(api_key="test-key")
        with patch.object(judge, "_call_llm_sync", return_value=json.dumps(mock_response)):
            passed, score, reason = judge.judge(
                "The quick brown fox jumps",
                {"semantic_equivalence": "A fast brown fox leaps"},
            )

        assert passed is True
        assert score == 0.95
        assert "semantically equivalent" in reason

    def test_semantic_equivalence_fails(self) -> None:
        """LLM returns passed=False for unrelated outputs."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        mock_response = {
            "passed": False,
            "score": 0.1,
            "reason": "Outputs discuss completely different topics.",
        }

        judge = LLMJudge(api_key="test-key")
        with patch.object(judge, "_call_llm_sync", return_value=json.dumps(mock_response)):
            passed, score, _reason = judge.judge(
                "Climate change is real",
                {"semantic_equivalence": "Pasta recipes from Italy"},
            )

        assert passed is False
        assert score == 0.1

    def test_criteria_based_judgment(self) -> None:
        """LLM evaluates output against custom criteria."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        mock_response = {
            "passed": True,
            "score": 0.85,
            "reason": "Output contains analysis but lacks examples.",
        }

        judge = LLMJudge(api_key="test-key")
        with patch.object(judge, "_call_llm_sync", return_value=json.dumps(mock_response)):
            passed, score, _reason = judge.judge(
                "The algorithm has O(n log n) complexity.",
                {"criteria": "Must explain time complexity and provide examples."},
            )

        assert passed is True
        assert 0.8 <= score <= 1.0

    def test_malformed_llm_response_defaults_to_fail(self) -> None:
        """Non-JSON LLM response should default to fail gracefully."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        judge = LLMJudge(api_key="test-key")
        with patch.object(judge, "_call_llm_sync", return_value="I'm not JSON at all"):
            passed, score, reason = judge.judge("output", {"criteria": "test"})

        assert passed is False
        assert score == 0.0
        assert "parse" in reason.lower() or "invalid" in reason.lower()

    def test_empty_llm_response_defaults_to_fail(self) -> None:
        """Empty LLM response should default to fail."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        judge = LLMJudge(api_key="test-key")
        with patch.object(judge, "_call_llm_sync", return_value=""):
            passed, _score, _reason = judge.judge("output", {"criteria": "test"})

        assert passed is False

    def test_llm_timeout_defaults_to_fail(self) -> None:
        """Timeout should default to fail gracefully."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        judge = LLMJudge(api_key="test-key")
        with patch.object(judge, "_call_llm_sync", side_effect=TimeoutError("API timeout")):
            passed, _score, reason = judge.judge("output", {"criteria": "test"})

        assert passed is False
        assert "timed out" in reason.lower()

    def test_custom_model(self) -> None:
        """Should accept custom model name."""
        from skill_infra.test_runner.judgers.llm_judge import LLMJudge

        judge = LLMJudge(api_key="test-key", model="claude-3-5-sonnet-20241022")
        assert judge.model == "claude-3-5-sonnet-20241022"
