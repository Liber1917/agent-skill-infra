# Agent Skill 依赖处理机制调研报告

## 调研背景

本次调研旨在梳理当前主流 Agent 平台和 Skill 生态中的依赖处理方式，为 Agent Skill 基础设施化项目提供参考依据。

---

## 第一组：典型 Skill 仓库结构分析

### 1. Vercel Skills（vercel-labs/skills）

**仓库地址**：https://github.com/vercel-labs/skills

**定位**：跨 Agent 的技能包管理器 CLI（`npx skills`），支持 Claude Code、Cursor、Windsurf、Codex、Goose、OpenCode 等 17+ 主流 Agent。

**SKILL.md 格式**：
```yaml
---
name: find-skills
description: Find and add skills to your project
author: Steven T. Campbell (@stevenforford)
id: 4f7e7c7a-c5d8-4c21-b6f1-1a9d1e2f3b4a
createdAt: 2023-10-05
---
```

**支持字段**：
| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 唯一标识符（小写、连字符） |
| `description` | 是 | 技能功能和适用场景 |
| `metadata.internal` | 否 | 设为 true 可隐藏技能 |
| `author` | 否 | 作者信息 |
| `id` | 否 | UUID 标识符 |

**依赖处理**：无 dependencies 字段，通过 `compatibility` 字段声明运行环境要求。

---

### 2. x-cmd Skill 仓库（x-cmd/skill）

**仓库地址**：https://github.com/x-cmd/skill

**定位**：x-cmd 的官方技能索引，数据统一托管在仓库中，受 Apache-2.0 许可证覆盖。

**目录结构**：
```
x-cmd/skill/
├── data/              # 技能数据（按工具名组织子目录）
│   ├── anthropics/
│   ├── openai/
│   └── x-cmd/         # 包含 aider, docker, ffmpeg 等 140+ 工具
├── index/             # 技能索引（MCP/skill）
└── SKILL.md          # 规范定义
```

**SKILL.md 格式**：采用 frontmatter + Markdown 结构，字段待进一步确认。

**依赖处理**：依赖声明内嵌在 Shell 脚本中，通过 `x-cmd` 内置函数或 `source` 声明对其他模块的依赖。

---

### 3. Agent Skills 官方规范（agentskills.io）

**规范地址**：https://agentskills.io/specification

**SKILL.md 完整字段定义**：

| 字段 | 必填性 | 约束/说明 |
|------|--------|-----------|
| `name` | 必填 | 1-64 字符，小写字母/数字/连字符，不能以连字符开头/结尾 |
| `description` | 必填 | 1-1024 字符，说明功能和适用场景 |
| `license` | 可选 | 技能许可证 |
| `compatibility` | 可选 | 1-500 字符，声明系统包、语言版本、网络访问等环境依赖 |
| `metadata` | 可选 | 字符串键值映射，可存放自定义依赖信息 |
| `allowed-tools` | 可选（实验性） | 空格分隔的预批准工具列表 |

**关于 dependencies 字段**：官方规范中**未定义**名为 `dependencies` 的字段。如需声明依赖，可使用：
1. `compatibility` 字段（环境要求）
2. `metadata` 字段（自定义依赖声明）

---

## 第二组：Claude Code / WorkBuddy / Cursor 的 Skill 加载机制

### 1. Claude Code Skills

**文档地址**：https://docs.anthropic.com/en/docs/claude-code/skills

**技能存放位置**：
| 位置 | 路径 | 作用域 |
|------|------|--------|
| 企业托管 | 通过 managed settings | 企业内所有用户 |
| 个人技能 | `~/.claude/skills/<skill-name>/SKILL.md` | 所有项目 |
| 项目级 | `.claude/skills/<skill-name>/SKILL.md` | 仅当前项目 |
| 插件级 | `<plugin>/skills/<skill-name>/SKILL.md` | 插件启用时 |

**加载机制**：
- 目录监视 + 热加载，修改即时生效
- 支持嵌套目录自动发现
- 技能描述始终加载，完整内容仅在调用时加载

**自动依赖安装**：❌ **不支持**。技能不自动安装 npm 包、Python 库等。用户需自行确保环境已具备。

---

### 2. WorkBuddy Skills

**Skills 定位**：WorkBuddy 的 Skills 是扩展 AI 能力的工作流封装模块，本质是 `.md` 文件。

**目录结构**：
```
~/.workbuddy/skills/
├── my-skill/
│   ├── SKILL.md        # 必需，核心定义
│   ├── scripts/        # 可选，代码模板
│   └── references/     # 可选，参考资料
```

**SKILL.md 格式**：
```yaml
---
name: gis-assistant
description: GIS 数据处理助手，处理坐标系转换、空间分析等任务
trigger: gis|地理|坐标|地图
---
```

**依赖处理**：
- 无显式 dependencies 字段
- 技能通过 `scripts/` 目录支持自定义脚本
- 脚本需自包含或明确说明依赖要求

---

### 3. Cursor（Cursorrules）

**Cursorrules 定位**：项目级配置文件，用于定义 AI 编码规范和行为。

**机制**：
- 在项目根目录创建 `.cursorrules` 文件
- 定义代码风格、架构偏好、编码规范
- 让 AI 在整个项目中保持一致的行为

**依赖概念**：❌ 无传统意义上的 Skill/依赖机制。Cursorrules 主要是指令规则，不支持包管理式依赖声明。

---

## 第三组：带脚本的 Skill 运行时依赖处理

### 1. Microsoft Agent Framework（最佳实践参考）

