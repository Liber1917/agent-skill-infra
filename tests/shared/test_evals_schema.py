"""Tests for evals.json Schema validation."""

from __future__ import annotations

import pytest

from skill_infra.shared.evals_schema import EVALS_JSON_SCHEMA, EvalsValidationError, validate_evals


class TestValidateEvals:
    """validate_evals checks evals.json format against the schema."""

    def test_valid_evals_passes(self) -> None:
        evals = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    "expected": {"keywords": ["hello"]},
                    "judge_type": "keyword",
                }
            ],
        }
        # Should not raise
        validate_evals(evals)

    def test_valid_with_tags_and_timeout(self) -> None:
        evals = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    "expected": {"keywords": ["hello"]},
                    "judge_type": "keyword",
                    "tags": ["smoke"],
                    "timeout": 60,
                }
            ],
        }
        validate_evals(evals)

    def test_valid_new_judge_types(self) -> None:
        """flow and snapshot judge types should be accepted."""
        evals = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-002",
                    "prompt": "do something",
                    "expected": {"tool_sequence": [{"name": "read_file"}]},
                    "judge_type": "flow",
                },
                {
                    "id": "tc-003",
                    "prompt": "check output",
                    "expected": {},
                    "judge_type": "snapshot",
                },
            ],
        }
        validate_evals(evals)

    def test_missing_skill_field(self) -> None:
        evals = {
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    "expected": {"keywords": ["hello"]},
                    "judge_type": "keyword",
                }
            ],
        }
        with pytest.raises(EvalsValidationError, match="skill"):
            validate_evals(evals)

    def test_missing_cases_field(self) -> None:
        evals = {
            "skill": "test",
            "version": "0.1.0",
        }
        with pytest.raises(EvalsValidationError, match="cases"):
            validate_evals(evals)

    def test_invalid_judge_type(self) -> None:
        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    "expected": {},
                    "judge_type": "invalid_type",
                }
            ],
        }
        with pytest.raises(EvalsValidationError, match="judge_type"):
            validate_evals(evals)

    def test_missing_required_case_fields(self) -> None:
        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    # missing expected and judge_type
                }
            ],
        }
        with pytest.raises(EvalsValidationError):
            validate_evals(evals)

    def test_timeout_out_of_range(self) -> None:
        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    "expected": {"keywords": ["hello"]},
                    "judge_type": "keyword",
                    "timeout": 500,  # exceeds max 300
                }
            ],
        }
        with pytest.raises(EvalsValidationError, match="timeout"):
            validate_evals(evals)

    def test_timeout_zero(self) -> None:
        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "hello",
                    "expected": {"keywords": ["hello"]},
                    "judge_type": "keyword",
                    "timeout": 0,  # below min 1
                }
            ],
        }
        with pytest.raises(EvalsValidationError, match="timeout"):
            validate_evals(evals)

    def test_empty_cases_valid(self) -> None:
        """Empty cases array should be valid (just useless)."""
        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [],
        }
        validate_evals(evals)

    def test_schema_is_dict(self) -> None:
        """EVALS_JSON_SCHEMA should be a valid JSON Schema dict."""
        assert isinstance(EVALS_JSON_SCHEMA, dict)
        assert EVALS_JSON_SCHEMA["$schema"] == "http://json-schema.org/draft-07/schema#"
