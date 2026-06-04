# 矩阵分解 Matrix Decomposition

## LU 分解

将矩阵分解为下三角 $L$ 和上三角 $U$ 的乘积：$A = LU$。

### 高斯消元视角
通过初等行变换（消元）将 $A$ 化为上三角 $U$，消元矩阵的逆乘积构成 $L$。
$$L = \begin{pmatrix}1 & 0 & \cdots & 0 \\ l_{21} & 1 & \cdots & 0 \\ \vdots & \vdots & \ddots & \vdots \\ l_{n1} & l_{n2} & \cdots & 1\end{pmatrix}, \quad U = \begin{pmatrix}u_{11} & u_{12} & \cdots & u_{1n} \\ 0 & u_{22} & \cdots & u_{2n} \\ \vdots & \vdots & \ddots & \vdots \\ 0 & 0 & \cdots & u_{nn}\end{pmatrix}$$

### 选主元
当 $A$ 有零主元或接近零主元时，数值不稳定。需要**部分选主元（PA=LU）**，即用置换矩阵 $P$ 重排行：
$$PA = LU$$
**完全选主元**同时对行和列进行置换：$PAQ = LU$。

### 用途
解线性方程组 $Ax = b$：先解 $Ly = b$（前代），再解 $Ux = y$（回代），复杂度 $O(n^2)$。

---

## QR 分解

$A = QR$，其中 $Q$ 正交（$Q^T Q = I$），$R$ 上三角。

### Gram-Schmidt 过程
对列向量 $a_1,...,a_n$ 正交化：
1. $u_1 = a_1$, $q_1 = u_1 / \|u_1\|$
2. $u_k = a_k - \sum_{i=1}^{k-1} \langle a_k, q_i\rangle q_i$, $q_k = u_k / \|u_k\|$

**数值问题**：经典 GS 不稳定 → **修正 Gram-Schmidt (MGS)**：每步实时更新剩余向量。

### Householder 反射
通过反射矩阵 $H = I - 2vv^T / v^T v$ 逐列消去下三角元素，更稳定，实际中最常用。

### 用途
最小二乘 $Ax \approx b$：$Rx = Q^T b$（无需解正规方程，条件数更好）。

---

## Cholesky 分解

对**对称正定矩阵** $A$：$A = LL^T$（$L$ 下三角）。
或 $A = R^T R$（$R$ 上三角）。

### 存在条件
- $A$ 对称：$A = A^T$
- $A$ 正定：$x^T A x > 0, \forall x \neq 0$
- 所有顺序主子式 $> 0$

### 计算
$A_{ii} = \sum_{k=1}^{i-1} L_{ik}^2 + L_{ii}^2$，递推解出 $L$，$O(n^3/3)$（是 LU 的一半）。

### 用途
最速求解正定线性系统（如正规方程 $X^T X \beta = X^T y$）。

---

## SVD 奇异值分解

任意 $A \in \mathbb{R}^{m \times n}$ 可分解为：
$$A = U \Sigma V^T$$
- $U \in \mathbb{R}^{m \times m}$：左奇异向量，正交
- $\Sigma \in \mathbb{R}^{m \times n}$：对角奇异值 $\sigma_1 \geq \sigma_2 \geq ... \geq \sigma_r > 0$
- $V \in \mathbb{R}^{n \times n}$：右奇异向量，正交

### 几何意义
$A$ 将单位球映射为椭球，$\sigma_i$ 是椭球半轴长，$u_i$ 方向为半轴方向。

### Truncated SVD
保留前 $k$ 个最大奇异值：$A_k = U_k \Sigma_k V_k^T$，是**最优低秩逼近**（Eckart-Young 定理）。

### PCA 关系
数据矩阵 $X$ 的 SVD：$X = U \Sigma V^T$，则协方差矩阵 $X^T X = V \Sigma^T \Sigma V^T$。
- 主成分方向 = $V$ 的列 = 右奇异向量
- 主成分得分 = $U \Sigma$（投影后的坐标）

---

## Eigenvalue Decomposition vs SVD

| 特性 | 特征值分解 (EVD) | SVD |
|------|-----------------|-----|
| 适用矩阵 | 方阵（对角化需要 $n$ 个独立特征向量） | 任意矩阵 |
| 分解形式 | $A = PDP^{-1}$（$P$ 未必正交） | $A = U \Sigma V^T$（正交基） |
| 对称矩阵 | $A = Q \Lambda Q^T$（$Q$ 正交） | $U = V$，$\Sigma = |\Lambda|$ |
| 数值稳定性 | 对非对称矩阵较差 | 极稳定 |
| 实对称时 | EVD = SVD（排序差异） | 奇异值 = 特征值绝对值 |

---

## 数值稳定性总结

| 分解 | 复杂度 | 稳定性 | 适用场景 |
|------|--------|--------|---------|
| LU (无选主元) | $O(2n^3/3)$ | 不稳定 | 仅理论 |
| LU (部分选主元) | $O(2n^3/3)$ | 稳定 | 一般线性系统 |
| Cholesky | $O(n^3/3)$ | 稳定 | 正定矩阵 |
| QR (Householder) | $O(4n^3/3)$ | 稳定 | 最小二乘 |
| SVD | $O(4mn^2)$ | 极稳定 | 低秩逼近、PCA |
