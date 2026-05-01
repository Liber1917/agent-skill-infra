# Agent Skill 基础设施化——整合方案 v4

## Executive Summary

本报告整合了四份前置调研（可行性分析、消费者侧解决方案、开发测试实践调研、依赖管理现状调研）的全部发现，以及后续安全审计赛道竞争格局调研的关键结论，提出一套覆盖 Skill 全生命周期的单线三模块基础设施方案。

v3 方案采用双线架构（安全审计 + 开发工具），但安全审计赛道竞争格局调研（2026-04-29）发现该赛道已高度拥挤：13 个直接竞争者（Cisco Scanner、AI-Infra-Guard、Snyk、Repello、SkillScan.dev、AgentMagic、Claude Code Security 官方、X-Skill-Scanner 等），且 OWASP 已发布 AST10、中科院已发表安全分类论文。我们的安全审计方案在安装前扫描场景上无任何差异化空间。

v4 方案据此将安全审计从独立产品线砍掉，降级为基础设施的可选子模块。新架构聚焦**单线三模块**：质量检查、行为测试运行器、版本感知。安全能力通过整合实现（调用 Cisco Scanner CLI 等），不自建扫描引擎。最有价值的切入点不变：**行为测试运行器**——当前唯一的完全空白点（成熟度 2/10）。

唯一的安全相关空白是 OWASP AST07: Update Drift（版本更新后的安全变更检测），这属于版本感知模块的范畴，而非独立的安全审计能力。

---

## 一、为什么从 v3 双线架构转向 v4 单线架构

### 1.1 安全审计赛道竞争格局

v3 方案撰写时，安全审计赛道尚有差异化空间。但 2026 年 4 月底的调研发现格局已完全改变：

**直接竞争者（13 个）：**

| 工具 | 类型 | 层级 | 最后更新 |
|------|------|------|---------|
| Cisco Skill Scanner | CLI 开源（Apache 2.0） | L3 完整（YARA+AST+LLM+VirusTotal） | 2026-04-10, v2.0.9 |
| AI-Infra-Guard（朱雀实验室） | Docker 平台（Apache 2.0） | L3 全栈红队 | 2026-04-23, v4.1.6 |
| Claude Code Security | Anthropic 官方内置 | L3 语义推理 | 2026-02-20 |
| Snyk Agent Scan | 网页+CLI（免费） | L2 自动化 | 2026-02-13 |
| Repello SkillCheck | 网页（免费） | L2 AI 驱动 | 2026-02-24 |
| SkillScan.dev | 网页（免费，Beta） | L2 AI 驱动 | 持续更新 |
| AgentMagic | 网页（148 项检查） | L2 OWASP Top 10 | 持续更新 |
| X-Skill-Scanner | CLI | L3（12 个检测引擎） | 2026-04-03 |
| skill-security-scanner（Gitee） | CLI（MIT） | L3（YARA+LLM+CVSS 3.1） | 2026-04 |
| skill-security-analyzer v2.0 | 元技能（DeepToAI） | L2（40+ 模式检测） | 2025-11 |
| agentlinter | Web+CLI | L1-L2（6 条安全规则） | 2026-02 |
| x-security（x-cmd） | CLI 工具集 | 非 Skill 安全审计 | 2026-04 |
| agent-skill-linter | CLI（Apache 2.0） | L1 格式检查（无安全规则） | 2026-04-09 |

**行业标准化动作：**
- OWASP 发布 Agentic Skills Top 10（AST10），对近 4000 个 Skill 扫描后发现超 1/3 有安全风险
- 中科院软件所发表《Towards Secure Agent Skills》论文，建立 7 类 17 个威胁场景分类体系
- Anthropic 正式推出 Claude Code Security（Enterprise/Team 专属）

### 1.2 v3 安全审计方案逐项对比

| v3 安全审计能力 | 竞争者覆盖 |
|----------------|-----------|
| L1 关键词扫描（敏感操作、外部 URL） | Cisco Static、Snyk、Repello、AgentMagic 全覆盖，且更全面 |
| L2 YARA 规则匹配 | Cisco 内置+自定义、Gitee scanner、X-Skill-Scanner 全覆盖 |
| L2 文件权限检查 | AI-Infra-Guard 覆盖 |
| L2 依赖漏洞扫描 | AI-Infra-Guard（1200+ CVE）、Snyk 全覆盖 |
| L3 LLM 意图分析 | Cisco（共识机制）、Gitee、X-Skill-Scanner 全覆盖 |

