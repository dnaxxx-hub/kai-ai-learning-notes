# 强化学习 #5：Actor-Critic（A2C / A3C）

> 从策略梯度到 Actor-Critic：当"演员"有了"评论家"指点，学习效率天差地别。

---

## 一、前情回顾：策略梯度的问题

上一章（REINFORCE）的朴素的策略梯度方法：

$$ \nabla J(\theta) = \mathbb{E}_{\tau \sim \pi_\theta} \left[ \sum_{t=0}^{T} \nabla_\theta \log \pi_\theta(a_t|s_t) \cdot G_t \right] $$

### 问题 1：高方差（High Variance）

- $G_t = \sum_{k=t}^{T} \gamma^{k-t} r_k$ 是一个 **采样回报**，每一次 rollout 的 $G_t$ 波动极大
- 同一个 $(s_t, a_t)$ 在不同 trajectory 中可能得到天差地别的 $G_t$
- 结果：训练不稳定，收敛慢，需要海量样本

### 问题 2：样本效率低

- REINFORCE 是 **on-policy** 的：只能用当前策略产生的数据更新，用完就丢
- 每更新一次策略就要重新收集一批 trajectory
- Monte Carlo 回报需要跑到 episode 结束才能计算

### 问题 3：随机梯度 $\nabla_\theta \log \pi_\theta(a_t|s_t) \cdot G_t$ 的无偏估计

虽然无偏，但方差大 → 需要极小的学习率才能稳定训练

### 核心矛盾

用 $G_t$ 作为"这个动作好不好"的评分：
- 评分 = 整个 episode 的累积回报 → **噪声大但无偏**
- 能不能找一个 **低方差** 的评分，即使小有偏也能更快收敛？

---

## 二、Actor-Critic 核心思想

### 两条腿走路

| 组件 | 名称 | 角色 | 输入 → 输出 |
|------|------|------|-------------|
| **Actor** | 演员（策略网络） | 决定动作 | $s \to \pi_\theta(a\|s)$ |
| **Critic** | 评论家（价值网络） | 评价动作好坏 | $s \to V_\phi(s)$ |

### 直觉

- **Actor** = 做决策的人，拿着 Critic 的打分来改进自己的策略
- **Critic** = 裁判，学习评估"当前状态有多好"，给 Actor 提供反馈
- 两者一起训练，互相促进

### 数学形式

原始的梯度更新（使用 $G_t$）：

$$ \nabla J(\theta) = \mathbb{E} \left[ \nabla_\theta \log \pi_\theta(a_t|s_t) \cdot G_t \right] $$

用 Critic 的估计值 **替代** $G_t$：

$$ \nabla J(\theta) \approx \mathbb{E} \left[ \nabla_\theta \log \pi_\theta(a_t|s_t) \cdot \delta_t \right] $$

其中 $\delta_t$ 是 **TD error** 或 **优势函数**（见下一节）。

Critic 自己通过 TD learning 更新：

$$ \mathcal{L}(\phi) = \mathbb{E} \left[ \left( r_t + \gamma V_\phi(s_{t+1}) - V_\phi(s_t) \right)^2 \right] $$

### 为什么这么做？

- $G_t$ 是未来所有奖励的 **无偏估计**，方差大
- $V_\phi(s_t)$ 是价值函数的 **有偏估计**（因为用神经网络近似），方差小
- 用 Critic 代替真实的 $G_t$ → **方差大幅降低**，代价是引入少量偏差
- 偏差 - 方差权衡（Bias-Variance Tradeoff）：稍微有点偏但稳定，比无偏但疯狂震荡要好得多

---

## 三、优势函数：$A(s,a)$ 的引入

### 为什么需要优势函数？

单纯用 $V(s)$ 做 Critic 还不够——我们想知道的是"在这个状态下选这个动作比平均水平好多少"，而不是"这个状态本身有多好"。

### 定义

$$ A^\pi(s_t, a_t) = Q^\pi(s_t, a_t) - V^\pi(s_t) $$

