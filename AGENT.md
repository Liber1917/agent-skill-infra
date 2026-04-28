# Agent Behavior Guide

This file defines conventions for AI agents working on this repository.

## Git Workflow
- Always create a new branch from main: `git checkout -b agent/<task-id>-<description>`
- Never push directly to main/master
- All changes require a PR + human review before merge

## Commit Convention
- Use Conventional Commits: `type(scope): summary`
  - Types: feat, fix, docs, style, refactor, test, chore
  - Scopes: shared, quality-check, test-runner, version-aware
- Each commit MUST include a trailer:
  ```
  Agent-Task: <brief description of what this commit achieves>
  Agent-Model: <model identifier used>
  ```
- Atomic commits: one logical change per commit, independently revertable
- Long tasks: use Checkpoint commits during work, rebase before PR

## Branch Strategy
- Naming: `agent/<task-id>-<brief-description>`
- One task per branch
- Base branch: main

## PR Requirements
- Use `.github/pull_request_template/agent.md` template
- Must include: Task Description, Agent Context, Testing
- All CI checks must pass before review
