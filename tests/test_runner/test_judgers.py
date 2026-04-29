"""Tests for KeywordJudger, SchemaJudger, LLMStubJudger."""

from __future__ import annotations

import pytest

from skill_infra.test_runner.judgers.keyword import KeywordJudger
from skill_infra.test_runner.judgers.llm_stub import LLMStubJudger
from skill_infra.test_runner.judgers.schema import SchemaJudger


class TestKeywordJudger:
    def setup_method(self) -> None:
        self.judger = KeywordJudger()

    def test_any_match_single_keyword(self) -> None:
        passed, score, _ = self.judger.judge("hello world", {"keywords": ["hello"]})
        assert passed is True
        assert score == 1.0

    def test_any_match_one_of_multiple(self) -> None:
        passed, score, _ = self.judger.judge("hello world", {"keywords": ["hello", "missing"]})
        assert passed is True
        assert pytest.approx(score) == 0.5

    def test_any_match_none_fails(self) -> None:
        passed, score, _ = self.judger.judge("completely different", {"keywords": ["missing"]})
        assert passed is False
        assert score == 0.0

    def test_any_mode_threshold(self) -> None:
        # 1/3 keywords = 0.33 < default threshold 0.5 => fail
        passed, score, _ = self.judger.judge(
            "only_one",
            {"keywords": ["only_one", "two", "three"], "mode": "any"},
        )
        assert passed is False
        assert pytest.approx(score, abs=0.01) == 1 / 3

    def test_all_mode_all_match(self) -> None:
        passed, score, reason = self.judger.judge(
            "alpha beta gamma",
            {"keywords": ["alpha", "beta", "gamma"], "mode": "all"},
        )
        assert passed is True
        assert score == 1.0
        assert "all" in reason

    def test_all_mode_partial_fails(self) -> None:
        passed, score, _ = self.judger.judge(
            "alpha beta",
            {"keywords": ["alpha", "beta", "gamma"], "mode": "all"},
        )
        assert passed is False
        assert pytest.approx(score, abs=0.01) == 2 / 3

    def test_case_insensitive(self) -> None:
        passed, _, _ = self.judger.judge("HELLO WORLD", {"keywords": ["hello"]})
        assert passed is True

    def test_empty_keywords_always_passes(self) -> None:
        passed, score, _ = self.judger.judge("anything", {"keywords": []})
        assert passed is True
        assert score == 1.0

    def test_score_fraction(self) -> None:
        # 2 out of 3 matched
        _, score, _ = self.judger.judge(
            "one two",
            {"keywords": ["one", "two", "three"], "mode": "any"},
        )
        assert pytest.approx(score, abs=0.01) == 2 / 3


class TestSchemaJudger:
    def setup_method(self) -> None:
        self.judger = SchemaJudger()

    def test_valid_json_matching_schema(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        passed, score, _ = self.judger.judge('{"name": "Alice"}', schema)
        assert passed is True
        assert score == 1.0

    def test_valid_json_failing_schema(self) -> None:
        schema = {"type": "object", "required": ["name"]}
        passed, score, reason = self.judger.judge('{"age": 30}', schema)
        assert passed is False
        assert score == 0.0
        assert "schema" in reason.lower() or "validation" in reason.lower()

    def test_invalid_json_fails(self) -> None:
        passed, score, reason = self.judger.judge("this is not json", {"type": "object"})
        assert passed is False
        assert score == 0.0
        assert "not valid JSON" in reason

    def test_array_schema(self) -> None:
        schema = {"type": "array", "items": {"type": "string"}}
        passed, _, _ = self.judger.judge('["a", "b", "c"]', schema)
        assert passed is True

    def test_number_schema(self) -> None:
        schema = {"type": "number"}
        passed, _, _ = self.judger.judge("42", schema)
        assert passed is True


class TestLLMStubJudger:
    def setup_method(self) -> None:
        self.judger = LLMStubJudger()

    def test_always_passes(self) -> None:
        passed, score, _reason = self.judger.judge("any output", {"anything": "here"})
        assert passed is True
        assert score == 1.0

    def test_stub_reason_mentions_not_implemented(self) -> None:
        _, _, reason = self.judger.judge("output", {})
        assert "not implemented" in reason.lower() or "stub" in reason.lower()
