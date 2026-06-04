# 凸优化 Convex Optimization

## 凸集与凸函数

### 凸集定义
集合 $C \subseteq \mathbb{R}^n$ 是凸集，当对任意 $x,y \in C$ 和 $\theta \in [0,1]$，有：
$$\theta x + (1-\theta)y \in C$$

**常见凸集**：超平面 $\{x | a^T x = b\}$、半空间 $\{x | a^T x \leq b\}$、多面体、欧氏球、椭球、范数锥。

### 凸函数判定
函数 $f: \mathbb{R}^n \to \mathbb{R}$ 是凸函数，当 $\text{dom}(f)$ 是凸集且：
$$f(\theta x + (1-\theta)y) \leq \theta f(x) + (1-\theta)f(y), \quad \forall \theta \in [0,1]$$

**一阶条件**（可微）：$f(y) \geq f(x) + \nabla f(x)^T (y-x)$，即切线是全局下界。

**二阶条件**（二次可微）：$\nabla^2 f(x) \succeq 0$（Hessian 半正定）。

**保凸运算**：非负加权和、与仿射函数复合、逐点极大、逐点上确界。

---

## 凸优化问题标准形式

$$\begin{aligned}
&\min_{x} f_0(x) \\
&\text{s.t. } f_i(x) \leq 0, \quad i=1,...,m \\
&\qquad h_j(x) = 0, \quad j=1,...,p
\end{aligned}$$

其中 $f_0,...,f_m$ 是凸函数，$h_j$ 是仿射函数。**可行域是凸集** → 局部最优即全局最优。

---

## Lagrange 对偶

Lagrange 函数：$L(x,\lambda,\nu) = f_0(x) + \sum_{i=1}^m \lambda_i f_i(x) + \sum_{j=1}^p \nu_j h_j(x)$，其中 $\lambda_i \geq 0$。

对偶函数：$g(\lambda,\nu) = \inf_x L(x,\lambda,\nu)$（一定是凹函数）。

对偶问题：$\max_{\lambda \geq 0, \nu} g(\lambda,\nu)$

**弱对偶**：$d^* \leq p^*$。**强对偶**：$d^* = p^*$（需满足约束规格）。

### Slater 条件（强对偶的充分条件）
存在严格内点 $x \in \text{relint}(\mathcal{D})$，使得 $f_i(x) < 0$（对不等式约束），$h_j(x) = 0$。

### KKT 条件（最优性充要条件）
在强对偶且可微条件下，最优解满足：
1. **原始可行**：$f_i(x^*) \leq 0,\; h_j(x^*) = 0$
2. **对偶可行**：$\lambda_i^* \geq 0$
3. **互补松弛**：$\lambda_i^* f_i(x^*) = 0$
4. **梯度为零**：$\nabla f_0(x^*) + \sum \lambda_i^* \nabla f_i(x^*) + \sum \nu_j^* \nabla h_j(x^*) = 0$

---

## 梯度下降变体

| 算法 | 核心公式 | 特点 |
|------|---------|------|
| **BGD** | $x_{k+1} = x_k - \eta \nabla f(x_k)$ | 全数据梯度，稳定但慢 |
| **SGD** | $x_{k+1} = x_k - \eta \nabla f_i(x_k)$ | 单样本，噪声大，收敛快 |
| **Mini-batch** | $x_{k+1} = x_k - \eta \frac{1}{|B|} \sum_{i \in B} \nabla f_i(x_k)$ | 折中，利用矩阵运算加速 |
| **Momentum** | $v_k = \gamma v_{k-1} + \eta \nabla f(x_k)$; $x_{k+1} = x_k - v_k$ | 累积历史梯度，加速穿越平坦区 |
| **NAG** | $v_k = \gamma v_{k-1} + \eta \nabla f(x_k - \gamma v_{k-1})$; $x_{k+1} = x_k - v_k$ | 看前方再更新，更准确 |
| **AdaGrad** | $G_k = G_{k-1} + \nabla f_k \odot \nabla f_k$; $x_{k+1} = x_k - \frac{\eta}{\sqrt{G_k + \epsilon}} \odot \nabla f_k$ | 自适应学习率，稀疏特征好 |
| **RMSProp** | $E[g^2]_k = \beta E[g^2]_{k-1} + (1-\beta) \nabla f_k^2$; $\Delta x_k = -\frac{\eta}{\sqrt{E[g^2]_k + \epsilon}} \odot \nabla f_k$ | 解决 AdaGrad 学习率骤降问题 |
| **Adam** | $m_k = \beta_1 m_{k-1} + (1-\beta_1) \nabla f_k$（一阶矩）; $v_k = \beta_2 v_{k-1} + (1-\beta_2) \nabla f_k^2$（二阶矩）; 偏差校正后更新 | Momentum + RMSProp，最实用 |

**Adam 偏差校正**：$\hat{m}_k = m_k/(1-\beta_1^k)$, $\hat{v}_k = v_k/(1-\beta_2^k)$

---

## 软间隔 SVM — 凸优化案例

**原始问题**（线性不可分）：
$$\min_{w,b,\xi} \frac{1}{2}\|w\|^2 + C \sum_{i=1}^n \xi_i$$
$$\text{s.t. } y_i(w^T x_i + b) \geq 1 - \xi_i, \quad \xi_i \geq 0$$

这是一个二次规划（QP）问题，目标函数二次凸，约束线性 → 标准凸优化。

**对偶问题**：
$$\max_{\alpha} \sum_{i=1}^n \alpha_i - \frac{1}{2} \sum_{i,j} \alpha_i \alpha_j y_i y_j \langle x_i, x_j \rangle$$
$$\text{s.t. } 0 \leq \alpha_i \leq C, \quad \sum \alpha_i y_i = 0$$

KKT 互补松弛决定支持向量：$\alpha_i(y_i(w^T x_i + b) - 1 + \xi_i) = 0$。
