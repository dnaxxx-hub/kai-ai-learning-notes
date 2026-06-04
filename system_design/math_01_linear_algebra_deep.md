# 第1课：线性代数深潜 — 矩阵分解与量化实战

> 前置：羽已学过ML/DL全套，本课聚焦矩阵分解的几何直觉、numpy实现和量化实战

## 1. 特征值与特征向量：几何意义

### 1.1 核心直觉

矩阵 $A$ 乘以向量 $x$ 是一个**线性变换**（拉伸、旋转、剪切）。特征向量是那些在变换后**方向不变**（只被拉伸）的向量：

$$A v = \lambda v$$

- $\lambda$：拉伸因子（特征值）
- $v$：不变方向的特殊向量

```python
import numpy as np
import matplotlib.pyplot as plt

def plot_eigen_geometry():
    """可视化特征向量的几何意义：矩阵A对向量的作用"""
    A = np.array([[2, 1], [1, 2]])
    eigvals, eigvecs = np.linalg.eig(A)
    
    # 生成单位圆上的向量
    angles = np.linspace(0, 2*np.pi, 100)
    unit_vectors = np.column_stack([np.cos(angles), np.sin(angles)])
    
    # A 变换后的结果
    transformed = unit_vectors @ A.T
    
    print("矩阵 A:\n", A)
    print("\n特征值:", eigvals)
    print("特征向量:\n", eigvecs)
    print("\n几何意义:")
    print(f"  v1方向被拉伸 {eigvals[0]:.2f} 倍")
    print(f"  v2方向被拉伸 {eigvals[1]:.2f} 倍")
    print(f"  条件数 = {max(eigvals)/min(eigvals):.2f} (矩阵病态程度)")
    
    # 验证 Av = λv
    for i in range(2):
        v = eigvecs[:, i]
        lhs = A @ v
        rhs = eigvals[i] * v
        print(f"  A·v{i+1} = λ·v{i+1}: {np.allclose(lhs, rhs)}")

plot_eigen_geometry()
```

### 1.2 谱定理（Spectral Theorem）

**实对称矩阵** $A = A^T$ 可被正交对角化：

$$A = Q \Lambda Q^T = \sum_{i=1}^n \lambda_i q_i q_i^T$$

协方差矩阵就是实对称矩阵 → 天然可谱分解 → PCA的数学基础。

```python
def spectral_decomposition_example():
    """谱分解：协方差矩阵的谱表示"""
    # 生成二维数据
    np.random.seed(42)
    X = np.random.multivariate_normal(
        mean=[0, 0], 
        cov=[[3, 1.8], [1.8, 1]], 
        size=200
    )
    
    # 协方差矩阵
    cov = np.cov(X.T)
    eigvals, eigvecs = np.linalg.eigh(cov)  # eigh for symmetric
    
    print("协方差矩阵:\n", cov)
    print("\n谱分解 A = QΛQ^T:")
    
    # 重构验证
    Q = eigvecs
    Lambda = np.diag(eigvals)
    reconstructed = Q @ Lambda @ Q.T
    print(f"重构误差: {np.linalg.norm(cov - reconstructed):.2e}")
    
    # 外积和表示
    print("\n外积和表示 (sum λ_i·q_i·q_i^T):")
    outer_sum = np.zeros_like(cov)
    for i in range(2):
        outer = np.outer(eigvecs[:, i], eigvecs[:, i])
        outer_sum += eigvals[i] * outer
        print(f"  λ_{i+1}·q_{i+1}·q_{i+1}^T = {eigvals[i]:.2f} ×\n{outer}")
    print(f"\n总和 = \n{outer_sum}")

spectral_decomposition_example()
```

## 2. SVD（奇异值分解）实战

### 2.1 核心公式

任何矩阵 $A_{m\times n}$ 都可分解为：

$$A = U \Sigma V^T$$

- $U$：左奇异向量（$AA^T$的特征向量）
- $V$：右奇异向量（$A^TA$的特征向量）
- $\Sigma$：奇异值（$\sqrt{A^TA的特征值}$）

**与特征值分解的关系**：如果 $A$ 是方阵且对称，SVD = 谱分解。

### 2.2 完全numpy实现

