# 数值线性代数 Numerical Linear Algebra

## 浮点误差与病态问题

### IEEE 754 浮点数
- 单精度 (float32)：23 位尾数，约 7 位十进制精度，$\epsilon_{\text{mach}} \approx 1.19 \times 10^{-7}$
- 双精度 (float64)：52 位尾数，约 16 位十进制精度，$\epsilon_{\text{mach}} \approx 2.22 \times 10^{-16}$

**浮点运算非结合**：$(a+b)+c \neq a+(b+c)$。大数吃小数是常见误差源。

### Ill-conditioned 问题
输入微扰导致输出巨大变化。典型案例：

**Hilbert 矩阵**：$H_{ij} = 1/(i+j-1)$，$n \times n$ Hilbert 矩阵的条件数以指数级增长，$n=6$ 时 $\kappa \approx 10^7$，$n=12$ 时 $\approx 10^{16}$，完全无法可靠求逆。

## 条件数

定义：$\kappa(A) = \|A\| \cdot \|A^{-1}\|$

### 意义
关于线性系统 $Ax = b$：
- $\frac{\|\delta x\|}{\|x\|} \leq \kappa(A) \frac{\|\delta b\|}{\|b\|}$（输入扰动放大倍数）
- $\frac{\|\delta x\|}{\|x\|} \leq \kappa(A) \frac{\|\delta A\|}{\|A\|}$（系数矩阵扰动）

**规则**：$\log_{10}(\kappa(A)) \approx$ 损失的有效数字位数。

### 常用范数下的条件数
- $\kappa_2(A) = \sigma_{\max}/\sigma_{\min}$（SVD 计算，最常用）
- $\kappa_\infty(A) = \|A\|_\infty \cdot \|A^{-1}\|_\infty$

---

## 迭代法求解线性方程组

当 $A$ 为大型稀疏矩阵时，直接法（LU）不可行，使用迭代法。

### Jacobi 迭代
$$x_i^{(k+1)} = \frac{1}{a_{ii}} \left(b_i - \sum_{j \neq i} a_{ij} x_j^{(k)}\right)$$
收敛条件：$A$ 严格对角占优（$|a_{ii}| > \sum_{j \neq i} |a_{ij}|$）。

### Gauss-Seidel 迭代
$$x_i^{(k+1)} = \frac{1}{a_{ii}} \left(b_i - \sum_{j < i} a_{ij} x_j^{(k+1)} - \sum_{j > i} a_{ij} x_j^{(k)}\right)$$
始终使用最新值，比 Jacobi 更快，需 $A$ 对称正定或对角占优。

### 共轭梯度法 (CG)
用于**对称正定**矩阵，每步沿 $A$-共轭方向搜索。

**算法**：
1. $r_0 = b - Ax_0$, $p_0 = r_0$
2. $\alpha_k = (r_k^T r_k) / (p_k^T A p_k)$
3. $x_{k+1} = x_k + \alpha_k p_k$
4. $r_{k+1} = r_k - \alpha_k A p_k$
5. $\beta_k = (r_{k+1}^T r_{k+1}) / (r_k^T r_k)$
6. $p_{k+1} = r_{k+1} + \beta_k p_k$

**理论收敛**：$n$ 步内精确解。实际快速收敛取决于**特征值聚集**程度。

---

## 预处理 (Preconditioner)

将 $Ax = b$ 转化为 $M^{-1}Ax = M^{-1}b$，使 $\kappa(M^{-1}A) \ll \kappa(A)$。

### 常见预处理方法

| 方法 | $M$ 选择 | 特点 |
|------|---------|------|
| **Jacobi** | $\text{diag}(A)$ | 最简单，对角占优时有效 |
| **SSOR** | $(D+L)D^{-1}(D+L)^T$ | 对称，可结合 CG |
| **不完全 Cholesky** (IC) | $LL^T \approx A$（舍去非零填充） | 对 SPD 矩阵极佳 |
| **不完全 LU** (ILU) | $LU \approx A$ | 一般矩阵 |
| **多重网格** | 多尺度粗化 | Poisson 问题最优 |

---

## Lanczos 与 Arnoldi 迭代

### Arnoldi 迭代
将一般矩阵 $A$ 约化为**上 Hessenberg 矩阵** $H_m$：
$$A Q_m = Q_m H_m + \beta_m q_{m+1} e_m^T$$
用于 **GMRES**（一般矩阵的 Krylov 子空间法）。

### Lanczos 迭代
Arnoldi 在对称矩阵上的特例，$H_m$ 退化为**三对角**矩阵 $T_m$：
$$A Q_m = Q_m T_m + \beta_m q_{m+1} e_m^T$$
用于 **CG** 和 **Lanczos 特征值求解**。

---

## BLAS (Basic Linear Algebra Subprograms)

| Level | 运算 | 复杂度 | 例子 |
|-------|------|--------|------|
| **1** | 向量-向量 | $O(n)$ | $y \leftarrow \alpha x + y$ (AXPY), 点积 |
| **2** | 矩阵-向量 | $O(n^2)$ | $y \leftarrow \alpha A x + y$ (GEMV) |
| **3** | 矩阵-矩阵 | $O(n^3)$ | $C \leftarrow \alpha AB + \beta C$ (GEMM) |

**性能关键**：BLAS 3 支持缓存块化（tiling），FLOP/s 远超 BLAS 1/2。实际库如 OpenBLAS、MKL、cuBLAS 都精心手工优化。
