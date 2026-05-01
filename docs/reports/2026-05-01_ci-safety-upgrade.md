# agent-skill-infra CI/Safety 升级报告

**仓库**: [Liber1917/agent-skill-infra](https://github.com/Liber1917/agent-skill-infra)
**日期**: 2026-05-01
**Commit**: `fba82bc`
**版本**: 0.2.0 (unchanged)
**测试**: 182/182 passed (+20 new)

---

## 背景

基于对 `everything-claude-code` (2,200 tests) 和 `oh-my-openagent` (5,872 tests) 的测试最佳实践分析，识别出三个直接服务于 agent-skill-infra "开发安全测试一体化" 核心目的的改进项。

## 实施内容

### Task 1: Safety-first CI Gate

**新增**: `scripts/ci/pre_flight.py` (150 lines)

6 阶段预检流水线，在 pytest 之前运行：

| 阶段 | 检查项 | 严重度 |
|------|--------|--------|
| 1 | Git 可用性 | 阻断 (git 缺失则 version_aware 不可用) |
| 2 | cisco-scanner 可用性 | 警告 (--security flag 的依赖) |
| 3 | npx 可用性 | 警告 (--lint flag 的依赖) |
| 4 | 3 个 CLI entry point 可导入 | 阻断 |
| 5 | 3 个 SKILL.md fixture 可解析 | 阻断 |
| 6 | 源文件无硬编码绝对路径 | 警告 |

Exit codes: 0 = all clear, 1 = critical, 2 = warnings only.

**修改**: `.github/workflows/ci.yml` — 在 pytest 之前插入 `uv run python scripts/ci/pre_flight.py`

### Task 2: Catalog Consistency Check

**新增**: `tests/test_catalog.py` (9 tests, 150 lines)

防止"静默能力缩水"：

| 测试 | 验证内容 |
|------|---------|
| `test_checker_class_count` | checkers.py 有 5 个公开 checker 类 |
| `test_checker_types_match_readme` | README 提及 3 个模块 |
| `test_judger_export_count` | judgers/__init__.py 导出 7 个名称 |
| `test_judger_registry_coverage` | 每个 judger 在 `_DEFAULT_JUDGER_REGISTRY` 有对应 key |
| `test_judge_type_in_schema` | evals_schema.py 允许所有 registerd judge_type |
| `test_cli_entry_point_count` | pyproject.toml 有 3 个 CLI 入口 |
| `test_cli_subcommand_counts` | test=2, quality=1, version=5 子命令 |
| `test_all_three_modules_importable` | 3 个模块均可 import |
| `test_checker_names_are_descriptive` | checker 类名含 'Checker' |

### Task 3: Snapshot Judger

**新增**: `src/skill_infra/test_runner/judgers/snapshot_judge.py` (85 lines) + 测试 (8 tests, 130 lines)

**修改**: 4 个文件 — `judgers/__init__.py`, `runner.py`, `cli.py`, `evals_schema.py`

功能：
- **Auto-baseline 模式**：首次运行自动存储输出为基线，后续运行 diff 对比
- **`--update-snapshots` flag**：显式覆盖所有基线
- **内置 normalizer**：时间戳/路径/空白标准化，减少假阳性
- **registry 集成**：`judge_type: "snapshot"` 开箱即用

```
$ skill-test run evals.json              # auto-baseline → stores → matches
$ skill-test run evals.json --update-snapshots  # overwrite all baselines
```

## 影响对比

| 维度 | 实施前 | 实施后 |
|------|--------|--------|
| CI 流水线 | `ruff → pyright → pytest` | `pre_flight(6 checks) → ruff → pyright → pytest(182)` |
| 安全工具可用性 | 静默失败（--security skip 无感知） | CI gate 警告 + 测试 assert |
| 能力一致性 | 无校验（checker 可被误删） | 9 个 catalog test 守护 |
| Snapshot 使用 | 仅自测（test_snapshot.py） | 接入 test_runner registry + CLI |
| 测试数量 | 162 | 182 (+12.3%) |

## 测试结果

```
182 passed in 12.56s
ruff: All checks passed!
pyright: 0 errors, 0 warnings, 0 informations
```
