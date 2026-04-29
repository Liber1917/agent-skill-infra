"""Tests for FlowJudge: tool call sequence validation."""

from __future__ import annotations

import json

from skill_infra.test_runner.judgers.flow import FlowJudge


class TestFlowJudge:
    """FlowJudge validates agent tool call sequences against expected patterns."""

    def setup_method(self) -> None:
        self.judger = FlowJudge()

    # -- helpers --

    def _output(self, tool_calls: list[dict]) -> str:
        """Wrap tool calls as structured JSON output."""
        return json.dumps({"tool_calls": tool_calls})

    # -- basic matching --

    def test_exact_sequence_match(self) -> None:
        output = self._output([
            {"name": "read_file", "args": {"path": "/tmp/a.txt"}},
            {"name": "edit_file", "args": {"path": "/tmp/a.txt", "content": "new"}},
            {"name": "write_file", "args": {"path": "/tmp/a.txt"}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
                {"name": "write_file"},
            ],
            "strict_order": True,
        }
        passed, score, reason = self.judger.judge(output, expected)
        assert passed is True
        assert score == 1.0
        assert "sequence" in reason.lower() or "match" in reason.lower()

    def test_missing_tool(self) -> None:
        output = self._output([
            {"name": "read_file", "args": {}},
            {"name": "write_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
                {"name": "write_file"},
            ],
            "strict_order": False,
        }
        passed, _score, reason = self.judger.judge(output, expected)
        assert passed is False
        assert "edit_file" in reason

    def test_wrong_order_strict(self) -> None:
        output = self._output([
            {"name": "edit_file", "args": {}},
            {"name": "read_file", "args": {}},
            {"name": "write_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
                {"name": "write_file"},
            ],
            "strict_order": True,
        }
        passed, _score, reason = self.judger.judge(output, expected)
        assert passed is False
        assert "mismatch" in reason.lower() or "order" in reason.lower()

    def test_wrong_order_relaxed(self) -> None:
        output = self._output([
            {"name": "read_file", "args": {}},
            {"name": "other_tool", "args": {}},
            {"name": "edit_file", "args": {}},
            {"name": "write_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
                {"name": "write_file"},
            ],
            "strict_order": False,
        }
        passed, score, _reason = self.judger.judge(output, expected)
        assert passed is True
        assert score == 1.0

    def test_extra_tools_allowed_strict(self) -> None:
        """Extra tools before the expected sequence should fail in strict mode."""
        output = self._output([
            {"name": "search_file", "args": {}},
            {"name": "read_file", "args": {}},
            {"name": "edit_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
            ],
            "strict_order": True,
        }
        passed, _score, _reason = self.judger.judge(output, expected)
        assert passed is False

    def test_extra_tools_allowed_relaxed(self) -> None:
        """Extra tools are allowed in relaxed mode as long as core sequence exists."""
        output = self._output([
            {"name": "search_file", "args": {}},
            {"name": "read_file", "args": {}},
            {"name": "list_dir", "args": {}},
            {"name": "edit_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
            ],
            "strict_order": False,
        }
        passed, _score, _reason = self.judger.judge(output, expected)
        assert passed is True

    # -- args_contains --

    def test_args_contains_check(self) -> None:
        output = self._output([
            {"name": "read_file", "args": {"filePath": "/tmp/a.txt"}},
            {"name": "edit_file", "args": {"filePath": "/tmp/a.txt", "newContent": "hello"}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file", "args_contains": {"filePath": "/tmp/a.txt"}},
                {"name": "edit_file", "args_contains": {"filePath": "/tmp/a.txt"}},
            ],
        }
        passed, _score, _reason = self.judger.judge(output, expected)
        assert passed is True

    def test_args_contains_mismatch(self) -> None:
        output = self._output([
            {"name": "read_file", "args": {"filePath": "/tmp/b.txt"}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file", "args_contains": {"filePath": "/tmp/a.txt"}},
            ],
        }
        passed, _score, reason = self.judger.judge(output, expected)
        assert passed is False
        assert "arg" in reason.lower() or "param" in reason.lower()

    # -- edge cases --

    def test_empty_tool_sequence(self) -> None:
        output = self._output([])
        expected = {"tool_sequence": []}
        passed, _score, _ = self.judger.judge(output, expected)
        assert passed is True

    def test_no_tool_calls_in_output(self) -> None:
        output = "Just some text without tool calls"
        expected = {
            "tool_sequence": [{"name": "read_file"}],
        }
        passed, _score, _reason = self.judger.judge(output, expected)
        assert passed is False

    def test_malformed_json_output(self) -> None:
        output = "{not valid json"
        expected = {
            "tool_sequence": [{"name": "read_file"}],
        }
        passed, _score, _reason = self.judger.judge(output, expected)
        assert passed is False

    def test_default_strict_order_true(self) -> None:
        """When strict_order is not specified, default to True."""
        output = self._output([
            {"name": "read_file", "args": {}},
            {"name": "edit_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
            ],
        }
        passed, _score, _ = self.judger.judge(output, expected)
        assert passed is True

    def test_partial_score(self) -> None:
        """Score should reflect how many expected tools were found."""
        output = self._output([
            {"name": "read_file", "args": {}},
            # edit_file is missing
            {"name": "write_file", "args": {}},
        ])
        expected = {
            "tool_sequence": [
                {"name": "read_file"},
                {"name": "edit_file"},
                {"name": "write_file"},
            ],
            "strict_order": False,
        }
        passed, score, _reason = self.judger.judge(output, expected)
        assert passed is False
        assert score > 0.0
        assert score < 1.0