v3 方案中安全审计部分没有任何一项能力是现有工具做不到的。作为个人开发者，不可能在功能上超越 Cisco（思科级工程团队）或 Snyk（安全领域独角兽）。

### 1.3 唯一的安全空白：版本变更检测

Repello 的对比文章指出所有扫描工具的共同局限：当前扫描干净的 Skill，作者后续更新可能植入恶意行为。OWASP AST07: Update Drift 和中科院论文的 T2.2: Post-Installation Modification 都指向这个问题。

但这个空白属于"版本感知"的范畴，而非独立的安全审计能力。v4 方案在版本感知模块中内置了安全变更检测。

### 1.4 转向决策

**砍掉的部分：**
- 产品线 A（安全审计 Skill）作为独立产品线——取消
- L1 安全扫描 SKILL.md、L2 YARA 扫描器、L3 LLM 意图分析——不自建

**保留但降级的部分：**
- 安装前安全检查：行为测试运行器中增加 `security-check` 步骤，调用 Cisco Scanner CLI
- 版本变更安全检测：版本感知模块的子功能，更新时自动触发 Cisco CLI

**核心逻辑：** 自建安全扫描引擎是重复造轮子且无法超越竞争者；整合 Cisco 等成熟工具，用户得到的是更强的安全能力（7 引擎 vs 我们能自建的），不是更弱的替代品。

---

## 二、v4 单线三模块架构

### 2.1 架构总览

v3 的双线架构（安全审计 + 开发工具）简化为**单线三模块**：

| 模块 | 定位 | 核心用户 | 核心能力 | 生态成熟度 |
|------|------|---------|---------|-----------|
| 质量检查 | 开发阶段 | Skill 作者 | 8 维度评分 + 触发优化 + 输出规范 | 3/10 |
| 行为测试运行器 | 开发+CI 阶段 | Skill 作者 | evals.json 运行 + 多维度判定 + 快照 + CI | 2/10（完全空白） |
| 版本感知 | 运维阶段 | Skill 用户 | 变更摘要 + 行为差异 + 依赖校验 + 回滚 + 安全扫描 | 1/10 |

三个模块共享分层设计（L1/L2/L3），每层独立可用、渐进增强。安全能力作为横切关注点贯穿三个模块，通过调用外部工具（Cisco Scanner CLI、agent-skill-linter 等）实现，不自建。

### 2.2 共享的分层架构原则

**L1 纯文档层：** 纯 SKILL.md 格式，零依赖。Agent 使用内置工具（文件读取、文本分析）执行检查。可在所有 Agent 平台使用，可通过 x-cmd/skill 仓库分发。

**L2 脚本化层：** SKILL.md + scripts/（Python）。通过脚本提供自动化能力（测试执行、格式校验、安全扫描调用等）。依赖 Python 3，`scripts/setup.sh` 自动安装 uv 和依赖包。

**L3 增强层：** 接入 LLM API（Claude/GPT），提供语义理解、意图分析、质量评分等高级能力。需用户配置 API Key。

每一层独立可用。L3 不会因为 L1 不存在就无法工作——每层都是完整的功能闭环。

---

## 三、模块一：质量检查

### 3.1 定位

面向 Skill 作者，提供开发阶段的结构化质量评估。基于 helloandy 8 维度评分体系和 qa-agent-testing 6 维度方法论，从纯文档层到自动化评分逐层增强。

### 3.2 L1 开发引导（纯文档）

Agent 读取作者的 SKILL.md，按结构化步骤进行质量检查：

- **触发优化检查**：评估 description 是否包含足够具体的触发关键词，是否可能导致误触发或漏触发
- **输出规范检查**：检查 SKILL.md 是否明确定义了输出格式、示例、约束条件
- **容错覆盖检查**：扫描多步流程，检查是否有容错处理（"一出错就崩溃"是新手最常踩的坑）
- **Token 效率检查**：评估是否遵循渐进式披露（<500 行），过长内容应拆分到 references/
- **helloandy 8 维度快速评分**：触发精度、输出完整性、铁律具体性、错误恢复覆盖、示例质量、简洁性、一致性、边缘情况处理

输出：结构化质量报告，标注改进建议和优先级。

### 3.3 L2 自动化质量检查（脚本化）

在 L1 基础上增加：

