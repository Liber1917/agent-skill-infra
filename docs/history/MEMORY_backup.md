# Agent Skill 基础设施化项目记忆

## 项目概述
用户正在探索"Agent Skill 基础设施化"概念，通过一套流程/基础设施来集成规范 Agent 行为，提高 Skill 稳定性。覆盖开发侧（创建+测试+发布）和运行侧（调度+治理+监控）。

## 核心结论
- 可行性：技术上可行、市场需求强、竞争未固化
- 最佳切入点：**安全审计+版本管理**
- 时间窗口：12-18个月（大厂垂直整合前）
- 实施策略：**资源整合为主**，串联现有开源工具

## v2 修订讨论结论（2026-04-29）
三个关键收敛决策：
1. **个人开发者定位**：砍掉企业级（Nacos/Zentinelle/Microsoft AGT）
2. **预警雷达定位**：不包办测试，安全审计=安装前风险感知，版本管理=变更感知
3. **零侵入现有生态**：依赖声明可选，推断+容错兜底，分层渐进适配

四层收敛架构（原七层）：
1. 标准化规范层（可选字段，不阻断）
2. 依赖管理+环境感知层（声明→推断→容错）
3. 安全预警层（YARA快扫→LLM意图分析→人话风险摘要）
4. 版本感知+变更预警层（变更摘要→行为差异→依赖校验→回滚→更新提醒）

安全审计关键发现：
- LLM意图分析：Cisco Scanner第5层（Claude 3.5 Sonnet）+ GovTech五步结构化推理（F1=0.844）
- 砍掉：对抗性红队测试、运行时权限拦截、社区众包信誉（个人开发者不需要）

版本管理关键发现：
- 工流失效根因：接口语义漂移、隐式依赖升级、prompt指令改写、上游依赖断裂
- 核心能力：变更摘要(diff+LLM)、行为差异检测(Snapshot)、依赖校验、一键回滚(Git)、更新提醒(Hash)

## 已完成的报告
1. **可行性分析报告**：`research_report_agent_skill_infra_feasibility.md`
   - 技术生态、竞品格局、开发者痛点、产品机会
2. **解决方案报告**：`research_report_agent_skill_infra_solutions.md`（v2修订版）
   - 四层收敛架构（规范层→依赖感知层→安全预警层→版本感知层）
   - 分层渐进依赖管理（声明→推断→容错）
   - 安全预警三步流程（YARA→LLM意图分析→人话摘要）
   - 版本感知五项能力（变更摘要→行为差异→依赖校验→回滚→更新提醒）
   - 砍掉企业级：Nacos/Zentinelle/Microsoft AGT/lock文件/SemVer强制
3. **Skill开发测试实践调研报告**：`research_report_skill_dev_test_practices.md`
   - 生态成熟度 3/10，关键空白是行为测试
   - 格式校验已有3个工具（agent-skill-linter最全），但都不查行为正确性
   - skill-creator 是唯一有自动化eval流程的工具，但覆盖面窄、无CI
   - SkillsBench：精选Skill提升16.2pp，自生成Skill无效
   - 建议首选切入点：Skill行为测试运行器

## 已安装的 Skill
- superpowers（wlshlad85）：spec-first TDD 开发工作流
- get-shit-done（shoootyou）：32个子Skill，需symlink到workbuddy
- autoresearch（thomaslwang）：Karpathy风格内容优化

## 关键工具清单
| 领域 | 推荐工具 | 备注 |
|------|----------|------|
| 依赖管理 | x-cmd pkg + 静态推断引擎 | x-cmd首选，uvx/npx语言特定补充，xlings通过抽象层隔离 |
| 安全预警 | AI-Infra-Guard + Cisco Scanner(L5) | GovTech五步推理prompt增强 |
| 版本感知 | Git + Hash-based + Snapshot Testing | 变更摘要用LLM生成 |
| 跨平台 | SKILL.md + llms.txt | x-cmd/skill仓库参考，npx skills适配器 |

## 技术栈（2026-04-29 确认）
- 语言：Python 3.12（替代 TypeScript，因 Skill 安全工具链生态主流为 Python）
- 包管理：uv workspace（Astral 出品，Rust 实现，极快）
- 测试：pytest + pytest-asyncio + pytest-cov
- Lint/Format：ruff（lint + format 统一，替代 eslint+prettier+black+isort）
- 类型检查：pyright（strict mode）
- CLI 框架：Typer
- CI：GitHub Actions
- 分发：PyPI + uvx/pipx
- 构建后端：hatchling
- Git 规范：Conventional Commits + Agent-Task/Agent-Model trailers
- L1 Skills：纯文档 SKILL.md（可注册进 x-cmd/skill 仓库）

