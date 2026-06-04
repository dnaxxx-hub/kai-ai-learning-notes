# 概率论基础深化 — 数学/统计学深潜第1课

> **学习原则**：每个公式都要能说出"它解决了什么问题"和"为什么长这样"。
> 面向后续课程：信息论、统计推断、随机过程、强化学习。

---

## 1. 概率公理：从直觉到测度论

### 1.1 为什么需要公理？

概率论最早来自赌博（Pascal, Fermat, 1654），直觉上没问题：掷骰子每个面概率 1/6。但到了 20 世纪初，数学家发现直觉不够用了——有些"不可测"的集合（如 Vitali 集）让朴素概率崩了。Kolmogorov 在 1933 年用测度论给概率论打了一个**严格的地基**。

### 1.2 Kolmogorov 三公理

设 $(\Omega, \mathcal{F}, P)$ 是一个概率空间：

- **Ω (样本空间)**：所有可能结果的集合。如掷骰子 Ω = {1,2,3,4,5,6}
- **ℱ (事件域 / σ-代数)**：Ω 的子集族，对可数并、可数交、补封闭。通俗说：你关心的事件的集合
- **P (概率测度)**：从 ℱ 到 [0,1] 的函数，满足：

**公理 1** (非负性)：$P(A) \ge 0$ 对任意 $A \in \mathcal{F}$  
**公理 2** (归一化)：$P(\Omega) = 1$  
**公理 3** (可数可加性)：若 $A_1, A_2, \dots$ 两两互斥，则  
$$P\left(\bigcup_{i=1}^\infty A_i\right) = \sum_{i=1}^\infty P(A_i)$$

### 1.3 直觉理解

| 概念 | 日常类比 | 数学角色 |
|------|---------|---------|
| Ω | 一切可能发生的事情 | 全集 |
| ℱ | 你能提的问题的集合（不能问"第π次掷硬币"这种奇怪问题） | 事件结构 |
| P | 对每个问题打一个 0~1 的分数 | 测度 |

**为什么需要 σ-代数？**  
因为有些集合太"奇怪"了（如 Vitali 集），无法赋予合理的概率。ℱ 就是 "well-behaved" 的集合集合。

### 1.4 公理的重要推论

- $P(\emptyset) = 0$
- $P(A^c) = 1 - P(A)$
- 有限可加性：$P(A \cup B) = P(A) + P(B) - P(A \cap B)$（容斥原理）
- 若 $A \subseteq B$，则 $P(A) \le P(B)$

### 1.5 测度论视角一句话

> 概率就是一个**总质量为 1 的测度**。积分就是期望。

这就是为什么概率论课本总是和测度论绑在一起——它们共享同一套语言。

---

## 2. 条件概率与贝叶斯定理：从先验到后验

### 2.1 条件概率的本质

$$P(A|B) = \frac{P(A \cap B)}{P(B)}, \quad P(B) > 0$$

**直观**：已知 B 发生了，Ω 缩小为 B。A ∩ B 是 A 在 B 中的"那一部分"。概率重新归一化。

```python
import numpy as np

# 直觉验证：蒙提霍尔问题 (Monty Hall Problem)
# 三扇门，一车两羊。你选一扇，主持人开一扇羊门，换还是不换？
n_trials = 100000
doors = np.array([0, 0, 1])  # 0=goat, 1=car

stay_wins = 0
switch_wins = 0

for _ in range(n_trials):
    np.random.shuffle(doors)
    choice = np.random.randint(0, 3)
    
    # 主持人打开一扇羊门（不是你的选择，不是车）
    available = [i for i in range(3) if i != choice and doors[i] == 0]
    host_open = np.random.choice(available)
    
    # 剩下的门
    remaining = [i for i in range(3) if i != choice and i != host_open][0]
    
    stay_wins += doors[choice] == 1
    switch_wins += doors[remaining] == 1

print(f"不换门胜率: {stay_wins/n_trials:.3f}")  # ≈ 0.333
print(f"换门胜率:   {switch_wins/n_trials:.3f}")  # ≈ 0.667
```

**为什么换门胜率是 2/3？**  
因为条件概率：你初始选到车的概率是 1/3，选到羊的概率是 2/3。主持人打开羊门后，概率"坍缩"了——如果初始选到羊（概率 2/3），换门就赢。

### 2.2 全概率公式

$$P(B) = \sum_{i} P(B|A_i) P(A_i)$$

其中 $\{A_i\}$ 是 Ω 的一个划分。  
**直观**：把 B 的概率"拆碎"到每个 A_i 上再求和。

