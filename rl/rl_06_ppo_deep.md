# 强化学习 #6 PPO 深度解析

> **PPO (Proximal Policy Optimization)** — 2017 年 OpenAI 提出，至今仍是 RL 领域最广泛使用的 on-policy 算法之一。它用极简的裁剪技巧解决了 TRPO 复杂且昂贵的二阶优化问题。

---

## 1. PPO 动机：为什么需要 PPO？

### 1.1 TRPO 的问题

TRPO（Trust Region Policy Optimization）的核心思路：**每次更新时，新策略不要离旧策略太远**。它通过约束新旧策略的 KL 散度来实现：

```
max  L(θ) = E[r_t(θ) * A_t]
s.t. D_KL(π_old || π_new) ≤ δ
```

但 TRPO 有严重不足：

| 问题 | 影响 |
|------|------|
| **二阶优化太贵** | 需要计算 Fisher 信息矩阵 + 共轭梯度法，每步更新计算量大 |
| **实现复杂** | 需要专门的优化器，天然不稳定易出错 |
| **不兼容现代框架** | 无法用 SGD/Adam 直接优化，工程落地困难 |

### 1.2 PPO 的简化思路

PPO 的核心思想与 TRPO 一致——**信任区域**，但采用截然不同的实现路径：

- TRPO：**硬约束** → KL 散度 ≤ δ（二阶优化求解）
- PPO：**软惩罚 / 裁剪** → 在目标函数中直接限制更新幅度（一阶优化）

PPO 目标函数中巧妙地加入了一个 **clip 操作**，使得：
- 当策略更新太激进时，目标函数自动截断梯度
- 依然可以用简单的 SGD/Adam 优化
- 计算量是 TRPO 的 1/10，效果相当甚至更好

> **一句话**：PPO 用「裁剪梯度」代替了 TRPO 的「约束优化」，大幅降低计算成本。

---

## 2. PPO-Clip 核心机制

### 2.1 重要性采样比率

在 PPO 中，我们使用重要性采样来评估新策略的表现：

```
r_t(θ) = π_θ(a_t|s_t) / π_θ_old(a_t|s_t)
```

- 如果 r_t(θ) > 1：新策略选择该动作的概率 **大于** 旧策略
- 如果 r_t(θ) < 1：新策略选择该动作的概率 **小于** 旧策略
- r_t(θ) ∈ (0, ∞)，当策略差异极大时，比率可能爆炸

### 2.2 Clip 函数

PPO-Clip 的目标函数：

```
L^CLIP(θ) = E[ min(
    r_t(θ) * A_t,
    clip(r_t(θ), 1-ε, 1+ε) * A_t
) ]
```

**ε 的经典取值**：0.2（即允许策略比率在 [0.8, 1.2] 范围内变化）

### 2.3 Min 操作的直观理解

`min(r*A, clip(r)*A)` 分为两种情况：

**当 A > 0（好动作）**：
- 我们想增加这个动作的概率 → r_t(θ) 希望 > 1
- 但 clip 设上限 1+ε=1.2，r_t(θ) 超过 1.2 就被截断
- 梯度被裁剪，不会过度更新

**当 A < 0（差动作）**：
- 我们想降低这个动作的概率 → r_t(θ) 希望 < 1
- 但 clip 设下限 1-ε=0.8，r_t(θ) 低于 0.8 就被截断
- 同样防止过度更新

```
    L^CLIP
      ↑
      |       /─── (无裁剪区域)
      |      /
      |     / 
      |    /  
      |   /   ← r*A (无限制)
      |  /
      | /
      ──┴──┬──────────→ r_t(θ)
     0.8  1.0  1.2
```

> **本质**：对好动作不贪心，对坏动作不放弃。每次只走一小步，确保稳定性。

### 2.4 最终目标函数（含熵奖励）

```
L^CLIP(θ) = E[ min(r_t(θ)*A_t, clip(r_t(θ),1-ε,1+ε)*A_t) + c * S[π_θ](s_t) ]
```

其中 `S[π_θ](s_t)` 是策略熵，鼓励探索；`c` 是熵系数。

---

## 3. PPO-Penalty：自适应 KL 惩罚

PPO 有两种变体，PPO-Clip 是主流，PPO-Penalty 较少用但思路值得了解。

### 3.1 核心公式

PPO-Penalty 直接在目标函数中加入 KL 散度惩罚项：

