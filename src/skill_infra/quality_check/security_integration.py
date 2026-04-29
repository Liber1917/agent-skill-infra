"""Security integration: optionally run Cisco Scanner as part of quality check."""

from __future__ import annotations

from pathlib import Path

from skill_infra.quality_check.scorecard import DimensionScore
from skill_infra.shared.tool_adapter import CiscoScannerAdapter


class SecurityIntegration:
    """Wraps Cisco Scanner into a DimensionScore for quality reports."""

    _DIM_NAME = "security_scan"

    def run(self, skill_path: str | Path) -> DimensionScore:
        """Run Cisco Scanner and return a DimensionScore.

        If the scanner is not installed, returns a skipped result (score=1.0).
        """
        import asyncio

        adapter = CiscoScannerAdapter()

        try:
            result = asyncio.get_event_loop().run_until_complete(adapter.run(str(skill_path)))
        except RuntimeError:
            # No event loop running (e.g., in tests), create one
            result = asyncio.run(adapter.run(str(skill_path)))

        if not result.success:
            if result.exit_code == 127:
                # Not installed
                return DimensionScore(
                    name=self._DIM_NAME,
                    score=1.0,
                    findings=["Security scan skipped (cisco-scanner not installed)"],
                )
            return DimensionScore(
                name=self._DIM_NAME,
                score=0.0,
                findings=[f"Security scan failed: {result.stderr}"],
            )

        # Parse scanner output for findings
        findings = self._parse_scanner_output(result.stdout)

        # If scanner succeeded, check if it found issues
        has_findings = any("risk" in f.lower() or "vulnerability" in f.lower() for f in findings)
        score = 0.5 if has_findings else 1.0

        if not findings:
            findings.append("No security issues detected")

        return DimensionScore(name=self._DIM_NAME, score=score, findings=findings)

    @staticmethod
    def _parse_scanner_output(stdout: str) -> list[str]:
        """Extract key findings from scanner output."""
        findings: list[str] = []

        if not stdout.strip():
            return ["Scanner returned empty output"]

        # Try JSON parsing
        try:
            data = __import__("json").loads(stdout)
            if isinstance(data, dict):
                for key in ("findings", "issues", "results", "alerts"):
                    if key in data and isinstance(data[key], list):
                        for item in data[key][:10]:
                            if isinstance(item, dict):
                                msg = item.get("message", item.get("description", str(item)))
                                findings.append(str(msg)[:200])
                            else:
                                findings.append(str(item)[:200])
                        break
        except (ValueError, TypeError):
            # Not JSON, extract lines
            for line in stdout.strip().splitlines()[:10]:
                if line.strip():
                    findings.append(line.strip()[:200])

        return findings