- $Q^\pi(s,a)$ = 在状态 $s$ 执行动作 $a$ 后的期望回报
- $V^\pi(s)$ = 在状态 $s$ 的期望回报（按策略 $\pi$ 平均）
- $A^\pi(s,a) > 0$ → 这个动作比平均水平好 → 增加它的概率
- $A^\pi(s,a) < 0$ → 比平均水平差 → 降低它的概率

> 优势函数回答的核心问题："选这个动作，比随便选个平均动作好多少？"

### 用 TD Error 近似优势

我们不需要分别学习 $Q$ 和 $V$，可以用一个 Critic（只学 $V$）来近似优势：

$$ \hat{A}(s_t, a_t) = r_t + \gamma V_\phi(s_{t+1}) - V_\phi(s_t) $$

这个 $\delta_t$（TD error）实际上就是优势函数的一个 **有偏估计**。

### 为什么优势函数能减少方差？

把策略梯度重写为：

$$ \nabla J(\theta) = \mathbb{E} \left[ \nabla_\theta \log \pi_\theta(a_t|s_t) \cdot A(s_t, a_t) \right] $$

对比原始的 $G_t$：
- $G_t$ 里既包含"这个动作的效果"，也包含"这个状态本身的 baseline"
- $V(s_t)$ 作为 baseline 被减掉后，**只保留动作本身的贡献**
- 方差从 $\text{Var}(G_t)$ 降到 $\text{Var}(G_t - V(s_t))$

**直观理解**：一个学生考了90分（$Q$），班级平均分85（$V$）。只说 90 分看不出好坏（试卷可能很简单），但说"比平均高5分"（$A$）就很清楚了。

---

## 四、A2C：同步版的 Advantage Actor-Critic

### 全称

**A2C** = Advantage Actor-Critic（优势 Actor-Critic）

### 核心改进

#### 1. N步回报（N-step Returns）

单步 TD error 虽然好，但偏差还是大。N步回报在偏差-方差上折中：

$$ \hat{A}^{(n)}(s_t, a_t) = \sum_{k=0}^{n-1} \gamma^k r_{t+k} + \gamma^n V_\phi(s_{t+n}) - V_\phi(s_t) $$

- $n=1$ → 单步 TD（偏差小，方差大）
- $n=\infty$ → Monte Carlo（无偏，方差极大）
- $n$ 适中（通常 5~20）→ **较优的权衡**

#### 2. 多 Worker 同步训练

A2C 的核心架构：

```
┌──────────────────────────────────────┐
│            Global Network            │
│    ┌─────────┐   ┌─────────┐         │
│    │  Actor  │   │ Critic  │         │
│    └────┬────┘   └────┬────┘         │
│         │              │              │
└─────────┼──────────────┼──────────────┘
          │              │
    ┌─────┴──────────────┴─────┐
    │     同步梯度聚合           │
    └─────┬──────────────┬─────┘
          │              │
┌─────────┼──────────────┼─────────────┐
│ Worker1 │   Worker2    │   Worker3   │
│         │              │             │
│ run n   │   run n      │   run n     │
│ steps   │   steps      │   steps     │
│ compute │   compute    │   compute   │
│ grads   │   grads      │   grads     │
└─────────┴──────────────┴─────────────┘
```

关键流程：
1. N 个 worker 各自与环境交互 n 步
2. 每个 worker 计算自己的梯度
3. **所有 worker 同步等待**，梯度汇总后更新全局网络
4. 所有 worker 拉取最新参数，继续下一轮

#### 3. A2C 训练循环

```
for each iteration:
    for each worker w in parallel:
        reset environment, get s_0
        for step t = 0 to n-1:
            a_t ~ π_θ(s_t)               # Actor 选择动作
            s_{t+1}, r_t, done = env.step(a_t)
            store (s_t, a_t, r_t, done)
        
        # 计算 N-step 优势
        R = V_φ(s_n) if not done else 0
        for t = n-1 down to 0:
            R = r_t + γ * R
            A_t = R - V_φ(s_t)           # 优势估计
            accumulate policy gradient
            accumulate value loss
        
        # worker 返回梯度
        send gradients to global network
    
    # 同步更新
    global_network.apply(gradients)
    broadcast new params to all workers
```