```
L^KLPEN(θ) = E[ r_t(θ)*A_t - β * D_KL(π_old || π_new) ]
```

β 是**动态调整**的惩罚系数。

### 3.2 自适应调整 β

```
如果 D_KL > δ_target × 1.5  → β ← β × 2     (KL 太大，加强惩罚)
如果 D_KL < δ_target / 1.5  → β ← β / 2     (KL 太小，减弱惩罚)
```

- `δ_target` 是目标 KL 散度（通常 0.01~0.05）
- 每轮更新后根据实际 KL 调整 β

### 3.3 PPO-Clip vs PPO-Penalty

| 对比项 | PPO-Clip | PPO-Penalty |
|--------|----------|-------------|
| 超参数 | ε=0.2（固定） | δ_target + β 初值（需调参） |
| 稳定性 | 更稳定，对超参数不敏感 | 对 β 更新策略敏感 |
| 使用率 | ≈95% 的 PPO 实现 | 较少使用 |
| 直觉 | 硬边界截断 | 软惩罚约束 |

> **实践经验**：除非有明显原因，否则永远选 PPO-Clip。

---

## 4. 完整 PPO 训练流程

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    PPO 训练循环                        │
├─────────────────────────────────────────────────────┤
│  for iteration = 1,2,...                             │
│      1. 与环境交互 T 步，收集经验                     │
│         (s, a, r, s', done, logπ_old)               │
│                                                      │
│      2. 计算 GAE（泛化优势估计）                      │
│         A_t = δ_t + (γλ)δ_{t+1} + ...                │
│                                                      │
│      3. 归一化优势值（可选但强烈推荐）                │
│         A = (A - mean(A)) / std(A)                   │
│                                                      │
│      4. 对 batch 做 K 个 epoch 的 SGD 更新           │
│         for epoch = 1...K:                           │
│            for minibatch in data:                    │
│              - 计算新策略的 logπ(a|s)                │
│              - 计算 r_t(θ) = exp(logπ_new - logπ_old)│
│              - 计算 L^CLIP                            │
│              - 计算价值损失 L^VF                       │
│              - 总损失 = L^CLIP - c1*L^VF + c2*S      │
│              - 反向传播 + 梯度裁剪                    │
│                                                      │
│      5. π_old ← π_new（清空 buffer）                 │
└─────────────────────────────────────────────────────┘
```

### 4.2 GAE（Generalized Advantage Estimation）

GAE 是 PPO 的优势估计标配，在 n 步回报和 TD(λ) 之间做了权衡：

```
δ_t = r_t + γ*V(s_{t+1}) - V(s_t)     # TD 误差

A_t^GAE = Σ_{l=0}^{T-t} (γλ)^l * δ_{t+l}

# 等价递推（从后往前）：
A_T = r_T - V(s_T)                     # 最后一步
A_t = δ_t + γλ * A_{t+1}              # 向前递推
```

参数含义：
- **γ（折扣因子）**：考虑多远的未来奖励
- **λ（GAE 参数）**：控制偏差-方差权衡
  - λ=0 → 等价于 TD(0)（高偏差，低方差）
  - λ=1 → 等价于 MC（低偏差，高方差）
  - λ=0.95 → 折中方案（标准做法）

### 4.3 价值函数损失

```
L^VF = MSE(V(s_t), R_t)

R_t = A_t + V(s_t)    # 目标是 TD(λ) 回报
# 或直接用 GAE-A 的价值替代
# L^VF = (V(s_t) - (A_t + V(s_t).detach()))^2
```

### 4.4 关键超参数

| 参数 | 典型值 | 说明 |
|------|--------|------|
| ε | 0.2 | PPO-Clip 裁剪边界 |
| γ | 0.99 | 折扣因子 |
| λ (GAE) | 0.95 | GAE lambda |
| K | 3~15 | 每个 batch 重复训练的 epoch 数 |
| batch_size | 64~4096 | 取决于环境 |
| learning_rate | 3e-4 | Adam 默认，通常需调 |
| entropy_coef | 0.01 | 熵奖励系数 |
| value_coef | 0.5 | 价值损失系数 |
| max_grad_norm | 0.5 | 梯度裁剪阈值 |

---

## 5. 连续动作空间：Gaussian 策略

### 5.1 策略网络设计

对于连续动作空间（如 Humanoid、LunarLanderContinuous），策略网络输出**高斯分布的参数**：

```
# Actor 网络
s → [Linear → Tanh → Linear → ...]
    ├── μ(s) = Linear(h)          # 均值，[-1,1] 用 Tanh 输出
    └── log_σ = Parameter()       # 对数标准差（可学习）

# 采样动作
a = μ(s) + σ * ε,  ε ~ N(0, I)
logπ(a|s) = -0.5 * ((a-μ)/σ)^2 - log(σ) - const
```

### 5.2 状态无关 vs 状态相关标准差

两种实现方式：

**状态无关（state-independent）**：
```python
self.log_std = nn.Parameter(torch.full((action_dim,), -0.5))
```
- 常数标准差，简单稳定
- 适用于大部分环境

**状态相关（state-dependent）**：
```python
self.log_std = nn.Sequential(Linear(hidden_dim, action_dim), ...)
```
- 标准差随状态变化
- 更灵活但更难训练

> **工程建议**：先试状态无关。当策略方差需要随状态自适应时再升级。

### 5.3 Tanh 高斯策略细节

当动作空间有界（如 [-1, 1]），需要将高斯采样的原始动作乘以 Tanh 压缩：

```
a_raw = μ + σ*ε
a = tanh(a_raw)
```

此时对数概率需要做 **Jacobian 修正**（否则概率密度计算错误）：

```
logπ(a|s) = logπ_raw(a_raw|s) - Σ log(1 - tanh²(a_raw))
           = logπ_raw(a_raw|s) - Σ 2*log(cosh(a_raw)) - log(2)
```

> **实际实现**：PyTorch 的 `distributions.TransformedDistribution` + `TanhTransform` 自动处理。

---

## 6. PyTorch 实现 PPO（LunarLander / Humanoid）

> ⚠️ 本节展示核心结构，不执行完整训练。

### 6.1 网络定义

```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class ActorCritic(nn.Module):
    """共享特征提取器的 Actor-Critic 网络"""

    def __init__(self, obs_dim, act_dim, continuous=False):
        super().__init__()
        self.continuous = continuous

        # 共享网络
        self.feat = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
        )

        # Actor: 策略
        if continuous:
            self.actor_mean = nn.Linear(64, act_dim)
            self.log_std = nn.Parameter(torch.full((act_dim,), -0.5))
        else:
            self.actor = nn.Linear(64, act_dim)    # 离散动作 logits

        # Critic: 价值函数
        self.critic = nn.Linear(64, 1)

    def forward(self, obs):
        feat = self.feat(obs)
        value = self.critic(feat)
        if self.continuous:
            mean = self.actor_mean(feat)
            std = self.log_std.exp().expand_as(mean)
            return mean, std, value
        else:
            logits = self.actor(feat)
            return logits, value

    def get_action(self, obs, action=None):
        """返回动作、log_prob、价值、熵"""
        if self.continuous:
            mean, std, value = self.forward(obs)
            dist = torch.distributions.Normal(mean, std)
            if action is None:
                action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1)
        else:
            logits, value = self.forward(obs)
            dist = torch.distributions.Categorical(logits=logits)
            if action is None:
                action = dist.sample()
            log_prob = dist.log_prob(action)
            entropy = dist.entropy()
        return action, log_prob, value.squeeze(-1), entropy

    def evaluate(self, obs, action):
        """用于 PPO 更新的前向计算"""
        if self.continuous:
            mean, std, value = self.forward(obs)
            dist = torch.distributions.Normal(mean, std)
            log_prob = dist.log_prob(action).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1)
        else:
            logits, value = self.forward(obs)
            dist = torch.distributions.Categorical(logits=logits)
            log_prob = dist.log_prob(action)
            entropy = dist.entropy()
        return log_prob, value.squeeze(-1), entropy
