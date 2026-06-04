# 统计推断基础 — 数学/统计学深潜第2课

> ✅ 课程类型：#数学深潜 #统计推断
> 📅 日期：2026-05-17
> 📍 位置：memory/learning/math_stat_02_inference.md

---

## 1. 最大似然估计（MLE）

### 1.1 似然函数 vs 概率

**关键区别（必须刻进脑子里）：**
- **概率 P(D | θ)**：给定参数 θ，预测数据 D 出现的可能性。θ 固定，D 是随机变量。
- **似然 L(θ | D)**：给定观察到的数据 D，参数 θ 的"合理程度"。D 固定，θ 是未知参数。
- 两者数学形式一样：L(θ | D) = P(D | θ)，但**解读不同**
- 似然**不是概率密度**，因为对 θ 的积分不一定等于 1！

**直觉理解**：概率是把上帝视角看未来（已知参数预测数据），似然是把侦探视角看过去（从已知数据反推参数）。

### 1.2 常用分布的 MLE 推导

#### 伯努利分布 MLE

数据：x₁, x₂, ..., xₙ ∈ {0, 1}

似然函数：L(p) = ∏_{i=1}^{n} p^{x_i} (1-p)^{1-x_i}

对数似然：ℓ(p) = Σ x_i log p + (n - Σ x_i) log(1-p)

求导并令为0：∂ℓ/∂p = (Σ x_i)/p - (n - Σ x_i)/(1-p) = 0

解得：**p̂ = Σ x_i / n = x̄**

#### 正态分布 MLE

数据：x₁, ..., xₙ ∈ ℝ，服从 N(μ, σ²)

对数似然：ℓ(μ, σ²) = -n/2 log(2π) - n/2 log(σ²) - 1/(2σ²) Σ (x_i - μ)²

对 μ 求导：∂ℓ/∂μ = 1/σ² Σ (x_i - μ) = 0 ⇒ **μ̂ = x̄**

对 σ² 求导：∂ℓ/∂σ² = -n/(2σ²) + 1/(2σ⁴) Σ (x_i - μ̂)² = 0 ⇒ **σ̂² = 1/n Σ (x_i - x̄)²**

⚠️ σ̂² 是**有偏**估计，Bessel 修正为 S² = 1/(n-1) Σ (x_i - x̄)²

#### 泊松分布 MLE

数据：x₁, ..., xₙ，服从 Poisson(λ)

对数似然：ℓ(λ) = Σ (x_i log λ - λ - log x_i!) = (Σ x_i) log λ - nλ - Σ log x_i!

求导：∂ℓ/∂λ = (Σ x_i)/λ - n = 0 ⇒ **λ̂ = x̄**

### 1.3 MLE 的渐近性质（大样本性质）

在正则条件下（Cramér-Rao 条件）：

1. **一致性**：θ̂ₙ → θ₀（依概率收敛到真实值）
2. **渐近正态性**：√n(θ̂ₙ - θ₀) → N(0, I(θ₀)⁻¹)
   - I(θ) 是 Fisher 信息量：[I(θ)]_{ij} = -E[∂²log f(X;θ)/∂θ_i ∂θ_j]
   - 方差渐近地为 Cramér-Rao 下界
3. **不变性**：如果 τ = g(θ)，则 τ̂ = g(θ̂) 是 MLE（对于单射 g）
4. **渐近效率**：在大样本中，MLE 达到了最小可能方差

### 1.4 数值 MLE

当没有解析解时（如 Logistic 回归），使用数值优化：
- **牛顿-拉夫森法**：θ^{t+1} = θ^t - [H(θ^t)]⁻¹ ∇ℓ(θ^t)
- **梯度上升**：θ^{t+1} = θ^t + η ∇ℓ(θ^t)
- **BFGS/L-BFGS**：拟牛顿法，避免计算 Hessian

---

## 2. 贝叶斯推断

### 2.1 核心思维转换

| 频率派 | 贝叶斯派 |
|--------|----------|
| θ 是固定（但未知）常量 | θ 是随机变量 |
| 用点估计 + 置信区间 | 用后验分布（完整的不确定性） |
| 依靠大样本理论 | 小样本也能工作（依赖先验） |
| 概率是频率极限 | 概率是信念度 |
| f(x;θ) | f(x|θ)π(θ) |

### 2.2 贝叶斯定理

**后验 ∝ 似然 × 先验**

P(θ | D) = P(D | θ) · P(θ) / P(D)

其中 P(D) = ∫ P(D|θ)P(θ) dθ 是归一化常数（证据/边缘似然）

### 2.3 共轭先验（Conjugate Prior）

共轭先验 = 先验和后验属于同一分布族

