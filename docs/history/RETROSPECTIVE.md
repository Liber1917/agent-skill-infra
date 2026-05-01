# Agent Skill Infrastructure — 项目回顾

> 从 2026-04-28 到 2026-05-01，一个想法到可工作原型 + CI + 自动化测试系统

---

## 目录

1. [时间线](#时间线)
2. [关键决策与转折点](#关键决策与转折点)
3. [技术演进](#技术演进)
4. [踩坑经验](#踩坑经验)
5. [外部参考与启发](#外部参考与启发)
6. [当前状态](#当前状态)
7. [设计原则总结](#设计原则总结)

---

## 时间线

### Phase 0: 研究期 (2026-04-28 ~ 04-29)

**背景**: 用户提出 "Agent Skill 基础设施化" 概念——通过一套流程/基础设施来规范 Agent Skill 的创建、测试、发布和运维。

**产出**:

| 报告 | 篇幅 | 核心结论 |
|------|------|---------|
| `feasibility.md` | 165 行 | 技术可行，市场需求强，竞争未固化。时间窗口 12-18 个月 |
| `solutions.md` | 523 行 | 四层收敛架构（规范→依赖→安全→版本），砍掉企业级定位 |
| `skill_dev_test_practices.md` | 313 行 | 生态成熟度 3/10，行为测试完全空白，建议首选测试运行器 |
| `dependencies.md` | 298 行 | 所有平台不提供 Skill 级别依赖管理 |
| `integrated_solution_v3.md` | 440 行 | 双线架构（质量+安全），后废弃 |
| `integrated_solution_v4.md` | 503 行 | 单线三模块架构（质量+测试+版本），安全降级为横切 |

**关键收敛**:
- 语言从 TypeScript → Python 3.12（Skill 安全工具链生态主流为 Python）
- 定位从"大而全" → "个人开发者友好的预警雷达"
- 架构从 7 层 → 4 层 → 最终收敛为 3 个独立模块

### Phase 0-4: 基础建设 (2026-04-29 ~ 05-01)

**28 个 commits**，从零到可用的三模块原型：

```
Phase 0: uv workspace 初始化        (3 commits)
Phase 1: 共享类型 + adapter + CLI    (4 commits)
Phase 2: test_runner 核心 + judgers  (4 commits)
Phase 3: quality_check + version     (3 commits)
Phase 4: LLM judge + linter + PyPI   (4 commits)
```

**Phase 4 完成状态**: 162 tests, 3 CLI entry points, PyPI 可用

### 2026-05-01: 实战验证日

当天完成的工作构成了项目的"第二曲线"：

| 时间 | 事项 | 产出 |
|------|------|------|
| 18:42 | 自测 agent-skill-infra | 162 tests all green |
| 18:47 | 测试 oh-my-openagent | 5,829/5,872 (99.3%) |
| 19:52 | 测试 everything-claude-code | 2,200/2,200 |
| 20:04 | 提炼最佳实践 | 4 个 P0/P1/P2 建议 |
| 20:13 | 实施 P0 升级 | pre-flight + catalog + snapshot |
| 20:42 | Issue-triggered 测试系统 | GitHub Actions 全自动 |

> **一日之内**：测试了 3 个外部仓库 → 提炼了最佳实践 → 实施了 3 项架构升级 → 建了 Issue 驱动的自动化测试系统 → 全部提交并推送

---

## 关键决策与转折点

### 1. Python over TypeScript

**触发**: Skill 安全工具链（AI-Infra-Guard, Cisco Scanner）均为 Python。

**影响**: 决定了整个技术栈——uv, pytest, ruff, pyright, Typer。

### 2. 砍掉安全审计独立产品线

**触发**: v3 方案评审时发现个人开发者不需要独立的"安全审计工具"，只需要"安装前的风险感知"。

**结果**: v4 架构中安全能力降级为横切子模块，通过整合 Cisco Scanner CLI 实现。

### 3. 三模块收敛

最终产品 = quality_check（评分）+ test_runner（行为测试）+ version_aware（版本感知）。

三者有自己的 CLI、自己的 SKILL.md fixture、自己的测试套件，但通过共享类型和 snapshot 基础设施互联。

### 4. Issue-Triggered 测试 = 产品化临门一脚

不是"再做一轮研究"，而是直接问"能不能用 GitHub 自有基础设施"。答案是能——Issue Form + Actions + GITHUB_TOKEN = 零额外成本的自动化测试服务。

---

## 技术演进

### 代码量增长

| 阶段 | 文件数 | 测试数 | CLI |
|------|--------|--------|-----|
| Phase 0 | ~10 | 0 | 0 |
| Phase 4 | ~56 | 162 | 3 |
| 实战日后 | ~63 | **202** | 3 + Issue workflow |

### 模块演进

```
quality_check/           test_runner/            version_aware/
  checkers.py (5类)       judgers/ (6种)          git_diff.py
  parser.py               - keyword              regression.py
  scorecard.py            - schema               rollback.py
  cli.py                  - llm / llm-stub       security_diff.py
  linter_adapter.py       - flow                 cli.py
  security_integration.py - snapshot (NEW)
  cli.py                  runner.py
                          snapshot.py
  skills/quality-check/   skills/test-runner/     skills/version-aware/
    SKILL.md                SKILL.md                SKILL.md
    evals.json
```

### 共享基础设施

```
shared/                   scripts/ci/               docs/reports/
  types.py                pre_flight.py             (4 份测试报告)
  evals_schema.py         issue_tester.py
  adapter.py              .github/workflows/
  tool_adapter.py           ci.yml
                            issue-test.yml
                          .github/ISSUE_TEMPLATE/
                            test-request.yml
```

---

## 踩坑经验

从 MEMORY.md 积累的 10 条经验：

| # | 踩坑 | 教训 |
|---|------|------|
| 1 | hatchling 不自动发现 src 下的包 | 必须显式配置 `packages = ["src/skill_infra"]` |
| 2 | uv dev-dependencies 弃用 | 改用 `[dependency-groups]` |
| 3 | uv 安装路径非常规 | macOS 上是 `~/.local/bin/uv` |
| 4 | textwrap.dedent + f-string 反斜杠 | 前导空格残留，用 `"\n".join(parts)` 替代 |
| 5 | Typer 函数默认值触发 B008 | 需要 per-line `# noqa: B008` |
| 6 | asyncio event loop | 无 running loop 时须用同步 httpx.Client |
| 7 | TOML urls section | `[project.urls]` 后直接写其他 section 会被解析为 URL |
| 8 | smoke test 硬编码版本号 | bump 版本需同步更新 smoke test |
| 9 | GitHub Pages → Vercel | 自定义域名问题导致 Pages 全量 301 重定向 |
| 10 | pyright strict → standard | 251 个 fixture 类型注解假阳性 |

---

## 外部参考与启发

### 测试过的仓库

| 仓库 | 版本 | 测试规模 | 通过率 | 学到的 |
|------|------|---------|--------|--------|
| oh-my-openagent | 3.17.12 | 5,872 tests / 587 files | 99.3% | 测试文件隔离模式、regression test 命名约定 |
| everything-claude-code | 2.0.0-rc1 | 2,200 tests / 109 files | 100% | CI 分层管道、catalog check、安全门禁 |

### 借鉴实现的改进

| 来源 | 学到了什么 | 实现为什么 |
|------|-----------|-----------|
| ecc catalog:check | 代码与文档数量一致性校验 | `test_catalog.py` (9 tests) |
| ecc 7-stage CI | 测试前先预检关键依赖 | `pre_flight.py` (6 checks) |
| oh-my snapshot | 输出快照用于回归检测 | `SnapshotJudger` + registry |

---

## 当前状态

**Commit**: `43b724b` on `main`  
**Tests**: 202 all green  
**Lint**: ruff clean  
**Type Check**: pyright: 0 errors  
**Version**: 0.2.0  
**PyPI**: agent-skill-infra  

### 三个 CLI

```bash
skill-quality check <SKILL.md> [--lint] [--security]
skill-test run <evals.json> [--update-snapshots]
skill-version diff|check|rollback|baseline
```

### CI 流水线

```
pre_flight (6 checks) → ruff → pyright → pytest (202 tests)
                                          │
Issue 触发器 (独立 workflow)                │
  test-request label → clone → detect → test → comment
```

### 历史文档存档

```
docs/reports/
├── 2026-05-01_agent-skill-infra_self-check.md
├── 2026-05-01_oh-my-openagent.md
├── 2026-05-01_everything-claude-code.md
└── 2026-05-01_ci-safety-upgrade.md

docs/history/
└── RETROSPECTIVE.md (this file)

research_report_*.md (6 份研究阶段报告，在 workspace 根目录)
```

---

## 设计原则总结

经过 28 个 commits 的实践，沉淀出以下原则：

1. **资源整合 > 重复造轮子** — Cisco Scanner, agent-skill-linter, git 全部通过 CLI wrapper 整合
2. **分层渐进，不阻断** — 依赖声明可选，推断+容错兜底
3. **配置驱动，测试结构化验证** — ecc-universal 的成功证明了"配置为王"
4. **CI 是产品的一部分** — pre_flight + catalog + issue-triggered 不是运维脚本，是产品功能
5. **个人开发者友好** — 砍掉企业级复杂度，零侵入现有生态
6. **Python 3.12 + uv** — 选型因生态而非语言偏好
7. **snapshot 是回归检测的通用语言** — 连通 test_runner ↔ version_aware
8. **Issue 就是 API** — 不建 web 端，用 GitHub 原生 Issue + Actions 做自动化入口

---

*项目起于一个"Agent Skill 如何被测试和管理"的问题，经过 4 天密集研究 + 开发，最终产出了一个可发布、可自动化、可由社区驱动的测试基础设施。*