```

### 6.2 PPO Buffer

```python
class PPOBuffer:
    """存储交互数据，单轨迹"""

    def __init__(self, obs_dim, act_dim, size, gamma=0.99, gae_lambda=0.95):
        self.obs = torch.zeros(size, obs_dim)
        self.actions = torch.zeros(size, act_dim if isinstance(act_dim, int) else 1)
        self.rewards = torch.zeros(size)
        self.dones = torch.zeros(size)
        self.log_probs = torch.zeros(size)
        self.values = torch.zeros(size)
        self.advantages = torch.zeros(size)
        self.returns = torch.zeros(size)

        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.ptr = 0
        self.max_size = size

    def store(self, obs, action, reward, done, log_prob, value):
        self.obs[self.ptr] = torch.as_tensor(obs)
        self.actions[self.ptr] = torch.as_tensor(action)
        self.rewards[self.ptr] = reward
        self.dones[self.ptr] = done
        self.log_probs[self.ptr] = log_prob
        self.values[self.ptr] = value
        self.ptr += 1

    def compute_gae(self, last_value):
        """从后往前计算 GAE"""
        advantages = torch.zeros(self.max_size)
        gae = 0
        for t in reversed(range(self.max_size)):
            if t == self.max_size - 1:
                next_value = last_value
                done_mask = self.dones[t]
            else:
                next_value = self.values[t + 1]
                done_mask = self.dones[t]

            delta = self.rewards[t] + self.gamma * next_value * (1 - done_mask) - self.values[t]
            gae = delta + self.gamma * self.gae_lambda * (1 - done_mask) * gae
            advantages[t] = gae

        self.advantages = advantages
        self.returns = advantages + self.values
