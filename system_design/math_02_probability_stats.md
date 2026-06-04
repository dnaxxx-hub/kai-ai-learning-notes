# 第2课：概率论与统计深潜 — 贝叶斯推断与量化实战

> 前置：已掌握MLE/MAP基础，本课聚焦深层对比、因果推断和回测统计

## 1. 贝叶斯 vs 频率学派：深层对比

### 1.1 哲学分歧

| 维度 | 频率学派 | 贝叶斯学派 |
|---|---|---|
| 概率定义 | 事件在无限次重复试验中的频率 | 对不确定性的信念度量 |
| 参数 | 固定的未知常数 | 随机变量，有分布 |
| 推断 | 基于似然的点估计+置信区间 | 后验分布 |
| 先验 | 不需要 | 必需（可以是无信息先验） |
| 对"已知信息"的处理 | 难以融入 | 通过先验自然融入 |

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

def frequentist_vs_bayesian():
    """贝叶斯 vs 频率学派：硬币投掷对比"""
    np.random.seed(42)
    true_p = 0.3
    n_trials = [5, 20, 100, 1000]
    
    print("=== 频率学派 vs 贝叶斯：估计硬币正面概率 p ===")
    print(f"真实概率 p = {true_p}")
    
    for n in n_trials:
        # 模拟数据
        heads = np.random.binomial(n, true_p)
        
        # 频率学派：MLE
        p_mle = heads / n
        # Wald置信区间（正态近似）
        se = np.sqrt(p_mle * (1 - p_mle) / n)
        ci_freq = (p_mle - 1.96 * se, p_mle + 1.96 * se)
        
        # 贝叶斯：Beta-Bernoulli共轭
        # 先验 Beta(2, 2) — 轻微偏向0.5
        alpha_prior, beta_prior = 2, 2
        alpha_post = alpha_prior + heads
        beta_post = beta_prior + n - heads
        
        # 后验均值 + 可信区间
        p_bayes = alpha_post / (alpha_post + beta_post)
        ci_bayes = stats.beta.interval(0.95, alpha_post, beta_post)
        
        print(f"\nn={n:4d}, 正面={heads:3d}:")
        print(f"  MLE: p̂={p_mle:.3f}, 95%CI=({ci_freq[0]:.3f}, {ci_freq[1]:.3f})")
        print(f"  Bayes: E[p|D]={p_bayes:.3f}, 95%可信区间=({ci_bayes[0]:.3f}, {ci_bayes[1]:.3f})")
        
        if n < 20:
            print(f"  → 小样本下贝叶斯更稳定（先验提供正则化）")
        elif n >= 100:
            print(f"  → 大样本下两者趋于一致")

frequentist_vs_bayesian()
```

### 1.2 关键差异：置信区间 vs 可信区间

```python
def credible_vs_confidence():
    """置信区间 vs 可信区间：本质区别演示"""
    np.random.seed(42)
    
    # 频率学派视角
    print("=== 95%置信区间的频率学派解释 ===")
    print("如果重复实验100次，约95个区间包含真值")
    
    true_mu = 0
    coverage_count = 0
    n_experiments = 1000
    
    for i in range(n_experiments):
        data = np.random.randn(30) + true_mu
        mu_hat = data.mean()
        se = data.std() / np.sqrt(30)
        ci = (mu_hat - 1.96*se, mu_hat + 1.96*se)
        if ci[0] <= true_mu <= ci[1]:
            coverage_count += 1
    
    print(f"覆盖率: {coverage_count/n_experiments:.1%} (应≈95%)")
    
    # 贝叶斯视角
    print("\n=== 95%后验可信区间的贝叶斯解释 ===")
    print("给定观测数据，参数有95%概率落在此区间内")
    
    # 单次实验
    data = np.random.randn(30) + true_mu
    # 假设无信息先验（均匀），后验 = N(mean, 1/n)
    post_mean = data.mean()
    post_std = 1 / np.sqrt(30)
    
    hdi_low = stats.norm.ppf(0.025, post_mean, post_std)
    hdi_high = stats.norm.ppf(0.975, post_mean, post_std)
    
    print(f"后验均值={post_mean:.3f}, 后验标准差={post_std:.3f}")
    print(f"95% HDI: ({hdi_low:.3f}, {hdi_high:.3f})")
    print(f"P(真值在区间内|数据) = 0.95（这是贝叶斯的直接表述）")
    
    # 频率学派不能这样说！
    print("\n⚠️ 区分：频率学派不能说'参数有95%概率在CI内'")
    print("         只能说'长期来看95%的CI包含真值'")

