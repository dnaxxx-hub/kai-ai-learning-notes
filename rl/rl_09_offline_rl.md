# 强化学习 #9：离线强化学习（Offline RL）

> **核心思想**：从固定的、预先收集的数据集中学习最优策略，不再与环境交互。

---

## 1. 动机：为什么需要离线 RL？

### 在线 RL 的痛点
- **交互成本高**：机器人（摔一次维修费上万）、自动驾驶（出事故不可逆）、医疗（试错会死人）
- **数据效率低**：在线 RL 需要数百万步交互，在真实系统中不现实
- **安全风险**：探索阶段可能采取危险动作

### 离线 RL 的愿景
- 利用已有的历史数据（日志、演示、其他策略收集的数据）
- 像监督学习一样"一通训练后部署"
- 适用于：推荐系统、医疗治疗策略、自动驾驶、机器人技能学习

### 核心挑战
离线 RL ≠ 在固定数据集上跑 Q-learning。**直接套用在线算法会失败**。

---

## 2. 分布外动作问题（OOD Actions / Extrapolation Error）

### 问题根源
Q-learning 在更新时依赖 $\max_a Q(s', a)$，但在离线数据集中，**不是所有 $(s', a)$ 组合都出现过**。

```
数据集中的动作: a1, a2（专家演示）
未出现的动作:   a3, a4, a5（从未被采集过）
```

- Q 网络会**给未见过的动作赋予荒谬的高 Q 值**
- Policy 被"骗"去选择这些 OOD 动作
- 形成恶性循环：策略选 OOD → Q 进一步高估 → 策略更依赖 OOD

### 数学直觉
Bellman 误差只覆盖数据集中出现的 $(s,a)$ 对。对于未出现的动作，Q 函数的梯度是**不受约束的**，模型自由发挥→过估计。

### 形象理解
> 就像只见过猫和狗，但让模型"最大化奖励"→ 模型说"选独角兽，奖励最高"——它从没见过独角兽，所以可以随意编造 Q 值。

---

## 3. 三大约束方法路径

目标：防止策略选择 OOD 动作，让 Q 值估计保持保守。

### 3.1 策略约束（Policy Constraint）

**思路**：强制学习策略 $\pi(a|s)$ 与数据集的行为策略 $\pi_\beta(a|s)$ 分布接近。

| 方法 | 约束方式 | 特点 |
|------|----------|------|
| **BCQ** (Batch Constrained Q-learning) | $\pi(s) = \arg\max_{a \sim G(s)} Q(s,a)$，其中 G 是 VAE 生成的数据集分布样本 | 显式采样数据集附近动作 |
| **BEAR** (Bootstrapping Error Accumulation Reduction) | 用 MMD 距离约束 $\pi$ 与 $\pi_\beta$ 的分布距离 | 基于核的距离度量 |

**BCQ 核心伪逻辑**：
```
1. 训练 VAE 拟合数据集动作分布
2. 对于每个状态 s，从 VAE 采样 N 个候选动作
3. 添加小扰动（perturbation network）增加多样性
4. 选择 Q 值最高的那个动作执行
```

**问题**：需要知道 / 估计 $\pi_\beta$，而 $\pi_\beta$ 往往未知。

### 3.2 正则化 Q 学习（Regularized Q）

**思路**：不直接约束策略，而是修改 Q 学习目标，让 Q 函数本身保守。

**核心方法：CQL（Conservative Q-Learning）**— 见第 4 节。

### 3.3 不确定性惩罚（Uncertainty Penalty）

**思路**：使用 Ensemble Q 网络，对高不确定性的动作施加惩罚。

```
Q_target(s,a) = Q_mean(s,a) - λ × Var(Q_ensemble(s,a))
```

- 离数据集越远的动作，Q 值方差越大 → 惩罚越大
- 策略自然避开哪些"没人知道好坏"的动作
- 代表工作：**EDAC**、**PBRL（触底方法）**

---

## 4. CQL 详解（Conservative Q-Learning）

### 核心思想
在标准 Bellman 误差上**额外加一项正则化**，压低"在数据分布下可能出现的动作的 Q 值"，同时保持"真实动作的 Q 值"。

### CQL 目标函数