### 2.3 贝叶斯定理——推理引擎

$$P(A|B) = \frac{P(B|A) P(A)}{P(B)}$$

或者更完整地：

$$P(A|B) = \frac{P(B|A) P(A)}{\sum_{i} P(B|A_i) P(A_i)}$$

**核心框架**：

$$\text{后验} \propto \text{似然} \times \text{先验}$$

| 术语 | 含义 | 示例（医疗检测） |
|------|------|-----------------|
| 先验 $P(A)$ | 看到数据前的信念 | 患病率 1% |
| 似然 $P(B\|A)$ | 数据在假设下的概率 | 检测准确率 99% |
| 证据 $P(B)$ | 数据的边际概率 | 检测阳性概率 |
| 后验 $P(A\|B)$ | 看到数据后的更新信念 | 检测阳性后实际患病概率 |

```python
# 直觉实验：罕见病检测
# 先验：患病率 1%
# 检测：患病者 99% 阳性，健康者 2% 假阳性
# 问：检测阳性的人，实际患病的概率是多少？

prior = 0.01          # P(患病)
sensitivity = 0.99    # P(阳性|患病)
false_positive = 0.02 # P(阳性|健康)

# 全概率公式算证据
evidence = sensitivity * prior + false_positive * (1 - prior)

# 贝叶斯公式
posterior = (sensitivity * prior) / evidence
print(f"检测阳性后实际患病概率: {posterior:.3f}")  # ≈ 0.334
# 直觉陷阱：看似 99% 准确率的检测，阳性了也只有 1/3 概率真患病
```

**关键洞察**：贝叶斯定理是说：**不要只看"检测准确率"，要结合先验**。当先验很低时，假阳性的影响远大于你可以凭直觉感受到的程度。

### 2.4 从先验到后验的迭代过程

贝叶斯推理最优雅的地方是：**今天后验 = 明天先验**。

$$P(\theta | x_1) \rightarrow P(\theta | x_1, x_2) \rightarrow \dots$$

看到第一个数据点 → 更新信念 → 带着更新后的信念看第二个数据点 → 继续更新……这就是**在线学习 (online learning)** 的本质。

---

## 3. 随机变量：从事件到数字

### 3.1 什么是随机变量？

**定义**：随机变量 $X$ 是从样本空间 Ω 到实数 ℝ 的函数。

$$X: \Omega \to \mathbb{R}$$

**为什么需要随机变量？**  
因为 Ω 可以是任何东西（硬币、天气、用户行为），但数字好操作。我们给每个"结果"贴一个数字标签。

### 3.2 三种类型

| 类型 | 取值 | 例子 | 数学工具 |
|------|------|------|---------|
| 离散 | 可数集（有限或可数无穷） | 掷骰子点数 | PMF |
| 连续 | 不可数集（实数区间） | 身高、温度 | PDF |
| 混合 | 部分离散 + 部分连续 | 保险赔付（有概率为 0） | CDF + 概率质量点 |

### 3.3 PMF / PDF / CDF

**PMF（概率质量函数）**：
$$p_X(x) = P(X = x)$$
只对离散变量。满足：$\sum_x p_X(x) = 1$

**PDF（概率密度函数）**：
$$P(a \le X \le b) = \int_a^b f_X(x)\,dx$$
关键是：单点的概率为 0。$f_X(x)$ 本身不是概率，密度×区间长度才是。

**CDF（累积分布函数）**：
$$F_X(x) = P(X \le x)$$

CDF 是"万能的"，所有随机变量都有 CDF，适用于连续/离散/混合。性质：

- 非减：$x_1 < x_2 \Rightarrow F(x_1) \le F(x_2)$
- 右连续：$\lim_{x \to a^+} F(x) = F(a)$
- 极限：$\lim_{x \to -\infty} F(x) = 0$, $\lim_{x \to +\infty} F(x) = 1$

```python
import numpy as np
import matplotlib.pyplot as plt

# 用 CDF 做逆变换采样（生成任意分布的随机数）
# 原理：如果 U ~ Uniform(0,1)，则 X = F^{-1}(U) 服从分布 F

def exponential_cdf_inv(u, rate=1.0):
    """指数分布的逆 CDF"""
    return -np.log(1 - u) / rate

# 生成指数分布的样本
n = 100000
u = np.random.uniform(0, 1, n)
samples = exponential_cdf_inv(u, rate=1.0)

# 验证：ECDF vs 理论 CDF
sorted_samples = np.sort(samples)
ecdf = np.arange(1, n+1) / n
theoretical_cdf = 1 - np.exp(-sorted_samples)

print(f"最大偏差: {np.max(np.abs(ecdf - theoretical_cdf)):.4f}")  # ≈ 0.005
```