- **格式校验集成**：直接调用 agent-skill-linter（17 条规则），不做重复造轮子
- **content-aware 检查**：description 质量评估、输出规范完整性检查的自动化实现
- **安全检查子模块**：调用 Cisco Scanner CLI（`skill-scanner scan /path/to/skill`），将安全扫描作为质量检查流程的一个步骤。不自建扫描引擎。
- **评分报告**：JSON 格式输出，可被 CI 系统消费

### 3.4 L3 智能质量评分（LLM 增强）

- **helloandy 8 维度自动化评分**：从手工评分升级为 LLM 自动评分
- **qa-agent-testing 6 维度评分**：自动化实现
- **改进建议生成**：基于评分结果，LLM 生成具体、可操作的改进建议

### 3.5 分发策略

- L1：注册进 x-cmd/skill 仓库，`x skill add quality` 一条命令安装。这是给 x-cmd 社区的"礼物"——基础质量检查免费贡献，建立生态位。
- L2/L3：GitHub Release + Agent 平台手动安装

---

## 四、模块二：行为测试运行器

### 4.1 定位

这是 v4 方案的核心切入点，也是当前生态中唯一的完全空白点（成熟度 2/10）。

面向 Skill 作者和 CI 系统，提供"Skill 被触发后是否按预期执行"的自动化验证。没有现有工具能做到这一点——agent-skill-linter 只查格式不查行为，skill-creator eval 是唯一有自动化 eval 流程的工具但覆盖面窄（2-3 个用例）且无 CI 集成。

### 4.2 L1 测试用例定义与引导（纯文档）

Agent 读取作者的 SKILL.md 和 evals.json（如有），引导编写测试用例：

- **正例设计**：按触发关键词设计应该触发 Skill 的输入
- **负例设计**：设计不应触发 Skill 的输入（验证不会误触发）
- **输出断言设计**：定义预期的输出格式、内容关键词、工具调用序列
- **evals.json 格式校验**：检查测试用例是否符合 JSON Schema

evals.json 格式（兼容 skill-creator，扩展支持负例和流程校验）：
```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": "should-trigger-positive",
      "type": "positive",
      "prompt": "帮我分析这段代码的性能",
      "expected": {
        "triggered": true,
        "output_contains": ["时间复杂度", "空间复杂度"],
        "tools_used": ["read_file", "search_content"]
      }
    },
    {
      "id": "should-not-trigger-negative",
      "type": "negative",
      "prompt": "今天天气怎么样",
      "expected": {
        "triggered": false
      }
    }
  ]
}
```

### 4.3 L2 行为测试运行器（脚本化）

这是最有价值的切入点。核心能力：

| 步骤 | 能力 | 实现方式 |
|------|------|---------|
| 1. 测试用例定义 | 支持 evals.json 格式 | JSON Schema 校验 |
| 2. 自动运行 | 给定 Skill 路径 + 测试套件，启动 Agent 运行每个用例 | 调用 Claude Code / OpenCode CLI 接口 |
| 3. 触发判定 | 正例是否触发、负例是否跳过 | 解析 Agent 日志/轨迹 |
| 4. 流程判定 | Agent 是否按 SKILL.md 定义的步骤执行 | 工具调用序列校验 |
| 5. 输出判定 | 结果是否符合输出规范 | 格式检查 + 内容关键词检查 |
| 6. 快照对比 | 首次保存快照，后续与快照对比 | 文本 diff（L3 可用语义等价判断） |
| 7. CI 集成 | JSON 报告 + 退出码 | GitHub Actions / GitLab CI |
| 8. 安全检查（可选） | 测试前对 Skill 做安全扫描 | 调用 Cisco Scanner CLI |

**Agent 运行时适配层：** 行为测试运行器依赖 Agent 运行时来执行 Skill。先做适配层抽象，不硬编码特定 Agent 的接口。优先支持 Claude Code CLI（最主流），后续可扩展 OpenCode、Cursor 等。

### 4.4 L3 智能增强（LLM 增强）

- **语义等价判断**：LLM 输出具有非确定性，逐字对比不可靠。L3 调用 LLM 判断两次输出在语义上是否等价（Agent-as-Judge 方法论）
- **自动生成测试用例**：给定 SKILL.md，LLM 自动生成正例/负例测试 prompt，扩展测试覆盖面
- **变形测试**：保留语义的小改动输入（同义词替换、语序调整），验证输出不变性（参考 qa-agent-testing）
- **质量评分自动化**：helloandy 8 维度和 qa-agent-testing 6 维度的 LLM 自动评分

