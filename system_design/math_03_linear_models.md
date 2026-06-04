# 线性模型 — 数学/统计学深潜第3课

> ✅ 课程类型：#数学深潜 #线性模型 #GLM
> 📅 日期：2026-05-17
> 📍 位置：memory/learning/math_03_linear_models.md

---

## 1. 普通最小二乘（OLS）

### 1.1 模型形式

y = Xβ + ε, ε ~ N(0, σ²I)

- y ∈ ℝⁿ — 响应变量
- X ∈ ℝ^{n×p} — 设计矩阵（每行一个样本，每列一个特征）
- β ∈ ℝ^p — 回归系数
- ε — 误差项，独立同分布正态

**矩阵展开：**
```
[y₁]   [1 x₁₁ ... x₁ₚ] [β₀]   [ε₁]
[y₂]   [1 x₂₁ ... x₂ₚ] [β₁]   [ε₂]
[...]= [...]          [...] + [...]
[yₙ]   [1 xₙ₁ ... xₙₚ] [βₚ]   [εₙ]
```

### 1.2 损失函数与解析解

目标：最小化残差平方和

L(β) = ||y - Xβ||² = (y - Xβ)^T (y - Xβ)

展开：L(β) = y^T y - 2β^T X^T y + β^T X^T X β

对 β 求导并令为 0：
∂L/∂β = -2X^T y + 2X^T X β = 0

**正态方程：** X^T X β = X^T y

**解析解（当 X^T X 可逆时）：** β̂ = (X^T X)^{-1} X^T y

### 1.3 几何解释

ŷ = Xβ̂ = X(X^T X)^{-1} X^T y = Hy

其中 H = X(X^T X)^{-1} X^T 是**帽子矩阵**。

ŷ 是 y 在 X 列空间上的正交投影。
H 的作用："给 y 戴上帽子"——从原始观测到预测值的线性变换。

### 1.4 β̂ 的分布性质

- 无偏性：E[β̂] = β
- 协方差：Var(β̂) = σ²(X^T X)^{-1}
- 分布：β̂ ~ N(β, σ²(X^T X)^{-1})
- t 统计量：t_j = β̂_j / (σ̂√[(X^T X)^{-1}]_{jj}) ~ t_{n-p}

### 1.5 高斯-马尔可夫定理

**核心结论**：在所有的线性无偏估计中，OLS 的方差最小（BLUE）。

- 不要求正态分布！只要求 E[ε]=0, Var(ε)=σ²I
- 只要满足这两个条件，OLS 就是最优线性无偏估计

### 1.6 R² 和调整 R²

**R²（决定系数）：**
R² = 1 - SS_res / SS_tot = 1 - Σ(y_i - ŷ_i)² / Σ(y_i - ȳ)²

- 衡量模型解释了多少数据变异
- 范围 [0, 1]，越大越好
- **问题**：加多少特征 R² 都只升不降（过拟合）

**调整 R²：**
R²_adj = 1 - [SS_res/(n-p)] / [SS_tot/(n-1)] = 1 - (1-R²)(n-1)/(n-p)

- 惩罚特征数 p
- 可能为负（模型比均值还差时）

---

## 2. 回归诊断

### 2.1 关键假设

| 假设 | 含义 | 违反后果 |
|------|------|---------|
| 线性 | E[y|X] = Xβ | 模型偏差，预测系统偏误 |
| 独立 | ε_i 之间不相关 | 标准误有偏（时序中常见）|
| 同方差 | Var(ε_i) = σ² | 标准误无效，估计仍无偏 |
| 正态性 | ε_i ~ N(0, σ²) | 小样本推断失效，大样本尚可 |

### 2.2 残差分析

**标准残差：** r_i = e_i / (σ̂ √(1-h_ii))
其中 h_ii 是帽子矩阵 H 的对角元素（杠杆值）。

**常用图：**
- **残差 vs 拟合值**：应无任何模式（散点随机分布在零线附近）
- **Q-Q 图**：残差的分位数 vs 正态分布的理论分位数，应在对角线上
- **Scale-Location 图**：√|标准化残差| vs 拟合值，检查同方差

### 2.3 异方差