```

### 6.3 PPO Update 核心

```python
def ppo_update(agent, buffer, optimizer, epochs=10, batch_size=64,
               clip_eps=0.2, value_coef=0.5, entropy_coef=0.01, max_grad_norm=0.5):
    """PPO-Clip 核心更新逻辑"""

    obs = buffer.obs
    actions = buffer.actions
    old_log_probs = buffer.log_probs
    advantages = buffer.advantages
    returns = buffer.returns

    # 归一化优势
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    dataset = torch.utils.data.TensorDataset(obs, actions, old_log_probs, advantages, returns)
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    for _ in range(epochs):
        for batch in loader:
            obs_b, act_b, old_logp_b, adv_b, ret_b = batch

            # 前向计算新策略
            new_logp, values, entropy = agent.evaluate(obs_b, act_b)

            # 重要性采样比率
            ratio = torch.exp(new_logp - old_logp_b)

            # PPO-Clip 目标
            surr1 = ratio * adv_b
            surr2 = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps) * adv_b
            policy_loss = -torch.min(surr1, surr2).mean()

            # 价值损失
            value_loss = F.mse_loss(values, ret_b)

            # 熵奖励
            entropy_loss = -entropy.mean()

            # 总损失
            loss = policy_loss + value_coef * value_loss + entropy_coef * entropy_loss

            # 反向传播
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(agent.parameters(), max_grad_norm)
            optimizer.step()
```

### 6.4 完整训练循环

```python
def train_ppo(env, agent, total_steps=1_000_000, steps_per_iter=2048,
              update_epochs=10, batch_size=64, lr=3e-4):

    optimizer = torch.optim.Adam(agent.parameters(), lr=lr)
    buffer = PPOBuffer(obs_dim, act_dim, steps_per_iter)

    obs, _ = env.reset()
    episode_return = 0
    step = 0

    while step < total_steps:
        # ─── 收集经验 ───
        for _ in range(steps_per_iter):
            action, log_prob, value, _ = agent.get_action(obs[None])[0]
            next_obs, reward, done, truncated, _ = env.step(action.numpy())
            episode_return += reward

            buffer.store(obs, action, reward, done or truncated, log_prob, value)

            obs = next_obs
            step += 1

            if done or truncated:
                obs, _ = env.reset()
                print(f"Step {step}, Return {episode_return:.1f}")
                episode_return = 0

        # ─── GAE 计算 ───
        _, _, last_value, _ = agent.get_action(obs[None])[0]
        buffer.compute_gae(last_value)

        # ─── PPO 更新 ───
        ppo_update(agent, buffer, optimizer, epochs=update_epochs, batch_size=batch_size)

        # 清空 buffer
        buffer.ptr = 0
```

---

## 7. PPO 改进技巧

### 7.1 奖励裁剪（Reward Clipping）

```python
reward = np.clip(reward, -10, 10)
```

- 防止异常奖励导致价值网络震荡
- 特别适用于奖励范围未知的新环境

### 7.2 梯度裁剪（Gradient Clipping）

```python
nn.utils.clip_grad_norm_(agent.parameters(), max_grad_norm=0.5)
```

- 限制梯度范数，防止梯度爆炸
- 使训练更稳定，收敛更快

### 7.3 学习率调度（LR Scheduling）

```python
scheduler = torch.optim.lr_scheduler.LinearLR(
    optimizer, start_factor=1.0, end_factor=0.0, total_iters=total_updates
)
```

- 前期大步探索，后期精细收敛
- 三个常见调度策略：

| 调度策略 | 适合场景 |
|----------|----------|
| 线性衰减 | 通用，最稳定 |
| 余弦退火 | 复杂环境，追求最优性能 |
| Step decay | 训练周期较长的场景 |

### 7.4 正交初始化（Orthogonal Initialization）

```python
def orthogonal_init(layer, gain=1.0):
    nn.init.orthogonal_(layer.weight, gain=gain)
    nn.init.constant_(layer.bias, 0)

