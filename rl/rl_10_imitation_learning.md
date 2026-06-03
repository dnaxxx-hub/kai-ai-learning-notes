# 强化学习笔记 #10：模仿学习与行为克隆

> Imitation Learning & Behavior Cloning —— 看一遍就会了

## 1. 什么是模仿学习（Imitation Learning）

**核心思想**：不需要奖励信号（reward），直接从**专家演示**（expert demonstrations）中学习最优策略。

- 传统 RL：通过与环境交互 + 奖励信号探索最优策略
- 模仿学习：给你看一段"正确做法"的视频，你照着学

**适用场景**：
- 奖励函数难以设计（如开车、做饭）
- 奖励过于稀疏，RL 探索效率极低
- 已有大量人类/专家数据可用

**数学上**：给定专家轨迹数据集 $\mathcal{D} = \{\tau_1, \tau_2, ...\}$，其中 $\tau_i = (s_0, a_0, s_1, a_1, ...)$，学习策略 $\pi_\theta(a|s)$。

---

## 2. 行为克隆（Behavior Cloning, BC）

最简单、最直观的模仿学习方法。

### 方法

把问题当作**监督学习**：
- 输入：状态 $s$（观察）
- 输出：动作 $a$（专家在该状态下的动作）
- 损失函数：$\mathcal{L}(\theta) = \mathbb{E}_{(s,a) \sim \mathcal{D}}[-\log \pi_\theta(a|s)]$

本质上就是**分类/回归问题**——像教模型"对着答案抄"。

### 伪代码

```
输入：专家轨迹数据集 D = {(s₁,a₁), (s₂,a₂), ...}
1. 随机初始化策略网络 π_θ
2. 重复：
   a. 从 D 中采样一个 batch (s, a)
   b. 计算监督损失 L = -log π_θ(a|s)
   c. 更新 θ ← 梯度下降(L)
3. 返回 π_θ
```

### 严重缺点：分布偏移（Distributional Shift / Covariate Shift）

**问题本质**：训练数据来自专家轨迹分布，但执行时策略会犯错偏离专家轨迹 → 遇到从未见过的状态 → 决策越来越差 → 级联错误（cascading errors）。

```
专家路径：    s0 → s1 → s2 → s3 → ... (完美)
策略执行：    s0 → s1' → s2' → ??? (偏离)
                                   ↑ 从未训练过，乱猜
```

类比：学开车时教练只教你在车道中间开，但你手一抖偏了一点，就不知道该怎么回正了。

**数据需求量大**：需要覆盖所有可能的状态空间 → 指数增长，不现实。

---

## 3. DAgger（Dataset Aggregation）

> 解决 BC 分布偏移问题的经典方法

**核心思想**：交互式学习——策略自己跑，遇到新状态时**向专家查询**该怎么做。

### 算法流程

```
1. 初始化策略 π_θ
2. 用 BC 在专家数据 D 上预训练
3. 重复 N 轮：
   a. 用当前策略 π_θ 与环境交互，生成轨迹 {s₁, s₂, ...}
   b. 对轨迹中的每个状态 s_t，向专家查询动作 a_t^*
   c. 将 (s_t, a_t^*) 加入数据集 D
   d. 在增强后的 D 上重新训练 π_θ
4. 返回 π_θ

Dataset Aggregation = D ← D ∪ 新数据
```

### 优点
- ✅ 有效缓解分布偏移
- ✅ 策略见过的状态都得到校正
- ✅ 理论上可收敛到专家水平

### 缺点
- ❌ 需要专家**在线交互**（一直得有人帮忙纠错）
- ❌ 需要"带状态回放"的环境
- ❌ 查询成本高（人类专家很贵）

---

## 4. GAIL（Generative Adversarial Imitation Learning）

> 将 GAN（生成对抗网络）思想融入模仿学习

### 核心思想

引入一个**判别器** $D_\psi(s,a)$ 区分"这是专家行为"还是"策略生成的行为"，策略 $\pi_\theta$ 则尽量让判别器分不清。

### 结构

```
┌─────────┐   专家轨迹 (s,a) ──┐
│         │                    │
│ 判别器  │←───────────────────┤──→ 真/假？
│ D_ψ(s,a)│                    │
│         │   策略轨迹 (s,a) ──┘
└────┬────┘
     ↑
     │ 梯度（策略要最大化判别的困惑度）
     │
┌────┴────┐
│ 策略 π_θ │ ←── 与环境交互
└─────────┘
```