credible_vs_confidence()
```

## 2. MLE vs MAP：推导对比

### 2.1 数学框架

**MLE**：最大化似然 $P(D|\theta)$
$$\theta_{MLE} = \arg\max_\theta \prod_i P(x_i|\theta)$$

**MAP**：最大化后验 $P(\theta|D) \propto P(D|\theta)P(\theta)$
$$\theta_{MAP} = \arg\max_\theta \left(\sum_i \log P(x_i|\theta) + \log P(\theta)\right)$$

```python
def mle_vs_map_comparison():
    """
    MLE vs MAP 对比
    
    MLE = 无先验的MAP
    MAP = MLE + 先验的正则化
    Ridge回归 = MAP with Gaussian prior on weights
    Lasso回归 = MAP with Laplace prior on weights
    """
    np.random.seed(42)
    
    # 生成数据：少量样本 + 已知先验
    true_mu = 0.5
    n = 10
    data = np.random.randn(n) + true_mu
    
    # MLE: 样本均值
    mu_mle = data.mean()
    
    # MAP: 后验众数（Gaussian prior ~ N(0, 1)）
    # 后验 ~ N( (τ²/σ²)·x̄ + (σ²/τ²)·0 , 1/(1/σ² + 1/τ²) ) 
    # 其中 σ² = 数据方差 ≈ 1, τ² = 先验方差 = 1
    
    # 简化：已知σ²=1, 先验τ²=1
    sigma2_known = 1.0
    tau2_prior = 1.0
    
    # MAP = (n/σ²) * x̄ / (n/σ² + 1/τ²)
    weight_data = n / sigma2_known
    weight_prior = 1 / tau2_prior
    mu_map = (weight_data * mu_mle + weight_prior * 0) / (weight_data + weight_prior)
    
    print("MLE vs MAP 对比")
    print(f"真实均值: {true_mu}")
    print(f"MLE估计: {mu_mle:.4f} (无正则化，小样本下容易过拟合)")
    print(f"MAP估计: {mu_map:.4f} (向先验均值0收缩)")
    print(f"MSE(MLE) = {(mu_mle-true_mu)**2:.6f}")
    print(f"MSE(MAP) = {(mu_map-true_mu)**2:.6f}")
    
    # 不同样本量下的表现
    print("\n不同样本量下的收缩程度:")
    for n_small in [3, 10, 30, 100]:
        weight_d = n_small / sigma2_known
        weight_p = 1 / tau2_prior
        shrinkage = weight_p / (weight_d + weight_p)
        print(f"  n={n_small:3d}: 收缩因子={shrinkage:.3f} (越大越依赖先验)")

