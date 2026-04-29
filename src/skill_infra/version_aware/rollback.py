"""Rollback: revert to a previous git version."""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_previous_sha(repo_path: str | Path) -> str | None:
    """Get the SHA of the previous commit (HEAD~1).

    Returns None if there is only one commit in the repository.
    """
    repo = str(repo_path)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    sha = result.stdout.strip()
    return sha if sha else None


def rollback_to(
    repo_path: str | Path,
    target_sha: str,
) -> dict:
    """Rollback working tree files to a specific commit.

    This performs `git checkout <sha> -- .` which restores all files
    to the state at the target commit, but does NOT move HEAD.

    Args:
        repo_path: Path to the git repository.
        target_sha: Commit SHA to rollback to.

    Returns:
        Dict with target_sha and list of affected files.
    """
    repo = str(repo_path)

    # Get list of files that would change
    diff_result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", target_sha],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    affected_files = diff_result.stdout.strip().splitlines() if diff_result.returncode == 0 else []

    # Perform the checkout
    checkout_result = subprocess.run(
        ["git", "checkout", target_sha, "--", "."],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    if checkout_result.returncode != 0:
        raise RuntimeError(f"Rollback failed: {checkout_result.stderr}")

    return {
        "target_sha": target_sha,
        "files": affected_files,
    }