$$
\mathcal{L}_{CQL} = \underbrace{\alpha \cdot \mathbb{E}_{s \sim \mathcal{D}} \left[ \log \sum_a \exp(Q(s,a)) - \mathbb{E}_{a \sim \mathcal{D}} [Q(s,a)] \right]}_{\text{CQL 正则项}} + \underbrace{\mathcal{L}_{Bellman}}_{\text{标准 TD 误差}}
$$

### 直观理解

| 项 | 作用 |
|----|------|
| $\log \sum_a \exp(Q(s,a))$ | **推低**所有可能的动作（尤其是 OOD 动作）的 Q 值 |
| $\mathbb{E}_{a \sim \mathcal{D}}[Q(s,a)]$ | **拉高**数据集中真实出现的动作的 Q 值 |
| $\alpha$ 系数 | 保守程度：$\alpha$ 越大越保守 |

### 梯度效果
- 对数据集内的动作：Q 值保持不变或上升
- 对 OOD 动作：Q 值被强制压低 → 策略不会选择它们

### CQL 变体
- **CQL($\mathcal{H}$)**：使用 entropy-regularized policy，有闭式解
- **CQL($\rho$)**：直接对策略分布做约束

---

## 5. IQL（Implicit Q-Learning）

### 动机
之前的离线方法全部试图**避免查询 OOD 动作**。IQL 换了一个更优雅的思路：
> **只使用数据集中出现的动作来更新 Q 函数，完全不去查询 OOD 动作。**

### 关键技术：Expectile 回归

IQL 用 expectile 回归替代传统的 Bellman 最优更新：

$$
\min_\theta \mathbb{E}_{(s,a,s',a' \sim \mathcal{D})} \left[ L_2^\tau \left( r + \gamma Q_{\bar{\theta}}(s',a') - Q_\theta(s,a) \right) \right]
$$

其中 $L_2^\tau(u)$ 是不对称的 L2 损失：
- $u > 0$（好消息，当前 Q 偏低）：权重 $\tau$（$\tau > 0.5$，比如 0.7）
- $u < 0$（坏消息，当前 Q 偏高）：权重 $1-\tau$

### 效果
- $\tau > 0.5$ 意味着 Q 函数**偏向高估**，但只对数据集内的动作高估
- 等价于隐式地在数据分布内做 $\max$ 操作
- 不需要生成/采样 OOD 动作
- 不需要约束策略分布

### IQL vs CQL
| 方面 | CQL | IQL |
|------|-----|-----|
| 是否需要 OOD 动作采样 | 是（log-sum-exp） | 否 |
| 保守程度 | 全局保守 | 只在数据集内隐式保守 |
| 训练稳定性 | 对 $\alpha$ 敏感 | 更稳定 |
| 性能上限 | 偏保守，上限可能低 | 通常更高 |

---

## 6. 离线 → 在线迁移

### 为什么需要？
- 纯离线策略受限于数据集质量
- 在线微调可以突破数据集覆盖范围

### AWAC（Advantage-Weighted Actor-Critic）

**思想**：先离线预训练，再在线微调，但**不破坏离线学到的知识**。

#### AWAC 的 actor 更新
$$
\theta \leftarrow \arg\max_\theta \mathbb{E}_{(s,a) \sim \mathcal{D}_{\text{online}}} \left[ \log \pi_\theta(a|s) \cdot \exp\left( \frac{A(s,a)}{\lambda} \right) \right]
$$

- 离线和在线数据混合使用
- 只有**优势为正**的 action 才会被强化
- 防止策略远离离线数据中的好动作

### 离线预训练 + 在线微调流程
```
1. 用离线数据预训练策略和 Q 函数（如 CQL / IQL）
2. 部署策略到环境，收集新数据
3. 混合离线 + 在线数据继续更新（AWAC / CalQL）
4. 逐步减少离线数据比例
```

---

## 7. 代码：CQL 在 D4RL 数据集上的伪代码

