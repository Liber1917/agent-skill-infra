"""LinterAdapter: wrapper around agent-skill-linter CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LinterViolation:
    """A single linter violation."""

    rule: str
    severity: str  # "error" | "warning" | "info"
    message: str


@dataclass
class LinterResult:
    """Result of running agent-skill-linter on a skill."""

    passed: bool
    violations: list[LinterViolation] = field(default_factory=list)
    raw_output: str = ""


class LinterAdapter:
    """Adapter for the agent-skill-linter CLI."""

    def is_available(self) -> bool:
        """Check if agent-skill-linter is available via npx."""
        return shutil.which("npx") is not None

    def run(self, skill_path: str | Path) -> LinterResult:
        """Run agent-skill-linter on a skill file/directory.

        Returns a graceful skip result if the linter is not installed.
        """
        if not self.is_available():
            return LinterResult(
                passed=True,
                violations=[],
                raw_output="agent-skill-linter not available (npx not found)",
            )

        skill_path = Path(skill_path)
        cmd = [
            "npx",
            "--yes",
            "agent-skill-linter",
            str(skill_path.resolve()),
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(skill_path.parent),
                env={**os.environ, "CI": "true"},
            )
        except FileNotFoundError:
            return LinterResult(
                passed=True,
                violations=[],
                raw_output="agent-skill-linter not available (executable not found)",
            )
        except subprocess.TimeoutExpired:
            return LinterResult(
                passed=False,
                violations=[
                    LinterViolation(
                        rule="linter-timeout",
                        severity="error",
                        message="agent-skill-linter timed out after 30s",
                    )
                ],
                raw_output="",
            )

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # Try to parse JSON output
        try:
            data = json.loads(stdout)
            violations = [
                LinterViolation(
                    rule=v.get("rule", "unknown"),
                    severity=v.get("severity", "warning"),
                    message=v.get("message", ""),
                )
                for v in data.get("violations", [])
            ]
            return LinterResult(
                passed=data.get("passed", proc.returncode == 0),
                violations=violations,
                raw_output=stdout,
            )
        except json.JSONDecodeError:
            # Non-JSON output: create a synthetic violation
            return LinterResult(
                passed=False,
                violations=[
                    LinterViolation(
                        rule="linter-raw-output",
                        severity="warning",
                        message=stderr or stdout or "unknown error",
                    )
                ],
                raw_output=stdout or stderr,
            )
