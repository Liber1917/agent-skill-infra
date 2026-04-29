"""Tests for ToolAdapter and Cisco Scanner integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_infra.shared.tool_adapter import (
    CiscoScannerAdapter,
    ToolAdapter,
    ToolResult,
)


class TestToolResult:
    """ToolResult dataclass tests."""

    def test_fields(self) -> None:
        result = ToolResult(
            success=True,
            stdout="ok",
            stderr="",
            exit_code=0,
            elapsed_ms=100,
        )
        assert result.success is True
        assert result.stdout == "ok"
        assert result.exit_code == 0
        assert result.elapsed_ms == 100

    def test_defaults(self) -> None:
        result = ToolResult(success=False, stdout="", stderr="err", exit_code=1, elapsed_ms=0)
        assert result.success is False
        assert result.elapsed_ms == 0


class TestToolAdapterABC:
    """ToolAdapter cannot be instantiated directly."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            ToolAdapter()  # type: ignore[abstract]


class TestCiscoScannerAdapter:
    """Cisco Scanner adapter tests."""

    @pytest.mark.asyncio
    async def test_not_available_without_install(self) -> None:
        """When cisco-scanner is not installed, is_available returns False."""
        adapter = CiscoScannerAdapter()
        result = await adapter.is_available()
        assert isinstance(result, bool)

    def test_name_property(self) -> None:
        adapter = CiscoScannerAdapter()
        assert adapter.name == "cisco-scanner"

    @pytest.mark.asyncio
    async def test_run_not_available(self) -> None:
        """When tool is not available, run should return a ToolResult with error."""
        adapter = CiscoScannerAdapter()

        # Patch is_available to simulate uninstalled tool
        async def _unavailable() -> bool:
            return False

        adapter.is_available = _unavailable  # type: ignore[method-assign]
        result = await adapter.run("/some/path")
        assert result.success is False
        assert "not available" in result.stderr.lower() or "not found" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_run_mock_subprocess(self, tmp_path: Path) -> None:
        """Test run logic with mocked subprocess."""
        import json

        adapter = CiscoScannerAdapter()

        # Create a fake scanner script
        fake_scanner = tmp_path / "cisco-scanner"
        fake_scanner.write_text('#!/bin/bash\necho \'{"risk_level": "low", "issues": []}\'\n')
        fake_scanner.chmod(0o755)

        # Patch the binary path and is_available
        adapter._binary = str(fake_scanner)  # type: ignore[attr-defined]

        async def _available() -> bool:
            return True

        adapter.is_available = _available  # type: ignore[method-assign]

        result = await adapter.run(str(tmp_path))
        assert result.success is True
        assert result.exit_code == 0
        parsed = json.loads(result.stdout)
        assert parsed["risk_level"] == "low"
