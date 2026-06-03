# RL#4：Actor-Critic 方法 — 从策略梯度到A3C/SAC

> ⭐ 难度：高级 | 预计阅读：40分钟 | 配套代码：`rl_04_ac_demo.py`

## 1. 为什么需要 Actor-Critic？

### 1.1 纯策略梯度（REINFORCE）的问题

- **高方差**：MC回报 $G_t$ 方差大，学习不稳定
- **样本效率低**：每episode只更新一次，抛弃了中间信息
- **无信用分配**：无法区分「好动作」和「运气好」

### 1.2 纯价值方法（DQN）的问题

- **离散动作限制**：不能直接处理连续动作空间
- **策略退化**：微小Q值变化可能导致完全不同的动作选择
- **过估计**：$Q(s,a) = r + \gamma \max_{a'} Q(s',a')$ 天然高估

### 1.3 Actor-Critic 的解决思路

```
纯PG:  π(a|s) ← ∇log π * G_t       (用完整回报更新)
纯DQN: Q(s,a) ← r + γ max Q(s',a') (用TD误差更新)
A-C:   π(a|s) ← ∇log π * δ         (用TD误差更新)
       V(s)   ← δ                   (同时学习价值函数)
```

**Actor** = 策略网络 $\pi(a|s)$ — 决定「做什么」
**Critic** = 价值网络 $V(s)$ — 评价「做得好不好」

Critic 提供低方差的TD误差作为Actor的学习信号，同时Actor的探索行为产生Critic需要的数据。

---

## 2. 基础 Actor-Critic（单步TD）

### 2.1 算法流程

```
初始化策略网络 π_θ、价值网络 V_φ
对于每个episode:
  初始化状态 s
  while not done:
    从 π_θ(.|s) 采样动作 a
    执行 a，观察 r, s'
    δ = r + γV_φ(s') - V_φ(s)          # TD误差
    ∇θ = ∇log π_θ(a|s) * δ              # 策略梯度
    θ ← θ + α_θ * ∇θ                    # 更新Actor
    φ ← φ + α_φ * ∇V_φ(s) * δ           # 更新Critic（最小化TD误差²）
    s ← s'
```

### 2.2 为什么TD误差比MC回报好？

**MC回报：**
$$G_t = r_t + \gamma r_{t+1} + \gamma^2 r_{t+2} + \cdots$$
- 无偏但高方差（需要完整episode，累积随机性）

**TD误差：**
$$\delta_t = r_t + \gamma V(s_{t+1}) - V(s_t)$$
- 有偏但低方差（单步估计，V的估计引入偏差）
- 偏差-方差权衡中偏方差侧

**n步回报（折中）：**
$$G_t^{(n)} = r_t + \gamma r_{t+1} + \cdots + \gamma^{n-1} r_{t+n-1} + \gamma^n V(s_{t+n})$$

### 2.3 代码实现

```python
"""rl_04_ac_demo.py — Actor-Critic 从零实现"""

import numpy as np
import gymnasium as gym
from collections import deque
import matplotlib.pyplot as plt

class ActorCritic:
    """
    双网络 Actor-Critic (离散动作)
    - Actor: softmax policy
    - Critic: linear V(s)
    """
    
    def __init__(self, state_dim, action_dim, lr_actor=0.01, lr_critic=0.01, gamma=0.99):
        self.gamma = gamma
        self.action_dim = action_dim
        
        # Actor: θ (state_dim × action_dim) → softmax policy
        self.theta = np.random.randn(state_dim, action_dim) * 0.01
        self.lr_actor = lr_actor
        
        # Critic: w (state_dim,) → V(s) = w^T s
        self.w = np.random.randn(state_dim) * 0.01
        self.lr_critic = lr_critic
        
    def _softmax(self, logits):
        """数值稳定的softmax"""
        logits = logits - np.max(logits)
        exp = np.exp(logits)
        return exp / (np.sum(exp) + 1e-10)
    
    def get_action(self, state):
        """从策略采样动作"""
        logits = state @ self.theta  # (action_dim,)
        probs = self._softmax(logits)
        return np.random.choice(self.action_dim, p=probs), probs
    
    def get_value(self, state):
        """Critic 估计状态价值"""
        return state @ self.w
    
    def update(self, state, action, reward, next_state, done):
        """单步TD更新"""
        v = self.get_value(state)
        v_next = self.get_value(next_state) if not done else 0.0
        
        # TD误差
        td_error = reward + self.gamma * v_next - v
        
        # 更新 Critic（梯度下降：最小化 TD 误差²）
        # ∇_w (1/2 * δ²) = -δ * ∇_w V(s) = -δ * s
        self.w += self.lr_critic * td_error * state
        
        # 更新 Actor（策略梯度）
        # ∇θ log π(a|s) * δ
        logits = state @ self.theta
        probs = self._softmax(logits)
        
        # ∇θ log π(a|s) = s^T * (1_{a} - π(.|s))
        # 对应每个 θ_{:,j}: s * (1_{a=j} - π_j)
        grad_actor = np.outer(state, -probs)  # 负号来自 -π_j
        grad_actor[:, action] += state         # 加上 1_{a=j} * s
        
        self.theta += self.lr_actor * td_error * grad_actor


def train_cartpole():
    """在 CartPole 上训练 Actor-Critic"""
    env = gym.make("CartPole-v1")
    agent = ActorCritic(
        state_dim=4, action_dim=2,
        lr_actor=0.005, lr_critic=0.01, gamma=0.99
    )
    
    rewards = []
    recent = deque(maxlen=20)
    
    for episode in range(500):
        state, _ = env.reset()
        ep_reward = 0
        
        while True:
            action, probs = agent.get_action(state)
            next_state, reward, terminated, truncated, _ = env.step(action)
            done = terminated or truncated
            
            agent.update(state, action, reward, next_state, done)
            
            ep_reward += reward
            state = next_state
            if done:
                break
        
        recent.append(ep_reward)
        rewards.append(ep_reward)
        
        if episode % 50 == 0:
            avg = np.mean(recent)
            print(f"Episode {episode:3d} | Reward: {ep_reward:3d} | Avg(20): {avg:.1f}")
    
    return rewards


if __name__ == "__main__":
    print("=" * 55)
    print("  Actor-Critic: CartPole-v1")
    print("=" * 55)
    
    rewards = train_cartpole()
    
    print(f"\n训练完成！最终20轮平均: {np.mean(rewards[-20:]):.1f}")
    print(f"最佳单轮: {max(rewards)}")
    
    # 简单绘图
    plt.figure(figsize=(10, 4))
    plt.plot(rewards, alpha=0.6, label='Episode Reward')
    # 移动平均
    if len(rewards) > 20:
        ma = np.convolve(rewards, np.ones(20)/20, mode='valid')
        plt.plot(range(19, len(rewards)), ma, 'g-', label='MA(20)')
    plt.xlabel('Episode'); plt.ylabel('Total Reward')
    plt.title('Actor-Critic on CartPole-v1')
    plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig('rl_04_cartpole_ac.png', dpi=150)
    print("  图表已保存: rl_04_cartpole_ac.png")
```

---

## 3. 优势函数：从V到A

### 3.1 为什么需要优势函数？

基础AC使用 $V(s)$ 本身作为基线：
$$\nabla J \approx \mathbb{E}[\nabla\log\pi(a|s) \cdot (Q(s,a) - V(s))]$$

但 $Q(s,a) - V(s)$ 比单步TD误差更精确地衡量「这个动作比平均好多少」。

**优势函数定义：**
$$A(s,a) = Q(s,a) - V(s)$$

**用TD误差估计优势：**
$$\hat{A}(s,a) = r + \gamma V(s') - V(s) = \delta$$

单步优势 = TD误差，多步优势 = TD误差的n步累积：

$$\hat{A}^{(n)}_t = \sum_{k=0}^{n-1} \gamma^k \delta_{t+k}$$

### 3.2 GAE（Generalized Advantage Estimation）

**核心思想**：用权重指数衰减的方式综合所有n步优势估计：

$$\hat{A}^{\text{GAE}(\lambda,\gamma)}_t = \sum_{l=0}^\infty (\gamma\lambda)^l \delta_{t+l}$$

其中：
- $\gamma$ = 折扣因子（长期 vs 短期）
- $\lambda$ = GAE参数（偏差 vs 方差）
  - $\lambda = 0$：只用单步TD（高偏差，低方差）
  - $\lambda = 1$：用完整MC回报（低偏差，高方差）
  - $\lambda = 0.95$：典型折中

**为什么GAE效果好？**
```
MC(λ=1):    高方差 + 低偏差  ← 偏向蒙特卡洛
TD(λ=0):    低方差 + 高偏差  ← 偏向时序差分
GAE(0.95):  偏差-方差的帕累托最优
```

### 3.3 GAE实现

```python
def compute_gae(rewards, values, gamma=0.99, lam=0.95):
    """
    GAE(λ) 优势估计
    rewards: [r_0, r_1, ..., r_{T-1}]
    values:  [v_0, v_1, ..., v_{T-1}, v_T]  (包含最后一个状态)
    """
    T = len(rewards)
    advantages = np.zeros(T)
    gae = 0.0
    
    for t in reversed(range(T)):
        delta = rewards[t] + gamma * values[t+1] - values[t]
        gae = delta + gamma * lam * gae
        advantages[t] = gae
    
    # returns = advantages + values[:-1] (用于Critic更新)
    returns = advantages + values[:T]
    
    return advantages, returns
```

---

## 4. A2C（Advantage Actor-Critic）

### 4.1 A2C vs A3C

| 特性 | A3C（Asynchronous） | A2C（Synchronous） |
|------|---------------------|-------------------|
| worker | 多个独立worker异步更新 | 多个worker同步等齐 |
| 梯度 | 各自更新全局参数 | 平均后更新 |
| 硬件需求 | 低（单CPU可跑） | 稍高（需要等待） |
| 效率 | worker可能用过期参数 | 参数一致性好 |
| 实践 | 较复杂、已基本被取代 | 更简单、效果相当 |

**现在基本上都用A2C代替A3C。**

### 4.2 A2C损失函数

**Actor损失（策略梯度）：**
$$\mathcal{L}_\pi = -\mathbb{E}[\log \pi_\theta(a|s) \cdot \hat{A}(s,a)]$$

加上**熵正则化**（鼓励探索）：
$$\mathcal{L}_\pi = -\mathbb{E}[\log \pi_\theta(a|s) \cdot \hat{A}(s,a) + \beta \cdot H(\pi_\theta(\cdot|s))]$$

**Critic损失（价值函数）：**
$$\mathcal{L}_V = \mathbb{E}[(V_\phi(s) - \hat{R}_t)^2]$$

其中 $\hat{R}_t = \hat{A}_t + V_\phi(s)$（GAE优势 + 基线）。

### 4.3 A2C完整实现

```python
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

class A2CNetwork(nn.Module):
    """共享特征提取层的 Actor-Critic 网络"""
    
    def __init__(self, state_dim, action_dim, hidden=128):
        super().__init__()
        self.features = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
        )
        self.actor = nn.Linear(hidden, action_dim)   # policy logits
        self.critic = nn.Linear(hidden, 1)           # V(s)
    
    def forward(self, x):
        features = self.features(x)
        logits = self.actor(features)
        value = self.critic(features)
        return logits, value


class A2CAgent:
    """
    A2C Agent with GAE(λ)
    - 共享特征提取的 Actor-Critic 网络
    - 支持连续/离散动作空间（此处为离散）
    """
    
    def __init__(self, state_dim, action_dim, lr=3e-4, gamma=0.99, lam=0.95, entropy_beta=0.01):
        self.gamma = gamma
        self.lam = lam
        self.entropy_beta = entropy_beta
        
        self.net = A2CNetwork(state_dim, action_dim)
        self.optimizer = optim.Adam(self.net.parameters(), lr=lr)
    
    def get_action(self, state, deterministic=False):
        """从策略采样动作（同时返回log prob和熵）"""
        state = torch.FloatTensor(state).unsqueeze(0)
        logits, value = self.net(state)
        
        if deterministic:
            action = torch.argmax(logits, dim=1)
            return action.item(), 0.0
        
        probs = F.softmax(logits, dim=1)
        dist = torch.distributions.Categorical(probs)
        action = dist.sample()
        
        return action.item(), dist.log_prob(action), dist.entropy()
    
    def update(self, states, actions, rewards, next_states, dones):
        """批量更新"""
        states = torch.FloatTensor(states)
        actions = torch.LongTensor(actions).unsqueeze(1)
        rewards = torch.FloatTensor(rewards)
        dones = torch.FloatTensor(dones)
        
        # 获取价值和动作概率
        logits, values = self.net(states)
        _, next_values = self.net(torch.FloatTensor(next_states))
        
        # TD目标
        targets = rewards + self.gamma * next_values.squeeze() * (1 - dones)
        advantages = targets - values.squeeze()
        
        # Critic损失 (MSE)
        critic_loss = advantages.pow(2).mean()
        
        # Actor损失 (策略梯度 + 熵正则)
        probs = F.softmax(logits, dim=1)
        dist = torch.distributions.Categorical(probs)
        log_probs = dist.log_prob(actions.squeeze())
        actor_loss = -(log_probs * advantages.detach()).mean()
        
        # 熵（鼓励探索）
        entropy = dist.entropy().mean()
        total_loss = actor_loss + 0.5 * critic_loss - self.entropy_beta * entropy
        
        # 反向传播
        self.optimizer.zero_grad()
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.net.parameters(), max_norm=0.5)
        self.optimizer.step()
        
        return {
            'actor_loss': actor_loss.item(),
            'critic_loss': critic_loss.item(),
            'entropy': entropy.item(),
            'advantage_mean': advantages.mean().item(),
        }
```

---

## 5. PPO（Proximal Policy Optimization）

### 5.1 为什么要clip？

A2C的问题：**策略更新步长难控制**。
- 学习率太小 → 更新慢
- 学习率太大 → 一次更新就毁了策略

**PPO的核心思想**：限制每次更新的幅度。

### 5.2 PPO-Clip 目标函数

$$\mathcal{L}^{\text{CLIP}}(\theta) = \mathbb{E}[\min(r_t(\theta) \hat{A}_t, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon) \hat{A}_t)]$$

其中：
- $r_t(\theta) = \frac{\pi_\theta(a_t|s_t)}{\pi_{\theta_{old}}(a_t|s_t)}$ — 新旧策略比率
- $\epsilon = 0.2$ — clip范围
- 当 $A_t > 0$（好动作）：鼓励增大 $r_t$，但不超过 $1+\epsilon$
- 当 $A_t < 0$（差动作）：鼓励减小 $r_t$，但不超过 $1-\epsilon$

**直观理解：**
```
好动作(A>0):  想多选它，但限制不能太贪心 → 概率最多增大20%
差动作(A<0):  想少选它，但限制不能太激进 → 概率最多减小20%
```

### 5.3 PPO完整实现

```python
class PPOAgent:
    """
    PPO-Clip Agent
    - 多epoch更新（每个batch跑K个epoch）
    - 重要性采样比率截断
    - 自适应KL惩罚
    """
    
    def __init__(self, state_dim, action_dim, lr=3e-4, gamma=0.99, lam=0.95,
                 clip_epsilon=0.2, epochs=10, batch_size=64):
        self.gamma = gamma
        self.lam = lam
        self.clip_epsilon = clip_epsilon
        self.epochs = epochs
        self.batch_size = batch_size
        
        self.net = A2CNetwork(state_dim, action_dim)
        self.optimizer = optim.Adam(self.net.parameters(), lr=lr)
    
    def collect_rollout(self, env, steps=2048):
        """收集一轨数据"""
        states, actions, rewards, dones, next_states, log_probs_old = [], [], [], [], [], []
        
        state, _ = env.reset()
        for _ in range(steps):
            state_t = torch.FloatTensor(state).unsqueeze(0)
            logits, _ = self.net(state_t)
            probs = F.softmax(logits, dim=1)
            dist = torch.distributions.Categorical(probs)
            
            action = dist.sample()
            log_prob = dist.log_prob(action)
            
            next_state, reward, terminated, truncated, _ = env.step(action.item())
            done = terminated or truncated
            
            states.append(state)
            actions.append(action.item())
            rewards.append(reward)
            dones.append(done)
            next_states.append(next_state)
            log_probs_old.append(log_prob.detach())
            
            state = next_state
            if done:
                state, _ = env.reset()
        
        return {
            'states': np.array(states),
            'actions': np.array(actions),
            'rewards': np.array(rewards),
            'dones': np.array(dones),
            'next_states': np.array(next_states),
            'log_probs_old': torch.cat(log_probs_old),
        }
    
    def compute_gae(self, rewards, states, next_states, dones):
        """GAE(λ) 优势估计"""
        with torch.no_grad():
            _, values = self.net(torch.FloatTensor(states))
            _, next_values = self.net(torch.FloatTensor(next_states))
            values = values.squeeze().numpy()
            next_values = next_values.squeeze().numpy()
        
        advantages = np.zeros_like(rewards)
        returns = np.zeros_like(rewards)
        gae = 0.0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                delta = rewards[t] + self.gamma * next_values[t] * (1 - dones[t]) - values[t]
            else:
                delta = rewards[t] + self.gamma * values[t+1] * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.lam * gae * (1 - dones[t])
            advantages[t] = gae
            returns[t] = advantages[t] + values[t]
        
        return advantages, returns
    
    def update(self, rollout):
        """PPO核心更新（多epoch）"""
        states = torch.FloatTensor(rollout['states'])
        actions = torch.LongTensor(rollout['actions']).unsqueeze(1)
        advantages, returns = self.compute_gae(
            rollout['rewards'], rollout['states'],
            rollout['next_states'], rollout['dones']
        )
        advantages = torch.FloatTensor(advantages)
        returns = torch.FloatTensor(returns)
        
        # 多epoch优化
        dataset_size = len(states)
        for _ in range(self.epochs):
            indices = np.random.permutation(dataset_size)
            for start in range(0, dataset_size, self.batch_size):
                idx = indices[start:start + self.batch_size]
                
                batch_states = states[idx]
                batch_actions = actions[idx]
                batch_advantages = advantages[idx]
                batch_returns = returns[idx]
                
                logits, values = self.net(batch_states)
                probs = F.softmax(logits, dim=1)
                dist = torch.distributions.Categorical(probs)
                
                log_probs = dist.log_prob(batch_actions.squeeze())
                entropy = dist.entropy().mean()
                
                # 重要性采样比率
                ratio = torch.exp(log_probs - rollout['log_probs_old'][idx])
                
                # PPO-Clip目标
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * batch_advantages
                actor_loss = -torch.min(surr1, surr2).mean()
                
                # Critic损失
                critic_loss = F.mse_loss(values.squeeze(), batch_returns)
                
                # 总损失
                total_loss = actor_loss + 0.5 * critic_loss - 0.01 * entropy
                
                self.optimizer.zero_grad()
                total_loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), 0.5)
                self.optimizer.step()
    
    def train(self, env, total_steps=1_000_000):
        """完整训练循环"""
        steps = 0
        episode = 0
        rewards = []
        
        while steps < total_steps:
            rollout = self.collect_rollout(env)
            self.update(rollout)
            steps += len(rollout['states'])
            episode += 1
            
            if episode % 10 == 0:
                avg = np.mean(rollout['rewards'])
                print(f"Steps {steps:7d} | Avg Reward: {avg:.2f} | Episode {episode}")
```

---

## 6. SAC（Soft Actor-Critic）

### 6.1 SAC的核心理念

**最大熵强化学习**：
$$\pi^* = \arg\max_\pi \mathbb{E} \left[ \sum_t \gamma^t (r_t + \alpha H(\pi(\cdot|s_t))) \right]$$

不只是最大化累积奖励，还最大化**策略的熵** → 鼓励探索和鲁棒性。

### 6.2 SAC vs PPO

| 特性 | PPO | SAC |
|------|-----|-----|
| 策略 | on-policy | off-policy（可重用旧数据） |
| 样本效率 | 低 | 高 |
| 动作空间 | 离散+连续 | 主要连续 |
| 温度参数 | 无 | $\alpha$（自动调节） |
| 目标网络 | 无 | 有（双Q网络） |
| 典型应用 | 游戏、机器人 | 机器人控制、自动驾驶 |

### 6.3 SAC五个网络

```
Q_θ1(s,a)    — Q网络1（主）
Q_θ2(s,a)    — Q网络2（减小过估计）
Q_θ1_target  — 目标Q网络1
Q_θ2_target  — 目标Q网络2  
π_φ(a|s)     — 策略网络（输出高斯分布参数）
α            — 温度参数（可学习）
```

### 6.4 最小化Q过估计：Clipped Double-Q

SAC的Q更新取两个Q的最小值：
$$y = r + \gamma (\min_{i=1,2} Q_{\theta_i'}(s', a') - \alpha \log \pi_\phi(a'|s'))$$

这和TD3的思路一样。

### 6.5 温度α的自动调节

**目标**：维持策略熵接近目标值 $\bar{H}$。

$$\mathcal{L}(\alpha) = -\alpha \mathbb{E}[\log \pi_\phi(a|s) + \bar{H}]$$

直觉：
- 如果熵太低 → $\mathcal{L}$ 梯度为负 → $\alpha$ 增大 → 更多探索
- 如果熵太高 → $\mathcal{L}$ 梯度为正 → $\alpha$ 减小 → 更多利用

---

## 7. Actor-Critic 算法对比

| 算法 | 状态空间 | 动作空间 | 样本效率 | 实现复杂度 | 稳定性 |
|------|---------|---------|---------|-----------|-------|
| 基础AC | 连续 | 离散 | ❌ 低 | ⭐ 极高 | ❌ 不稳定 |
| A2C | 连续 | 离散+连续 | ❌ 低 | ⭐ 高 | 🟡 一般 |
| PPO | 连续 | 离散+连续 | 🟡 中 | ⭐ 高 | ✅ 极稳定 |
| SAC | 连续 | 连续 | ✅ 高 | 🟡 中 | ✅ 稳定 |
| DDPG | 连续 | 连续 | 🟡 中 | 🟡 中 | ❌ 不稳定 |
| TD3 | 连续 | 连续 | ✅ 高 | 🟡 中 | ✅ 稳定 |

**选择建议**：
- 游戏（离散动作）→ **PPO**
- 机器人控制（连续动作）→ **SAC**
- 样本效率优先 → **SAC**
- 实现简单优先 → **A2C**
- 稳定优先 → **PPO**
- 离线学习 → **CQL / IQL**（基于SAC）

---

## 8. 实践技巧

### 8.1 网络架构

```
输入 → [共享层] → [Actor头] → 动作分布
              ↘ [Critic头] → 标量V(s)
```

共享特征提取的优点：
- 参数更少
- 特征复用
- 但：需要分别反向传播梯度

### 8.2 超参数调优

关键超参数（按重要性排列）：
1. **学习率** — 最敏感
2. **GAE λ** — 偏差-方差平衡
3. **PPO clip ε** — 更新幅度
4. **SAC α** — 探索-利用平衡
5. **batch size / rollout size** — 数据量

**默认值（好的起点）：**
```python
config = {
    'lr': 3e-4,           # Adam默认学习率
    'gamma': 0.99,        # 长期回报
    'lam': 0.95,          # GAE
    'clip_epsilon': 0.2,  # PPO
    'entropy_beta': 0.01, # 基础A2C
    'batch_size': 64,     # PPO
    'epochs': 10,         # PPO
    'hidden': 256,        # 网络宽度
}
```

### 8.3 常见问题

**问题1：策略崩溃**
- 症状：所有动作概率一样
- 原因：熵项太强或学习率太低
- 解决：降低熵系数或提高学习率

**问题2：训练不收敛**
- 症状：奖励上下波动
- 原因：GAE λ 太高或batch size太小
- 解决：降低λ到0.9或增大batch

**问题3：过拟合**
- 症状：训练奖励高但测试差
- 原因：epoch太多或隐藏层太大
- 解决：减少epoch或加dropout

**问题4：梯度爆炸**
- 症状：NaN loss
- 原因：梯度范数太大
- 解决：梯度裁剪 `max_norm=0.5`

---

## 总结

```
Actor-Critic = 策略梯度 + 价值函数   (双网络)
GAE          = 多步TD + 权重衰减     (低方差优势估计)  
PPO          = A2C + Clip限制        (稳定更新)
SAC          = 最大熵 + Double-Q     (高效探索)
```

**下一步**：RL#5 多智能体强化学习 / RL#6 离线强化学习

---

*笔记：rl_04_actor_critic.md | 完成时间: 2026-05-16 | 总字数: ~4500*