# Actor head gain 设小（如 0.01），防止初始策略输出太大
orthogonal_init(agent.actor_mean, gain=0.01)
orthogonal_init(agent.critic, gain=1.0)
# 特征提取器：用 √2
orthogonal_init(agent.feat[0], gain=√2)
```

为什么有效：
- 正交矩阵保持梯度的范数，防止 vanish/explode
- Actor head 小 gain → 初始动作接近 0 → 在 [-1,1] 中心探索
- Critic head normal gain → 价值估计随训练自然变化

### 7.5 其他实用技巧

| 技巧 | 做法 | 效果 |
|------|------|------|
| **状态归一化** | RunningMeanStd 在线归一化 obs | 大幅加速收敛 |
| **奖励缩放** | /max_abs_reward | 使奖励在合理范围内 |
| **价值裁剪** | clip(value, min_ret, max_ret) | 防止 V 值过估计 |
| **Actor 滞后** | Actor 更新频率低于 Critic | 平衡 policy/value |
| **TD(lambda) 替代** | 用 λ-return 代替 GAE | 简单场景够用 |
| **n-step 回退** | n ≤ 环境 horizon | 减少偏差 |

---

## 8. 为什么 PPO 比 A2C 强

### 8.1 A2C 的根本问题

A2C（Advantage Actor-Critic）每次更新公式简单：

```
L^A2C = logπ(a|s) * A(s,a)
```

**问题**：缺少对更新步长的限制！

- 碰到一个好动作 → 策略大幅向它偏移
- 碰到一个坏动作 → 策略大幅远离它
- 收集的数据稍有噪声 → 策略震荡甚至崩溃

> **A2C 的致命弱点**：一次不好的更新就能毁掉已经学好的策略。而且因为没有保护机制，后续也很难恢复。

### 8.2 PPO 的 clip 保护

PPO 通过 clipping 限制了每次更新的「最大步长」：

```
# A2C 的梯度（无保护）
∇L ∝ A(s,a)    # 优势多大，更新就有多大

# PPO 的梯度（有保护）
∇L ∝ clip(A(s,a), -εV, +εV)   # 优势再大，步长被封顶
```

### 8.3 稳定性对比

| 场景 | A2C | PPO |
|------|-----|-----|
| 数据噪声大 | 容易崩 | 稳定 |
| 奖励稀疏 | 收敛慢/不收敛 | 能逐步推进 |
| 训练离策略 | 偏差很大 | 通过 clip 控制 |
| 超参数敏感 | 非常敏感 | 相对鲁棒 |
| 样本效率 | 低 | 中（多 epoch 提高效率） |
| 实现难度 | 简单 | 略复杂 |

### 8.4 核心洞察

PPO 的本质是**在「信任区域」内做多步更新**：

1. **收集一批数据**（on-policy）
2. **在这批数据上做 K 个 epoch 优化**（利用 off-policy 思想提高效率）
3. **但限制每次更新的范围**（clip 确保不离旧策略太远）

```
A2C:  采样1步 → 更新1次 → 采样1步 → 更新1次 → ...
PPO:  采样N步 → 更新K次 → 采样N步 → 更新K次 → ...
        ↑ 每个 epoch 都受 clip 保护，不会推太远
```

> **一句话**：PPO = A2C + 安全护栏。

---

## 9. 结合 RL Trader：PPO 替换 RL v3 的 TD(λ) 逻辑

### 9.1 当前 RL v3 的做法

目前的 RL trader 使用 **TD(λ) + A2C-style 更新**：

```
# 当前流程
for step in episode:
    action = policy(state)
    next_state, reward = env.step(action)
    buffer.store(state, action, reward, done)

# 在每个终止点做 TD(λ) 更新
returns = compute_td_lambda(rewards, values, gamma, lambda_)
advantages = returns - values

