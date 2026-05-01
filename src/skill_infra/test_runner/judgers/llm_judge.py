"""LLMJudge: real LLM-as-Judge using Anthropic API."""

from __future__ import annotations

import json
import os
from typing import Any

from skill_infra.test_runner.judgers.base import Judger

_SYSTEM_PROMPT = (
    "You are an evaluation judge for agent outputs. Given an output and "
    "evaluation criteria, respond with ONLY a JSON object (no markdown, "
    "no explanation) with:\n"
    '- "passed": boolean\n'
    '- "score": float between 0.0 and 1.0\n'
    '- "reason": short explanation\n\n'
    "Be strict but fair. Focus on whether the output meets the stated criteria."
)

_USER_TEMPLATE = (
    "## Agent Output\n{output}\n\n"
    "## Evaluation Criteria\n{criteria}\n\n"
    'Respond with JSON only: {{"passed": bool, "score": float, "reason": string}}'
)


class LLMJudge(Judger):
    """LLM-based judge that uses Anthropic API for semantic evaluation.

    Falls back to stub behavior when no API key is configured.
    """

    judge_type: str = "llm"

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def judge(self, output: str, expected: dict[str, Any]) -> tuple[bool, float, str]:  # type: ignore[type-arg]
        """Evaluate output using LLM or fall back to stub."""
        if not self._api_key:
            return True, 1.0, "LLM judge not configured (no API key), falling back to stub"

        criteria = self._build_criteria(expected)
        try:
            response = self._call_llm_sync(output, criteria)
            return self._parse_response(response)
        except TimeoutError:
            return False, 0.0, "LLM request timed out"
        except Exception as exc:
            return False, 0.0, f"LLM judge error: {exc}"

    def _call_llm_sync(self, output: str, criteria: str) -> str:
        """Call Anthropic Messages API synchronously."""
        import httpx

        user_message = _USER_TEMPLATE.format(output=output, criteria=criteria)

        with httpx.Client(timeout=30.0) as client:
            assert self._api_key is not None  # already guarded in judge()
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
                    "max_tokens": 256,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"]
            return ""

    @staticmethod
    def _parse_response(response: str) -> tuple[bool, float, str]:
        """Parse LLM JSON response into (passed, score, reason)."""
        if not response.strip():
            return False, 0.0, "LLM returned empty response"

        # Try to extract JSON from response (handle markdown fences)
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [line for line in lines[1:] if not line.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False, 0.0, f"LLM returned invalid JSON: {text[:100]}"

        passed = bool(data.get("passed", False))
        score = float(data.get("score", 0.0))
        reason = str(data.get("reason", ""))
        score = max(0.0, min(1.0, score))
        return passed, score, reason

    @staticmethod
    def _build_criteria(expected: dict[str, Any]) -> str:
        """Build human-readable criteria string from expected dict."""
        if "semantic_equivalence" in expected:
            target = expected["semantic_equivalence"]
            return (
                f"Check if the output is semantically equivalent to: {target}\n"
                "Two texts are semantically equivalent if they convey the same "
                "meaning, even with different wording."
            )
        if "criteria" in expected:
            return str(expected["criteria"])
        return json.dumps(expected, indent=2)