## GitHub 仓库
- Liber1917/agent-skill-infra（public）
- Phase 0 已完成（4 commits on main）
- Phase 1 已完成（4 commits on main，总计 8 commits）
- Phase 2 已完成（4 commits on main，总计 12 commits）
- Phase 3 已完成（3 commits on main，总计 15 commits）
- Phase 4 已完成（4 commits on main，总计 19 commits）
- 版本: 0.2.0
- 162 tests all green（模块测试 + smoke test）
- CLI entry points:
  - `skill-test run|show`
  - `skill-quality check [--lint] [--security]`
  - `skill-version diff|check|rollback|baseline`
- judge_type 支持: keyword, schema, llm, flow, snapshot
- LLM judge: 真实 Anthropic API 调用，支持 semantic_equivalence / criteria 模式
- 可选依赖: pip install agent-skill-infra[llm]

## 踩坑经验
- hatchling 需配置 `[tool.hatch.build.targets.wheel] packages = ["src/skill_infra"]`，否则找不到包
- `tool.uv.dev-dependencies` 在 uv 0.11+ 已弃用，改用 `[dependency-groups]`
- uv macOS 安装路径是 `~/.local/bin/uv`（非 `~/.cargo/bin`）
- textwrap.dedent + f-string 反斜杠续行会导致前导空格残留，用 `"\n".join(parts)` 替代
- Typer B008 函数调用默认值需要 per-line `# noqa: B008`
- ruff RUF012 类属性 mutable default 需要 `ClassVar` 注解
- ruff RUF059 未使用的解包变量需前缀下划线 `_sha2`
- asyncio.get_event_loop().run_until_complete 在无 running loop 环境失败，改用同步 httpx.Client
- TOML 中 `[project.urls]` 后的第一个 key 仍在 urls table 内，需先闭合（放在 dependencies 之后）
- smoke test 硬编码版本号，每次 bump 版本需同步更新

## 产品形态（2026-04-29 最新：v4 单线三模块架构）
- **v4 报告已完成**：`research_report_integrated_solution_v4.md`
- **从 v3 双线架构转向 v4 单线三模块**：安全审计从独立产品线砍掉，降级为横切子模块
- 新架构：单线三模块（质量检查 + 行为测试运行器 + 版本感知）
- 安全能力通过整合实现（调用Cisco Scanner CLI），不自建扫描引擎
- 唯一安全相关空白：版本变更检测（OWASP AST07: Update Drift），属于版本感知模块
- **最有价值切入点不变**：L2 行为测试运行器（完全空白，生态成熟度2/10）
- 差异化叙事："从开发到运维全流程覆盖，别人只做安装前扫描"
- v3 报告保留作为历史参考：`research_report_integrated_solution_v3.md`

## 依赖管理现状调研（2026-04-29）
- 所有 Agent 平台不提供 Skill 级别依赖管理，安装=文件复制
- 主流做法：文档引导 + Agent 按指令执行依赖安装
- 唯一声明依赖的 Skill：ArXiv 论文精读（requires.bins: [uv]），但不自动安装
- x-cmd/skill 仓库：index.yml 无依赖字段，有依赖的 Skill 在 SKILL.md 中写 pip install
- x-security 和 AI-Infra-Guard Skill 版都是纯文档 Skill（零外部依赖）

## 架构定位：工程底座 vs 能力整合目标（2026-04-29）
- 工程底座：x-cmd（运行时环境）、Git（版本控制）——决定"能不能做"
- 能力整合目标：AI-Infra-Guard、Cisco Scanner、GovTech推理、Snapshot Testing——决定"有没有价值"
- x-cmd 是底座提供者，不是竞争对手；我们的差异化是安全和版本感知

## Skill 开发测试生态调研发现（2026-04-29）
- 开发流程：手工编写 SKILL.md 为主，无脚手架；官方只提供 template/ 目录
- 最大痛点：触发不准（90%新手踩坑）、无容错、Token膨胀、输出不一致
- 格式校验工具：agent-skill-linter（17规则，CI集成，v0.11.0）、Smithery skill-linter（14规则）、LLMVLab在线验证器
- 行为测试：完全空白，skill-creator eval 是唯一自动化工具但覆盖窄（2-3用例）
- helloandy 8维度质量评分体系最系统（技术5分+输出3分），但是框架非工具
- qa-agent-testing 方法论最完整（6维评分、变形测试、故障注入），但是文档非运行器
- SkillsBench 证明自生成Skill无效，聚焦Skill(2-3模块)优于综合文档
- 建议首选切入点：Skill行为测试运行器（自动运行+多维度判定+快照+CI）
- 建议次选：开发脚手架+热重载（skill init/dev/lint/test）

## 用户偏好
- 方法论：批判实用主义，从现象追踪根本原因
- 工作流：方案→确认→实施，复用优先
- 输出要求：事实性陈述需附证据链接，图表必须附带视觉案例
- 技术阅读偏好英文，需求梳理/设计解释倾向中文
