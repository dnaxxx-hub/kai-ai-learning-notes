# 矩阵分解与降维 — 数学/统计学深潜第4课

> ✅ 课程类型：#数学深潜 #矩阵分解 #SVD #PCA
> 📅 日期：2026-05-17
> 📍 位置：memory/learning/math_04_matrix_decomp.md

---

## 1. 特征值分解（EVD）

### 1.1 核心概念

方阵 A ∈ ℝ^{n×n}，若存在非零向量 v 使得 Av = λv，则 λ 是特征值，v 是特征向量。

**几何意义**：矩阵 A 在 v 方向上只是做了 λ 倍的拉伸，没有旋转。

**矩阵形式**：AV = VΛ

### 1.2 对称矩阵的对角化

如果 A = A^T（对称矩阵），则：
- 特征值全是实数
- 不同特征值对应的特征向量互相正交
- A = QΛQ^T，其中 Q 是正交矩阵（Q^T = Q^{-1}）

**谱定理**：对称矩阵可以分解为一维投影的和：
A = Σ λ_i q_i q_i^T

### 1.3 正定矩阵

如果所有特征值 λ_i > 0，则 A 是正定矩阵：
- x^T A x > 0 对所有 x ≠ 0 成立
- 在统计学中就是协方差矩阵的性质

### 1.4 局限

特征分解只能用于方阵，而且不是所有矩阵都可对角化（如非满秩的 Jordan 标准形）。

---

## 2. 奇异值分解（SVD）【核心】

### 2.1 定义

**任何矩阵** A ∈ ℝ^{m×n} 都可以分解为：

A = U Σ V^T

其中：
- U ∈ ℝ^{m×m}：左奇异向量，列是 AA^T 的特征向量，U^T U = I
- Σ ∈ ℝ^{m×n}：对角矩阵，对角元素 σ₁ ≥ σ₂ ≥ ... ≥ σ_r > 0，其余为 0
- V ∈ ℝ^{n×n}：右奇异向量，列是 A^T A 的特征向量，V^T V = I

### 2.2 几何解释

SVD 把线性变换分解为三步：
1. **旋转**（V^T 作用）
2. **拉伸**（Σ 作用——每个方向按 σ_i 缩放）
3. **旋转**（U 作用）

### 2.3 与特征分解的关系

- AA^T = UΣΣ^T U^T（U 是 AA^T 的特征向量）
- A^T A = VΣ^T Σ V^T（V 是 A^T A 的特征向量）
- σ_i² = λ_i(A^T A)

### 2.4 截断 SVD（Truncated SVD）

只看前 k 个最大的奇异值：
A ≈ U_k Σ_k V_k^T

**Eckart-Young 定理**：在秩 k 矩阵中，截断 SVD 给出了最优的 Frobenius 范数逼近。

### 2.5 应用

- **降维**：保留最大奇异值对应的方向
- **图像压缩**：取前 10% 的奇异值就能重构高质量图像
- **推荐系统**：矩阵填充的 SVD 方法
- **PCA**：通过 SVD 实现
- **矩阵求逆/伪逆**：A^† = VΣ^{-1}U^T（Moore-Penrose 伪逆）

---

## 3. PCA（主成分分析）

### 3.1 问题设定

给定中心化数据 X ∈ ℝ^{n×p}（已减均值），找 d 个方向 w_j（|w_j|=1）使得投影方差最大。

### 3.2 推导

**第一主成分：**
max w^T Σ w，s.t. w^T w = 1

拉格朗日函数：L = w^T Σ w - λ(w^T w - 1)

求导：∂L/∂w = 2Σw - 2λw = 0 → Σw = λw

所以 w 就是协方差矩阵 Σ 的最大特征值对应的特征向量！

**第 k 主成分：**
在第 k-1 个方向的正交补空间中找到最大方差方向 → Σ 的第 k 大特征向量

### 3.3 与 SVD 的关系

PCA 本质上就是 SVD 在中心化数据矩阵上的应用：

X = UΣV^T

- V 的列 = 主成分方向（载荷向量 / loadings）
- UΣ = 主成分得分（scores）
- 第 k 个主成分解释的方差 = σ²_k / Σσ²_j

### 3.4 方差解释比例

**Scree Plot**：画 σ²_k 对 k 的图

**累积方差解释比例：** (Σ_{j=1}^{k} σ²_j) / (Σ_{j=1}^{r} σ²_j)

**选取 k 的方法：**
- 累积方差 > 80%
- **Kaiser 准则**：取特征值 > 1 的
- **肘部法则**：Scree Plot 陡坡变缓的位置

### 3.5 几何理解

PCA 就是在数据点云中找到"最扩展"的 d 个正交方向。

```python
# 2D 直观理解
# 原始数据的协方差椭圆的"长轴"就是第一主成分
# "短轴"就是第二主成分
```

### 3.6 PCA 的局限

