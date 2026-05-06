"""Capability discovery for agent skills.

Uses GitHub Models API (gpt-4o-mini) to analyze a parsed skill
and identify its current capabilities and potential expansion areas.

Endpoint: https://models.github.ai/inference/chat/completions
Auth: Bearer GITHUB_TOKEN (automatically available in GitHub Actions)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from skill_infra.quality_check.parser import ParsedSkill

_ENDPOINT = "https://models.github.ai/inference/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class Capability:
    """A single capability identified for a skill.

    Attributes:
        name: Short label for the capability (e.g. "sentiment_analysis").
        description: Human-readable explanation of what this capability does.
        is_current: True if the capability is already handled by the skill.
                     False if it is a potential expansion area.
        confidence: 0.0 - 1.0 how confident the model is in this capability.
        evidence: Specific text snippets from SKILL.md that support this capability.
        expansion_suggestion: How to implement or improve this capability.
    """

    name: str
    description: str
    is_current: bool
    confidence: float
    evidence: list[str] = field(default_factory=list)
    expansion_suggestion: str = ""


@dataclass
class CapabilityReport:
    """Result of a capability discovery analysis."""

    capabilities: list[Capability] = field(default_factory=list)
    skill_name: str = ""
    summary: str = ""
    total_current: int = 0
    total_potential: int = 0

    @classmethod
    def from_api_response(cls, data: dict, skill_name: str = "") -> CapabilityReport:
        """Build report from parsed API JSON response."""
        cap_list: list[Capability] = []
        for item in data.get("capabilities", data.get("dimensions", [])):
            cap = Capability(
                name=item.get("name", "unknown"),
                description=item.get("description", ""),
                is_current=bool(item.get("is_current", True)),
                confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                evidence=item.get("evidence", []),
                expansion_suggestion=item.get("expansion_suggestion", ""),
            )
            cap_list.append(cap)

        total_current = sum(1 for c in cap_list if c.is_current)
        total_potential = sum(1 for c in cap_list if not c.is_current)

        return cls(
            capabilities=cap_list,
            skill_name=skill_name,
            summary=data.get("summary", ""),
            total_current=total_current,
            total_potential=total_potential,
        )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a capability analyst for Agent Skill definitions (SKILL.md files). "
    "Your job is to identify what capabilities a skill CURRENTLY handles "
    "and what POTENTIAL capabilities could be added based on existing patterns.\n\n"
    "Analyze the skill carefully:\n"
    "1. Identify CURRENT capabilities — things the skill explicitly handles.\n"
    "2. Identify POTENTIAL capabilities — things the skill could plausibly handle "
    "based on descriptions, existing patterns, or domain adjacency.\n\n"
    "Be comprehensive but realistic. Consider:\n"
    "- The skill's name and description\n"
    "- Its triggers and when statements\n"
    "- Available tools and allowed-tools\n"
    "- Code examples and workflow patterns\n"
    "- Domain knowledge and expertise area\n\n"
    "Respond with ONLY a JSON object. No markdown fences, no explanation.\n\n"
    'JSON format:\n'
    '{"summary": "1-2 sentence overview of skill\'s capability landscape",\n'
    '"capabilities": [\n'
    '  {\n'
    '    "name": "short_label",\n'
    '    "description": "What this capability does (1 sentence)",\n'
    '    "is_current": true|false,\n'
    '    "confidence": 0.X,\n'
    '    "evidence": ["specific line/quotation from skill"],\n'
    "    \"expansion_suggestion\": \"How to extend this or fill gaps\"\n"
    '  }\n'
    "]}\n\n"
    "Aim for 3-6 current capabilities and 2-4 potential capabilities. "
    "Be specific — vague capabilities like 'general_help' should be avoided. "
    "Evidence must be actual text found in the SKILL.md body."
)

_USER_TEMPLATE = (
    "## Skill Frontmatter\n"
    "name: {name}\n"
    "description: {description}\n"
    "triggers: {triggers}\n\n"
    "## Skill Content\n{body}\n\n"
    "Identify current and potential capabilities. JSON only."
)


# ---------------------------------------------------------------------------
# Discoverer
# ---------------------------------------------------------------------------


class CapabilityDiscoverer:
    """Analyze a parsed skill to discover current and potential capabilities.

    Uses GitHub Models API (gpt-4o-mini) for LLM-based analysis.
    Falls back to keyword-based heuristic when no token is available.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        github_token: str | None = None,
    ) -> None:
        self.model = model
        self._token = github_token or os.environ.get("GITHUB_TOKEN")

    def discover(self, parsed: ParsedSkill) -> CapabilityReport:
        """Run capability discovery on a parsed skill.

        Falls back to keyword-based analysis when GITHUB_TOKEN is unavailable.
        """
        if not self._token:
            return self._fallback_discover(parsed, "No GITHUB_TOKEN")

        try:
            response = self._call_api(parsed)
            data = self._parse_response(response)
            return CapabilityReport.from_api_response(data, skill_name=parsed.meta.name)
        except Exception as exc:
            return self._fallback_discover(parsed, f"GitHub Models API error: {exc}")

    def is_available(self) -> bool:
        """Check if the GitHub Models API is available (token present)."""
        return bool(self._token)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_api(self, parsed: ParsedSkill) -> str:
        import httpx

        desc = parsed.meta.description.strip() or parsed.meta.name
        triggers = ", ".join(parsed.meta.triggers) if parsed.meta.triggers else "(none)"
        body = parsed.raw_body[:8000]
        user_message = _USER_TEMPLATE.format(
            name=parsed.meta.name,
            description=desc,
            triggers=triggers,
            body=body,
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
                    "temperature": 0.1,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
            return json.dumps({
                "summary": "Empty response from API",
                "capabilities": [
                    {
                        "name": "unknown",
                        "description": "Unable to analyze — empty API response",
                        "is_current": True,
                        "confidence": 0.0,
                        "evidence": [],
                        "expansion_suggestion": "Retry with valid API response",
                    }
                ],
            })

    @staticmethod
    def _parse_response(response: str) -> dict:
        """Parse JSON from LLM response, stripping markdown fences if present."""
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = [ln for ln in lines[1:] if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "summary": f"Failed to parse LLM response: {text[:100]}",
                "capabilities": [],
            }

    @staticmethod
    def _fallback_discover(parsed: ParsedSkill, reason: str = "") -> CapabilityReport:
        """Keyword-based fallback when API is unavailable.

        Extracts basic capability heuristics from sections and description.
        """
        caps: list[Capability] = []

        # Try to derive current capabilities from section headings
        section_titles_seen: set[str] = set()
        for section in parsed.sections:
            title = section.get("title", "").strip().lower()
            if title and title not in section_titles_seen:
                section_titles_seen.add(title)
                caps.append(
                    Capability(
                        name=title.replace(" ", "_").lower(),
                        description=f"Handles {title} as described in skill",
                        is_current=True,
                        confidence=0.6,
                        evidence=[f"Section heading: ## {title}"],
                        expansion_suggestion=(
                            f"Consider adding examples for {title}"
                            if not section.get("body", "").strip()
                            else ""
                        ),
                    )
                )

        # Derive potential from description keywords
        desc = parsed.meta.description.lower()
        if "analyze" in desc or "analyze" in desc:
            potential_name = "data_analysis"
            if not any(c.name == potential_name for c in caps):
                caps.append(
                    Capability(
                        name=potential_name,
                        description="Analyze and interpret structured information",
                        is_current=False,
                        confidence=0.4,
                        evidence=["Derived from skill description keyword: 'analyze'"],
                        expansion_suggestion="Add explicit analysis workflow and output format",
                    )
                )

        if "generate" in desc or "create" in desc:
            potential_name = "content_generation"
            if not any(c.name == potential_name for c in caps):
                caps.append(
                    Capability(
                        name=potential_name,
                        description="Generate structured content and outputs",
                        is_current=False,
                        confidence=0.4,
                        evidence=["Derived from skill description keyword: 'generate'/'create'"],
                        expansion_suggestion=(
                            "Add output templates and examples"
                            " for generated content"
                        ),
                    )
                )

        # Add a general catch-all potential if nothing found
        if not any(not c.is_current for c in caps):
            caps.append(
                Capability(
                    name="domain_expansion",
                    description="Extend to adjacent use cases within the skill's domain",
                    is_current=False,
                    confidence=0.3,
                    evidence=[],
                    expansion_suggestion=(
                        "Review skill body for reusable patterns"
                        " that could generalize"
                    ),
                )
            )

        total_current = sum(1 for c in caps if c.is_current)
        total_potential = sum(1 for c in caps if not c.is_current)

        prefix = f"Keyword-based fallback ({reason})"
        return CapabilityReport(
            capabilities=caps,
            skill_name=parsed.meta.name,
            summary=(
                f"{prefix}. Found {total_current} current, "
                f"{total_potential} potential capabilities via heuristics."
            ),
            total_current=total_current,
            total_potential=total_potential,
        )
