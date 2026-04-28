---
name: skill-quality-check
description: >
  Analyze and score Agent Skills using an 8-dimension quality framework (helloandy methodology).
  Checks trigger accuracy, output structure, error tolerance, token efficiency, and security posture.
  Use when reviewing, improving, or evaluating SKILL.md files for quality.
---

# Skill Quality Check

Evaluate Agent Skills against the helloandy 8-dimension quality framework.

## Dimensions

### Technical Quality (5 dimensions, 5 points each = 25 total)

1. **Trigger Accuracy** — Does the skill activate on the right inputs and ignore irrelevant ones?
2. **Output Structure** — Are outputs well-formatted, consistent, and follow expected schemas?
3. **Error Tolerance** — Does the skill handle edge cases gracefully without crashing?
4. **Token Efficiency** — Is the SKILL.md concise? Does it avoid unnecessary repetition?
5. **Tool Integration** — Are tool calls correct, efficient, and properly error-handled?

### Output Quality (3 dimensions, 5 points each = 15 total)

6. **Completeness** — Does the skill fully address the user's request?
7. **Actionability** — Are the outputs immediately usable without further clarification?
8. **Consistency** — Are outputs deterministic across similar inputs?

## Process

1. Read the target SKILL.md file
2. Score each dimension (1-5) with evidence
3. Calculate total score (max 40)
4. Provide specific improvement suggestions for any dimension scoring below 3
5. Output a structured report with scores, evidence, and recommendations

## Report Format

```
## Quality Report: [Skill Name]

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Trigger Accuracy | X/5 | ... |
| Output Structure | X/5 | ... |
| ... | ... | ... |

**Total: XX/40**
**Grade: [A/B/C/D/F]**

### Improvement Suggestions
- [Specific actionable suggestion for low-scoring dimensions]
```
