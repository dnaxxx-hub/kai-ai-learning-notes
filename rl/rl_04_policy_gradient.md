# RL #4：策略梯度与 PPO

> 前三课我们一直在学 **Value-Based** 方法：学 Q 值，然后根据 Q 值选动作（ε-贪心）。但 Value-Based 有三大短板：1) 连续动作空间没法枚举 max；2) 策略本质是确定性的（argmax），对**随机策略**不友好；3) 策略的小改进也可能导致 Q 值巨变，稳定性差。
>
> 这一课我们换个思路——**不学 Q 值，直接学策略**。从 REINFORCE 走到 Actor-Critic 再到 PPO，最终理解为什么 PPO 是当前最主流的在线 RL 算法之一，以及它怎么适配量化交易。

---

## 1. 从值函数到策略梯度

### 1.1 Value-Based 的隐性问题

回顾 DQN 的更新方式：

$$Q(s, a) \leftarrow Q(s, a) + \alpha \left[ r + \gamma \max_{a'} Q(s', a') - Q(s, a) \right]$$

每一步都在调整 Q 值，然后通过 $\arg\max_a Q(s,a)$ 决定策略。这种 **"先估值，后决策"** 的间接方式有三个问题：

| 问题 | 说明 | 后果 |
|------|------|------|
| **连续动作** | $\max_a$ 在连续空间无法枚举 | 需要特殊设计（如 DDPG） |
| **确定性策略** | $\arg\max$ 是确定性的 | 无法表示随机策略（如扑克中的诈唬） |
| **Q 值震荡** | Q 值微小变化 → 策略突变 | 训练不稳定 |

### 1.2 策略梯度的核心思想

直接参数化策略：$\pi_\theta(a|s) = P(a|s;\theta)$

目标是最大化期望累积奖励：

$$J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta} \left[ \sum_{t=0}^{T} \gamma^t r_t \right]$$

然后用梯度上升更新 $\theta$：

$$\theta \leftarrow \theta + \alpha \nabla_\theta J(\theta)$$

**关键问题**：怎么算 $\nabla_\theta J(\theta)$？期望中的轨迹分布本身依赖于 $\theta$，我们不能直接对期望求导。

### 1.3 策略梯度定理

策略梯度定理给出了答案：

$$\nabla_\theta J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta} \left[ \sum_{t=0}^{T} \nabla_\theta \log \pi_\theta(a_t | s_t) \cdot \left( \sum_{k=t}^{T} \gamma^{k-t} r_k \right) \right]$$

**直觉理解**：
- $\nabla_\theta \log \pi_\theta(a_t|s_t)$：参数的**变化方向**，增加/减少某个动作的概率
- $\sum_{k=t}^{T} \gamma^{k-t} r_k$：从 $t$ 时刻开始的**实际回报**（Reward-to-Go）
- **乘积**：如果某动作导致回报好 → 增大该动作的概率；回报差 → 减小

这比 Value-Based 优雅得多——策略梯度直接告诉你"往哪个方向调参数能提高表现"。

---

## 2. REINFORCE

### 2.1 算法思想

REINFORCE 是策略梯度最基础的版本，也叫 **Monte Carlo Policy Gradient**。它用完整轨迹的实际回报作为动作好坏的评判标准。

**数学形式**：

对每个更新步：

$$\nabla_\theta J(\theta) \approx \frac{1}{N} \sum_{i=1}^{N} \sum_{t=0}^{T_i} \nabla_\theta \log \pi_\theta(a_{i,t} | s_{i,t}) \cdot G_{i,t}$$

其中 $G_{i,t} = \sum_{k=t}^{T_i} \gamma^{k-t} r_{i,k}$ 是 $t$ 时刻的实际折扣回报。

### 2.2 NumPy 伪代码

