# AGENTS.md

You are an AI agent working in the agent-skill-infra repository.
This file tells you what matters.

## What this repo is

**agent-skill-infra** is a Python CLI toolkit for testing, scoring, and versioning Agent Skills.
Three modules: skill-quality, skill-test, skill-version.

We are **not** a skill marketplace or content platform.
We are quality infrastructure for skills.

## What matters

| File | Why it matters |
|------|---------------|
| `src/skill_infra/quality_check/` | 8-dimension scoring, LLM + GitHub Models evaluators |
| `src/skill_infra/test_runner/` | Behavior test runner, 5 judge types (keyword/schema/llm/flow/snapshot) |
| `src/skill_infra/version_aware/` | Git diff, rollback, regression detection |
| `src/skill_infra/shared/` | Core types, ToolAdapter, Cisco Scanner integration |
| `scripts/ci/` | Issue-triggered testing, pre-flight gate |
| `tests/` | 221 tests across all modules |
| `pyproject.toml` | Python 3.12, uv workspace, hatchling build, ruff + pyright |

## Commands you'll use

```bash
uv run pytest                    # 221 tests
uv run ruff check .              # lint
uv run ruff format .             # format
uv run skill-quality <path> --gh-models --output json
uv run skill-test run <evals.json>
uv run skill-version diff <path> --old-ref HEAD~1 --new-ref HEAD
```

## How to contribute (for agents)

1. Make changes, write or update tests
2. `uv run ruff check . && uv run ruff format . && uv run pyright && uv run pytest`
3. All three must pass before committing
4. Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`
5. If adding a new checker/judge/adapter, update `tests/test_catalog.py`

## What NOT to do

- Do not delete `.workbuddy/` — project data, not temp cache
- Do not add ECC bundles, Claude Code configs, or platform-specific YAML — we're language-agnostic
- Do not hardcode quality benchmarks — use LLM judges instead
- Do not change version in two places — `importlib.metadata` reads from pyproject.toml

## CI pipeline

```
pre_flight (git/cisco/npx/import/paths) → ruff → pyright → pytest (221)
                                Issue trigger (labeled) → clone → detect → test → comment
```

## Design constraints

- Python 3.12+, uv workspace
- ruff for lint+format, pyright (standard mode) for type checking
- Typer for CLI, pytest for tests
- Three evaluation tiers: keyword (fallback) → Anthropic Claude → GitHub Models (free)
- GitHub Models (gpt-4o-mini) via `--gh-models` flag uses GITHUB_TOKEN — zero API key
- Scoring always includes actionable improvement suggestions, never just a number