#### 4. A2C 的损失函数

Critic 损失（MSE）：

$$ \mathcal{L}_{value} = \frac{1}{n} \sum_{t} \left( R_t - V_\phi(s_t) \right)^2 $$

Actor 损失（带熵正则化鼓励探索）：

$$ \mathcal{L}_{policy} = -\frac{1}{n} \sum_{t} \left[ \log \pi_\theta(a_t|s_t) \cdot A_t + \beta \cdot H(\pi_\theta(\cdot|s_t)) \right] $$

其中 $H(\pi) = -\sum_a \pi(a) \log \pi(a)$ 是策略熵，$\beta$ 控制探索强度。

总损失：

$$ \mathcal{L} = \mathcal{L}_{policy} + c_v \cdot \mathcal{L}_{value} $$

---

## 五、A3C：异步版的优势

### 全称

**A3C** = Asynchronous Advantage Actor-Critic

### 历史地位

- 2016 年 DeepMind 提出（Mnih et al.）
- 深度学习时代的奠基性算法之一
- 首次证明**异步训练**在 RL 中的巨大价值

### 与 A2C 的核心区别

| 维度 | A2C（同步） | A3C（异步） |
|------|-------------|-------------|
| 更新方式 | 所有 worker 算完 → 同步聚合 → 一次更新 | 每个 worker 算完 → **立即更新** 全局网络 |
| 等待 | 需要等待最慢的 worker（同步屏障） | 不用等，各自为战 |
| 参数一致性 | 每个迭代所有 worker 参数一致 | **stale gradients**（用了过时的参数算梯度） |
| 数据多样性 | 多个 worker 提供多样数据 | 多个 worker 提供多样数据 |
| 硬件需求 | 可以 GPU 加速（batch 训练） | 更适合 CPU 多线程 |
| 效果 | 通常比 A3C 更稳定 | 历史意义重大，但 A2C 在实践中更常用 |

### A3C 的异步更新

```
Worker 1 (thread 1):    采样 → 算梯度 → push → pull → 采样 → ...
Worker 2 (thread 2):    采样 → 算梯度 → push → pull → 采样 → ...
Worker 3 (thread 3):    采样 → 算梯度 → push → pull → 采样 → ...
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Global Network    │
                    │  (参数仓库)         │
                    └─────────────────────┘
```

### 关键技巧

每个 worker 维护自己的环境副本和局部参数副本（local copy）：
1. 从全局网络拉取最新参数到 local copy
2. 用 local copy 与环境交互 n 步
3. 计算梯度
4. **异步 push** 到全局网络（可能有多个 worker 同时 push）

### A3C 的历史意义

1. **去中心化训练的先驱**：证明了多个异步探索者可以稳定训练，奠定了分布式 RL 的基础
2. **CPU 友好的训练范式**：不需要 GPU，多 CPU 核即可高效训练
3. **打破数据相关性**：不同 worker 在不同环境中探索，自然产生 de-correlated 数据
4. **探索多样性**：每个 worker 的探索方向不同，自然地覆盖更多状态空间

### 为什么 A2C 后来居上？

实践中人们发现：
- A3C 的 "stale gradients"（过期梯度）理论上会引入噪声
- A2C 去掉异步后，用**批量同步梯度**反而更稳定
- 同步版本可以用 GPU 加速（把多个 worker 的样本打包成 batch）
- A2C 通常和 A3C 一样好，甚至更好，而且实现更简单

> 现在的标准做法是 A2C（同步多 worker），A3C 更多被记入历史。

---

## 六、GAE：广义优势估计

### 问题

- 单步 TD 偏差大（只用了一步 reward，后续全靠 Value 估计）
- N 步 TD 需要选择 $n$，太小的 $n$ 偏差大，太大的 $n$ 方差大
- 能不能 **自动平衡** 不同步长？

### GAE（Generalized Advantage Estimation）