mle_vs_map_comparison()
```

### 2.2 MAP = 带正则化的MLE

```python
def map_as_regularized_mle():
    """MAP作为带正则化的MLE：Ridge/Lasso的贝叶斯解释"""
    
    print("=== MAP = MLE + 正则化（贝叶斯视角） ===")
    print()
    print("先验分布 → 正则化项 → 对应的回归模型")
    print("-" * 60)
    print("Gaussian先验   → L2正则化 → Ridge回归")
    print("Laplace先验    → L1正则化 → Lasso回归")
    print("Cauchy先验     → 非凸正则化 → 鲁棒回归")
    print("Horseshoe先验  → 稀疏收缩 → 贝叶斯压缩估计")
    print()
    
    # 演示：Ridge = MAP with Gaussian prior
    np.random.seed(42)
    n, p = 50, 10
    X = np.random.randn(n, p)
    beta_true = np.array([3, 0, 0, 0, -2, 0, 0, 0, 0, 0])  # 稀疏
    y = X @ beta_true + np.random.randn(n) * 0.5
    
    # OLS (MLE)
    beta_ols = np.linalg.lstsq(X, y, rcond=None)[0]
    
    # Ridge (MAP with Gaussian prior, σ²=1, λ=1)
    lambda_reg = 1.0
    beta_ridge = np.linalg.inv(X.T @ X + lambda_reg * np.eye(p)) @ X.T @ y
    
    print("MLE (OLS) vs MAP (Ridge) 对比:")
    print(f"{'参数':>8} {'真值':>8} {'OLS':>8} {'Ridge':>8}")
    print("-" * 34)
    for i in range(p):
        print(f"{f'β{i}':>8} {beta_true[i]:>8.1f} {beta_ols[i]:>8.3f} {beta_ridge[i]:>8.3f}")
    
    print(f"\nMSE(OLS)   = {np.mean((beta_ols - beta_true)**2):.4f}")
    print(f"MSE(Ridge) = {np.mean((beta_ridge - beta_true)**2):.4f}")
    print(f"\n结论: 对稀疏真实参数，MAP(Ridge)通过收缩降低了MSE")

map_as_regularized_mle()
```

## 3. 指数族分布与共轭先验

### 3.1 指数族分布

$$p(x|\theta) = h(x) \exp\left(\eta(\theta)^T T(x) - A(\eta)\right)$$

包含：Gaussian, Bernoulli, Poisson, Gamma, Dirichlet, Categorical...

```python
def exponential_family():
    """指数族分布的通用形式"""
    
    print("=== 指数族分布的三个核心组件 ===")
    print("\n通用形式: p(x|θ) = h(x)·exp(η(θ)·T(x) - A(η))")
    print()
    print(f"{'分布':<12} {'η(θ)':<15} {'T(x)':<12} {'A(η)':<20} {'h(x)':<10}")
    print("-" * 70)
    
    examples = [
        ("Bernoulli", "log(p/(1-p))", "x", "-log(1-p)", "1"),
        ("Poisson", "log(λ)", "x", "exp(η)", "1/x!"),
        ("Gaussian", "μ/σ²", "x", "η²σ²/2", "1/√(2π)exp(-x²/(2σ²))"),
        ("Exp", "-λ", "x", "-log(-η)", "1"),
    ]
    
    for name, eta, Tx, A, hx in examples:
        print(f"{name:<12} {eta:<15} {Tx:<12} {A:<20} {hx:<10}")
    
    print("\n指数族的重要性：")
    print("1. 共轭先验存在且形式优美")
    print("2. MLE有闭式解（矩匹配）")
    print("3. 变分推断的天然框架")
    print("4. GLM（广义线性模型）的基础")

exponential_family()
```

### 3.2 共轭先验实战

```python
def conjugate_prior_demo():
    """
    共轭先验：先验+似然→后验同族
    
    常用共轭组合：
    似然      | 先验          | 后验
    Bernoulli | Beta          | Beta
    Gaussian  | Gaussian      | Gaussian
    Poisson   | Gamma         | Gamma
    Categorical | Dirichlet   | Dirichlet
    """
    
    print("=== 共轭先验实战：多重贝塔-伯努利 ===")
    np.random.seed(42)
    
    # 模拟10个网站版本的CTR
    true_ctrs = np.array([0.05, 0.06, 0.04, 0.07, 0.05,
                          0.15, 0.05, 0.05, 0.06, 0.05])
    n_visits_per = 100
    
    # 先验：Beta(1, 19) — 认为CTR约5%
    alpha0, beta0 = 1, 19
    
    print(f"{'版本':>4} {'真实CTR':>8} {'观测点击':>8} {'MLE':>8} {'MAP':>8} {'后验α':>6} {'后验β':>6}")
    print("-" * 54)
    
    for i, true_p in enumerate(true_ctrs):
        clicks = np.random.binomial(n_visits_per, true_p)
        mle = clicks / n_visits_per
        # 后验
        alpha_n = alpha0 + clicks
        beta_n = beta0 + n_visits_per - clicks
        map_est = (alpha_n - 1) / (alpha_n + beta_n - 2)  # 后验众数
        
        print(f"  {i:2d}   {true_p:.3f}      {clicks:3d}      {mle:.3f}  {map_est:.3f}   {alpha_n:3d}   {beta_n:3d}")

