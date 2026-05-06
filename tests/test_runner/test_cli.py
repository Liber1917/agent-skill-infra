"""Tests for the CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from skill_infra.test_runner.cli import app

runner = CliRunner()


class TestCLIRun:
    def test_run_table_output(self, tmp_path) -> None:
        import json

        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "say hello",
                    "expected": {"keywords": ["mock", "response"]},
                    "judge_type": "keyword",
                }
            ],
        }
        f = tmp_path / "evals.json"
        f.write_text(json.dumps(evals))

        # mock adapter returns "mock response" -> should pass
        result = runner.invoke(app, ["run", str(f), "--adapter", "mock"])
        assert result.exit_code == 0
        assert "PASS" in result.output or "100.0%" in result.output

    def test_run_json_output(self, tmp_path) -> None:
        import json

        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-001",
                    "prompt": "say something",
                    "expected": {"keywords": ["mock", "response"]},
                    "judge_type": "keyword",
                }
            ],
        }
        f = tmp_path / "evals.json"
        f.write_text(json.dumps(evals))

        result = runner.invoke(app, ["run", str(f), "--output", "json"])
        assert result.exit_code == 0
        # Verify valid JSON output (may have typer prefix lines)
        lines = result.output.strip().split("\n")
        # Find the first line starting with '{'
        json_start = next(i for i, line in enumerate(lines) if line.strip().startswith("{"))
        json_output = "\n".join(lines[json_start:])
        parsed = json.loads(json_output)
        assert parsed["total"] == 1
        assert parsed["passed"] == 1

    def test_run_with_failure_returns_exit_1(self, tmp_path) -> None:
        import json

        evals = {
            "skill": "test",
            "version": "0.1.0",
            "cases": [
                {
                    "id": "tc-fail",
                    "prompt": "say something",
                    "expected": {"keywords": ["MISSING_KEYWORD_12345"]},
                    "judge_type": "keyword",
                }
            ],
        }
        f = tmp_path / "evals.json"
        f.write_text(json.dumps(evals))

        result = runner.invoke(app, ["run", str(f)])
        assert result.exit_code == 1

    def test_run_empty_evals_file(self, tmp_path) -> None:
        import json

        f = tmp_path / "evals.json"
        f.write_text(json.dumps({"skill": "test", "version": "0.1.0", "cases": []}))

        result = runner.invoke(app, ["run", str(f)])
        assert result.exit_code == 1
        assert "No test cases" in result.output

    def test_run_nonexistent_file(self, tmp_path) -> None:
        result = runner.invoke(app, ["run", str(tmp_path / "nope.json")])
        assert result.exit_code != 0


class TestCLIShow:
    def test_show_json_report(self, tmp_path) -> None:
        import json

        report_data = {
            "skill_name": "test",
            "total": 2,
            "passed": 1,
            "failed": 1,
            "pass_rate": 0.5,
            "started_at": "2026-04-29T13:00:00",
            "elapsed_ms": 42,
            "results": [
                {
                    "case_id": "tc-001",
                    "passed": True,
                    "score": 1.0,
                    "elapsed_ms": 20,
                    "reason": "all keywords matched",
                    "error": None,
                    "actual_output": "keyword present",
                },
                {
                    "case_id": "tc-002",
                    "passed": False,
                    "score": 0.0,
                    "elapsed_ms": 22,
                    "reason": "no keywords matched",
                    "error": None,
                    "actual_output": "nothing relevant",
                },
            ],
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report_data))

        result = runner.invoke(app, ["show", str(f)])
        assert result.exit_code == 0


_SKILL_MD_CONTENT = """---
name: test-skill
description: A test skill for generating reports
version: 0.1.0
triggers:
  - generate report
  - create markdown
---

## Usage

Use this skill to generate reports.

## Examples

