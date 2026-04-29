"""SchemaJudger: validates output JSON against a JSON Schema."""

from __future__ import annotations

import json

import jsonschema

from skill_infra.test_runner.judgers.base import Judger


class SchemaJudger(Judger):
    """JSON Schema validation judger.

    Expected dict IS the JSON Schema (e.g. ``{"type": "object", "properties": {...}}``).
    The agent output must be parseable as JSON and validate against the schema.
    """

    def judge(self, output: str, expected: dict) -> tuple[bool, float, str]:  # type: ignore[type-arg]
        # Try to parse JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError as exc:
            return False, 0.0, f"output is not valid JSON: {exc}"

        # Validate against schema
        try:
            jsonschema.validate(instance=data, schema=expected)
            return True, 1.0, "JSON output matches schema"
        except jsonschema.ValidationError as exc:
            return False, 0.0, f"schema validation failed: {exc.message}"
