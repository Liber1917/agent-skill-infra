"""Tests for quality scorecard data structures."""

from __future__ import annotations

import pytest

from skill_infra.quality_check.scorecard import DimensionScore, QualityReport


class TestDimensionScore:
    """Tests for DimensionScore."""

    def test_creation(self) -> None:
        ds = DimensionScore(
            name="trigger_precision",
            score=0.85,
            findings=["Good keyword coverage", "Consider adding more specific phrases"],
        )
        assert ds.name == "trigger_precision"
        assert ds.score == 0.85
        assert len(ds.findings) == 2

    def test_score_bounds(self) -> None:
        """Score should be 0.0-1.0."""
        ds_pass = DimensionScore(name="test", score=0.0, findings=[])
        ds_max = DimensionScore(name="test", score=1.0, findings=[])
        assert ds_pass.score == 0.0
        assert ds_max.score == 1.0

    def test_empty_findings(self) -> None:
        ds = DimensionScore(name="test", score=1.0, findings=[])
        assert ds.findings == []


class TestQualityReport:
    """Tests for QualityReport."""

    def test_creation(self) -> None:
        dims = [
            DimensionScore(name="d1", score=0.8, findings=["ok"]),
            DimensionScore(name="d2", score=0.6, findings=["needs work"]),
        ]
        report = QualityReport(
            skill_name="test-skill",
            overall_score=0.7,
            dimensions=dims,
            file_path="/path/to/SKILL.md",
            total_lines=100,
            token_estimate=400,
        )
        assert report.skill_name == "test-skill"
        assert report.overall_score == 0.7
        assert len(report.dimensions) == 2
        assert report.file_path == "/path/to/SKILL.md"

    def test_overall_score_average(self) -> None:
        """overall_score is the average of all dimension scores."""
        dims = [
            DimensionScore(name="d1", score=0.5, findings=[]),
            DimensionScore(name="d2", score=1.0, findings=[]),
            DimensionScore(name="d3", score=0.0, findings=[]),
        ]
        expected_avg = (0.5 + 1.0 + 0.0) / 3
        report = QualityReport(
            skill_name="test",
            overall_score=expected_avg,
            dimensions=dims,
            file_path="/test",
            total_lines=10,
            token_estimate=40,
        )
        assert report.overall_score == pytest.approx(0.5)

    def test_empty_dimensions(self) -> None:
        """Report with zero dimensions has overall_score of 0.0."""
        report = QualityReport(
            skill_name="empty",
            overall_score=0.0,
            dimensions=[],
            file_path="/empty",
            total_lines=0,
            token_estimate=0,
        )
        assert report.overall_score == 0.0
        assert report.dimensions == []

    def test_dimension_scores_all_present(self) -> None:
        """Standard 8-dimension report."""
        dims = [DimensionScore(name=f"dim_{i}", score=0.75, findings=[]) for i in range(8)]
        report = QualityReport(
            skill_name="full",
            overall_score=0.75,
            dimensions=dims,
            file_path="/full",
            total_lines=200,
            token_estimate=800,
        )
        assert len(report.dimensions) == 8
        assert all(d.score == 0.75 for d in report.dimensions)