### 4.5 分发策略

- L2 是核心层：行为测试运行器需要 Agent 运行时支持，通过 GitHub Release 分发
- L3 同 L2，额外需要 API Key
- L1 的测试用例定义引导可注册进 x-cmd/skill 仓库

---

## 五、模块三：版本感知

### 5.1 定位

面向 Skill 用户（安装和使用 Skill 的人），提供"安装后的变更感知"。不做版本锁定，只告知变更内容和潜在风险。

这是 v3 方案中"版本感知层"的独立化和增强。安全审计赛道调研发现 OWASP AST07: Update Drift（更新偏移）是所有竞争者的共同盲区——13 个安全扫描工具都是"安装前单点扫描"，没有覆盖"安装后 Skill 更新带来的安全变更"。

### 5.2 L1 基础版本感知（纯文档）

Agent 执行以下检查：

- **检测可用更新**：Git fetch + SHA 对比（需要 Skill 通过 Git 管理）
- **变更摘要**：Git diff 读取，Agent 展示变更文件列表和关键修改
- **一键回滚**：Git checkout 到上一个已知安全版本
- **更新提醒**：基于 Hash 变化检测新版本可用

### 5.3 L2 自动化版本感知（脚本化）

在 L1 基础上增加：

- **自动 diff 解析**：程序化解析 Git diff，结构化输出变更摘要（新增/修改/删除的文件和关键段落）
- **依赖差异检测**：对比新旧 dependencies 字段，解析依赖树变化
- **行为差异检测（Snapshot Testing）**：版本更新前后运行行为测试（调用模块二的行为测试运行器），对比输出变化。如果快照对比发现显著差异，标记为"行为退化风险"
- **安全变更检测**：版本更新时自动调用 Cisco Scanner CLI，对比更新前后的安全扫描结果。如果新增了安全风险标记，在变更摘要中醒目提示

### 5.4 L3 智能版本感知（LLM 增强）

- **自然语言变更摘要**：LLM 将 diff 翻译为开发者可理解的变更说明
- **行为差异语义判断**：Snapshot Testing 的结果由 LLM 做语义等价判断（与模块二 L3 共享能力）
- **依赖影响评估**：LLM 分析依赖变化可能带来的连锁影响

### 5.5 分发策略

- L1/L2/L3 统一通过 GitHub Release 分发
- L1 可注册进 x-cmd/skill 仓库作为基础版本检查工具

---

## 六、三个模块的关系

### 6.1 独立但可组合

三个模块在功能上独立——用户可以只安装质量检查，或只安装行为测试运行器。但它们在架构上协同：

- **质量检查**（模块一）帮作者产出更高质量的 Skill → 产出附带 evals.json 的 Skill → 供行为测试运行器使用
- **行为测试运行器**（模块二）的快照和测试用例 → 供版本感知模块在更新后重跑，检测行为退化
- **版本感知**（模块三）在检测到更新时 → 调用行为测试运行器重跑测试 → 调用 Cisco Scanner 做安全扫描

### 6.2 安全能力作为横切关注点

安全能力不是独立模块，而是贯穿三个模块的横切子功能：

| 安全能力 | 实现位置 | 实现方式 |
|---------|---------|---------|
| 安装前安全扫描 | 质量检查 L2 | 调用 Cisco Scanner CLI |
| 测试前安全扫描 | 行为测试运行器 L2 | 调用 Cisco Scanner CLI |
| 版本更新安全检测 | 版本感知 L2 | 对比更新前后 Cisco 扫描结果 |
| 格式规范检查 | 质量检查 L2 | 调用 agent-skill-linter CLI |

### 6.3 共享的工程基础设施

三个模块共享：
- Git 作为版本控制底座
- x-cmd 作为可选的工程底座和分发通道
- 相同的 L1/L2/L3 分层设计理念
- 相同的 evals.json 测试用例格式
- 相同的外部工具集成层（Cisco Scanner、agent-skill-linter）

### 6.4 与 x-cmd 的关系

