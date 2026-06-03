# 多智能体强化学习（Multi-Agent Reinforcement Learning, MARL）

## 1. 多智能体场景分类

多智能体强化学习研究**多个智能体共存于同一环境**中的决策问题。根据智能体之间的收益关系，可分为三大类：

| 类型 | 收益关系 | 典型例子 |
|------|----------|----------|
| **完全合作（Fully Cooperative）** | 所有智能体共享同一个奖励函数 | 多机器人协同搬箱子、编队飞行 |
| **完全竞争（Fully Competitive）** | 零和博弈，一方收益 = 另一方损失 | 围棋、五子棋、1v1格斗游戏 |
| **混合 / 一般和（Mixed / General-sum）** | 各有自己的奖励函数，既有合作也有竞争 | 团队竞技（Dota 2、SC2）、自动驾驶交互 |

- **关键认识**：现实世界的大多数多智能体问题都属于**混合场景**，纯合作或纯竞争只是理想化特例。

---

## 2. 核心困难

多智能体学习的三个核心挑战：

### 2.1 非平稳环境（Non-stationarity）

> **最根本的困难**

- 每个智能体的策略都在**持续变化**
- 一个智能体的最优策略取决于其他智能体的当前策略
- **MDP 假设崩塌**：环境转移概率 $P(s'|s,a)$ 不再固定，因为其他智能体的策略本身在变
- 经验回放（Replay Buffer）中存储的旧经验失效——"分布漂移"

### 2.2 维度爆炸（Scalability / Curse of Dimensionality）

- 联合动作空间随智能体数量**指数级增长**：$|\mathcal{A}|^N$
- 联合观察空间同样爆炸：$|\mathcal{O}|^N$
- 难以扩展到大规模智能体系统

### 2.3 信用分配（Credit Assignment）

- 如果只有**全局团队奖励**，如何判断单个智能体的贡献？
- 一个智能体的好动作可能被另一个队友的坏动作掩盖
- "懒惰智能体"问题：搭便车，不贡献但共享奖励

---

## 3. 学习范式

### 3.1 CTDE — Centralized Training Decentralized Execution

> 最主流的框架，也是目前 MARL 的核心思想。

| 阶段 | 原则 | 信息 |
|------|------|------|
| 训练（Training） | **集中式** | Critic 可以看到所有智能体的观察和动作 |
| 执行（Execution） | **去中心化** | 每个 Actor 只用自己的局部观察做决策 |

**优势**：
- 训练时 Critic 有全局信息，梯度信号更准确（缓解非平稳性）
- 执行时不需要通信，可扩展到实际部署

**代表算法**：MADDPG、QMIX、MAPPO 都属于 CTDE 范式。

### 3.2 IQL — Independent Q-Learning

- 每个智能体独立做 Q-Learning，把其他智能体视为环境的一部分
- 问题：**非平稳性**——其他智能体的策略变化导致 Q 值不稳定
- 优点：简单、易于实现
- 缺点：通常效果很差，尤其在需要协作的复杂场景

> 结论：IQL 是 MARL 的"baseline"，不是最终方案。

### 3.3 参数共享（Parameter Sharing, PS）

- 多个同质智能体复用同一套网络参数
- 输入中通常包含 agent_id 来区分身份
- 优势：**大幅减少参数量**，训练效率高
- 适用：同质智能体（所有 agent 拥有相同的观察空间和动作空间）

> PS 常与 CTDE 结合使用——训练时参数共享，执行时各自用自己的 agent_id 输入。

---

## 4. MADDPG（Multi-Agent DDPG）

> 论文：*Multi-Agent Actor-Critic for Mixed Cooperative-Competitive Environments* (Lowe et al., 2017)

### 4.1 核心思想

| 组件 | 训练时输入 | 执行时输入 |
|------|-----------|-----------|
| **Actor**（去中心化） | 自己观察 $o_i$ | 自己观察 $o_i$ |
| **Critic**（集中式） | 所有观察 $o_1,...,o_N$ + 所有动作 $a_1,...,a_N$ | — |
| **目标 Actor**（去中心化） | 自己观察 | 自己观察 |
| **目标 Critic**（集中式） | 所有观察 + 所有动作 | — |

**关键直觉**：
- Critic 看到全部信息，知道整个系统的状态，因此梯度估计更准确
- 每个 Actor 只需要知道自己的观测，执行时不需要任何通信
- 对每个 Agent $i$，Critic $Q_i$ 是一个**独立的**函数，可以有不同的奖励函数（支持混合场景）

### 4.2 优化目标

对 Agent $i$，其 Critic 通过最小化以下损失来更新：

$$\mathcal{L}(\theta_i) = \mathbb{E}\left[ \left( Q_i^{\mu}(\mathbf{o}, \mathbf{a}) - y_i \right)^2 \right]$$

其中目标值：

$$y_i = r_i + \gamma \, Q_i^{\mu'}(\mathbf{o}', \mathbf{a}')\big|_{a'_j = \mu'_j(o'_j)}$$

