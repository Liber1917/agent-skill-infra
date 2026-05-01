"""Tests for SnapshotJudger: auto-baseline, diff, update-snapshots."""

from __future__ import annotations

import tempfile
from pathlib import Path

from skill_infra.test_runner.judgers.snapshot_judge import SnapshotJudger


class TestSnapshotJudger:
    """Test the snapshot-based judger with auto-baseline and update modes."""

    def test_auto_baseline_first_run(self) -> None:
        """First run with auto-baseline stores output and passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(snapshot_dir=tmpdir, auto_baseline=True)
            passed, score, reason = judger.judge("hello world", {})

            assert passed is True
            assert score == 1.0
            assert "baseline" in reason
            # Snapshot file should exist
            snap_path = Path(tmpdir) / "__snapshots__" / "output.txt"
            assert snap_path.exists()
            assert snap_path.read_text() == "hello world"

    def test_auto_baseline_second_run_match(self) -> None:
        """Second run with same output matches snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(snapshot_dir=tmpdir, auto_baseline=True)

            # First run — stores baseline
            judger.judge("hello world", {})
            # Second run — should match
            passed, score, reason = judger.judge("hello world", {})

            assert passed is True
            assert score == 1.0
            assert "snapshot matches" in reason

    def test_auto_baseline_mismatch_detects_regression(self) -> None:
        """Changed output is detected as snapshot mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(snapshot_dir=tmpdir, auto_baseline=True)

            # Store baseline
            judger.judge("version 1 output", {})
            # Change output
            passed, score, reason = judger.judge("version 2 output modified", {})

            assert passed is False
            assert score == 0.0
            assert "snapshot mismatch" in reason
            # Diff should show changes
            assert "+version 2" in reason or "-version 1" in reason

    def test_update_snapshots_mode(self) -> None:
        """Update-snapshots mode always passes and overwrites."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(
                snapshot_dir=tmpdir,
                auto_baseline=True,
                update_snapshots=True,
            )

            # Store initial
            judger.judge("original", {})
            # Update snapshot with new output
            passed, score, reason = judger.judge("updated output", {})

            assert passed is True
            assert score == 1.0
            assert "snapshot updated" in reason

            # Verify snapshot was overwritten
            snap_path = Path(tmpdir) / "__snapshots__" / "output.txt"
            assert snap_path.read_text() == "updated output"

    def test_case_id_from_expected(self) -> None:
        """Expected dict with case_id controls snapshot filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(snapshot_dir=tmpdir, auto_baseline=True)

            judger.judge("data-a", {"case_id": "case-a"})
            judger.judge("data-b", {"case_id": "case-b"})

            snap_a = Path(tmpdir) / "__snapshots__" / "case-a.txt"
            snap_b = Path(tmpdir) / "__snapshots__" / "case-b.txt"
            assert snap_a.read_text() == "data-a"
            assert snap_b.read_text() == "data-b"

    def test_judge_type_property(self) -> None:
        """judge_type returns 'snapshot'."""
        judger = SnapshotJudger()
        assert judger.judge_type == "snapshot"

    def test_no_auto_baseline_without_snapshot(self) -> None:
        """Without auto-baseline and no existing snapshot, fails cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(snapshot_dir=tmpdir, auto_baseline=False)
            passed, _score, _reason = judger.judge("some output", {})

            # No snapshot exists and auto_baseline is off — diff returns (False, "")
            assert passed is False
            assert _score == 0.0

    def test_normalizers_reduce_false_positives(self) -> None:
        """Timestamps and paths in output don't cause false mismatches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judger = SnapshotJudger(snapshot_dir=tmpdir, auto_baseline=True)

            # Store baseline with a timestamp
            judger.judge("Output at 2024-01-01T12:00:00Z", {})
            # Same content, different timestamp — should match after normalization
            passed, _score, reason = judger.judge(
                "Output at 2025-06-15T08:30:00Z", {}
            )

            assert passed is True, f"Normalizers should strip timestamps. Got: {reason}"
            assert "snapshot matches" in reason
