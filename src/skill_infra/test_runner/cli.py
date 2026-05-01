"""CLI entry point for the skill test runner."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC
from pathlib import Path

import typer

from skill_infra.shared.evals_schema import EvalsValidationError
from skill_infra.shared.types import EvalReport, EvalResult
from skill_infra.test_runner.adapters.mock import MockAdapter
from skill_infra.test_runner.report import print_table, report_to_json
from skill_infra.test_runner.runner import SkillTestRunner

app = typer.Typer(
    name="skill-test",
    help="Agent Skill behavior test runner",
    no_args_is_help=True,
)


@app.command()
def run(
    evals_file: Path = typer.Argument(help="Path to evals.json file"),
    adapter: str = typer.Option("mock", help="Agent adapter to use (currently only 'mock')"),
    output: str = typer.Option("table", help="Output format: 'table' or 'json'"),
    fail_fast: bool = typer.Option(False, help="Stop on first failure"),
    update_snapshots: bool = typer.Option(
        False,
        "--update-snapshots",
        help="Overwrite all snapshot baselines with current output.",
    ),
) -> None:
    """Run skill behavior tests from an evals.json file."""
    if adapter == "mock":
        agent = MockAdapter()
    else:
        typer.echo(f"Unknown adapter: {adapter!r}. Only 'mock' is supported in Phase 1.", err=True)
        raise typer.Exit(code=1)

    try:
        runner = SkillTestRunner.from_evals_file(
            evals_file, agent, update_snapshots=update_snapshots
        )
    except EvalsValidationError as exc:
        typer.echo(f"Invalid evals.json: {exc}", err=True)
        raise typer.Exit(code=1) from None
    if not runner.cases:
        typer.echo(f"No test cases found in {evals_file}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Running {len(runner.cases)} test cases with '{adapter}' adapter...\n")

    skill_name = getattr(runner, "_skill_name", evals_file.stem)
    report = asyncio.run(_run_with_fail_fast(runner, runner.cases, skill_name, fail_fast))

    if output == "json":
        typer.echo(report_to_json(report))
    else:
        print_table(report)

    # Exit code: 0 if all passed, 1 if any failed
    if report.passed < report.total:
        raise typer.Exit(code=1)


async def _run_with_fail_fast(
    runner: SkillTestRunner,
    cases: list,
    skill_name: str,
    fail_fast: bool,
) -> EvalReport:
    """Run tests, optionally stopping on first failure."""
    if not fail_fast:
        return await runner.run_all(cases, skill_name=skill_name)

    # fail-fast: run one at a time and stop
    import time
    from datetime import datetime

    started_at = datetime.now(tz=UTC).isoformat()
    t0 = time.monotonic()
    results: list[EvalResult] = []

    for case in cases:
        result = await runner.run_case(case)
        results.append(result)
        if not result.passed:
            break

    elapsed = int((time.monotonic() - t0) * 1000)
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    return EvalReport(
        skill_name=skill_name,
        total=total,
        passed=passed_count,
        failed=total - passed_count,
        pass_rate=(passed_count / total) if total > 0 else 1.0,
        results=results,
        started_at=started_at,
        elapsed_ms=elapsed,
    )


@app.command()
def show(
    report_file: Path = typer.Argument(help="Path to a JSON report file"),
) -> None:
    """Display a previously saved JSON report as a Rich table."""
    data = json.loads(report_file.read_text(encoding="utf-8"))

    # Reconstruct EvalReport from JSON
    results = []
    for r in data["results"]:
        results.append(
            EvalResult(
                case_id=r["case_id"],
                passed=r["passed"],
                actual_output=r.get("actual_output", ""),
                score=r["score"],
                reason=r["reason"],
                elapsed_ms=r["elapsed_ms"],
                error=r.get("error"),
            )
        )

    report = EvalReport(
        skill_name=data["skill_name"],
        total=data["total"],
        passed=data["passed"],
        failed=data["failed"],
        pass_rate=data["pass_rate"],
        results=results,
        started_at=data["started_at"],
        elapsed_ms=data["elapsed_ms"],
    )
    print_table(report)


if __name__ == "__main__":
    app()
