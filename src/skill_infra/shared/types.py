"""Core data types for agent-skill-infra."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillMeta:
    """Parsed metadata from a SKILL.md file."""

    name: str
    description: str
    version: str = "0.0.0"
    triggers: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # type: ignore[type-arg]


@dataclass
class EvalCase:
    """A single test case loaded from evals.json."""

    id: str
    prompt: str  # Input sent to the agent
    expected: dict  # type: ignore[type-arg]  # Interpreted by the judger
    judge_type: str  # "keyword" | "schema" | "llm"
    tags: list[str] = field(default_factory=list)
    timeout: int = 30  # seconds


@dataclass
class EvalResult:
    """Result of executing a single EvalCase."""

    case_id: str
    passed: bool
    actual_output: str
    score: float  # 0.0-1.0
    reason: str
    elapsed_ms: int
    error: str | None = None


@dataclass
class EvalReport:
    """Aggregated report of a complete test run."""

    skill_name: str
    total: int
    passed: int
    failed: int
    pass_rate: float  # passed / total
    results: list[EvalResult]
    started_at: str  # ISO 8601
    elapsed_ms: int
