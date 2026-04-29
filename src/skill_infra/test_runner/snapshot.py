"""SnapshotStore: regression detection via output snapshots."""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from pathlib import Path

# ---------------------------------------------------------------------------
# Built-in normalizers
# ---------------------------------------------------------------------------

_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_TEMP_PATH_RE = re.compile(r"/tmp/[/\w._-]+")


def normalize_timestamps(text: str) -> str:
    """Replace ISO 8601 timestamps with a fixed placeholder."""
    return _TIMESTAMP_RE.sub("<TIMESTAMP>", text)


def normalize_paths(text: str) -> str:
    """Replace /tmp/ paths with a fixed placeholder."""
    return _TEMP_PATH_RE.sub("<TMP_PATH>", text)


def normalize_whitespace(text: str) -> str:
    """Collapse consecutive whitespace to single space."""
    return re.sub(r"[ \t]+", " ", text)


class SnapshotStore:
    """Manages snapshot files for regression detection.

    Snapshots are stored as plain text files under ``__snapshots__/<case_id>.txt``.
    """

    def __init__(
        self,
        snapshot_dir: str | Path,
        normalizers: list[Callable[[str], str]] | None = None,
    ) -> None:
        self._dir = Path(snapshot_dir)
        self._snap_dir = self._dir / "__snapshots__"
        self._normalizers = normalizers or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self, case_id: str) -> str | None:
        """Read an existing snapshot. Returns None if it doesn't exist."""
        path = self._snap_path(case_id)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_snapshot(self, case_id: str, content: str) -> None:
        """Write (or overwrite) a snapshot for the given case ID."""
        self._snap_dir.mkdir(parents=True, exist_ok=True)
        self._snap_path(case_id).write_text(content, encoding="utf-8")

    def has_snapshot(self, case_id: str) -> bool:
        """Check whether a snapshot exists for the given case ID."""
        return self._snap_path(case_id).exists()

    def diff(
        self,
        case_id: str,
        actual: str,
        normalizers: list[Callable[[str], str]] | None = None,
    ) -> tuple[bool, str]:
        """Compare actual output against stored snapshot.

        Returns:
            (matches, diff_text) where matches is True if the content
            matches after normalization, and diff_text is a human-readable
            unified diff (empty string when matches is True).
        """
        snapshot = self.get_snapshot(case_id)
        if snapshot is None:
            return False, ""

        norms = normalizers or self._normalizers
        expected = self._apply(snapshot, norms)
        got = self._apply(actual, norms)

        if expected == got:
            return True, ""

        diff_lines = list(
            difflib.unified_diff(
                expected.splitlines(keepends=True),
                got.splitlines(keepends=True),
                fromfile="snapshot",
                tofile="actual",
            )
        )
        return False, "".join(diff_lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _snap_path(self, case_id: str) -> Path:
        return self._snap_dir / f"{case_id}.txt"

    @staticmethod
    def _apply(text: str, normalizers: list[Callable[[str], str]]) -> str:
        for fn in normalizers:
            text = fn(text)
        return text
