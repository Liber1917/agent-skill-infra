"""Tests for issue_tester.py: parsing, detection, report generation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest  # noqa: F401

# Add scripts/ci to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "ci"))

from issue_tester import (  # type: ignore[import-not-found]
    _build_result,
    _count_config_files,
    detect_project_type,
    extract_repo_url,
    generate_report,
    parse_issue_body,
)


class TestParseIssueBody:
    def test_extracts_repo_url(self) -> None:
        body = """### Repository URL

https://github.com/test-owner/test-repo

### Branch (optional)

main
"""
        fields = parse_issue_body(body)
        assert fields.get("repo_url") == "https://github.com/test-owner/test-repo"
        assert fields.get("branch") == "main"

    def test_extracts_with_optional_fields(self) -> None:
        body = """### Repository URL

https://github.com/foo/bar

### Branch (optional)

develop

### Custom test command (optional)

pytest tests/unit/

"""
        fields = parse_issue_body(body)
        assert fields["repo_url"] == "https://github.com/foo/bar"
        assert fields["branch"] == "develop"
        assert fields["test_command"] == "pytest tests/unit/"

    def test_missing_fields_return_empty(self) -> None:
        fields = parse_issue_body("### Some other heading\n\ncontent")
        assert fields == {}


class TestExtractRepoUrl:
    def test_extracts_standard_url(self) -> None:
        result = extract_repo_url("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_extracts_url_with_git_suffix(self) -> None:
        result = extract_repo_url("clone https://github.com/a/b.git now")
        assert result == ("a", "b")

    def test_no_url_returns_none(self) -> None:
        assert extract_repo_url("no url here") is None

    def test_multiline_body_finds_url(self) -> None:
        body = """### Repository URL

https://github.com/hello/world

other stuff"""
        result = extract_repo_url(body)
        assert result == ("hello", "world")


class TestDetectProjectType:
    def test_detects_python(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "pyproject.toml").write_text("[project]\nname='test'")
            assert detect_project_type(Path(td)) == "python"

    def test_detects_bun(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "bun.lock").write_text("{}")
            assert detect_project_type(Path(td)) == "bun"

    def test_detects_npm(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "package.json").write_text('{"name":"test"}')
            assert detect_project_type(Path(td)) == "npm"

    def test_detects_config_driven(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "agents").mkdir()
            (Path(td) / "skills").mkdir()
            assert detect_project_type(Path(td)) == "config"

    def test_unknown_for_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            assert detect_project_type(Path(td)) == "unknown"


class TestCountConfigFiles:
    def test_counts_directories(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agents").mkdir()
            (root / "agents" / "agent1.md").write_text("test")
            (root / "skills").mkdir()
            (root / "skills" / "skill-a").mkdir()

            result = _count_config_files(root)
            assert result["counts"]["agents"] == 1
            assert result["counts"]["skills"] == 1  # 1 directory
            assert result["total_files"] == 2


class TestBuildResult:
    def test_parses_pytest_output(self) -> None:
        stdout = "5 passed in 0.5s"
        result = _build_result(0, stdout, "", "pytest")
        assert result["passed"] == 5
        assert result["failed"] == 0
        assert result["test_count"] == 5

    def test_parses_pytest_with_failures(self) -> None:
        stdout = "8 passed, 2 failed in 1.2s"
        result = _build_result(1, stdout, "", "pytest")
        assert result["passed"] == 8
        assert result["failed"] == 2
        assert result["test_count"] == 10

    def test_parses_bun_output(self) -> None:
        stdout = "5829 pass\n43 fail\n5872 tests"
        result = _build_result(0, stdout, "", "bun test")
        assert result["passed"] == 5829
        assert result["failed"] == 43

    def test_parses_npm_pass_count(self) -> None:
        stdout = "(pass) test one\n(pass) test two\n(pass) test three\n"
        result = _build_result(0, stdout, "", "npm test")
        assert result["passed"] == 3
        assert result["test_count"] == 3


class TestGenerateReport:
    def test_all_passed_report(self) -> None:
        result = {
            "passed": 100, "failed": 0,
            "test_count": 100, "exit_code": 0, "command": "pytest",
        }
        report = generate_report("https://github.com/x/y", "python", "main", result, 5.0)
        assert "All Passed" in report
        assert "100" in report
        assert "agent-skill-infra" in report

    def test_failed_report(self) -> None:
        result = {
            "passed": 90, "failed": 10,
            "test_count": 100, "exit_code": 1, "command": "npm test",
        }
        report = generate_report("https://github.com/a/b", "npm", "main", result, 3.0)
        assert "Tests Failed" in report
        assert "90" in report
        assert "10" in report

    def test_timeout_report(self) -> None:
        result = {"passed": 0, "failed": 0, "test_count": 0, "exit_code": -1, "command": "unknown"}
        report = generate_report("https://github.com/c/d", "unknown", "main", result, 300.0)
        assert "Timeout" in report
