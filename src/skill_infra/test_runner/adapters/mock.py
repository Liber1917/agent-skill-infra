"""MockAdapter: a configurable in-memory agent adapter for testing."""

from __future__ import annotations

from skill_infra.shared.adapter import AgentAdapter


class MockAdapter(AgentAdapter):
    """Deterministic adapter that returns pre-configured responses.

    Useful for unit testing the runner and judgers without a live agent.

    Args:
        responses: Optional mapping of prompt → response string.
            Prompts not in the mapping fall back to ``default``.
        default: Response to return when no mapping matches.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default: str = "mock response",
    ) -> None:
        self._responses: dict[str, str] = responses or {}
        self._default = default

    async def run(self, prompt: str, timeout: int = 30) -> str:
        return self._responses.get(prompt, self._default)

    @property
    def name(self) -> str:
        return "mock"
