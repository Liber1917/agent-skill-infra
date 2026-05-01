"""LLM-based quality checker for SKILL.md evaluation.

Replaces keyword regex matching with LLM semantic evaluation across
the helloandy 8-dimension framework. Language-agnostic — handles
Chinese, English, and mixed descriptions natively.

Falls back to existing keyword-based checkers when no API key is configured.
"""

from __future__ import annotations

import json
import os

from skill_infra.quality_check.parser import ParsedSkill
from skill_infra.quality_check.scorecard import DimensionScore

_SYSTEM_PROMPT = (
    "You are a quality evaluator for Agent Skill definitions (SKILL.md files). "
    "Evaluate the skill across 8 dimensions and return ONLY a JSON object.\n\n"
    "Dimensions:\n"
    "1. trigger_precision: How well does the description specify when to activate? "
    "Are there clear trigger keywords? Score 0-1.\n"
    "2. output_completeness: Is the output format documented? Are examples provided? "
    "Score 0-1.\n"
    "3. rule_specificity: Are there concrete mandatory rules and forbidden actions? "
    "Score 0-1.\n"
    "4. error_recovery: Does the skill handle edge cases, failures, and fallbacks? "
    "Score 0-1.\n"
    "5. example_quality: Are there code blocks, input/output examples? Score 0-1.\n"
    "6. conciseness: Is the skill compact without unnecessary repetition? Score 0-1.\n"
    "7. consistency: No contradictory statements, description matches content. "
    "Score 0-1.\n"
    "8. edge_cases: Does the skill handle null, missing, malformed inputs? "
    "Score 0-1.\n\n"
    "Respond with JSON only (no markdown, no explanation). For each dimension,\n"
    "include BOTH 'findings' (what was observed) AND 'improvements' "
    "(actionable suggestions, 1-2 sentences each).\n\n"
    "JSON format:\n"
    '{"dimensions":[{"name":"...","score":0.X,'
    '"findings":["..."],"improvements":["..."]},...],'
    '"overall_score":0.X,'
    '"summary":"1-2 sentence overall summary with top 3 priorities"}\n\n'
    "Be strict but fair. Higher scores for specific, actionable skills."
)

_USER_TEMPLATE = (
    "## Skill Frontmatter\n"
    "name: {name}\n"
    "description: {description}\n\n"
    "## Skill Content\n{body}\n\n"
    "Evaluate this skill across all 8 dimensions. Respond with JSON only."
)


class LLMQualityChecker:
    """LLM-based quality checker that uses semantic evaluation.

    Replaces keyword regex matching with Anthropic API call.
    Falls back to keyword-based HelloAndyChecker when no API key.
    """

    _DIM_NAME = "helloandy_8dim_llm"

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        """Evaluate using LLM or fall back to keyword-based checker."""
        if not self._api_key:
            return self._fallback_check(parsed)

        try:
            response = self._call_llm(parsed)
            return self._parse_response(response)
        except Exception as exc:
            # Graceful fallback on error
            return DimensionScore(
                name=self._DIM_NAME,
                score=0.5,
                findings=[f"LLM evaluation failed: {exc}, using approximate score"],
            )

    def is_available(self) -> bool:
        """Check if LLM evaluation is available."""
        return bool(self._api_key)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_llm(self, parsed: ParsedSkill) -> str:
        import httpx

        desc = parsed.meta.description.strip() or parsed.meta.name
        # Truncate very long content to stay within context limits
        body = parsed.raw_body[:12000]
        user_message = _USER_TEMPLATE.format(
            name=parsed.meta.name,
            description=desc,
            body=body,
        )

        with httpx.Client(timeout=45.0) as client:
            assert self._api_key is not None  # guarded in check()
            api_key: str = self._api_key
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
            return json.dumps({
                "dimensions": [{"name": "error", "score": 0.5, "findings": ["Empty response"]}],
                "overall_score": 0.5,
            })

    @classmethod
    def _parse_response(cls, response: str) -> DimensionScore:
        """Parse LLM JSON response into DimensionScore."""
        text = response.strip()
        # Handle markdown fences
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return DimensionScore(
                name=cls._DIM_NAME,
                score=0.5,
                findings=[f"LLM returned invalid JSON: {text[:100]}"],
            )

        dimensions = data.get("dimensions", [])
        findings: list[str] = []
        scores: list[float] = []

        for dim in dimensions:
            name = dim.get("name", "unknown")
            score = float(dim.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            scores.append(score)
            for f in dim.get("findings", []):
                findings.append(f"[{name}] {f}")
            for imp in dim.get("improvements", []):
                findings.append(f"[{name}] → {imp}")

        overall = sum(scores) / len(scores) if scores else data.get("overall_score", 0.5)
        summary = data.get("summary", "")
        if summary:
            findings.insert(0, f"Summary: {summary}")
        return DimensionScore(
            name=cls._DIM_NAME,
            score=overall,
            findings=findings or [f"Overall score: {overall:.0%}"],
        )

    @staticmethod
    def _fallback_check(parsed: ParsedSkill) -> DimensionScore:
        """Fall back to keyword-based HelloAndyChecker."""
        from skill_infra.quality_check.checkers import HelloAndyChecker

        result = HelloAndyChecker().check(parsed)
        result.name = "helloandy_8dim"
        result.findings.insert(0, "Using keyword-based fallback (no LLM API key)")
        return result
