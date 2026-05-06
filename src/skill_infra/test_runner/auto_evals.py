"""Auto-generate evals.json test prompts using LLM.

Reads a ParsedSkill and uses LLM (GitHub Models, gpt-4o-mini, temperature=0.1)
to auto-generate test cases as evals.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from skill_infra.quality_check.parser import ParsedSkill

_ENDPOINT = "https://models.github.ai/inference/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a test case generator for AI Agent Skills. "
    "Given a skill definition, generate 3 realistic user prompts that test "
    "whether the agent correctly activates and responds according to the skill.\n\n"
    "Rules:\n"
    "1. Each prompt should be a realistic user message in Chinese that would "
    "trigger this skill.\n"
    "2. Each expected keyword list should contain 2-4 key Chinese "
    "words/phrases that MUST appear in the agent's response.\n"
    "3. Use judge_type \"keyword\" with mode \"any\" and threshold 0.5.\n"
    "4. Tag all cases with \"auto-generated\".\n\n"
    "Respond with JSON only, in this format:\n"
    '{\n'
    '  "cases": [\n'
    '    {\n'
    '      "id": "auto-001",\n'
    '      "prompt": "...",\n'
    '      "judge_type": "keyword",\n'
    '      "expected": {\n'
    '        "keywords": ["key1", "key2"],\n'
    '        "mode": "any",\n'
    '        "threshold": 0.5\n'
    '      },\n'
    '      "tags": ["auto-generated"]\n'
    '    }\n'
    '  ]\n'
    '}\n'
    'Do NOT include any text outside the JSON.'
)

_USER_TEMPLATE = (
    "## Skill Name\n{name}\n\n"
    "## Skill Description\n{description}\n\n"
    "## Skill Content\n{body}\n\n"
    "Generate 3 test prompts for this skill. Respond with JSON only."
)


class AutoEvalsGenerator:
    """Uses LLM to auto-generate evals.json test cases from a ParsedSkill.

    Uses GitHub Models free API (gpt-4o-mini). Requires GITHUB_TOKEN.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        github_token: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        self.model = model
        self._token = github_token or os.environ.get("GITHUB_TOKEN")
        self._temperature = temperature

    def is_available(self) -> bool:
        """Check if a GitHub token is available for API calls."""
        return bool(self._token)

    def generate(self, parsed: ParsedSkill, output_dir: Path) -> Path:
        """Generate evals.json in output_dir and return the output path.

        Args:
            parsed: Parsed skill data from SKILL.md.
            output_dir: Directory where evals.json will be written.

        Returns:
            Path to the generated evals.json file.

        Raises:
            RuntimeError: If no GITHUB_TOKEN is available or API call fails.
        """
        if not self._token:
            raise RuntimeError("No GITHUB_TOKEN available")

        user_message = self._build_user_message(parsed)
        response_text = self._call_api(user_message)

        skill_name = parsed.meta.name
        version = parsed.meta.version or "0.1.0"
        evals_data = self._parse_response(response_text, skill_name, version)

        # Validate cases
        cases = evals_data.get("cases", [])
        if not cases:
            raise RuntimeError("LLM returned no test cases")

        # Validate each case has required fields
        for case in cases:
            for field in ("id", "prompt", "expected", "judge_type"):
                if field not in case:
                    raise RuntimeError(f"LLM returned case missing field: {field}")

        output_path = output_dir / "evals.json"
        output_path.write_text(
            json.dumps(evals_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_message(parsed: ParsedSkill) -> str:
        desc = parsed.meta.description.strip() or parsed.meta.name
        body = parsed.raw_body[:8000]
        return _USER_TEMPLATE.format(name=parsed.meta.name, description=desc, body=body)

    def _call_api(self, user_message: str) -> str:
        import httpx

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
                    "temperature": self._temperature,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
            raise RuntimeError("Empty response from GitHub Models API")

    @staticmethod
    def _parse_response(response: str, skill_name: str, version: str) -> dict:
        """Parse LLM response into evals.json data structure."""
        text = response.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(f"API returned invalid JSON: {text[:200]}") from None

        cases: list[dict] = data.get("cases", [])
        for case in cases:
            case.setdefault("tags", [])

        return {"skill": skill_name, "version": version, "cases": cases}
