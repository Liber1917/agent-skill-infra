"""LLM-powered change narrative builder for skill version diffs.

Generates human-readable explanations of WHAT changed between two git refs
and WHY quality scores might shift, using the GitHub Models API (gpt-4o-mini).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

_ENDPOINT = "https://models.github.ai/inference/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a change analyst for Agent Skill definitions (SKILL.md files). "
    "Given a git diff and optional quality scores (before/after), produce a "
    "concise, structured change narrative. Be factual — do not invent changes "
    "that are not in the diff.\n\n"
    "Respond with JSON only. Format:\n"
    '{"summary":"2-3 sentence summary of the diff",'
    '"affected_sections":["section1","section2",...],'
    '"dimension_analysis":['
    '  {"dimension":"name","before_score":0.X,"after_score":0.X,"delta":+/-0.X,'
    '   "analysis":"why this dimension likely changed (or "unchanged")"}'
    "]}"
)

_USER_TEMPLATE = (
    "## Git Diff (old → new)\n{diff_text}\n\n"
    "## Quality Scores\n"
    "Before: {before_scores}\n"
    "After: {after_scores}\n\n"
    "Analyze the diff and score changes. Identify which sections of SKILL.md "
    "were affected and explain which changes likely caused score shifts. "
    "Respond with JSON only."
)

_USER_TEMPLATE_NO_SCORES = (
    "## Git Diff (old → new)\n{diff_text}\n\n"
    "Analyze the diff. Identify which sections of SKILL.md were affected. "
    "Respond with JSON only (dimension_analysis may be empty)."
)


@dataclass
class DimensionNarrative:
    """Narrative for a single quality dimension."""

    dimension: str
    before_score: float | None = None
    after_score: float | None = None
    delta: float | None = None
    analysis: str = ""


@dataclass
class ChangeNarrative:
    """LLM-generated change narrative for a skill version diff."""

    summary: str = ""
    affected_sections: list[str] = field(default_factory=list)
    dimension_analysis: list[DimensionNarrative] = field(default_factory=list)
    raw_response: str = ""


class ChangeNarrator:
    """Generates human-readable change narratives via GitHub Models API.

    Uses gpt-4o-mini with temperature=0.1 for consistent, factual output.
    Falls back to a basic keyword-based narrative when the API is unavailable.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        github_token: str | None = None,
    ) -> None:
        self.model = model
        self._token = github_token or os.environ.get("GITHUB_TOKEN")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def narrate(
        self,
        diff_text: str,
        before_scores: dict[str, float] | None = None,
        after_scores: dict[str, float] | None = None,
    ) -> ChangeNarrative:
        """Generate a change narrative from a git diff and optional quality scores.

        Args:
            diff_text: Unified diff text (git diff old..new).
            before_scores: Optional quality dimension scores BEFORE the change.
            after_scores: Optional quality dimension scores AFTER the change.

        Returns:
            ChangeNarrative with summary, affected sections, and dimension analysis.
        """
        if not diff_text.strip():
            return ChangeNarrative(
                summary="No changes detected (empty diff).",
            )

        if not self._token:
            return self._fallback_narrate(diff_text, before_scores, after_scores)

        try:
            response = self._call_api(diff_text, before_scores, after_scores)
            return self._parse_response(response, before_scores, after_scores)
        except Exception:
            return self._fallback_narrate(diff_text, before_scores, after_scores)

    def is_available(self) -> bool:
        """Check whether the GitHub Models API is available."""
        return bool(self._token)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(
        self,
        diff_text: str,
        before_scores: dict[str, float] | None,
        after_scores: dict[str, float] | None,
    ) -> str:
        import httpx

        # Truncate diff if excessively large (gpt-4o-mini context is generous).
        diff = diff_text[:16000]

        if before_scores and after_scores:
            before_fmt = ", ".join(f"{k}={v:.2f}" for k, v in before_scores.items())
            after_fmt = ", ".join(f"{k}={v:.2f}" for k, v in after_scores.items())
            user_message = _USER_TEMPLATE.format(
                diff_text=diff,
                before_scores=before_fmt,
                after_scores=after_fmt,
            )
        else:
            user_message = _USER_TEMPLATE_NO_SCORES.format(diff_text=diff)

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
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
            return json.dumps(
                {
                    "summary": "API returned empty response.",
                    "affected_sections": [],
                    "dimension_analysis": [],
                }
            )

    @staticmethod
    def _parse_response(
        response: str,
        before_scores: dict[str, float] | None = None,
        after_scores: dict[str, float] | None = None,
    ) -> ChangeNarrative:
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ChangeNarrative(
                summary=f"LLM returned unparseable response: {text[:200]}",
                raw_response=response,
            )

        dimensions: list[DimensionNarrative] = []
        for dim in data.get("dimension_analysis", []):
            dim_name = dim.get("dimension", "unknown")
            before = dim.get("before_score")
            after = dim.get("after_score")
            delta = dim.get("delta")
            analysis = dim.get("analysis", "")

            dimensions.append(
                DimensionNarrative(
                    dimension=dim_name,
                    before_score=float(before) if before is not None else None,
                    after_score=float(after) if after is not None else None,
                    delta=float(delta) if delta is not None else None,
                    analysis=analysis,
                )
            )

        return ChangeNarrative(
            summary=data.get("summary", ""),
            affected_sections=data.get("affected_sections", []),
            dimension_analysis=dimensions,
            raw_response=response,
        )

    @staticmethod
    def _fallback_narrate(
        diff_text: str,
        before_scores: dict[str, float] | None = None,
        after_scores: dict[str, float] | None = None,
    ) -> ChangeNarrative:
        """Keyword-based fallback when LLM is unavailable."""
        lines = diff_text.splitlines()
        sections: list[str] = []

        # Detect affected sections from @@ headers in unified diff
        for line in lines:
            if line.startswith("@@ ") and "SKILL.md" in diff_text[:200]:
                # Extract function/section context from the hunk header
                # Format: @@ -l,s +l,s @@ context
                rest = line.split("@@", 2)[-1].strip()
                if rest:
                    sections.append(rest)

        # Count meaningful changes
        add_count = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
        del_count = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
        changed_files: list[str] = []
        for ln in lines:
            if ln.startswith("diff --git"):
                changed_files.append(ln.split()[-1].lstrip("b/"))

        if not add_count and not del_count:
            summary = "No meaningful changes detected."
        else:
            summary = (
                f"Found {add_count} addition(s) and {del_count} deletion(s) "
                f"across {len(changed_files) or 0} file(s)."
            )

        # Dimension analysis from score deltas (keyword-free)
        dimension_analysis: list[DimensionNarrative] = []
        if before_scores and after_scores:
            for dim_name in before_scores:
                before = before_scores.get(dim_name, 0.0)
                after = after_scores.get(dim_name, before)
                delta = round(after - before, 4)  # avoid float precision noise
                direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
                analysis = f"Score {direction} by {abs(delta):.2f}."
                dimension_analysis.append(
                    DimensionNarrative(
                        dimension=dim_name,
                        before_score=before,
                        after_score=after,
                        delta=delta,
                        analysis=analysis,
                    )
                )

        return ChangeNarrative(
            summary=summary,
            affected_sections=sections if sections else changed_files,
            dimension_analysis=dimension_analysis,
        )