Generate a report about sales data.
"""

_MOCK_CASES_RESPONSE = {
    "cases": [
        {
            "id": "auto-001",
            "prompt": "帮我生成一份销售报告",
            "judge_type": "keyword",
            "expected": {"keywords": ["报告", "销售"], "mode": "any", "threshold": 0.5},
            "tags": ["auto-generated"],
        },
        {
            "id": "auto-002",
            "prompt": "创建一份数据分析",
            "judge_type": "keyword",
            "expected": {"keywords": ["分析", "数据"], "mode": "any", "threshold": 0.5},
            "tags": ["auto-generated"],
        },
        {
            "id": "auto-003",
            "prompt": "输出测试报告",
            "judge_type": "keyword",
            "expected": {"keywords": ["测试", "结果"], "mode": "any", "threshold": 0.5},
            "tags": ["auto-generated"],
        },
    ]
}


class TestCLIGenerate:
    def test_generate_from_skill_md(self, tmp_path) -> None:
        import json

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(_SKILL_MD_CONTENT, encoding="utf-8")

        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.generate.return_value = tmp_path / "evals.json"
        # Pre-write the expected output so the CLI can read case_count
        output_data = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": _MOCK_CASES_RESPONSE["cases"],
        }
        (tmp_path / "evals.json").write_text(json.dumps(output_data), encoding="utf-8")

        with patch(
            "skill_infra.test_runner.auto_evals.AutoEvalsGenerator",
            return_value=mock_instance,
        ):
            result = runner.invoke(app, ["generate", str(skill_md)])
            assert result.exit_code == 0
            assert "Generated 3 test case" in result.output

    def test_generate_from_dir_finds_skill_md(self, tmp_path) -> None:
        import json

        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")

        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.generate.return_value = skill_dir / "evals.json"
        output_data = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": _MOCK_CASES_RESPONSE["cases"],
        }
        (skill_dir / "evals.json").write_text(json.dumps(output_data), encoding="utf-8")

        with patch(
            "skill_infra.test_runner.auto_evals.AutoEvalsGenerator",
            return_value=mock_instance,
        ):
            result = runner.invoke(app, ["generate", str(skill_dir)])
            assert result.exit_code == 0
            assert "Generated 3 test case" in result.output

    def test_generate_no_token_fails(self, tmp_path) -> None:
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(_SKILL_MD_CONTENT, encoding="utf-8")

        mock_instance = MagicMock()
        mock_instance.is_available.return_value = False

        with patch(
            "skill_infra.test_runner.auto_evals.AutoEvalsGenerator",
            return_value=mock_instance,
        ):
            result = runner.invoke(app, ["generate", str(skill_md)])
            assert result.exit_code == 1
            assert "GITHUB_TOKEN" in result.output

    def test_generate_nonexistent_path(self, tmp_path) -> None:
        result = runner.invoke(app, ["generate", str(tmp_path / "nope.md")])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_generate_generator_exception(self, tmp_path) -> None:
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(_SKILL_MD_CONTENT, encoding="utf-8")

        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.generate.side_effect = RuntimeError("LLM API error")

        with patch(
            "skill_infra.test_runner.auto_evals.AutoEvalsGenerator",
            return_value=mock_instance,
        ):
            result = runner.invoke(app, ["generate", str(skill_md)])
            assert result.exit_code == 1
            assert "LLM API error" in result.output

    def test_generate_with_output_option(self, tmp_path) -> None:
        import json

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(_SKILL_MD_CONTENT, encoding="utf-8")
        custom_output = tmp_path / "custom_evals.json"

        mock_instance = MagicMock()
        mock_instance.is_available.return_value = True
        mock_instance.generate.return_value = tmp_path / "evals.json"
        output_data = {
            "skill": "test-skill",
            "version": "0.1.0",
            "cases": _MOCK_CASES_RESPONSE["cases"],
        }
        (tmp_path / "evals.json").write_text(json.dumps(output_data), encoding="utf-8")

        with patch(
            "skill_infra.test_runner.auto_evals.AutoEvalsGenerator",
            return_value=mock_instance,
        ):
            result = runner.invoke(app, ["generate", str(skill_md), "--output", str(custom_output)])
            assert result.exit_code == 0
            assert custom_output.exists()
