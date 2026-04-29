"""Tests for Git diff parser and rollback."""

from __future__ import annotations

import subprocess


def _git_init_repo(tmp_path):
    """Initialize a git repo with some commits for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    # Commit 1: initial file
    (tmp_path / "file1.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    sha1 = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        .stdout.strip()
        .decode()
    )

    # Commit 2: modify file1, add file2
    (tmp_path / "file1.txt").write_text("hello world\n", encoding="utf-8")
    (tmp_path / "file2.txt").write_text("new file\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "update"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    sha2 = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        .stdout.strip()
        .decode()
    )

    return sha1, sha2


class TestGitDiffParser:
    def test_parse_diff_modified_file(self, tmp_path) -> None:
        from skill_infra.version_aware.git_diff import parse_version_diff

        sha1, sha2 = _git_init_repo(tmp_path)
        diff = parse_version_diff(str(tmp_path), sha1, sha2)

        assert diff.old_sha == sha1
        assert diff.new_sha == sha2
        assert len(diff.files) >= 1
        # file1.txt was modified
        modified = [f for f in diff.files if "file1.txt" in f.path]
        assert len(modified) >= 1
        assert modified[0].status == "modified"
        assert modified[0].additions > 0

    def test_parse_diff_added_file(self, tmp_path) -> None:
        from skill_infra.version_aware.git_diff import parse_version_diff

        sha1, sha2 = _git_init_repo(tmp_path)
        diff = parse_version_diff(str(tmp_path), sha1, sha2)

        added = [f for f in diff.files if "file2.txt" in f.path]
        assert len(added) >= 1
        assert added[0].status == "added"

    def test_parse_diff_same_ref(self, tmp_path) -> None:
        from skill_infra.version_aware.git_diff import parse_version_diff

        sha1, _sha2 = _git_init_repo(tmp_path)
        diff = parse_version_diff(str(tmp_path), sha1, sha1)

        assert diff.old_sha == sha1
        assert diff.new_sha == sha1
        assert len(diff.files) == 0


class TestRollback:
    def test_rollback_to_previous(self, tmp_path) -> None:
        from skill_infra.version_aware.rollback import rollback_to

        sha1, _sha2 = _git_init_repo(tmp_path)

        # Current content should be commit 2
        assert (tmp_path / "file1.txt").read_text() == "hello world\n"
        assert (tmp_path / "file2.txt").exists()

        # Rollback to sha1
        result = rollback_to(str(tmp_path), sha1)
        assert result["target_sha"] == sha1
        assert len(result["files"]) >= 0

        # file1 should be back to initial content, file2 should still exist
        assert (tmp_path / "file1.txt").read_text() == "hello\n"

    def test_get_previous_sha(self, tmp_path) -> None:
        from skill_infra.version_aware.rollback import get_previous_sha

        sha1, _sha2 = _git_init_repo(tmp_path)

        prev = get_previous_sha(str(tmp_path))
        assert prev == sha1

    def test_get_previous_sha_single_commit(self, tmp_path) -> None:
        from skill_infra.version_aware.rollback import get_previous_sha

        # Only one commit
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "file.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "first"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        prev = get_previous_sha(str(tmp_path))
        assert prev is None