| 模块 | L1 与 x-cmd 的关系 | L2/L3 与 x-cmd 的关系 |
|------|-------------------|---------------------|
| 质量检查 | L1 注册进 x-cmd/skill 仓库，回馈基础质量检查能力 | 独立分发，行为测试运行器 x-cmd 没有 |
| 行为测试 | L1 测试引导注册进 x-cmd/skill 仓库 | 独立分发，需要 Agent 运行时 |
| 版本感知 | L1 基础版本检查可注册进 x-cmd/skill 仓库 | 独立分发，Snapshot + 安全检测 x-cmd 没有 |

---

## 七、与现有生态的整合策略

### 7.1 不重复造轮子的部分

以下能力已有成熟的开源工具，直接整合而不自建：

| 能力 | 现有工具 | 整合方式 |
|------|---------|---------|
| 格式校验 | agent-skill-linter（17 规则） | L2 直接调用 CLI |
| 官方规范验证 | agentskills.io skills-ref | L1 指导 Agent 调用 |
| 安全扫描 | Cisco Skill Scanner（7 引擎） | L2 调用 CLI，不自建扫描引擎 |
| 依赖漏洞检查 | AI-Infra-Guard / OSV | 可选后端，安全扫描子模块 |
| LLM 意图分析 | Cisco Scanner（L5 共识机制） | Cisco 内置，我们直接调用 |
| 快速扫描 | AI-Infra-Guard（Docker 平台） | 可选替代后端 |

### 7.2 我们需要自建的部分

以下能力是现有工具的完全空白，必须自建：

| 能力 | 空白程度 | 原因 |
|------|---------|------|
| 行为测试运行器 | 完全空白 | 没有工具能自动验证 Skill 触发后的执行行为 |
| 版本变更安全检测 | 完全空白 | 版本更新时的安全扫描对比不存在（OWASP AST07） |
| 版本变更行为检测 | 完全空白 | 版本更新后自动重跑行为测试不存在 |
| 测试用例自动生成 | 完全空白 | LLM 自动生成正/负例测试 prompt 不存在 |
| 开发脚手架 | 接近空白 | Anthropic 有 template/ 但不是 CLI 工具 |
| 触发准确性测试 | 接近空白 | skill-creator 有描述优化但不测试触发准确性 |

### 7.3 需要自建但可借鉴的部分

| 能力 | 借鉴来源 | 差异化 |
|------|---------|--------|
| 质量评分框架 | helloandy 8 维度 + qa-agent-testing 6 维度 | 从手工评分升级为自动化评分 |
| Snapshot Testing | DeepEval + syrupy | 适配 Skill 场景（语义等价而非逐字对比） |
| 测试用例格式 | skill-creator evals.json | 扩展支持负例、流程校验、安全检查 |

---

## 八、实施路径

### 8.1 优先级排序

| 优先级 | 切入点 | 原因 |
|--------|--------|------|
| P0（最高） | L2 行为测试运行器 | 完全空白、最有差异化价值、开发者痛感最强 |
| P1（高） | L1 质量检查 + L1 版本感知基础 | 零依赖、可快速上线、建立社区存在感 |
| P2（中） | L1 测试用例引导 + 脚手架 | 有价值但非核心差异化 |
| P3（中低） | L2 脚手架 + 热重载 | 开发体验优化 |
| P4（低） | L3 LLM 增强 | 依赖 API Key，用户门槛高，但差异化最强 |

### 8.2 三阶段实施路径

**第一阶段（0-3 个月）：L1 基础 + L2 行为测试运行器原型**

质量检查：
- 实现 L1 质量检查 SKILL.md（helloandy 8 维度 + 触发优化 + 输出规范）
- 注册进 x-cmd/skill 仓库

行为测试运行器：
- 实现 L2 核心原型：evals.json 解析 + Agent 调用 + 触发判定 + 输出判定
- 输出 JSON 报告 + 退出码，可集成 CI
- 可选：集成 Cisco Scanner CLI 作为测试前安全检查

版本感知：
- 实现 L1 基础版本感知（Git SHA 对比 + 变更摘要 + 回滚）
- 注册进 x-cmd/skill 仓库

产出：两个 L1 Skill（x-cmd 可分发）+ 一个 L2 行为测试运行器原型（GitHub Release）

**第二阶段（3-6 个月）：运行器完善 + 版本感知增强**

质量检查：
- L2 自动化评分集成 agent-skill-linter + Cisco Scanner CLI
- JSON 评分报告输出

行为测试运行器：
- 增加流程判定、快照对比
- CI 集成完善（GitHub Actions workflow template）
- Agent 运行时适配层扩展（OpenCode 支持）

