# 博弈论、决策理论与随机过程

> 从纳什均衡到HMM — 策略思维与市场状态识别

---

## 1. 博弈论基础

### 1.1 纳什均衡

```python
import numpy as np

# 囚徒困境
#         Cooperate   Defect
# Cooperate  (-1,-1)  (-3, 0)
# Defect     ( 0,-3)  (-2,-2)

def prisoner_dilemma():
    payoffs = {
        ('C', 'C'): (-1, -1),
        ('C', 'D'): (-3,  0),
        ('D', 'C'): ( 0, -3),
        ('D', 'D'): (-2, -2),
    }
    
    # 找纯策略纳什均衡
    actions = ['C', 'D']
    equilibria = []
    
    for a1 in actions:
        for a2 in actions:
            p1 = payoffs[(a1, a2)][0]
            p2 = payoffs[(a1, a2)][1]
            
            # 检查玩家1是否有单方面偏离的动机
            best_1 = all(payoffs[(a1_alt, a2)][0] <= p1 
                        for a1_alt in actions)
            # 检查玩家2
            best_2 = all(payoffs[(a1, a2_alt)][1] <= p2 
                        for a2_alt in actions)
            
            if best_1 and best_2:
                equilibria.append((a1, a2))
    
    print("囚徒困境纯策略纳什均衡:", equilibria)
    # 结果：(D, D) — 双方都背叛是唯一均衡
    # 但(C, C)才是全局最优（-1,-1 > -2,-2）

prisoner_dilemma()
```

### 1.2 混合策略均衡

```python
def mixed_nash_2x2(a, b, c, d):
    """2x2博弈的混合策略纳什均衡
    玩家1以概率p选行动A，玩家2以概率q选行动C
    收益矩阵：
          C      D
    A  (a, a') (b, b')
    B  (c, c') (d, d')
    """
    # 玩家2的无差异条件：p*a + (1-p)*c = p*b + (1-p)*d
    # 玩家1的无差异条件：q*a' + (1-q)*b' = q*c' + (1-q)*d'
    
    # 这里假设收益矩阵是玩家1的，玩家2对称
    denom_p = (b - d) + (a - c) - (b - d)
    denom_q = (c - d) + (a - b) - (c - d)
    
    if denom_p != 0:
        p = (d - c) / denom_p
    else:
        p = 0.5  # 规避除零
    
    if denom_q != 0:
        q = (d - b) / denom_q
    else:
        q = 0.5
    
    return max(0, min(1, p)), max(0, min(1, q))

# 猎鹿博弈：两个猎人合作打鹿各得5，各自打兔各得2
#          Stag       Hare
# Stag    (5, 5)    (0, 2)
# Hare    (2, 0)    (2, 2)

p, q = mixed_nash_2x2(5, 0, 2, 2)
print(f"猎鹿博弈混合策略均衡: p(选Stag)={p:.3f}, q(选Stag)={q:.3f}")
print(f"  → 有 {(1-p)*(1-q)*100:.1f}% 概率双方选Hare（次优）")
```

## 2. 重复博弈与合作演化

```python
def repeated_prisoner(rounds=100, strategy1='tit_for_tat', strategy2='always_defect'):
    """重复囚徒困境"""
    def get_action(strategy, history, player):
        # history: [(a1, a2), ...]
        if strategy == 'always_cooperate':
            return 'C'
        elif strategy == 'always_defect':
            return 'D'
        elif strategy == 'tit_for_tat':
            if len(history) == 0:
                return 'C'  # 首轮合作
            last = history[-1]
            return last[1] if player == 0 else last[0]  # 镜像对方的上轮
    
    payoffs = {
        ('C', 'C'): (-1, -1),
        ('C', 'D'): (-3,  0),
        ('D', 'C'): ( 0, -3),
        ('D', 'D'): (-2, -2),
    }
    
    history = []
    total1, total2 = 0, 0
    
    for _ in range(rounds):
        a1 = get_action(strategy1, history, 0)
        a2 = get_action(strategy2, history, 1)
        history.append((a1, a2))
        p1, p2 = payoffs[(a1, a2)]
        total1 += p1
        total2 += p2
    
    return total1, total2

# 对比不同策略
strategies = ['always_cooperate', 'always_defect', 'tit_for_tat']
results = {}
for s1 in strategies:
    for s2 in strategies:
        r1, r2 = repeated_prisoner(100, s1, s2)
        results[(s1, s2)] = (r1, r2)

print("重复囚徒困境结果（100轮总收益）：")
print(f"{'策略1':<20} {'策略2':<20} {'收益1':>8} {'收益2':>8}")
for (s1, s2), (r1, r2) in sorted(results.items()):
    print(f"{s1:<20} {s2:<20} {r1:>8} {r2:>8}")

# TFT vs TFT 是合作解（-100, -100）
# TFT vs ALLD: TFT 吃亏（-300, -200）
# ALLD vs ALLD: 双方苦果（-200, -200）
```