**逆变换采样**：这是从"你知道 CDF 但不知道怎么直接采样"的分布中生成随机数的通用方法。

---

## 4. 期望、方差、协方差、相关系数

### 4.1 期望——分布的"重心"

**离散**：$E[X] = \sum_x x \cdot p_X(x)$  
**连续**：$E[X] = \int_{-\infty}^{\infty} x \cdot f_X(x)\,dx$

**直观**：如果你在分布的重力场中放一块板子，期望就是平衡点的位置。  
**重要性质**：

- 线性：$E[aX + bY] = aE[X] + bE[Y]$（不需要独立性！）
- 函数期望：$E[g(X)] = \int g(x) f_X(x) dx$（洛必达变换，LOTUS）

### 4.2 方差——分布的"散布程度"

$$Var(X) = E[(X - E[X])^2] = E[X^2] - (E[X])^2$$

**直观**：从"重心"到各点的平均**平方**距离。取平方的原因：既消除正负抵消，又放大离群点的影响。

$$\sigma = \sqrt{Var(X)} \quad\text{(标准差)}$$

```python
# 方差的直觉：两个分布，相同期望，不同方差
np.random.seed(42)

X1 = np.random.normal(0, 1, 10000)   # N(0,1)
X2 = np.random.normal(0, 3, 10000)   # N(0,9)

print(f"X1 期望: {np.mean(X1):.3f}, 方差: {np.var(X1):.3f}")
print(f"X2 期望: {np.mean(X2):.3f}, 方差: {np.var(X2):.3f}")
# X1: 方差≈1, X2: 方差≈9
```

### 4.3 协方差——两个变量的"共变趋势"

$$Cov(X, Y) = E[(X - E[X])(Y - E[Y])] = E[XY] - E[X]E[Y]$$

**直观**：
- 正：X 大时 Y 也大
- 负：X 大时 Y 小
- 零：线性无关（但不独立！）

**重要性质**：
- $Var(X + Y) = Var(X) + Var(Y) + 2Cov(X, Y)$
- 独立 $\Rightarrow$ $Cov(X,Y) = 0$，但反之不成立

```python
# 协方差的直觉：协方差为 0 但不独立
x = np.linspace(-2, 2, 1000)
y = x**2  # 抛物线关系

cov_xy = np.cov(x, y)[0, 1]
print(f"协方差: {cov_xy:.3f}")  # ≈ 0
# 虽有完美关系，但协方差 ≈ 0 —— 对称性抵消了正负贡献
```

### 4.4 相关系数——归一化的协方差

$$\rho_{X,Y} = \frac{Cov(X, Y)}{\sigma_X \sigma_Y} \in [-1, 1]$$

**直观**：协方差的"无量纲化"。$\rho = 0.8$ 和 $\rho = 0.8$（摄氏/华氏）意义相同。

```python
# 相关系数的含义可视化
n = 500
rho = 0.7
mean = [0, 0]
cov = [[1, rho], [rho, 1]]
data = np.random.multivariate_normal(mean, cov, n)

print(f"经验相关系数: {np.corrcoef(data.T)[0, 1]:.3f}")  # ≈ 0.7
# rho=0.7 意味着 X 的差异可以"解释"约 49% (r²) 的 Y 的差异
```

### 4.5 为什么协方差/相关这么重要？

它们是**线性关系**的度量。概率论中大量的结构（如 PCA、回归、卡尔曼滤波）本质都是在"捕捉协方差结构"。

---

## 5. 大数定律与中心极限定理

### 5.1 大数定律（LLN）——"平均会收敛"

**弱大数定律**（随机收敛）：
$$\bar{X}_n = \frac{1}{n}\sum_{i=1}^n X_i \xrightarrow{P} \mu$$

**强大数定律**（几乎必然收敛）：
$$\bar{X}_n \xrightarrow{a.s.} \mu$$

**区别**：
- 弱：对任意 $\epsilon > 0$，$P(|\bar{X}_n - \mu| > \epsilon) \to 0$
- 强：$P(\lim_{n \to \infty} \bar{X}_n = \mu) = 1$

直观：弱是说"误差大于 ε 的概率趋近于 0"，强是说"从某个 n 开始，误差永远小于 ε"。

