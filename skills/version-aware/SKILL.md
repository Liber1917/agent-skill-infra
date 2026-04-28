---
name: skill-version-aware
description: >
  Track and manage Agent Skill versions using Git-backed versioning.
  Provides change summaries, behavior regression detection, dependency validation, and one-click rollback.
  Use when updating Skills, reviewing changes, or diagnosing post-update issues.
---

# Skill Version Awareness

Track and manage Agent Skill versions with change visibility and rollback capability.

## Core Capabilities

### 1. Version Fingerprinting
- Hash-based version identification (SHA-256 of SKILL.md content)
- Git commit SHA for repository-backed skills
- Semantic versioning for published skills

### 2. Change Summary
- Diff-based change detection between versions
- LLM-generated natural language summary of changes
- Classification: trigger change, output change, tool change, structural change

### 3. Dependency Validation
- Track external tool dependencies (CLI tools, APIs, packages)
- Validate dependencies are still available after update
- Detect dependency version conflicts

### 4. Behavior Regression Detection
- Compare test results before and after update
- Flag new test failures as potential regressions
- Generate regression report with before/after comparison

### 5. One-Click Rollback
- Git-based rollback to any previous version
- Preserve rollback history
- Validate skill functionality after rollback

## Workflow

### Before Update
1. Run current version's test suite → save baseline
2. Record current fingerprint

### After Update
1. Compute new fingerprint
2. Generate change summary (diff + LLM)
3. Validate dependencies
4. Run test suite → compare with baseline
5. If regressions detected: present report, offer rollback

## Report Format

```
## Version Update Report: [Skill Name]

**Before:** [fingerprint/commit]
**After:** [fingerprint/commit]

### Changes
- [Change summary in natural language]

### Dependency Check
| Dependency | Status | Notes |
|-----------|--------|-------|
| tool-name | OK/MISSING | ... |

### Behavior Regression
| Test | Before | After | Status |
|------|--------|-------|--------|
| test-id | PASS | PASS/FAIL | REGRESSION/OK |

### Recommendation
[Proceed / Rollback / Investigate]
```
