# AI Agent Skill 作者开发与测试流程调研报告

## Executive Summary

Skill 作者当前的开发流程以手工编写 SKILL.md 为主，缺乏系统化的开发工具链。测试方面几乎完全依赖人工试错——作者写完 Skill 后反复向 Agent 输入不同提示词来验证触发和执行效果，没有标准化的自动化测试框架。生态中已出现三类辅助工具：格式校验工具（agent-skill-linter、skill-linter、在线验证器）、评估框架（skill-creator 的 eval 流程、qa-agent-testing）、基准测试（SkillsBench），但三者之间割裂、覆盖面窄、使用门槛高。现有生态成熟度评估为 **3/10**，关键空白在于：缺乏从开发到测试到发布的端到端工具链，尤其缺少"写完即测"的快速反馈机制。

---

## 第一组：Skill 开发流程

### 1.1 官方推荐的开发流程

Agent Skills 的官方规范由 [agentskills.io](https://agentskills.io/specification) 定义，核心要求非常简单：一个 Skill 就是一个包含 SKILL.md 文件的文件夹。SKILL.md 采用 YAML frontmatter + Markdown 正文的格式，必需字段仅有 `name` 和 `description` 两个字段。

官方规范强调三个设计原则：

- **渐进式披露**：元数据层（~100 tokens，始终加载）→ 指令层（< 5000 tokens，触发时加载）→ 资源层（按需加载），SKILL.md 正文不超过 500 行
- **description 即路由**：description 是 Skill 的主要触发机制，需包含触发关键词和使用场景
- **结构化目录**：`scripts/`（可执行代码）、`references/`（参考文档）、`assets/`（模板资源）三个可选子目录

[Anthropic 官方 Skills 仓库](https://github.com/anthropics/skills) 提供了 `template/` 目录作为脚手架，以及 `spec/` 目录中的规范定义，但没有提供开发工具、CLI 脚手架或自动化测试工具。仓库本质是一个示例集合（文档处理、创意设计、开发工具等 17 个 Skills），而非开发工具箱。

### 1.2 社区开发实践与痛点

综合多个中文技术社区的文章（[知乎](https://zhuanlan.zhihu.com/p/2019727701573902968)、[CSDN](https://blog.csdn.net/weixin_55154866/article/details/157699886)、[火山引擎](https://developer.volcengine.com/articles/7602118327812489266)、[fly63](https://fly63.com/article/detial/13673)），Skill 作者面临的核心痛点如下：

**痛点 1：触发不准（最普遍的痛点）**

description 写得太模糊导致 Skill 永远触发不了，这是 90% 的新手都会犯的错误。社区经验是 description 中必须包含具体的触发关键词列表，加上"必须使用本 Skill"的强制措辞，才能将触发概率提升到可接受水平。触发问题的根本原因是：Skill 的触发机制完全依赖 LLM 对 description 文本的语义理解，没有任何确定性的路由逻辑。

**痛点 2：没有容错，一出错就崩溃**

Skill 的指令如果写得过于刚性（"必须先读 a.md，再读 b.md"），一旦中间步骤失败整个流程就断了。社区建议每个可能出错的步骤都加上容错处理规则，但这是手工活——没有工具帮你检查"你的 Skill 有没有覆盖所有错误场景"。

**痛点 3：Token 膨胀与内容过长**

很多作者把所有规则都堆在 SKILL.md 正文里，导致上下文窗口浪费。虽然渐进式披露是官方推荐的做法，但没有任何工具自动帮你把过长内容拆分到 references/ 目录。

**痛点 4：输出不一致**

没有输出规范时，同一个 Skill 在不同会话中可能产出格式完全不同的结果。社区建议明确规定输出格式并给出示例，但这同样靠手工。

### 1.3 x-cmd/skill 仓库

[x-cmd/skill 仓库](https://github.com/x-cmd/skill/)（[Codeberg 镜像](https://codeberg.org/x-cmd/skill)）是社区策展的 Skills 集合，提供 `x skill add` 一键安装。仓库本身没有开发工具或测试工具，但有 [skill-creator](https://cn.x-cmd.com/skill/anthropics/skill-creator)（详见第二组分析）和 200+ 社区 Skills 可参考。`index.yml` 中无依赖字段和测试字段，安装过程就是文件复制。

---

## 第二组：开发类 Skill 的内部流程

### 2.1 skill-creator：目前最完善的 Skill 开发+评估工具

[x-cmd skill-creator](https://cn.x-cmd.com/skill/anthropics/skill-creator)（源自 Anthropic 官方）是目前发现的**功能最完整的 Skill 开发工具**，覆盖了创建、评估、迭代三个阶段：

**创建阶段**：捕获意图 → 访谈研究（边缘情况、依赖项）→ 编写 SKILL.md

**评估阶段**（五步核心循环）：
1. 并行运行带 Skill 和不带 Skill 的对比测试
2. 起草可客观验证的断言（assertions）
3. 捕获计时数据（tokens、耗时）
4. 评分 + 聚合基准 + 启动查看器（HTML 报告）
5. 迭代改进 → 重跑所有测试用例

**高级功能**：
- **盲对比**：将两个版本的输出交给独立 Agent，不告知版本号，让其判断质量
- **描述优化**：生成 20 个触发评估查询（8-10 个应触发 + 8-10 个不应触发），运行优化循环，按测试集分数选择最佳 description
- **迭代终止条件**：用户满意 / 反馈全为空 / 无显著进展

评估数据存储在 `evals/evals.json` 中，格式为 `{skill_name, evals: [{id, prompt, expected_output, files}]}`。每次迭代保存到独立目录 `<skill-name>-workspace/iteration-N/`，支持跨迭代对比。

**关键局限**：
- 需要 Claude Code 环境才能完整运行（子 Agent、浏览器查看器）
- 在 claude.ai 上跳过基准测试和描述优化
- 没有与 CI/CD 的原生集成
- 测试用例数量少（2-3 个），覆盖面有限

### 2.2 Superpowers：TDD 工作流对 Skill 开发的启发

[Superpowers](https://github.com/obra/superpowers)（11w+ stars）是一套完整的软件开发工作流框架，核心流程为 brainstorming → plan → TDD → subagent-driven development → review。其 TDD 流程的关键步骤：

1. **brainstorming**：通过一问一答精炼设计，探索多种方案
2. **writing-plans**：保存到 docs/plans/
3. **test-driven-development**：先写测试（RED），再写实现（GREEN），然后重构
4. **subagent-driven-development**：并行子 Agent 执行
5. **review**：代码审查

**对 Skill 开发的适用性**：Superpowers 的 TDD 是面向代码的，不是面向自然语言 Skill 的。SKILL.md 是自然语言指令而非代码，"先写测试再写 Skill"的范式需要重新定义"测试"的含义——在 Skill 场景下，"测试"不是 assert 输出等于预期值，而是"Agent 在给定提示下是否正确触发并产生符合规范的输出"。这个差异意味着传统 TDD 工具不能直接套用。

### 2.3 GSD（get-shit-done）：测试子 Skill

[GSD](https://github.com/gsd-build/get-shit-done) 提供 [gsd-add-tests](https://www.claudepluginhub.com/commands/glittercowboy-get-shit-done/commands/gsd/add-tests) 子 Skill，功能是"为指定阶段生成单元测试和 E2E 测试"，基于 SUMMARY.md、CONTEXT.md 和 VERIFICATION.md 规格自动生成。还有 [gsd-verify-work](https://gsd.build/) 用于 UAT 验证。

但这些测试同样面向代码，不适用于 SKILL.md 的自然语言测试。GSD 的价值更多在"spec-driven"的开发流程（规格驱动开发），这个理念可以迁移到 Skill 开发——先定义 Skill 的规格（触发条件、预期行为、输出格式），再编写 SKILL.md。

### 2.4 SKILL.md 格式校验工具

目前发现了三个格式校验工具：

**[William-Yeh/agent-skill-linter](https://github.com/William-Yeh/agent-skill-linter)**（v0.11.0，Apache-2.0）：

最全面的 Skill 校验工具，17 条自动检查规则覆盖：
- SKILL.md 规范合规性（通过 skills-ref 检查）
- LICENSE 文件存在性与年份
- Frontmatter 元数据完整性（author 字段）
- README 中的徽章、CI 配置、安装/使用章节
- 渐进式披露（嵌入式模板转移至 references/）
- Python 项目调用一致性
- 技能隔离性（根目录不得有非技能制品）

支持 CLI 独立运行（`./scripts/skill-lint.py check ./my-skill`），输出 JSON 格式可集成 CI，退出码 0/1 可做门禁。部分问题支持 `--fix` 自动修复。

**[Smithery skill-linter](https://smithery.ai/skills/majesticlabs-dev/skill-linter)**（majesticlabs-dev）：

14 项验证规则，侧重 agentskills.io 规范合规：
- 目录结构、命名规范、frontmatter 字段
- 内容质量：禁止 ASCII 艺术、人设声明、营销文案
- 描述路由质量评估（好/尚可/差/反模式四级）
- 支持 CI 集成的批量验证

**[LLMVLab 在线验证器](https://www.llmvlab.com/tools/agent-skill-validator)**：

免费在线工具，粘贴 SKILL.md 内容即可验证规范合规性，基于 skills specification 和 skills-ref 规则。适合快速检查，但不支持自动化集成。

**[helloandy 质量评分体系](https://helloandy.net/skill-linter-guide/)**：

提出了 8 维度质量评分体系（技术维度 5 分 + 输出质量 3 分），检查项包括：触发精度、输出完整性、铁律具体性、错误恢复覆盖、示例质量、简洁性、一致性、边缘情况处理。这是目前发现的**最系统的 Skill 质量评估方法论**，但它是一个评分框架而非自动化工具。

### 2.5 官方验证工具

[agentskills.io](https://agentskills.io/specification) 提供 `skills-ref validate ./my-skill` 命令用于验证 Skill 是否符合规范，但仅检查 frontmatter 和命名约定，不涉及内容质量或行为正确性。

---

## 第三组：Skill 测试方法论

### 3.1 SkillsBench：首个系统化的 Skill 效能基准

[SkillsBench](https://arxiv.org/abs/2602.12670)（arXiv:2602.12670，2026年2月）是首个系统评估 Agent Skill 效果的学术基准，核心发现如下：

| 指标 | 数据 |
|------|------|
| 任务数量 | 86 个任务，11 个领域 |
| 测试配置 | 7 种 agent-model 配置 |
| 总测试量 | 7,308 条轨迹 |
| 评估方式 | 每个任务配备确定性验证器 |

**关键发现**：

- 精选 Skills 使平均通过率提升 **16.2 个百分点**
- 效果因领域差异极大：医疗 +51.9pp，软件工程仅 +4.5pp
- 84 个任务中有 **16 个显示负面影响**（Skill 反而降低了表现）
- **自生成 Skills 没有带来任何收益**——模型无法可靠地编写自己需要的技能知识
- 包含 2-3 个模块的聚焦型 Skills 优于冗长的综合文档
- 较小的模型配合 Skills 可以匹敌没有 Skills 的较大模型

SkillsBench 的方法论对 Skill 测试的启示是：评估 Skill 需要（1）有明确的任务定义，（2）有确定性的验证器（而非 LLM 评估），（3）需要与无 Skill 基线对比，（4）需要跨多次运行评估稳定性。

### 3.2 LLM-as-Judge / Agent-as-Judge 评估范式

[Agent-as-a-Judge](https://arxiv.org/abs/2410.10934)（arXiv:2410.10934）提出用 Agent 评估 Agent，显著优于 LLM-as-Judge，可靠性接近人类评估基线。[LLMs-as-Judges 综述](https://arxiv.org/abs/2412.05579)系统梳理了从功能、方法、应用、元评估到局限性的全链路。

在 Skill 测试场景中的适用性：LLM-as-Judge 适合评估 Skill 的输出质量（格式、完整性、准确性），但不适合评估触发正确性（需要确定性的规则匹配而非语义判断）。Agent-as-Judge 更适合复杂的多步 Skill 评估，因为 Agent 可以模拟用户交互并检查中间状态。

### 3.3 qa-agent-testing：最系统的 Agent QA 框架

[qa-agent-testing](https://skillkit.io/zh/skills/claude-code/qa-agent-testing)（SkillKit）是当前发现的**最系统的 Agent 测试 Skill**，核心设计：

**7 步 QA 工作流**：
1. 定义被测角色（PUT）：明确范围、排除项、安全边界
2. 定义 10 个代表性任务（必须通过）
3. 定义 5 个拒绝边界案例（必须拒绝并重定向）
4. 定义输出契约：格式、语气、结构、引用
5. 运行测试套件：确定性控制 + 工具追踪
6. 6 维度评分：任务成功率、安全/策略、可靠性、延迟/成本、可调试性、事实基础
7. 记录基线：回归时对比，阈值未达标则阻止合并

**高级测试方法**：
- **变形测试**：保留语义的小改动输入，验证输出不变性
- **提示注入测试**：将工具输出/用户文档视为不可信
- **工具故障注入**：模拟超时、重试、部分数据
- **差异测试**：跨模型/配置版本比较行为

**评分标准**：每任务满分 18 分（6 维度 × 0-3 分），通过标准 ≥ 12/18。

这个框架的方法论非常完整，但它本质上是一个**方法论文档 + 模板**，不是一个可自动执行的测试运行器。作者仍需手动创建测试用例、手动运行、手动评分。

### 3.4 DeepEval：LLM 评估框架

[DeepEval](https://deepeval.com/) 是一个开源 LLM 评估框架，类似 Pytest 但专门用于 LLM 输出测试，提供 50+ 即插即用的评估指标。在 Skill 测试场景中可以用于：

- 评估 Skill 输出的 faithfulness（忠实度）、relevancy（相关性）
- 检测幻觉
- 批量运行评估并生成报告

但 DeepEval 是通用 LLM 评估框架，不针对 Skill 特有的问题（触发准确性、渐进式披露、多步流程执行），需要自行编写适配层。

### 3.5 Snapshot Testing 的适用性

Snapshot Testing（如 syrupy）在传统软件测试中用于捕获组件的渲染输出并与之前保存的快照对比。在 Skill 场景中，可以用于：

- 对同一输入，运行 Skill 后捕获 Agent 的完整输出（工具调用序列 + 最终输出）
- 后续修改 SKILL.md 后重跑，与快照对比，检测行为变化

但这存在一个根本问题：LLM 输出具有非确定性，同一输入在不同运行中可能产生不同但都正确的结果。因此 Snapshot Testing 需要与语义等价判断结合使用——不是逐字对比，而是判断两次输出在语义上是否等价。这又回到了 LLM-as-Judge 的需求。

---

## 现有工具生态全景

| 工具 | 类型 | 覆盖阶段 | 核心能力 | 关键局限 |
|------|------|----------|----------|----------|
| agentskills.io `skills-ref` | 官方验证器 | 发布 | frontmatter + 命名规范 | 仅格式检查，不测行为 |
| agent-skill-linter | 社区校验工具 | 发布 | 17 条规则，CI 集成 | 仅格式+结构，不测行为 |
| Smithery skill-linter | 社区校验工具 | 发布 | 14 条规则，CI 集成 | 仅规范合规，不测行为 |
| LLMVLab Validator | 在线验证器 | 开发 | 粘贴即验 | 仅规范合规，不可自动化 |
| skill-creator eval | 开发评估工具 | 开发+测试 | 对比测试、断言、评分、迭代 | 需 Claude Code，2-3 测试用例，无 CI |
| qa-agent-testing | QA 方法论 | 测试 | 6维评分、变形测试、故障注入 | 方法论文档，非自动运行器 |
| SkillsBench | 学术基准 | 评估 | 86 任务、确定性验证器 | 研究工具，非开发工具 |
| DeepEval | LLM 评估框架 | 测试 | 50+ 评估指标 | 通用框架，非 Skill 特化 |
| Superpowers TDD | 开发工作流 | 开发+测试 | spec-first TDD | 面向代码，非自然语言 Skill |

---

## 生态成熟度评估：3/10

| 维度 | 评分 | 理由 |
|------|------|------|
| 开发工具 | 2/10 | 无脚手架、无模板生成器、无实时反馈；skill-creator 是唯一有开发引导的工具 |
| 格式校验 | 6/10 | 三个工具覆盖规范合规，agent-skill-linter 质量最高，但都不检查内容质量和行为正确性 |
| 行为测试 | 2/10 | skill-creator eval 是唯一有自动化测试流程的工具，但覆盖面窄、无 CI 集成 |
| 质量评估 | 3/10 | helloandy 8 维度评分体系最系统，但无自动化实现；qa-agent-testing 方法论完整但非可执行工具 |
| 发布流程 | 4/10 | ClawHub 提供市场，但无质量门禁；agent-skill-linter 可做 CI 门禁但覆盖有限 |
| 文档与教程 | 5/10 | 官方规范 + 社区教程较丰富，但缺少"最佳实践"的共识 |

---

## 关键空白点

1. **"写完即测"的快速反馈机制缺失**：作者写完 SKILL.md 后，必须手动在 Agent 中反复输入不同提示来验证触发和执行效果，没有"运行测试套件"的能力。skill-creator 的 eval 流程是目前最接近的方案，但使用门槛高、测试用例少。

2. **行为正确性测试为零**：所有现有工具都只检查格式合规性（frontmatter 有没有、name 对不对），没有一个工具能自动验证"这个 Skill 在被触发后是否按预期执行"——这是 Skill 测试的核心问题。

3. **触发准确性无自动化验证**：触发不准是开发者反馈最多的痛点，但验证触发准确性需要构造大量正例和负例提示词并观察 Agent 是否正确选择 Skill，目前只有 skill-creator 的描述优化功能提供部分支持。

4. **回归测试缺失**：修改 SKILL.md 后无法自动检测行为变化，没有 Snapshot Testing 或语义等价检测。qa-agent-testing 的回归协议是方法论文档，非可执行工具。

5. **工具间割裂**：格式校验（linter）、行为测试（eval）、质量评分（8维度）三个维度由不同工具覆盖，没有统一的工具链串联。

6. **CI/CD 集成不完整**：agent-skill-linter 支持 JSON 输出和退出码，可以做格式门禁，但行为测试无法集成 CI。

---

## 建议：统一开发测试工具的最有价值切入点

基于以上分析，如果要做"统一开发测试工具"，最有价值的切入点是：

### 首选：Skill 行为测试运行器（Skill Test Runner）

**为什么是它而非格式校验**：格式校验已经有 agent-skill-linter 做得很好（17 条规则、CI 集成、自动修复），再做一个边际价值低。行为测试是完全的空白——目前没有任何工具能自动验证"Skill 被触发后是否按预期执行"。

**核心能力设计**：

1. **测试用例定义**：采用 skill-creator 的 `evals/evals.json` 格式（已有社区基础），扩展支持正例（应触发）和负例（不应触发）
2. **自动运行**：给定 Skill 路径 + 测试套件，自动启动 Agent 执行每个测试用例，捕获完整轨迹（工具调用序列 + 最终输出）
3. **多维度判定**：
   - 触发判定：Skill 是否被正确激活/正确跳过
   - 流程判定：Agent 是否按 SKILL.md 中定义的流程执行
   - 输出判定：结果是否符合输出规范（格式 + 内容）
   - 安全判定：是否触发了不允许的操作
4. **快照 + 语义对比**：首次运行保存快照，后续运行与快照做语义等价对比（调用 LLM-as-Judge），检测行为退化
5. **CI 集成**：输出 JSON + 退出码，可直接嵌入 GitHub Actions

**与现有生态的整合策略**：
- 格式校验：直接调用 agent-skill-linter（不做重复造轮子）
- 测试用例格式：兼容 skill-creator 的 evals.json
- 质量评分：参考 helloandy 的 8 维度体系，实现自动化评分
- 方法论：融合 qa-agent-testing 的 6 维度评分和变形测试思路

### 次选：Skill 开发脚手架 + 热重载

如果行为测试运行器的技术难度过高（需要深度集成 Agent 运行时），次优选择是做一个轻量的开发脚手架：

1. `skill init <name>`：基于模板生成 Skill 目录结构
2. `skill dev`：监听 SKILL.md 变更，自动推送到 Agent 技能目录
3. `skill lint`：集成 agent-skill-linter + 内容质量检查
4. `skill test`：运行触发测试（给定一组提示词，检查是否正确触发）

这个方案的技术风险更低，能更快交付价值，但覆盖面也窄——只解决开发效率问题，不解决行为正确性验证。

---

## References

1. [Agent Skills Specification - agentskills.io](https://agentskills.io/specification)
2. [Anthropic Official Skills Repository](https://github.com/anthropics/skills)
3. [William-Yeh/agent-skill-linter - GitHub](https://github.com/William-Yeh/agent-skill-linter)
4. [skill-linter - Smithery](https://smithery.ai/skills/majesticlabs-dev/skill-linter)
5. [Free Agent Skill Validator - LLMVLab](https://www.llmvlab.com/tools/agent-skill-validator)
6. [How to Lint SKILL.md Files - helloandy](https://helloandy.net/skill-linter-guide/)
7. [skill-creator - x-cmd skill](https://cn.x-cmd.com/skill/anthropics/skill-creator)
8. [Superpowers - GitHub](https://github.com/obra/superpowers)
9. [GSD (Get Shit Done) - GitHub](https://github.com/gsd-build/get-shit-done/)
10. [SkillsBench: Benchmarking How Well Agent Skills Work - arXiv:2602.12670](https://arxiv.org/abs/2602.12670)
11. [Agent-as-a-Judge: Evaluate Agents with Agents - arXiv:2410.10934](https://arxiv.org/abs/2410.10934)
12. [LLMs-as-Judges: A Comprehensive Survey - arXiv:2412.05579](https://arxiv.org/abs/2412.05579)
13. [qa-agent-testing - SkillKit](https://skillkit.io/zh/skills/claude-code/qa-agent-testing)
14. [DeepEval - LLM Evaluation Framework](https://deepeval.com/)
15. [x-cmd/skill Repository - GitHub](https://github.com/x-cmd/skill/)
16. [生产级Skill开发指南：从踩坑到最佳实践 - fly63](https://fly63.com/article/detial/13673)
17. [从"能用"到"会用"｜如何写好一个 Skill - 火山引擎](https://developer.volcengine.com/articles/7602118327812489266)
18. [SkillsBench Official Site](https://www.skillsbench.ai/)
19. [ClawHub - OpenClaw Skills Marketplace](https://docs.openclaw.ai/zh-CN/tools/clawhub)
20. [5种来自谷歌的Agent Skill设计模式 - 掘金](https://juejin.cn/post/7625898031914139657)
