"""Quality check CLI: skill-quality check <path>."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from skill_infra.quality_check.auto_fix import AutoFixSuggester
from skill_infra.quality_check.capability_discovery import CapabilityDiscoverer, CapabilityReport
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
    llm: bool = typer.Option(
        False,
        "--llm",
        help="Use LLM-based quality evaluation (requires ANTHROPIC_API_KEY).",
    ),
    gh_models: bool = typer.Option(
        False,
        "--gh-models",
        help="Use GitHub Models free API for evaluation (requires GITHUB_TOKEN).",
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
    # When using LLM, use its trigger_precision instead of keyword-based
    if gh_models:
        from skill_infra.quality_check.gh_model_quality import GitHubModelQualityChecker

        gh_checker = GitHubModelQualityChecker()
        if gh_checker.is_available():
            helloandy = gh_checker.check(parsed)
            llm_trigger = gh_checker.extract_trigger()
            llm_7dim = gh_checker.extract_helloandy_excluding_trigger()
            if llm_trigger and llm_7dim:
                trigger = llm_trigger
                helloandy = llm_7dim
            else:
                trigger = TriggerChecker().check(parsed)
                helloandy = HelloAndyChecker().check(parsed)
        else:
            typer.echo(
                "Warning: --gh-models set but no GITHUB_TOKEN, using fallback",
                err=True,
            )
            trigger = TriggerChecker().check(parsed)
            helloandy = HelloAndyChecker().check(parsed)
    elif llm:
        from skill_infra.quality_check.llm_quality import LLMQualityChecker

        quality_llm = LLMQualityChecker()
        if quality_llm.is_available():
            helloandy = quality_llm.check(parsed)
            llm_trigger = quality_llm.extract_trigger()
            llm_7dim = quality_llm.extract_helloandy_excluding_trigger()
            if llm_trigger and llm_7dim:
                trigger = llm_trigger
                helloandy = llm_7dim
            else:
                trigger = TriggerChecker().check(parsed)
                helloandy = HelloAndyChecker().check(parsed)
        else:
            typer.echo(
                "Warning: --llm set but no ANTHROPIC_API_KEY, using fallback",
                err=True,
            )
            trigger = TriggerChecker().check(parsed)
            helloandy = HelloAndyChecker().check(parsed)
    else:
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
    if gh_models:
        report.model = "gpt-4o-mini (GitHub Models)"
    elif llm:
        report.model = "claude-sonnet-4 (Anthropic)"
    else:
        report.model = "keyword-heuristic"

    # Output
    if output == "json":
        _print_json(report)
    else:
        _print_table(report)


@app.command()
def discover(
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
) -> None:
    """Discover current and potential capabilities of a SKILL.md file."""
    # Resolve path
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

    # Discover
    discoverer = CapabilityDiscoverer()
    report = discoverer.discover(parsed)

    # Output
    if output == "json":
        _print_discover_json(report)
    else:
        _print_discover_table(report, target)


def _print_discover_table(report: CapabilityReport, target: Path) -> None:
    """Print capability discovery results as a human-readable table."""
    typer.echo(f"Capability Report: {report.skill_name}")
    typer.echo(f"File: {target}")
    typer.echo(f"Summary: {report.summary}")
    typer.echo(f"Current: {report.total_current} | Potential: {report.total_potential}")
    typer.echo()

    current = [c for c in report.capabilities if c.is_current]
    potential = [c for c in report.capabilities if not c.is_current]

    if current:
        typer.echo("--- Current Capabilities ---")
        for cap in current:
            typer.echo(f"  {cap.name} (confidence: {cap.confidence:.0%})")
            typer.echo(f"    {cap.description}")
            for ev in cap.evidence:
                typer.echo(f"    • {ev}")
            if cap.expansion_suggestion:
                typer.echo(f"    → {cap.expansion_suggestion}")
            typer.echo()

    if potential:
        typer.echo("--- Potential Capabilities ---")
        for cap in potential:
            typer.echo(f"  {cap.name} (confidence: {cap.confidence:.0%})")
            typer.echo(f"    {cap.description}")
            if cap.evidence:
                for ev in cap.evidence:
                    typer.echo(f"    • {ev}")
            typer.echo(f"    → {cap.expansion_suggestion}")
            typer.echo()


def _print_discover_json(report: CapabilityReport) -> None:
    """Print capability discovery results as JSON."""
    data = {
        "skill_name": report.skill_name,
        "summary": report.summary,
        "total_current": report.total_current,
        "total_potential": report.total_potential,
        "capabilities": [
            {
                "name": c.name,
                "description": c.description,
                "is_current": c.is_current,
                "confidence": c.confidence,
                "evidence": c.evidence,
                "expansion_suggestion": c.expansion_suggestion,
            }
            for c in report.capabilities
        ],
    }
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _print_table(report: QualityReport) -> None:
    """Print report as a human-readable table."""
    typer.echo(f"Quality Report: {report.skill_name}")
    typer.echo(f"Overall Score: {report.overall_label} — {report.decision_label}")
    typer.echo(f"Model: {report.model}")
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


@app.command()
def suggest(
    skill_path: Path = typer.Argument(
        default=None,
        help="Path to the SKILL.md file or skill directory.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply suggested fixes in-place (creates .backup).",
    ),
    gh_models: bool = typer.Option(
        False,
        "--gh-models",
        help="Use GitHub Models API for quality evaluation (requires GITHUB_TOKEN).",
    ),
) -> None:
    """Generate quality improvement suggestions for a SKILL.md file."""
    target = skill_path
    if target.is_dir():
        target = target / "SKILL.md"
    if not target.exists():
        typer.echo(f"Error: {target} not found", err=True)
        raise typer.Exit(code=1)

    try:
        parsed = parse_skill_md(str(target))
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    # Build a QualityReport to feed into the suggester
    if gh_models:
        from skill_infra.quality_check.gh_model_quality import GitHubModelQualityChecker

        gh_checker = GitHubModelQualityChecker()
        if gh_checker.is_available():
            helloandy = gh_checker.check(parsed)
            llm_trigger = gh_checker.extract_trigger()
            if llm_trigger:
                trigger = llm_trigger
                helloandy = gh_checker.extract_helloandy_excluding_trigger() or helloandy
            else:
                trigger = TriggerChecker().check(parsed)
                helloandy = HelloAndyChecker().check(parsed)
        else:
            typer.echo(
                "Warning: --gh-models set but no GITHUB_TOKEN, using fallback",
                err=True,
            )
            trigger = TriggerChecker().check(parsed)
            helloandy = HelloAndyChecker().check(parsed)
    else:
        trigger = TriggerChecker().check(parsed)
        helloandy = HelloAndyChecker().check(parsed)

    report = QualityReport.from_dimensions(
        skill_name=parsed.meta.name,
        dimensions=[trigger, helloandy],
        file_path=str(target),
        total_lines=parsed.total_lines,
        token_estimate=parsed.token_estimate,
    )
    if gh_models:
        report.model = "gpt-4o-mini (GitHub Models)"
    else:
        report.model = "keyword-heuristic"

    # Generate suggestions
    suggester = AutoFixSuggester()
    result = suggester.suggest(
        report=report,
        parsed=parsed,
        apply=apply,
        file_path=str(target) if apply else "",
    )

    if result.apply_error:
        typer.echo(f"Error: {result.apply_error}", err=True)
        raise typer.Exit(code=1)

    if not result.suggestions:
        if not suggester.is_available():
            typer.echo(
                "Error: GITHUB_TOKEN not set. Cannot generate LLM-based suggestions.",
                err=True,
            )
        else:
            typer.echo("No suggestions generated (skill may already be well-optimized).")
        raise typer.Exit(code=1)

    typer.echo(f"Suggestions for: {result.skill_name}")
    typer.echo()

    for s in result.suggestions:
        status = "✓" if s.applied else ""
        typer.echo(f"  [{s.dimension}] (score: {s.score:.2f}) {status}")
        typer.echo(f"    {s.suggestion}")
        if s.error:
            typer.echo(f"    Error: {s.error}")
        if s.replace:
            rp = s.replace[:60]
            if len(s.replace) > 60:
                rp += "..."
            rw = s.replace_with[:60]
            if len(s.replace_with) > 60:
                rw += "..."
            typer.echo(f"    Replace: {rp}")
            typer.echo(f"    With:    {rw}")
        typer.echo()

    if apply:
        typer.echo(
            f"Applied {result.applied_count}/{len(result.suggestions)} suggestions "
            f"({result.failed_count} failed)."
        )
        if result.backup_path:
            typer.echo(f"Backup saved to: {result.backup_path}")


def _print_json(report: QualityReport) -> None:
    """Print report as JSON."""
    data = {
        "skill_name": report.skill_name,
        "overall_score": report.overall_score,
        "decision": report.decision,
        "model": report.model,
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