```python
def svd_manual(A):
    """手写SVD（教学用，生产请用np.linalg.svd）"""
    # 1. 计算 A^T A 的特征分解得到 V 和 σ²
    ATA = A.T @ A
    eigvals_V, V = np.linalg.eigh(ATA)
    
    # eigh返回升序，需要反转
    idx = np.argsort(eigvals_V)[::-1]
    eigvals_V = eigvals_V[idx]
    V = V[:, idx]
    
    # 2. 奇异值 = sqrt(特征值)
    singular_vals = np.sqrt(np.maximum(eigvals_V, 0))
    
    # 3. 计算 U: u_i = A·v_i / σ_i
    # 只对非零奇异值计算
    r = np.sum(singular_vals > 1e-10)
    U = np.zeros((A.shape[0], r))
    Sigma = np.zeros((A.shape[0], A.shape[1]))
    
    for i in range(r):
        U[:, i] = (A @ V[:, i]) / singular_vals[i]
        Sigma[i, i] = singular_vals[i]
    
    return U, singular_vals, V, Sigma

# 测试
np.random.seed(42)
A = np.random.randn(5, 3)

U_manual, s_manual, V_manual, Sigma_manual = svd_manual(A)
U_lib, s_lib, Vt_lib = np.linalg.svd(A, full_matrices=False)

print("SVD验证:")
print(f"手动奇异值: {s_manual}")
print(f"库函数奇异值: {s_lib}")
print(f"U向量一致: {np.allclose(np.abs(U_manual), np.abs(U_lib))}")
print(f"重构误差: {np.linalg.norm(A - U_manual @ Sigma_manual @ V_manual.T):.2e}")
```

### 2.3 SVD的三种视角

```python
def svd_perspectives():
    """SVD的三种理解视角"""
    A = np.array([[3, 2, 1],
                  [1, 2, 3],
                  [2, 1, 3],
                  [1, 3, 2]])
    
    U, s, Vt = np.linalg.svd(A, full_matrices=False)
    V = Vt.T
    S = np.diag(s)
    
    print("原始矩阵 A (4×3):")
    print(A)
    
    print("\n视角1: 列空间基")
    print("U 的列是列空间的正交基（4D→3D的映射方向）:")
    print(U.round(3))
    
    print("\n视角2: 行空间基")
    print("V^T 的行是行空间的正交基（3D→4D的映射方向）:")
    print(Vt.round(3))
    
    print("\n视角3: 秩-r 外积和")
    print("A = σ₁u₁v₁^T + σ₂u₂v₂^T + ...")
    r = np.sum(s > 1e-10)
    for i in range(r):
        term = s[i] * np.outer(U[:, i], V[:, i])
        print(f"  σ_{i+1}={s[i]:.2f}: \n{term.round(2)}")

svd_perspectives()
```

### 2.4 低秩近似与压缩

```python
def low_rank_approx():
    """SVD低秩近似：图像压缩视角"""
    # 生成一个"图像"矩阵
    n = 50
    X, Y = np.meshgrid(np.linspace(-3, 3, n), np.linspace(-3, 3, n))
    img = np.sin(X) * np.cos(Y) + 0.5 * np.sin(2*X) * np.cos(2*Y)
    img += np.random.randn(n, n) * 0.1
    
    U, s, Vt = np.linalg.svd(img, full_matrices=False)
    
    print(f"原始大小: {n}×{n} = {n*n} 个值")
    
    for k in [1, 3, 5, 10, 20, 50]:
        approx = U[:, :k] @ np.diag(s[:k]) @ Vt[:k, :]
        error = np.linalg.norm(img - approx) / np.linalg.norm(img)
        compression = (k * (1 + n + n)) / (n * n)
        print(f"  k={k:2d}: 相对误差={error:.3f}, 压缩比={compression:.2%}")

low_rank_approx()
```

## 3. PCA（主成分分析）—— 协方差矩阵的谱分解

### 3.1 PCA = 数据协方差矩阵的特征分解