conjugate_prior_demo()
```

## 4. 假设检验：p值陷阱与多重比较校正

### 4.1 p值的正确理解和常见误解

```python
def p_value_trap_demo():
    """p值陷阱：为什么p值不能告诉你想要什么"""
    np.random.seed(42)
    
    print("=== p值陷阱演示 ===")
    print("\n情景：检验某个交易策略的 mean return = 0")
    print()
    
    # 生成真实没有效应（μ=0）的数据
    n_days = 60
    true_mu = 0
    n_simulations = 10000
    
    sig_results = []
    for sim in range(n_simulations):
        returns = np.random.randn(n_days) * 0.02  # 日收益率，年化波动约30%
        t_stat = returns.mean() / (returns.std() / np.sqrt(n_days))
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=n_days-1))
        sig_results.append(p_value < 0.05)
    
    false_positive_rate = np.mean(sig_results)
    print(f"真实μ=0（策略无效），显著性水平α=0.05")
    print(f"模拟{n_simulations}次，发现\"显著\"结果: {false_positive_rate:.1%}")
    print(f"（应约等于5%，这是Type I Error的准确定义）")
    
    print("\n⚠️ 常见p值误解：")
    print("  ❌ p=0.03 意味着策略有97%概率有效")
    print("  ✓  p=0.03 意味着如果策略无效，只有3%概率观测到如此极端的数据")
    print("  关键区别：前者是P(假设|数据)，后者是P(数据|假设)")
    
    # 多重比较效应
    print("\n=== 多重比较校正 ===")
    n_strategies = 100
    
    # 100个随机策略的回测
    sig_count = 0
    for i in range(n_strategies):
        returns = np.random.randn(60) * 0.02
        t_stat = returns.mean() / (returns.std() / np.sqrt(60))
        p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=59))
        if p_val < 0.05:
            sig_count += 1
    
    print(f"回测{n_strategies}个随机策略（全部无效）：")
    print(f"  发现显著(p<0.05): {sig_count}个 (预期{int(n_strategies*0.05)}个)")
    print(f"  → 这就是p-hacking / data snooping的问题")

p_value_trap_demo()
```

### 4.2 多重比较校正方法

```python
def multiple_testing_correction():
    """多重比较校正：Bonferroni / FDR / Holm"""
    np.random.seed(42)
    
    n_tests = 100
    true_effects = np.array([True]*10 + [False]*90)  # 只有10个真有效
    
    # 生成p值
    p_values = np.ones(n_tests)
    p_values[true_effects] = 10**np.random.uniform(-4, -1, 10)  # 有效的小p
    p_values[~true_effects] = np.random.uniform(0.01, 0.99, 90)  # 无效的均匀p
    
    # 方法1: Bonferroni（最保守）
    alpha = 0.05
    bonf_threshold = alpha / n_tests
    bonf_reject = p_values < bonf_threshold
    
    # 方法2: Benjamini-Hochberg (FDR控制)
    def benjamini_hochberg(p_vals, q=0.05):
        n = len(p_vals)
        sorted_idx = np.argsort(p_vals)
        sorted_p = p_vals[sorted_idx]
        
        # BH临界值
        threshold = np.arange(1, n+1) * q / n
        reject = sorted_p < threshold
        
        # 找到最大的k使得p_k ≤ q*k/n
        if np.any(reject):
            max_k = np.max(np.where(reject)[0])
            threshold_actual = threshold[max_k]
        else:
            max_k = -1
            threshold_actual = 0
        
        reject_final = p_vals < threshold_actual
        return reject_final
    
    bh_reject = benjamini_hochberg(p_values)
    
    print("多重比较校正对比（100个假设，10个真有效）:")
    print(f"{'方法':<20} {'发现数':>6} {'真阳性':>6} {'假阳性':>6} {'FDR':>8}")
    print("-" * 48)
    
    for name, reject in [("无校正(p<0.05)", p_values < 0.05),
                          ("Bonferroni", bonf_reject),
                          ("BH-FDR", bh_reject)]:
        tp = np.sum(reject & true_effects)
        fp = np.sum(reject & ~true_effects)
        fdr = fp / max(np.sum(reject), 1)
        print(f"{name:<20} {np.sum(reject):>6} {tp:>6} {fp:>6} {fdr:>8.1%}")