```python
import numpy as np

class REINFORCE:
    def __init__(self, n_states, n_actions, lr=0.001, gamma=0.99):
        # 策略网络：简单 softmax 策略
        # π(a|s) = softmax(s · W)
        self.W = np.random.randn(n_states, n_actions) * 0.01
        self.lr = lr
        self.gamma = gamma
        self.n_actions = n_actions
        
    def forward(self, state):
        """计算策略分布 π(a|s)"""
        logits = state @ self.W          # (n_actions,)
        exp = np.exp(logits - logits.max())  # 数值稳定
        probs = exp / exp.sum()
        return probs
    
    def sample_action(self, state):
        """从策略分布采样动作"""
        probs = self.forward(state)
        return np.random.choice(self.n_actions, p=probs)
    
    def compute_returns(self, rewards):
        """计算折扣回报 G_t = Σ γ^{k-t} r_k"""
        T = len(rewards)
        returns = np.zeros(T)
        G = 0.0
        for t in reversed(range(T)):
            G = rewards[t] + self.gamma * G
            returns[t] = G
        return returns
    
    def update(self, states, actions, rewards):
        """REINFORCE 策略梯度更新"""
        # (1) 计算每个 time step 的回报
        returns = self.compute_returns(rewards)
        
        # (2) 对每个 time step 计算梯度并累积
        dW = np.zeros_like(self.W)
        for s, a, G in zip(states, actions, returns):
            probs = self.forward(s)
            
            # ∇ log π(a|s) 的推导：
            # softmax 策略下，∇ log π(a|s) = 1{a=a'} - π(a'|s)
            # 这是 one-hot 编码减去概率分布的差值
            grad_log = -probs.copy()      # -π(a'|s)
            grad_log[a] += 1.0            # +1 对于选中的动作
            
            # 外积：特征 × 梯度
            dW += np.outer(s, grad_log) * G
        
        # (3) 梯度上升
        self.W += self.lr * dW / len(states)
```

### 2.3 REINFORCE 的核心问题

| 问题 | 原因 | 后果 |
|------|------|------|
| **高方差** | $G_t$ 是单条轨迹的具体值，噪声极大 | 训练震荡，收敛慢 |
| **样本效率低** | 蒙特卡洛方式，每条轨迹只用一次 | 需要海量交互 |
| **同策略(on-policy)** | 只能用当前策略采集的数据更新 | 不能复用旧数据 |

最致命的是**高方差**。想象一个场景：某动作 A 的期望回报是 +0.1，但随机噪声下某次实际得到了 +5.0。REINFORCE 会大幅增加 A 的概率，但下次可能回落到 -3.0，又大幅降低。这就是 REINFORCE 在复杂环境中几乎无法收敛的原因。

---

## 3. Baseline 减方差

### 3.1 核心思想

$G_t$ 的方差来自两个部分：
1. 环境本身是随机的（MPD 的随机性）
2. 策略是随机的（采样动作）

但很多方差是**冗余的**——某个状态的价值本身有期望值，实际回报在这个期望值附近波动。如果能减去这个期望值，只保留**相对于平均水平的优势**，方差就会显著降低。

**数学上**：任何只与状态有关的函数 $b(s_t)$ 作为 baseline 都不改变梯度的期望：

$$\mathbb{E}[\nabla_\theta \log \pi_\theta(a_t|s_t) \cdot (G_t - b(s_t))] = \mathbb{E}[\nabla_\theta \log \pi_\theta(a_t|s_t) \cdot G_t]$$

因为 $\mathbb{E}[\nabla_\theta \log \pi_\theta(a_t|s_t) \cdot b(s_t)] = 0$（期望下，梯度与 baseline 正交）。

### 3.2 最好的 Baseline：状态价值函数 V(s)

最好的 baseline 是 $V^\pi(s_t) = \mathbb{E}[G_t | s_t]$，即从 $s_t$ 出发的期望回报。

此时：

$$G_t - V(s_t) = \left( \text{实际回报} \right) - \left( \text{期望回报} \right) = \text{这个动作比平均好多少}$$

这就是 **优势 (Advantage)**：

$$A(s_t, a_t) = G_t - V(s_t)$$

**为什么好**：
- 方差大幅降低（只保留"偏离平均"的部分）
- 梯度方向更准确（平均值附近的小波动被滤掉了）

---

## 4. Actor-Critic

### 4.1 从 MC 到 TD：两个网络的结合

REINFORCE 是蒙特卡洛的（走完一整条轨迹才更新）。Actor-Critic 把价值网络（Critic）和策略网络（Actor）结合起来，实现 **TD 更新**——每一步都能学。

| 组件 | 角色 | 输入输出 |
|------|------|---------|
| **Actor** (策略网络 $\pi_\theta$) | 决策者 | $s \rightarrow a$ 的概率分布 |
| **Critic** (价值网络 $V_\phi$) | 评判者 | $s \rightarrow V(s)$，评估当前状态好坏 |