```
Algorithm: CQL-SAC on D4RL

Input: 离线数据集 D, 学习率 α_q, α_pi, α_cql
Initialize: Q1, Q2, policy π, target Q1', Q2', replay buffer ← D

For each iteration:
    Sample batch (s, a, r, s') ~ D

    # ─── 1. 更新 Q 函数 ───
    # 1a. 计算 TD target（使用 Clipped Double Q）
    a' ~ π(s')                         # policy 输出的动作
    q1_target = Q1'(s', a')
    q2_target = Q2'(s', a')
    q_target = r + γ * min(q1_target, q2_target)

    # 1b. 标准 TD 误差
    td_loss = MSE(Q1(s,a), q_target) + MSE(Q2(s,a), q_target)

    # 1c. CQL 正则项
    # 对当前状态 s, 从 policy 采样 N 个动作
    actions_pi = π.sample_n(s, N)        # shape: (batch, N, act_dim)
    q_pi = logsumexp(Q(s, actions_pi))   # log ∑ exp(Q), 即 softmax 的 log 分母

    # 数据集中真实动作的 Q
    q_data = Q(s, a).mean()

    cql_loss = α_cql * (q_pi - q_data)   # 压低 OOD, 抬高 in-distribution

    # 1d. 总 Q loss
    q_loss = td_loss + cql_loss
    Q ← Q - α_q * ∇q_loss

    # ─── 2. 更新策略 π（最大化 Q）───
    # SAC 风格：π 最大化 Q + entropy
    actions, log_probs = π.sample(s)
    q_min = min(Q1(s, actions), Q2(s, actions))
    pi_loss = (α * log_probs - q_min).mean()
    π ← π - α_pi * ∇pi_loss

    # ─── 3. Soft update target network ───
    Q' ← τ * Q + (1 - τ) * Q'
```

### D4RL 数据集类型
| 数据集 | 质量 | 典型用法 |
|--------|------|----------|
| `-random` | 随机策略采集 | 基线测试 |
| `-medium` | 部分训练后的策略 | 中等难度 |
| `-medium-replay` | 训练过程中的 replay buffer | 评估样本效率 |
| `-medium-expert` | 混合中等 + 专家数据 | 常见 benchmark |
| `-expert` | 专家演示 | 上限测试 |

---

## 8. 离线 RL 的评估与数据集质量影响

### 评估困境
- 离线 RL 无法直接评估策略（因为不能与环境交互）
- 估计 Q 值不可靠（正是要解决的问题）
- **FQE（Fitted Q Evaluation）**：用 holdout 数据评估，但仍有偏

### 常见评估方式
1. **仿真器评估**：学术研究用 MuJoCo/D4RL 仿真环境评估
2. **重要性采样（IS）**：用 IS 估计策略回报，方差大但不偏
3. **加权重要性采样（WIS）**：降低方差
4. **离线指标**：CQL 的 Q 值本身可作为下界估计

### 数据集质量的影响

| 数据集质量 | 离线 RL 效果 | 原因 |
|-----------|-------------|------|
| 高覆盖 + 高质量 | 接近在线 RL | 数据包含了接近最优的轨迹 |
| 窄覆盖 + 高质量 | 还行，但有上限 | 策略被限制在数据覆盖区域内 |
| 宽覆盖 + 低质量 | 可能比行为策略好 | 可以从失败中学习 |
| 窄覆盖 + 低质量 | 很差 | 数据量和质量双输 |

### 经验法则
- **中等数据 + 好覆盖** > 专家数据 + 窄覆盖
- 数据多样性的重要性甚至高于数据质量
- 对 $\alpha$（保守程度）的调参至关重要：太保守学不到新东西，太松会导致 OOD 崩溃

---

## 总结表格

| 方法 | 核心机制 | 是否需要行为策略 | 是否约束策略 | 离线性能 | 在线微调 |
|------|----------|:---:|:---:|:---:|:---:|
| BCQ | VAE 采样 + 扰动 | 是（隐式） | 是 | ★★★ | 难 |
| BEAR | MMD 约束 | 是（样本） | 是 | ★★★ | 中等 |
| **CQL** | Q 值保守正则化 | 否 | 否 | ★★★★ | 容易 |
| **IQL** | Expectile 回归 | 否 | 否 | ★★★★ | 中等 |
| AWAC | 优势加权 | 否 | 软约束 | ★★★ | ★★★★★ |
| EDAC | Ensemble 不确定性 | 否 | 否 | ★★★★ | 中等 |

### 一句话总结

> **离线 RL 的关键在于"对未知保持谦逊"——让你的算法只在见过的地方学习，不给未见过的动作开空头支票。CQL 强硬压低未知动作的 Q 值，IQL 则干脆不看未知动作。两者殊途同归。** 🚀

---

*笔记日期：2026-02-27*
*下一篇：#10 基于模型的强化学习（MBRL）与规划*