multiple_testing_correction()
```

## 5. 因果推断基础

### 5.1 相关 ≠ 因果 + do-calculus概念

```python
def causal_inference_basics():
    """因果推断基础：混淆变量与do-calculus"""
    np.random.seed(42)
    n = 1000
    
    print("=== 因果推断：相关 ≠ 因果 ===")
    print()
    
    # 场景：冰淇淋销量 vs 溺水人数
    # 混淆变量 Z = 温度
    Z = np.random.randn(n) * 10 + 30  # 温度
    X = 0.5 * Z + np.random.randn(n) * 2  # 冰淇淋销量
    Y = 0.3 * Z + np.random.randn(n) * 2  # 溺水人数
    
    # 观察性关联：X和Y正相关（但无因果）
    corr_observed = np.corrcoef(X, Y)[0, 1]
    print(f"场景1: 冰淇淋销量(X) vs 溺水人数(Y)")
    print(f"  观察性相关系数: {corr_observed:.3f} (高度正相关)")
    print(f"  但X和Y无直接因果关系!")
    print(f"  混淆变量 Z=温度 同时影响 X 和 Y")
    
    # 控制混淆变量后
    # 对Z做线性回归的残差
    def residualize(x, z):
        beta = np.linalg.lstsq(np.column_stack([z, np.ones(n)]), x, rcond=None)[0]
        return x - (z * beta[0] + beta[1])
    
    X_resid = residualize(X, Z)
    Y_resid = residualize(Y, Z)
    corr_adjusted = np.corrcoef(X_resid, Y_resid)[0, 1]
    
    print(f"  控制Z后的偏相关: {corr_adjusted:.3f} (因果效应≈0)")
    
    # 场景2: 药物效果（因果）
    print(f"\n场景2: 药物(X) vs 康复(Y)")
    # 随机对照实验 (do(X)操作)
    X_random = np.random.binomial(1, 0.5, n)  # 随机分配药物
    Y_effect = 0.3 * X_random + np.random.randn(n) * 0.5  # 治疗效果
    corr_causal = np.corrcoef(X_random, Y_effect)[0, 1]
    
    print(f"  随机实验相关系数: {corr_causal:.3f}")
    print(f"  (这≈因果效应，因为随机化消除了混淆)")

causal_inference_basics()
```

### 5.2 do-calculus核心概念

```python
def do_calculus_concepts():
    """do-calculus的三个基本规则"""
    
    print("=== do-calculus 基本概念 ===")
    print()
    print("P(Y|do(X)) vs P(Y|X) 的区别：")
    print("  P(Y|X=x)   = 在观察到X=x的条件下Y的分布")
    print("  P(Y|do(X=x)) = 在强制X=x的条件下Y的分布")
    print()
    print("例子：")
    print("  P(血压高|吃药)   vs P(血压高|do(吃药))")
    print("  前者有混杂（生病才吃药）")
    print("  后者才是因果效应的度量")
    
    print("\ndo-calculus三条规则：")
    print("  规则1: 若Y⟂Z|X,W，可忽略干预")
    print("  规则2: 若Y⟂do(Z)|X,W，可用P(Y|X,W)替代")
    print("  规则3: 若Y⟂Z|do(X),W，可删除条件")
    print()
    print("实践意义：并非所有因果问题都需随机实验")
    print("          通过DAG和后门准则，可以从观测数据")
    print("          推断因果效应（如果DAG正确）")

