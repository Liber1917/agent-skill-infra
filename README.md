# Agent Skill Infrastructure

> Quality tools for Agent Skills. Not a marketplace. Not a platform.
> A testing and scoring toolkit that works wherever you do.

[![CI](https://github.com/Liber1917/agent-skill-infra/actions/workflows/ci.yml/badge.svg)](https://github.com/Liber1917/agent-skill-infra/actions)
[![PyPI](https://img.shields.io/pypi/v/agent-skill-infra.svg)](https://pypi.org/project/agent-skill-infra/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## What It Is

Three modules. One toolkit. From local CLI to automated CI.

```
skill-quality    →  Score your SKILL.md (keyword → LLM → GitHub Models)
skill-test       →  Run behavior tests against evals.json
skill-version    →  Track changes, detect regressions, roll back
```

## What It Is Not

We don't sell skills. We don't host a marketplace. We're not a content platform.
We test, score, and version the skills you already have.

---

## Quick Start

```bash
pip install agent-skill-infra
skill-quality /path/to/skill/SKILL.md
```

Too simple? Good. That's the point.

## How to use it — three ways

| Channel | Setup | Best for |
|---------|-------|----------|
| **CLI** | `pip install agent-skill-infra` | Local dev, pre-commit hooks |
| **GitHub Issue** | [Open a test-request issue](https://github.com/Liber1917/agent-skill-infra/issues/new?template=test-request.yml) | Zero-setup testing, community submissions |
| **CI** | `uses: Liber1917/agent-skill-infra/.github/workflows/issue-test.yml` *(coming)* | PR gates, automated reviews |

---

## `skill-quality` — Quality Scoring

Three evaluation tiers, automatically selected:

```bash
# Tier 1: Fast keyword-based (no API needed, instant)
skill-quality skills/my-skill/SKILL.md

# Tier 2: Anthropic Claude (semantic evaluation, language-aware)
skill-quality skills/my-skill/SKILL.md --llm

# Tier 3: GitHub Models (free, zero-config, gpt-4o-mini)
skill-quality skills/my-skill/SKILL.md --gh-models

# Options
skill-quality skills/my-skill/SKILL.md --lint      # agent-skill-linter
skill-quality skills/my-skill/SKILL.md --security   # cisco-scanner
skill-quality skills/my-skill/SKILL.md --output json
```

**What you get**: Score (0–100%), 8-dimension breakdown, and actionable improvement suggestions — not just a number.

## `skill-test` — Behavior Testing

Run evals.json test suites. Five judge types. No Agent runtime required.

```bash
skill-test run tests/fixtures/evals.json

# With mock adapter (offline, no runtime)
skill-test run tests/fixtures/evals.json --adapter mock

# Update snapshot baselines
skill-test run tests/fixtures/evals.json --update-snapshots
```

**Judge types**: `keyword`, `schema`, `llm` (Claude), `flow`, `snapshot`

## `skill-version` — Version Awareness

Catch drift before it breaks things.

```bash
skill-version diff /path/to/skill --old-ref HEAD~3 --new-ref HEAD
skill-version check /path/to/skill --security
skill-version rollback /path/to/skill --target-ref HEAD~1 --yes
skill-version baseline store /path/to/skill case-1 output.txt
skill-version baseline detect /path/to/skill case-1 output.txt
```

---

## Design Philosophy

**No hardcoded benchmarks.** The keyword-based checker is a fallback, not the product.
Real evaluation happens through LLMs — Anthropic when you have a key, GitHub Models when you don't.

**Scoring is useless without suggestions.** Every quality report includes per-dimension findings
and concrete "do this next" improvements. A number alone isn't a tool.

**The tool adapts to the skill, not vice versa.** Chinese descriptions, mixed-language triggers,
single SKILL.md repos — we detect and score them all. No required JSON schema. No mandatory structure.

**Free tier for everyone.** GitHub Models (gpt-4o-mini) via the `--gh-models` flag costs nothing.
Zero API keys. Automated in CI via GITHUB_TOKEN.

---

## Development

```bash
git clone https://github.com/Liber1917/agent-skill-infra.git
cd agent-skill-infra
uv sync

uv run pytest          # 221 tests
uv run ruff check .     # lint
uv run pyright          # type check
```

---

## License

MIT