### 优化目标

$$
\min_{\pi} \max_{D} \mathbb{E}_{\pi_E}[\log D(s,a)] + \mathbb{E}_{\pi}[ \log(1 - D(s,a))] - \lambda H(\pi)
$$

- 判别器 $D$：最大化区分能力
- 策略 $\pi$：最小化区分能力（让 $D$ 分不清）
- $H(\pi)$：策略熵正则项，鼓励探索

### 优点
- ✅ 不需要专家在线交互
- ✅ 学到的是"风格/分布"而非简单复制
- ✅ 理论上等价于最小化专家与策略的 occupancy measure 散度

### 缺点
- ❌ GAN 训练不稳定（模式坍塌、收敛困难）
- ❌ 计算开销大（策略 + 判别器两个网络）
- ❌ 超参数敏感

---

## 5. 三大方法对比：BC vs DAgger vs GAIL

| 维度 | BC | DAgger | GAIL |
|------|----|--------|------|
| **数据需求** | 需要**大量**离线专家数据 | 中等 + **在线专家查询** | 少量离线数据即可 |
| **交互要求** | 无 | 需要与环境和专家交互 | 需要与**环境**交互（无需专家） |
| **分布偏移** | ❌ 严重 | ✅ 解决 | ✅ 缓解 |
| **训练难度** | ⭐ 简单 | ⭐⭐ 中等 | ⭐⭐⭐ 困难 |
| **稳定性** | ✅ 稳定 | ✅ 稳定 | ⚠️ 不稳定（GAN） |
| **数据效率** | 低 | 中 | 高（效率好） |
| **计算开销** | 低 | 中 | 高 |
| **适用场景** | 数据充足、简单任务 | 有专家在线指导 | 复杂分布匹配任务 |

**选型口诀**：
- 数据多、任务简单 → **BC**
- 专家随叫随到 → **DAgger**
- 数据少、任务复杂 → **GAIL**

---

## 6. IRL vs 模仿学习

**逆向强化学习（Inverse RL, IRL）** 和模仿学习都从专家演示中学习，但路径不同。

| | IRL | 模仿学习（Imitation Learning） |
|--|-----|-------------------------------|
| **步骤** | 先学奖励函数 → 再用 RL 学策略 | 直接学策略 |
| **通用性** | 奖励函数可复用、迁移性更好 | 策略专用，换任务需重学 |
| **计算成本** | 高（两步、需内层 RL 优化） | 低（一步到位） |
| **理论基础** | 奖励可解释、可泛化 | 直接逼近专家行为 |
| **典型方法** | MaxEnt IRL, Apprenticeship Learning | BC, DAgger, GAIL |

**一句话总结**：
- IRL：学"为什么这么做" → 更通用，但更贵
- 模仿学习：学"怎么做" → 更直接，但泛化弱

---

## 7. 单样本/少样本模仿学习（One-shot / Few-shot Imitation Learning）

**问题**：传统模仿学习需要海量专家演示。能不能看**一次**就学会？

### 方法

**元学习（Meta-Learning）框架**：
- 训练阶段：在大量**不同**任务上训练，学会"如何快速模仿"
- 测试阶段：看一次新任务的专家演示 → 快速适应

**代表性方法**：
- **MAML**（Model-Agnostic Meta-Learning）：学习好的初始化参数，一步梯度更新适应新任务
- **Context-based**：把演示编码为 context vector，条件化策略 $π(a|s, context)$

### 应用

- 机器人看一次人类做，自己就会了
- 游戏 AI 看一次通关视频，复现操作

---

## 8. 视觉模仿学习（Visual Imitation Learning）

**核心**：以**原始图像/视频**作为输入，而非低维状态向量。

### 难点
- 高维输入 → 需要视觉表征学习
- 视角差异 → 示教者视角 ≠ 学习者视角
- 物体状态变化 → 需要理解物理交互

### 经典方法

**端到端方法**：图像 → CNN → 动作（模仿人类开车的 ALVINN 系统是鼻祖）

**Third-person Imitation**：
- 学习者在第三人称视频中看专家
- 需要**视角不变**表征
- 代表：TCN（Time-Contrastive Networks）、PVN（Placing via Viewpoint Nirvana）

**Video Prediction**：预测下一帧图像，隐式地推断动作