do_calculus_concepts()
```

## 6. 量化实战

### 6.1 回测的统计显著性

```python
def backtest_statistical_significance():
    """
    回测统计显著性检验
    
    关键问题：回测中发现的超额收益，是真实的还是过拟合？
    """
    np.random.seed(42)
    
    print("=== 回测统计显著性与过拟合适配 ===")
    
    # 模拟一个"看起来很好"的策略
    n_days = 1000
    n_strategies = 100
    
    # 生成随机策略的夏普比
    def random_strategy_sharpe(n_days):
        returns = np.random.randn(n_days) * 0.01
        sharpe = np.sqrt(252) * returns.mean() / returns.std()
        return sharpe
    
    # 生成100个随机策略的夏普比
    sharpes = [random_strategy_sharpe(n_days) for _ in range(n_strategies)]
    max_sharpe = max(sharpes)
    
    print(f"生成{n_strategies}个随机策略（全部无效）：")
    print(f"  最大夏普比: {max_sharpe:.2f}")
    
    # 正确的多重比较校正
    # 用极值理论：M个独立策略的最大夏普比的分布
    def expected_max_sharpe(n_strategies, n_days):
        """在零假设下的期望最大夏普比"""
        E_S_approx = np.sqrt(2 * np.log(n_strategies)) / np.sqrt(n_days/252)
        return E_S_approx
    
    expected_max = expected_max_sharpe(n_strategies, n_days)
    print(f"  零假设下期望最大夏普比: {expected_max:.2f}")
    print(f"  → 观测到的最大夏普比 {max_sharpe:.2f} 在随机波动范围内")
    
    # 更严格的方法：调整后p值
    # 如果用Bonferroni：每个策略的α = 0.05 / 100 = 0.0005
    # 对应的夏普比阈值
    from scipy import stats
    bonf_threshold = stats.t.ppf(1 - 0.05/(2*100), n_days-1) / np.sqrt(n_days/252)
    print(f"  Bonferroni校正后的夏普比阈值: {bonf_threshold:.2f}")

backtest_statistical_significance()
```

### 6.2 蒙特卡洛模拟风险

```python
def monte_carlo_risk():
    """
    蒙特卡洛模拟：策略风险评估
    
    用途：
    - VaR（风险价值）
    - CVaR（条件风险价值）
    - 最大回撤分布
    - 路径依赖策略的压力测试
    """
    np.random.seed(42)
    
    n_simulations = 10000
    n_days = 252  # 一年交易日
    annual_return = 0.12
    annual_vol = 0.20
    mu = annual_return / 252
    sigma = annual_vol / np.sqrt(252)
    initial_capital = 1000000
    
    # 蒙特卡洛模拟
    final_values = []
    max_drawdowns = []
    
    for sim in range(n_simulations):
        # 几何布朗运动
        log_returns = np.random.normal(mu - sigma**2/2, sigma, n_days)
        price_path = initial_capital * np.exp(np.cumsum(log_returns))
        
        final_values.append(price_path[-1])
        
        # 最大回撤
        peak = np.maximum.accumulate(price_path)
        drawdown = (price_path - peak) / peak
        max_drawdowns.append(np.min(drawdown))
    
    final_values = np.array(final_values)
    max_drawdowns = np.array(max_drawdowns)
    
    # 风险指标
    print("=== 蒙特卡洛风险分析 ===")
    print(f"模拟次数: {n_simulations}")
    print(f"初始资金: ¥{initial_capital:,.0f}")
    print(f"年化收益率: {annual_return:.0%}")
    print(f"年化波动率: {annual_vol:.0%}")
    print()
    
    # VaR 和 CVaR
    var_95 = np.percentile(final_values, 5)
    cvar_95 = final_values[final_values <= var_95].mean()
    
    print(f"风险指标 (95%置信度):")
    print(f"  95% VaR = ¥{initial_capital - var_95:,.0f} (最差5%情景下的最小损失)")
    print(f"  95% CVaR = ¥{initial_capital - cvar_95:,.0f} (尾部损失的均值)")
    
    # 最大回撤分析
    print(f"\n最大回撤:")
    print(f"  平均最大回撤: {max_drawdowns.mean():.1%}")
    print(f"  95%最大回撤: {np.percentile(max_drawdowns, 5):.1%}")
    print(f"  最坏情景最大回撤: {max_drawdowns.min():.1%}")
    
    # 夏普比分布
    sharpes = (final_values / initial_capital - 1) / (annual_vol)
    print(f"\n夏普比:")
    print(f"  平均: {sharpes.mean():.2f}")
    print(f"  95% CI: ({np.percentile(sharpes, 2.5):.2f}, {np.percentile(sharpes, 97.5):.2f})")

