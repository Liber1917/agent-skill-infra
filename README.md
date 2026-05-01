# Agent Skill Infrastructure

> From dev to ops: quality check, behavior test runner, and version awareness for Agent Skills.

[![CI](https://github.com/Liber1917/agent-skill-infra/actions/workflows/ci.yml/badge.svg)](https://github.com/Liber1917/agent-skill-infra/actions)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Install

```bash
# PyPI (recommended)
pip install agent-skill-infra

# With LLM judge support (requires Anthropic API key)
pip install agent-skill-infra[llm]

# From source
git clone https://github.com/Liber1917/agent-skill-infra.git
cd agent-skill-infra
uv sync
```

## CLI Commands

### `skill-test` — Behavior Test Runner

Run evals.json test suites against skills with multi-dimension judgment.

```bash
# Run tests
skill-test run tests/fixtures/evals.json

# Output as JSON
skill-test run tests/fixtures/evals.json --output json

# Use mock adapter (no Agent runtime needed)
skill-test run tests/fixtures/evals.json --adapter mock
```

**Judge types**: keyword, schema, llm, flow, snapshot

### `skill-quality` — Quality Assessment

Score your SKILL.md against helloandy 8-dimension framework.

```bash
# Quick quality check
skill-quality check /path/to/skill/SKILL.md

# JSON output
skill-quality check /path/to/skill/SKILL.md --output json

# With agent-skill-linter integration
skill-quality check /path/to/skill/SKILL.md --lint

# With security scan (requires cisco-scanner)
skill-quality check /path/to/skill/SKILL.md --security
```

### `skill-version` — Version Awareness

Track changes, detect regressions, and roll back safely.

```bash
# See what changed between versions
skill-version diff /path/to/skill --old-ref HEAD~3 --new-ref HEAD

# Diff + security analysis
skill-version check /path/to/skill --security

# Roll back to previous version
skill-version rollback /path/to/skill --target-ref HEAD~1 --yes

# Store and compare baselines
skill-version baseline store /path/to/skill case-1 output.txt
skill-version baseline detect /path/to/skill case-1 output.txt
```

## Modules

| Module | CLI | Description |
|--------|-----|-------------|
| quality_check | `skill-quality` | 8-dimension scoring, linter integration, security |
| test_runner | `skill-test` | evals.json runner, 5 judge types, snapshot testing |
| version_aware | `skill-version` | diff, rollback, regression, security diff |

## Development

```bash
# Install dev dependencies
uv sync

# Run tests (162+)
uv run pytest

# Lint & format
uv run ruff check .
uv run ruff format .

# Type check
uv run pyright

# Build
uv build
```

## License

MIT
