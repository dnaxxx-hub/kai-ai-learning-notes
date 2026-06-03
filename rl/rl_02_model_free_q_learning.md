# RL #2：Model-Free 与 Q-Learning

> 强化学习中，当环境转移概率和奖励函数未知时，智能体必须通过与环境的交互来学习最优策略。这就是 **Model-Free** 方法的用武之地。本文从蒙特卡洛方法出发，经过时序差分学习，最终深入 Q-Learning 和 SARSA 两种经典算法，并通过 Cliff Walking 实验对比它们的表现。

---

## 1. Model-Free vs Model-Based

| 特性 | Model-Based | Model-Free |
|------|-------------|------------|
| 对环境建模 | 学习/已知转移概率 $$P(s'|s,a)$$ 和奖励 $$R(s,a)$$ | 不建模，直接从经验中学习价值函数或策略 |
| 样本效率 | 通常更高（利用模型进行规划） | 通常更低（需要大量交互） |
| 计算开销 | 规划阶段计算量大 | 训练后行动极快 |
| 典型算法 | Dyna-Q, AlphaGo, MCTS | MC, TD, Q-Learning, SARSA, DQN |
| 适用场景 | 环境可建模或可模拟 | 环境复杂、难以建模 |
| 偏差来源 | 模型偏差（学到错的模型） | 估计偏差（值函数近似误差） |

核心区别一句话：**Model-Based 先学"世界怎么运作"，再在这个世界模型上做规划；Model-Free 直接学"在什么状态做什么动作好"，不关心世界怎么运作。**

---

## 2. 蒙特卡洛方法 (Monte Carlo, MC)

蒙特卡洛方法通过**完整回合**的回报来估计价值函数。它的核心思想是：大数定律——用大量样本的平均值逼近期望。

### 2.1 First-Visit vs Every-Visit

在同一个回合中，同一个状态可能被访问多次。两种处理方式：

| 方法 | 做法 | 偏差-方差 |
|------|------|-----------|
| **First-Visit MC** | 只取该状态**第一次出现**后的回报 | 无偏估计，方差较大 |
| **Every-Visit MC** | 取该状态**每次出现**后的回报 | 有偏估计（实际中偏差很小），方差更小 |

实际中 Every-Visit 更常用，因为它利用了更多数据。

### 2.2 MC 策略评估——代码实现

下面实现一个用 MC 评估给定策略的算法，环境使用经典的 Blackjack (21点)。

```python
import numpy as np
import gymnasium as gym
from collections import defaultdict

# ---------- 蒙特卡洛策略评估 (First-Visit) ----------

def mc_policy_evaluation(env, policy, gamma=1.0, num_episodes=500000):
    """
    使用 First-Visit MC 评估一个策略的价值函数 V(s)
    
    Args:
        env: 环境
        policy: dict 或函数，给定 state 返回 action
        gamma: 折扣因子
        num_episodes: 采样回合数
    
    Returns:
        V: 状态价值函数 (dict)
    """
    returns_sum = defaultdict(float)
    returns_count = defaultdict(float)
    
    for episode in range(num_episodes):
        # 生成一个完整回合
        episode_data = []
        obs, _ = env.reset()
        done = False
        truncated = False
        
        while not (done or truncated):
            action = policy[obs] if isinstance(policy, dict) else policy(obs)
            next_obs, reward, done, truncated, _ = env.step(action)
            episode_data.append((obs, action, reward))
            obs = next_obs
        
        # 从后往前计算回报 G
        G = 0
        visited_states = set()
        
        for t in range(len(episode_data) - 1, -1, -1):
            state, _, reward = episode_data[t]
            G = gamma * G + reward
            
            # First-Visit: 只在第一次访问时更新
            if state not in visited_states:
                visited_states.add(state)
                returns_sum[state] += G
                returns_count[state] += 1
    
    # 计算平均值
    V = {s: returns_sum[s] / returns_count[s] for s in returns_sum}
    return V


# ---------- 测试：Blackjack 随机策略评估 ----------

env = gym.make("Blackjack-v1")
# 随机策略
random_policy = {s: np.random.choice([0, 1]) for s in [(12 + i, j, k) 
                for i in range(10) for j in range(10) for k in [True, False]]}

# 实际上随机策略更合理的生成方式：
def get_random_action(state):
    return np.random.choice([0, 1])

V_random = mc_policy_evaluation(env, get_random_action, gamma=1.0, num_episodes=10000)
print(f"评估了 {len(V_random)} 个状态的估值")
print(f"状态 (20, 3, False) 的 V 值 ≈ {V_random.get((20, 3, False), 0):.3f}")
print(f"状态 (16, 5, True)  的 V 值 ≈ {V_random.get((16, 5, True), 0):.3f}")
```

### 2.3 MC vs DP 的差异

| 维度 | 动态规划 (DP) | 蒙特卡洛 (MC) |
|------|-------------|---------------|
| 是否需要环境模型 | 是 | 否 |
| 更新方式 | Bootstrapping（用其他状态估计更新当前状态） | 无 Bootstrapping（用完整回报） |
| 更新时机 | 每步都可更新 | 必须等回合结束 |
| 适用环境 | 有限状态 MDP | 有终止状态的回合制任务 |
| 方差 | 低（利用已知模型） | 高（样本方差） |

---

## 3. 时序差分学习 (Temporal Difference, TD)

TD 方法是 MC 和 DP 的**结合体**：
- 像 MC 一样：不需要环境模型，直接从经验学习
- 像 DP 一样：使用 Bootstrapping（用当前估计更新当前估计）

### 3.1 TD(0) —— 最简形式

TD(0) 用一个经验转移 $$(s_t, a_t, r_{t+1}, s_{t+1})$$ 来更新价值函数：

$$ V(s_t) \leftarrow V(s_t) + \alpha \underbrace{[r_{t+1} + \gamma V(s_{t+1}) - V(s_t)]}_{\text{TD error } \delta_t} $$

这里 $$r_{t+1} + \gamma V(s_{t+1})$$ 被称为 **TD Target**。

对比三种更新方式：

| 方法 | Target 公式 | 特性 |
|------|------------|------|
| MC | $$G_t = r_{t+1} + \gamma r_{t+2} + \gamma^2 r_{t+3} + \dots$$ | 无偏、高方差、回合完整 |
| DP | $$r_{t+1} + \gamma \sum P V(s_{t+1})$$ | 有偏（用估计更新估计）、需要模型 |
| TD(0) | $$r_{t+1} + \gamma V(s_{t+1})$$ | 有偏（用估计更新估计）、不需要模型 |

### 3.2 TD(λ) 与资格迹 (Eligibility Traces)

TD(λ) 是一个统一框架，它将 MC 和 TD(0) 视为两个极端：

- **λ = 0**：等价于 TD(0)，只在线更新一步
- **λ = 1**：等价于 MC（蒙特卡洛）
- **0 < λ < 1**：介于两者之间

核心在于**资格迹 (Eligibility Traces)**——记录哪些状态"最近被访问过"，以及"多久之前"。

$$ e_t(s) = \gamma \lambda e_{t-1}(s) + \mathbb{1}(S_t = s) $$

更新时，所有状态的服务器的更新量都和各自的资格迹成正比：

$$ V(s) \leftarrow V(s) + \alpha \, \delta_t \, e_t(s) $$

好处：
- 加速学习：一次 TD 误差可以传播到多个之前的状态
- 平滑偏差-方差权衡
- 在非马尔可夫任务中表现更好

```python
# ---------- TD(0) 策略评估代码 ----------

def td0_policy_evaluation(env, policy, gamma=1.0, alpha=0.1, num_episodes=10000):
    """
    使用 TD(0) 评估一个策略
    
    Args:
        env: 环境
        policy: 策略函数
        gamma: 折扣因子
        alpha: 学习率
        num_episodes: 回合数
    
    Returns:
        V: 状态价值函数
    """
    V = defaultdict(float)
    
    for episode in range(num_episodes):
        obs, _ = env.reset()
        done = False
        truncated = False
        
        while not (done or truncated):
            action = policy(obs)
            next_obs, reward, done, truncated, _ = env.step(action)
            
            # TD(0) 更新
            td_target = reward + gamma * V[next_obs] * (0 if done else 1)
            td_error = td_target - V[obs]
            V[obs] += alpha * td_error
            
            obs = next_obs
    
    return V


# 简单测试对比 MC vs TD
# 注意：实际需要更复杂的对比才能看出差异，这里仅展示接口
# V_td = td0_policy_evaluation(env, get_random_action)
```

### 3.3 MC vs TD 对比总结

| 特性 | MC | TD(0) |
|------|-----|-------|
| 更新时机 | 回合结束后 | 每一步 |
| Bootstrapping | 否 | 是 |
| 偏差 | 无偏 | 有偏（初始估计不好时） |
| 方差 | 高 | 低 |
| 收敛性 | 对任意策略保证收敛 | 对任意策略保证收敛（表格型） |
| 在线/离线 | 仅离线（批处理） | 可在线学习 |
| 非马尔可夫环境 | 受影响（累积误差） | 更鲁棒 |

---

## 4. Q-Learning —— Off-Policy TD 控制

Q-Learning 是强化学习中最具影响力的算法之一。它由 Chris Watkins 在 1989 年提出。

### 4.1 核心思想：Q 表与更新公式

Q-Learning 维护一个 **Q 表** $$Q(s, a)$$ 表示在状态 s 下采取动作 a 的期望累积奖励。

更新公式：

$$ Q(s_t, a_t) \leftarrow Q(s_t, a_t) + \alpha \left[ r_{t+1} + \gamma \max_{a'} Q(s_{t+1}, a') - Q(s_t, a_t) \right] $$

关键点在于 **max**——Q-Learning 使用的 TD Target 是 $$r_{t+1} + \gamma \max_{a'} Q(s_{t+1}, a')$$，这代表**最优 Q 值的估计**，与当前行为策略无关。

### 4.2 Off-Policy 的威力

Q-Learning 是 **Off-Policy** 算法：
- **行为策略 (Behavior Policy)**：用来生成数据（通常是 ε-greedy，探索）
- **目标策略 (Target Policy)**：我们要学习的最优策略（贪婪，利用）

这种分离意味着 Q-Learning 可以**从任何行为产生的数据中学习最优策略**，包括：
- 其他智能体的演示数据
- 过去的经验回放
- 高度探索的策略

### 4.3 完整 Q-Learning 算法实现

```python
import numpy as np
import gymnasium as gym
import matplotlib.pyplot as plt
from collections import defaultdict


class QLearningAgent:
    """
    Q-Learning Agent — Off-Policy TD Control
    """
    def __init__(self, env, alpha=0.1, gamma=0.99, epsilon=0.1, epsilon_decay=0.9999):
        self.env = env
        self.alpha = alpha          # 学习率
        self.gamma = gamma          # 折扣因子
        self.epsilon = epsilon      # 初始探索率
        self.epsilon_decay = epsilon_decay
        self.q_table = defaultdict(lambda: np.zeros(env.action_space.n))
    
    def get_action(self, state, greedy=False):
        """ε-greedy 策略选择动作"""
        if not greedy and np.random.random() < self.epsilon:
            return self.env.action_space.sample()
        return np.argmax(self.q_table[state])
    
    def update(self, state, action, reward, next_state, done):
        """Q-Learning 更新"""
        # 当前 Q 值
        current_q = self.q_table[state][action]
        
        # TD Target: r + γ * max(Q(next_state, a'))
        if done:
            td_target = reward
        else:
            td_target = reward + self.gamma * np.max(self.q_table[next_state])
        
        # TD Error
        td_error = td_target - current_q
        
        # Q 表更新
        self.q_table[state][action] += self.alpha * td_error
    
    def train(self, num_episodes=10000, log_interval=1000):
        """
        训练 Q-Learning 智能体
        
        Returns:
            episode_rewards: 每回合的总奖励
        """
        episode_rewards = []
        
        for episode in range(num_episodes):
            state, _ = self.env.reset()
            total_reward = 0
            done = False
            truncated = False
            
            while not (done or truncated):
                action = self.get_action(state)
                next_state, reward, done, truncated, _ = self.env.step(action)
                self.update(state, action, reward, next_state, done)
                total_reward += reward
                state = next_state
            
            episode_rewards.append(total_reward)
            
            # 衰减 epsilon
            self.epsilon = max(0.01, self.epsilon * self.epsilon_decay)
            
            if (episode + 1) % log_interval == 0:
                avg_reward = np.mean(episode_rewards[-log_interval:])
                print(f"Episode {episode + 1}, Avg Reward: {avg_reward:.2f}, Epsilon: {self.epsilon:.3f}")
        
        return episode_rewards
```

### 4.4 Q-Learning 收敛条件

表格型 Q-Learning 保证收敛到最优 Q* 需要的条件：

1. **有限状态和动作空间** — Q 表可表示
2. **Greedy in the Limit with Infinite Exploration (GLIE)** — 探索率最终趋于 0，但无限长时间下所有状态-动作对被访问无穷多次
3. **学习率满足**：
   $$ \sum_{t=1}^{\infty} \alpha_t = \infty \quad \text{且} \quad \sum_{t=1}^{\infty} \alpha_t^2 < \infty $$
4. **马尔可夫性** — 状态满足马尔可夫性质

---

## 5. SARSA —— On-Policy TD 控制

SARSA (State-Action-Reward-State-Action) 和 Q-Learning 几乎一样，除了一处关键的差异。

### 5.1 更新公式

$$ Q(s_t, a_t) \leftarrow Q(s_t, a_t) + \alpha \left[ r_{t+1} + \gamma Q(s_{t+1}, a_{t+1}) - Q(s_t, a_t) \right] $$

注意到没有？SARSA 用的是 $$Q(s_{t+1}, a_{t+1})$$（实际采取的动作），而 Q-Learning 用的是 $$\max_{a'} Q(s_{t+1}, a')$$。

### 5.2 On-Policy vs Off-Policy

| 特性 | Q-Learning | SARSA |
|------|-----------|-------|
| 类型 | **Off-Policy** | **On-Policy** |
| TD Target | $$r + \gamma \max_a Q(s', a)$$ | $$r + \gamma Q(s', a')$$ |
| 目标策略 | 最优策略（贪婪） | 当前策略（含探索） |
| 保守性 | 更激进（追求最优路径） | 更保守（考虑探索风险） |
| 悬崖问题 | 可能学习到靠近悬崖的路径 | 会学习更安全的路径 |

### 5.3 SARSA 完整实现

```python
class SARSAAgent:
    """
    SARSA Agent — On-Policy TD Control
    """
    def __init__(self, env, alpha=0.1, gamma=0.99, epsilon=0.1, epsilon_decay=0.9999):
        self.env = env
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.q_table = defaultdict(lambda: np.zeros(env.action_space.n))
    
    def get_action(self, state, greedy=False):
        """ε-greedy 策略选择动作"""
        if not greedy and np.random.random() < self.epsilon:
            return self.env.action_space.sample()
        return np.argmax(self.q_table[state])
    
    def update(self, state, action, reward, next_state, next_action, done):
        """SARSA 更新 —— 使用实际的 next_action，而不是 max"""
        current_q = self.q_table[state][action]
        
        if done:
            td_target = reward
        else:
            td_target = reward + self.gamma * self.q_table[next_state][next_action]
        
        td_error = td_target - current_q
        self.q_table[state][action] += self.alpha * td_error
    
    def train(self, num_episodes=10000, log_interval=1000):
        """
        训练 SARSA 智能体
        """
        episode_rewards = []
        
        for episode in range(num_episodes):
            state, _ = self.env.reset()
            action = self.get_action(state)
            total_reward = 0
            done = False
            truncated = False
            
            while not (done or truncated):
                next_state, reward, done, truncated, _ = self.env.step(action)
                
                if done:
                    self.update(state, action, reward, None, None, done)
                else:
                    next_action = self.get_action(next_state)
                    self.update(state, action, reward, next_state, next_action, done)
                    state, action = next_state, next_action
                
                total_reward += reward
            
            episode_rewards.append(total_reward)
            self.epsilon = max(0.01, self.epsilon * self.epsilon_decay)
            
            if (episode + 1) % log_interval == 0:
                avg_reward = np.mean(episode_rewards[-log_interval:])
                print(f"Episode {episode + 1}, Avg Reward: {avg_reward:.2f}, Epsilon: {self.epsilon:.3f}")
        
        return episode_rewards
```

### 5.4 Q-Learning vs SARSA 详细对比

| 对比维度 | Q-Learning | SARSA |
|---------|-----------|-------|
| 更新使用 | $$r + \gamma \max Q(s', \cdot)$$ | $$r + \gamma Q(s', a')$$ |
| 学什么 | 最优策略 $$Q^*$$ | 当前策略下的 $$Q^\pi$$ |
| 对探索的看法 | 探索是获取数据的手段 | 探索影响目标策略本身 |
| 风险偏好 | 激进（忽略短期风险） | 保守（考虑实际行为） |
| 收敛性 | 保证收敛到 $$Q^*$$（GLIE 条件） | 保证收敛到 $$Q^\pi$$ |
| 数据效率 | 高（复用过去的探索数据） | 低（需要 On-Policy 数据） |

---

## 6. Cliff Walking 实验

### 6.1 环境说明

Cliff Walking 是 Gymnasium 中的一个标准环境：
- 网格世界：4 行 × 12 列
- S：起点（左下角）
- G：终点（右下角）
- 悬崖（Cliff）：终点正下方的区域，踏入得 -100 奖励并回到起点
- 每步得 -1 奖励（鼓励走最短路径）
- 动作：上、下、左、右

最优路径是紧贴着悬崖上方行走（最短），但危险——一个 ε 探索就可能跌入悬崖。安全路径是绕到上面再下去。

### 6.2 完整对比实验代码

```python
import numpy as np
import gymnasium as gym
import matplotlib.pyplot as plt
from collections import defaultdict

# ============ 实验设置 ============

env = gym.make("CliffWalking-v0")

NUM_EPISODES = 5000
ALPHA = 0.1
GAMMA = 0.99
EPSILON = 0.1
EPSILON_DECAY = 0.9995

# ============ 训练函数 ============

def train_agent(agent_class, env, num_episodes, **kwargs):
    """统一训练接口"""
    agent = agent_class(env, **kwargs)
    episode_rewards = []
    episode_lengths = []
    
    for episode in range(num_episodes):
        state, _ = env.reset()
        total_reward = 0
        steps = 0
        done = False
        truncated = False
        
        # Q-Learning 和 SARSA 都继承自同一个基类
        if isinstance(agent, SARSAAgent):
            action = agent.get_action(state)
            while not (done or truncated):
                next_state, reward, done, truncated, _ = env.step(action)
                if done:
                    agent.update(state, action, reward, None, None, done)
                else:
                    next_action = agent.get_action(next_state)
                    agent.update(state, action, reward, next_state, next_action, done)
                    state, action = next_state, next_action
                total_reward += reward
                steps += 1
        else:
            while not (done or truncated):
                action = agent.get_action(state)
                next_state, reward, done, truncated, _ = env.step(action)
                agent.update(state, action, reward, next_state, done)
                total_reward += reward
                steps += 1
                state = next_state
        
        episode_rewards.append(total_reward)
        episode_lengths.append(steps)
        agent.epsilon = max(0.01, agent.epsilon * agent.epsilon_decay)
    
    return agent, episode_rewards, episode_lengths


# ============ 多次实验求平均 ============

NUM_RUNS = 10
all_q_rewards = []
all_sarsa_rewards = []

for run in range(NUM_RUNS):
    print(f"Run {run + 1} / {NUM_RUNS}")
    
    # Q-Learning
    q_agent, q_rewards, q_lengths = train_agent(
        QLearningAgent, env, NUM_EPISODES,
        alpha=ALPHA, gamma=GAMMA,
        epsilon=EPSILON, epsilon_decay=EPSILON_DECAY
    )
    all_q_rewards.append(q_rewards)
    
    # SARSA
    sarsa_agent, sarsa_rewards, sarsa_lengths = train_agent(
        SARSAAgent, env, NUM_EPISODES,
        alpha=ALPHA, gamma=GAMMA,
        epsilon=EPSILON, epsilon_decay=EPSILON_DECAY
    )
    all_sarsa_rewards.append(sarsa_rewards)

# 转换为 numpy 数组以便计算统计量
all_q_rewards = np.array(all_q_rewards)
all_sarsa_rewards = np.array(all_sarsa_rewards)

# 计算滑动平均（窗口大小 100）
def smooth(data, window=100):
    smoothed = np.zeros_like(data)
    for i in range(len(data)):
        start = max(0, i - window + 1)
        smoothed[i] = np.mean(data[start:i + 1])
    return smoothed

q_mean = np.mean(all_q_rewards, axis=0)
q_std = np.std(all_q_rewards, axis=0)
sarsa_mean = np.mean(all_sarsa_rewards, axis=0)
sarsa_std = np.std(all_sarsa_rewards, axis=0)

q_smoothed = smooth(q_mean)
sarsa_smoothed = smooth(sarsa_mean)

# ============ 绘图 ============

plt.figure(figsize=(14, 6))

# 子图 1：原始奖励曲线
plt.subplot(1, 2, 1)
plt.plot(q_mean, alpha=0.3, color='blue', label='Q-Learning (raw)')
plt.plot(sarsa_mean, alpha=0.3, color='red', label='SARSA (raw)')
plt.plot(q_smoothed, color='blue', linewidth=2, label='Q-Learning (smoothed)')
plt.plot(sarsa_smoothed, color='red', linewidth=2, label='SARSA (smoothed)')
plt.xlabel('Episode')
plt.ylabel('Total Reward')
plt.title('Cliff Walking: Q-Learning vs SARSA')
plt.legend()
plt.grid(alpha=0.3)

# 子图 2：最终学习到的策略可视化
plt.subplot(1, 2, 2)

def visualize_policy(agent, title):
    """可视化学到的策略（格子世界路线）"""
    grid = np.zeros((4, 12))
    cliff_penalty = -100
    
    for i in range(4):
        for j in range(12):
            state = i * 12 + j
            if state == 36:  # G
                continue
            if 37 <= state <= 46:  # 悬崖
                continue
            # 选择最优动作
            best_action = np.argmax(agent.q_table[state])
            grid[i, j] = best_action
    
    # 显示网格方向
    action_symbols = ['↑', '→', '↓', '←']
    for i in range(4):
        for j in range(12):
            state = i * 12 + j
            if state == 36:
                print(' G ', end=' ')
            elif 37 <= state <= 46:
                print(' C ', end=' ')
            else:
                print(f' {action_symbols[int(grid[i, j])]} ', end=' ')
        print()

print("Q-Learning 学到的策略：")
visualize_policy(q_agent, "Q-Learning")
print("\nSARSA 学到的策略：")
visualize_policy(sarsa_agent, "SARSA")

plt.figtext(0.5, 0.01, f"Q-Learning Avg Reward (last 500): {np.mean(q_mean[-500:]):.1f} | "
           f"SARSA Avg Reward (last 500): {np.mean(sarsa_mean[-500:]):.1f}",
           ha='center', fontsize=12, bbox={'facecolor': 'lightgray', 'alpha': 0.5})

plt.tight_layout()
plt.savefig('cliff_walking_comparison.png', dpi=150)
plt.show()
```

---

## 7. 实验结果讨论

### 7.1 典型结果

运行上述实验，你会观察到：

**Q-Learning 的行为：**
- 初期探索阶段频繁跌入悬崖（奖励极低，-100 甚至更低）
- 一旦收敛，学到的路径往往**贴着悬崖边**——这是理论最优解（11 步到达终点，总奖励 -13）
- 但在 ε-greedy 策略下执行时，仍有小概率跌入悬崖

**SARSA 的行为：**
- 初期更加保守，主动回避悬崖附近的动作
- 收敛后学到的路径会绕到悬崖上方再下到终点（约 15-17 步，总奖励 -15 到 -17）
- 在实际执行时更安全——即使在 ε 探索下也不容易跌入悬崖

### 7.2 典型奖励曲线解读

```
收敛后平均奖励对比：
Q-Learning: -13 ~ -20（取决于 ε）
SARSA:     -15 ~ -25（取决于 ε）
```

- **如果 ε 较大**：SARSA 会表现更好（实际更安全）
- **如果 ε 很小**：Q-Learning 会表现更好（接近最优解）
- **Online 执行时**：需要根据实际部署的探索需求选择

### 7.3 核心启示

1. **Off-Policy 并不总是更好**：Q-Learning 学的目标策略是贪婪的，但在 Online 执行中，行为策略仍然有探索，这可能导致灾难性后果

2. **选择依据**：
   - 如果**部署时的策略和执行时一致**（On-Policy），选 SARSA
   - 如果**能从历史/其他数据中学习**（Off-Policy），选 Q-Learning
   - 如果**安全性要求高**，选 SARSA 或对 Q-Learning 做安全修正

3. **实践中的选择**：现代深度 RL（DQN）选择 Q-Learning 路线，因为它能从经验回放池中学习，数据效率更高。但 DQN 也继承了 Q-Learning 高估和冒险的倾向。

### 7.4 进一步思考

- **Q-Learning 的高估问题**：由于存在 $$\max$$ 操作，Q-Learning 系统性地高估 Q 值。这是 DQN 中 Double Q-Learning 改进的动机
- **Expected SARSA**：用期望值 $$E[Q(s', a')]$$ 代替 SARSA 的采样值或 Q-Learning 的 max，结合了二者优点
- **N-step TD**：介于 TD(0) 和 MC 之间，用 n 步回报作为 Target，减少偏差

---

## 总结

| 方法 | 特性 | 适用场景 |
|------|------|---------|
| MC | 无偏、高方差、回合完整 | 回合制任务，需要无偏估计 |
| TD(0) | 有偏、低方差、步进更新 | 连续任务，在线学习 |
| Q-Learning | Off-Policy、激进、最优解 | 数据可复用，追求最优策略 |
| SARSA | On-Policy、保守、安全 | 在线执行安全性重要 |

**一句话记住**：MC 用完整回估计价值，TD 用一步预测更新价值，Q-Learning 用 max 追求最优，SARSA 用实际动作体现当前策略。