| 似然 | 共轭先验 | 后验 |
|------|----------|------|
| Bernoulli(p) | Beta(α, β) | Beta(α+Σx, β+n-Σx) |
| Normal(μ)（σ 已知） | Normal(μ₀, σ₀²) | Normal((μ₀/σ₀² + Σx/σ²) / (1/σ₀² + n/σ²), 1/(1/σ₀² + n/σ²)) |
| Poisson(λ) | Gamma(α, β) | Gamma(α+Σx, β+n) |
| Multinomial(p) | Dirichlet(α) | Dirichlet(α + counts) |
| Exponential(λ) | Gamma(α, β) | Gamma(α+n, β+Σx) |

**Beta-Bernoulli 例子**：Beta(α=2, β=2) 先验，观测到 3 次正面、7 次反面
→ 后验 Beta(2+3, 2+7) = Beta(5, 9)
→ MAP 估计：(5-1)/(5+9-2) = 4/12 = 0.333
→ 后验均值：5/(5+9) = 0.357

### 2.4 MAP 估计

**最大后验估计**

θ̂_MAP = argmax P(θ|D) = argmax [log P(D|θ) + log P(θ)]

MAP = MLE + 先验对数项

- 共轭先验 Beta(1,1) = Uniform → MAP = MLE
- Beta(2,2) 相当于加了 2 个"伪观测"（1 个正面 + 1 个反面）
- 所以 MAP 其实相当于**带正则化的 MLE**

### 2.5 贝叶斯更新

贝叶斯推断的自然之美：

```
P(θ) → 看到数据 x₁ → P(θ | x₁) → 看到数据 x₂ → P(θ | x₁, x₂) → ...
```

每步：后验(θ | 当前所有数据) = 下一个的先验

这和人类的认知过程一模一样：**看到新证据就更新信念**

### 2.6 贝叶斯 vs 频率派的实际对比

**抛硬币问题**：10 次抛掷，8 次正面

- **频率派 MLE**：p̂ = 0.8，置信区间 ≈ [0.55, 0.94]
- **贝叶斯（Beta(1,1) 先验）**：后验 Beta(9,3)，90% HDI ≈ [0.62, 0.96]
- **贝叶斯（Beta(5,5) 先验——偏向公平）**：后验 Beta(13,7)，90% HDI ≈ [0.55, 0.85]

贝叶斯的优势：当数据少时，先验起稳定作用；数据多时先验被淹没。

---

## 3. 假设检验

### 3.1 基本框架

- H₀（零假设）：默认状态 / 无效应（如新药无效）
- H₁（备择假设）：有效应（如新药有效）
- 目标是：能否有足够证据拒绝 H₀

### 3.2 两类错误

| 决策 \ 真实状态 | H₀ 真 | H₁ 真 |
|-----------------|-------|-------|
| 不拒绝 H₀ | ✅ 正确 | ❌ Type II (β) |
| 拒绝 H₀ | ❌ Type I (α) | ✅ 正确 (power=1-β) |

- **Type I Error** = 假阳性（虚惊一场）
- **Type II Error** = 假阴性（遗漏发现）
- **显著性水平 α** = 允许的最大 Type I 错误率（通常 0.05）
- **统计功效 Power** = 当效应真实存在时能检测到的概率

### 3.3 p 值的真正含义

**错误理解**（太常见了！）：p 值是 H₀ 为真的概率 ❌

**正确含义**：**在 H₀ 为真的前提下，观测到当前（或更极端）结果的概率**

P(数据 | H₀ 真) 而不是 P(H₀ 真 | 数据)

误区源头其实是个**条件翻转**——频率派没有对 H₀/H₁ 的"概率"概念，H₀ 要么真要么假，不是随机的。

**红色预警**：p > 0.05 不意味"H₀ 一定为真"，p < 0.05 不意味"H₁ 一定为真"。

### 3.4 统计功效（Power Analysis）

功效 = 1 - β = P(拒绝 H₀ | H₁ 真)

影响功效的因素：
1. **效应大小**（effect size）：效应越大 → 功效越高
2. **样本量 n**：n 越大 → 功效越高
3. **显著性水平 α**：α 越大 → 功效越高（但 Type I 也变多）
4. **方差**：方差越小 → 功效越高

**实验设计前提**：做实验前先算需要多少样本才能达到 80% 功效

### 3.5 常见检验

#### t 检验（比较均值）

| 类型 | 公式 | 自由度 |
|------|------|--------|
| 单样本 t | t = (x̄ - μ₀) / (s/√n) | n-1 |
| 独立双样本 t | t = (x̄₁ - x̄₂) / √(s²_p/n₁ + s²_p/n₂) | n₁+n₂-2 |
| 配对 t | t = d̄ / (s_d/√n) | n-1 |

