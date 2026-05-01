"""Quality check CLI: skill-quality check <path>."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from skill_infra.quality_check.checkers import HelloAndyChecker, TriggerChecker
from skill_infra.quality_check.parser import parse_skill_md
from skill_infra.quality_check.scorecard import QualityReport

app = typer.Typer(
    name="skill-quality",
    help="Quality assessment for Agent Skills (SKILL.md files).",
    no_args_is_help=True,
)


@app.command()
def check(
    skill_path: Path = typer.Argument(
        default=None,
        help="Path to the SKILL.md file or skill directory.",
    ),
    output: str = typer.Option(
        "table",
        "--output",
        "-o",
        help="Output format: table or json.",
    ),
    security: bool = typer.Option(
        False,
        "--security",
        help="Include security scan (requires cisco-scanner).",
    ),
    lint: bool = typer.Option(
        False,
        "--lint",
        help="Include agent-skill-linter check (requires npx).",
    ),
) -> None:
    """Run quality checks on a SKILL.md file."""
    # Resolve path: if directory, look for SKILL.md inside
    target = skill_path
    if target.is_dir():
        target = target / "SKILL.md"
    if not target.exists():
        typer.echo(f"Error: {target} not found", err=True)
        raise typer.Exit(code=1)

    # Parse
    try:
        parsed = parse_skill_md(str(target))
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    # Run checkers
    trigger = TriggerChecker().check(parsed)
    helloandy = HelloAndyChecker().check(parsed)

    dimensions = [trigger, helloandy]

    # Security scan (optional)
    if security:
        from skill_infra.quality_check.security_integration import SecurityIntegration

        sec_result = SecurityIntegration().run(str(target))
        dimensions.append(sec_result)

    # Linter integration (optional)
    if lint:
        from skill_infra.quality_check.linter_adapter import LinterAdapter
        from skill_infra.quality_check.scorecard import DimensionScore

        adapter = LinterAdapter()
        linter_result = adapter.run(target)
        lint_score = 1.0 if linter_result.passed else 0.5
        lint_findings = [f"[{v.severity}] {v.rule}: {v.message}" for v in linter_result.violations]
        if not lint_findings:
            lint_findings.append("No linter violations found.")
        dimensions.append(
            DimensionScore(
                name="agent-skill-linter",
                score=lint_score,
                findings=lint_findings,
            )
        )

    report = QualityReport.from_dimensions(
        skill_name=parsed.meta.name,
        dimensions=dimensions,
        file_path=str(target),
        total_lines=parsed.total_lines,
        token_estimate=parsed.token_estimate,
    )

    # Output
    if output == "json":
        _print_json(report)
    else:
        _print_table(report)


def _print_table(report: QualityReport) -> None:
    """Print report as a human-readable table."""
    typer.echo(f"Quality Report: {report.skill_name}")
    typer.echo(f"Overall Score: {report.overall_label}")
    typer.echo(f"File: {report.file_path}")
    typer.echo(f"Lines: {report.total_lines} | Est. Tokens: {report.token_estimate}")
    typer.echo()

    for dim in report.dimensions:
        typer.echo(f"  {dim.name}: {dim.label}")
        for finding in dim.findings:
            typer.echo(f"    - {finding}")
        typer.echo()

    # Exit code: 0 if score >= 0.5, 1 otherwise
    if report.overall_score < 0.5:
        raise typer.Exit(code=1)


def _print_json(report: QualityReport) -> None:
    """Print report as JSON."""
    data = {
        "skill_name": report.skill_name,
        "overall_score": report.overall_score,
        "file_path": report.file_path,
        "total_lines": report.total_lines,
        "token_estimate": report.token_estimate,
        "dimensions": [
            {
                "name": dim.name,
                "score": dim.score,
                "findings": dim.findings,
            }
            for dim in report.dimensions
        ],
    }
    typer.echo(json.dumps(data, indent=2))


if __name__ == "__main__":
    app()