版本感知：
- L2 自动 diff 解析 + 依赖差异检测
- 行为差异检测：版本更新前后调用行为测试运行器重跑
- 安全变更检测：版本更新前后对比 Cisco Scanner 结果

产出：完整的 L2 三模块工具链

**第三阶段（6-12 个月）：L3 智能增强 + 生态扩展**

质量检查：
- helloandy/qa-agent-testing 评分自动化

行为测试运行器：
- 语义等价判断（Agent-as-Judge）
- 自动测试用例生成
- 变形测试

版本感知：
- LLM 生成自然语言变更摘要
- 行为差异语义判断（与模块二 L3 共享）

生态侧：
- 向 x-cmd 社区提交 L1 的 PR
- 推动 SKILL.md 规范扩展（可选的 evals/ 目录）
- 建立测试用例社区贡献机制

产出：完整的 L1/L2/L3 三层单线工具链

### 8.3 风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|---------|
| 行为测试运行器依赖 Agent 运行时 | Claude Code/OpenCode CLI 接口可能变化或受限 | 先做适配层抽象，不硬编码特定 Agent 接口 |
| x-cmd 吸收 L1 能力 | GPL-3.0 下社区可能内置类似功能 | L2/L3 保持独立分发，L1 价值是"建立生态位" |
| LLM API 成本 | L3 的 LLM 调用有使用成本 | L3 完全可选，L1/L2 不依赖 LLM |
| 测试用例生态冷启动 | 没人写 evals.json | 从自测开始，为核心 Skill 写测试用例作为示范 |
| Cisco Scanner 停止维护或闭源 | 安全扫描子模块失效 | 适配层抽象，可切换到 AI-Infra-Guard 或其他工具 |

---

## 九、与 v3 的变更对照

| 维度 | v3（双线架构） | v4（单线架构） |
|------|--------------|--------------|
| 产品线 | 2 条（安全审计 + 开发工具） | 1 条（3 个模块） |
| 安全审计 | 独立产品线，自建 L1-L3 扫描能力 | 降级为横切子模块，调用 Cisco Scanner CLI |
| 版本感知 | 隶属于安全审计产品线 | 独立模块，且增加安全变更检测（OWASP AST07） |
| 行为测试运行器 | 隶属于开发工具产品线 | 独立模块，仍是核心切入点 |
| 质量检查 | 隶属于开发工具产品线 | 独立模块 |
| L1 分发 | 安全审计 L1 + 开发工具 L1 | 质量检查 L1 + 版本感知 L1 + 测试引导 L1 |
| 自建安全引擎 | YARA 规则 + 静态分析 | 不自建，调用 Cisco Scanner |
| 差异化叙事 | "安全审计 + 开发工具双线覆盖" | "从开发到运维全流程覆盖，别人只做安装前扫描" |

v4 的差异化叙事更强：安全审计赛道的 13 个竞争者都只做"安装前单点扫描"，我们通过版本感知模块覆盖"安装后更新变更检测"（OWASP AST07），配合行为测试运行器形成"开发→测试→运维"全流程覆盖。安全能力不自建但通过整合实现，用户得到的是 Cisco 7 引擎级别的扫描能力。

---

## 十、决策回顾

### 10.1 如何回应 feasibility 报告的四个缺口

| 缺口 | 严重度 | v4 对应能力 | 模块 | 实施阶段 |
|------|--------|-----------|------|---------|
| 版本管理缺失 | 8/10 | 版本感知（变更摘要+回滚+依赖校验+安全检测） | 版本感知 | 第一阶段 L1 + 第二阶段 L2 |
| 测试框架空白 | 7/10 | 行为测试运行器（触发判定+流程判定+输出判定+快照） | 行为测试运行器 | 第一阶段 L2 原型 + 第二阶段完善 |
| 安全审计缺位 | 9/10 | 安全扫描（调用 Cisco Scanner CLI，不自建） | 横切子模块 | 贯穿所有模块 |
| 跨平台不兼容 | 7/10 | 格式校验（agent-skill-linter 集成）+ 触发优化 | 质量检查 | 第一阶段 L1 + 第二阶段 L2 |

### 10.2 如何回应三个关键收敛决策

**决策一：个人开发者定位。** 三个模块都面向个人开发者。不做企业治理面板，不做团队协作集成。

**决策二：预警雷达定位。** 版本感知仍然是"变更感知"——不锁定版本，只告知变更。安全扫描通过调用 Cisco CLI 实现，不做深度红队测试。

