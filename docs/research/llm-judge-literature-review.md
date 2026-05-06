# LLM-as-Judge 评分系统：文献综述与实验验证

> 研究分支: `research/llm-judge-eval`
> 日期: 2026-05-06

## 论文清单

| # | 论文 | 发表 | 核心发现 |
|---|------|------|---------|
| 1 | Li et al. *Evaluating Scoring Bias in LLM-as-a-Judge* | arXiv 2506.22316 (2025) | 3 种评分偏差 + 缓解策略 |
| 2 | Xu et al. *Position Bias in Rubric-Based LLM-as-a-Judge* | arXiv 2602.02219 (2026) | 维度顺序影响评分，排列校准有效 |
| 3 | Lee et al. *How to Correctly Report LLM-as-a-Judge Evaluations* | arXiv 2511.21140 (2025) | 偏差修正公式 + CI + 自适应校准 |
| 4 | EMNLP *Analyzing Uncertainty of LLM-as-a-Judge* | EMNLP 2025 | 9 种 conformal prediction 方法 |
| 5 | Li et al. *CalibraEval* | ACL 2025 | 分布校准 + 非参数保序算法 |
| 6 | OpenReview *Pairwise or Pointwise?* | OpenReview 2025 | 绝对评分比 pairwise 更稳健 |

---

## 1. Li et al. — Scoring Bias（核心参考）

### 三种评分偏差

| 偏差类型 | 定义 | 根因 |
|---------|------|------|
| **Rubric Order Bias** | 评分标准顺序影响评分 | 前几条标准被过度重视 |
| **Score ID Bias** | 分数标签本身影响评分 | 数字 vs 字母 vs 罗马数字 |
| **Reference Answer Bias** | 参考答案的分数"拉偏"评分 | 锚定效应 |

### 关键发现（直接影响 agent-skill-infra）

1. **温度=0 必须用于偏差测试**。所有实验在 temperature=0 下进行。
2. **不要随机排列评分标准**——这会普遍降低准确性。
3. **尝试降序排列**（最好→最差）可能提升准确性。
4. **满分参考答案（Ref-5）是唯一安全的外部参考**——中低分参考会拉偏分数。
5. **大模型更稳健**：GPT-4o 的稳定性远优于 8B/24B 模型。
6. **偏差有时反而提高准确性**——需要同时测量稳定性和准确性，不能只看分数是否变化。

### 可操作的 prompt 设计原则

```
✅ DO:
- 使用最大的可用模型
- 包含满分参考答案
- 尝试降序排列评分标准
- 尝试字母/罗马数字替代阿拉伯数字

❌ DON'T:
- 随机排列评分标准
- 使用中低分参考答案
- 给多个维度相同的数字锚点（这正是 57% 集群的根因）
```

---

## 2. Xu et al. — Position Bias

### 核心发现

评分标准在 prompt 中的**位置决定其权重**。排列校准（balanced permutation + aggregation）可以消除此偏差。

### 方法

对同一技能运行 3 次评估，每次评分标准排列不同，取均值。

### 对 agent-skill-infra 的启示

我们 8 个维度目前固定排列：trigger_precision → output_completeness → ... → edge_cases。应实现维度随机排列。

---

## 3. UW-Madison — Calibration Framework

### 偏差修正公式

```
θ = (p + q₀ - 1) / (q₀ + q₁ - 1)
```

其中 p = 测试集通过率，q₀ = 特异性，q₁ = 灵敏度。

### 可安装的 Python 包

```bash
pip install "git+https://github.com/UW-Madison-Lee-Lab/LLM-judge-reporting.git"
```

提供三个函数：
- `point_estimator(p, q0, q1)` — 偏差修正后的点估计
- `confidence_interval(p, q0, q1, n, m0, m1, alpha=0.05)` — 95% CI
- `allocate_calibration_sample(m, p, ...)` — 自适应校准分配

### 对 agent-skill-infra 的启示

可以将此框架作为可选依赖集成到 `skill-quality` 中。当用户提供人类标注的校准集时，报告偏差修正后的分数 + CI。

---

## 4. 我们的实验验证

### 实验 1：温度校准

| 温度 | nuwa R1/R2/R3 | σ |
|------|-------------|----|
| 0.3 (默认) | 38%/50%/51% | ~7% |
| 0.0 | 41%/42%/41% | ~0.5% |
| **0.1** | **42%/42%/42%** | **~0.5%** ✅ |

结论：温度 0.1 在确定性和自然区间之间取得最佳平衡。

### 实验 2：Score ID 偏差

| 组 | prompt | mode 浓度 | 57% 集群 |
|------|--------|---------|---------|
| A（对照）| 含 `0.5=adequate` 数字锚 | 34% at 57% | 10/29 |
| B（实验）| 移除所有数字锚 | 19% at 74% | **1/27** ✅ |

结论：移除数字锚点将 57% 集群从 34% 降到 4%，验证了 Score ID Bias。

### 实验 3：大规模统计

n=27 OpenClaw 内置 skill，temperature=0.1 + 无锚 prompt：
- 均值 68.1%，标准差 8.4，14 个唯一分值
- 分布从 41% 到 76%，覆盖 35 分全距

---

## 5. 下一步

| 优先级 | 改进 | 论文支撑 |
|--------|------|---------|
| P0 | 维度随机排列（3 次均值） | Xu et al. + Li et al. |
| P1 | 集成 UW-Madison 校准框架 | Lee et al. |
| P2 | 测试降序排列评分标准 | Li et al. |
| P3 | 测试非数字评分标识（A/B/C...）| Li et al. |