monte_carlo_risk()
```

### 6.3 贝叶斯策略评估

```python
def bayesian_strategy_evaluation():
    """贝叶斯方法评估策略表现"""
    np.random.seed(42)
    
    n_days = 60
    # 假设策略日收益率
    strategy_returns = np.random.randn(n_days) * 0.015 + 0.002
    
    # 贝叶斯推断：策略的真实日收益率
    # 先验：N(0, 0.01) — 保守认为策略无效
    mu_prior = 0
    sigma_prior = 0.01
    sigma_likelihood = np.std(strategy_returns)
    
    # 后验均值
    n = len(strategy_returns)
    precision_prior = 1 / sigma_prior**2
    precision_data = n / sigma_likelihood**2
    mu_posterior = (precision_data * strategy_returns.mean() + 
                    precision_prior * mu_prior) / (precision_data + precision_prior)
    sigma_posterior = np.sqrt(1 / (precision_data + precision_prior))
    
    # 后验概率P(μ > 0|数据)
    p_positive = 1 - stats.norm.cdf(0, mu_posterior, sigma_posterior)
    
    print("=== 贝叶斯策略评估 ===")
    print(f"观测{n_days}个交易日")
    print(f"样本均值: {strategy_returns.mean():.4f}")
    print(f"年化夏普: {np.sqrt(252) * strategy_returns.mean() / strategy_returns.std():.2f}")
    print()
    print(f"贝叶斯后验:")
    print(f"  后验均值: {mu_posterior:.4f}")
    print(f"  后验标准差: {sigma_posterior:.4f}")
    print(f"  P(策略有效|数据) = {p_positive:.1%}")
    print(f"  95% 可信区间: ({stats.norm.ppf(0.025, mu_posterior, sigma_posterior):.4f}, "
          f"{stats.norm.ppf(0.975, mu_posterior, sigma_posterior):.4f})")
    
    if p_positive < 0.95:
        print("\n⚠️ 即使样本均值>0，后验概率显示策略可能无效")
        print("   小样本下先验信息应得到重视")

bayesian_strategy_evaluation()
```

## 7. ML/DL关联总结

| 概率/统计概念 | ML/DL应用 | 量化应用 |
|---|---|---|
| MLE | 交叉熵损失、线性回归 | 因子模型参数估计 |
| MAP | Ridge/Lasso（正则化）、Dropout变分解释 | 协方差矩阵收缩估计 |
| 共轭先验 | 贝叶斯神经网络、主题模型 | 动态因子模型在线更新 |
| 指数族分布 | GLM、变分自编码器的均场近似 | 收益率分布建模 |
| p值校正 | 特征选择时的多重假设 | 多重策略回测过拟合控制 |
| 贝叶斯推断 | 不确定性度量、主动学习 | 策略后验评估、组合优化 |
| 蒙特卡洛 | MC Dropout、REINFORCE算法 | VaR/CVaR计算、压力测试 |
| do-calculus | 因果表示学习、反事实推理 | 策略归因（哪个因子真正贡献收益） |
