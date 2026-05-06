# agent-skill-infra 下一步优化路线

## 已完成（今天）

| # | 项目 | 验证 |
|---|------|------|
| 1 | temperature=0.1 | σ 从 7% → 0.5% |
| 2 | 移除数字锚点 | 57% 集群 34% → 4% |
| 3 | 30-skill 统计基准 | n=27, μ=68.1, σ=8.4 |
| 4 | 6 篇论文文献综述 | 发布于 research/llm-judge-eval |
| 5 | 向 ClawHub 推介 | openclaw/clawhub#2042 |
| 6 | 修复 trigger double-counting | 评分正确 8 维度等权 |

## 下一步优化（优先级排序）

| 优先级 | 项目 | 工作量 | 收益 |
|--------|------|--------|------|
| **P0** | 合并研究分支到 main | 5min | 文献可引用 |
| **P0** | 维度随机排列（3次均值） | 15min | Xu et al. 验证：消除 position bias |
| **P1** | 基于 27-skill 数据设定三态阈值 | 10min | pass/quarantine/reject 有数据支撑 |
| **P1** | 关闭 benchmark issues 清理仓库 | 5min | 仓库整洁 |
| **P2** | 集成 UW-Madison 校准 pip 包 | 30min | 偏差修正 + CI |
| **P2** | 测试降序评分标准排列 | 15min | Li et al. 发现可能提升准确性 |
| **P3** | 扩大样本至 100+ skill | 批量 CI | 统计显著性 |

按这个顺序执行？