**检测：** Breusch-Pagan 检验
- 将残差平方对预测值回归
- 如果回归显著 → 存在异方差

**处理：**
- **异方差稳健标准误**（White/Huber 标准误）：修正推断，不改估计
- **加权最小二乘（WLS）**：给不同观测不同的权重
- **变换响应变量**：如 log(y)

### 2.4 多重共线性

当特征间高度相关时（如 x₁ 和 2x₁ + 噪声）：

**检测：** VIF（方差膨胀因子）
VIF_j = 1 / (1 - R²_j)
其中 R²_j 是第 j 个特征对其他特征回归的 R²

- VIF > 5：中度共线性
- VIF > 10：严重共线性（建议处理）

**后果：** β̂ 的方差变大，系数估计不稳定

**处理：** Ridge 回归（看第4节）、PCA、删除特征

### 2.5 异常值检测

**杠杆值：** h_ii = [H]_{ii}，衡量第 i 个点在 X 空间中的"极端程度"
- 高杠杆：该点的 x 值远离其他点

**Cook's Distance：** D_i = r²_i · h_ii / [p(1-h_ii)]
- 综合衡量第 i 个点对回归的影响
- D_i > 4/n 通常认为是高影响点

---

## 3. 广义线性模型（GLM）

### 3.1 为什么需要 GLM？

OLS 假设正态误差和线性关系，但现实中：
- 二分类问题：y ∈ {0, 1}，不能假设正态
- 计数数据：y ∈ {0, 1, 2, ...}，方差与均值相关
- 非负响应：如价格、时间

GLM 把线性模型的适用范围扩展到**指数族分布**。

### 3.2 GLM 的三部件

**1. 随机成分：** y_i 来自指数族分布
- 正态 → 连续数据
- 伯努利/二项 → 二分类
- 泊松 → 计数数据
- Gamma → 正偏态数据

**2. 系统成分：** η_i = X_i^T β（线性预测器）

**3. 连接函数：** g(μ_i) = η_i，其中 μ_i = E[y_i]
- 连接函数把响应均值映射到线性预测器
- 不同的分布用不同的连接函数

### 3.3 常见 GLM

| 数据类型 | 分布 | 典型连接 | 名称 |
|----------|------|---------|------|
| 二分类 | Bernoulli | logit(μ) = ln[μ/(1-μ)] | Logistic 回归 |
| 计数 | Poisson | ln(μ) | Poisson 回归 |
| 正连续 | Gamma | 1/μ 或 ln(μ) | Gamma 回归 |
| 多项式 | Multinomial | softmax | 多分类 |

### 3.4 Logistic 回归

**模型：**
P(y=1|X) = σ(X^T β) = 1 / (1 + e^{-Xβ})

**对数几率（log-odds）：** log[P/(1-P)] = X^T β

**损失函数（交叉熵）：**
L(β) = -Σ [y_i log(p_i) + (1-y_i) log(1-p_i)]

**IRLS求解：**
β^{t+1} = (X^T W_t X)^{-1} X^T W_t z_t

其中：
- W_t = diag(p_i^{(t)} (1 - p_i^{(t)}))
- z_t = Xβ_t + W_t^{-1} (y - p_t)

IRLS 本质上就是**加权最小二乘的迭代应用**！

### 3.5 Poisson 回归

**模型：**
log(μ_i) = X_i^T β
P(y=k) = e^{-μ} μ^k / k!

**特点：**
- 隐含假设：Var(y) = E(y)（均等散度）
- 实际数据通常过离散（方差 > 均值）→ 用负二项回归

### 3.6 偏差（Deviance）

在 GLM 中，偏差是"残差"的替代：

D = 2[ℓ(y; y) - ℓ(μ̂; y)]

- ℓ(y; y) 是饱和模型（每个点一个参数）的对数似然
- ℓ(μ̂; y) 是实际模型的对数似然
- 偏差越小，模型拟合越好

---

## 4. 正则化

### 4.1 Ridge 回归

**动机：** 当 p > n 或共线性严重时，X^T X 不可逆或非常病态。

**目标函数：**
L(β) = ||y - Xβ||² + λ||β||²

**解析解：**
β̂_ridge = (X^T X + λI)^{-1} X^T y

