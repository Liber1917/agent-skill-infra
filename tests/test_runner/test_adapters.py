"""Tests for AgentAdapter ABC and MockAdapter."""

from __future__ import annotations

import pytest

from skill_infra.test_runner.adapters.mock import MockAdapter


class TestMockAdapter:
    @pytest.mark.asyncio
    async def test_default_response(self) -> None:
        adapter = MockAdapter()
        result = await adapter.run("any prompt")
        assert result == "mock response"

    @pytest.mark.asyncio
    async def test_mapped_response(self) -> None:
        adapter = MockAdapter(responses={"hello": "hi there"})
        result = await adapter.run("hello")
        assert result == "hi there"

    @pytest.mark.asyncio
    async def test_fallback_to_default_for_unmapped(self) -> None:
        adapter = MockAdapter(responses={"a": "b"}, default="fallback")
        result = await adapter.run("something else")
        assert result == "fallback"

    def test_adapter_name(self) -> None:
        adapter = MockAdapter()
        assert adapter.name == "mock"

    @pytest.mark.asyncio
    async def test_custom_default(self) -> None:
        adapter = MockAdapter(default="custom default response")
        result = await adapter.run("anything")
        assert result == "custom default response"

    @pytest.mark.asyncio
    async def test_async_semantics(self) -> None:
        """Ensure run() is a proper coroutine."""
        import asyncio

        adapter = MockAdapter()
        coro = adapter.run("test")
        assert asyncio.iscoroutine(coro)
        result = await coro
        assert isinstance(result, str)
