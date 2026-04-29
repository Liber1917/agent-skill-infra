"""AgentAdapter abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod


class AgentAdapter(ABC):
    """Abstract interface for agent execution backends.

    Implementations wrap different agent runtimes (Claude Code, mock, etc.)
    and expose a uniform async interface for the test runner.
    """

    @abstractmethod
    async def run(self, prompt: str, timeout: int = 30) -> str:
        """Execute a prompt and return the agent's raw text output.

        Args:
            prompt: The input to send to the agent.
            timeout: Maximum seconds to wait for a response.

        Returns:
            The agent's response as a plain string.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for this adapter, used in reports."""
        ...