**工作流程**：
1. Actor 根据当前策略采样动作 $a$
2. Critic 评估状态价值 $V(s)$
3. 执行动作后得到 $(r, s')$
4. Critic 用 TD 误差更新自己
5. Actor 用 TD 误差作为"优势"更新自己

### 4.2 TD 误差作为 Advantage

不再用完整的 $G_t$，而是用一步 TD 误差：

$$\delta_t = r_t + \gamma V_\phi(s_{t+1}) - V_\phi(s_t)$$

**关键洞察**：$\delta_t$ 是 $A(s_t, a_t)$ 的无偏估计（在期望意义上）：

$$\mathbb{E}[\delta_t | s_t, a_t] = \mathbb{E}[r_t + \gamma V(s_{t+1}) - V(s_t) | s_t, a_t] = Q(s_t, a_t) - V(s_t) = A(s_t, a_t)$$

但 $\delta_t$ 的方差远低于 $G_t$，因为它只用了一步的实际结果，而不是整条轨迹。

### 4.3 NumPy 伪代码（A2C）

```python
import numpy as np

class ActorCritic:
    def __init__(self, n_states, n_actions, lr_actor=0.001, lr_critic=0.01, gamma=0.99):
        # Actor: s → softmax(s · Wa)
        self.Wa = np.random.randn(n_states, n_actions) * 0.01
        # Critic: s → V(s) = s · Wc
        self.Wc = np.random.randn(n_states) * 0.01
        self.lr_a = lr_actor
        self.lr_c = lr_critic
        self.gamma = gamma
        self.n_actions = n_actions
    
    def act(self, state):
        """Actor 采样动作"""
        logits = state @ self.Wa
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()
        action = np.random.choice(self.n_actions, p=probs)
        return action, probs
    
    def value(self, state):
        """Critic 评估状态价值"""
        return state @ self.Wc
    
    def update(self, state, action, reward, next_state, done):
        # (1) Critic 更新：最小化 TD 误差
        V = self.value(state)
        V_next = 0.0 if done else self.value(next_state)
        td_target = reward + self.gamma * V_next
        td_error = td_target - V                     # δ = r + γV(s') - V(s)
        
        # Critic 梯度下降（MSE）
        self.Wc += self.lr_c * td_error * state      # ∇(V - target)² ∝ -td_error · state
        
        # (2) Actor 更新：用 TD 误差作为 Advantage
        probs = state @ self.Wa
        exp = np.exp(probs - probs.max())
        probs = exp / exp.sum()
        
        # ∇log π(a|s) = 1-hot(a) - π
        grad_log = -probs.copy()
        grad_log[action] += 1.0
        
        # 策略梯度上升：∇J(θ) ≈ δ · ∇log π(a|s)
        self.Wa += self.lr_a * td_error * np.outer(state, grad_log)
        
        return td_error  # 可用于监控
```

### 4.4 Actor-Critic 的进一步演变

**A2C (Advantage Actor-Critic)**：使用多步 TD（n-step returns）平衡偏差-方差：

$$A_t = \sum_{k=0}^{n-1} \gamma^k r_{t+k} + \gamma^n V(s_{t+n}) - V(s_t)$$

**A3C (Asynchronous Advantage Actor-Critic)**：开启多个并行 worker 同时采集数据，异步更新共享参数。A2C 是 A3C 的同步版本，实践中通常更好。

---

## 5. PPO — Proximal Policy Optimization

### 5.1 为什么需要 PPO

Actor-Critic 有一个严重问题：**策略更新步长不好控制**。

- **步子太大**：策略突然变差，进入"坏区域"，再也回不来（崩溃性更新）
- **步子太小**：学得太慢

TRPO (Trust Region Policy Optimization) 率先解决了这个问题：每次更新策略时，限制新旧策略的 **KL 散度**不超过某个阈值。但 TRPO 需要计算二阶 Hessian 矩阵（共轭梯度法），实现复杂、计算量大。

PPO 是 TRPO 的简化版：用一阶方法（只需要梯度）近似 TRPO 的效果，实现简单且性能相当甚至更优。

### 5.2 Importance Sampling — 复用旧数据

PPO 是 on-policy 算法，但通过 **importance sampling** 可以复用之前策略采集的数据做多次更新。

定义新旧策略的概率比：

$$r_t(\theta) = \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}$$