其中 s²_p = [(n₁-1)s²₁ + (n₂-1)s²₂] / (n₁+n₂-2)

#### 卡方检验（检验分类数据）

**拟合优度检验**：观测分布是否符合理论分布
χ² = Σ (观测值 - 期望值)² / 期望值
自由度 = 类别数 - 1 - 估计参数数

**独立性检验**：两个分类变量是否独立
χ² = Σ Σ (O_ij - E_ij)² / E_ij
自由度 = (r-1)(c-1)

#### F 检验（方差分析/ANOVA）

比较多个组的均值：F = MS_组间 / MS_组内

- 大 F → 组均值有显著差异
- 标准化为 F(r-1, n-r) 分布

### 3.6 多重比较问题

每做一次检验都有 α 的概率犯 Type I 错误。做 m 次检验：

**至少一次 Type I 的概率** = 1 - (1-α)^m

m=10, α=0.05 → 40% 概率至少得一次假阳性！

**修正方法：**
- **Bonferroni**：α_adj = α/m（最保守，容易错过真的效应）
- **FDR (Benjamini-Hochberg)**：控制错误发现率而非 FWER
  - 把所有 p 值排序 p₁ ≤ p₂ ≤ ... ≤ p_m
  - 找到最大的 k 使得 p_k ≤ (k/m) · q（q 是目标 FDR，如 0.1）
  - 拒绝前 k 个假设

### 3.7 A/B 测试的统计基础

A/B 测试本质上就是假设检验：
- H₀：转化率_A = 转化率_B
- H₁：转化率_A ≠ 转化率_B
- 统计量：z = (p̂_A - p̂_B) / √[p̂(1-p̂)(1/n_A + 1/n_B)]

**常见坑**：
1. **提前停止**：每隔几天看一次 p 值，看到显著就停——这是 p-hacking
2. **不设 MDE**：最小可检测效应（Minimum Detectable Effect）应在实验前设定
3. **多重端点**：测 10 个 KPI 不做多重比较修正
4. **忽略流量**：转化率 0.1% 需要 10 万+ 用户才能检测到 10% 相对提升

---

## 4. Python 代码示例

