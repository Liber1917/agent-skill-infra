"""Version-aware CLI: skill-version diff|check|rollback|baseline."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from skill_infra.version_aware.git_diff import parse_version_diff
from skill_infra.version_aware.regression import RegressionDetector
from skill_infra.version_aware.rollback import rollback_to
from skill_infra.version_aware.security_diff import SecurityDiffAnalyzer

app = typer.Typer(
    name="skill-version",
    help="Version-aware skill management (diff, check, rollback, baseline).",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


@app.command()
def diff(
    repo_path: Path = typer.Argument(
        default=None,
        help="Path to the git repository.",
    ),
    old_ref: str = typer.Option(
        "HEAD~1",
        "--old-ref",
        help="Old commit SHA or ref.",
    ),
    new_ref: str = typer.Option(
        "HEAD",
        "--new-ref",
        help="New commit SHA or ref.",
    ),
    output: str = typer.Option(
        "table",
        "--output",
        "-o",
        help="Output format: table or json.",
    ),
) -> None:
    """Show structured diff between two git refs."""
    vd = parse_version_diff(str(repo_path), old_ref, new_ref)

    if output == "json":
        data = {
            "old_sha": vd.old_sha,
            "new_sha": vd.new_sha,
            "files": [
                {
                    "path": f.path,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in vd.files
            ],
        }
        typer.echo(json.dumps(data, indent=2))
        return

    typer.echo(f"Version Diff: {vd.old_sha[:8]}... -> {vd.new_sha[:8]}...")
    if not vd.files:
        typer.echo("0 files changed (empty)")
        return
    typer.echo(f"{len(vd.files)} file(s) changed:")
    for f in vd.files:
        marker = "+" * min(f.additions, 10) + "-" * min(f.deletions, 10)
        typer.echo(f"  {f.status:8s} {f.path:40s} +{f.additions:3d} -{f.deletions:3d}  {marker}")


# ---------------------------------------------------------------------------
# check (diff + security)
# ---------------------------------------------------------------------------


@app.command()
def check(
    repo_path: Path = typer.Argument(
        default=None,
        help="Path to the git repository.",
    ),
    old_ref: str = typer.Option(
        "HEAD~1",
        "--old-ref",
        help="Old commit SHA or ref.",
    ),
    new_ref: str = typer.Option(
        "HEAD",
        "--new-ref",
        help="New commit SHA or ref.",
    ),
    security: bool = typer.Option(
        False,
        "--security",
        help="Include security diff analysis.",
    ),
) -> None:
    """Check diff + security analysis between two refs."""
    vd = parse_version_diff(str(repo_path), old_ref, new_ref)

    typer.echo(f"Version Check: {vd.old_sha[:8]}... -> {vd.new_sha[:8]}...")
    typer.echo(f"Files changed: {len(vd.files)}")
    for f in vd.files:
        typer.echo(f"  {f.path} ({f.status}, +{f.additions}/-{f.deletions})")

    if security and vd.files:
        analyzer = SecurityDiffAnalyzer()
        sec_report = analyzer.analyze(str(repo_path), old_ref, new_ref)

        label = "CHANGES DETECTED" if sec_report.has_security_changes else "clean"
        typer.echo(f"Security: {label}")
        typer.echo(f"Max severity: {sec_report.max_severity}")
        if sec_report.findings:
            for f in sec_report.findings:
                typer.echo(f"  [{f.severity}] {f.file_path}: {f.description}")
    elif not vd.files:
        typer.echo("No files changed — skip security analysis.")


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


@app.command()
def rollback(
    repo_path: Path = typer.Argument(
        default=None,
        help="Path to the git repository.",
    ),
    target_ref: str = typer.Option(
        "HEAD~1",
        "--target-ref",
        help="Ref to roll back to.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Roll back working tree to a previous version."""
    if not yes:
        confirmed = typer.confirm(
            f"Roll back to {target_ref}? This will overwrite working tree changes."
        )
        if not confirmed:
            typer.echo("Aborted.")
            raise typer.Exit(code=1)

    rollback_to(str(repo_path), target_ref)
    typer.echo(f"Rolled back to {target_ref}")


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------


baseline_app = typer.Typer(help="Manage regression baselines.", no_args_is_help=True)
app.add_typer(baseline_app, name="baseline")


@baseline_app.command(name="store")
def baseline_store(
    repo_path: Path = typer.Argument(
        default=None,
        help="Path to the git repository.",
    ),
    case_id: str = typer.Argument(
        default=None,
        help="Test case identifier.",
    ),
    output_file: Path = typer.Argument(
        default=None,
        help="Path to the output file to store as baseline.",
    ),
) -> None:
    """Store a baseline output for regression detection."""
    content = output_file.read_text(encoding="utf-8")
    detector = RegressionDetector(str(repo_path))
    detector.store_baseline(case_id, content)
    typer.echo(f"Baseline stored for case '{case_id}' ({len(content)} bytes)")


@baseline_app.command(name="detect")
def baseline_detect(
    repo_path: Path = typer.Argument(
        default=None,
        help="Path to the git repository.",
    ),
    case_id: str = typer.Argument(
        default=None,
        help="Test case identifier.",
    ),
    output_file: Path = typer.Argument(
        default=None,
        help="Path to the current output file to test.",
    ),
) -> None:
    """Detect regression by comparing output against stored baseline."""
    content = output_file.read_text(encoding="utf-8")
    detector = RegressionDetector(str(repo_path))
    report = detector.detect(case_id, content)

    if report.regressed:
        typer.echo(f"REGRESSION DETECTED for case '{case_id}'")
        typer.echo(report.diff)
        raise typer.Exit(code=1)
    else:
        typer.echo(f"No regression for case '{case_id}'")


if __name__ == "__main__":
    app()
