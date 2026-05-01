"""GitHub Models API client for SKILL.md quality evaluation.

Uses the free GitHub Models API (gpt-4o-mini) — no API key needed in Actions.
Endpoint: https://models.github.ai/inference/chat/completions
Auth: Bearer GITHUB_TOKEN (automatically available in GitHub Actions)
"""

from __future__ import annotations

import json
import os

from skill_infra.quality_check.parser import ParsedSkill
from skill_infra.quality_check.scorecard import DimensionScore

_ENDPOINT = "https://models.github.ai/inference/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"

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
    '"summary":"1-2 sentence overall summary with top 3 priorities"}'
)

_USER_TEMPLATE = (
    "## Skill Frontmatter\n"
    "name: {name}\n"
    "description: {description}\n\n"
    "## Skill Content\n{body}\n\n"
    "Evaluate this skill across all 8 dimensions. Respond with JSON only."
)


class GitHubModelQualityChecker:
    """Quality checker using GitHub Models free API.

    Uses gpt-4o-mini via GitHub Models endpoint.
    Zero API key needed in GitHub Actions — uses GITHUB_TOKEN.
    Falls back to keyword-based checker when token unavailable.
    """

    _DIM_NAME = "helloandy_8dim_gh_models"

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        github_token: str | None = None,
    ) -> None:
        self.model = model
        self._token = github_token or os.environ.get("GITHUB_TOKEN")

    def check(self, parsed: ParsedSkill) -> DimensionScore:
        """Evaluate using GitHub Models or fall back to keyword-based."""
        if not self._token:
            return self._fallback_check(parsed, "No GITHUB_TOKEN")

        try:
            response = self._call_api(parsed)
            return self._parse_response(response)
        except Exception as exc:
            return self._fallback_check(
                parsed, f"GitHub Models API error: {exc}"
            )

    def is_available(self) -> bool:
        return bool(self._token)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(self, parsed: ParsedSkill) -> str:
        import httpx

        desc = parsed.meta.description.strip() or parsed.meta.name
        body = parsed.raw_body[:8000]  # gpt-4o-mini has large context
        user_message = _USER_TEMPLATE.format(
            name=parsed.meta.name, description=desc, body=body,
        )

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
                    "temperature": 0.3,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
            return json.dumps({
                "dimensions": [{"name": "error", "score": 0.5,
                                "findings": ["Empty response from API"]}],
                "overall_score": 0.5,
            })

    @classmethod
    def _parse_response(cls, response: str) -> DimensionScore:
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return DimensionScore(
                name=cls._DIM_NAME, score=0.5,
                findings=[f"API returned invalid JSON: {text[:100]}"],
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
            name=cls._DIM_NAME, score=overall,
            findings=findings or [f"Overall: {overall:.0%}"],
        )

    @staticmethod
    def _fallback_check(parsed: ParsedSkill, reason: str = "") -> DimensionScore:
        from skill_infra.quality_check.checkers import HelloAndyChecker

        result = HelloAndyChecker().check(parsed)
        result.name = "helloandy_8dim"
        prefix = f"Using keyword-based fallback ({reason})"
        result.findings.insert(0, prefix)
        return result