```python
def pca_from_scratch(X, n_components=None):
    """从零实现PCA"""
    # 1. 中心化
    mean = np.mean(X, axis=0)
    X_centered = X - mean
    
    # 2. 协方差矩阵
    cov = (X_centered.T @ X_centered) / (X.shape[0] - 1)
    
    # 3. 特征分解
    eigvals, eigvecs = np.linalg.eigh(cov)
    
    # 4. 按特征值降序排列
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]
    
    if n_components:
        eigvecs = eigvecs[:, :n_components]
    
    # 5. 投影
    X_pca = X_centered @ eigvecs
    
    # 6. 解释方差比
    explained_ratio = eigvals / np.sum(eigvals)
    
    return X_pca, eigvecs, mean, explained_ratio

# 测试：对合成数据做PCA
np.random.seed(42)
n = 300
# 构造：本质是2维的，嵌入在5维空间
Z = np.random.randn(n, 2) 
W = np.array([[2, 1, 0, 3, -1], 
              [1, -2, 4, 0, 2]])  # 2×5 的载荷矩阵
X = Z @ W + np.random.randn(n, 5) * 0.2

X_pca, components, mean, ev_ratio = pca_from_scratch(X, n_components=2)

print("PCA结果:")
print(f"前2个主成分解释方差: {ev_ratio[:2].sum():.2%}")
print(f"各成分解释方差比: {ev_ratio[:5].round(3)}")
print("载荷矩阵（主成分方向）:")
print(components.round(3))
```

### 3.2 与SVD的关系

**核心关系**：$X = U\Sigma V^T$，则 $X^TX = V\Sigma^2 V^T$

```python
def pca_via_svd(X):
    """通过SVD做PCA（数值更稳定）"""
    # 中心化
    X_centered = X - X.mean(axis=0)
    
    # SVD
    U, s, Vt = np.linalg.svd(X_centered, full_matrices=False)
    
    # 主成分得分 = U @ diag(s)
    scores = U * s  # broadcasting
    
    # 载荷矩阵 = V^T 的行
    loadings = Vt.T
    
    # 解释方差
    explained_var = s**2 / (X.shape[0] - 1)
    explained_ratio = explained_var / explained_var.sum()
    
    return scores, loadings, explained_ratio
```

## 4. 伪逆与最小二乘

### 4.1 Moore-Penrose 伪逆

对于不可逆矩阵（非方阵或奇异），伪逆是逆的推广：

$$A^+ = V \Sigma^+ U^T$$

其中 $\Sigma^+$ 是对角线上取 $\sigma_i^{-1}$（非零奇异值倒数）。

```python
def pseudo_inverse_manual(A):
    """手写伪逆"""
    U, s, Vt = np.linalg.svd(A, full_matrices=False)
    
    # 截断过小的奇异值（防止数值爆炸）
    tol = 1e-10 * max(A.shape) * s[0]
    s_inv = np.array([1/si if si > tol else 0 for si in s])
    
    # A^+ = V·Σ^+·U^T
    A_pinv = Vt.T @ np.diag(s_inv) @ U.T
    return A_pinv

# 验证
A = np.array([[1, 2], [3, 4], [5, 6]])
A_pinv_manual = pseudo_inverse_manual(A)
A_pinv_lib = np.linalg.pinv(A)

print("伪逆验证:")
print(f"手动:\n{A_pinv_manual.round(3)}")
print(f"numpy:\n{A_pinv_lib.round(3)}")
print(f"一致: {np.allclose(A_pinv_manual, A_pinv_lib)}")

# 伪逆的性质
print(f"\nA·A⁺·A = A: {np.allclose(A @ A_pinv_lib @ A, A)}")
print(f"A⁺·A·A⁺ = A⁺: {np.allclose(A_pinv_lib @ A @ A_pinv_lib, A_pinv_lib)}")
```

### 4.2 最小二乘：几何视角

求解 $Ax = b$（超定方程，$m > n$）：

$$x^* = \arg\min_x \|Ax - b\|_2^2$$

**正规方程**：$A^T A x = A^T b$ → $x = (A^T A)^{-1} A^T b = A^+ b$

```python
def least_squares_demo():
    """最小二乘推导 + 与伪逆的关系"""
    # 生成数据：y = 2x + 1 + 噪声
    np.random.seed(42)
    x = np.linspace(0, 10, 20)
    true_w, true_b = 2.0, 1.0
    y = true_w * x + true_b + np.random.randn(20) * 1.5
    
    # 设计矩阵
    A = np.column_stack([x, np.ones_like(x)])
    
    # 方法1: 正规方程
    w_ls = np.linalg.inv(A.T @ A) @ A.T @ y
    
    # 方法2: 伪逆
    w_pinv = np.linalg.pinv(A) @ y
    
    # 方法3: numpy.linalg.lstsq
    w_lstsq, residuals, rank, s = np.linalg.lstsq(A, y, rcond=None)
    
    print("最小二乘结果 (w, b):")
    print(f"  正规方程: {w_ls}")
    print(f"  伪逆:     {w_pinv}")
    print(f"  lstsq:    {w_lstsq}")
    print(f"  真值:     ({true_w}, {true_b})")
    
    # 几何解释：残差垂直于列空间
    y_hat = A @ w_ls
    residual = y - y_hat
    print(f"\n几何解释:")
    print(f"  残差与列空间正交: {np.allclose(A.T @ residual, 0, atol=1e-10)}")
    print(f"  ||残差|| = {np.linalg.norm(residual):.3f}")

least_squares_demo()
```

