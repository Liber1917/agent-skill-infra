"""Tests for SnapshotStore: regression detection via output snapshots."""

from __future__ import annotations

from pathlib import Path

from skill_infra.test_runner.snapshot import SnapshotStore


class TestSnapshotStore:
    """SnapshotStore manages snapshot files for regression detection."""

    def test_no_snapshot_auto_write(self, tmp_path: Path) -> None:
        """When no snapshot exists, auto-write and report as no baseline."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        assert not store.has_snapshot("tc-001")
        store.write_snapshot("tc-001", "first output")
        assert store.has_snapshot("tc-001")
        assert store.get_snapshot("tc-001") == "first output"

    def test_existing_snapshot_match(self, tmp_path: Path) -> None:
        """Exact match with existing snapshot returns passes."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        store.write_snapshot("tc-001", "expected output")
        matches, diff = store.diff("tc-001", "expected output")
        assert matches is True
        assert diff == ""

    def test_existing_snapshot_mismatch(self, tmp_path: Path) -> None:
        """Content change from existing snapshot returns diff."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        store.write_snapshot("tc-001", "original output")
        matches, diff = store.diff("tc-001", "changed output")
        assert matches is False
        assert "original" in diff or "changed" in diff or "-" in diff or "+" in diff

    def test_normalize_timestamps(self, tmp_path: Path) -> None:
        """Timestamp normalization should make outputs with different timestamps match."""
        from skill_infra.test_runner.snapshot import normalize_timestamps

        store = SnapshotStore(snapshot_dir=tmp_path, normalizers=[normalize_timestamps])
        store.write_snapshot("tc-002", "Generated at 2025-01-01T00:00:00Z")
        matches, _diff = store.diff("tc-002", "Generated at 2026-06-15T12:30:00Z")
        assert matches is True

    def test_normalize_paths(self, tmp_path: Path) -> None:
        """Path normalization should make outputs with different temp paths match."""
        from skill_infra.test_runner.snapshot import normalize_paths

        store = SnapshotStore(snapshot_dir=tmp_path, normalizers=[normalize_paths])
        store.write_snapshot("tc-003", "File at /tmp/abc123/data.txt")
        matches, _diff = store.diff("tc-003", "File at /tmp/xyz789/data.txt")
        assert matches is True

    def test_normalize_whitespace(self, tmp_path: Path) -> None:
        """Whitespace normalization should collapse extra whitespace."""
        from skill_infra.test_runner.snapshot import normalize_whitespace

        store = SnapshotStore(snapshot_dir=tmp_path, normalizers=[normalize_whitespace])
        store.write_snapshot("tc-004", "hello  world")
        matches, _diff = store.diff("tc-004", "hello    world")
        assert matches is True

    def test_multiple_snapshots(self, tmp_path: Path) -> None:
        """Different case IDs should have independent snapshots."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        store.write_snapshot("tc-001", "output for tc-001")
        store.write_snapshot("tc-002", "output for tc-002")
        assert store.get_snapshot("tc-001") == "output for tc-001"
        assert store.get_snapshot("tc-002") == "output for tc-002"
        assert store.has_snapshot("tc-001")
        assert store.has_snapshot("tc-002")
        assert not store.has_snapshot("tc-003")

    def test_update_snapshot(self, tmp_path: Path) -> None:
        """Writing a snapshot should update the existing one."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        store.write_snapshot("tc-001", "v1")
        store.write_snapshot("tc-001", "v2")
        assert store.get_snapshot("tc-001") == "v2"
        matches, _diff = store.diff("tc-001", "v2")
        assert matches is True

    def test_snapshot_file_location(self, tmp_path: Path) -> None:
        """Snapshots should be stored in __snapshots__ subdirectory."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        store.write_snapshot("tc-001", "data")
        expected_file = tmp_path / "__snapshots__" / "tc-001.txt"
        assert expected_file.exists()
        assert expected_file.read_text() == "data"

    def test_diff_format_is_readable(self, tmp_path: Path) -> None:
        """Diff output should be human-readable unified diff format."""
        store = SnapshotStore(snapshot_dir=tmp_path)
        store.write_snapshot("tc-001", "line1\nline2\nline3")
        _matches, diff = store.diff("tc-001", "line1\nmodified\nline3")
        # Should contain unified diff markers
        assert "---" in diff or "+++" in diff