**关键洞察**：
> 视觉模仿学习 ≈ 答案 = 表征学习 + 模仿学习
> 学不会往往是因为表征不够好，而非模仿算法不行

---

## 9. 代码实现：行为克隆（PyTorch 示例）

### 设置

```python
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from torch.utils.data import Dataset, DataLoader

# 假设我们有一个专家轨迹数据集
# 状态维度 = obs_dim，动作维度 = act_dim（连续）或动作类别数（离散）

class ExpertDataset(Dataset):
    def __init__(self, states, actions):
        """
        states: (N, obs_dim) numpy array
        actions: (N, act_dim) numpy array (连续) 或 (N,) numpy array (离散)
        """
        self.states = torch.FloatTensor(states)
        self.actions = torch.FloatTensor(actions) if actions.ndim > 1 else torch.LongTensor(actions)

    def __len__(self):
        return len(self.states)

    def __getitem__(self, idx):
        return self.states[idx], self.actions[idx]
```

### 策略网络（连续动作 / 离散动作）

```python
# 连续动作：输出均值 + 固定方差
class ContinuousPolicy(nn.Module):
    def __init__(self, obs_dim, act_dim, hidden_dim=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, act_dim),
        )
        self.log_std = nn.Parameter(torch.zeros(act_dim))

    def forward(self, obs):
        mean = self.net(obs)
        return mean, self.log_std.exp()

# 离散动作：输出类别概率
class DiscretePolicy(nn.Module):
    def __init__(self, obs_dim, num_actions, hidden_dim=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_actions),
        )

    def forward(self, obs):
        return torch.softmax(self.net(obs), dim=-1)
```

### 损失函数

```python
def bc_loss(policy, states, actions, continuous=True):
    if continuous:
        mean, std = policy(states)
        # 负对数似然：高斯分布下的 NLL
        dist = torch.distributions.Normal(mean, std)
        log_prob = dist.log_prob(actions).sum(dim=-1)
    else:
        probs = policy(states)
        # 交叉熵损失
        log_prob = torch.log(probs.gather(1, actions.unsqueeze(-1)).squeeze(-1) + 1e-8)

    return -log_prob.mean()
```

### 训练循环

```python
def train_bc(policy, train_loader, lr=1e-3, epochs=100):
    optimizer = optim.Adam(policy.parameters(), lr=lr)
    continuous = isinstance(policy, ContinuousPolicy)

    for epoch in range(epochs):
        epoch_loss = 0.0
        for states, actions in train_loader:
            optimizer.zero_grad()
            loss = bc_loss(policy, states, actions, continuous)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        if epoch % 20 == 0:
            print(f"Epoch {epoch}, Loss: {epoch_loss / len(train_loader):.4f}")

    return policy

# ─── 使用示例 ────────────────────────────────────────────
# # 加载专家数据（假设已有）
# states = np.load("expert_states.npy")   # (N, obs_dim)
# actions = np.load("expert_actions.npy")  # (N, act_dim)
#
# dataset = ExpertDataset(states, actions)
# loader = DataLoader(dataset, batch_size=64, shuffle=True)
#
# policy = ContinuousPolicy(obs_dim=states.shape[1], act_dim=actions.shape[1])
# trained_policy = train_bc(policy, loader, epochs=100)
```

### 评估：检测分布偏移

```python
def evaluate_bc(policy, env, num_episodes=10):
    """执行策略看看表现的退化解情况"""
    total_rewards = []
    for ep in range(num_episodes):
        obs = env.reset()
        done = False
        ep_reward = 0.0

        while not done:
            obs_t = torch.FloatTensor(obs).unsqueeze(0)
            with torch.no_grad():
                if isinstance(policy, ContinuousPolicy):
                    mean, _ = policy(obs_t)
                    action = mean.squeeze(0).numpy()
                else:
                    probs = policy(obs_t)
                    action = torch.multinomial(probs, 1).item()

            obs, reward, done, _ = env.step(action)
            ep_reward += reward

        total_rewards.append(ep_reward)
        print(f"Episode {ep+1}: {ep_reward:.2f}")

    print(f"平均奖励: {np.mean(total_rewards):.2f} ± {np.std(total_rewards):.2f}")
```

### DAgger 简化实现