- $r_t(\theta) > 1$：新策略给这个动作的概率更大
- $r_t(\theta) < 1$：新策略给这个动作的概率更小

Policy Gradient 在 importance sampling 下的形式（带优势）：

$$J(\theta) = \mathbb{E}_{(s_t, a_t) \sim \pi_{\theta_{old}}} \left[ \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)} \cdot A_t \right]$$

如果在旧数据上做多步梯度更新，这个 $r_t(\theta)$ 可能越滚越大或越滚越小，导致更新灾难。

### 5.3 Clipped Surrogate Objective

PPO 的**核心创新**：给 $r_t(\theta)$ 加一个剪切范围 $[1-\epsilon, 1+\epsilon]$。

**PPO 的目标函数**：

$$L^{CLIP}(\theta) = \mathbb{E} \left[ \min \left( r_t(\theta) A_t, \; \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon) A_t \right) \right]$$

**结合完整的正则项**（包含价值损失和熵奖励）：

$$L_t(\theta, \phi) = \mathbb{E} \left[ L_t^{CLIP}(\theta) - c_1 L_t^{VF}(\phi) + c_2 S[\pi_\theta](s_t) \right]$$

**图解直觉**：

```
当 A_t > 0（好动作）：
    - r 增大 → 增加该动作概率
    - 但 r > 1+ε 时，clip 截断 → 不贪心，限制增长
    
当 A_t < 0（坏动作）：
    - r 减小 → 降低该动作概率  
    - 但 r < 1-ε 时，clip 截断 → 防止过度惩罚
```

**min 的作用**：取 $r_t A_t$ 和 $\text{clip}(r_t) A_t$ 中较小的那个。这确保了目标函数是**真实目标（未经 clip）的下界**——虽然我们在优化下界，但保证不会让策略变得更差。

| 情况 | 无 clip | 有 clip | 效果 |
|------|---------|---------|------|
| 好动作，$r$ 变得极大 | 概率暴涨 | 截止到 $1+\epsilon$ | 防止贪心冒进 |
| 坏动作，$r$ 变得极小 | 概率骤降 | 截止到 $1-\epsilon$ | 防止过度惩罚 |

$\epsilon$ 的典型值：0.1 或 0.2。

### 5.4 为什么 PPO 有效

1. **信任区域**：严格限制每次更新的"步长"，避免灾难性策略崩溃
2. **样本高效**：重要性采样允许一条数据用多次（通常 4-10 个 epoch）
3. **实现简单**：只需梯度，不需二阶 Hessian
4. **广泛适用**：离散/连续动作空间都能处理（通过高斯分布输出动作均值/方差）

---

## 6. PPO 伪代码