### 4.3 NMF（非负矩阵分解）

```python
def nmf_manual(V, r, max_iter=200, tol=1e-4):
    """手写NMF（乘法更新规则）"""
    m, n = V.shape
    W = np.abs(np.random.randn(m, r))
    H = np.abs(np.random.randn(r, n))
    
    errors = []
    for i in range(max_iter):
        # 乘法更新
        H *= (W.T @ V) / (W.T @ W @ H + 1e-10)
        W *= (V @ H.T) / (W @ H @ H.T + 1e-10)
        
        error = np.linalg.norm(V - W @ H, 'fro')
        errors.append(error)
        
        if i > 0 and abs(errors[-2] - errors[-1]) < tol:
            break
    
    return W, H, errors

# 测试：分解一个非负矩阵
np.random.seed(42)
V_true = np.random.rand(100, 50) @ np.random.rand(50, 80)
V_true = np.maximum(V_true, 0)  # 强制非负

W, H, errors = nmf_manual(V_true, r=50)
print(f"NMF完成: 迭代{len(errors)}次, 最终误差={errors[-1]:.4f}")
print(f"原始V: {V_true.shape}, W: {W.shape}, H: {H.shape}")
```

## 5. 量化实战

### 5.1 PCA因子模型（降维构建因子）

```python
def pca_factor_model():
    """
    PCA因子模型：从多个资产收益率中提取主要因子
    
    在量化中的用途：
    - 识别市场的主驱动因子
    - 剔除噪音，做统计套利
    - 风险归因：看组合在不同因子上的暴露
    """
    np.random.seed(42)
    n_assets = 30
    n_days = 500
    n_factors = 3
    
    # 模拟因子收益率
    factors = np.random.randn(n_days, n_factors)
    
    # 载荷矩阵
    loadings = np.random.randn(n_factors, n_assets) * 0.5
    
    # 资产收益率 = 因子 * 载荷 + 特有风险
    returns = factors @ loadings + np.random.randn(n_days, n_assets) * 0.2
    
    # PCA提取因子
    returns_centered = returns - returns.mean(axis=0)
    U, s, Vt = np.linalg.svd(returns_centered, full_matrices=False)
    
    # 提取的主成分（因子）
    n_components = 3
    extracted_factors = returns_centered @ Vt[:n_components].T
    
    # 相关性分析
    corr_matrix = np.corrcoef(extracted_factors.T, factors.T)[:n_components, n_components:]
    print("PCA因子 vs 真实因子的相关性矩阵:")
    print(corr_matrix.round(3))
    print(f"对角线均值: {np.mean([corr_matrix[i,i] for i in range(n_components)]):.3f}")
    
    # 解释方差
    explained = s**2 / np.sum(s**2)
    print(f"\n前{n_components}个因子解释方差: {explained[:n_components].sum():.2%}")
    
    # 用于风险归因：组合方差分解
    weights = np.ones(n_assets) / n_assets  # 等权组合
    factor_exposure = weights @ Vt[:n_components].T  # 组合在因子上的暴露
    factor_risk = factor_exposure**2 * explained[:n_components]
    specific_risk = 1 - factor_risk.sum()
    
    print(f"\n等权组合风险归因:")
    for i in range(n_components):
        print(f"  因子{i+1}风险占比: {factor_risk[i]:.2%}")
    print(f"  特有风险占比: {specific_risk:.2%}")

pca_factor_model()
```

### 5.2 SVD矩阵补全（推荐系统/缺失数据处理）