**为什么它 work？**  
方差缩放了：$Var(\bar{X}_n) = \sigma^2/n$，平均的方差随着 n 增大而缩小。Chebyshev 不等式给出定量界限：
$$P(|\bar{X}_n - \mu| \ge \epsilon) \le \frac{\sigma^2}{n\epsilon^2}$$

```python
# 大数定律演示：掷硬币的频率逼近 0.5
np.random.seed(42)
n_max = 10000
flips = np.random.binomial(1, 0.5, n_max)
running_mean = np.cumsum(flips) / np.arange(1, n_max + 1)

# 看收敛速度
for n in [10, 100, 1000, 10000]:
    print(f"n={n:5d}: 均值={running_mean[n-1]:.4f}, 距离理论值={running_mean[n-1]-0.5:.4f}")
# 收敛到 0.5，但速度约 1/sqrt(n)
```

### 5.2 中心极限定理（CLT）——"和的分布是正态的"

> 这是概率论最神奇的定理——没有之一。

$$Z_n = \frac{\bar{X}_n - \mu}{\sigma / \sqrt{n}} \xrightarrow{d} \mathcal{N}(0, 1)$$

**直观**：**不管原始分布是什么**（只要方差有限），**均值（或和）的分布总是趋向正态**。

为什么？因为正态分布是"最大熵分布"（给定均值和方差），大数定律说信息"搅匀"了，只剩下均值和方差两个统计量有意义。

```python
# CLT 演示：从指数分布（偏态）采样，看均值的分布
np.random.seed(42)

# 指数分布非常不对称，偏度 2
n_samples = 10000
sample_sizes = [1, 5, 30, 100]

for n in sample_sizes:
    # 每次采样 n 个样本，计算均值，重复 n_samples 次
    means = np.zeros(n_samples)
    for i in range(n_samples):
        means[i] = np.mean(np.random.exponential(scale=1.0, size=n))
    
    # 标准化
    z = (means - 1) / (1 / np.sqrt(n))
    
    # 检查近似正态的程度
    print(f"n={n:3d}: 标准化均值的偏度={np.mean((z-np.mean(z))**3):.3f} (期望 0)")
# n=1:  高度偏态（原始分布）
# n=5:  仍偏态
# n=30: 接近正态
# n=100: 几乎完美正态
```

### 5.3 为什么 LLN 和 CLT 如此重要？

| 定理 | 回答的问题 | 在实践中的意义 |
|------|-----------|--------------|
| LLN | 样本量够大时，样本均值可信吗？ | 大数弱→需要更多样本减小误差 |
| CLT | 误差有多大？什么分布？ | 给出了置信区间和假设检验的基础 |

**一句话**：LLN 让你敢赌，CLT 让你知道怎么赌。

---

## 6. 条件期望——"在已知信息下的最佳预测"

### 6.1 定义与直觉

**条件期望** $E[X | Y]$ 是在已知 Y 后，对 X 的**最佳预测**。

更准确地说，它是 Y 的函数 $g(Y)$，使得预测误差的均方最小化：
$$g^* = \arg\min_{g} E[(X - g(Y))^2]$$

解就是：$g^*(Y) = E[X | Y]$

**直觉**：如果你知道 Y，你对 X 的"最佳赌注"就是条件期望。

### 6.2 重要性质

**全期望公式（塔性质, law of total expectation）**：
$$E[X] = E[E[X | Y]]$$

这是整个随机过程中最重要的公式之一。**外层期望**是关于 Y 取的。

```python
# 塔性质的蒙特卡洛验证
np.random.seed(42)

# 两阶段过程：Y ~ Bernoulli(0.5)，X|Y ~ N(Y, 1)
N = 100000
Y = np.random.binomial(1, 0.5, N)
X = np.random.normal(Y, 1)

# 直接算 E[X]
E_X_direct = np.mean(X)

# 算 E[E[X|Y]]
E_X_given_Y_0 = np.mean(X[Y == 0])  # E[X|Y=0]
E_X_given_Y_1 = np.mean(X[Y == 1])  # E[X|Y=1]
E_X_tower = 0.5 * E_X_given_Y_0 + 0.5 * E_X_given_Y_1

print(f"直接: {E_X_direct:.3f}, 塔性质: {E_X_tower:.3f}")
# 两者一致: ≈ 0.5
```

### 6.3 条件期望 vs 无条件期望

| 性质 | 条件期望 $E[X\|Y]$ | 无条件期望 $E[X]$ |
|------|------------------|-----------------|
| 谁在变 | 是 Y 的随机变量 | 常数 |
| 预测性 | 使用 Y 的信息 | 不用任何信息 |
| 方差 | 总是更小或相等 | 更大（除非独立） |