Schulman et al., 2016 — 用指数加权平均融合所有 n 步优势估计：

定义单步 TD error：

$$ \delta_t = r_t + \gamma V(s_{t+1}) - V(s_t) $$

GAE 的核心公式：

$$ \hat{A}^{GAE(\gamma, \lambda)}_t = \sum_{l=0}^{\infty} (\gamma\lambda)^l \delta_{t+l} $$

### 直觉

- **$\lambda = 0$** = 只用一步 TD：$\hat{A}_t = \delta_t$（高偏差，低方差）
- **$\lambda = 1$** = MC 回报：$\hat{A}_t = \sum_{l} \gamma^l \delta_{t+l} = G_t - V(s_t)$（低偏差，高方差）
- **$0 < \lambda < 1$** = 指数衰减的折中

```
λ = 0 ──────────────► λ = 1
  高偏差/低方差         低偏差/高方差
  (纯TD)                (纯MC)
  
        ←── 实际使用 ──→
        λ 通常在 0.9~0.99
```

### 计算实现（非常优雅）

在实际编码中，GAE 可以高效地**反向递归**计算：

```python
def compute_gae(rewards, values, next_value, dones, gamma=0.99, lam=0.95):
    """
    rewards: list of n rewards
    values: list of n state values
    next_value: V(s_{n}), 终结态为 0
    dones: list of boolean terminated flags
    """
    advantages = []
    gae = 0
    for t in reversed(range(len(rewards))):
        delta = rewards[t] + gamma * next_value * (1 - dones[t]) - values[t]
        gae = delta + gamma * lam * (1 - dones[t]) * gae
        advantages.insert(0, gae)
        next_value = values[t]
    returns = [adv + val for adv, val in zip(advantages, values)]
    return advantages, returns
```

### 为什么 GAE 如此重要？

- **只需一个超参数 $\lambda$** 就能精细控制偏差-方差权衡
- 在实践中极其稳定，几乎是现代 Actor-Critic 方法（PPO、TRPO）的标准配置
- 训练时通常固定 $n$ 步长度（如 2048），用 GAE($\lambda$) 计算优势，兼顾效率和质量

---

## 七、完整代码：CartPole 上的 A2C

以下是一个完整可运行的 A2C 实现，在 CartPole-v1 上训练：

