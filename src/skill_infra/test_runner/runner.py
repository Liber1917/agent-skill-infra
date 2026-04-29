"""SkillTestRunner: loads evals.json and drives test execution."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from skill_infra.shared.adapter import AgentAdapter
from skill_infra.shared.evals_schema import validate_evals
from skill_infra.shared.types import EvalCase, EvalReport, EvalResult
from skill_infra.test_runner.judgers.flow import FlowJudge
from skill_infra.test_runner.judgers.keyword import KeywordJudger
from skill_infra.test_runner.judgers.llm_stub import LLMStubJudger
from skill_infra.test_runner.judgers.schema import SchemaJudger

# Default judger registry, keyed by judge_type string
_DEFAULT_JUDGER_REGISTRY = {
    "keyword": KeywordJudger(),
    "schema": SchemaJudger(),
    "llm": LLMStubJudger(),
    "flow": FlowJudge(),
}


class SkillTestRunner:
    """Orchestrates loading, executing, and judging skill test cases.

    Args:
        adapter: The agent backend to send prompts to.
        judger_registry: Optional override for the judger lookup table.
            Defaults to keyword/schema/llm-stub judgers.
    """

    def __init__(
        self,
        adapter: AgentAdapter,
        judger_registry: dict | None = None,  # type: ignore[type-arg]
    ) -> None:
        self._adapter = adapter
        self._registry = judger_registry or _DEFAULT_JUDGER_REGISTRY
        self.cases: list[EvalCase] = []

    # ------------------------------------------------------------------
    # Factory: load from evals.json
    # ------------------------------------------------------------------

    @classmethod
    def from_evals_file(cls, path: str | Path, adapter: AgentAdapter) -> SkillTestRunner:
        """Load EvalCase list from an evals.json file.

        Expected JSON schema::

            {
                "skill": "my-skill",
                "version": "0.1.0",
                "cases": [
                    {
                        "id": "tc-001",
                        "prompt": "...",
                        "expected": { ... },
                        "judge_type": "keyword",
                        "tags": ["smoke"],
                        "timeout": 30
                    }
                ]
            }
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        validate_evals(raw)
        skill_name = raw.get("skill", "unknown")
        version = raw.get("version", "0.0.0")
        runner = cls(adapter=adapter)
        runner.cases = [
            EvalCase(
                id=c["id"],
                prompt=c["prompt"],
                expected=c["expected"],
                judge_type=c["judge_type"],
                tags=c.get("tags", []),
                timeout=c.get("timeout", 30),
            )
            for c in raw.get("cases", [])
        ]
        runner._skill_name = skill_name  # type: ignore[attr-defined]
        runner._skill_version = version  # type: ignore[attr-defined]
        return runner

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_case(self, case: EvalCase) -> EvalResult:
        """Execute a single EvalCase and return its EvalResult.

        Steps:
        1. Call adapter.run(case.prompt, case.timeout)
        2. Look up the appropriate judger by case.judge_type
        3. Call judger.judge(output, case.expected)
        4. Return EvalResult with timing info
        """
        judger = self._registry.get(case.judge_type)
        if judger is None:
            return EvalResult(
                case_id=case.id,
                passed=False,
                actual_output="",
                score=0.0,
                reason=f"unknown judge_type: {case.judge_type!r}",
                elapsed_ms=0,
                error=f"UnknownJudgeType: {case.judge_type!r}",
            )

        start = time.monotonic()
        try:
            output = await self._adapter.run(case.prompt, timeout=case.timeout)
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return EvalResult(
                case_id=case.id,
                passed=False,
                actual_output="",
                score=0.0,
                reason="adapter raised an exception",
                elapsed_ms=elapsed,
                error=repr(exc),
            )

        elapsed = int((time.monotonic() - start) * 1000)
        passed, score, reason = judger.judge(output, case.expected)
        return EvalResult(
            case_id=case.id,
            passed=passed,
            actual_output=output,
            score=score,
            reason=reason,
            elapsed_ms=elapsed,
        )

    async def run_all(
        self,
        cases: list[EvalCase],
        skill_name: str = "unknown",
    ) -> EvalReport:
        """Run all cases sequentially and return an EvalReport.

        Args:
            cases: List of EvalCase to execute.
            skill_name: Label for the report header.
        """
        started_at = datetime.now(tz=UTC).isoformat()
        t0 = time.monotonic()

        results: list[EvalResult] = []
        for case in cases:
            result = await self.run_case(case)
            results.append(result)

        elapsed = int((time.monotonic() - t0) * 1000)
        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        failed_count = total - passed_count
        pass_rate = (passed_count / total) if total > 0 else 1.0

        return EvalReport(
            skill_name=skill_name,
            total=total,
            passed=passed_count,
            failed=failed_count,
            pass_rate=pass_rate,
            results=results,
            started_at=started_at,
            elapsed_ms=elapsed,
        )