**文档地址**：https://learn.microsoft.com/en-us/agent-framework/agents/skills

**技能目录结构**：
```
expense-report/
├── SKILL.md
├── scripts/
│   └── validate.py
├── references/
│   └── POLICY_FAQ.md
└── assets/
    └── expense-report-template.md
```

**依赖处理方式（三种）**：

#### 方式一：依赖注入（DI）
```csharp
// C# 实现
.AddResource("distance-table", (IServiceProvider sp) => {
    return sp.GetRequiredService<ConversionService>().GetDistanceTable();
})
.AddScript("convert", (double value, double factor, IServiceProvider sp) => {
    return sp.GetRequiredService<ConversionService>().Convert(value, factor);
});
```

#### 方式二：运行时参数传递
```python
response = await agent.run(
    "How many kilometers is 26.2 miles?",
    function_invocation_kwargs={"precision": 2, "user_id": "alice"},
)
```

#### 方式三：渐进式加载（按需）
| 阶段 | Token 消耗 | 说明 |
|------|-----------|------|
| 1. Advertise | ~100 tokens/skill | 技能名称和描述 |
| 2. Load | < 5000 tokens | 完整 SKILL.md |
| 3. Read resources | 按需 | 补充文件 |
| 4. Run scripts | 按需 | 脚本执行 |

---

### 2. skill-tools 工具（SKILL.md 质量工具）

**仓库地址**：https://github.com/skill-tools/skill-tools

**Lint 规则**：
| 规则 | 说明 |
|------|------|
| Description uses specific verbs | 描述使用特定动词 |
| No hardcoded paths | 不含硬编码路径 |
| No embedded secrets | 不含嵌入密钥 |
| Instructions include examples | 指令包含示例 |

**未发现**专门针对 dependencies 字段的检查规则。

---

## 总结表格

| 平台/Skill | 依赖声明方式 | 自动安装 | 运行时依赖处理 |
|-----------|------------|---------|--------------|
| **Vercel Skills** | `compatibility` + `metadata` | ❌ | 无内置机制 |
| **x-cmd Skill** | Shell 脚本内嵌依赖 | ❌ | 通过 x-cmd 模块系统 |
| **Agent Skills 规范** | `compatibility` + `metadata` | ❌ | 无内置机制 |
| **Claude Code** | 无依赖声明字段 | ❌ | 用户自行配置环境 |
| **WorkBuddy** | 无依赖声明字段 | ❌ | scripts/ 目录需自包含 |
| **Cursor** | 无依赖机制 | ❌ | N/A |
| **Microsoft Agent Framework** | `IServiceProvider` DI | ❌ | 依赖注入 + 运行时参数 |

---

## 关键发现与结论

### 发现一：dependencies 字段非标准

当前主流 SKILL.md 规范中**未定义** `dependencies` 字段：
- Agent Skills 官方规范：用 `compatibility` 声明环境要求，用 `metadata` 存放自定义信息
- Vercel Skills：仅支持 `name`、`description`、`metadata.internal`
- Claude Code Skills：无依赖声明机制
- WorkBuddy Skills：无依赖声明机制

### 发现二：自动依赖安装是空白领域

所有调研的平台**均不支持**自动依赖安装。带脚本的 Skill 需要：
- 自包含脚本（无外部依赖）
- 或在 SKILL.md 中明确说明环境要求
- 由用户自行安装前置依赖

### 发现三：主流依赖处理方式

1. **环境声明式**（compatibility）：声明运行环境要求，不自动安装
2. **元数据扩展式**（metadata）：用自定义字段存放依赖信息
3. **渐进式加载**（Microsoft）：按需加载资源，控制 Token 消耗
4. **依赖注入式**（Microsoft DI）：运行时注入服务依赖

### 发现四：最佳实践参考

Microsoft Agent Framework 提供了相对完善的依赖处理方案：
- `IServiceProvider` 依赖注入
- `function_invocation_kwargs` 运行时参数传递
- 渐进式加载控制
- 脚本执行沙箱建议

---

## 对 Agent Skill 基础设施化项目的启示

### 建议一：扩展 SKILL.md 标准字段

在现有规范基础上，可新增：
```yaml
dependencies:
  runtime: ["python>=3.10", "requests>=2.31"]
  system: ["ffmpeg", "imagemagick"]
  install: "pip install -r requirements.txt"
```

### 建议二：分层渐进依赖管理

参考现有最佳实践，实现三层依赖处理：
1. **声明层**：`dependencies` 字段声明所需依赖
2. **推断层**：从脚本内容推断隐式依赖（如 import 语句）
3. **容错层**：提供降级方案，不阻断执行

### 建议三：集成 x-cmd 模块系统

x-cmd 的 POSIX Shell 模块化方案可作为依赖管理底座：
- 利用 `x-cmd pkg` 管理工具依赖
- 通过 `x-cmd` 内联模块隔离复杂依赖

---

## 参考来源

1. [Vercel Skills CLI - vercel-labs/skills](https://github.com/vercel-labs/skills)
2. [x-cmd Skill 仓库 - x-cmd/skill](https://github.com/x-cmd/skill)
3. [Agent Skills 官方规范 - agentskills.io](https://agentskills.io/specification)
4. [Claude Code Skills 文档](https://docs.anthropic.com/en/docs/claude-code/skills)
5. [Microsoft Agent Framework Skills](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
6. [skill-tools 工具库](https://github.com/skill-tools/skill-tools)
7. [skill-tools 规范文档](https://skills.sh/docs)
