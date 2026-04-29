"""Tests for the CLI entry point."""

from __future__ import annotations

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