| 局限 | 说明 | 替代方案 |
|------|------|---------|
| 线性 | 只能捕捉线性关系 | Kernel PCA |
| 全局 | 所有点用相同降维 | t-SNE, UMAP |
| 方差驱动 | 方差小的信息可能被丢弃 | ICA |
| 可解释性 | 载荷向量通常是所有特征的组合 | Sparse PCA |

---

## 4. NMF（非负矩阵分解）

### 4.1 定义

X ≈ WH，其中 W ≥ 0, H ≥ 0

- X ∈ ℝ^{n×m}_+：非负数据矩阵（n 个样本，m 个特征）
- W ∈ ℝ^{n×r}_+：基矩阵
- H ∈ ℝ^{r×m}_+：系数矩阵
- r 是降维后的维度

### 4.2 与 PCA 的本质区别

| PCA | NMF |
|-----|-----|
| 正交基（可有负值） | 非负基（"零件"解释） |
| 全局方向 | 局部部件 |
| 方差排序 | 无排序 |
| 可加减组合 | 只能加性组合 |

**例子**：对于人脸数据
- PCA 给出"特征脸"——整体方向
- NMF 给出"特征部位"——鼻子、眼睛、嘴巴（非负导致只能"添加"不能"减去"）

### 4.3 乘法更新规则（Lee & Seung, 1999）

```
H_{αμ} ← H_{αμ} · (W^T X)_{αμ} / (W^T WH)_{αμ}
W_{iα} ← W_{iα} · (XH^T)_{iα} / (WHH^T)_{iα}
```

这是**乘法更新**（不是减法的梯度下降），保证了非负性。

### 4.4 应用

- **主题模型**：W 是文档-主题矩阵，H 是主题-词矩阵
- **音乐分解**：分离不同乐器的频谱
- **推荐系统**：用户-商品分解

---

## 5. 更多矩阵分解

### 5.1 QR 分解

A = QR，其中 Q 正交，R 上三角

**Gram-Schmidt 正交化**：从左到右，每次取一列，减去在前面的投影，再归一化。

**应用**：解线性方程组、最小二乘
- OLS 的数值稳定解法：β̂ = R^{-1} Q^T y

### 5.2 Cholesky 分解

对于对称正定矩阵 A：
A = LL^T（L 是下三角）

**复杂度**：O(n³/3)，比 LU 的 O(2n³/3) 快一倍

**应用**：
- 多元正态采样：生成 z ~ N(0,I)，然后 x = μ + Lz
- 卡尔曼滤波中的协方差更新

### 5.3 LU 分解

A = LU，L 下三角（对角线为 1），U 上三角

**应用**：解线性方程组 Ax = b
1. 解 Ly = b（前代）
2. 解 Ux = y（回代）

### 5.4 低秩近似

A ≈ U_k Σ_k V_k^T

**图像压缩演示**：
- 原始图像：m×n，需要 mn 个值
- 秩 k 近似：k(m+n) 个值
- 压缩比：mn / [k(m+n)]
- 比如 1000×1000 的图像，k=10 → 压缩比 50x！

---

## 6. Python 代码

