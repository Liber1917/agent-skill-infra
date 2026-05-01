"""Tests for version_aware CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_repo(repo: Path) -> tuple[str, str]:
    """Initialize a git repo with two commits, return (sha1, sha2)."""
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: v1\nversion: 1.0.0\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    sha1 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: v2\nversion: 2.0.0\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "update to v2"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    sha2 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return sha1, sha2


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVersionCLI:
    """Tests for skill-version CLI commands."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path) -> None:
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        self.sha1, self.sha2 = _init_repo(self.repo)

    def test_diff_table_output(self) -> None:
        """skill-version diff should output table format by default."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["diff", str(self.repo), "--old-ref", self.sha1, "--new-ref", self.sha2],
        )
        assert result.exit_code == 0
        assert "SKILL.md" in result.output
        assert "modified" in result.output.lower() or "changed" in result.output.lower()

    def test_diff_json_output(self) -> None:
        """skill-version diff should output valid JSON with --output json."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "diff",
                str(self.repo),
                "--old-ref",
                self.sha1,
                "--new-ref",
                self.sha2,
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["old_sha"] == self.sha1
        assert data["new_sha"] == self.sha2
        assert len(data["files"]) > 0

    def test_diff_same_ref(self) -> None:
        """Diff between identical refs should produce empty result."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["diff", str(self.repo), "--old-ref", self.sha1, "--new-ref", self.sha1],
        )
        assert result.exit_code == 0
        assert "0 files" in result.output.lower() or "empty" in result.output.lower()

    def test_check_with_security(self) -> None:
        """skill-version check should include diff + security analysis."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "check",
                str(self.repo),
                "--old-ref",
                self.sha1,
                "--new-ref",
                self.sha2,
                "--security",
            ],
        )
        assert result.exit_code == 0
        assert "SKILL.md" in result.output

    def test_rollback_with_confirm(self) -> None:
        """skill-version rollback should work with --yes flag."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["rollback", str(self.repo), "--target-ref", self.sha1, "--yes"],
        )
        assert result.exit_code == 0
        assert "rolled back" in result.output.lower()

    def test_rollback_without_confirm_rejected(self) -> None:
        """rollback without --yes should be rejected in non-interactive mode."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["rollback", str(self.repo), "--target-ref", self.sha1],
        )
        # In non-interactive mode, should exit with non-zero
        assert result.exit_code != 0

    def test_baseline_store(self, tmp_path: Path) -> None:
        """skill-version baseline store should save output to a file."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        output_file = tmp_path / "baseline-output.txt"
        output_file.write_text("test baseline output", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "baseline",
                "store",
                str(self.repo),
                "case-1",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert "stored" in result.output.lower() or "saved" in result.output.lower()

        # Verify baseline file was created
        baseline_path = self.repo / "__baselines__" / "case-1.txt"
        assert baseline_path.exists()
        assert baseline_path.read_text() == "test baseline output"

    def test_baseline_detect_no_regression(self, tmp_path: Path) -> None:
        """baseline detect should report no regression when output matches."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        # Store baseline first
        output_file = tmp_path / "current-output.txt"
        output_file.write_text("same output", encoding="utf-8")

        runner = CliRunner()
        runner.invoke(
            app,
            ["baseline", "store", str(self.repo), "detect-case", str(output_file)],
        )

        # Detect with same output
        result = runner.invoke(
            app,
            ["baseline", "detect", str(self.repo), "detect-case", str(output_file)],
        )
        assert result.exit_code == 0
        assert "no regression" in result.output.lower()