```python
"""
A2C (Advantage Actor-Critic) for CartPole-v1
同步版，单 worker（展示核心逻辑）
"""

import gym
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
from collections import deque
import random

# ── 设置随机种子 ──
SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)


# ════════════════════════════════════════
# 1. Actor-Critic 网络
# ════════════════════════════════════════
class ActorCritic(nn.Module):
    """
    共享 backbone + 双头输出：
    - Actor head: 输出动作概率分布（softmax）
    - Critic head: 输出状态价值 V(s)
    """
    def __init__(self, state_dim, action_dim, hidden_dim=128):
        super().__init__()
        # 共享特征提取层
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)

        # Actor 头：输出动作 logits
        self.actor = nn.Linear(hidden_dim, action_dim)

        # Critic 头：输出标量价值
        self.critic = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        action_logits = self.actor(x)          # [batch, action_dim]
        state_value = self.critic(x)           # [batch, 1]
        return action_logits, state_value

    def act(self, state):
        """给定状态，返回动作和 log 概率"""
        state = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            logits, value = self.forward(state)
            probs = F.softmax(logits, dim=-1)
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            log_prob = dist.log_prob(action)
        return action.item(), log_prob.item(), value.item()


# ════════════════════════════════════════
# 2. A2C Agent
# ════════════════════════════════════════
class A2CAgent:
    def __init__(
        self,
        state_dim,
        action_dim,
        hidden_dim=128,
        lr=3e-4,
        gamma=0.99,
        n_steps=5,              # N-step 长度
        value_coef=0.5,         # Value loss 系数
        entropy_coef=0.01,      # 熵正则化系数
        max_grad_norm=0.5,      # 梯度裁剪
    ):
        self.gamma = gamma
        self.n_steps = n_steps
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.max_grad_norm = max_grad_norm

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = ActorCritic(state_dim, action_dim, hidden_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)

        # 经验缓冲区（n步）
        self.states = []
        self.actions = []
        self.rewards = []
        self.next_states = []
        self.dones = []
        self.log_probs = []
        self.values = []

    def reset_buffer(self):
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.next_states.clear()
        self.dones.clear()
        self.log_probs.clear()
        self.values.clear()

    def store_transition(self, s, a, r, s_next, done, log_prob, value):
        self.states.append(s)
        self.actions.append(a)
        self.rewards.append(r)
        self.next_states.append(s_next)
        self.dones.append(done)
        self.log_probs.append(log_prob)
        self.values.append(value)

    def compute_gae(self, next_value):
        """计算 GAE(λ) 优势估计"""
        # 这里使用简化版：N-step 优势
        rewards = np.array(self.rewards)
        values = np.array(self.values)
        dones = np.array(self.dones)

        returns = np.zeros_like(rewards)
        R = next_value
        for t in reversed(range(len(rewards))):
            R = rewards[t] + self.gamma * R * (1 - dones[t])
            returns[t] = R

        advantages = returns - values
        return advantages, returns

    def learn(self):
        """从缓冲区采样并更新网络"""
        if len(self.states) < self.n_steps:
            return

        # 计算最后一个 next_state 的 value（bootstrapping）
        next_state = torch.FloatTensor(self.next_states[-1]).unsqueeze(0).to(self.device)
        with torch.no_grad():
            _, next_value = self.model(next_state)
            next_value = next_value.item()

        # 计算优势
        advantages, returns = self.compute_gae(next_value)

        # 转为 tensor
        states = torch.FloatTensor(np.array(self.states)).to(self.device)
        actions = torch.LongTensor(np.array(self.actions)).to(self.device)
        old_log_probs = torch.FloatTensor(np.array(self.log_probs)).to(self.device)
        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)

        # 归一化优势（稳定训练的小技巧）
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # 前向传播
        logits, values = self.model(states)
        probs = F.softmax(logits, dim=-1)
        dist = torch.distributions.Categorical(probs)

        # Actor 损失
        new_log_probs = dist.log_prob(actions)
        ratio = torch.exp(new_log_probs - old_log_probs)
        policy_loss = -(advantages * new_log_probs).mean()

        # 熵 bonus（鼓励探索）
        entropy = dist.entropy().mean()
        entropy_loss = -self.entropy_coef * entropy

        # Critic 损失
        values = values.squeeze()
        value_loss = F.mse_loss(values, returns)

        # 总损失
        total_loss = policy_loss + self.value_coef * value_loss + entropy_loss

        # 反向传播
        self.optimizer.zero_grad()
        total_loss.backward()
        nn.utils.clip_grad_norm_(self.model.parameters(), self.max_grad_norm)
        self.optimizer.step()

        # 清空缓冲区
        self.reset_buffer()

        return {
            'policy_loss': policy_loss.item(),
            'value_loss': value_loss.item(),
            'entropy': entropy.item(),
            'total_loss': total_loss.item(),
        }


# ════════════════════════════════════════
# 3. 训练循环
# ════════════════════════════════════════
def train_a2c(
    env_name="CartPole-v1",
    n_episodes=1000,
    n_steps=5,
    gamma=0.99,
    lr=3e-4,
    render=False,
    print_interval=20,
):
    env = gym.make(env_name)
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n

    agent = A2CAgent(
        state_dim=state_dim,
        action_dim=action_dim,
        n_steps=n_steps,
        gamma=gamma,
        lr=lr,
    )

    episode_rewards = []
    running_reward = None

    for episode in range(1, n_episodes + 1):
        state, _ = env.reset()
        episode_reward = 0
        done = False

        while not done:
            # Actor 选择动作
            action, log_prob, value = agent.model.act(state)

            # 环境交互
            next_state, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated

            # 存储一步经验
            agent.store_transition(
                state, action, reward, next_state, done,
                log_prob, value
            )

            state = next_state
            episode_reward += reward

            # 每 n_steps 或 episode 结束时更新
            if len(agent.states) >= n_steps or done:
                agent.learn()

            if render:
                env.render()

        episode_rewards.append(episode_reward)
        running_reward = episode_reward if running_reward is None else (
            0.95 * running_reward + 0.05 * episode_reward
        )

        if episode % print_interval == 0:
            avg_reward = np.mean(episode_rewards[-print_interval:])
            print(f"Episode {episode:4d} | "
                  f"Avg Reward: {avg_reward:5.1f} | "
                  f"Running Reward: {running_reward:5.1f} | "
                  f"Epsilon: N/A (A2C)")

        # CartPole 达到 500 即为 solved
        if running_reward is not None and running_reward >= 450:
            print(f"\n🎉 Solved at episode {episode}! (running reward = {running_reward:.1f})")
            break

    env.close()
    return episode_rewards


# ════════════════════════════════════════
# 4. 多 Worker A2C（A2C 的威力所在）
# ════════════════════════════════════════
class MultiWorkerA2C:
    """
    多 Worker A2C 的简化实现（非并行，但逻辑相同）
    实际并行时使用 Python multiprocessing 启动 N 个 worker
    """
    def __init__(self, env_name="CartPole-v1", n_workers=4, **kwargs):
        self.n_workers = n_workers
        self.envs = [gym.make(env_name) for _ in range(n_workers)]
        state_dim = self.envs[0].observation_space.shape[0]
        action_dim = self.envs[0].action_space.n
        self.agent = A2CAgent(state_dim, action_dim, **kwargs)

    def train(self, n_episodes=1000):
        # ... 并行训练逻辑（实际用多进程）
        pass


# ════════════════════════════════════════
# 5. 运行
# ════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("Training A2C on CartPole-v1")
    print("=" * 50)

    rewards = train_a2c(
        env_name="CartPole-v1",
        n_episodes=500,
        n_steps=5,
        gamma=0.99,
        lr=3e-4,
        print_interval=20,
    )

    print(f"\nTraining complete! Final 100-episode avg: {np.mean(rewards[-100:]):.2f}")
```