```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA, NMF

# ═══════════════════════════════════════════
# 1. SVD 手动实现（幂迭代法）
# ═══════════════════════════════════════════
np.random.seed(42)

def power_iteration(A, n_iter=100):
    """幂迭代法求最大奇异值和对应向量"""
    n, m = A.shape
    v = np.random.randn(m)
    v = v / np.linalg.norm(v)
    
    for _ in range(n_iter):
        u = A @ v
        v = A.T @ u
        v = v / np.linalg.norm(v)
    
    u = A @ v
    sigma = np.linalg.norm(u)
    u = u / sigma
    return u, sigma, v

def svd_power(A, k=3):
    """用幂迭代+减影法求前k个SVD分量"""
    n, m = A.shape
    U = np.zeros((n, k))
    S = np.zeros(k)
    V = np.zeros((m, k))
    
    residual = A.copy()
    for i in range(k):
        u, s, v = power_iteration(residual)
        U[:, i] = u
        S[i] = s
        V[:, i] = v
        # 减去已找到的分量（减影法/正交化）
        residual -= s * np.outer(u, v)
    
    return U, S, V.T  # V^T 形式

# 测试：合成数据
n, m = 100, 50
A = np.random.randn(n, m)

# numpy SVD
U_np, S_np, Vt_np = np.linalg.svd(A, full_matrices=False)
print(f"NumPy SVD top 5 singular values: {S_np[:5].round(2)}")

# 幂迭代 SVD
U_pw, S_pw, Vt_pw = svd_power(A, k=5)
print(f"Power-iter SVD: {S_pw.round(2)}")

# ═══════════════════════════════════════════
# 2. PCA 手动实现
# ═══════════════════════════════════════════
# 生成数据
X = np.random.randn(200, 10)
# 加一些低维结构
true_W = np.random.randn(10, 3)  # 低维结构
scores = np.random.randn(200, 3)
X += scores @ true_W.T * 5

# SVD 实现 PCA
X_centered = X - X.mean(0)
U_pca, S_pca, Vt_pca = np.linalg.svd(X_centered, full_matrices=False)
loadings = Vt_pca.T  # 主成分方向
scores_pca = U_pca @ np.diag(S_pca)  # 主成分得分

# 解释方差比例
var_exp = S_pca**2 / (S_pca**2).sum()
cum_var_exp = np.cumsum(var_exp)

print(f"\n前3个主成分解释方差: {var_exp[:3].round(4)}")
print(f"累积: {cum_var_exp[2]:.4f}")

# ═══════════════════════════════════════════
# 3. sklearn PCA 验证
# ═══════════════════════════════════════════
pca_sk = PCA(n_components=3)
scores_sk = pca_sk.fit_transform(X)
print(f"sklearn PCA 解释方差: {pca_sk.explained_variance_ratio_.round(4)}")

# ═══════════════════════════════════════════
# 4. NMF 手动实现（乘法更新）
# ═══════════════════════════════════════════
X_nmf = np.random.rand(100, 50)  # 非负数据
r = 5

# 随机初始化
W = np.random.rand(100, r)
H = np.random.rand(r, 50)

def nmf_update(X, W, H, max_iter=200):
    for it in range(max_iter):
        H = H * (W.T @ X) / (W.T @ W @ H + 1e-10)
        W = W * (X @ H.T) / (W @ H @ H.T + 1e-10)
        if it % 50 == 0:
            recon_err = np.linalg.norm(X - W @ H) / np.linalg.norm(X)
            print(f"  iter {it}: relative error = {recon_err:.4f}")
    return W, H

print("\nNMF 收敛过程:")
W_final, H_final = nmf_update(X_nmf, W, H)

# ═══════════════════════════════════════════
# 5. 图像压缩演示（SVD低秩近似）
# ═══════════════════════════════════════════
# 用简单合成"图像"代替真实图片
img = np.zeros((200, 200))
for i in range(200):
    for j in range(200):
        dx, dy = i - 100, j - 100
        img[i, j] = np.sin(dx/20) * np.cos(dy/15) + \
                    np.sin((dx+dy)/30) + \
                    np.random.randn() * 0.1

# SVD
U_img, S_img, Vt_img = np.linalg.svd(img, full_matrices=False)

# 不同秩的重构
ranks = [1, 2, 5, 10, 20, 50]
print(f"\n== 图像低秩近似 ==")
for k in ranks:
    approx = U_img[:, :k] @ np.diag(S_img[:k]) @ Vt_img[:k, :]
    compression = k * (200 + 200) / (200 * 200)
    rel_err = np.linalg.norm(img - approx) / np.linalg.norm(img)
    print(f"  rank-{k}: 压缩比 {1/compression:.1f}x, 相对误差 {rel_err:.4f}")

# ═══════════════════════════════════════════
# 6. 特征脸概念演示（SVD成分可视化）
# ═══════════════════════════════════════════
# 随机数据上的"成分"可视化
X_faces_ish = np.random.randn(100, 400)  # 20×20的"脸"
U_f, S_f, Vt_f = np.linalg.svd(X_faces_ish, full_matrices=False)

# 前5个成分（"特征脸"）
fig, axes = plt.subplots(1, 5, figsize=(12, 3))
for i in range(5):
    component = Vt_f[i].reshape(20, 20)
    axes[i].imshow(component, cmap='RdBu')
    axes[i].set_title(f'SV={S_f[i]:.1f}')
    axes[i].axis('off')
plt.suptitle('Top 5 SVD Components')
plt.tight_layout()
plt.show()
```

---

## 7. 核心公式速查卡

| 分解 | 公式 | 适用矩阵 | 关键性质 |
|------|------|---------|---------|
| EVD | A = QΛQ^T | 对称方阵 | Q 正交，Λ 实对角 |
| SVD | A = UΣV^T | 任意 | U,V 正交，Σ 含奇异值 |
| QR | A = QR | 任意（方/长方） | Q 正交，R 上三角 |
| Cholesky | A = LL^T | 对称正定 | L 下三角 |
| NMF | X ≈ WH | 非负 | W,H ≥ 0，零件构成 |

---

## 学习要点总结

1. **SVD 是矩阵分解的瑞士军刀**——任何矩阵都能用，连接了 PCA、压缩、伪逆
2. **PCA = 中心化数据的 SVD**，理解 SVD 就理解了 PCA
3. **NMF ≠ PCA**：非负导致"加性部件"解释，和 PCA 的"整体方向"是天壤之别
4. **低秩近似 = 压缩**：前 k 个奇异值往往占了 90% 以上的信息
5. **数值稳定性排序**：SVD > QR > Cholesky ≈ EVD > 直接求 (X^T X)^{-1}