注意加了 λI 后，X^T X 一定可逆（正定）。

**几何解释：**
- 约束条件：||β||² ≤ t
- 相当于在半径为 t 的球内找最优 β
- λ 越大，收缩越强

**SVD 视角：**
设 X = UDV^T，则：
β̂_ols = V D^{-1} U^T y
β̂_ridge = V (D² + λI)^{-1} D U^T y

Ridge 的收缩效应：对第 j 个奇异方向，收缩因子为 d²_j / (d²_j + λ)
- 大奇异值方向（重要特征）：几乎不收缩
- 小奇异值方向（噪声）：强烈收缩

### 4.2 Lasso

**目标函数：**
L(β) = ||y - Xβ||² + λ||β||₁

**关键区别：**
- L1 范数导致**稀疏解**（很多系数精确为 0）
- Ridge 只会收缩，不会清零

**求解（坐标下降）：**
每次固定其他系数，更新一个：
β_j ← S(Σ x_ij(y_i - ŷ_i^{(-j)}), λ) / Σ x²_ij

其中 S(z, γ) = sign(z)(|z| - γ)_+ 是软阈值算子。

**λ 的选取：** 交叉验证
- λ 从小到大遍历，每个 λ 做 k 折 CV
- 选 CV 误差最小的 λ（或 1se 规则）

### 4.3 Elastic Net

**目标函数：**
L(β) = ||y - Xβ||² + λ(α||β||₁ + (1-α)/2 ||β||²)

- α=1 → Lasso
- α=0 → Ridge
- 优点：既能选特征（L1），又能稳定相关性强的特征组（L2）

### 4.4 正则化路径

当 λ 从 ∞ 到 0：
- λ→∞：所有 β_j = 0
- λ 逐渐减小：系数逐个非零
- λ→0：趋向 OLS

对于 Lasso，路径是**分段线性**的（LARS 算法利用这个性质快速计算）

---

## 5. Python 代码