### 运行方式

```bash
pip install gym torch numpy
python a2c_cartpole.py
```

### 预期效果

- CartPole-v1 通常在 **200~400 个 episode** 左右达到 500 分
- 相比 REINFORCE（通常 500~1000+ episodes），A2C 收敛**快 2~3 倍**
- 更稳定，reward 曲线震荡更小

---

## 八、与 DQN 的对比

| 维度 | DQN | Actor-Critic (A2C) |
|------|-----|--------------------|
| **类型** | Value-based | Policy-based + Value-based |
| **学习方式** | 学习 $Q(s,a)$，由 $Q$ 隐式导出策略 | 直接学习策略 $\pi(a\|s)$ + 价值 $V(s)$ |
| **策略形式** | 确定性（$\epsilon$-greedy 近似随机） | **随机策略**（输出分布） |
| **动作空间** | ✅ 离散 ✓ | ✅ 离散 ✓ / ✅ **连续** ✓ |
| **On/Off-policy** | **Off-policy**（用经验回放） | **On-policy**（数据用完即弃） |
| **样本效率** | 高（复用历史数据） | 低（on-policy 限制） |
| **稳定性** | 需要 target network + 经验回放 | 天然更稳定（随机策略自正则化） |
| **收敛理论** | 可能发散（函数近似 + off-policy） | 更接近 true gradient 下降 |
| **实现复杂度** | 中等 | 稍复杂（双网络 + 优势计算） |
| **适合场景** | 高维状态 + 离散动作（如 Atari） | 连续控制、机器人、需要随机策略的场景 |

### 核心差异详解

#### 1. On-policy vs Off-policy

```
DQN:          旧数据 (s,a,r,s') → replay buffer → 可反复训练
A2C:          旧数据 (s,a,r,s') → 用一次就扔 → 必须重新采集
```

