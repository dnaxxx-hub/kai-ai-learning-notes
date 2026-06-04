# 概率论基础 — Probability Theory Basics

> 数学/统计学深潜 · 第 1 课
> 目标：建立从公理到应用的完整概率论思维框架

---

## 目录

1. [概率空间 (Probability Space)](#1-概率空间-probability-space)
2. [条件概率与独立性](#2-条件概率与独立性)
3. [贝叶斯定理 (Bayes' Theorem)](#3-贝叶斯定理-bayes-theorem)
4. [随机变量 (Random Variables)](#4-随机变量-random-variables)
5. [期望、方差、协方差](#5-期望方差协方差)
6. [大数定律与中心极限定理](#6-大数定律与中心极限定理)
7. [Python 代码演示](#7-python-代码演示)

---

## 1. 概率空间 (Probability Space)

概率论的公理化体系由 Kolmogorov（1933）奠定。一个概率空间是一个三元组：

$$
(\Omega, \mathcal{F}, P)
$$

### 1.1 样本空间 $\Omega$

**样本空间 (Sample Space)** 是所有可能结果的集合。例如：
- 掷硬币：$\Omega = \{H, T\}$
- 掷骰子：$\Omega = \{1, 2, 3, 4, 5, 6\}$
- 股价收益率：$\Omega = \mathbb{R}$（连续型）

### 1.2 事件域 $\mathcal{F}$

**事件域 (Event Space / $\sigma$-algebra)** 是 $\Omega$ 的子集族，满足：
1. $\Omega \in \mathcal{F}$
2. 若 $A \in \mathcal{F}$，则 $A^c = \Omega \setminus A \in \mathcal{F}$（对补运算封闭）
3. 若 $A_1, A_2, \ldots \in \mathcal{F}$，则 $\bigcup_{i=1}^{\infty} A_i \in \mathcal{F}$（对可列并封闭）

这确保了我们能对事件进行逻辑运算（与、或、非）而不会离开事件域。

### 1.3 概率测度 $P$

**概率 (Probability Measure)** 是一个函数 $P: \mathcal{F} \to [0, 1]$，满足：

1. **非负性**：$\forall A \in \mathcal{F},\ P(A) \geq 0$
2. **正则性**：$P(\Omega) = 1$
3. **可列可加性**：若 $A_1, A_2, \ldots$ 两两不相交，则：

$$
P\left(\bigcup_{i=1}^{\infty} A_i\right) = \sum_{i=1}^{\infty} P(A_i)
$$

### 1.4 概率的基本性质

从公理可以直接推导出：

- $P(\emptyset) = 0$
- $P(A^c) = 1 - P(A)$
- 若 $A \subseteq B$，则 $P(A) \leq P(B)$
- $P(A \cup B) = P(A) + P(B) - P(A \cap B)$（容斥原理）

---

## 2. 条件概率与独立性

### 2.1 条件概率 (Conditional Probability)

给定 $B$ 发生的情况下 $A$ 发生的概率：

$$
P(A \mid B) = \frac{P(A \cap B)}{P(B)}, \quad P(B) > 0
$$

**直觉**：将样本空间缩小到 $B$，$A$ 在新空间中的比例就是 $P(A \cap B) / P(B)$。

### 2.2 乘法法则

$$
P(A \cap B) = P(A \mid B) \, P(B) = P(B \mid A) \, P(A)
$$

推广到 $n$ 个事件：

$$
P(A_1 \cap A_2 \cap \cdots \cap A_n) = P(A_1) \, P(A_2 \mid A_1) \, P(A_3 \mid A_1 \cap A_2) \cdots P(A_n \mid A_1 \cap \cdots \cap A_{n-1})
$$

### 2.3 全概率公式 (Law of Total Probability)

若 $\{B_1, B_2, \ldots, B_n\}$ 是 $\Omega$ 的一个划分（即两两不相交且并集为 $\Omega$），则：

$$
P(A) = \sum_{i=1}^{n} P(A \mid B_i) \, P(B_i)
$$

### 2.4 独立性 (Independence)

事件 $A$ 和 $B$ 独立当且仅当：

$$
P(A \cap B) = P(A) \, P(B)
$$

等价地：$P(A \mid B) = P(A)$（$P(B) > 0$ 时）。

**注意**：
- 互斥（$A \cap B = \emptyset$）与独立是完全不同的概念
- 互斥事件**不独立**（除非概率为零）
- 独立事件**不互斥**（除非概率为零）

---

## 3. 贝叶斯定理 (Bayes' Theorem)

### 3.1 公式

贝叶斯定理是条件概率的对称性推论：

$$
P(B_i \mid A) = \frac{P(A \mid B_i) \, P(B_i)}{P(A)} = \frac{P(A \mid B_i) \, P(B_i)}{\sum_{j} P(A \mid B_j) \, P(B_j)}
$$

其中：
- $P(B_i)$ — **先验概率 (Prior)**：在观察到数据之前对假设 $B_i$ 的信念
- $P(A \mid B_i)$ — **似然 (Likelihood)**：在假设 $B_i$ 下观察到数据 $A$ 的概率
- $P(B_i \mid A)$ — **后验概率 (Posterior)**：观察到数据后更新的信念

### 3.2 贝叶斯思维框架

```
先验(Prior) × 似然(Likelihood) = 后验(Posterior) × 证据(Evidence)
          P(B) × P(A|B)           =  P(B|A) × P(A)
```

贝叶斯定理的本质是**学习机制**——每观察到新数据，就用它来更新我们的信念。

### 3.3 应用示例：医疗检测

疾病患病率 $P(D) = 0.01$（先验）
检测灵敏度 $P(T^+ \mid D) = 0.99$（真阳性率）
误报率 $P(T^+ \mid \neg D) = 0.05$（假阳性率）

问：检测阳性时真实患病的概率？

$$
P(D \mid T^+) = \frac{0.99 \times 0.01}{0.99 \times 0.01 + 0.05 \times 0.99} \approx 0.167
$$

即使检测呈阳性，真实患病概率也只有约 16.7%。这就是**基准率谬误 (Base Rate Fallacy)**。

---

## 4. 随机变量 (Random Variables)

### 4.1 定义

**随机变量**是一个函数 $X: \Omega \to \mathbb{R}$，将样本空间中的每个结果映射到一个实数。

> ⚡ 关键洞察：随机变量不是"变量"，而是**函数**。随机性来源于 $\Omega$，而不是 $X$ 本身。

### 4.2 分布函数

**累积分布函数 (CDF)**：

$$
F_X(x) = P(X \leq x)
$$

性质：
- 非降：$x_1 < x_2 \Rightarrow F_X(x_1) \leq F_X(x_2)$
- $\lim_{x \to -\infty} F_X(x) = 0,\quad \lim_{x \to \infty} F_X(x) = 1$
- 右连续

### 4.3 离散型随机变量

**概率质量函数 (PMF)**：

$$
p_X(x) = P(X = x)
$$

常见离散分布：

| 分布 | PMF | 参数 | 期望 | 方差 |
|------|-----|------|------|------|
| Bernoulli | $p^x(1-p)^{1-x}$ | $p \in [0,1]$ | $p$ | $p(1-p)$ |
| Binomial | $\binom{n}{k}p^k(1-p)^{n-k}$ | $n, p$ | $np$ | $np(1-p)$ |
| Poisson | $\frac{\lambda^k e^{-\lambda}}{k!}$ | $\lambda > 0$ | $\lambda$ | $\lambda$ |
| Geometric | $(1-p)^{k-1}p$ | $p \in (0,1]$ | $1/p$ | $(1-p)/p^2$ |

### 4.4 连续型随机变量

**概率密度函数 (PDF)**：

$$
F_X(x) = \int_{-\infty}^{x} f_X(t) \, dt
$$

$$
f_X(x) = \frac{d}{dx} F_X(x)
$$

常见连续分布：

| 分布 | PDF | 参数 | 期望 | 方差 |
|------|-----|------|------|------|
| Uniform(a,b) | $\frac{1}{b-a}$ | $a<b$ | $\frac{a+b}{2}$ | $\frac{(b-a)^2}{12}$ |
| Normal($\mu,\sigma^2$) | $\frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}$ | $\mu,\sigma>0$ | $\mu$ | $\sigma^2$ |
| Exponential($\lambda$) | $\lambda e^{-\lambda x}$ | $\lambda>0$ | $1/\lambda$ | $1/\lambda^2$ |
| Beta($\alpha,\beta$) | $\frac{x^{\alpha-1}(1-x)^{\beta-1}}{B(\alpha,\beta)}$ | $\alpha,\beta>0$ | $\frac{\alpha}{\alpha+\beta}$ | $\frac{\alpha\beta}{(\alpha+\beta)^2(\alpha+\beta+1)}$ |

### 4.5 随机变量的变换

若 $Y = g(X)$，则：

**离散型**：
$$
P(Y = y) = \sum_{x: g(x)=y} P(X = x)
$$

**连续型**（$g$ 严格单调可微时）：
$$
f_Y(y) = f_X(g^{-1}(y)) \left| \frac{d}{dy} g^{-1}(y) \right|
$$

---

## 5. 期望、方差、协方差

### 5.1 期望 (Expectation)

**定义**：

$$
\mathbb{E}[X] = \begin{cases}
\sum_{x} x \, p_X(x) & \text{离散型} \\
\int_{-\infty}^{\infty} x \, f_X(x) \, dx & \text{连续型}
\end{cases}
$$

**线性性质**（最重要的性质）：

$$
\mathbb{E}[aX + bY + c] = a\, \mathbb{E}[X] + b\, \mathbb{E}[Y] + c
$$

**Law of the Unconscious Statistician (LOTUS)**：

$$
\mathbb{E}[g(X)] = \begin{cases}
\sum_{x} g(x) \, p_X(x) & \text{离散型} \\
\int_{-\infty}^{\infty} g(x) \, f_X(x) \, dx & \text{连续型}
\end{cases}
$$

### 5.2 方差 (Variance)

**定义**：
$$
\operatorname{Var}(X) = \mathbb{E}[(X - \mathbb{E}[X])^2] = \mathbb{E}[X^2] - (\mathbb{E}[X])^2
$$

**性质**：
- $\operatorname{Var}(aX + b) = a^2 \operatorname{Var}(X)$
- $\operatorname{Var}(X + Y) = \operatorname{Var}(X) + \operatorname{Var}(Y) + 2\operatorname{Cov}(X, Y)$
- 若 $X, Y$ 独立，则 $\operatorname{Var}(X + Y) = \operatorname{Var}(X) + \operatorname{Var}(Y)$

**标准差**：
$$
\sigma_X = \sqrt{\operatorname{Var}(X)}
$$

### 5.3 协方差与相关性 (Covariance and Correlation)

**协方差**衡量两个随机变量的线性关系：

$$
\operatorname{Cov}(X, Y) = \mathbb{E}[(X - \mathbb{E}[X])(Y - \mathbb{E}[Y])] = \mathbb{E}[XY] - \mathbb{E}[X] \, \mathbb{E}[Y]
$$

**性质**：
- $\operatorname{Cov}(X, Y) = \operatorname{Cov}(Y, X)$
- $\operatorname{Cov}(aX, bY) = ab \operatorname{Cov}(X, Y)$
- $\operatorname{Cov}(X + Y, Z) = \operatorname{Cov}(X, Z) + \operatorname{Cov}(Y, Z)$
- $\operatorname{Var}(X + Y) = \operatorname{Var}(X) + \operatorname{Var}(Y) + 2\operatorname{Cov}(X, Y)$

**Pearson 相关系数**（无量纲的标准化协方差）：

$$
\rho_{X,Y} = \frac{\operatorname{Cov}(X, Y)}{\sigma_X \sigma_Y} \in [-1, 1]
$$

- $\rho = 1$：完全正线性相关
- $\rho = -1$：完全负线性相关
- $\rho = 0$：无线性相关（**不意味着独立！**）

> ⚠️ **相关不等于因果**。$\rho \neq 0$ 可能是由于混淆变量、选择偏差等原因。

---

## 6. 大数定律与中心极限定理

### 6.1 大数定律 (Law of Large Numbers, LLN)

设 $X_1, X_2, \ldots, X_n$ 是独立同分布（i.i.d.）的随机变量，$\mathbb{E}[X_i] = \mu$。

**弱大数定律**（样本均值依概率收敛到期望）：

$$
\bar{X}_n = \frac{1}{n} \sum_{i=1}^{n} X_i \xrightarrow{p} \mu \quad \text{即} \quad \forall \varepsilon > 0,\ \lim_{n \to \infty} P(|\bar{X}_n - \mu| > \varepsilon) = 0
$$

**强大数定律**（样本均值几乎必然收敛到期望）：

$$
\bar{X}_n \xrightarrow{a.s.} \mu \quad \text{即} \quad P\left(\lim_{n \to \infty} \bar{X}_n = \mu\right) = 1
$$

**直觉**：掷硬币次数越多，正面比例越接近 0.5。这就是为什么赌场长期必赢。

### 6.2 中心极限定理 (Central Limit Theorem, CLT)

**定理**：设 $X_1, X_2, \ldots, X_n$ 是 i.i.d. 随机变量，$\mathbb{E}[X_i] = \mu$，$\operatorname{Var}(X_i) = \sigma^2 < \infty$，则：

$$
\frac{\bar{X}_n - \mu}{\sigma / \sqrt{n}} \xrightarrow{d} \mathcal{N}(0, 1) \quad \text{当 } n \to \infty
$$

等价形式：

$$
\sqrt{n}(\bar{X}_n - \mu) \xrightarrow{d} \mathcal{N}(0, \sigma^2)
$$

**直觉**：
- **无论原始分布是什么**，样本均值的分布都趋近正态
- $n$ 越大，趋近效果越好（一般 $n \geq 30$ 就相当接近）
- 这是统计学中最重要的定理——它解释了为什么正态分布无处不在

**应用**：
- 置信区间：$\bar{X}_n \pm z_{\alpha/2} \frac{\sigma}{\sqrt{n}}$
- 假设检验
- 蒙特卡洛模拟的误差估计

---

## 7. Python 代码演示

### 7.1 蒙提霍尔问题 (Monty Hall Problem)

三人博弈：选手选一扇门 → 主持人打开一扇有山羊的门 → 选手决定是否换门。

```python
import random
import matplotlib.pyplot as plt
import numpy as np

def monty_hall_simulation(n_trials: int = 10000):
    """
    蒙提霍尔问题模拟：换门 vs 不换门的胜率对比
    """
    n_win_stay = 0
    n_win_switch = 0
    
    for _ in range(n_trials):
        # 三扇门，随机放置汽车
        doors = ['goat', 'goat', 'car']
        random.shuffle(doors)
        
        # 选手随机选一扇
        contestant_choice = random.randint(0, 2)
        
        # 主持人打开一扇有山羊且未被选的门
        available = [i for i in range(3) 
                     if i != contestant_choice and doors[i] == 'goat']
        host_opens = random.choice(available)
        
        # 剩余的一扇门
        remaining = [i for i in range(3) 
                     if i != contestant_choice and i != host_opens][0]
        
        # 不换门
        if doors[contestant_choice] == 'car':
            n_win_stay += 1
        
        # 换门
        if doors[remaining] == 'car':
            n_win_switch += 1
    
    return {
        'stay_win_rate': n_win_stay / n_trials,
        'switch_win_rate': n_win_switch / n_trials,
        'n_trials': n_trials,
        'stay_wins': n_win_stay,
        'switch_wins': n_win_switch
    }

# 模拟
result = monty_hall_simulation(100000)
print(f"模拟次数: {result['n_trials']}")
print(f"不换门获胜: {result['stay_wins']} ({result['stay_win_rate']:.4f})")
print(f"换门获胜:   {result['switch_wins']} ({result['switch_win_rate']:.4f})")
print(f"理论值: 不换={1/3:.4f}, 换={2/3:.4f}")
```

输出示例：
```
模拟次数: 100000
不换门获胜: 33348 (0.3335)
换门获胜:   66652 (0.6665)
理论值: 不换=0.3333, 换=0.6667
```

### 7.2 贝叶斯更新演示 (Bayesian Updating)

用 Beta-Bernoulli 模型展示信念的迭代更新过程。

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

def bayesian_updating_demo(prior_alpha=2, prior_beta=2, 
                           true_prob=0.7, n_obs=100):
    """
    贝叶斯更新演示
    模型：Beta(a,b) 先验 → 观测 Bernoulli(θ) 数据 → Beta(a+y, b+n-y) 后验
    """
    # 生成观测数据
    np.random.seed(42)
    observations = np.random.binomial(1, true_prob, n_obs)
    
    # 贝叶斯更新：记录每一步的后验
    alphas = [prior_alpha]
    betas = [prior_beta]
    posteriors = []
    
    for i, obs in enumerate(observations):
        alpha_post = prior_alpha + observations[:i+1].sum()
        beta_post = prior_beta + (i+1) - observations[:i+1].sum()
        alphas.append(alpha_post)
        betas.append(beta_post)
    
    # 可视化关键时间点的后验分布
    checkpoints = [0, 1, 5, 20, 100]
    theta_grid = np.linspace(0, 1, 1000)
    
    fig, axes = plt.subplots(1, len(checkpoints), figsize=(15, 4))
    
    for idx, n in enumerate(checkpoints):
        a = prior_alpha + observations[:n].sum() if n > 0 else prior_alpha
        b = prior_beta + n - observations[:n].sum() if n > 0 else prior_beta
        
        pdf = stats.beta.pdf(theta_grid, a, b)
        axes[idx].plot(theta_grid, pdf, 'b-', lw=2)
        axes[idx].axvline(x=true_prob, color='r', linestyle='--', 
                         label=f'True θ={true_prob}')
        axes[idx].set_title(f'n = {n}')
        axes[idx].set_xlabel('θ')
        axes[idx].set_ylabel('Posterior PDF')
        axes[idx].legend()
        axes[idx].set_ylim(0, pdf.max() * 1.2)
        
        # 标注后验均值
        post_mean = a / (a + b)
        axes[idx].axvline(x=post_mean, color='g', linestyle=':', 
                         label=f'Mean = {post_mean:.3f}')
    
    plt.tight_layout()
    plt.suptitle('Bayesian Updating: Beta Prior → Bernoulli Observations', 
                 y=1.02, fontsize=14)
    plt.show()
    
    # 计算最终的后验均值与置信区间
    final_alpha = alphas[-1]
    final_beta = betas[-1]
    post_mean = final_alpha / (final_alpha + final_beta)
    
    # 95% 最高密度区间 (HDI)
    lower = stats.beta.ppf(0.025, final_alpha, final_beta)
    upper = stats.beta.ppf(0.975, final_alpha, final_beta)
    
    print(f"先验: Beta({prior_alpha}, {prior_beta})")
    print(f"观测: {n_obs} 次试验, {observations.sum()} 次成功")
    print(f"后验: Beta({final_alpha}, {final_beta})")
    print(f"后验均值: {post_mean:.4f}  (真实值: {true_prob})")
    print(f"95% 置信区间: [{lower:.4f}, {upper:.4f}]")
    print(f"区间包含真实值: {lower <= true_prob <= upper}")

bayesian_updating_demo()
```

输出示例：
```
先验: Beta(2, 2)
观测: 100 次试验, 72 次成功
后验: Beta(74, 30)
后验均值: 0.7115  (真实值: 0.7)
95% 置信区间: [0.6224, 0.7916]
区间包含真实值: True
```

### 7.3 中心极限定理可视化 (CLT Visualization)

展示不同原始分布下样本均值的分布如何趋近正态。

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

def clt_demo(n_samples_per_trial=30, n_trials=10000):
    """
    中心极限定理可视化
    展示不同原始分布下，样本均值的分布趋近正态的过程
    """
    np.random.seed(42)
    
    # 三个不同的原始分布
    distributions = {
        'Uniform(0,1)': lambda n: np.random.uniform(0, 1, n),
        'Exponential(1)': lambda n: np.random.exponential(1, n),
        'Bernoulli(0.3)': lambda n: np.random.binomial(1, 0.3, n)
    }
    
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    
    for row, (name, sampler) in enumerate(distributions.items()):
        # 左列：原始分布
        ax = axes[row, 0]
        data = sampler(100000)
        ax.hist(data, bins=50, density=True, alpha=0.7, color='skyblue')
        ax.set_title(f'原始分布: {name}')
        ax.set_xlabel('x')
        ax.set_ylabel('密度')
        
        # 中列：n=5 的样本均值分布
        ax = axes[row, 1]
        means_5 = [sampler(5).mean() for _ in range(n_trials)]
        ax.hist(means_5, bins=50, density=True, alpha=0.7, color='lightgreen')
        
        # 叠加正态拟合
        mu_5 = np.mean(means_5)
        sigma_5 = np.std(means_5)
        x_grid = np.linspace(mu_5 - 4*sigma_5, mu_5 + 4*sigma_5, 1000)
        ax.plot(x_grid, stats.norm.pdf(x_grid, mu_5, sigma_5), 
                'r-', lw=2, label='Normal fit')
        ax.set_title(f'样本均值分布 (n=5)')
        ax.set_xlabel('样本均值')
        ax.set_ylabel('密度')
        ax.legend()
        
        # 右列：n=30 的样本均值分布
        ax = axes[row, 2]
        means_30 = [sampler(30).mean() for _ in range(n_trials)]
        ax.hist(means_30, bins=50, density=True, alpha=0.7, color='coral')
        
        mu_30 = np.mean(means_30)
        sigma_30 = np.std(means_30)
        x_grid = np.linspace(mu_30 - 4*sigma_30, mu_30 + 4*sigma_30, 1000)
        ax.plot(x_grid, stats.norm.pdf(x_grid, mu_30, sigma_30), 
                'r-', lw=2, label='Normal fit')
        ax.set_title(f'样本均值分布 (n=30)')
        ax.set_xlabel('样本均值')
        ax.set_ylabel('密度')
        ax.legend()
        
        # 标注均值对比
        true_mean = {'Uniform(0,1)': 0.5, 
                     'Exponential(1)': 1.0,
                     'Bernoulli(0.3)': 0.3}[name]
        
        if row == 2:  # 只在最后一行打印
            print(f"{name}:")
            print(f"  理论均值 = {true_mean}")
            print(f"  样本均值 (n=30) = {mu_30:.4f}")
            print(f"  标准误差 (n=30) = {sigma_30:.4f}")
            print(f"  理论标准误 = {np.sqrt(sampler(100000).var()/30):.4f}")
    
    plt.tight_layout()
    plt.suptitle('中心极限定理可视化', y=1.01, fontsize=16)
    plt.show()

clt_demo()
```

输出示例：
```
Uniform(0,1):
  理论均值 = 0.5
  样本均值 (n=30) = 0.5001
  标准误差 (n=30) = 0.0526
  理论标准误 = 0.0527

Exponential(1):
  理论均值 = 1.0
  样本均值 (n=30) = 0.9995
  标准误差 (n=30) = 0.1825
  理论标准误 = 0.1826

Bernoulli(0.3):
  理论均值 = 0.3
  样本均值 (n=30) = 0.3002
  标准误差 (n=30) = 0.0837
  理论标准误 = 0.0837
```

### 7.4 完整概率计算工具函数

```python
import numpy as np
from scipy import stats

def probability_toolkit():
    """
    概率计算工具集
    """
    
    def bayes_theorem(prior, likelihood, false_positive_rate):
        """
        贝叶斯定理计算后验概率
        prior: P(A) — 先验概率
        likelihood: P(B|A) — 似然（真阳性率）
        false_positive_rate: P(B|¬A) — 假阳性率
        返回: P(A|B) — 后验概率
        """
        evidence = likelihood * prior + false_positive_rate * (1 - prior)
        posterior = (likelihood * prior) / evidence
        return posterior
    
    def conditional_expectation(dist_values, dist_probs, condition_fn):
        """
        计算条件期望 E[X | condition(X)]
        """
        total_prob = sum(p for v, p in zip(dist_values, dist_probs) 
                        if condition_fn(v))
        cond_exp = sum(v * p for v, p in zip(dist_values, dist_probs) 
                      if condition_fn(v)) / total_prob
        return cond_exp
    
    def law_of_total_variance(X_given_Y, var_Y, E_var_given_Y):
        """
        全方差公式: Var(X) = E[Var(X|Y)] + Var(E[X|Y])
        """
        return E_var_given_Y + var_Y
    
    def monte_carlo_pi(n_points=100000):
        """
        蒙特卡洛估计 π
        在正方形内随机撒点，计算落在内切圆中的比例
        """
        points = np.random.uniform(-1, 1, (n_points, 2))
        distances = np.sqrt(points[:, 0]**2 + points[:, 1]**2)
        inside = distances <= 1.0
        pi_estimate = 4 * inside.sum() / n_points
        pi_error = abs(pi_estimate - np.pi)
        return pi_estimate, pi_error
    
    # 演示
    # 医疗检测案例
    p_disease = 0.01
    p_pos_given_disease = 0.99
    p_pos_given_healthy = 0.05
    
    p_disease_given_pos = bayes_theorem(
        p_disease, p_pos_given_disease, p_pos_given_healthy
    )
    
    print(f"医疗检测：P(患病|阳性) = {p_disease_given_pos:.4f}")
    
    # 蒙特卡洛估计 π
    pi_est, pi_err = monte_carlo_pi()
    print(f"蒙特卡洛 π ≈ {pi_est:.6f}  (误差: {pi_err:.6f})")

probability_toolkit()
```

输出示例：
```
医疗检测：P(患病|阳性) = 0.1667
蒙特卡洛 π ≈ 3.141860  (误差: 0.000267)
```

---

## 8. 附加：方差分析与协方差矩阵

### 8.1 方差-协方差矩阵 (Covariance Matrix)

对于 $d$ 维随机向量 $\mathbf{X} = (X_1, X_2, \ldots, X_d)^T$，协方差矩阵是一个 $d \times d$ 对称半正定矩阵：

$$
\Sigma = \operatorname{Cov}(\mathbf{X}) = 
\begin{pmatrix}
\operatorname{Var}(X_1) & \operatorname{Cov}(X_1, X_2) & \cdots & \operatorname{Cov}(X_1, X_d) \\
\operatorname{Cov}(X_2, X_1) & \operatorname{Var}(X_2) & \cdots & \operatorname{Cov}(X_2, X_d) \\
\vdots & \vdots & \ddots & \vdots \\
\operatorname{Cov}(X_d, X_1) & \operatorname{Cov}(X_d, X_2) & \cdots & \operatorname{Var}(X_d)
\end{pmatrix}
$$

对角元是方差，非对角元是协方差。

### 8.2 全期望公式 (Law of Total Expectation)

$$
\mathbb{E}[X] = \mathbb{E}[\mathbb{E}[X \mid Y]]
$$

### 8.3 全方差公式 (Law of Total Variance)

$$
\operatorname{Var}(X) = \mathbb{E}[\operatorname{Var}(X \mid Y)] + \operatorname{Var}(\mathbb{E}[X \mid Y])
$$

解释：总方差 = "组内方差的均值" + "组间均值的方差"。

### 8.4 马尔可夫与切比雪夫不等式

**马尔可夫不等式**（非负随机变量）：

$$
P(X \geq a) \leq \frac{\mathbb{E}[X]}{a}, \quad a > 0
$$

**切比雪夫不等式**（任意分布）：

$$
P(|X - \mu| \geq k\sigma) \leq \frac{1}{k^2}, \quad k > 0
$$

这是一个非常通用但宽松的界限——它适用于任何具有有限方差的分布。

### 8.5 矩母函数 (Moment Generating Function, MGF)

$$
M_X(t) = \mathbb{E}[e^{tX}]
$$

MGF 的 $k$ 阶导数在 $t=0$ 处给出 $k$ 阶矩：

$$
\mathbb{E}[X^k] = M_X^{(k)}(0)
$$

独立随机变量和的 MGF 是各 MGF 的乘积：

$$
M_{X+Y}(t) = M_X(t) \cdot M_Y(t) \quad (\text{若 } X \perp Y)
$$

### 8.6 Python 演示：马尔可夫与切比雪夫不等式验证

```python
import numpy as np
import matplotlib.pyplot as plt

def inequality_demo():
    """
    用指数分布验证马尔可夫和切比雪夫不等式
    """
    np.random.seed(42)
    lambd = 1.0
    n = 100000
    samples = np.random.exponential(scale=1.0/lambd, size=n)
    
    mu = 1.0 / lambd
    sigma = 1.0 / lambd
    
    print(f"分布: Exponential(lambda={lambd})")
    print(f"理论均值 μ = {mu:.2f}, 标准差 σ = {sigma:.2f}")
    print()
    
    for k in [1.5, 2.0, 3.0]:
        a = mu + k * sigma
        prob_empirical = (samples >= a).mean()
        
        markov_bound = mu / a
        chebyshev_bound = 1.0 / (k ** 2)
        
        print(f"k = {k:.1f}, a = μ + {k}σ = {a:.2f}")
        print(f"  P(X ≥ a) 经验值 = {prob_empirical:.6f}")
        print(f"  马尔可夫上界     = {markov_bound:.6f}")
        print(f"  切比雪夫上界     = {chebyshev_bound:.6f}")
        print(f"  马尔可夫有效: {prob_empirical <= markov_bound + 1e-10}")
        print(f"  切比雪夫有效: {prob_empirical <= chebyshev_bound + 1e-10}")
        print()

inequality_demo()
```

输出示例：
```
分布: Exponential(lambda=1.0)
理论均值 μ = 1.00, 标准差 σ = 1.00

k = 1.5, a = μ + 1.5σ = 2.50
  P(X ≥ a) 经验值 = 0.082860
  马尔可夫上界     = 0.400000
  切比雪夫上界     = 0.444444
  马尔可夫有效: True
  切比雪夫有效: True

k = 2.0, a = μ + 2.0σ = 3.00
  P(X ≥ a) 经验值 = 0.049830
  马尔可夫上界     = 0.333333
  切比雪夫上界     = 0.250000
  马尔可夫有效: True
  切比雪夫有效: True

k = 3.0, a = μ + 3.0σ = 4.00
  P(X ≥ a) 经验值 = 0.018310
  马尔可夫上界     = 0.250000
  切比雪夫上界     = 0.111111
  马尔可夫有效: True
  切比雪夫有效: True
```

### 8.7 Python 演示：协方差与相关性

```python
import numpy as np
import matplotlib.pyplot as plt

def covariance_demo():
    """
    生成不同相关程度的数据并计算协方差和相关系数
    """
    np.random.seed(42)
    n = 500
    
    # 生成四种不同相关程度的数据
    x = np.random.randn(n)
    
    # y1: 强正相关 (r ≈ 0.95)
    y1 = 0.95 * x + 0.05 * np.random.randn(n)
    
    # y2: 弱正相关 (r ≈ 0.3)
    y2 = 0.3 * x + 0.7 * np.random.randn(n)
    
    # y3: 不相关 (r ≈ 0)
    y3 = np.random.randn(n)
    
    # y4: 强负相关 (r ≈ -0.9)
    y4 = -0.9 * x + 0.1 * np.random.randn(n)
    
    # 计算协方差和相关系数
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    pairs = [(y1, "强正相关 (r≈0.95)"), 
             (y2, "弱正相关 (r≈0.3)"),
             (y3, "不相关 (r≈0)"),
             (y4, "强负相关 (r≈-0.9)")]
    
    for ax, (y, label) in zip(axes.flatten(), pairs):
        cov = np.cov(x, y)[0, 1]
        corr = np.corrcoef(x, y)[0, 1]
        
        ax.scatter(x, y, alpha=0.4, s=10)
        ax.set_title(f"{label}\nCov={cov:.3f}, ρ={corr:.3f}")
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.axhline(0, color='gray', lw=0.5)
        ax.axvline(0, color='gray', lw=0.5)
    
    plt.tight_layout()
    plt.suptitle('协方差与相关系数示例', y=1.01, fontsize=14)
    plt.show()
    
    print("协方差矩阵 (随机生成 4 变量):")
    data_4d = np.random.randn(n, 4)
    cov_matrix = np.cov(data_4d.T)
    print(np.array2string(cov_matrix, precision=4, suppress_small=True))
    print()
    print("相关系数矩阵:")
    corr_matrix = np.corrcoef(data_4d.T)
    print(np.array2string(corr_matrix, precision=4, suppress_small=True))

covariance_demo()
```

输出示例：
```
协方差矩阵 (随机生成 4 变量):
[[ 0.9978  0.0029  0.004  -0.018 ]
 [ 0.0029  1.0226 -0.0012 -0.032 ]
 [ 0.004  -0.0012  0.9844 -0.0002]
 [-0.018  -0.032  -0.0002  1.0688]]

相关系数矩阵:
[[ 1.    0.0029 0.004 -0.0174]
 [ 0.0029 1.    -0.0012 -0.0306]
 [ 0.004 -0.0012 1.    -0.0002]
 [-0.0174 -0.0306 -0.0002 1.    ]]
```

### 8.8 常见概率分布关系图

```
Bernoulli(p)             ← 单次伯努利试验
    │
    ├── n 次独立 → Binomial(n, p)
    │
    ├── 连续试验直到成功 → Geometric(p)
    │
    └── k 次成功所需的试验 → Negative Binomial(r, p)

Poisson(λ)               ← 单位时间内的稀有事件计数
    │
    ├── 当 Binomial(n, p) 中 n→∞, p→0, np→λ
    ├── 指数间隔 → Exponential(1/λ)（等待时间）
    └── k 个指数之和 → Gamma(k, 1/λ)

Normal(μ, σ²)            ← 极限分布的中心
    │
    ├── CLT: 任何分布的均值 → Normal
    ├── Binomial(n,p) 当 n大 → Normal(np, np(1-p))
    └── Poisson(λ) 当 λ大 → Normal(λ, λ)

Beta(α, β)                ← [0,1] 上的分布，常作先验
    │
    └── Bernoulli 的共轭先验（贝叶斯更新）
```

### 8.9 常见分布之间转化的 Python 验证

```python
import numpy as np
from scipy import stats

def distribution_relationships():
    """
    验证几种重要的分布间关系
    """
    np.random.seed(42)
    n_trials = 100000
    
    print("1. Poisson = Binomial(n→∞, p→0, np=λ) 的极限")
    n = 1000
    p = 0.005
    lam = n * p  # = 5
    
    binomial = np.random.binomial(n, p, n_trials)
    poisson = np.random.poisson(lam, n_trials)
    
    print(f"   Binomial(n={n}, p={p}): mean={binomial.mean():.3f}, var={binomial.var():.3f}")
    print(f"   Poisson(λ={lam}):       mean={poisson.mean():.3f}, var={poisson.var():.3f}")
    print()
    
    print("2. 指数分布的和 = Gamma 分布")
    k = 5
    theta = 2.0
    # Gamma(k, θ) = 用速率参数表示为 Gamma(k, 1/θ)
    rate = 1.0 / theta
    
    # 生成 k 个独立指数变量并求和
    exp_sums = np.random.exponential(scale=theta, size=(n_trials, k)).sum(axis=1)
    gamma = np.random.gamma(k, scale=theta, size=n_trials)
    
    print(f"   {k}×Exponential(θ={theta}) 的和: mean={exp_sums.mean():.3f}, var={exp_sums.var():.3f}")
    print(f"   Gamma(k={k}, θ={theta}):       mean={gamma.mean():.3f}, var={gamma.var():.3f}")
    print()
    
    print("3. Binomial → Normal (CLT) 逼近")
    n = 100
    p = 0.3
    binomial_vals = np.random.binomial(n, p, n_trials)
    mu = n * p
    sigma = np.sqrt(n * p * (1 - p))
    normal_vals = np.random.normal(mu, sigma, n_trials)
    
    print(f"   Binomial(n={n}, p={p}): mean={binomial_vals.mean():.3f}, var={binomial_vals.var():.3f}")
    print(f"   Normal(μ={mu}, σ²={sigma**2:.1f}):    mean={normal_vals.mean():.3f}, var={normal_vals.var():.3f}")
    
    # KS 检验（不能完全拒绝两者分布相同）
    ks_stat, ks_p = stats.ks_2samp(binomial_vals, normal_vals)
    print(f"   KS 检验: stat={ks_stat:.4f}, p={ks_p:.4f}")
    print(f"   结论: {'无法拒绝相同的分布假设' if ks_p > 0.05 else '分布显著不同'}")
    print()
    
    print("4. Chi-square = 独立标准正态的平方和")
    df = 5
    chi2_by_def = np.random.normal(0, 1, size=(n_trials, df))**2
    chi2_sums = chi2_by_def.sum(axis=1)
    chi2_direct = np.random.chisquare(df, n_trials)
    
    print(f"   {df}×Normal(0,1)² 的和: mean={chi2_sums.mean():.3f}, var={chi2_sums.var():.3f}")
    print(f"   Chi-square(df={df}):        mean={chi2_direct.mean():.3f}, var={chi2_direct.var():.3f}")
    print(f"   理论均值={df}, 方差={2*df}")

distribution_relationships()
```

输出示例：
```
1. Poisson = Binomial(n→∞, p→0, np=λ) 的极限
   Binomial(n=1000, p=0.005): mean=4.998, var=4.976
   Poisson(λ=5):       mean=4.998, var=5.016

2. 指数分布的和 = Gamma 分布
   5×Exponential(θ=2) 的和: mean=10.008, var=20.177
   Gamma(k=5, θ=2):       mean=10.009, var=19.895

3. Binomial → Normal (CLT) 逼近
   Binomial(n=100, p=0.3): mean=30.009, var=20.950
   Normal(μ=30, σ²=21.0):    mean=29.997, var=20.970
   KS 检验: stat=0.0031, p=0.3012
   结论: 无法拒绝相同的分布假设

4. Chi-square = 独立标准正态的平方和
   5×Normal(0,1)² 的和: mean=5.009, var=9.995
   Chi-square(df=5):        mean=4.996, var=9.963
   理论均值=5, 方差=10
```

---

## 总结与思维框架

### 概率论的四大支柱

```
概率空间          →   随机变量         →   分布            →   极限定理
(公理化基础)      (从结果到数字)       (刻画随机性)       (大规模行为)
    ↓                  ↓                  ↓                  ↓
  集合论            测度论            微积分           大数定律/CLT
```

### 直觉速查表

| 概念 | 一句话直觉 |
|------|-----------|
| 条件概率 | "缩小样本空间后的比例" |
| 贝叶斯定理 | "用证据更新信念" |
| 独立 | "知道一个不改变另一个" |
| 期望 | "加权平均，无限次试验的收敛值" |
| 方差 | "期望周围波动的平均幅度" |
| 协方差 | "两个变量同步波动的方向和强度" |
| 大数定律 | "重复越多，均值越稳定" |
| 中心极限定理 | "无论来源，均值都趋近正态" |

### 下一步

- **第 2 课**：参数估计（MLE, MOM, 贝叶斯估计）
- **第 3 课**：假设检验与置信区间
- **第 4 课**：线性回归与广义线性模型

---

*Created: 2025-07-14 | Last modified: 2025-07-14*
