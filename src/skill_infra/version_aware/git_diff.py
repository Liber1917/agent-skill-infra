"""Git diff parser: structured diff analysis for version awareness."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileDiff:
    """Structured representation of a single file's diff."""

    path: str
    status: str  # "added" | "modified" | "deleted" | "renamed"
    additions: int = 0
    deletions: int = 0
    patch: str = ""


@dataclass
class VersionDiff:
    """Structured diff between two git refs."""

    old_sha: str
    new_sha: str
    files: list[FileDiff] = field(default_factory=list)
    summary: str = ""


def parse_version_diff(
    repo_path: str | Path,
    old_ref: str,
    new_ref: str,
) -> VersionDiff:
    """Parse git diff between two refs into a structured VersionDiff.

    Args:
        repo_path: Path to the git repository.
        old_ref: Old commit SHA or ref.
        new_ref: New commit SHA or ref.

    Returns:
        VersionDiff with structured file-level changes.
    """
    repo = str(repo_path)

    if old_ref == new_ref:
        return VersionDiff(old_sha=old_ref, new_sha=new_ref, files=[], summary="No changes")

    # Get list of changed files with stats
    result = subprocess.run(
        ["git", "diff", "--numstat", old_ref, new_ref],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    files: list[FileDiff] = []
    total_add = 0
    total_del = 0

    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                additions = int(parts[0]) if parts[0] != "-" else 0
                deletions = int(parts[1]) if parts[1] != "-" else 0
                filepath = parts[2]

                # Determine status
                # Check if file exists in old ref
                old_exists = _file_exists_in_ref(repo, old_ref, filepath)
                new_exists = _file_exists_in_ref(repo, new_ref, filepath)

                if not old_exists and new_exists:
                    status = "added"
                elif old_exists and not new_exists:
                    status = "deleted"
                else:
                    status = "modified"

                # Get patch for the file
                patch = _get_file_patch(repo, old_ref, new_ref, filepath)

                files.append(
                    FileDiff(
                        path=filepath,
                        status=status,
                        additions=additions,
                        deletions=deletions,
                        patch=patch,
                    )
                )
                total_add += additions
                total_del += deletions

    # Generate summary
    added_count = sum(1 for f in files if f.status == "added")
    modified_count = sum(1 for f in files if f.status == "modified")
    deleted_count = sum(1 for f in files if f.status == "deleted")

    summary_parts: list[str] = []
    if added_count:
        summary_parts.append(f"{added_count} added")
    if modified_count:
        summary_parts.append(f"{modified_count} modified")
    if deleted_count:
        summary_parts.append(f"{deleted_count} deleted")

    summary = ", ".join(summary_parts) if summary_parts else "No file changes"
    summary += f" (+{total_add}/-{total_del})"

    return VersionDiff(
        old_sha=old_ref,
        new_sha=new_ref,
        files=files,
        summary=summary,
    )


def _file_exists_in_ref(repo: str, ref: str, filepath: str) -> bool:
    """Check if a file exists in a given git ref."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}:{filepath}"],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode == 0


def _get_file_patch(repo: str, old_ref: str, new_ref: str, filepath: str) -> str:
    """Get the unified diff patch for a specific file."""
    result = subprocess.run(
        ["git", "diff", old_ref, new_ref, "--", filepath],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout
    return ""