```python
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# ═══════════════════════════════════════════
# 1. OLS 手动实现
# ═══════════════════════════════════════════
np.random.seed(42)
n, p = 100, 3
X = np.random.randn(n, p)
true_beta = np.array([2.0, -1.5, 0.5])
y = X @ true_beta + np.random.randn(n) * 0.5

# 手动 OLS
X_design = np.c_[np.ones(n), X]
beta_ols = np.linalg.inv(X_design.T @ X_design) @ X_design.T @ y
y_pred = X_design @ beta_ols
residuals = y - y_pred
sigma2 = np.sum(residuals**2) / (n - p - 1)
var_beta = sigma2 * np.linalg.inv(X_design.T @ X_design)

print("OLS 系数估计:")
for i, (b, se) in enumerate(zip(beta_ols, np.sqrt(np.diag(var_beta)))):
    t_stat = b / se
    p_val = 2 * stats.t.sf(abs(t_stat), n - p - 1)
    print(f"  β{i}: {b:.3f} ± {se:.3f}, t={t_stat:.2f}, p={p_val:.4f}")

# ═══════════════════════════════════════════
# 2. Ridge 正则化对比
# ═══════════════════════════════════════════
lambdas = np.logspace(-3, 3, 50)
beta_path = np.zeros((len(lambdas), p + 1))
for i, lam in enumerate(lambdas):
    beta_path[i] = np.linalg.inv(X_design.T @ X_design + lam * np.eye(p + 1)) @ X_design.T @ y

fig, axes = plt.subplots(1, 2, figsize=(12, 4))

for j in range(p + 1):
    axes[0].plot(np.log10(lambdas), beta_path[:, j], label=f'β{j}')
axes[0].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
axes[0].set_xlabel('log(λ)')
axes[0].set_ylabel('β 估计值')
axes[0].set_title('Ridge 正则化路径')
axes[0].legend()
axes[0].grid(True)

# ═══════════════════════════════════════════
# 3. Logistic 回归（IRLS）
# ═══════════════════════════════════════════
y_bin = (y > 0).astype(float)  # 二分类

def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -100, 100)))

def logistic_irls(X, y, max_iter=100, tol=1e-6):
    n, p = X.shape
    beta = np.zeros(p)
    
    for it in range(max_iter):
        eta = X @ beta
        mu = sigmoid(eta)
        W = np.diag(mu * (1 - mu))
        z = eta + (y - mu) / (mu * (1 - mu) + 1e-10)
        
        beta_new = np.linalg.inv(X.T @ W @ X) @ X.T @ W @ z
        
        if np.linalg.norm(beta_new - beta) < tol:
            break
        beta = beta_new
    
    return beta

beta_logit = logistic_irls(X_design, y_bin)
print(f"\nLogistic 回归系数: {beta_logit.round(3)}")
print(f"预测准确率: {(sigmoid(X_design @ beta_logit).round() == y_bin).mean():.3f}")

# ═══════════════════════════════════════════
# 4. Lasso （坐标下降 + 软阈值）
# ═══════════════════════════════════════════
def soft_threshold(z, gamma):
    return np.sign(z) * np.maximum(np.abs(z) - gamma, 0)

def lasso_coordinate_descent(X, y, lam, max_iter=1000, tol=1e-4):
    n, p = X.shape
    beta = np.zeros(p)
    residuals = y.copy()
    
    for it in range(max_iter):
        beta_old = beta.copy()
        for j in range(p):
            # 去掉第 j 个特征的影响
            residuals += X[:, j] * beta[j]
            # 计算单变量回归系数
            rho = X[:, j] @ residuals / n
            beta[j] = soft_threshold(rho, lam)
            # 更新残差
            residuals -= X[:, j] * beta[j]
        
        if np.linalg.norm(beta - beta_old) < tol:
            break
    
    return beta

# 标准化数据做 Lasso
X_std = (X_design[:, 1:] - X_design[:, 1:].mean(0)) / X_design[:, 1:].std(0)
y_centered = y - y.mean()
beta_lasso = lasso_coordinate_descent(X_std, y_centered, lam=0.1)
print(f"\nLasso 系数 (λ=0.1): {beta_lasso.round(4)}")

# ═══════════════════════════════════════════
# 5. sklearn 对比验证
# ═══════════════════════════════════════════
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression, Lasso

# OLS
lr = LinearRegression().fit(X, y)
print(f"\nSklearn OLS: {np.round(lr.intercept_, 3)}, {np.round(lr.coef_, 3)}")

# Ridge
ridge = Ridge(alpha=1.0).fit(X, y)
print(f"Sklearn Ridge: {np.round(ridge.intercept_, 3)}, {np.round(ridge.coef_, 3)}")

# Lasso
lasso = Lasso(alpha=0.1).fit(X_std, y_centered)
print(f"Sklearn Lasso: {np.round(lasso.coef_, 4)}")

# Logistic
logit = LogisticRegression(C=1e10, solver='lbfgs').fit(X, y_bin)
print(f"Sklearn Logistic: {np.round(logit.intercept_, 3)}, {np.round(logit.coef_, 3)}")
```

---

## 6. 技能速查卡

| 方法 | 适用场景 | 关键公式 | 特点 |
|------|---------|---------|------|
| OLS | 连续 y，线性关系 | β̂ = (X^T X)^{-1} X^T y | 解析解，BLUE |
| Ridge | 多重共线性 | β̂ = (X^T X + λI)^{-1}X^T y | 收缩，不解系数 |
| Lasso | 特征选择 | min ||y-Xβ||² + λ||β||₁ | 稀疏解，自动选特征 |
| Elastic Net | 特征选择+组效应 | 两者之和 | 综合 L1+L2 |
| Logistic | 二分类 | P=1/(1+e^{-Xβ}) | IRLS 求解 |
| Poisson | 计数数据 | log(μ)=Xβ | 均等散度假设 |

---

## 学习要点总结

1. **OLS 是线性模型的起点**，所有正则化和 GLM 都是它的推广
2. **残差诊断**比模型拟合更重要——看 R² 不如看残差图
3. **Ridge = OLS + 圆形约束**，**Lasso = OLS + 菱形约束**——几何上 L1 更易产生稀疏
4. **GLM 统一了回归框架**：线性回归、Logistic、Poisson 只是连接函数不同
5. **机器学习里没有银弹**——如果数据少，Ridge 比 Lasso 更稳定；如果特征多且稀疏，Lasso 更有效
