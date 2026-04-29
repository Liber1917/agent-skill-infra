"""Report formatting: Rich table and JSON output."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from skill_infra.shared.types import EvalReport

console = Console()


def format_table(report: EvalReport) -> Table:
    """Build a Rich Table from an EvalReport."""
    table = Table(title=f"Skill Test Report: {report.skill_name}")
    table.add_column("Case ID", style="cyan", no_wrap=True)
    table.add_column("Pass", justify="center")
    table.add_column("Score", justify="right")
    table.add_column("Time (ms)", justify="right")
    table.add_column("Reason", max_width=50)

    for r in report.results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(r.case_id, status, f"{r.score:.3f}", str(r.elapsed_ms), r.reason)

    # Summary row
    rate = f"{report.pass_rate:.1%}"
    table.add_section()
    table.add_row(
        f"Total: {report.total}",
        f"Passed: {report.passed}",
        f"Failed: {report.failed}",
        f"Rate: {rate}",
        f"Time: {report.elapsed_ms}ms",
        style="bold",
    )

    return table


def print_table(report: EvalReport) -> None:
    """Print the report as a Rich table to stdout."""
    table = format_table(report)
    console.print(table)


def report_to_json(report: EvalReport) -> str:
    """Serialize an EvalReport to a JSON string."""
    data = {
        "skill_name": report.skill_name,
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": round(report.pass_rate, 4),
        "started_at": report.started_at,
        "elapsed_ms": report.elapsed_ms,
        "results": [
            {
                "case_id": r.case_id,
                "passed": r.passed,
                "score": round(r.score, 4),
                "elapsed_ms": r.elapsed_ms,
                "reason": r.reason,
                "error": r.error,
                "actual_output": r.actual_output[:200] if r.actual_output else None,
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