Actor $\mu_i$ 通过梯度上升最大化：

$$\nabla_{\theta_i} J(\mu_i) = \mathbb{E}\left[ \nabla_{\theta_i} \mu_i(o_i) \cdot \nabla_{a_i} Q_i^{\mu}(\mathbf{o}, a_1,...,a_i,...,a_N)\big|_{a_i = \mu_i(o_i)} \right]$$

### 4.3 核心实现技术

- **经验回放（Replay Buffer）**：存储 $(\mathbf{o}, \mathbf{a}, \mathbf{r}, \mathbf{o}')$，打破时间相关性
- **目标网络（Target Networks）**：软更新 $\theta' \leftarrow \tau\theta + (1-\tau)\theta'$，稳定训练
- **软更新（Soft Update）**：$\tau$ 很小（如 0.001），目标网络缓慢追踪
- **策略集成（Policy Ensemble）**：每个智能体有多条轨迹，在评估时选择最好的

### 4.4 MADDPG 的优势

- 支持 **混合合作竞争** 场景（每个 agent 有独立的 Q 函数）
- 训练时 Critic 看到全局，有效缓解**非平稳性问题**
- 执行时完全去中心化，**零通信延迟**

---

## 5. QMIX — 值分解方法

> 论文：*QMIX: Monotonic Value Function Factorisation for Deep Multi-Agent Reinforcement Learning* (Rashid et al., 2018)

### 5.1 核心思想

将全局 Q 值分解为各个智能体 Q 值的**单调混合**：

$$Q_{tot}(\boldsymbol{\tau}, \mathbf{a}) = f_{\text{mix}}\left(Q_1(\tau_1, a_1), Q_2(\tau_2, a_2), ..., Q_N(\tau_N, a_N)\right)$$

其中：
- $Q_i$ 是 Agent $i$ 的**局部** Q 网络（输入自己的历史轨迹 $\tau_i$）
- $f_{\text{mix}}$ 是**混合网络**，将各个局部 Q 值组合成全局 $Q_{tot}$

### 5.2 IGM 原则（Individual-Global-Max）

QMIX 保证的**关键性质**：

$$\arg\max_{\mathbf{a}} Q_{tot}(\boldsymbol{\tau}, \mathbf{a}) = 
\begin{pmatrix}
\arg\max_{a_1} Q_1(\tau_1, a_1) \\
\vdots \\
\arg\max_{a_N} Q_N(\tau_N, a_N)
\end{pmatrix}$$

**意义**：每个智能体贪心地选择自己 $Q_i$ 最大化的动作，结果就是全局最优。

### 5.3 混合网络的单调性约束

为了保证 IGM 原则，混合网络必须满足：

$$\frac{\partial Q_{tot}}{\partial Q_i} \geq 0 \quad \forall i$$

实现方式：混合网络的权重全部**非负**（通过取绝对值或 Softplus 激活）。

**混合网络结构**：
```
Q_1, Q_2, ..., Q_N → [Hypernetwork] → 权重全部非负
     ↓
[混合网络]（带 abs 权重的 MLP）
     ↓
    Q_tot
```
- Hypernetwork 接收全局状态 $s$ 作为输入，生成混合网络的权重
- 混合网络本身不包含任何非线性（只是加权求和 + ReLU 的浅层网络）

### 5.4 QMIX 的优势与局限

| 优势 | 局限 |
|------|------|
| 支持大规模智能体（值分解） | 只适用于**完全合作**场景 |
| 训练高效，不需要 Critic 输入所有动作 | 单调性约束可能限制表达力 |
| 天然满足 IGM（去中心化执行最优） | 无法处理非单调的协作关系 |

### 5.5 VDN 与 QMIX

- **VDN**（Value Decomposition Networks）：$Q_{tot} = \sum Q_i$，线性求和，是最简单的值分解
- **QMIX**：非线性混合网络，比 VDN 更强的表达能力，是目前最主流的值分解方法

---

## 6. MAPPO — PPO 的多智能体推广

> 论文：*The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games* (Yu et al., 2022)

### 6.1 核心思路

- 把 PPO 的 Actor-Critic 框架扩展到多智能体
- 每个 Agent 有自己的 Actor，Critic 可以用两种方式：
  - **CTDE 版本**：Critic 看到全局状态 + 所有动作（类似 MADDPG 的 Critic）
  - **独立版本**：每个 Critic 只看自己的局部观察
- 使用 **GAE**（Generalized Advantage Estimation）估计优势函数
- 通过 **PPO-Clip** 做策略更新，保证更新步长可控

### 6.2 与 MADDPG 的关键区别

| 维度 | MADDPG | MAPPO |
|------|--------|-------|
| 策略类型 | 确定性策略 (DDPG) | 随机策略 (PPO) |
| 更新方式 | Off-policy | On-policy |
| 梯度裁剪 | 不需要 | Clip 机制防止策略突变 |
| 样本效率 | 高（Off-policy） | 低（On-policy） |
| 稳定性 | 对超参数敏感 | 更稳定，调参友好 |
| 合作场景 | 一般 | **非常优秀**（论文结论） |

### 6.3 MAPPO 的实践优势

- **稳定**：PPO 的 Clip 机制天然适合多智能体场景
- **简单**：不依赖 Critic 看到所有动作就能取得好结果（实验发现 CTDE 版本提升有限）
- **可扩展**：可处理 100+ 智能体的场景

---

## 7. 代码实现：MADDPG 训练两个 Agent 合作推箱子

### 7.1 环境：MPE（Multi-Agent Particle Environment）

```python
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from pettingzoo.mpe import simple_push_v2
import copy

# ==================== 网络定义 ====================
class Actor(nn.Module):
    """Actor: 输入自己的观察，输出确定性动作"""
    def __init__(self, obs_dim, act_dim, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, act_dim),
            nn.Tanh(),  # MPE动作范围为[-1, 1]
        )

    def forward(self, obs):
        return self.net(obs)


class Critic(nn.Module):
    """Critic: 输入所有智能体的观察+动作，输出 Q 值"""
    def __init__(self, total_obs_dim, total_act_dim, hidden=64):
        super().__init__()
        input_dim = total_obs_dim + total_act_dim
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1),
        )

    def forward(self, obs_all, act_all):
        x = torch.cat([obs_all, act_all], dim=-1)
        return self.net(x)


# ==================== Replay Buffer ====================
class ReplayBuffer:
    def __init__(self, capacity=1_000_000):
        self.capacity = capacity
        self.buffer = []
        self.pos = 0

    def push(self, *args):
        if len(self.buffer) < self.capacity:
            self.buffer.append(args)
        else:
            self.buffer[self.pos] = args
        self.pos = (self.pos + 1) % self.capacity

    def sample(self, batch_size):
        idx = np.random.choice(len(self.buffer), batch_size, replace=False)
        batch = [self.buffer[i] for i in idx]
        return [np.array(x) for x in zip(*batch)]

    def __len__(self):
        return len(self.buffer)


# ==================== MADDPG Agent ====================
class MADDPGAgent:
    def __init__(self, obs_dim, act_dim, total_obs_dim, total_act_dim,
                 lr_actor=1e-4, lr_critic=1e-3, gamma=0.95, tau=0.01):
        self.gamma = gamma
        self.tau = tau

        # Actor
        self.actor = Actor(obs_dim, act_dim)
        self.actor_target = copy.deepcopy(self.actor)
        self.actor_optim = optim.Adam(self.actor.parameters(), lr=lr_actor)

        # Critic
        self.critic = Critic(total_obs_dim, total_act_dim)
        self.critic_target = copy.deepcopy(self.critic)
        self.critic_optim = optim.Adam(self.critic.parameters(), lr=lr_critic)

    def select_action(self, obs, noise_scale=0.1):
        obs = torch.FloatTensor(obs).unsqueeze(0)
        action = self.actor(obs).squeeze(0).detach().numpy()
        # 训练时加探索噪声
        action += noise_scale * np.random.randn_like(action)
        return np.clip(action, -1.0, 1.0)

    def soft_update(self):
        for target, source in [(self.actor_target, self.actor),
                               (self.critic_target, self.critic)]:
            for tp, sp in zip(target.parameters(), source.parameters()):
                tp.data.copy_(self.tau * sp.data + (1 - self.tau) * tp.data)


# ==================== 训练主循环 ====================
def train_maddpg(episodes=5000, max_steps=200, batch_size=1024):
    env = simple_push_v2.parallel_env(max_cycles=max_steps, continuous=True)
    obs_spaces = env.observation_spaces
    act_spaces = env.action_spaces
    agents = list(obs_spaces.keys())  # ['adversary_0', 'agent_0', 'agent_1']

    # 这里选择两个合作 agent（agent_0 和 agent_1）训练，
    # adversary_0 作为环境中的对手（固定策略或不参与训练）
    train_agents = ['agent_0', 'agent_1']

    obs_dim = obs_spaces['agent_0'].shape[0]  # 假设所有 agent 维度相同
    act_dim = act_spaces['agent_0'].shape[0]
    n_train = len(train_agents)
    total_obs_dim = obs_dim * n_train
    total_act_dim = act_dim * n_train

    # 为每个训练 agent 创建 MADDPG 实例（可以共享参数也可以各自独立）
    maddpg_agents = {
        name: MADDPGAgent(obs_dim, act_dim, total_obs_dim, total_act_dim)
        for name in train_agents
    }

    replay = ReplayBuffer(capacity=100_000)
    episode_rewards = []

    for ep in range(episodes):
        obs_dict = env.reset()
        ep_reward = {name: 0.0 for name in train_agents}

        for step in range(max_steps):
            # 1. 选择动作
            actions = {}
            for name in train_agents:
                actions[name] = maddpg_agents[name].select_action(obs_dict[name])

            # adversary 用随机动作
            for name in agents:
                if name not in train_agents:
                    actions[name] = env.action_spaces[name].sample()

            # 2. 环境步进
            next_obs_dict, rewards_dict, terminations, truncations, _ = env.step(actions)

            # 3. 存储经验
            obs_all = np.concatenate([obs_dict[name] for name in train_agents])
            act_all = np.concatenate([actions[name] for name in train_agents])
            next_obs_all = np.concatenate([next_obs_dict[name] for name in train_agents])
            reward_sum = np.mean([rewards_dict[name] for name in train_agents])

            replay.push(obs_all, act_all, reward_sum, next_obs_all,
                        any(terminations[name] or truncations[name] for name in train_agents))

            # 4. 记录奖励
            for name in train_agents:
                ep_reward[name] += rewards_dict[name]

            obs_dict = next_obs_dict

        episode_rewards.append(ep_reward)

        # 5. 如果经验足够，训练
        if len(replay) >= batch_size and ep % 2 == 0:
            for _ in range(10):
                batch = replay.sample(batch_size)
                obs_batch, act_batch, rew_batch, next_obs_batch, done_batch = batch

                obs_all = torch.FloatTensor(obs_batch)
                act_all = torch.FloatTensor(act_batch)
                rewards = torch.FloatTensor(rew_batch).unsqueeze(1)
                next_obs_all = torch.FloatTensor(next_obs_batch)
                dones = torch.FloatTensor(done_batch.astype(float)).unsqueeze(1)

                for idx, name in enumerate(train_agents):
                    agent = maddpg_agents[name]
                    i = idx

                    # 计算目标 Q 值
                    with torch.no_grad():
                        # 用目标 Actor 为每个训练 agent 选择下一时刻的动作
                        next_actions = []
                        for j, j_name in enumerate(train_agents):
                            obs_j = next_obs_all[:, j * obs_dim:(j + 1) * obs_dim]
                            next_actions.append(maddpg_agents[j_name].actor_target(obs_j))
                        next_act_all = torch.cat(next_actions, dim=1)

                        target_q = agent.critic_target(next_obs_all, next_act_all)
                        target_q = rewards + agent.gamma * (1 - dones) * target_q

                    # 更新 Critic
                    current_q = agent.critic(obs_all, act_all)
                    critic_loss = F.mse_loss(current_q, target_q)
                    agent.critic_optim.zero_grad()
                    critic_loss.backward()
                    torch.nn.utils.clip_grad_norm_(agent.critic.parameters(), 0.5)
                    agent.critic_optim.step()

                    # 更新 Actor
                    # 重新计算当前动作，但只替换 agent i 的动作
                    curr_actions = []
                    for j, j_name in enumerate(train_agents):
                        obs_j = obs_all[:, j * obs_dim:(j + 1) * obs_dim]
                        if j == i:
                            curr_actions.append(maddpg_agents[j_name].actor(obs_j))
                        else:
                            # 对其它 agent，使用 replay 中的动作（stop gradient）
                            curr_actions.append(act_all[:, j * act_dim:(j + 1) * act_dim].detach())
                    curr_act_all = torch.cat(curr_actions, dim=1)

                    actor_loss = -agent.critic(obs_all, curr_act_all).mean()
                    agent.actor_optim.zero_grad()
                    actor_loss.backward()
                    torch.nn.utils.clip_grad_norm_(agent.actor.parameters(), 0.5)
                    agent.actor_optim.step()

                    # 软更新目标网络
                    agent.soft_update()

        if ep % 500 == 0:
            avg_r = np.mean([ep_reward[name] for name in train_agents])
            print(f"Episode {ep}, Avg Reward = {avg_r:.2f}")

    env.close()
    return maddpg_agents, episode_rewards


if __name__ == "__main__":
    agents, rewards = train_maddpg(episodes=2000)
```

### 7.2 代码关键点说明

1. **经验格式**：存储时将所有训练 agent 的观察和动作拼接到一起，供 Critic 使用
2. **Actor 更新**：计算梯度时，对当前 agent 使用 Actor 输出，对其它 agent 使用 replay 中的动作（detach）
3. **探索**：训练时 Actor 输出后加高斯噪声
4. **软更新**：$\tau=0.01$，目标网络缓慢追踪

---

## 8. 应用场景

### 8.1 自动驾驶多车协同

- **场景**：多车在交叉口协同通行、高速公路合并、车队编队
- **挑战**：每辆车有自己的目的地（混合场景），环境高度动态
- **方法**：MADDPG / MAPPO + 通信约束

### 8.2 机器人编队

- **场景**：多无人机协同搜索、仓库多机器人调度、协作搬运
- **挑战**：完全合作场景，需要精确的信用分配
- **方法**：QMIX / VDN（值分解）+ 参数共享

### 8.3 游戏 AI

- **Dota 2**（OpenAI Five）：5v5 完全合作团队对抗
  - 使用 **LSTM + PPO**，团队奖励
  - 参数共享 + 每个 agent 独立 latent
- **StarCraft II**（AlphaStar）：多智能体分层架构
  - 使用 Transformer + 人类数据预训练 + 自博弈
- **SMAC**（StarCraft Multi-Agent Challenge）：可研究 MARL 算法的基准环境

### 8.4 其他应用

| 领域 | 场景 | 备注 |
|------|------|------|
| 电力系统 | 多区域电网调度 | 合作 + 约束满足 |
| 经济学 | 拍卖竞价、市场模拟 | 竞争 / 混合场景 |
| 通信 | 多基站频谱分配 | 合作 / 混合 |
| 社交网络 | 多智能体对话、舆论传播 | 混合场景 |

---

## 总结

| 算法 | 范式 | 策略类型 | 合作/竞争 | 特点 |
|------|------|----------|-----------|------|
| **IQL** | — | Off-policy | 任何 | 简单但效果差，非平稳性问题严重 |
| **MADDPG** | CTDE | 确定性 Off-policy | **混合** | 每个 agent 独立 Q 函数，支持混合奖励 |
| **QMIX** | CTDE | 值分解 | **合作** | 单调混合保证 IGM，适合大规模合作 |
| **VDN** | CTDE | 值分解 | **合作** | $Q_{tot}=\sum Q_i$，QMIX 的特例 |
| **MAPPO** | CTDE | 随机 On-policy | **合作** | 稳定、简单、可扩展 |

**选型建议**：
- 需要处理混合合作竞争 → **MADDPG**
- 纯合作场景，智能体较多 → **QMIX** 或 **MAPPO**
- 要求训练稳定、调参友好 → **MAPPO**
- 简单场景作为 baseline → **VDN / IQL**

---

> **参考资料**
>
> 1. Lowe et al., "Multi-Agent Actor-Critic for Mixed Cooperative-Competitive Environments", NeurIPS 2017
> 2. Rashid et al., "QMIX: Monotonic Value Function Factorisation for Deep Multi-Agent RL", ICML 2018
> 3. Yu et al., "The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games", NeurIPS 2022
> 4. Sunehag et al., "Value-Decomposition Networks For Cooperative Multi-Agent Learning", 2017
> 5. Gupta et al., "Cooperative Multi-Agent Control Using Deep Reinforcement Learning", 2017
