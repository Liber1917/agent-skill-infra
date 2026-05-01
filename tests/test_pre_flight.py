"""Tests for the pre-flight CI check script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PRE_FLIGHT = Path(__file__).parent.parent / "scripts" / "ci" / "pre_flight.py"


def test_pre_flight_runs() -> None:
    """pre_flight.py executes without crashing."""
    result = subprocess.run(
        [sys.executable, str(PRE_FLIGHT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path(__file__).parent.parent,
    )
    assert result.returncode in (0, 1, 2), (
        f"Unexpected exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_pre_flight_output_contains_sections() -> None:
    """pre_flight.py output mentions all 6 check sections."""
    result = subprocess.run(
        [sys.executable, str(PRE_FLIGHT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path(__file__).parent.parent,
    )
    stdout = result.stdout
    assert "pre-flight checks" in stdout
    assert "Git availability" in stdout
    assert "Cisco Scanner" in stdout
    assert "npx" in stdout
    assert "CLI entry point" in stdout
    assert "SKILL.md fixture" in stdout
    assert "Hardcoded path" in stdout


def test_pre_flight_git_required() -> None:
    """Git check is critical (would fail if git missing)."""
    result = subprocess.run(
        [sys.executable, str(PRE_FLIGHT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path(__file__).parent.parent,
    )
    # On this machine, git is available
    assert "git found" in result.stdout
