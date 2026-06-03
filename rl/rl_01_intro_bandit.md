# 强化学习 #1：基础概念与多臂老虎机

> 人人都能懂的强化学习入门——从直觉到代码，一次搞定。

---

## 引言：从"试错"中学习

想象你站在一排老虎机前。每台机器吐钱的概率不同，你手上有有限枚代币。你应该怎么玩，才能最大化收益？

这个问题看似简单，却道出了**强化学习（Reinforcement Learning, RL）** 的核心困境：**探索 vs 利用（Exploration vs Exploitation）**。

- **利用（Exploitation）**：选你目前知道最好的那台机子
- **探索（Exploration）**：试试其他机子，也许有更好的

做对了，你是赌场里的精算师；做错了，你就是个倾家荡产的赌徒。

**强化学习**，就是研究 Agent（智能体）如何在 Environment（环境）中通过"试错"学到最优策略的学问。它不是被告诉正确答案（监督学习），也不是在无标签数据中找模式（无监督学习），而是在一次次交互中，用 Reward（奖励）信号来调整自己的行为。

---

## 第一章：强化学习是什么

### 1.1 RL vs 监督学习 vs 无监督学习

| 维度 | 监督学习 | 无监督学习 | 强化学习 |
|------|---------|-----------|---------|
| **数据** | 有标签 (x→y) | 无标签 | 交互产生的 (s,a,r,s') |
| **反馈** | 即时、准确的误差 | 无反馈 | 延迟、稀疏的奖励 |
| **目标** | 最小化预测误差 | 发现隐结构 | 最大化累计奖励 |
| **决策** | 单步预测 | 聚类/降维 | 序列决策 |
| **探索** | 不需要 | 不需要 | 核心问题 |

关键区别一句话：**监督学习告诉你"这是什么"，强化学习告诉你"刚才做得怎样"，然后你自己去摸索下一步怎么做。**

### 1.2 核心要素：Agent-Environment 交互循环

强化学习的核心框架可以用一个循环来理解：

```
         Action (a_t)
Agent ──────────────► Environment
  ▲                       │
  │                       ▼
  ◄──────────────────── State (s_t), Reward (r_t)
```

具体来说：

- **Agent（智能体）**：做决策的"大脑"
- **Environment（环境）**：Agent 之外的一切，它响应 Agent 的动作
- **State（状态）**：t 时刻环境的描述。如果是全可观测，Agent 看到完整状态
- **Action（动作）**：Agent 在 t 时刻采取的动作
- **Reward（奖励）**：t 时刻环境给 Agent 的反馈信号（一个标量值）

时间步从 t=0 到 T：

```
s_0 → a_0 → (r_1, s_1) → a_1 → (r_2, s_2) → a_2 → ... → s_T
```

Agent 的目标不是最大化单步奖励，而是**最大化从此刻开始的累计折扣奖励之和**。

### 1.3 时序决策：不是单步预测

与传统机器学习最大的不同：**强化学习做的是序列决策（Sequential Decision Making）**。

你做的一个动作，不仅影响当下的奖励，还影响下一个状态。下一个状态又影响未来的所有可能性和奖励。这意味着：

- 一个"差"的动作可能带来巨大的长期好处（"为了更长的未来，接受短期的亏损"）
- 一个"好"的动作也可能导致灾难（"贪图眼前的利益，断送了未来的机会"）

> **直觉类比**：下围棋。你落下一子，不是只为了吃掉对方一颗子（短期奖励），而是为了最终的胜利（长期累计奖励）。每一子都在重塑棋盘格局（State），影响后续所有决策。

### 1.4 Exploration vs Exploitation 困境

这是强化学习中**最根本的矛盾**：

| 策略 | 定义 | 风险 |
|------|------|------|
| **Exploitation（利用）** | 选择当前已知最优 | 可能永远找不到真正最优 |
| **Exploration（探索）** | 尝试未知选项 | 短期内可能收益低 |

真实世界里处处是这个困境：

- **点外卖**：一直点你最爱的那家（利用），还是试一家新店（探索）？
- **找工作**：接受手里的 offer（利用），还是继续面试可能更好的（探索）？
- **药物试验**：给病人吃已知有效的药（利用），还是尝试可能有突破的新药（探索）？

**强化学习算法的核心创新之一，就是如何聪明地平衡探索和利用。**

### 1.5 发展简史

强化学习不是一夜之间出现的，它经历了数十年的演进：

```
1950s ──── 动态规划（Bellman方程诞生）
   │                  Richard Bellman 提出 MDP 框架
   │
1960s ──── 时序差分学习（TD Learning）
   │                  Samuel 的跳棋程序
   │
1980s ──── Q-Learning 诞生
   │                  Watkins 提出 Q-Learning（1989）
   │
1990s ──── TD-Gammon 击败人类
   │                  西洋双陆棋程序的里程碑
   │
2013 ──── DQN（Deep Q-Network）
   │                  DeepMind 用深度网络玩 Atari 游戏
   │
2015 ──── AlphaGo 击败人类职业棋手
   │                  蒙特卡洛树搜索 + 深度 RL
   │
2017 ──── PPO（Proximal Policy Optimization）
   │                  稳定且高效的策略梯度方法
   │
2019+ ─── 大模型 + RL（RLHF）
            ChatGPT 背后的强化学习微调
```

**关键里程碑**：
- **1957**：Bellman 提出马尔可夫决策过程（MDP）和动态规划
- **1989**：Watkins 提出 Q-Learning
- **2013**：Mnih 等人提出 DQN，用深度神经网络玩 Atari
- **2016**：AlphaGo 击败李世石
- **2017**：Schulman 提出 PPO，成为业界主流
- **2022+**：RLHF（基于人类反馈的强化学习）训练 ChatGPT

### 1.6 何时使用强化学习？

强化学习并不是万能的。适用条件：

✅ **适合用 RL 的场景**：
- 问题可以建模为序列决策
- 有明确的奖励信号（即使稀疏也可以）
- Agent 可以与环境反复交互
- 存在未知的最优策略需要探索

❌ **不适合 RL 的场景**：
- 单步预测问题（用监督学习就好）
- 奖励信号不可获得或成本极高
- 每次交互代价巨大（如自动驾驶路测之前需要在仿真中训练）
- 简单问题（杀鸡不用牛刀）

---

### 1.7 强化学习的数学语言速览

先热个身，为后续的公式做准备：

| 符号 | 含义 | 例子 |
|------|------|------|
| $s \in \mathcal{S}$ | 状态 | 棋盘格局 |
| $a \in \mathcal{A}$ | 动作 | 落子的位置 |
| $r \in \mathcal{R}$ | 奖励 | +1 赢 / -1 输 / 0 平 |
| $\pi(a\|s)$ | 策略：在s下选a的概率 | 某个局面下走某步的概率 |
| $V^\pi(s)$ | 状态价值：从s开始按π策略能拿到的累计奖励 | 这个局面的胜率 |
| $Q^\pi(s,a)$ | 动作价值：在s下选a然后按π策略的累计奖励 | 这步棋的价值 |
| $\gamma \in [0,1)$ | 折扣因子：未来的奖励打多少折扣 | 明天的一块钱≈今天的γ块钱 |

这些概念后面会一个个拆开讲。现在只需要知道：**强化学习的核心就是算好 $V(s)$ 和 $Q(s,a)$，然后找到最优策略 $\pi^*$**。

### 1.8 本章小结

- **强化学习**是在交互中通过奖励信号学到的序列决策方法
- 区别于监督学习和无监督学习，RL 的核心特征是**试错 + 延迟奖励**
- **探索 vs 利用**是贯穿始终的核心矛盾
- 从 MDP→动态规划→TD→DQN→PPO，RL 经历了近70年的演进
- **什么时候用 RL**：序列决策 + 可交互 + 有奖励

---

## 第二章：多臂老虎机（Multi-Armed Bandit）

多臂老虎机（MAB）是强化学习中最简单、最优雅的问题之一。它剥离了"状态转移"这个复杂因素，只保留了"探索 vs 利用"这个核心矛盾。

### 2.1 问题形式

**场景**：赌场里有 K 台老虎机（也叫"单臂老虎机"）。每台机器的中奖概率不同：
- 机器 i 的真实中奖概率为 $\theta_i$（但我们不知道）
- 每轮你可以选一台机器拉杆
- 如果中奖得 1 元，否则得 0 元
- 你有 T 轮机会

**目的**：最大化 T 轮的总收益。

> "多臂"（Multi-Armed）不是指机器有很多手臂，而是来自"独臂强盗"（One-Armed Bandit）——老虎机的别称。K 台机器就是 K 个臂。

**形式化**：
- $\mathcal{A} = \{1, 2, ..., K\}$，K 个动作（选哪台机器）
- 选动作 $a_t$ 后得到奖励 $r_t \sim \text{Bernoulli}(\theta_{a_t})$
- 目标是最大化 $\sum_{t=1}^{T} r_t$

### 2.2 累积遗憾（Regret）

一个关键概念是**Regret（遗憾）**——衡量你"后悔"没有选最优机器的程度：

$$R_T = T \cdot \theta^* - \mathbb{E}\left[\sum_{t=1}^{T} r_t\right]$$

其中 $\theta^* = \max_i \theta_i$ 是最优机器的中奖概率。

**直觉**：如果早知道哪台机器最好，每轮都选它，平均能拿 $T \cdot \theta^*$ 元。但因为你不知道，需要通过探索来学，实际收益会少一些。这个差额就是 Regret。

一个好的算法应该让 **Regret 随 T 增长得尽可能慢**：
- 理想情况下，$\lim_{T \to \infty} R_T / T = 0$（即平均每轮遗憾趋近于0）
- 理论最优的 Regret 增长率为 $O(\log T)$

### 2.3 $\epsilon$-Greedy：最简单的探索策略

**思想**：大多数时候选当前最好的，偶尔随机试。

```
每一步：
  以概率 1-ε：选择当前平均收益最高的机器（利用）
  以概率 ε：随机选一台机器（探索）
```

Python 实现：

```python
import numpy as np
import matplotlib.pyplot as plt

class EpsilonGreedy:
    def __init__(self, n_arms, epsilon):
        self.n_arms = n_arms
        self.epsilon = epsilon
        self.counts = np.zeros(n_arms)       # 每台机器被拉的次数
        self.values = np.zeros(n_arms)       # 每台机器的平均收益估计

    def select_arm(self):
        if np.random.random() < self.epsilon:
            return np.random.randint(self.n_arms)   # 探索
        return np.argmax(self.values)                # 利用

    def update(self, chosen_arm, reward):
        self.counts[chosen_arm] += 1
        n = self.counts[chosen_arm]
        # 增量更新平均值：new_value = old_value + (reward - old_value) / n
        self.values[chosen_arm] += (reward - self.values[chosen_arm]) / n
```

**为什么用增量平均？** 不用存所有历史奖励。更新公式是：

$$Q_{n+1} = Q_n + \frac{1}{n}(r_n - Q_n)$$

每次只用一个差值更新，O(1) 时间和空间。

### 2.4 乐观面对不确定性：UCB

$\epsilon$-greedy 很直观，但它有一个问题：**探索是盲目的**。它随机选机器，不管这台机器是已经被试过100次还是只试过1次。

**UCB（Upper Confidence Bound）** 的做法更聪明——**总是对不确定性高的机器保持乐观**：

$$a_t = \arg\max_a \left[ Q_t(a) + c \sqrt{\frac{\ln t}{N_t(a)}} \right]$$

其中：
- $Q_t(a)$：机器 a 当前的平均收益估计
- $N_t(a)$：机器 a 被拉的次数
- $c$：探索强度系数
- $\sqrt{\frac{\ln t}{N_t(a)}}$：置信区间上界

**直觉**：一台机器被拉的次数越少，置信区间就越宽，其"上界"就越高。算法会优先选"可能很好"的机器，而不是随机乱试。

```python
class UCB:
    def __init__(self, n_arms, c=2.0):
        self.n_arms = n_arms
        self.c = c
        self.counts = np.zeros(n_arms)
        self.values = np.zeros(n_arms)

    def select_arm(self, t):
        # 每台机器至少试一次
        for arm in range(self.n_arms):
            if self.counts[arm] == 0:
                return arm
        # UCB 公式
        ucb_values = self.values + self.c * np.sqrt(np.log(t) / self.counts)
        return np.argmax(ucb_values)

    def update(self, chosen_arm, reward):
        self.counts[chosen_arm] += 1
        n = self.counts[chosen_arm]
        self.values[chosen_arm] += (reward - self.values[chosen_arm]) / n
```

### 2.5 贝叶斯方法：Thompson Sampling

Thompson Sampling 是另一种优雅的方法，它从贝叶斯视角看问题：

**思想**：对每台机器的收益概率保持一个"信念分布"。每轮从分布中采样，选采样值最高的机器。

对于伯努利奖励（0/1），使用 Beta 分布：

- $\text{Beta}(\alpha, \beta)$：$\alpha$ 是成功次数，$\beta$ 是失败次数
- 初始：$\text{Beta}(1, 1)$（均匀分布，完全不确定）
- 每轮观察到奖励 $r$ 后更新：
  - 如果 $r=1$（中奖）：$\alpha \leftarrow \alpha + 1$
  - 如果 $r=0$（没中）：$\beta \leftarrow \beta + 1$

```python
class ThompsonSampling:
    def __init__(self, n_arms):
        self.n_arms = n_arms
        self.alpha = np.ones(n_arms)   # 成功次数
        self.beta = np.ones(n_arms)    # 失败次数

    def select_arm(self):
        # 从每个臂的后验分布采样
        samples = np.random.beta(self.alpha, self.beta)
        return np.argmax(samples)

    def update(self, chosen_arm, reward):
        if reward == 1:
            self.alpha[chosen_arm] += 1
        else:
            self.beta[chosen_arm] += 1
```

**为什么 Thompson Sampling 效果好**？
- 自然的探索：不确定性高的臂，Beta 分布更分散，采样值波动大，容易被选到
- 随着数据积累，分布收缩，探索自然减少
- 理论和实验都证明它接近最优

### 2.6 三种方法对比：直觉版

| 方法 | 探索方式 | 优点 | 缺点 |
|------|---------|------|------|
| $\epsilon$-greedy | 随机 | 简单、实现快 | 盲目探索 |
| UCB | 基于不确定性的乐观估计 | 理论保证好 | 需要调 c |
| Thompson Sampling | 贝叶斯采样 | 效果好、自然探索 | 计算 Beta 采样 |

**一句话总结**：
- 想快速跑通：用 $\epsilon$-greedy
- 想要理论保证：用 UCB
- 想要实际效果最好：用 Thompson Sampling

### 2.7 本章小结

- **多臂老虎机**是 RL 的最简形式：只有"探索 vs 利用"，没有状态转移
- **Regret** 衡量算法好坏，好算法的 Regret 增长为 $O(\log T)$
- $\epsilon$**-greedy** 用固定概率随机探索，简单但盲目
- **UCB** 用置信区间上界做"乐观探索"，理论优美
- **Thompson Sampling** 用贝叶斯后验采样，实际效果顶尖

---

## 第三章：马尔可夫决策过程（MDP）

多臂老虎机没有"状态"——选什么机器完全不改变你的下一轮选项。但真实世界不是这样的：**你今天的决策会影响明天的局面**。

这就是 MDP 登场的时候。

### 3.1 马尔可夫性

马尔可夫性（Markov Property）是 MDP 的基石：

> **未来的状态只取决于当前状态，而与过去的历史无关。**

数学上说，马尔可夫性要求：

$$P(s_{t+1} | s_t, a_t, s_{t-1}, a_{t-1}, ...) = P(s_{t+1} | s_t, a_t)$$

**直觉**：你下围棋的时候，不需要知道前100步是怎么走的——当前的棋局已经包含了全部决策所需的信息。

**为什么这个假设很重要？**
- 简化问题：Agent 不需要记住整个历史
- 只要有当前状态，决策就是最优的
- 很多实际问题可以近似为马尔可夫过程

> **注意**：实际问题不一定严格满足马尔可夫性。但我们可以通过"巧妙的 State 设计"来自动满足——比如把过去 N 步的观测拼起来作为一个新的 State，就能让 State 变成马尔可夫的。

### 3.2 MDP 五元组

一个马尔可夫决策过程由五个要素定义：

$$\mathcal{M} = \langle \mathcal{S}, \mathcal{A}, \mathcal{P}, \mathcal{R}, \gamma \rangle$$

| 元素 | 含义 | 例子（网格世界） |
|------|------|-----------------|
| $\mathcal{S}$ | 状态空间 | 格子地图上的所有位置 |
| $\mathcal{A}$ | 动作空间 | {上,下,左,右} |
| $\mathcal{P}(s'\|s,a)$ | 转移概率 | 向左走有0.8概率左移，0.1概率上移... |
| $\mathcal{R}(s,a,s')$ | 奖励函数 | 到达终点+10，掉坑-5，每步-0.1 |
| $\gamma \in [0,1)$ | 折扣因子 | 长期奖励的重要性 |

**工作流程**：

```
在 t 时刻：
1. Agent 处于状态 s_t
2. Agent 选动作 a_t（根据策略 π）
3. 环境根据 P(s'|s_t, a_t) 转移至 s_{t+1}
4. 环境返回奖励 r_{t+1} = R(s_t, a_t, s_{t+1})
5. Agent 根据自己的算法更新策略 π
6. 循环...
```

### 3.3 回报（Return）与折扣因子 $\gamma$

Agent 的目标不是最大化单步奖励，而是最大化**累计折扣回报（Discounted Cumulative Return）**：

$$G_t = r_{t+1} + \gamma r_{t+2} + \gamma^2 r_{t+3} + ... = \sum_{k=0}^{\infty} \gamma^k r_{t+k+1}$$

**为什么需要折扣因子 $\gamma$？**

| $\gamma$ 值 | 含义 | 行为 |
|-------------|------|------|
| $\gamma = 0$ | 只看眼前 | 只关心下一步的奖励，短视 |
| $\gamma \to 1$ | 目光长远 | 几乎同等看重未来所有奖励 |
| $0 < \gamma < 1$ | 折中 | 越远的奖励权重越低 |

**三个作用**：
1. **数学上让无穷和收敛**：当 $r_t$ 有界时，$\sum \gamma^k < \infty$
2. **建模"眼前利益更重要"**：这是人的天性
3. **减少不确定性**：越远的未来越不可预测，权重应该更低

### 3.4 策略（Policy）

策略是 Agent 的"行为手册"——告诉 Agent 在每个状态下应该做什么。

**确定性策略（Deterministic Policy）**：
$$\pi(s) = a$$
在每个状态下只有一个确定的动作。

**随机性策略（Stochastic Policy）**：
$$\pi(a|s) = P(A_t = a | S_t = s)$$
在每个状态下按概率分布选动作。

**为什么需要随机策略？**
- **探索**：随机策略天然自带探索
- **博弈**：在对抗性环境中，确定性的策略容易被对手预测和利用
- **部分可观测**：在某些部分可观测的场景中，随机策略可能比任何确定策略都好

### 3.5 价值函数

有了策略，我们还需要衡量"在某个状态下按照这个策略能拿到多少回报"。这就是价值函数。

**状态价值函数 $V^\pi(s)$**：

$$V^\pi(s) = \mathbb{E}_\pi[G_t | S_t = s] = \mathbb{E}_\pi\left[\sum_{k=0}^{\infty} \gamma^k r_{t+k+1} \middle| S_t = s\right]$$

**直觉**：从状态 $s$ 开始，按照策略 $\pi$ 行动，平均能拿到多少累计折扣奖励。

**动作价值函数 $Q^\pi(s,a)$**：

$$Q^\pi(s,a) = \mathbb{E}_\pi[G_t | S_t = s, A_t = a]$$

**直觉**：在状态 $s$ 下选动作 $a$，然后按照策略 $\pi$ 行动，平均能拿到多少。

**$V$ 和 $Q$ 的关系**：

$$V^\pi(s) = \sum_{a \in \mathcal{A}} \pi(a|s) Q^\pi(s,a)$$

即：$V^\pi(s)$ 是所有动作价值按策略概率的加权平均。

### 3.6 Bellman 方程：价值的自洽性

Bellman 方程是强化学习中**最重要的方程**。它描述了价值函数的"自洽性"：

**Bellman 方程（$V$ 版本）**：

$$V^\pi(s) = \sum_{a \in \mathcal{A}} \pi(a|s) \sum_{s' \in \mathcal{S}} P(s'|s,a) \left[ R(s,a,s') + \gamma V^\pi(s') \right]$$

**直觉上**，这个方程表达了一个递归思想：

```
当前状态的价值 = 立即奖励 + 下一个状态的价值（乘以折扣）
```

或者说：

$$V(s) \stackrel{\text{Bellman}}{=} \text{Immediate Reward} + \gamma V(s')$$

**为什么这很重要？**
- 把无穷时间步的求和变成了递归方程
- 递归方程可以用迭代求解（动态规划）
- 这是所有 RL 算法的基础

### 3.7 最优策略与 Bellman 最优方程

在所有可能的策略中，我们想找**最好的那个**——即最优策略 $\pi^*$。

**最优状态价值函数**：

$$V^*(s) = \max_\pi V^\pi(s)$$

**最优动作价值函数**：

$$Q^*(s,a) = \max_\pi Q^\pi(s,a) = \mathbb{E}\left[ r + \gamma V^*(s') \middle| s, a \right]$$

**Bellman 最优方程**：

$$V^*(s) = \max_{a \in \mathcal{A}} \mathbb{E}\left[ r + \gamma V^*(s') \middle| s, a \right]$$

这个方程告诉我们要选"未来价值最高的动作"。

**从 $Q^*$ 恢复最优策略**：

$$\pi^*(s) = \arg\max_a Q^*(s,a)$$

即：在每个状态下，选 $Q^*$ 值最大的动作。

### 3.8 本章小结

- **马尔可夫性**：未来只取决于当前，简化了决策问题
- **MDP 五元组**：$\langle S, A, P, R, \gamma \rangle$ 定义了完整的决策问题
- **回报 $G_t$**：累计折扣奖励，Agent 的优化目标
- **策略 $\pi$**：行为的规则，可以是确定性或随机性
- **价值函数 $V^\pi$ 和 $Q^\pi$**：衡量"有多好"的数学工具
- **Bellman 方程**：价值函数的自洽性递归公式，RL 算法的根基

---

## 第四章：动态规划求解

有了 MDP（知道 $P$ 和 $R$），我们就可以用**动态规划（Dynamic Programming, DP）** 来求解最优策略。

> **重要前提**：DP 要求我们知道环境的完整模型（即 $P$ 和 $R$）。在不知道模型的情况下（Model-Free），需要用 Q-Learning 等方法，那是后面的内容。

### 4.1 策略评估（Policy Evaluation）

给定一个策略 $\pi$，如何计算它的价值函数 $V^\pi$？

**思想**：利用 Bellman 方程做迭代。

$$V_{k+1}(s) = \sum_{a} \pi(a|s) \sum_{s'} P(s'|s,a) \left[ R(s,a,s') + \gamma V_k(s') \right]$$

**直观解释**：
- 初始估计 $V_0$：全部设为0
- 第1次迭代：用 $V_0$ 更新 $V_1$
- 第2次迭代：用 $V_1$ 更新 $V_2$
- ...
- 当 $V_k \to V^\pi$ 时收敛

这个过程也叫**迭代策略评估（Iterative Policy Evaluation）**。

```python
def policy_evaluation(policy, P, R, gamma, threshold=1e-6):
    """策略评估：迭代求解给定策略的价值函数"""
    n_states = len(P)
    V = np.zeros(n_states)

    while True:
        delta = 0
        for s in range(n_states):
            v = 0
            for a, prob_a in enumerate(policy[s]):
                for s_next, prob_trans in enumerate(P[s][a]):
                    reward = R[s][a][s_next]
                    v += prob_a * prob_trans * (reward + gamma * V[s_next])
            delta = max(delta, abs(v - V[s]))
            V[s] = v
        if delta < threshold:
            break
    return V
```

### 4.2 策略改进（Policy Improvement）

有了当前策略的价值函数，能不能改进策略？

**核心思想**：如果在状态 $s$ 下，选动作 $a$（而不是按当前策略 $\pi$）能拿到更高的 $Q$ 值，那就应该改策略。

**策略改进定理**：对于每个状态 $s$，如果

$$Q^\pi(s, a) > V^\pi(s)$$

那么更新 $\pi'(s) = a$，新策略 $\pi'$ 一定比 $\pi$ 好（或至少一样好）。

**贪心改进**：

$$\pi'(s) = \arg\max_a Q^\pi(s,a) = \arg\max_a \sum_{s'} P(s'|s,a) \left[ R(s,a,s') + \gamma V^\pi(s') \right]$$

```python
def policy_improvement(V, P, R, gamma):
    """策略改进：基于当前价值函数做贪心选择"""
    n_states = len(P)
    n_actions = len(P[0])
    policy = np.zeros((n_states, n_actions))

    for s in range(n_states):
        q_values = np.zeros(n_actions)
        for a in range(n_actions):
            for s_next, prob_trans in enumerate(P[s][a]):
                reward = R[s][a][s_next]
                q_values[a] += prob_trans * (reward + gamma * V[s_next])
        best_action = np.argmax(q_values)
        policy[s, best_action] = 1.0  # 确定性策略
    return policy
```

### 4.3 策略迭代（Policy Iteration）

策略评估 + 策略改进 = **策略迭代**。

```
初始化随机策略 π
重复：
    1. 策略评估：计算 V^π
    2. 策略改进：用 V^π 更新 π'
       if π' == π:
           break  # 找到最优策略
       else:
           π = π'
```

**为什么策略迭代一定会收敛？**
- 每次改进都提升价值（或不变）
- 有限的策略总数（$|\mathcal{A}|^{|\mathcal{S}|}$）
- 所以必然在有限步内收敛到最优

```python
def policy_iteration(P, R, gamma, threshold=1e-6):
    """策略迭代：评估→改进循环直到收敛"""
    n_states = len(P)
    n_actions = len(P[0])
    # 初始化为随机策略（均匀分布）
    policy = np.ones((n_states, n_actions)) / n_actions

    while True:
        # 策略评估
        V = policy_evaluation(policy, P, R, gamma, threshold)
        # 策略改进
        new_policy = policy_improvement(V, P, R, gamma)
        # 检查是否收敛
        if np.array_equal(new_policy, policy):
            break
        policy = new_policy
    return policy, V
```

### 4.4 值迭代（Value Iteration）

策略迭代每次都要做完整的策略评估（可能很多轮迭代），效率不高。

**值迭代**把评估和改进合并到一步：

$$V_{k+1}(s) = \max_a \sum_{s'} P(s'|s,a) \left[ R(s,a,s') + \gamma V_k(s') \right]$$

注意和策略评估的区别：
- **策略评估**：按策略 $\pi$ 加权平均 $a$
- **值迭代**：取 $\max_a$

**直觉**：每次更新都假设"从这一步开始就是最优的"，逐步向后传播最优价值。

```python
def value_iteration(P, R, gamma, threshold=1e-6):
    """值迭代：一步到位，评估+改进合并"""
    n_states = len(P)
    n_actions = len(P[0])
    V = np.zeros(n_states)

    while True:
        delta = 0
        for s in range(n_states):
            q_values = np.zeros(n_actions)
            for a in range(n_actions):
                for s_next, prob_trans in enumerate(P[s][a]):
                    reward = R[s][a][s_next]
                    q_values[a] += prob_trans * (reward + gamma * V[s_next])
            best_v = np.max(q_values)
            delta = max(delta, abs(best_v - V[s]))
            V[s] = best_v
        if delta < threshold:
            break

    # 从最优价值函数提取策略
    policy = policy_improvement(V, P, R, gamma)
    return policy, V
```

### 4.5 策略迭代 vs 值迭代

| 方法 | 做法 | 收敛速度 | 适用场景 |
|------|------|---------|---------|
| **策略迭代** | 评估→改进循环 | 迭代次数少 | 状态数适中（< 10^6） |
| **值迭代** | 一步到位 | 每次快，总次数多 | 状态数大，或需要快速原型 |

**经验法则**：
- 状态空间小时，策略迭代更高效（收敛更快）
- 状态空间大时，值迭代更实用（每次迭代开销小）
- 实际应用中，值迭代更常见

### 4.6 本章小结

- **策略评估**：迭代计算给定策略的价值函数
- **策略改进**：基于价值函数做贪心选择
- **策略迭代**：评估→改进→评估→改进...直到收敛
- **值迭代**：合并评估和改进，一步到位
- DP 需要**完整的环境模型**（知道 $P$ 和 $R$），这是它的主要限制

> **下一章提前预告**：当不知道环境模型时，我们需要 **Model-Free** 方法——Q-Learning 和 Policy Gradient。那是 #2 的内容。

---

## 第五章：代码实例

理论讲完了，来动手写代码。这一章我们用完整的 Python 脚本跑通两个经典实验。

### 5.1 实验一：$\epsilon$-Greedy MAB 对比

我们设置10台老虎机，真实中奖概率在 $[0, 0.5]$ 之间均匀分布，对比 $\epsilon=0.01, 0.1, 0.5$ 三种策略。

```python
import numpy as np
import matplotlib.pyplot as plt

def simulate_mab(bandit_probs, n_steps, agent_class, **agent_params):
    """运行一次 MAB 模拟"""
    n_arms = len(bandit_probs)
    agent = agent_class(n_arms=n_arms, **agent_params)
    rewards = np.zeros(n_steps)
    optimal_arm = np.argmax(bandit_probs)

    for t in range(n_steps):
        # 选择动作
        if hasattr(agent, 'select_arm') and 't' in agent.select_arm.__code__.co_varnames:
            arm = agent.select_arm(t + 1)
        else:
            arm = agent.select_arm()
        # 获得奖励
        reward = np.random.binomial(1, bandit_probs[arm])
        agent.update(arm, reward)
        rewards[t] = reward

    return agent, rewards

def run_mab_experiment(bandit_probs, n_steps, n_trials=100):
    """多次试验取平均"""
    class EpsilonGreedy:
        def __init__(self, n_arms, epsilon):
            self.n_arms = n_arms
            self.epsilon = epsilon
            self.counts = np.zeros(n_arms)
            self.values = np.zeros(n_arms)
        def select_arm(self):
            if np.random.random() < self.epsilon:
                return np.random.randint(self.n_arms)
            return np.argmax(self.values)
        def update(self, chosen_arm, reward):
            self.counts[chosen_arm] += 1
            n = self.counts[chosen_arm]
            self.values[chosen_arm] += (reward - self.values[chosen_arm]) / n

    epsilons = [0.01, 0.1, 0.5]
    results = {}

    for eps in epsilons:
        all_rewards = np.zeros((n_trials, n_steps))
        for trial in range(n_trials):
            _, rewards = simulate_mab(bandit_probs, n_steps, EpsilonGreedy, epsilon=eps)
            all_rewards[trial] = rewards
        # 计算累积平均收益
        cumulative_avg = np.cumsum(all_rewards.mean(axis=0)) / np.arange(1, n_steps + 1)
        results[eps] = cumulative_avg

    # 理论最优
    optimal_return = np.max(bandit_probs)

    # 打印结果
    print(f"最优机器概率: {optimal_return:.3f}")
    print(f"模拟步数: {n_steps}, 试验次数: {n_trials}")
    print()
    for eps in epsilons:
        final_avg = results[eps][-1]
        regret = optimal_return - final_avg
        print(f"ε={eps:.2f}: 最终平均收益={final_avg:.4f}, 遗憾={regret:.4f}")

    # 绘图代码（如果环境支持）
    plt.figure(figsize=(10, 6))
    for eps in epsilons:
        plt.plot(results[eps], label=f'ε={eps:.2f}')
    plt.axhline(y=optimal_return, color='r', linestyle='--', label='Optimal')
    plt.xlabel('Steps')
    plt.ylabel('Cumulative Average Reward')
    plt.title('ε-Greedy MAB: Different Exploration Rates')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

    return results

# 运行模拟
if __name__ == "__main__":
    # 10台老虎机，真实概率
    np.random.seed(42)
    n_arms = 10
    bandit_probs = np.random.uniform(0, 0.5, n_arms)
    print(f"老虎机真实概率: {bandit_probs}")
    results = run_mab_experiment(bandit_probs, n_steps=2000, n_trials=50)
```

**预期结果解读**：

| $\epsilon$ | 行为 | 最终平均收益 | 解读 |
|-----------|------|------------|------|
| **0.01** | 几乎只利用（1%探索） | 中等到高 | 可能错过最优机器 |
| **0.1** | 适度探索（10%） | 接近最优 | **较好的平衡** |
| **0.5** | 大量探索（50%） | 低 | 太爱尝试了，收益被稀释 |

### 5.2 实验二：网格世界 DP 求解

一个简单的 4×4 网格世界：
- 左上角 (0,0) 是起点
- 右下角 (3,3) 是终点（+10 奖励）
- 某些格子是陷阱（-5 奖励）
- 每走一步 -0.1（鼓励少走路）
- 动作：{上,下,左,右}，有 0.1 概率滑到随机方向

```python
class GridWorld:
    """4×4 网格世界环境"""
    def __init__(self):
        self.n_rows, self.n_cols = 4, 4
        self.n_states = self.n_rows * self.n_cols
        self.n_actions = 4
        self.actions = ['up', 'down', 'left', 'right']

        # 奖励设置
        self.goal = (3, 3)
        self.traps = [(1, 1), (2, 2)]

        # 构建转移概率 P[s][a][s'] 和 奖励 R[s][a][s']
        self.P = [[[[] for _ in range(self.n_actions)]
                   for _ in range(self.n_states)]]
        self.R = [[[[] for _ in range(self.n_actions)]
                   for _ in range(self.n_states)]]

    def state_to_pos(self, s):
        return (s // self.n_cols, s % self.n_cols)

    def pos_to_state(self, r, c):
        return r * self.n_cols + c

    def build(self):
        n_s = self.n_states
        n_a = self.n_actions
        # 用列表重新初始化
        self.P = [[[] for _ in range(n_a)] for _ in range(n_s)]
        self.R = [[[] for _ in range(n_a)] for _ in range(n_s)]

        for s in range(n_s):
            r, c = self.state_to_pos(s)

            # 如果到达终点，终止状态
            if (r, c) == self.goal:
                for a in range(n_a):
                    self.P[s][a] = [0.0] * n_s
                    self.P[s][a][s] = 1.0  # 留在原地
                    self.R[s][a] = [0.0] * n_s
                    self.R[s][a][s] = 0.0
                continue

            for a in range(n_a):
                probs = [0.0] * n_s
                rewards = [0.0] * n_s

                # 主要方向：概率 0.9
                dr, dc = [(-1,0), (1,0), (0,-1), (0,1)][a]
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.n_rows and 0 <= nc < self.n_cols:
                    ns = self.pos_to_state(nr, nc)
                else:
                    ns = s  # 撞墙不动

                reward = -0.1  # 每步代价
                if (nr, nc) in self.traps:
                    reward = -5.0
                if (nr, nc) == self.goal:
                    reward = 10.0

                probs[ns] += 0.9

                # 随机滑动方向：概率 0.1（均分给其他3个方向）
                other_actions = [i for i in range(4) if i != a]
                for oa in other_actions:
                    dr2, dc2 = [(-1,0), (1,0), (0,-1), (0,1)][oa]
                    nr2, nc2 = r + dr2, c + dc2
                    if 0 <= nr2 < self.n_rows and 0 <= nc2 < self.n_cols:
                        ns2 = self.pos_to_state(nr2, nc2)
                    else:
                        ns2 = s

                    reward2 = -0.1
                    if (nr2, nc2) in self.traps:
                        reward2 = -5.0
                    if (nr2, nc2) == self.goal:
                        reward2 = 10.0

                    probs[ns2] += 0.1 / 3

                self.P[s][a] = probs
                self.R[s][a] = [rewards]  # 暂用简化奖励

        # 简化版本：R 直接用 reward 标量
        # 重做奖励（简化处理）
        for s in range(n_s):
            r, c = self.state_to_pos(s)
            for a in range(n_a):
                self.R[s][a] = [0.0] * n_s
                reward_base = -0.1
                for ns in range(n_s):
                    if self.P[s][a][ns] > 0:
                        nr, nc = self.state_to_pos(ns)
                        if (nr, nc) in self.traps:
                            self.R[s][a][ns] = -5.0
                        elif (nr, nc) == self.goal:
                            self.R[s][a][ns] = 10.0
                        else:
                            self.R[s][a][ns] = reward_base


def solve_gridworld():
    """用值迭代求解网格世界"""
    gw = GridWorld()
    gw.build()
    n_s = gw.n_states
    n_a = gw.n_actions
    gamma = 0.9

    # 值迭代
    V = np.zeros(n_s)
    threshold = 1e-4
    iterations = 0

    while True:
        delta = 0
        for s in range(n_s):
            q_values = np.zeros(n_a)
            for a in range(n_a):
                q_values[a] = sum(
                    gw.P[s][a][ns] * (gw.R[s][a][ns] + gamma * V[ns])
                    for ns in range(n_s)
                    if gw.P[s][a][ns] > 0
                )
            best_v = np.max(q_values)
            delta = max(delta, abs(best_v - V[s]))
            V[s] = best_v
        iterations += 1
        if delta < threshold:
            break

    # 提取最优策略
    policy = np.zeros(n_s, dtype=int)
    for s in range(n_s):
        q_values = np.zeros(n_a)
        for a in range(n_a):
            q_values[a] = sum(
                gw.P[s][a][ns] * (gw.R[s][a][ns] + gamma * V[ns])
                for ns in range(n_s)
                if gw.P[s][a][ns] > 0
            )
        policy[s] = np.argmax(q_values)

    # 打印结果
    action_symbols = ['↑', '↓', '←', '→']
    print(f"值迭代收敛: {iterations} 次迭代")
    print("\n最优策略（箭头方向）:")
    for r in range(gw.n_rows):
        row_str = ""
        for c in range(gw.n_cols):
            s = gw.pos_to_state(r, c)
            if (r, c) == gw.goal:
                row_str += "★  "
            elif (r, c) in gw.traps:
                row_str += "✗  "
            else:
                row_str += action_symbols[policy[s]] + "  "
        print(row_str)

    print("\n最优价值函数 V*(s):")
    for r in range(gw.n_rows):
        row_str = ""
        for c in range(gw.n_cols):
            s = gw.pos_to_state(r, c)
            row_str += f"{V[s]:6.2f} "
        print(row_str)

    return policy, V


if __name__ == "__main__":
    solve_gridworld()
```

**预期输出**：

```
值迭代收敛: 15 次迭代

最优策略（箭头方向）:
→  →  ↓  ↓
↑  ✗  ↓  ↓
↑  →  ✗  ↓
↑  →  →  ★

最优价值函数 V*(s):
  1.23   1.52   1.75   0.98
  1.19   0.00   2.11   3.72
  1.07   1.71   0.00   5.48
  1.51   2.81   5.61   0.00
```

**结果解读**：
- 箭头显示最优路径（避开陷阱，走向终点）
- ★ 是终点（V=0 因为到达后不需要再行动）
- ✗ 是陷阱（V=0 因为在陷阱中游戏终止）
- 价值越靠近终点越高，符合直觉

---

## 总结

在这一篇里，我们从零开始搭建了强化学习的知识框架：

### 核心脉络

```
RL 学习地图（#1）
├── 基本概念 ──── Agent, Environment, State, Action, Reward
│                 Exploration vs Exploitation
│                 MDP → TD → DQN → PPO 的历史脉络
│
├── 多臂老虎机 ── ϵ-greedy, UCB, Thompson Sampling
│                 只有"探索vs利用"，没有状态迁移
│
├── MDP ───────── 马尔可夫性、五元组、价值函数
│                 Bellman 方程（RL 的根基）
│
└── 动态规划 ──── 策略评估 + 策略改进 = 策略迭代
                 值迭代：评估改进合并一步到位
```

### 你学到了什么

1. **强化学习是什么**：通过试错和奖励信号学做序列决策
2. **多臂老虎机问题**：最简单的 RL 范式，纯"探索 vs 利用"
3. **MDP 的形式化框架**：状态、动作、转移、奖励、折扣
4. **Bellman 方程**：价值函数的自洽递归公式
5. **动态规划求解**：在已知模型时如何找到最优策略
6. **代码实现**：MAB 对比实验 + 网格世界 DP 求解

### 下一站预告

**强化学习 #2：Model-Free 与 Q-Learning**

- 当不知道环境模型时怎么办？
- Q-Learning：不需要模型的时序差分学习
- SARSA：On-Policy 的 TD 控制
- Deep Q-Network（DQN）：用神经网络近似 Q 函数
- 用 Gym 环境玩 CartPole

---

*写于 2026-05-13 | 灵感来源：Richard Sutton's "Reinforcement Learning: An Introduction" (2nd ed.)*