```python
import numpy as np
from scipy import stats
from scipy.optimize import minimize
import matplotlib.pyplot as plt

# ═══════════════════════════════════════════
# 1. MLE 手动实现 - 伯努利分布
# ═══════════════════════════════════════════
np.random.seed(42)
true_p = 0.3
n = 100
data = np.random.binomial(1, true_p, n)

# 解析 MLE
p_mle = data.mean()
print(f"真实 p = {true_p}, MLE 估计 p̂ = {p_mle:.3f}")

# 对数似然函数
def neg_log_likelihood(p):
    if p <= 0 or p >= 1:
        return 1e9
    return - (data.sum() * np.log(p) + (n - data.sum()) * np.log(1 - p))

# 数值 MLE
result = minimize(neg_log_likelihood, x0=[0.5], method='Nelder-Mead')
print(f"数值 MLE p̂ = {result.x[0]:.3f}")

# 不同 n 下 MLE 的收敛
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

ns = [10, 50, 100, 500, 1000, 5000]
estimates = []
for ni in ns:
    data_i = np.random.binomial(1, true_p, ni)
    estimates.append(data_i.mean())

axes[0].plot(ns, estimates, 'o-', label='MLE')
axes[0].axhline(y=true_p, color='r', linestyle='--', label=f'true p={true_p}')
axes[0].set_xscale('log')
axes[0].set_xlabel('样本量 n')
axes[0].set_ylabel('p̂')
axes[0].set_title('MLE 收敛到真实值')
axes[0].legend()
axes[0].grid(True)

# ═══════════════════════════════════════════
# 2. MLE for 正态分布
# ═══════════════════════════════════════════
true_mean, true_std = 5.0, 2.0
n_norm = 1000
data_norm = np.random.normal(true_mean, true_std, n_norm)

mu_mle = data_norm.mean()
sigma_mle = np.sqrt(((data_norm - mu_mle)**2).mean())
sigma_unbiased = np.sqrt(((data_norm - mu_mle)**2).sum() / (n_norm - 1))

print(f"\n正态 MLE: μ̂={mu_mle:.3f} (真值={true_mean}), σ̂²={sigma_mle:.3f} (有偏)")
print(f"无偏 σ̂² = {sigma_unbiased:.3f}")

# ═══════════════════════════════════════════
# 3. 贝叶斯 Beta-Bernoulli 更新
# ═══════════════════════════════════════════
from scipy.stats import beta

# 实验：抛硬币
true_p_bayes = 0.4
n_trials = [0, 5, 10, 20, 50, 100]

fig2, axes2 = plt.subplots(1, len(n_trials), figsize=(15, 3))

alpha_prior, beta_prior = 2, 2  # 弱偏向公平
xs = np.linspace(0, 1, 200)

for i, n_t in enumerate(n_trials):
    if n_t == 0:
        # 纯先验
        y = beta.pdf(xs, alpha_prior, beta_prior)
        label = f'Prior Beta({alpha_prior},{beta_prior})'
    else:
        # 生成数据
        data_b = np.random.binomial(1, true_p_bayes, n_t)
        heads = data_b.sum()
        tails = n_t - heads
        alpha_post = alpha_prior + heads
        beta_post = beta_prior + tails
        y = beta.pdf(xs, alpha_post, beta_post)
        label = f'Posterior Beta({alpha_post},{beta_post})'

    axes2[i].plot(xs, y, 'b-')
    axes2[i].axvline(x=true_p_bayes, color='r', linestyle='--', alpha=0.5)
    axes2[i].set_title(f'n={n_t}')
    axes2[i].set_xlim(0, 1)
    axes2[i].set_ylim(0, None)

plt.tight_layout()
plt.show()

# ═══════════════════════════════════════════
# 4. 假设检验示例
# ═══════════════════════════════════════════

# 4a. 单样本 t 检验
print("\n=== 单样本 t 检验 ===")
group_a = np.random.normal(102, 15, 50)  # 均值 102
t_stat, p_val = stats.ttest_1samp(group_a, 100)  # H₀: μ=100
print(f"t = {t_stat:.3f}, p = {p_val:.4f}")
print(f"结论: {'拒绝 H₀' if p_val < 0.05 else '不能拒绝 H₀'}")

# 4b. 双样本 t 检验
print("\n=== 独立双样本 t 检验 ===")
group_b = np.random.normal(110, 15, 50)  # 均值 110
t_stat2, p_val2 = stats.ttest_ind(group_a, group_b)
print(f"t = {t_stat2:.3f}, p = {p_val2:.4f}")
print(f"结论: {'拒绝 H₀（有显著差异）' if p_val2 < 0.05 else '不能拒绝 H₀（无显著差异）'}")

# 4c. 卡方检验
print("\n=== 卡方检验（独立性）===")
observed = np.array([[30, 10], [20, 40]])  # 2×2 列联表
chi2, p_chi, dof, expected = stats.chi2_contingency(observed)
print(f"χ² = {chi2:.3f}, p = {p_chi:.4f}, df = {dof}")
print(f"期望频数:\n{expected}")

# 4d. 功效分析
print("\n=== 功效分析 ===")
from scipy.stats import nct, ncf
effect_size = 0.5  # Cohen's d
alpha = 0.05
n_sample = 64  # 每组 32 个，共 64
dof_test = n_sample - 2
t_crit = stats.t.ppf(1 - alpha/2, dof_test)
ncp = effect_size * np.sqrt(n_sample/4)  # 非中心参数
power = 1 - stats.nct.cdf(t_crit, dof_test, ncp) + stats.nct.cdf(-t_crit, dof_test, ncp)
print(f"effect_size={effect_size}, n={n_sample}: power = {power:.3f}")
```

---

## 5. 核心公式速查卡

| 概念 | 公式 |
|------|------|
| 贝叶斯定理 | P(θ|D) ∝ P(D|θ) · P(θ) |
| MLE | θ̂ = argmax Σ log f(x_i; θ) |
| Fisher 信息量 | I(θ) = -E[∂²ℓ/∂θ²] |
| CLT 版本 | √n(θ̂ - θ) → N(0, 1/I(θ)) |
| 贝叶斯更新 | P(θ|D) = P(D|θ)P(θ) / ∫P(D|θ)P(θ)dθ |
| 单样本 t | t = (x̄ - μ₀) / (s/√n) |
| 两样本 t | t = (x̄₁ - x̄₂) / √(s²_p(1/n₁ + 1/n₂)) |
| 功效（双样本 t） | 1 - T(t_crit | δ) + T(-t_crit | δ) |

---

## 学习要点总结

1. **MLE = 给数据最好的解释**：找最让数据"看起来合理"的参数
2. **贝叶斯 = MLE + 先验知识**：数据不足时靠先验撑住
3. **MAP = MLE + L2 正则化**：当先验是正态时，等价于 Ridge 回归
4. **p 值不是 H₀ 的概率**——最常被误解的统计概念，没有之一
5. **多重比较必修正**：做 100 次检验期待发现 5 个"显著"结果（α=0.05），那很可能全是假阳性
6. **功效分析是实验设计前提**：不是事后补的