- DQN 用经验回放池复用数据，样本效率更高
- A2C on-policy 保证梯度的无偏性，但数据效率低
- PPO 通过重要性采样做了一定程度的 off-policy 近似，但仍不如 DQN 高效

#### 2. 连续动作空间

这是 Actor-Critic **碾压** DQN 的地方：

- **DQN**：需要 $\max_a Q(s,a)$，对连续动作空间不可能枚举 → 需要额外技巧（NAF、DDPG）
- **Actor-Critic**：Actor 直接输出动作（均值 + 方差），天然支持连续空间

对于连续控制任务（机器人、自动驾驶），Actor-Critic 及其衍生方法（DDPG、SAC、PPO）是主流。

#### 3. 随机策略 vs 确定性策略

- **DQN**：$\epsilon$-greedy 是一种简单的近似随机策略，但本质上学习的还是确定性 $Q$
- **Actor-Critic**：Actor 输出动作概率分布 $\pi(a|s)$，天然是随机策略
- 随机策略的优势：
  - 自然探索（概率低的动作也有机会被选中）
  - 应对带部分可观测性的环境（POMDP）
  - 多模态动作分布（同样的状态可能有多种好动作）

#### 4. Bias - Variance Profile

```
DQN 的 Q-learning:  高偏差（max 算子 + bootstrap），无方差（确定性）
Actor-Critic:       可调偏差-方差（通过 λ、n-step 控制）
```

---

## 九、总结与脉络

### 演化路径

```
REINFORCE (MC Policy Gradient)
    │ 问题：高方差、样本效率低
    ▼
REINFORCE with Baseline
    │ 引入 V(s) 作为 baseline 减少方差
    ▼
Actor-Critic (TD-based)
    │ 用 Critic 网络代替 MC 回报
    │ 引入 TD error 作为优势
    ▼
A2C / A3C (2016)
    │ 多 worker 并行采样
    │ N-step + 优势函数
    ▼
GAE (Schulman 2016)
    │ 广义优势估计，精细控制 Bias-Variance
    ▼
PPO / TRPO (> Actor-Critic 的最新迭代)
    │ 约束策略更新幅度，解决 on-policy 的稳定性问题
    ▼
SAC (Soft Actor-Critic)
    │ 最大熵框架，off-policy Actor-Critic，SOTA
```

### 核心收获

| 概念 | 一句话总结 |
|------|-----------|
| **Actor** | 策略网络，输出动作分布，负责探索和决策 |
| **Critic** | 价值网络，提供低方差的动作评估信号 |
| **优势函数** | "这个动作比平均好多少"，是策略梯度的关键信号 |
| **N-step** | 平衡偏差-方差：用 n 步真实 reward + bootstrapping |
| **A2C** | 同步多 worker，各算各的梯度，集中更新 |
| **A3C** | 异步多 worker，各算各的，谁先算完谁更新全局 |
| **GAE** | 用 $\lambda$ 平滑融合所有步长的优势估计 |

### 当你要选择 A2C vs DQN

```
┌─ 动作空间是？ ───────────────────────┐
│                                      │
│  连续 ──────► Actor-Critic (必须)    │
│                                      │
│  离散 ──────► 数据多、样本宝贵？      │
│               是 → DQN               │
│               否 → A2C/PPO 也 OK     │
│                                      │
│  需要随机策略？                      │
│   (部分观测/多模态最优)              │
│   是 → Actor-Critic                  │
│                                      │
└──────────────────────────────────────┘
```

---

### 参考资源

- [Asynchronous Methods for Deep Reinforcement Learning (A3C), Mnih et al. 2016](https://arxiv.org/abs/1602.01783)
- [High-Dimensional Continuous Control Using Generalized Advantage Estimation (GAE), Schulman et al. 2016](https://arxiv.org/abs/1506.02438)
- [OpenAI Spinning Up - A2C](https://spinningup.openai.com/en/latest/algorithms/a2c.html)
- Sutton & Barto, *Reinforcement Learning: An Introduction*, Chapter 13
- [Understanding Actor Critic Methods - Lil'Log](https://lilianweng.github.io/posts/2018-04-08-policy-gradient/)
