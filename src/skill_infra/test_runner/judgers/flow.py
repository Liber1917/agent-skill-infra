"""FlowJudge: validates agent tool call sequences."""

from __future__ import annotations

import json
from typing import Any

from skill_infra.test_runner.judgers.base import Judger


class FlowJudge(Judger):
    """Validates that the agent called tools in the expected sequence.

    Expected dict format::

        {
            "tool_sequence": [
                {"name": "read_file", "args_contains": {"path": "..."}},
                {"name": "edit_file"},
            ],
            "strict_order": True   # optional, defaults to True
        }

    The agent output must contain a JSON object with a ``tool_calls`` key
    (an array of ``{"name": str, "args": dict}`` objects).
    """

    def judge(self, output: str, expected: dict[str, Any]) -> tuple[bool, float, str]:  # type: ignore[type-arg]
        tool_sequence: list[dict[str, Any]] = expected.get("tool_sequence", [])
        strict_order: bool = expected.get("strict_order", True)

        # Parse tool calls from agent output
        actual_calls = self._parse_tool_calls(output)
        if actual_calls is None:
            return False, 0.0, "Failed to parse tool_calls from output"

        if not tool_sequence:
            return True, 1.0, "Empty expected sequence, trivially matches"

        return self._validate_sequence(actual_calls, tool_sequence, strict_order)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_tool_calls(output: str) -> list[dict[str, Any]] | None:
        """Extract tool_calls array from structured JSON output."""
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return None

        if isinstance(data, dict) and "tool_calls" in data:
            calls = data["tool_calls"]
            if isinstance(calls, list):
                return calls
        return None

    def _validate_sequence(
        self,
        actual: list[dict[str, Any]],
        expected: list[dict[str, Any]],
        strict_order: bool,
    ) -> tuple[bool, float, str]:
        """Compare actual tool calls against expected sequence."""
        actual_names = [c.get("name", "") for c in actual]
        actual_by_name = {c.get("name", ""): c for c in actual}

        if strict_order:
            return self._strict_validate(actual, expected)
        return self._relaxed_validate(actual_names, actual_by_name, expected)

    def _strict_validate(
        self,
        actual: list[dict[str, Any]],
        expected: list[dict[str, Any]],
    ) -> tuple[bool, float, str]:
        """Strict order: actual must match expected exactly in sequence."""
        if len(actual) != len(expected):
            return False, 0.0, (f"Tool count mismatch: expected {len(expected)}, got {len(actual)}")

        for i, exp_tool in enumerate(expected):
            act_tool = actual[i]
            exp_name = exp_tool.get("name", "")
            act_name = act_tool.get("name", "")

            if exp_name != act_name:
                return (
                    False,
                    i / len(expected),
                    (f"Tool mismatch at position {i}: expected {exp_name!r}, got {act_name!r}"),
                )

            # Check args_contains
            args_contains = exp_tool.get("args_contains")
            if args_contains:
                match, detail = self._check_args(act_tool.get("args", {}), args_contains)
                if not match:
                    return (
                        False,
                        i / len(expected),
                        (f"Args mismatch at position {i} for {exp_name!r}: {detail}"),
                    )

        return True, 1.0, "Tool sequence matches exactly (strict order)"

    def _relaxed_validate(
        self,
        actual_names: list[str],
        actual_by_name: dict[str, dict[str, Any]],
        expected: list[dict[str, Any]],
    ) -> tuple[bool, float, str]:
        """Relaxed mode: expected sequence must be a subsequence of actual."""
        matched = 0
        actual_idx = 0

        for exp_tool in expected:
            exp_name = exp_tool.get("name", "")
            # Find next occurrence of exp_name in actual from current index
            found = False
            while actual_idx < len(actual_names):
                if actual_names[actual_idx] == exp_name:
                    # Check args_contains if present
                    args_contains = exp_tool.get("args_contains")
                    if args_contains:
                        act_args = actual_by_name[exp_name].get("args", {})
                        args_ok, _detail = self._check_args(act_args, args_contains)
                        if not args_ok:
                            actual_idx += 1
                            continue
                    matched += 1
                    actual_idx += 1
                    found = True
                    break
                actual_idx += 1

            if not found:
                return False, matched / len(expected), (f"Missing expected tool: {exp_name!r}")

        return True, 1.0, "All expected tools found in sequence (relaxed)"

    @staticmethod
    def _check_args(
        actual_args: dict[str, Any],
        expected_contains: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check that actual_args contains all expected key-value pairs."""
        for key, value in expected_contains.items():
            if key not in actual_args:
                return False, f"missing arg {key!r}"
            if actual_args[key] != value:
                return False, (f"arg {key!r}: expected {value!r}, got {actual_args[key]!r}")
        return True, ""
