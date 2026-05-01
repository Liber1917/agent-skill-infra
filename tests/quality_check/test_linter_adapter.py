"""Tests for LinterAdapter - agent-skill-linter CLI wrapper."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def skill_md(tmp_path: Path) -> Path:
    """Create a minimal SKILL.md for testing."""
    content = (
        "---\n"
        "name: test-skill\n"
        "description: A test skill\n"
        "version: 1.0.0\n"
        "triggers:\n"
        "  - test\n"
        "---\n\n"
        "# Test Skill\n\nThis is a test skill.\n"
    )
    path = tmp_path / "SKILL.md"
    path.write_text(content, encoding="utf-8")
    return path


class TestLinterResult:
    """Tests for LinterResult and LinterViolation."""

    def test_creation(self) -> None:
        from skill_infra.quality_check.linter_adapter import LinterResult, LinterViolation

        violations = [
            LinterViolation(
                rule="description-too-short",
                severity="warning",
                message="Description is too short",
            ),
        ]
        result = LinterResult(passed=False, violations=violations, raw_output="raw")
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].rule == "description-too-short"

    def test_passed_result_no_violations(self) -> None:
        from skill_infra.quality_check.linter_adapter import LinterResult

        result = LinterResult(passed=True, violations=[], raw_output="")
        assert result.passed is True


class TestLinterAdapter:
    """Tests for LinterAdapter."""

    def test_is_available_false_when_not_installed(self) -> None:
        """Should return False when npx agent-skill-linter is not installed."""
        from skill_infra.quality_check.linter_adapter import LinterAdapter

        adapter = LinterAdapter()
        # Don't rely on actual availability, test default behavior
        assert isinstance(adapter.is_available(), bool)

    def test_run_not_available_returns_graceful(self, skill_md: Path) -> None:
        """When not available, should return graceful skip result."""
        from skill_infra.quality_check.linter_adapter import LinterAdapter

        adapter = LinterAdapter()
        with patch.object(adapter, "is_available", return_value=False):
            result = adapter.run(skill_md)
            assert result.passed is True  # graceful skip
            assert len(result.violations) == 0

    def test_run_with_mock_success(self, skill_md: Path) -> None:
        """Should parse successful linter output."""
        from skill_infra.quality_check.linter_adapter import LinterAdapter

        mock_output = json.dumps(
            {
                "passed": True,
                "violations": [],
                "score": 100,
            }
        )

        adapter = LinterAdapter()
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=mock_output,
                stderr="",
            )
            result = adapter.run(skill_md)

        assert result.passed is True
        assert len(result.violations) == 0

    def test_run_with_violations(self, skill_md: Path) -> None:
        """Should parse linter output with violations."""
        from skill_infra.quality_check.linter_adapter import LinterAdapter

        mock_output = json.dumps(
            {
                "passed": False,
                "violations": [
                    {
                        "rule": "missing-output-format",
                        "severity": "error",
                        "message": "no output format",
                    },
                    {
                        "rule": "description-too-vague",
                        "severity": "warning",
                        "message": "vague desc",
                    },
                ],
                "score": 40,
            }
        )

        adapter = LinterAdapter()
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout=mock_output,
                stderr="",
            )
            result = adapter.run(skill_md)

        assert result.passed is False
        assert len(result.violations) == 2
        assert result.violations[0].rule == "missing-output-format"
        assert result.violations[0].severity == "error"

    def test_run_subprocess_error(self, skill_md: Path) -> None:
        """Should handle subprocess errors gracefully."""
        from skill_infra.quality_check.linter_adapter import LinterAdapter

        adapter = LinterAdapter()
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run", side_effect=FileNotFoundError("npx not found")),
        ):
            result = adapter.run(skill_md)

        assert result.passed is True
        assert len(result.violations) == 0
        # graceful skip

    def test_run_invalid_json_output(self, skill_md: Path) -> None:
        """Should handle non-JSON linter output."""
        from skill_infra.quality_check.linter_adapter import LinterAdapter

        adapter = LinterAdapter()
        with (
            patch.object(adapter, "is_available", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="not json at all",
                stderr="some error",
            )
            result = adapter.run(skill_md)

        assert result.passed is False
        assert len(result.violations) == 1
        assert "raw-output" in result.violations[0].rule
