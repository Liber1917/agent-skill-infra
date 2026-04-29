"""Regression detector: compare outputs against baselines for behavior regression."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from skill_infra.test_runner.snapshot import SnapshotStore


@dataclass
class RegressionReport:
    """Result of comparing a single output against its baseline."""

    case_id: str
    regressed: bool
    diff: str  # unified diff, empty if no regression


class RegressionDetector:
    """Detect behavior regression by comparing outputs against stored baselines.

    Baselines are stored under ``__baselines__/<case_id>.txt`` in the repo.
    """

    def __init__(
        self,
        repo_path: str | Path,
        normalizers: list[Callable[[str], str]] | None = None,
    ) -> None:
        self._store = SnapshotStore(
            snapshot_dir=repo_path,
            normalizers=normalizers,
        )
        # Override snapshot directory name
        self._baseline_dir = Path(repo_path) / "__baselines__"

    def store_baseline(self, case_id: str, output: str) -> None:
        """Store a baseline output for a given case ID."""
        self._baseline_dir.mkdir(parents=True, exist_ok=True)
        (self._baseline_dir / f"{case_id}.txt").write_text(output, encoding="utf-8")

    def detect(self, case_id: str, actual_output: str) -> RegressionReport:
        """Compare actual output against stored baseline.

        Args:
            case_id: The test case identifier.
            actual_output: The current output to check.

        Returns:
            RegressionReport with regression status and diff.

        Raises:
            ValueError: If no baseline exists for the given case_id.
        """
        baseline_path = self._baseline_dir / f"{case_id}.txt"
        if not baseline_path.exists():
            raise ValueError(f"No baseline found for case '{case_id}'")

        baseline = baseline_path.read_text(encoding="utf-8")
        normalizers = self._store._normalizers

        # Apply normalizers
        expected = baseline
        actual = actual_output
        for fn in normalizers:
            expected = fn(expected)
            actual = fn(actual)

        if expected == actual:
            return RegressionReport(case_id=case_id, regressed=False, diff="")

        # Generate unified diff
        import difflib

        diff_lines = list(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                actual.splitlines(keepends=True),
                fromfile="baseline",
                tofile="actual",
            )
        )
        return RegressionReport(
            case_id=case_id,
            regressed=True,
            diff="".join(diff_lines),
        )

    def batch_detect(self, cases: dict[str, str]) -> list[RegressionReport]:
        """Detect regression across multiple cases.

        Args:
            cases: Mapping of case_id to actual output.

        Returns:
            List of RegressionReport for each case, in insertion order.
        """
        results: list[RegressionReport] = []
        for case_id, output in cases.items():
            results.append(self.detect(case_id, output))
        return results
