"""LLMStubJudger: placeholder for LLM-based judgment (Phase 2)."""

from __future__ import annotations

from skill_infra.test_runner.judgers.base import Judger


class LLMStubJudger(Judger):
    """Stub LLM judger — always passes.

    Real LLM-based judgment will be implemented in Phase 2 when the
    Anthropic SDK integration is added.
    """

    def judge(self, output: str, expected: dict) -> tuple[bool, float, str]:  # type: ignore[type-arg]
        return True, 1.0, "LLM judger not implemented yet (stub)"
