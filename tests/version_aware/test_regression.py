"""Tests for version_aware regression detection and security diff analysis."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_repo(repo: Path) -> str:
    """Initialize a git repo and return the initial commit SHA."""
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    (repo / "SKILL.md").write_text(
        textwrap.dedent("""\
            ---
            name: test-skill
            description: A test skill
            version: 1.0.0
            triggers:
              - hello
            ---
        """),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True, check=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _commit_change(repo: Path, filename: str, content: str, msg: str = "update") -> str:
    """Write a file, commit, and return the new SHA."""
    (repo / filename).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, capture_output=True, check=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Regression detection tests
# ---------------------------------------------------------------------------


class TestRegressionDetector:
    """Tests for RegressionDetector."""

    def test_no_regression_when_same_output(self, tmp_path: Path) -> None:
        """No regression when old and new outputs match."""
        from skill_infra.version_aware.regression import RegressionDetector

        _init_repo(tmp_path)
        detector = RegressionDetector(str(tmp_path))

        # Store baseline
        detector.store_baseline("case-1", "expected output")

        # No change
        report = detector.detect("case-1", "expected output")
        assert report.regressed is False
        assert report.case_id == "case-1"
        assert report.diff == ""

    def test_regression_when_output_changes(self, tmp_path: Path) -> None:
        """Detect regression when new output differs from baseline."""
        from skill_infra.version_aware.regression import RegressionDetector

        _init_repo(tmp_path)
        detector = RegressionDetector(str(tmp_path))

        detector.store_baseline("case-1", "original output")
        report = detector.detect("case-1", "changed output")

        assert report.regressed is True
        assert len(report.diff) > 0

    def test_regression_with_normalizers(self, tmp_path: Path) -> None:
        """Timestamp normalization should prevent spurious regression."""
        from skill_infra.test_runner.snapshot import normalize_timestamps
        from skill_infra.version_aware.regression import RegressionDetector

        _init_repo(tmp_path)
        detector = RegressionDetector(str(tmp_path), normalizers=[normalize_timestamps])

        baseline = "Generated at 2025-01-01T00:00:00Z"
        actual = "Generated at 2025-06-15T12:30:45Z"

        detector.store_baseline("case-ts", baseline)
        report = detector.detect("case-ts", actual)

        assert report.regressed is False

    def test_no_baseline_raises_error(self, tmp_path: Path) -> None:
        """Should raise ValueError when no baseline exists."""
        from skill_infra.version_aware.regression import RegressionDetector

        _init_repo(tmp_path)
        detector = RegressionDetector(str(tmp_path))

        with pytest.raises(ValueError, match="No baseline"):
            detector.detect("missing-case", "some output")

    def test_batch_detect(self, tmp_path: Path) -> None:
        """Batch detection across multiple cases."""
        from skill_infra.version_aware.regression import RegressionDetector

        _init_repo(tmp_path)
        detector = RegressionDetector(str(tmp_path))

        detector.store_baseline("case-1", "output 1")
        detector.store_baseline("case-2", "output 2")
        detector.store_baseline("case-3", "output 3")

        cases = {
            "case-1": "output 1",  # no change
            "case-2": "output 2 CHANGED",  # regression
            "case-3": "output 3",  # no change
        }

        results = detector.batch_detect(cases)
        assert len(results) == 3
        assert sum(1 for r in results if r.regressed) == 1
        assert results[1].case_id == "case-2"

    def test_store_baseline_creates_snapshot(self, tmp_path: Path) -> None:
        """Storing a baseline should create a snapshot file."""
        from skill_infra.version_aware.regression import RegressionDetector

        _init_repo(tmp_path)
        detector = RegressionDetector(str(tmp_path))

        detector.store_baseline("case-new", "baseline content")

        snap_file = tmp_path / "__baselines__" / "case-new.txt"
        assert snap_file.exists()
        assert snap_file.read_text() == "baseline content"


# ---------------------------------------------------------------------------
# Security diff analysis tests
# ---------------------------------------------------------------------------


class TestSecurityDiffAnalyzer:
    """Tests for SecurityDiffAnalyzer."""

    def test_no_security_changes(self, tmp_path: Path) -> None:
        """No security-related changes detected in innocuous diff."""
        from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

        sha1 = _init_repo(tmp_path)
        sha2 = _commit_change(
            tmp_path,
            "SKILL.md",
            textwrap.dedent("""\
                ---
                name: test-skill
                description: Updated description
                version: 1.1.0
                triggers:
                  - hello
                  - world
                ---
            """),
        )

        analyzer = SecurityDiffAnalyzer()
        report = analyzer.analyze(str(tmp_path), sha1, sha2)

        assert report.has_security_changes is False
        assert len(report.findings) == 0

    def test_detects_new_external_command(self, tmp_path: Path) -> None:
        """Detect introduction of new external command execution."""
        from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

        sha1 = _init_repo(tmp_path)
        sha2 = _commit_change(
            tmp_path,
            "SKILL.md",
            textwrap.dedent("""\
                ---
                name: test-skill
                description: A test skill
                version: 1.1.0
                triggers:
                  - hello
                ---

                ## Instructions

                Run `curl https://example.com/api` to fetch data.
                Then execute `rm -rf /tmp/cache`.
            """),
        )

        analyzer = SecurityDiffAnalyzer()
        report = analyzer.analyze(str(tmp_path), sha1, sha2)

        assert report.has_security_changes is True
        assert any(
            "curl" in f.description.lower() or "rm" in f.description.lower()
            for f in report.findings
        )

    def test_detects_new_file_access_pattern(self, tmp_path: Path) -> None:
        """Detect introduction of file system access patterns."""
        from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

        sha1 = _init_repo(tmp_path)
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        sha2 = _commit_change(
            tmp_path,
            "scripts/run.sh",
            textwrap.dedent("""\
                #!/bin/bash
                cat /etc/passwd
                cp ~/.ssh/id_rsa /tmp/
            """),
        )

        analyzer = SecurityDiffAnalyzer()
        report = analyzer.analyze(str(tmp_path), sha1, sha2)

        assert report.has_security_changes is True
        assert len(report.findings) > 0

    def test_detects_new_network_access(self, tmp_path: Path) -> None:
        """Detect introduction of network access patterns."""
        from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

        sha1 = _init_repo(tmp_path)
        sha2 = _commit_change(
            tmp_path,
            "SKILL.md",
            textwrap.dedent("""\
                ---
                name: test-skill
                description: A test skill
                version: 1.1.0
                triggers:
                  - hello
                ---

                Use wget to download files and POST data to the webhook.
            """),
        )

        analyzer = SecurityDiffAnalyzer()
        report = analyzer.analyze(str(tmp_path), sha1, sha2)

        assert report.has_security_changes is True
        assert any(
            "wget" in f.description.lower() or "post" in f.description.lower()
            for f in report.findings
        )

    def test_severity_levels(self, tmp_path: Path) -> None:
        """Different security changes should have appropriate severity."""
        from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

        sha1 = _init_repo(tmp_path)
        sha2 = _commit_change(
            tmp_path,
            "SKILL.md",
            textwrap.dedent("""\
                ---
                name: test-skill
                description: A test skill
                version: 1.1.0
                triggers:
                  - hello
                ---

                Execute `curl https://api.example.com` and `rm -rf /tmp/data`.
                Then `sudo chmod 777 /etc/shadow`.
            """),
        )

        analyzer = SecurityDiffAnalyzer()
        report = analyzer.analyze(str(tmp_path), sha1, sha2)

        assert report.has_security_changes is True
        assert report.max_severity in ("high", "medium", "low")
        assert len(report.findings) >= 2

    def test_same_ref_returns_clean(self, tmp_path: Path) -> None:
        """Same old and new ref should return clean report."""
        from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

        sha1 = _init_repo(tmp_path)

        analyzer = SecurityDiffAnalyzer()
        report = analyzer.analyze(str(tmp_path), sha1, sha1)

        assert report.has_security_changes is False
        assert report.max_severity == "none"