```python
import numpy as np

class PPO:
    def __init__(self, n_states, n_actions, 
                 lr=3e-4, gamma=0.99, lam=0.95,
                 clip_eps=0.2, epochs=10, batch_size=64):
        # Actor: s → π(a|s) 使用 softmax
        self.Wa = np.random.randn(n_states, n_actions) * 0.01
        # Critic: s → V(s) 
        self.Wc = np.random.randn(n_states) * 0.01
        self.lr = lr
        self.gamma = gamma
        self.lam = lam              # GAE(lambda) 参数
        self.clip_eps = clip_eps    # ε，剪切范围
        self.epochs = epochs         # 每批次数据复用次数
        self.batch_size = batch_size
        self.n_actions = n_actions
    
    def act(self, state):
        """采样动作，同时返回概率分布（用于 importance sampling）"""
        logits = state @ self.Wa
        exp = np.exp(logits - logits.max())
        probs = exp / exp.sum()
        action = np.random.choice(self.n_actions, p=probs)
        return action, probs[action]  # 也返回 P(动作|状态)
    
    def value(self, state):
        return state @ self.Wc
    
    def gae(self, rewards, values, dones):
        """Generalized Advantage Estimation
           使用 lambda-return 平衡偏差-方差
        """
        T = len(rewards)
        advantages = np.zeros(T)
        last_gae = 0.0
        for t in reversed(range(T)):
            if dones[t]:
                delta = rewards[t] - values[t]
                last_gae = delta
            else:
                next_val = values[t+1] if t+1 < T else 0.0
                delta = rewards[t] + self.gamma * next_val - values[t]
                last_gae = delta + self.gamma * self.lam * last_gae
            advantages[t] = last_gae
        # 对优势做归一化（降低方差）
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        # 回报 = 价值 + 优势（用于 Critic 更新）
        returns = advantages + values
        return advantages, returns
    
    def update(self, states, actions, old_log_probs, rewards, dones):
        """PPO 单次更新，复用数据集多次"""
        # (1) 计算价值和优势
        values = np.array([self.value(s) for s in states])
        advantages, returns = self.gae(rewards, values, dones)
        
        # (2) 复用数据 epoch 次
        for _ in range(self.epochs):
            # 随机打乱
            idxs = np.random.permutation(len(states))
            
            for start in range(0, len(states), self.batch_size):
                batch_ids = idxs[start:start+self.batch_size]
                
                batch_states = states[batch_ids]
                batch_actions = actions[batch_ids]
                batch_old_logp = old_log_probs[batch_ids]
                batch_adv = advantages[batch_ids]
                batch_ret = returns[batch_ids]
                
                # ---- Actor 更新：PPO clipped surrogate ----
                dWa = np.zeros_like(self.Wa)
                for i, s, a, old_logp, A in zip(
                    range(len(batch_states)), 
                    batch_states, batch_actions, 
                    batch_old_logp, batch_adv):
                    
                    logits = s @ self.Wa
                    exp = np.exp(logits - logits.max())
                    probs = exp / exp.sum()
                    
                    # 新策略下该动作的概率
                    new_logp = np.log(probs[a] + 1e-8)
                    
                    # r_t(θ) = π_new / π_old
                    ratio = np.exp(new_logp - old_logp)
                    
                    # Clipped surrogate
                    surr1 = ratio * A
                    surr2 = np.clip(ratio, 1-self.clip_eps, 1+self.clip_eps) * A
                    actor_loss = -np.minimum(surr1, surr2)  # 取负 → 梯度上升
                    
                    # 手动计算梯度（简化版）
                    grad_log = -probs.copy()
                    grad_log[a] += 1.0
                    
                    # 如果 ratio 被 clip 了，梯度为 0
                    if ratio < 1-self.clip_eps and A < 0:
                        grad_log *= 0  # clipped: 下界外
                    elif ratio > 1+self.clip_eps and A > 0:
                        grad_log *= 0  # clipped: 上界外
                    
                    dWa += np.outer(s, grad_log) * A
                
                self.Wa -= self.lr * dWa / len(batch_states)
                
                # ---- Critic 更新：MSE ----
                V_pred = np.array([self.value(s) for s in batch_states])
                dWc = (V_pred - batch_ret) @ batch_states  # ∇MSE
                self.Wc -= self.lr * dWc / len(batch_states)
```

### PPO 运行流程

```
FOR iteration = 1 to N:
    # --- 收集数据（用当前策略）---
    运行当前策略 π_θ，收集 K 步 (s, a, r, done, logπ_old)
    
    # --- 计算 Advantage ---
    GAE: A_t = δ_t + γ·λ·A_{t+1}
    
    # --- 多 epoch 优化 ---
    FOR epoch = 1 to E:
        从收集的数据中随机采样 batch
        计算 clipped surrogate loss → 梯度更新 Actor
        计算 value loss (MSE) → 梯度更新 Critic
    
    # --- 丢弃旧数据 ---
    清空 buffer，下一轮用新策略重新采集
```

---

## 7. 与量化交易 Agent 的关联

### 7.1 从 DQN/TD(λ) 到 PPO 的进化路径

在量化交易场景中，我们之前尝试的 TD(λ) 表格方法表现不错（+35.91% 超额，-2.5% 回撤），但它有局限：

| 限制 | 表格 TD(λ) | PG / PPO 的优势 |
|------|-----------|----------------|
| 状态离散化 | 25 个离散状态靠手工设计 | 连续状态空间，神经网络自动提取特征 |
| 动作空间 | 固定 3 个 (buy/hold/sell) | 可扩展到连续仓位比例 |
| 随机策略 | ε-贪心有/无确定性 | 输出仓位概率分布，天然平滑 |
| 策略稳定性 | 无显式约束 | PPO 的 clip 天然稳定 |

### 7.2 量化交易的 PPO 适配方案

