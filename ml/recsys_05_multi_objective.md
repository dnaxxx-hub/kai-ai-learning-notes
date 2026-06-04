# 推荐系统 #5：多目标优化 — MMoE/PLE

> 2026-05-17
> 前置知识：深度学习推荐模型（#4）、多任务学习基础

## 为什么需要多目标

现实中推荐系统不是单一目标：
- 视频推荐：点击率 + 完播率 + 点赞率 + 分享率
- 电商推荐：点击率 + 转化率 + GMV + 好评率
- 信息流：点击率 + 停留时长 + 互动率

**单模型单目标**的问题：实际上这些目标相互关联但不完全一致。一个只优化点击率的模型会推荐"标题党"内容。

## 常见的多目标架构

### 1. Shared-Bottom（硬参数共享）

```
任务A → [输出] ┐
[底层共享层] → ┼ 任务B → [输出]
任务C → [输出] ┘
```

- 优点：参数共享、样本利用充分
- 缺点：如果任务差异太大（task conflict），共享层学不好

### 2. MMoE — Multi-gate Mixture-of-Experts

**核心思路**：不要强制共享同一层，让每个任务自己"选择"从哪几个专家（Experts）取信息。

```
              ┌→ 门控A → ┐
              │           │
[输入] → [专家1] → ┼→ 门控B → ┼→ [任务A输出]
         [专家2] → ┼        │
         [专家3] → ┘→ 门控C → ┘→ [任务B输出]
                          └→ [任务C输出]
```

- **专家（Expert）**：多个独立的子网络，每个学习不同的特征模式
- **门控（Gate）**：每个任务一个独立门控网络，学习加权组合专家输出
- **好处**：任务可以取不同权重的专家，避免 task conflict

### 3. PLE — Progressive Layered Extraction

MMoE 的进化版：

```
                    ┌→ 任务A门控 → 任务A专用专家
                    │
[输入] → [共享专家层] ┼→ 任务B门控 → 任务B专用专家
(Layer 1)     │     └→ 任务C门控 → 任务C专用专家
              │
              ↓
            [共享专家层]
            (Layer 2) → 最终输出
```

**核心改进**：
- 分层提取 — 底层共享，上层区分
- 每个任务有自己 **专用专家** + 共享专家
- 渐进式：每一层提取更抽象的特征

## 代码实现思路

```python
import torch
import torch.nn as nn

class MMoELayer(nn.Module):
    def __init__(self, input_dim, expert_dim, num_experts, num_tasks):
        super().__init__()
        self.experts = nn.ModuleList([
            nn.Sequential(
                nn.Linear(input_dim, expert_dim),
                nn.ReLU()
            ) for _ in range(num_experts)
        ])
        self.gates = nn.ModuleList([
            nn.Sequential(
                nn.Linear(input_dim, num_experts),
                nn.Softmax(dim=-1)
            ) for _ in range(num_tasks)
        ])

    def forward(self, x):
        expert_outs = [e(x) for e in self.experts]      # [B, E]
        expert_stack = torch.stack(expert_outs, dim=1)   # [B, n_experts, E]
        outputs = []
        for gate in self.gates:
            gate_weights = gate(x)                       # [B, n_experts]
            weighted = (gate_weights.unsqueeze(-1) * expert_stack).sum(dim=1)
            outputs.append(weighted)
        return outputs  # [task1_out, task2_out, ...]
```

## 训练技巧

1. **损失权重（Loss Weighting）**：
   - 固定权重：α₁L₁ + α₂L₂ + ...
   - 不确定性加权（Uncertainty Weighting）：把方差作为可学习参数
   - GradNorm：自动调整权重使梯度均衡

2. **不平衡数据**：
   - 转化率可能只有1%，但点击率20%
   - 解决方案：梯度裁剪、小批量采样平衡

3. **冲突检测**：
   - 计算梯度余弦相似度，负值表示冲突
   - 冲突严重时 → 增加专家数量或分层

## 实际应用中的经验

| 场景 | 推荐架构 | 目标数 | 关键点 |
|:----|:--------|:-----:|:-----:|
| YouTube 推荐 | MMoE | 3-5 | 加权损失+留存率 |
| TikTok 推荐 | PLE | 5-10 | 分层专家+实时训练 |
| 淘宝搜索 | ESMM | 2 | 点击→转化级联 |

## 与量化交易的潜在联系

有意思的类比：多目标优化 = 多因子评分

```
推荐系统的多目标             量化交易的多因子
──────────────────────────────────────────
点击率                      动量因子（短期收益）
停留时长                    均值回复因子（回归）
互动率                      波动率因子（风险）
转化率                      基本面因子（价值）
MMoE 门控 = 动态权重融合 = score = Σ(wi × fi)
```

多目标优化的门控机制，可以迁移到量化交易的多因子动态权重上。

## 参考

- MMoE: "Modeling Task Relationships in Multi-task Learning with Multi-gate Mixture-of-Experts" (KDD 2018)
- PLE: "Progressive Layered Extraction (PLE): A Novel Multi-Task Learning Model" (RecSys 2020)
- ESMM: "Entire Space Multi-Task Model" (WWW 2018)