## 3. 强化学习与博弈的关联

```python
# 多臂老虎机(MAB)：博弈论视角
# 每个"臂"是一个对手的策略
# 探索 vs 利用 = 寻找均衡 vs 利用已知最优

class EpsilonGreedyBandit:
    def __init__(self, n_arms, epsilon=0.1):
        self.n_arms = n_arms
        self.epsilon = epsilon
        self.counts = np.zeros(n_arms)
        self.values = np.zeros(n_arms)
    
    def select_arm(self):
        if np.random.random() < self.epsilon:
            return np.random.randint(self.n_arms)
        return np.argmax(self.values)
    
    def update(self, arm, reward):
        self.counts[arm] += 1
        n = self.counts[arm]
        self.values[arm] += (reward - self.values[arm]) / n

# 对比不同epsilon
np.random.seed(42)
n_arms = 5
true_means = [0.1, 0.2, 0.3, 0.4, 0.5]  # 第4个臂最优

for eps in [0, 0.1, 0.5]:
    bandit = EpsilonGreedyBandit(n_arms, eps)
    total_reward = 0
    regret = 0
    
    for t in range(1000):
        arm = bandit.select_arm()
        reward = np.random.normal(true_means[arm], 0.1)
        bandit.update(arm, reward)
        total_reward += reward
        regret += true_means[4] - reward  # 相对最优策略的遗憾
    
    print(f"epsilon={eps:.1f}: 总收益={total_reward:.2f}, 遗憾={regret:.2f}")
```

## 4. 马尔可夫链

```python
class MarkovChain:
    """离散时间马尔可夫链"""
    def __init__(self, transition_matrix, states):
        self.P = np.array(transition_matrix)
        self.states = states
        self.n = len(states)
        
        # 验证每行和为1
        assert np.allclose(self.P.sum(axis=1), 1)
    
    def step(self, current):
        return np.random.choice(self.n, p=self.P[current])
    
    def simulate(self, initial, steps=100):
        """模拟链的演化"""
        state = initial
        trajectory = [state]
        for _ in range(steps):
            state = self.step(state)
            trajectory.append(state)
        return trajectory
    
    def stationary_distribution(self):
        """求解平稳分布 πP = π"""
        eigvals, eigvecs = np.linalg.eig(self.P.T)
        # 找特征值1对应的特征向量
        idx = np.argmin(np.abs(eigvals - 1))
        pi = np.real(eigvecs[:, idx])
        pi = pi / pi.sum()  # 归一化
        return pi

# 三状态市场模型：牛→震荡→熊→牛
states = ['Bull', 'Sideways', 'Bear']
P = [
    [0.8, 0.15, 0.05],  # Bull → ... 
    [0.1, 0.7,  0.2],   # Sideways → ...
    [0.2, 0.3,  0.5],   # Bear → ...
]

mc = MarkovChain(P, states)
pi = mc.stationary_distribution()
print("平稳分布:")
for s, p in zip(states, pi):
    print(f"  {s}: {p:.2%}")

# 模拟
traj = mc.simulate(1, 20)  # 从牛市(1)开始
traj_states = [states[s] for s in traj]
print(f"\n20步模拟: {' → '.join(traj_states[:10])}...")

# 期望首次到达时间
def expected_first_hit_time(P, target_state):
    """求解到达target_state的期望时间"""
    n = P.shape[0]
    # 去除目标状态
    idx = [i for i in range(n) if i != target_state]
    Q = P[np.ix_(idx, idx)]
    
    # (I - Q)^{-1} * 1
    I = np.eye(len(idx))
    N = np.linalg.inv(I - Q)
    expected = N.sum(axis=1)
    
    for i, state_idx in enumerate(idx):
        print(f"  从{states[state_idx]}到达{states[target_state]}的期望步数: {expected[i]:.2f}")

print("\n首次到达时间:")
expected_first_hit_time(P, 1)  # 到达Sideways
```