**状态空间**（连续，不需离散化）：
```
state = [
    过去 N 天的收益率序列（归一化），
    技术指标（RSI, MACD, 均线差），
    持仓比例（当前仓位），
    账户净值变化率，
    市场波动率（如 ATR），
    行业轮动指标
]
```

**动作空间**（两种方案）：
- **离散**：{空仓, 30%仓位, 60%仓位, 满仓} — PPO 输出 softmax
- **连续**：仓位比例 [-1, 1]（允许做空）— PPO 输出高斯分布 $(\mu, \sigma)$

**奖励函数**：
```
r_t = 已实现收益率 - 交易成本 × 调仓量 - α × 波动率惩罚
```

其中波动率惩罚是可选的，PPO 的 GAE 本身就能处理风险调整后的回报。

### 7.3 PPO 在交易中的优势

1. **稳定的策略更新**：clip 机制防止某次大行情导致策略突变（"因为一次大涨就全仓 crypto"）
2. **随机策略**：天然输出仓位概率，可以按概率做多仓分散，而不是硬判断买/卖
3. **GAE 的优势估计**：能更好地分配 credit——是最近几天持仓导致了收益，还是今天的交易导致亏损
4. **连续动作支持**：如果需要输出精确仓位比例（如 37.5%），PPO 的自然输出是高斯分布

### 7.4 将 PPO 集成到 rl_trader.py

当前的 `rl_trader.py` 基于 TD(λ) 表格方法，集成 PPO 的关键改动：

```python
class PPOAgent:
    def __init__(self, state_dim, n_actions):
        # Actor: MLP(state_dim → 64 → 32 → n_actions, softmax)
        # Critic: MLP(state_dim → 64 → 32 → 1)
        # optimizer: Adam
        pass  # 使用上面 PPO 类或 PyTorch 实现
    
    def act(self, state, deterministic=False):
        # 训练模式：按概率采样
        # 测试模式：取概率最大的动作
    
    def store_transition(self, s, a, log_prob, r, done):
        # 存入 rollout buffer
    
    def learn(self):
        # 对 buffer 中的数据进行多 epoch PPO 更新
        # 清空 buffer
```

**预期改进**：
- DQN v1 超额 +9.19%，max DD -12.0%
- TD(λ) 超额 +35.91%，max DD -2.5%
- PPO 理论上能在保持低回撤的同时，通过连续状态空间捕捉更精细的市场信号

### 7.5 需要注意的风险

1. **PPO 是 on-policy**：每次更新要丢弃旧数据重新采集 → 样本效率低于 off-policy 方法
2. **在线环境需求**：PPO 每轮收集一批数据 → 需要回测器（或模拟器）源源不断生成数据
3. **过拟合风险**：PPO 多 epoch 优化 → 在历史数据上可能"死记硬背"，需要充分的随机性（随机时间点、随机起始）
4. **市场非平稳性**：RL 假设 MDP 固定，但市场分布不断变化，可能需要持续微调

---

## 8. 总结

| 概念 | 核心 | 与量化交易的连接点 |
|------|------|------------------|
| **策略梯度** | 直接优化策略 $\pi_\theta(a\|s)$，跳过 Q 值 | 端到端状态 → 仓位决策 |
| **REINFORCE** | MC 回报 $G_t$ 作为评判，高方差 | 基础，样本效率太低 |
| **Baseline** | 减去 $V(s)$ 降低方差 | 用市场"平均表现"做对照 |
| **Actor-Critic** | Actor 决策 + Critic 评判，TD 更新 | 两个网络协同工作 |
| **GAE** | $\lambda$ 平衡偏差-方差 | 处理交易序列的 credit assignment |
| **PPO Clip** | 截断概率比，稳定更新 | 防止策略被极端行情带偏 |
| **重要性采样** | 复用旧数据做多次更新 | 提高历史数据的利用率 |

**下一步**：在 rl_trader.py 中实现 PPOAgent，用连续状态空间替代手工离散化，对比 TD(λ) 的效果差异。

---

**前驱知识**：[RL #1：Introduction & Bandit](./rl_01_intro_bandit.md) | [RL #2：Model-Free & Q-Learning](./rl_02_model_free_q_learning.md) | [RL #3：值函数近似与 DQN](./rl_03_dqn.md)
**系列导航**：[强化学习系列目录](./rl_index.md)
