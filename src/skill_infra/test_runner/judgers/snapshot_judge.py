"""SnapshotJudger: compare skill output against stored snapshots for regression.

Auto-baselines on first run. On subsequent runs, diffs against stored snapshot.
Uses the same normalizers (timestamps, paths, whitespace) as the version_aware
module to minimize false positives.
"""

from __future__ import annotations

from pathlib import Path

from skill_infra.test_runner.judgers.base import Judger
from skill_infra.test_runner.snapshot import (
    SnapshotStore,
    normalize_paths,
    normalize_timestamps,
    normalize_whitespace,
)

_DEFAULT_NORMALIZERS = [normalize_timestamps, normalize_paths, normalize_whitespace]


class SnapshotJudger(Judger):
    """Judge skill output by comparing against a stored snapshot.

    Two modes:
    - auto-baseline (default): first run stores the output; subsequent runs diff.
    - update: always overwrite the snapshot with current output (passes).
    """

    def __init__(
        self,
        snapshot_dir: str | Path | None = None,
        auto_baseline: bool = True,
        update_snapshots: bool = False,
    ) -> None:
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir else Path("__snapshots__")
        self._auto_baseline = auto_baseline
        self._update_snapshots = update_snapshots
        self._store = SnapshotStore(
            snapshot_dir=self._snapshot_dir,
            normalizers=list(_DEFAULT_NORMALIZERS),
        )

    # ------------------------------------------------------------------
    # Judger interface
    # ------------------------------------------------------------------

    def judge(self, output: str, expected: object) -> tuple[bool, float, str]:
        """Compare output against stored snapshot.

        The ``expected`` dict may contain:
          - case_id (str): identifier for this test case (defaults to hash).
          - If missing, a generic case_id "output" is used.
        """
        case_id = self._resolve_case_id(expected)

        # Update mode: always overwrite and pass
        if self._update_snapshots:
            self._store.write_snapshot(case_id, output)
            return True, 1.0, f"snapshot updated ({len(output)} bytes)"

        # Auto-baseline: first run stores, subsequent runs diff
        if self._auto_baseline and not self._store.has_snapshot(case_id):
            self._store.write_snapshot(case_id, output)
            return True, 1.0, f"snapshot stored as baseline ({len(output)} bytes)"

        # Compare
        matches, diff_text = self._store.diff(case_id, output)
        if matches:
            return True, 1.0, "snapshot matches"

        return False, 0.0, f"snapshot mismatch:\n{diff_text}"

    @property
    def judge_type(self) -> str:
        return "snapshot"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_case_id(expected: object) -> str:
        """Extract case_id from expected, or fall back to default."""
        if isinstance(expected, dict):
            return str(expected.get("case_id", "output"))
        return str(expected) if expected else "output"