## 5. 隐马尔可夫模型（HMM）

```python
# 手动实现HMM的三个基本问题
from scipy.special import logsumexp

class SimpleHMM:
    def __init__(self, A, B, pi):
        """
        A: 转移概率矩阵 (n_states x n_states)
        B: 发射概率矩阵 (n_states x n_obs)
        pi: 初始状态分布
        """
        self.A = np.array(A)
        self.B = np.array(B)
        self.pi = np.array(pi)
        self.n_states = self.A.shape[0]
    
    def forward(self, obs):
        """前向算法：计算 P(obs | model)"""
        T = len(obs)
        alpha = np.zeros((T, self.n_states))
        
        # 初始化
        alpha[0] = self.pi * self.B[:, obs[0]]
        
        # 递推
        for t in range(1, T):
            for j in range(self.n_states):
                alpha[t, j] = (alpha[t-1] @ self.A[:, j]) * self.B[j, obs[t]]
        
        return alpha, alpha[-1].sum()
    
    def viterbi(self, obs):
        """维特比算法：找到最可能的状态序列"""
        T = len(obs)
        delta = np.zeros((T, self.n_states))
        psi = np.zeros((T, self.n_states), dtype=int)
        
        # 初始化
        delta[0] = np.log(self.pi + 1e-10) + np.log(self.B[:, obs[0]] + 1e-10)
        psi[0] = 0
        
        # 递推
        for t in range(1, T):
            for j in range(self.n_states):
                log_probs = delta[t-1] + np.log(self.A[:, j] + 1e-10)
                delta[t, j] = log_probs.max() + np.log(self.B[j, obs[t]] + 1e-10)
                psi[t, j] = log_probs.argmax()
        
        # 回溯
        states = np.zeros(T, dtype=int)
        states[-1] = delta[-1].argmax()
        for t in range(T-2, -1, -1):
            states[t] = psi[t+1, states[t+1]]
        
        return states, delta[-1].max()
    
    def baum_welch(self, obs, n_iter=50):
        """Baum-Welch算法：EM训练HMM参数"""
        T = len(obs)
        
        for iteration in range(n_iter):
            # E步：前向后向
            alpha, _ = self.forward(obs)
            
            # 后向算法
            beta = np.ones((T, self.n_states))
            for t in range(T-2, -1, -1):
                for i in range(self.n_states):
                    beta[t, i] = (self.A[i] * self.B[:, obs[t+1]] * beta[t+1]).sum()
            
            # gamma: t时刻处于状态i的概率
            gamma = alpha * beta
            gamma /= gamma.sum(axis=1, keepdims=True)
            
            # xi: t时刻从i转移到j的概率
            xi = np.zeros((T-1, self.n_states, self.n_states))
            for t in range(T-1):
                denom = (alpha[t] @ self.A * self.B[:, obs[t+1]] @ beta[t+1].T).sum()
                for i in range(self.n_states):
                    for j in range(self.n_states):
                        xi[t, i, j] = alpha[t, i] * self.A[i, j] * \
                                      self.B[j, obs[t+1]] * beta[t+1, j] / (denom + 1e-10)
            
            # M步：更新参数
            self.pi = gamma[0]
            
            for i in range(self.n_states):
                for j in range(self.n_states):
                    self.A[i, j] = xi[:, i, j].sum() / (gamma[:-1, i].sum() + 1e-10)
            
            for i in range(self.n_states):
                for k in range(self.B.shape[1]):
                    self.B[i, k] = gamma[obs == k, i].sum() / (gamma[:, i].sum() + 1e-10)
    
    def predict_states(self, obs):
        """用维特比预测状态"""
        states, log_prob = self.viterbi(obs)
        return states

# 测试：用HMM识别市场状态
np.random.seed(42)
n_states = 3
n_obs = 50  # 观测类型数（比如涨跌幅分档）

# 真实HMM参数
true_A = np.array([
    [0.8, 0.15, 0.05],
    [0.1, 0.7, 0.2],
    [0.2, 0.2, 0.6]
])

true_B = np.random.dirichlet(np.ones(n_obs), n_states)
true_pi = np.array([0.4, 0.4, 0.2])

# 生成观测序列
hmm_true = SimpleHMM(true_A, true_B, true_pi)
T = 500

states_true = np.zeros(T, dtype=int)
obs = np.zeros(T, dtype=int)

state = np.random.choice(n_states, p=true_pi)
for t in range(T):
    states_true[t] = state
    obs[t] = np.random.choice(n_obs, p=true_B[state])
    state = np.random.choice(n_states, p=true_A[state])

# 训练HMM
hmm_model = SimpleHMM(
    np.ones((3, 3)) / 3,
    np.ones((3, n_obs)) / n_obs,
    np.ones(3) / 3
)
hmm_model.baum_welch(obs, n_iter=30)

# 预测
states_pred = hmm_model.predict_states(obs)

# 评估（注意状态标签可能有排列不确定性）
from sklearn.metrics import adjusted_rand_score
ari = adjusted_rand_score(states_true, states_pred)
print(f"HMM状态识别 ARI: {ari:.4f}")
```

