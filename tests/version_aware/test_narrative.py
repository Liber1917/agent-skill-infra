"""Tests for ChangeNarrator and CLI --narrative integration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from skill_infra.version_aware.narrative import ChangeNarrative, ChangeNarrator, DimensionNarrative

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill_repo(repo: Path) -> tuple[str, str]:
    """Create a git repo with two commits on SKILL.md, return (sha1, sha2)."""
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )

    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\nversion: 1.0.0\n---\n\n"
        "## Usage\nThis skill helps with testing.\n\n## Examples\nNone yet.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "v1"], cwd=repo, capture_output=True, check=True)
    sha1 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    (repo / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A much improved test skill\nversion: 2.0.0\n---\n\n"
        "## Overview\nThis skill helps with testing and debugging.\n\n"
        "## Usage\nRun `test-skill run`.\n\n"
        "## Examples\n- Example 1: basic test\n- Example 2: edge case\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "v2"], cwd=repo, capture_output=True, check=True)
    sha2 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return sha1, sha2


def _get_diff_text(repo: Path, sha1: str, sha2: str) -> str:
    """Get unified diff text between two refs."""
    result = subprocess.run(
        ["git", "diff", sha1, sha2],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Data class tests
# ---------------------------------------------------------------------------


class TestDimensionNarrative:
    """Tests for DimensionNarrative data class."""

    def test_defaults(self) -> None:
        dn = DimensionNarrative(dimension="trigger_precision")
        assert dn.dimension == "trigger_precision"
        assert dn.before_score is None
        assert dn.after_score is None
        assert dn.delta is None
        assert dn.analysis == ""

    def test_with_scores(self) -> None:
        dn = DimensionNarrative(
            dimension="conciseness",
            before_score=0.6,
            after_score=0.8,
            delta=0.2,
            analysis="Score increased due to reduced filler content.",
        )
        assert dn.before_score == 0.6
        assert dn.after_score == 0.8
        assert dn.delta == 0.2
        assert "reduced filler" in dn.analysis


class TestChangeNarrative:
    """Tests for ChangeNarrative data class."""

    def test_defaults(self) -> None:
        cn = ChangeNarrative()
        assert cn.summary == ""
        assert cn.affected_sections == []
        assert cn.dimension_analysis == []
        assert cn.raw_response == ""

    def test_full_narrative(self) -> None:
        cn = ChangeNarrative(
            summary="Improved description and added examples.",
            affected_sections=["description", "examples"],
            dimension_analysis=[
                DimensionNarrative(
                    dimension="example_quality",
                    before_score=0.3,
                    after_score=0.8,
                    delta=0.5,
                    analysis="Added concrete examples.",
                ),
            ],
        )
        assert len(cn.affected_sections) == 2
        assert len(cn.dimension_analysis) == 1
        assert cn.dimension_analysis[0].delta == 0.5


# ---------------------------------------------------------------------------
# ChangeNarrator unit tests (keyword fallback — no LLM required)
# ---------------------------------------------------------------------------


class TestChangeNarratorFallback:
    """Tests for the keyword-based fallback path (no GITHUB_TOKEN needed)."""

    @pytest.fixture(autouse=True)
    def _unset_github_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def test_empty_diff(self) -> None:
        narrator = ChangeNarrator()
        result = narrator.narrate("")
        assert "No changes" in result.summary
        assert result.affected_sections == []

    def test_empty_diff_is_not_available(self) -> None:
        narrator = ChangeNarrator()
        assert not narrator.is_available()

    def test_simple_diff_fallback(self) -> None:
        narrator = ChangeNarrator()
        diff = (
            "diff --git a/SKILL.md b/SKILL.md\n"
            "--- a/SKILL.md\n"
            "+++ b/SKILL.md\n"
            "@@ -1,5 +1,8 @@\n"
            " # Old Title\n"
            "-# Old description\n"
            "+# New Title\n"
            "+New description line 1\n"
            "+New description line 2\n"
        )
        result = narrator.narrate(diff)
        assert "addition" in result.summary.lower() or "deletion" in result.summary.lower()

    def test_diff_with_scores_fallback(self) -> None:
        narrator = ChangeNarrator()
        diff = (
            "diff --git a/SKILL.md b/SKILL.md\n"
            "--- a/SKILL.md\n"
            "+++ b/SKILL.md\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        before = {"trigger_precision": 0.5, "conciseness": 0.6}
        after = {"trigger_precision": 0.7, "conciseness": 0.6}

        result = narrator.narrate(diff, before_scores=before, after_scores=after)
        # Should have dimension analysis from delta fallback
        assert len(result.dimension_analysis) == 2
        triggers = [d for d in result.dimension_analysis if d.dimension == "trigger_precision"]
        assert len(triggers) == 1
        assert triggers[0].delta == 0.2

        conciseness = [d for d in result.dimension_analysis if d.dimension == "conciseness"]
        assert len(conciseness) == 1
        assert conciseness[0].delta == 0.0

    def test_fallback_detects_affected_sections(self) -> None:
        narrator = ChangeNarrator()
        diff = (
            "diff --git a/SKILL.md b/SKILL.md\n"
            "--- a/SKILL.md\n"
            "+++ b/SKILL.md\n"
            "@@ -1,3 +1,3 @@ Updated description section @@\n"
            " old\n"
            "-removed\n"
            "+added\n"
        )
        result = narrator.narrate(diff)
        assert len(result.affected_sections) > 0


# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------


class TestNarratorParseResponse:
    """Test JSON response parsing independently (no API needed)."""

    def test_parse_valid_json(self) -> None:
        response = json.dumps(
            {
                "summary": "Added 3 examples and improved descriptions.",
                "affected_sections": ["frontmatter", "examples", "usage"],
                "dimension_analysis": [
                    {
                        "dimension": "example_quality",
                        "before_score": 0.4,
                        "after_score": 0.9,
                        "delta": 0.5,
                        "analysis": "New examples are concrete and well-documented.",
                    },
                    {
                        "dimension": "output_completeness",
                        "before_score": 0.5,
                        "after_score": 0.7,
                        "delta": 0.2,
                        "analysis": "Added input/output pairs.",
                    },
                ],
            }
        )
        result = ChangeNarrator._parse_response(response)
        assert "3 examples" in result.summary
        assert len(result.affected_sections) == 3
        assert "frontmatter" in result.affected_sections
        assert len(result.dimension_analysis) == 2
        assert result.dimension_analysis[0].dimension == "example_quality"
        assert result.dimension_analysis[0].delta == 0.5
        assert result.dimension_analysis[0].before_score == 0.4

    def test_parse_json_with_code_fence(self) -> None:
        response = (
            "```json\n"
            + json.dumps(
                {
                    "summary": "Minor wording fix.",
                    "affected_sections": ["usage"],
                    "dimension_analysis": [],
                }
            )
            + "\n```"
        )
        result = ChangeNarrator._parse_response(response)
        assert result.summary == "Minor wording fix."
        assert result.affected_sections == ["usage"]

    def test_parse_invalid_json(self) -> None:
        result = ChangeNarrator._parse_response("this is not json at all")
        assert "unparseable" in result.summary.lower()
        assert result.raw_response == "this is not json at all"

    def test_parse_missing_dimension_scores(self) -> None:
        response = json.dumps(
            {
                "summary": "No scores provided.",
                "affected_sections": ["overview"],
                "dimension_analysis": [
                    {
                        "dimension": "trigger_precision",
                        "analysis": "unchanged",
                    },
                ],
            }
        )
        result = ChangeNarrator._parse_response(response)
        assert len(result.dimension_analysis) == 1
        assert result.dimension_analysis[0].before_score is None
        assert result.dimension_analysis[0].delta is None


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCLINarrative:
    """CLI integration tests for --narrative flag."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        self.sha1, self.sha2 = _make_skill_repo(self.repo)

    def test_diff_with_narrative_json(self) -> None:
        """--narrative with --output json should include narrative field."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "diff",
                str(self.repo),
                "--old-ref",
                self.sha1,
                "--new-ref",
                self.sha2,
                "--output",
                "json",
                "--narrative",
            ],
        )
        assert result.exit_code == 0
        # Use stdout for clean JSON (stderr may contain fallback warnings)
        data = json.loads(result.stdout)
        assert "narrative" in data
        assert "summary" in data["narrative"]
        assert "affected_sections" in data["narrative"]
        # Fallback should mention "addition" or "deletion"
        assert data["narrative"]["summary"]

    def test_diff_with_narrative_table(self) -> None:
        """--narrative should add narrative section to table output."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "diff",
                str(self.repo),
                "--old-ref",
                self.sha1,
                "--new-ref",
                self.sha2,
                "--narrative",
            ],
        )
        assert result.exit_code == 0
        assert "Change Narrative" in result.output
        assert "Summary:" in result.output

    def test_diff_without_narrative(self) -> None:
        """Without --narrative, output should NOT contain narrative section."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "diff",
                str(self.repo),
                "--old-ref",
                self.sha1,
                "--new-ref",
                self.sha2,
            ],
        )
        assert result.exit_code == 0
        assert "Change Narrative" not in result.output

    def test_narrative_on_empty_diff(self) -> None:
        """Narrative on empty diff should produce a meaningful message."""
        from typer.testing import CliRunner

        from skill_infra.version_aware.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "diff",
                str(self.repo),
                "--old-ref",
                self.sha1,
                "--new-ref",
                self.sha1,
                "--narrative",
            ],
        )
        assert result.exit_code == 0
        assert "0 files" in result.output.lower()


# ---------------------------------------------------------------------------
# Integration with parse_version_diff
# ---------------------------------------------------------------------------


class TestNarratorWithVersionDiff:
    """Test ChangeNarrator fed with real VersionDiff patches."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        self.sha1, self.sha2 = _make_skill_repo(self.repo)

    def test_narrate_from_version_diff(self) -> None:
        from skill_infra.version_aware.git_diff import parse_version_diff

        vd = parse_version_diff(str(self.repo), self.sha1, self.sha2)
        diff_text = "\n".join(f.patch for f in vd.files if f.patch)

        narrator = ChangeNarrator()
        result = narrator.narrate(diff_text)
        assert result.summary
        # The fallback should detect changes
        assert "addition" in result.summary.lower() or "deletion" in result.summary.lower()

    def test_narrate_with_scores(self) -> None:
        from skill_infra.version_aware.git_diff import parse_version_diff

        vd = parse_version_diff(str(self.repo), self.sha1, self.sha2)
        diff_text = "\n".join(f.patch for f in vd.files if f.patch)

        before = {
            "trigger_precision": 0.4,
            "example_quality": 0.3,
            "conciseness": 0.7,
        }
        after = {
            "trigger_precision": 0.6,
            "example_quality": 0.8,
            "conciseness": 0.7,
        }

        narrator = ChangeNarrator()
        result = narrator.narrate(diff_text, before_scores=before, after_scores=after)
        assert len(result.dimension_analysis) == 3
        # example_quality should have positive delta
        eq = [d for d in result.dimension_analysis if d.dimension == "example_quality"]
        assert len(eq) == 1
        assert eq[0].delta == 0.5
        # conciseness unchanged
        conc = [d for d in result.dimension_analysis if d.dimension == "conciseness"]
        assert len(conc) == 1
        assert conc[0].delta == 0.0
