"""Auto-fix suggestion engine for SKILL.md quality improvements.

Uses GitHub Models API (gpt-4o-mini) to generate actionable rewrite suggestions
for the lowest-scoring quality dimensions. Can optionally apply suggestions
in-place with automatic backup.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skill_infra.quality_check.parser import ParsedSkill
from skill_infra.quality_check.scorecard import QualityReport

_ENDPOINT = "https://models.github.ai/inference/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class SuggestResult:
    """A single improvement suggestion for one dimension."""

    dimension: str
    score: float
    suggestion: str
    replace: str = ""
    replace_with: str = ""
    applied: bool = False
    error: str = ""


@dataclass
class AutoFixResult:
    """Result of running auto-fix suggestion generation."""

    skill_name: str
    suggestions: list[SuggestResult] = field(default_factory=list)
    backup_path: str = ""
    apply_error: str = ""

    @property
    def applied_count(self) -> int:
        return sum(1 for s in self.suggestions if s.applied)

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.suggestions if s.error and not s.applied)


def _build_suggest_prompt(report: QualityReport, parsed: ParsedSkill) -> str:
    """Build a system prompt asking the LLM to generate rewrite suggestions."""
    dim_lines = "\n".join(
        f"  - {d.name}: score={d.score}, findings={d.findings}" for d in report.dimensions
    )

    return (
        "You are an expert skill editor improving SKILL.md files for AI agents. "
        "Given the quality assessment report below, generate specific, actionable "
        "rewrite suggestions for the LOWEST-SCORING dimensions.\n\n"
        "CRITICAL RULES:\n"
        "1. Focus on dimensions with the lowest scores (especially below 0.5).\n"
        "2. Each suggestion MUST include EXACT text from the file in `replace` "
        "and the improved version in `replace_with`. The text must be an exact "
        "character-for-character match of what will be replaced.\n"
        "3. Prefer simple, targeted text substitutions (e.g., replace a single "
        "bad description, add a sentence, fix a section title, rewrite a trigger).\n"
        "4. Only suggest changes for 2-3 lowest-scoring dimensions maximum.\n"
        "5. Do NOT suggest changes for dimensions already scoring >= 0.7.\n\n"
        "Respond with a JSON array only. Each element:\n"
        '{"dimension":"dimension_name","score":0.X,'
        '"suggestion":"1-2 sentence explanation of the change",'
        '"replace":"exact text to find in the file",'
        '"replace_with":"exact replacement text"}\n\n'
        f"Quality report for: {report.skill_name}\n"
        f"Overall score: {report.overall_score:.2f}\n\n"
        "Dimension scores:\n"
        f"{dim_lines}\n\n"
        "## Skill Content\n"
        f"{parsed.raw_body[:6000]}"
    )


class AutoFixSuggester:
    """Generates and optionally applies quality improvement suggestions.

    Uses GitHub Models API (gpt-4o-mini) to analyze the quality report and
    skill content, producing specific text replacement suggestions for the
    lowest-scoring quality dimensions.

    Args:
        model: Model name to use (default: gpt-4o-mini).
        github_token: GitHub token for API auth. Falls back to GITHUB_TOKEN env.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        github_token: str | None = None,
    ) -> None:
        self.model = model
        self._token = github_token or os.environ.get("GITHUB_TOKEN")

    def is_available(self) -> bool:
        """Check if the GitHub Models API token is configured."""
        return bool(self._token)

    def suggest(
        self,
        report: QualityReport,
        parsed: ParsedSkill,
        apply: bool = False,
        file_path: str = "",
    ) -> AutoFixResult:
        """Generate improvement suggestions for a quality report.

        Args:
            report: Quality report with dimension scores.
            parsed: Parsed skill content.
            apply: If True, apply suggestions in-place with backup.
            file_path: Path to the SKILL.md file (required if apply=True).

        Returns:
            AutoFixResult with suggestions and apply status.
        """
        if not self._token:
            return AutoFixResult(
                skill_name=report.skill_name,
                suggestions=[],
                apply_error="No GITHUB_TOKEN available",
            )

        try:
            response = self._call_api(report, parsed)
            suggestions = self._parse_response(response)
        except Exception as exc:
            return AutoFixResult(
                skill_name=report.skill_name,
                suggestions=[],
                apply_error=f"API error: {exc}",
            )

        result = AutoFixResult(
            skill_name=report.skill_name,
            suggestions=suggestions,
        )

        if apply and suggestions and file_path:
            self._apply_suggestions(result, Path(file_path))

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(self, report: QualityReport, parsed: ParsedSkill) -> str:
        """Call GitHub Models API for fix suggestions."""
        import httpx

        prompt = _build_suggest_prompt(report, parsed)

        with httpx.Client(timeout=45.0) as client:
            assert self._token is not None
            resp = client.post(
                _ENDPOINT,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self._token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a SKILL.md quality editor. Respond with JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
            return "[]"

    @classmethod
    def _parse_response(cls, response: str) -> list[SuggestResult]:
        """Parse LLM response into a list of SuggestResult.

        Handles markdown code fences and JSON parsing.
        """
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data: list[dict[str, Any]] = json.loads(text)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        results: list[SuggestResult] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            dim = item.get("dimension", "")
            score = max(0.0, min(1.0, float(item.get("score", 0.5))))
            suggestion = item.get("suggestion", "")
            replace = item.get("replace", "")
            replace_with = item.get("replace_with", "")

            if dim and suggestion and replace and replace_with:
                results.append(
                    SuggestResult(
                        dimension=dim,
                        score=score,
                        suggestion=suggestion,
                        replace=replace,
                        replace_with=replace_with,
                    )
                )

        return results

    @classmethod
    def _apply_suggestions(
        cls,
        result: AutoFixResult,
        file_path: Path,
    ) -> None:
        """Apply suggestions in-place, creating a .backup copy first."""
        if not file_path.exists():
            result.apply_error = f"File not found: {file_path}"
            return

        # Create backup
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        shutil.copy2(str(file_path), str(backup_path))
        result.backup_path = str(backup_path)

        content = file_path.read_text(encoding="utf-8")
        new_content = content

        for suggestion in result.suggestions:
            if suggestion.replace in new_content:
                new_content = new_content.replace(suggestion.replace, suggestion.replace_with, 1)
                suggestion.applied = True
            else:
                suggestion.error = "Replace text not found in file"

        # Write updated content
        try:
            file_path.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            result.apply_error = f"Failed to write file: {exc}"
            # Restore from backup
            shutil.copy2(str(backup_path), str(file_path))