```python
def svd_matrix_completion():
    """
    SVD矩阵补全：用低秩近似填补缺失值
    
    量化应用：
    - 补全缺失的收益率序列
    - 构建相关性矩阵（处理不同时间段上市的股票）
    - 协同过滤：相似策略推荐
    """
    np.random.seed(42)
    n_assets = 20
    n_days = 100
    rank = 3
    
    # 生成低秩收益率矩阵
    U_true = np.random.randn(n_days, rank)
    V_true = np.random.randn(rank, n_assets)
    R_true = U_true @ V_true  # 真正的收益率矩阵
    
    # 观测到部分值（80%缺失）
    mask = np.random.binomial(1, 0.2, R_true.shape).astype(bool)
    R_obs = R_true.copy()
    R_obs[~mask] = 0
    
    def soft_impute(R_obs, mask, rank=5, max_iter=100, lambda_reg=1.0):
        """软阈值SVD补全（SoftImpute算法简化版）"""
        R_filled = R_obs.copy()
        
        for it in range(max_iter):
            # SVD
            U, s, Vt = np.linalg.svd(R_filled, full_matrices=False)
            
            # 软阈值
            s_thresholded = np.maximum(s - lambda_reg, 0)
            
            # 低秩近似
            R_approx = (U * s_thresholded) @ Vt
            
            # 只填充缺失值，保留观测值
            R_new = R_obs.copy()
            R_new[~mask] = R_approx[~mask]
            
            change = np.linalg.norm(R_new - R_filled) / np.linalg.norm(R_filled)
            R_filled = R_new
            
            if change < 1e-4:
                break
        
        return R_filled
    
    R_completed = soft_impute(R_obs, mask, rank=rank)
    
    # 评估
    error_obs = np.linalg.norm(R_completed[mask] - R_true[mask]) / np.linalg.norm(R_true[mask])
    error_missing = np.linalg.norm(R_completed[~mask] - R_true[~mask]) / np.linalg.norm(R_true[~mask])
    
    print("SVD矩阵补全结果:")
    print(f"  观测集误差: {error_obs:.4f}")
    print(f"  缺失集误差: {error_missing:.4f}")
    print(f"  缺失率: {1 - mask.mean():.0%}")

svd_matrix_completion()
```

### 5.3 协方差矩阵的谱修正

```python
def covariance_shrinkage():
    """
    协方差矩阵收缩：谱修正提高数值稳定性
    
    量化应用：
    - 协方差矩阵的"病态"导致组合优化失败
    - 小样本下样本协方差偏差大
    - 收缩估计 = 样本协方差 + 先验协方差的凸组合
    """
    np.random.seed(42)
    n_assets = 50
    n_days = 100  # 比资产数少！病态
    
    # 生成收益率矩阵
    returns = np.random.randn(n_days, n_assets) * 0.01
    
    # 样本协方差
    sample_cov = np.cov(returns.T)
    
    # 条件数
    eigvals = np.linalg.eigvalsh(sample_cov)
    cond_number = max(eigvals) / min(eigvals)
    
    print(f"协方差矩阵大小: {n_assets}×{n_assets}")
    print(f"样本数: {n_days} < {n_assets} → 不可逆!")
    print(f"条件数: {cond_number:.2e}")
    print(f"最小特征值: {min(eigvals):.2e}")
    print(f"非正特征值数: {np.sum(eigvals <= 0)}")
    
    # 谱修正：添加正则项（Ledoit-Wolf简化版）
    shrinkage_target = np.mean(np.diag(sample_cov)) * np.eye(n_assets)
    alpha = 0.3  # 收缩强度
    shrunk_cov = (1 - alpha) * sample_cov + alpha * shrinkage_target
    
    shrunk_eigvals = np.linalg.eigvalsh(shrunk_cov)
    shrunk_cond = max(shrunk_eigvals) / min(shrunk_eigvals)
    
    print(f"\n收缩后条件数: {shrunk_cond:.2e}")
    print(f"收缩后最小特征值: {min(shrunk_eigvals):.2e}")

covariance_shrinkage()
```

## 6. ML/DL关联总结

| 线性代数概念 | ML/DL应用 | 量化应用 |
|---|---|---|
| 谱分解 | PCA、谱聚类、图神经网络 | PCA因子模型、风险归因 |
| SVD | 矩阵补全、推荐系统、词嵌入（Word2Vec的SVD解释） | 缺失收益率补全、多空组合构造 |
| 伪逆 | Ridge回归解析解、神经网络的过参数化分析 | 最小二乘对冲比率计算 |
| NMF | 主题模型、人脸部件分解 | 因子拆解、风格暴露识别 |
| 特征值分解 | 谱归一化（GAN训练稳定化）、图拉普拉斯 | 协方差矩阵正则化、最优权重求解 |