**决策三：零侵入适配。** evals.json 是可选的——Skill 作者不写 evals.json 也能用质量检查 L1。所有模块对现有 Skill 零侵入——纯文档 Skill 也能被检查。

### 10.3 与前置报告的关系

- solutions v2 的四层架构（规范层、依赖感知层、安全预警层、版本感知层）仍然有效——它们是能力维度的分解
- v4 增加了用户维度的分解（开发阶段 → 测试阶段 → 运维阶段）
- v4 增加了安全审计竞争格局调研的决策结论
- 分层产品形态（L1/L2/L3）、与 x-cmd 的互补共生策略、零侵入适配原则、资源整合为主的实施策略——这些核心设计全部保留

---

## 十一、总结

v4 方案将 v3 的双线架构收敛为单线三模块（质量检查 + 行为测试运行器 + 版本感知），基于安全审计赛道竞争格局调研的决策：安全审计作为独立产品线砍掉，降级为横切子模块，通过调用 Cisco Scanner CLI 等外部工具实现安全能力。

最有价值的切入点不变：**行为测试运行器**——当前唯一的完全空白点（成熟度 2/10）。

v4 的差异化叙事更强：安全赛道的 13 个竞争者都只做"安装前单点扫描"，我们通过版本感知覆盖 OWASP AST07（更新偏移），配合行为测试运行器形成"开发→测试→运维"全流程覆盖。不自建安全扫描引擎，而是整合 Cisco 等成熟工具，用户得到的是更强的安全能力而非更弱的替代品。

实施路径不变：第一阶段（0-3 个月）交付 L1 基础 + L2 行为测试运行器原型，第二阶段（3-6 个月）完善 L2 三模块，第三阶段（6-12 个月）交付 L3 智能增强 + 生态扩展。

---

## 附录 A：本方案引用的前置调研报告

1. `research_report_agent_skill_infra_feasibility.md` —— 可行性分析与产品分析
2. `research_report_agent_skill_infra_solutions.md` —— 消费者侧解决方案（v2 修订版）
3. `research_report_skill_dev_test_practices.md` —— Skill 开发测试实践调研
4. `research_report_agent_skill_dependencies.md` —— 依赖管理现状调研

## 附录 B：安全审计赛道竞争格局调研（2026-04-29）

本次调研共识别 13 个直接竞争者。关键发现：

- **安装前扫描完全红海**：Cisco Scanner（7 引擎开源）、AI-Infra-Guard（3.6k stars）、Snyk（免费）、Repello/SkillScan.dev/AgentMagic（网页零门槛）已全面覆盖
- **企业级被占住**：Claude Code Security（官方内置）、Cisco（Apache 2.0）
- **唯一空白**：OWASP AST07 Update Drift（版本更新后的安全变更检测）
- **行业标准化**：OWASP AST10、中科院论文、Cisco Scanner v2.0（2026-04-10）

## 附录 C：关键参考工具

| 工具 | 类型 | URL | 本方案中的用途 |
|------|------|-----|--------------|
| Cisco Skill Scanner | 安全扫描 | Apache 2.0, v2.0.9 | 安全扫描子模块的默认后端引擎 |
| agent-skill-linter | 格式校验 | https://github.com/William-Yeh/agent-skill-linter | L2 直接集成 |
| AI-Infra-Guard | 安全扫描 | 朱雀实验室, v4.1.6 | 可选安全扫描替代后端 |
| skill-creator | Skill 开发+评估 | https://cn.x-cmd.com/skill/anthropics/skill-creator | evals.json 格式参考 |
| qa-agent-testing | QA 方法论 | https://skillkit.io/zh/skills/claude-code/qa-agent-testing | 6 维度评分、变形测试方法论 |
| helloandy | 质量评分 | https://helloandy.net/skill-linter-guide/ | 8 维度质量评分体系参考 |
| SkillsBench | 学术基准 | https://arxiv.org/abs/2602.12670 | Skill 效能评估方法论 |
| x-cmd/skill | Skill 仓库 | https://github.com/x-cmd/skill | L1 分发通道、互补共生 |
| DeepEval | LLM 评估 | https://deepeval.com/ | L3 语义等价判断参考 |
| darwin-skill | Skill 优化 | 本地安装 | 8 维度 rubric、test-prompts.json 格式参考 |