# 单次梯度更新
loss = -log_prob * advantages + value_loss
```

### 9.2 问题诊断

| 问题 | 描述 |
|------|------|
| **单步更新不稳定** | 每次交易信号只更新一次，梯度噪声大 |
| **无信任区域保护** | 一笔异常交易可能导致策略骤变 |
| **低样本效率** | 一条完整轨迹只更新一次，没复用好数据 |

### 9.3 PPO 替换方案

```
# PPO 替换后的流程

# ── 第1阶段：收集 ──
for step in episode:
    action, log_prob, value = agent(state)
    next_state, reward, done = env.step(action)
    buffer.store(state, action, reward, done, log_prob, value)

# ── 第2阶段：GAE 计算 ──
advantages = compute_gae(buffer.rewards, buffer.values, gamma=0.99, gae_lambda=0.95)
returns = advantages + buffer.values

# ── 第3阶段：多 epoch 更新（关键变化） ──
for epoch in range(K=5):               # 同一批数据反复用
    for minibatch in DataLoader(data):  # 打乱数据
        new_log_prob, new_value = agent.evaluate(minibatch)

        ratio = exp(new_log_prob - old_log_prob)
        surr1 = ratio * advantage
        surr2 = clip(ratio, 0.8, 1.2) * advantage
        policy_loss = -min(surr1, surr2).mean()

        value_loss = F.mse_loss(new_value, returns)
        entropy_loss = -entropy.mean()

        total_loss = policy_loss + 0.5*value_loss + 0.01*entropy_loss
        optimizer.step()
```

### 9.4 具体替换策略

```python
# 改动一览

# 1️⃣ 网络结构
# 原：单层 LSTM → Linear(act_dim) + Linear(1)
# 新：保持 LSTM，但增加标准化输出
class PPO_Trader(nn.Module):
    def __init__(self):
        self.lstm = nn.LSTM(input_dim, 128)
        self.actor = nn.Linear(128, n_actions)    # 离散动作（买入/卖出/持有）
        self.critic = nn.Linear(128, 1)

        # 正交初始化
        orthogonal_init(self.actor, gain=0.01)
        orthogonal_init(self.critic, gain=1.0)

    def get_action(self, state, hidden, action=None):
        feat, hidden = self.lstm(state, hidden)
        logits = self.actor(feat)
        value = self.critic(feat)
        dist = Categorical(logits=logits)
        # ...

# 2️⃣ Buffer 改造
# 原：每一次 TD 更新就清空 buffer
# 新：收集完整轨迹后统一计算 GAE，然后做多 epoch 更新

# 3️⃣ 更新逻辑
# 原：
#   advantages = td_lambda_returns - values   ← 一次计算
#   loss = -log_prob * advantages + value_loss
#   optimizer.step()                          ← 一步到位

# 新：
#   advantages = gae(rewards, values, γ, λ)   ← 用 GAE
#   advantages = normalize(advantages)          ← 归一化
#   for _ in range(K):                         ← 多 epoch
#       for batch in shuffle(data):            ← 小批量
#           ratio = exp(new_logp - old_logp)   ← 重要性采样
#           loss = clip(ratio * adv, ...)       ← clip 保护
#           optimizer.step()

# 4️⃣ 超参数适配
# 原超参数              → PPO 超参数
# gamma=0.95            → gamma=0.99         # 长期收益权重加大
# lambda_=0.8           → gae_lambda=0.95    # 降低偏差
# lr=1e-3               → lr=3e-4           # 缩小学习率
# -                     → clip_eps=0.2       # 新参数
# -                     → K=5 (epochs)       # 新参数
# -                     → batch_size=64      # 新参数
```

### 9.5 预期收益

| 指标 | 当前 RL v3 | PPO 替换后 |
|------|-----------|------------|
| 训练稳定性 | 中（偶尔崩溃） | 高（clip 保护） |
| 样本效率 | 低 | 中（多 epoch 复用） |
| Sharpe 比率 | 波动大 | 预计更稳定 |
| 超参数调优 | 难度高 | 相对更鲁棒 |
| 部署前训练 | 需要更多步 | 同等性能更快 |


> 注：离散动作交易场景的 PPO 与连续控制略有不同——不需要 Gaussian 策略，但需要处理 LSTM 隐藏状态的保存和 O(n²) 复杂度的时间序列 batch。在实现时注意序列长度的采样和 padding/truncation 的统一处理。
>
> **大规模交易系统建议**：PPO + 分布式优势（A3C-style），用多进程收集经验，集中做 PPO 更新。
