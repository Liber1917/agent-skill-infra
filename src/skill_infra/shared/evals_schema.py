"""evals.json Schema validation."""

from __future__ import annotations

import jsonschema

EVALS_JSON_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Skill Eval Cases",
    "type": "object",
    "required": ["skill", "version", "cases"],
    "properties": {
        "skill": {"type": "string", "description": "Skill identifier"},
        "version": {"type": "string", "description": "Skill version"},
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "prompt", "expected", "judge_type"],
                "properties": {
                    "id": {"type": "string", "description": "Unique case identifier"},
                    "prompt": {"type": "string", "description": "Input prompt for the agent"},
                    "expected": {
                        "type": "object",
                        "description": "Expected output spec, interpreted by judge_type",
                    },
                    "judge_type": {
                        "type": "string",
                        "enum": ["keyword", "schema", "llm", "flow", "snapshot"],
                        "description": "Which judger to use for evaluation",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for filtering/categorization",
                    },
                    "timeout": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 300,
                        "description": "Max execution time in seconds (1-300)",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


class EvalsValidationError(Exception):
    """Raised when an evals.json file fails schema validation."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


def validate_evals(data: dict) -> None:
    """Validate evals.json data against the schema.

    Args:
        data: Parsed JSON dict from evals.json file.

    Raises:
        EvalsValidationError: If validation fails, with detailed error messages.
    """
    validator = jsonschema.Draft7Validator(EVALS_JSON_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))

    if not errors:
        return

    messages: list[str] = []
    for err in errors:
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        messages.append(f"  {path}: {err.message}")

    detail = "\n".join(messages)
    raise EvalsValidationError(
        f"evals.json validation failed with {len(errors)} error(s):\n{detail}",
        errors=messages,
    )
