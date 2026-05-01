"""ToolAdapter: unified interface for external CLI tools."""

from __future__ import annotations

import asyncio
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standardized result from an external tool invocation."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    elapsed_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolAdapter(ABC):
    """Abstract adapter for external CLI tools.

    Subclass this to integrate specific tools (e.g., Cisco Scanner,
    agent-skill-linter) into the agent-skill-infra pipeline.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter identifier, used for logging and reporting."""
        ...

    @abstractmethod
    async def run(self, target: str, **kwargs: Any) -> ToolResult:
        """Execute the tool against the given target.

        Args:
            target: Path or identifier for the tool to operate on.
            **kwargs: Additional tool-specific arguments.

        Returns:
            ToolResult with standardized fields.
        """
        ...

    async def is_available(self) -> bool:
        """Check whether the tool is installed and accessible.

        Default implementation checks for the binary in PATH.
        Subclasses may override for more specific checks.
        """
        return shutil.which(self._binary_path()) is not None

    def _binary_path(self) -> str:
        """Return the command name or path for the tool binary."""
        return self.name


class CiscoScannerAdapter(ToolAdapter):
    """Adapter for Cisco Scanner CLI (cisco-scanner).

    Calls ``cisco-scanner scan <target>`` and parses JSON output.
    Gracefully handles the case where the tool is not installed.
    """

    def __init__(self, binary: str = "cisco-scanner") -> None:
        self._binary = binary

    @property
    def name(self) -> str:
        return "cisco-scanner"

    async def run(self, target: str, **kwargs: Any) -> ToolResult:
        """Run Cisco Scanner against the target path.

        Args:
            target: Path to the skill directory or file to scan.
            **kwargs: Currently unused. Reserved for future options.
        """
        if not await self.is_available():
            return ToolResult(
                success=False,
                stdout="",
                stderr=f"{self.name} is not installed or not found in PATH",
                exit_code=127,
                elapsed_ms=0,
            )

        import time

        cmd = [self._binary, "scan", target]
        t0 = time.monotonic()
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=120)
        except FileNotFoundError:
            return ToolResult(
                success=False,
                stdout="",
                stderr=f"{self.name} binary not found at {self._binary}",
                exit_code=127,
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            )
        except TimeoutError:
            if proc is not None:
                proc.kill()
            return ToolResult(
                success=False,
                stdout="",
                stderr=f"{self.name} timed out after 120s",
                exit_code=124,
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                stdout="",
                stderr=f"{self.name} raised: {exc}",
                exit_code=1,
                elapsed_ms=int((time.monotonic() - t0) * 1000),
            )

        elapsed = int((time.monotonic() - t0) * 1000)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        return ToolResult(
            success=proc.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode or 0,
            elapsed_ms=elapsed,
        )
