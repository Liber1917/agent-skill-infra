---
name: skill-test-runner
description: >
  Guide for writing behavior test cases (evals.json) for Agent Skills.
  Defines the eval schema, judgment criteria (trigger/flow/output), and snapshot testing conventions.
  Use when creating test cases for Skills or teaching others how to test Agent Skills.
---

# Skill Behavior Test Guide

Define and run behavior tests for Agent Skills using the evals.json format.

## evals.json Schema

```json
{
  "$schema": "http://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "skill_name": { "type": "string" },
    "skill_version": { "type": "string" },
    "evals": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "name": { "type": "string" },
          "trigger": {
            "type": "object",
            "properties": {
              "input": { "type": "string" },
              "should_trigger": { "type": "boolean" }
            },
            "required": ["input", "should_trigger"]
          },
          "flow": {
            "type": "object",
            "properties": {
              "expected_tools": { "type": "array", "items": { "type": "string" } },
              "expected_sequence": { "type": "boolean" }
            }
          },
          "output": {
            "type": "object",
            "properties": {
              "contains": { "type": "array", "items": { "type": "string" } },
              "not_contains": { "type": "array", "items": { "type": "string" } },
              "format": { "type": "string", "enum": ["text", "json", "markdown", "table", "code"] }
            }
          }
        },
        "required": ["id", "name", "trigger"]
      }
    }
  }
}
```

## Judgment Criteria

### Trigger Judgment
- Input matches skill description → skill should activate
- Input does not match → skill should NOT activate
- Edge cases: ambiguous inputs, multi-language, partial matches

### Flow Judgment (optional)
- Which tools should the skill call?
- In what order?
- Are there unnecessary tool calls?

### Output Judgment (optional)
- Must contain specific keywords/phrases
- Must NOT contain certain content
- Expected output format (text/json/markdown/table/code)

## Writing Guidelines

1. Each eval tests ONE behavior aspect (trigger, flow, or output)
2. Use descriptive IDs: `trigger-positive-basic`, `output-format-json`, `flow-tool-sequence`
3. Include at least 2 positive trigger tests and 1 negative trigger test per skill
4. Test edge cases: empty input, very long input, multi-language
5. Save evals.json alongside the SKILL.md being tested