```python
def dagger(policy, env, expert_policy, num_rounds=5, steps_per_round=500):
    """
    DAgger: 交互式数据聚合
    - policy: 当前策略
    - env: 环境
    - expert_policy: 专家策略（能给出动作标签）
    """
    dataset_states, dataset_actions = [], []  # 初始数据集需已包含专家数据

    for round_idx in range(num_rounds):
        # 用当前策略 rollout
        obs = env.reset()
        new_states, new_actions = [], []

        for step in range(steps_per_round):
            # 策略执行
            obs_t = torch.FloatTensor(obs).unsqueeze(0)
            with torch.no_grad():
                if isinstance(policy, ContinuousPolicy):
                    mean, _ = policy(obs_t)
                    action = mean.squeeze(0).numpy()
                else:
                    probs = policy(obs_t)
                    action = torch.multinomial(probs, 1).item()

            # 向专家查询在这个状态下的正确动作
            expert_action = expert_policy(obs)

            new_states.append(obs)
            new_actions.append(expert_action)

            obs, _, done, _ = env.step(action)
            if done:
                obs = env.reset()

        # 聚合数据
        dataset_states.extend(new_states)
        dataset_actions.extend(new_actions)

        # 在聚合数据上重新训练
        new_dataset = ExpertDataset(
            np.array(dataset_states), np.array(dataset_actions)
        )
        loader = DataLoader(new_dataset, batch_size=64, shuffle=True)
        policy = train_bc(policy, loader, epochs=50)

        print(f"DAgger Round {round_idx+1} done. Dataset size: {len(dataset_states)}")

    return policy
```

---

## 10. 现实应用

### 🤖 机器人技能学习
- **模仿人类演示**：让机器人看一遍人类操作，学会抓取、放置、折叠等精细动作
- **Sim-to-Real**：在仿真中通过 DAgger 训练，迁移到真机
- **代表案例**：Google RT-1 / RT-2，通过大规模互联网视频训练机器人

### 🚗 自动驾驶
- **端到端驾驶**：输入摄像头图像 → 输出方向盘角度/油门（NVIDIA PilotNet）
- **行为克隆**：从人类驾驶数据学习，是自动驾驶的基石技术之一
- **挑战**：分布偏移——遇到训练中没见过的路况可能出事故（DAgger 被认为很有前景）
- **Waymo / Tesla**：使用大量人类驾驶数据 + 仿真校正

### 🎮 游戏 AI
- **Minecraft / StarCraft**：先通过模仿学习初始化策略，再用 RL 精调
- **游戏 NPC**：克隆人类玩家行为，使 NPC 更自然
- **Speedrun 模仿**：AI 看一次世界纪录视频就模仿通关操作

### 🏭 其他领域
- **手术机器人**：从专家手术录像学习操作
- **无人机飞行**：从人类飞行员演示学习特技动作
- **对话系统**：从人类对话中学习回复策略

---

## 总结

```
模仿学习 = 不需要奖励，照着专家做就行

    BC  ─→ 简单但怕跑偏（分布偏移）
    │
    └── DAgger ─→ 一边跑一边让专家纠错（需要在线专家）
    │
    └── GAIL  ─→ 用 GAN 让策略像专家一样「分布」上相似
    │
    └── One-shot IL ─→ 看一次就学会（元学习）
    │
    └── Visual IL ─→ 看视频学，不用状态向量

应用：机器人 🤖  🚗 自动驾驶  🎮 游戏AI
```

---

## 参考文献

1. **Behavioral Cloning**: Pomerleau, D.A. "ALVINN: An Autonomous Land Vehicle in a Neural Network." NIPS 1989.
2. **DAgger**: Ross, S., Gordon, G., & Bagnell, D. "A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning." AISTATS 2011.
3. **GAIL**: Ho, J. & Ermon, S. "Generative Adversarial Imitation Learning." NeurIPS 2016.
4. **IRL**: Ng, A.Y. & Russell, S. "Algorithms for Inverse Reinforcement Learning." ICML 2000.
5. **One-shot Imitation**: Duan, Y., et al. "One-Shot Imitation Learning." NeurIPS 2017.
6. **Visual Imitation**: Pathak, D., et al. "Zero-Shot Visual Imitation." ICLR 2018.
7. **MAML**: Finn, C., Abbeel, P., & Levine, S. "Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks." ICML 2017.
8. **RT-2**: Brohan, A., et al. "RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control." arXiv 2023.

---

*写作日期：2025-07-17*
*系列笔记：#10，上一篇：#9 策略梯度，下一篇：#11 逆向强化学习*
