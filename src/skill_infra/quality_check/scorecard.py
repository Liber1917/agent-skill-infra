"""Quality scorecard: data structures for quality assessment results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    name: str
    score: float  # 0.0 - 1.0
    findings: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """Human-readable label: score as percentage."""
        return f"{self.score:.0%}"


@dataclass
class QualityReport:
    """Aggregated quality assessment report for a skill."""

    skill_name: str
    overall_score: float  # 0.0 - 1.0
    dimensions: list[DimensionScore] = field(default_factory=list)
    file_path: str = ""
    total_lines: int = 0
    token_estimate: int = 0
    model: str = ""  # e.g. "gpt-4o-mini"
    score_interval: str = ""  # e.g. "41% ± 2%"

    @property
    def decision(self) -> str:
        """Three-state output based on overall score.
        
        Thresholds calibrated on n=27 OpenClaw official skills:
        P25=63, P50=66, P75=70. Conservative pass at median.
        """
        if self.overall_score >= 0.63:
            return "pass"
        if self.overall_score >= 0.50:
            return "quarantine"
        return "reject"

    @property
    def decision_label(self) -> str:
        """Human-readable decision with emoji."""
        labels = {
            "pass": "✅ SKILL.md well-documented",
            "quarantine": "⚠️ SKILL.md needs improvement",
            "reject": "❌ SKILL.md requires revision",
        }
        return labels.get(self.decision, self.decision)

    @property
    def overall_label(self) -> str:
        """Human-readable overall score as percentage."""
        return f"{self.overall_score:.0%}"

    def get_dimension(self, name: str) -> DimensionScore | None:
        """Look up a dimension score by name."""
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        return None

    @classmethod
    def from_dimensions(
        cls,
        skill_name: str,
        dimensions: list[DimensionScore],
        file_path: str = "",
        total_lines: int = 0,
        token_estimate: int = 0,
    ) -> QualityReport:
        """Build a report with auto-calculated overall score (average)."""
        overall = sum(d.score for d in dimensions) / len(dimensions) if dimensions else 0.0
        return cls(
            skill_name=skill_name,
            overall_score=overall,
            dimensions=dimensions,
            file_path=file_path,
            total_lines=total_lines,
            token_estimate=token_estimate,
        )
