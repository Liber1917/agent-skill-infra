"""Tests for auto_evals.py — LLM-based evals.json generation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from skill_infra.quality_check.parser import ParsedSkill
from skill_infra.shared.types import SkillMeta
from skill_infra.test_runner.auto_evals import AutoEvalsGenerator


@pytest.fixture
def sample_skill() -> ParsedSkill:
    return ParsedSkill(
        meta=SkillMeta(
            name="test-skill",
            description="A test skill for generating markdown reports",
            version="0.2.0",
            triggers=["generate report", "create markdown"],
        ),
        sections=[{"title": "Usage", "body": "Use this skill to generate reports."}],
        raw_body=(
            "## Usage\n\nUse this skill to generate reports.\n\n"
            "## Examples\n\nGenerate a report about sales."
        ),
        total_lines=20,
        token_estimate=200,
    )


_MOCK_API_RESPONSE = {
    "cases": [
        {
            "id": "auto-001",
            "prompt": "帮我生成一份销售报告",
            "judge_type": "keyword",
            "expected": {"keywords": ["报告", "销售", "生成"], "mode": "any", "threshold": 0.5},
            "tags": ["auto-generated"],
        },
        {
            "id": "auto-002",
            "prompt": "创建一个关于用户活跃度的分析",
            "judge_type": "keyword",
            "expected": {"keywords": ["分析", "数据", "用户"], "mode": "any", "threshold": 0.5},
            "tags": ["auto-generated"],
        },
        {
            "id": "auto-003",
            "prompt": "输出一份测试覆盖率报告",
            "judge_type": "keyword",
            "expected": {"keywords": ["覆盖率", "测试", "报告"], "mode": "any", "threshold": 0.5},
            "tags": ["auto-generated"],
        },
    ]
}


class TestAutoEvalsGenerator:
    def test_is_available_with_token(self) -> None:
        gen = AutoEvalsGenerator(github_token="fake-token")
        assert gen.is_available() is True

    def test_is_available_without_token(self, monkeypatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        gen = AutoEvalsGenerator()
        assert gen.is_available() is False

    def test_is_available_with_env_token(self, monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        gen = AutoEvalsGenerator()
        assert gen.is_available() is True

    def test_generate_without_token_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        gen = AutoEvalsGenerator()
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
            gen.generate(_dummy_skill(), MagicMock())

    def test_generate_writes_evals_json(self, sample_skill, tmp_path) -> None:
        def fake_call_api(user_message: str) -> str:
            return json.dumps(_MOCK_API_RESPONSE, ensure_ascii=False)

        gen = AutoEvalsGenerator(github_token="fake-token")
        gen._call_api = fake_call_api  # type: ignore[method-assign]

        evals_path = gen.generate(sample_skill, tmp_path)
        assert evals_path.name == "evals.json"
        assert evals_path.exists()

        data = json.loads(evals_path.read_text(encoding="utf-8"))
        assert data["skill"] == "test-skill"
        assert data["version"] == "0.2.0"
        assert len(data["cases"]) == 3
        assert data["cases"][0]["judge_type"] == "keyword"
        assert "keywords" in data["cases"][0]["expected"]
        assert data["cases"][0]["tags"] == ["auto-generated"]

    def test_generate_empty_cases_raises(self, tmp_path) -> None:
        def fake_call_api(user_message: str) -> str:
            return json.dumps({"cases": []})

        gen = AutoEvalsGenerator(github_token="fake-token")
        gen._call_api = fake_call_api  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="no test cases"):
            gen.generate(_dummy_skill(), tmp_path)

    def test_generate_missing_expected_field_raises(self, tmp_path) -> None:
        def fake_call_api(user_message: str) -> str:
            return json.dumps({"cases": [{"id": "auto-001", "prompt": "hi"}]})

        gen = AutoEvalsGenerator(github_token="fake-token")
        gen._call_api = fake_call_api  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="missing field"):
            gen.generate(_dummy_skill(), tmp_path)

    def test_user_message_includes_name_description_body(self, sample_skill) -> None:
        msg = AutoEvalsGenerator._build_user_message(sample_skill)
        assert "test-skill" in msg
        assert "generating markdown reports" in msg
        assert "Generate a report about sales" in msg

    def test_parse_response_strips_code_fences(self) -> None:
        response = "```json\n" + json.dumps(_MOCK_API_RESPONSE) + "\n```"
        data = AutoEvalsGenerator._parse_response(response, "test", "1.0")
        assert len(data["cases"]) == 3
        assert data["skill"] == "test"

    def test_parse_response_invalid_json_raises(self) -> None:
        with pytest.raises(RuntimeError, match="invalid JSON"):
            AutoEvalsGenerator._parse_response("not valid json", "test", "1.0")

    def test_parse_response_sets_default_tags(self) -> None:
        response = json.dumps({"cases": [
            {"id": "t1", "prompt": "p1", "expected": {"kw": []}, "judge_type": "keyword"}
        ]})
        data = AutoEvalsGenerator._parse_response(response, "s", "1.0")
        assert data["cases"][0]["tags"] == []

    def test_default_model_and_temperature(self) -> None:
        gen = AutoEvalsGenerator(github_token="t")
        assert gen.model == "gpt-4o-mini"
        assert gen._temperature == 0.1


def _dummy_skill() -> ParsedSkill:
    return ParsedSkill(
        meta=SkillMeta(name="dummy", description="dummy skill"),
        raw_body="dummy content",
    )


class TestAutoEvalsGeneratorAPI:
    """Integration-style tests that mock httpx."""

    def test_call_api_makes_correct_request(self, sample_skill) -> None:
        import json as _json

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": _json.dumps(_MOCK_API_RESPONSE)}}],
        }
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client", return_value=mock_client):
            gen = AutoEvalsGenerator(github_token="fake-token")
            gen._call_api("test message")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["model"] == "gpt-4o-mini"
        assert call_args[1]["json"]["temperature"] == 0.1
        assert call_args[1]["headers"]["Authorization"] == "Bearer fake-token"

    def test_call_api_empty_choices_raises(self) -> None:
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": []}
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client", return_value=mock_client):
            gen = AutoEvalsGenerator(github_token="fake-token")
            with pytest.raises(RuntimeError, match="Empty response"):
                gen._call_api("test")