**条件降低不确定性**：$Var(X) = Var(E[X|Y]) + E[Var(X|Y)]$（方差分解）

### 6.4 条件期望的几何视角

$E[X | Y]$ 是 X 在"由 Y 生成的函数空间"上的**正交投影**。  
这就是为什么条件期望和最小二乘回归是一回事——只是条件期望允许任意非线性。

### 6.5 为什么条件期望是 Martingale 和 RL 的基础

**Martingale 定义**：一个随机过程 $X_t$，如果 $E[X_{t+1} | X_1, \dots, X_t] = X_t$，则是 Martingale。

**强化学习中的价值函数**：
$$V^\pi(s) = E\left[\sum_{t=0}^\infty \gamma^t R_t \;\Big|\; S_0 = s\right]$$

这就是条件期望——已知当前状态，对未来累积回报的**最佳预测**。

```python
# 条件期望在 RL 中的雏形：给定单价，预测总营收
np.random.seed(42)

n = 1000
price = np.random.uniform(10, 50, n)          # 价格
demand = 100 - 0.5 * price + np.random.normal(0, 5, n)  # 需求（受价格影响）
revenue = price * demand                       # 营收

# E[revenue | price] 就是条件期望
# 用 KNN 近似计算条件期望
from collections import defaultdict

k = 50
price_bins = np.linspace(10, 50, 20)
price_idx = np.digitize(price, price_bins)

cond_mean = defaultdict(list)
for i in range(n):
    cond_mean[price_idx[i]].append(revenue[i])

for k in sorted(cond_mean.keys()):
    pass  # 每个价格段的条件期望（近似）

# 实际中 RL 用神经网络近似条件期望（即价值函数）
print(f"示例完成 - 条件期望≈神经网络价值函数")
```

---

## 7. 综合练习：联合理解

一个稍微综合的栗子，把大部分概念串起来：

```python
"""
场景：某平台用户行为建模
- 用户登录次数 X（服从 Poisson 分布）
- 每次登录的购买金额 Y_i（服从 Exponential 分布）
- 总消费 S = Σ Y_i（复合分布）
"""
import numpy as np

np.random.seed(42)
n_users = 50000

# 1) 随机变量类型：X 离散，Y_i 连续
lam = 3  # 平均每天登录 3 次
X = np.random.poisson(lam, n_users)

# 2) 总消费 S 是 X 个独立同分布指数随机变量的和
rate = 0.5  # 平均每次消费 2 元
S = np.zeros(n_users)
for i in range(n_users):
    if X[i] > 0:
        S[i] = np.sum(np.random.exponential(scale=1/rate, size=X[i]))

# 3) 大数定律 + CLT
# 理论 E[S] = E[X] * E[Y] = 3 * 2 = 6
# 理论 Var[S] = E[X] * Var[Y] + Var[X] * (E[Y])² = 3 * 4 + 3 * 4 = 24

print(f"E[S] 理论: 6.00, 经验: {np.mean(S):.3f}")
print(f"Var[S] 理论: 24.00, 经验: {np.var(S):.3f}")

# 4) 相关性：X 和 S 显然正相关
print(f"Corr(X, S): {np.corrcoef(X, S)[0, 1]:.3f}")  # ≈ 0.4-0.6

# 5) 条件期望 E[S | X] = X * E[Y] = 2X
# 检查条件期望
for x in [0, 1, 2, 3, 5, 10]:
    mask = X == x
    if np.sum(mask) > 10:
        empirical = np.mean(S[mask])
        theoretical = x * 2
        print(f"E[S|X={x:2d}]: 理论={theoretical:.1f}, 经验={empirical:.2f}")
```

---

## 8. 后记：通向下一站

本课覆盖的概念是后续课程的"词汇表"：

| 下一站 | 必备概念 |
|--------|---------|
| **信息论** | 随机变量、期望、分布差距 → 熵、KL 散度 |
| **统计推断** | 大数定律 + CLT → 置信区间、假设检验 |
| **随机过程** | 条件期望 → Martingale → 鞅收敛 |
| **强化学习** | 条件期望 → Bellman 方程 → Q-learning |

**最重要的是**：每次看到一个概率公式，先问：
> "为什么它长这样？它解决了什么问题？它的直觉是什么？"

公式会忘，但直觉不会。而直觉才是让你在复杂问题上能推导出正确答案的东西。

---

> **下一课预告**：信息论基础——熵、互信息、KL 散度的概率视角
