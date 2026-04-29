"""Base class for all judgers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Judger(ABC):
    """Abstract judger interface.

    A judger takes the agent's raw output and the expected spec from a test
    case, and decides whether the output passes, along with a numeric score
    and a human-readable reason.
    """

    @abstractmethod
    def judge(self, output: str, expected: dict) -> tuple[bool, float, str]:  # type: ignore[type-arg]
        """Evaluate agent output against the expected spec.

        Args:
            output: The raw string produced by the agent.
            expected: The expected spec dict from the EvalCase.

        Returns:
            (passed, score, reason)
            - passed: True if the output meets the criteria.
            - score: Numeric quality score in [0.0, 1.0].
            - reason: Short human-readable explanation.
        """
        ...