## 6. 多智能体博弈在量化中的应用

```python
# 做T+0的博弈模型
# 场景：多个做市商竞争提供流动性
class MarketMaker:
    def __init__(self, name, spread_min=0.01, inventory_limit=100):
        self.name = name
        self.spread = spread_min * 3  # 初始价差
        self.spread_min = spread_min
        self.inventory = 0
        self.inventory_limit = inventory_limit
        self.pnl = 0
    
    def update_spread(self, competitors_spreads, market_volatility):
        """根据竞争和市场波动调整价差"""
        # 如果库存接近上限，缩小价差吸引反向交易
        inventory_ratio = abs(self.inventory) / self.inventory_limit
        
        # 比竞争对手略小的价差
        if competitors_spreads:
            avg_comp = np.mean(competitors_spreads)
            self.spread = max(self.spread_min, avg_comp * 0.95)
        
        # 库存压力调整
        self.spread *= (1 + 0.5 * inventory_ratio)
        
        return self.spread
    
    def trade(self, side, price):
        """成交"""
        if side == 'buy':
            self.inventory += 1
            self.pnl -= price
        else:
            self.inventory -= 1
            self.pnl += price

def simulate_market_making(n_makers=5, n_steps=1000):
    makers = [MarketMaker(f"MM_{i}") for i in range(n_makers)]
    
    for step in range(n_steps):
        spreads = []
        for m in makers:
            vol = np.random.gamma(1, 0.01)
            s = m.update_spread(
                [mm.spread for mm in makers if mm != m],
                vol
            )
            spreads.append(s)
        
        # 最低价差的做市商成交
        best_idx = np.argmin(spreads)
        side = np.random.choice(['buy', 'sell'])
        price = 100 + (1 if side == 'buy' else -1) * spreads[best_idx] / 2
        makers[best_idx].trade(side, price)
    
    print("做市商博弈结果:")
    for m in makers:
        print(f"  {m.name}: PnL={m.pnl:.2f}, 最终库存={m.inventory}")

simulate_market_making()
```

## 总结

| 概念 | 量化应用 | 实现工具 |
|------|---------|---------|
| 纳什均衡 | 做市商价差竞争、策略选择 | 博弈矩阵分析 |
| 重复博弈 | 策略演化、合作的涌现 | TFT类算法 |
| 马尔可夫链 | 市场状态切换、波动率预测 | 转移矩阵 |
| HMM | 状态识别、择时信号 | Baum-Welch |
| 多臂老虎机 | 策略参数调优、行业选择 | ε-greedy/UCB |
