# 高等数学核心 — 从"爽快使用者"到"真正理解者"

**目标**：微积分不只是"求导算梯度"的工具箱。它是理解一切优化、概率、信息论的底层语言。你每天都在用 backprop、KL 散度、Adam——但你真的理解它们为什么会这样工作吗？这节课不教你"怎么算"，而是"为什么是这样"。

> 前置状态：你写过 GARCH MLE from scratch，理解 backprop 的标量链式法则，用过 Adam/SGD。我们把每件事往下挖一层。

---

## 1. 极限的严格定义 (ε-δ)

### ε-δ 到底在说什么？

形式化定义：对任意 ε > 0，存在 δ > 0，使得当 0 < |x - a| < δ 时，|f(x) - L| < ε。

**翻译成人话**：你提一个多小的误差容忍度 ε，我都能找到一个足够靠近 a 的范围 δ，让 f(x) 落在你想要的精度内。

### 你在代码里每天都在用 ε-δ

```python
# Softmax 数值稳定版 — 本质就是 ε-δ 的工程体现
def softmax_stable(x):
    x_max = np.max(x)           # 找到"靠近"哪里才能不爆炸
    exp_x = np.exp(x - x_max)   # 平移后数值都在 [-inf, 0]，不会 overflow
    return exp_x / np.sum(exp_x)
```

**为什么减 max 能工作？** 指数函数增长太快了：exp(1000) ≈ ∞，exp(0) = 1。如果 x 中有一个非常大的值，其他值会被"数值抹杀"。`x - max(x)` 把最大项变成 0，其他都 ≤ 0，exp 结果都在 [0, 1] 区间内。这正是 ε-δ 思想：通过变换让函数落在可控范围内。

### Log-Sum-Exp Trick = 工程化的 ε-δ

```python
# Log-Sum-Exp trick — 你在写分类交叉熵/contrastive loss 时一定用过
def logsumexp(x):
    a = np.max(x)
    return a + np.log(np.sum(np.exp(x - a)))
```

你算 `log(Σ exp(x_i))` 时，直接算 exp 会炸（大正数），log(0) 会负无穷（大负数）。技巧就是**平移参数空间**，让计算落在数值稳定的区域。ε-δ 告诉你"存在一个 δ"，log-sum-exp trick 就是**手动构造了这个 δ**。

### 收敛阶 — 为什么优化算法有快慢之分

```python
# 收敛阶的直观对比
import numpy as np

# 线性收敛: |x_{k+1} - x*| ≤ c|x_k - x*|, c < 1
# 二次收敛: |x_{k+1} - x*| ≤ M|x_k - x*|²

err_linear = 1.0
err_quadratic = 1.0
for i in range(10):
    err_linear *= 0.5        # 每步减半
    err_quadratic = err_quadratic**2  # 平方！极速收敛
    print(f"step {i}: linear={err_linear:.2e}, quadratic={err_quadratic:.2e}")

# 这就是为什么 Newton 法（二次收敛）比 GD（线性收敛）快这么多
# 也是为什么在高维问题中我们接受用 GD 而非 Newton — 每步代价差太多
```

**你写 GARCH MLE 时**：MLE 的收敛速度取决于似然函数的曲率。如果似然面是"碗形"（二次型），Newton 几部就搞定；如果很平坦（GARCH 参数退化），梯度下降像蜗牛爬。

---

## 2. 导数与微分

### 方向导数 → 梯度 → 全微分

你写 backprop 时算的是 `∂L/∂w`。但你真正在做的是**全微分**：

```
df = (∂f/∂x₁)dx₁ + (∂f/∂x₂)dx₂ + ... + (∂f/∂xₙ)dxₙ
```

梯度 ∇f 是**使方向导数最大的方向**。梯度下降就是沿着这个方向走一小步。

**关键直觉**：梯度不是"向下的方向"，而是**上升最快的方向**。我们取负号让它变成"最速下降"。

### 雅可比矩阵：backprop 真正的数学形式

**你在框架里用的是自动微分，不是标量链式法则。**

```python
# 标量链式法则你写了无数遍
# dL/dx = dL/dy * dy/dx  ← 这是标量形式

# 但实际 backprop 是雅可比-向量积 (JVP)！
# z = f(y), y = g(x)  其中 x ∈ ℝᵐ, y ∈ ℝⁿ, z ∈ ℝᵏ
# J_f 是 k×n 矩阵, J_g 是 n×m 矩阵
# 链式法则: J_{f∘g}(x) = J_f(g(x)) · J_g(x)

# 反向模式自动微分计算的不是整个 J，而是 Jᵀv（向量-雅可比积 VJP）
# 这才是 backprop 的高效所在！
```

```python
import numpy as np

# 手动验证雅可比链式法则
def jacobian_numerical(f, x, eps=1e-6):
    """数值法计算雅可比矩阵"""
    f0 = f(x)
    J = np.zeros((len(f0), len(x)))
    for i in range(len(x)):
        x_plus = x.copy()
        x_plus[i] += eps
        x_minus = x.copy()
        x_minus[i] -= eps
        J[:, i] = (f(x_plus) - f(x_minus)) / (2 * eps)
    return J

# 一个简单的 MLP 前向传播 (单层)
def linear(x, W, b):
    return W @ x + b

def relu(z):
    return np.maximum(0, z)

# 合成函数: f(x) = ReLU(Wx + b)
x = np.array([1.0, 2.0, 3.0])
W = np.array([[0.5, -0.2, 0.1],
              [0.3, 0.8, -0.4]])
b = np.array([0.1, -0.2])

def f(x):
    return relu(linear(x, W, b))

J_num = jacobian_numerical(f, x)  # 2×3 雅可比
print("Numerical Jacobian:\n", J_num)

# 如果从输出 v 反向传播:
# vᵀ · J  就是参数梯度 🔑
v = np.array([1.0, 0.0])  # 第一个输出的梯度
grad_params = v @ J_num     # 实际 backprop 做的事！
print("Parameter gradient via JVP:", grad_params)
```

**为什么这很重要**？因为你写 `loss.backward()` 时，PyTorch/TF/JAX 计算的不是标量导数，而是**完整雅可比矩阵的向量乘积**。神经网络有百万参数，但你只需要参数梯度——雅可比-向量积提供了线性时间计算，而不是矩阵乘法的平方时间。

### 海森矩阵：Adam 为什么比 SGD 好

```python
# 想象一维损失函数
# SGD 只知道梯度（一阶信息），用固定步长
# 曲率大的地方（海森大），SGD 容易震荡
# 
# Adam 的直观解释:
# - 一阶动量（指数滑动平均）: 平滑梯度方向 → 穿越平坦区域
# - 二阶动量（梯度平方滑动平均）: 自适应调整学习率 → 曲率大处步长小
#
# 二阶动量本质上是对角海森的粗糙估计！
# 真正的海森 H_ij = ∂²L/∂w_i∂w_j 太大（N×N），算不起
# Adam 只跟踪每个参数的对角元素近似：E[g²] ≈ diag(H)
# 然后用 1/√(E[g²]+ε) 作为自适应学习率

# 对比验证
def sgd_step(w, grad, lr=0.01):
    return w - lr * grad

def adam_step(m, v, grad, beta1=0.9, beta2=0.999, lr=0.001, eps=1e-8, t=1):
    m = beta1 * m + (1 - beta1) * grad
    v = beta2 * v + (1 - beta2) * grad**2
    m_hat = m / (1 - beta1**t)
    v_hat = v / (1 - beta2**t)
    return m_hat, v_hat, lr * m_hat / (np.sqrt(v_hat) + eps)

# 在曲率不同的区域对比
w = 0.5
# 高曲率损失面: L(w) = 100*(w-1)²  → 海森 ≈ 200
# 低曲率损失面: L(w) = 0.1*(w-1)²  → 海森 ≈ 0.2
```

**关键点**：SGD 对所有参数用同一个学习率 — 如果你的 loss landscape 在不同方向曲率差异大（条件数大），SGD 会极其低效。Adam 的每个参数有独立学习率，就是这个原因。

---

## 3. 泰勒级数与逼近

### 从泰勒看所有优化算法

一阶泰勒展开 = 梯度下降，二阶泰勒展开 = Newton 法，零阶（只采样）= 随机搜索。

```python
# exp(x) 的泰勒展开：理解 softmax+log 的关键
def taylor_exp(x, n_terms=10):
    """exp(x) ≈ Σ x^k/k!  for k=0 to n_terms"""
    result = 0.0
    term = 1.0  # x^0/0!
    for k in range(n_terms):
        result += term
        term *= x / (k + 1)  # 递推: term_{k+1} = term_k * x/(k+1)
    return result

import numpy as np

x = 1.0
print(f"exp({x}) exact: {np.exp(x):.10f}")
for n in [1, 2, 3, 5, 10]:
    approx = taylor_exp(x, n)
    print(f"  {n}-term approx: {approx:.10f}, error: {np.exp(x)-approx:.2e}")

# 扩展：softmax 为什么用 exp？
# softmax(x_i) = exp(x_i)/Σexp(x_j)
# 指数确保正数 + 泰勒展开的"放大差异"特性
# log softmax = x_i - log(Σexp(x_j)) = x_i - logsumexp(x)
# 完美衔接！
```

### SGD 不收敛到精确最小值 — 截断误差视角

SGD 是**一阶近似 + 随机噪声**。每次只用 batch 估计梯度，不是真梯度：

```
w_{t+1} = w_t - η · g̃_t    其中 g̃_t = ∇L_batch(w_t) ≠ ∇L_full(w_t)
```

泰勒看：我们在找 min L(w)，但只用了梯度近似。方差始终存在 → w_t 会在最小值附近振荡，不会精确收敛。需要 **学习率衰减**（方差缩减）才能收敛。

---

## 4. 积分

### Riemann 积分：你每天都在做

```python
# Riemann 积分: 把函数拍成"一列柱子"，求和
# ∫_a^b f(x)dx ≈ Σ f(x_i*) · Δx

def riemann_integral(f, a, b, n=1000):
    """左 Riemann 和"""
    dx = (b - a) / n
    x = np.linspace(a, b, n, endpoint=False)
    return np.sum(f(x)) * dx

def gaussian_pdf(x, mu=0, sigma=1):
    return 1/(sigma * np.sqrt(2*np.pi)) * np.exp(-0.5*((x-mu)/sigma)**2)

# KL 散度正是积分！
# KL(p||q) = ∫ p(x) * log(p(x)/q(x)) dx
# 连续分布下你需要 Riemann 近似来算这个
# 你写 GARCH MLE 时就在做这个
```

**你写 GARCH MLE 的似然函数是积分**：GARCH 模型的条件似然是 `f(ε_t | σ²_t)`，但边缘似然需要对不可观测的波动率积分——这正是求积分。在标准 GARCH 中我们有封闭形式，但在随机波动率模型中，你**必须**数值积分（或者用 MCMC）。

### 蒙特卡洛积分：为什么随机采样可以

```python
# Monte Carlo 积分: E[f(X)] ≈ (1/N) Σ f(x_i)
# 其中 x_i ~ p(x)
#
# 不需要知道函数形状！只需采样

def monte_carlo_integral(f, sampler, n_samples=100000):
    samples = sampler(n_samples)
    return np.mean(f(samples))

# 算 E[X²] 其中 X ~ N(0,1)
def sampler_normal(n):
    return np.random.randn(n)

mc_est = monte_carlo_integral(lambda x: x**2, sampler_normal)
print(f"Monte Carlo E[X²]: {mc_est:.4f} (exact: 1.0)")

# GARCH MLE 中的数值积分：E[log L(θ|数据)] 就是蒙特卡洛近似
# 当你用 bootstrap 算标准误时，你也在用蒙特卡洛
```

### Lebesgue vs Riemann — "测度"的第一次出现

**Riemann**：把 x 轴切成小段，每段上取 f(x) 值。

**Lebesgue**：把 y 轴切成小段，看"f(x) 在这个值附近"的 x 集合有多大。

```python
# Dirichlet 函数: f(x)=1 if x∈Q, else 0
# Riemann 不可积（无法定义 x 轴的"有理数间距"）
# Lebesgue 可积（有理数集合的"测度" = 0）
#
# 当你学到信息论中的 "几乎处处"、"几乎必然"、"测度 0"
# 根源都在 Lebesgue 积分中对"集合大小"的重新定义
```

**为什么这对你重要**：KL 散度的定义 `KL(p||q) = ∫ p log(p/q) dμ` 中的 `dμ` 就是**测度**。连续分布用 Lebesgue 测度（dx），离散分布用计数测度。一个定义覆盖两种情况，这就是 Lebesgue 视角的优势。

---

## 5. 级数与序列

### RL 折扣回报 = 几何级数

```python
# RL 的折扣回报 G_t = Σ γ^k · r_{t+k+1}, 其中 γ ∈ [0,1)
#
# 等比级数: Σ_{k=0}^∞ γ^k = 1/(1-γ)  ← γ=0.9 → 10, γ=0.99 → 100
#
# 收敛: γ < 1 保证无限 horizon 的回报有限
# 发散: γ = 1 时无限和 → ∞ (除非 episode 终止)

gamma = 0.99
max_horizon = 1 / (1 - gamma)  # ≈ 100
print(f"有效 horizon: {max_horizon:.0f} 步")
# 这就是为什么 γ=0.99 时 agent 规划约 100 步
# γ=0.9 时只考虑约 10 步 — 更"短视"
```

### 幂级数 = 泰勒展开的统一视角

泰勒级数 `Σ f^{(k)}(a)/k! · (x-a)^k` 本质上就是幂级数 `Σ c_k (x-a)^k`。每次做泰勒展开，你都在构造一个幂级数来逼近原函数。

---

## 6. 多元微积分关键

### 梯度场、势函数、旋度

```python
# 梯度场 ∇f 是保守力场: 从 A 到 B 的线积分只与端点有关
# 旋度 ∇×F = 0  ⟹ F 是保守场 ⟹ F = ∇f 对某个 f 成立

# Adam 的动量累积为什么不是纯梯度下降？
# 因为它用了指数滑动平均:
# m_t = β₁·m_{t-1} + (1-β₁)·g_t
# 这相当于引入了"历史路径依赖" → 类似非保守场中的"记忆效应"
# SGD 的每一步沿梯度走，是保守场
# Adam 的动量让路径有了"惯性"，更像是磁场中的运动（非保守）

# 散度 ∇·F 告诉你某点是"源"（发散）还是"汇"（汇聚）
# 梯度下降中，局部最小值附近梯度散度为负（梯度指向内部）
```

### Lagrange 乘子 → KKT

```python
# 优化问题: min f(x)  subject to g(x) = 0
# Lagrange 函数: L(x, λ) = f(x) + λ·g(x)
# 最优条件 ∇L = 0:  
#   ∇f(x) + λ·∇g(x) = 0  ⟺ ∇f = -λ·∇g
#   g(x) = 0
#
# 几何解释: 在约束面上，f 的等值面与约束面"相切"
# 梯度方向平行 ⟺ 存在 λ 使等式成立

# KKT 给不等式约束加了"对偶变量 ≥ 0"的条件
# 你在 SVM 推导中见过: max margin ⟶ 对偶问题
# 你在 GARCH MLE 中: 参数约束 (ω>0, α>0, β>0) 就是不等式约束
```

---

## 7. 与已学内容桥接（完整对照表）

| 你已掌握的 | 底层数学 | 洞见 |
|-----------|---------|------|
| Backprop `dz/dx = dz/dy · dy/dx` | 雅可比-向量积 (JVP) | 标量链式法则是 1×1 雅可比的特殊情况 |
| KL 散度 `∫ p·log(p/q)` | Riemann/Lebesgue 积分 | 连续和离散用同一个积分定义（测度） |
| GARCH MLE 似然函数 | 对数似然的平均 = Riemann 和 | 数值优化等价于积分近似 |
| SGD `w -= lr·∇L` | 一阶泰勒截断: 忽略 ∇²L | 收敛慢是因为丢了曲率信息 |
| Adam `lr / sqrt(E[g²]+ε)` | 对角海森近似 √(H_ii)≈√(E[g²]) | 自适应学习率≈不同轴不同步长 |
| Attention Softmax 梯度 | softmax 雅可比是对称阵 J_ij = s_i(δ_ij - s_j) | 这就是为什么 attention 梯度有"self-competition"效应 |
| RL 折扣回报 `Σγᵗrₜ` | 几何级数和 = 1/(1-γ) | 收敛条件直接定义 horizon |
| 牛顿法 `w -= H⁻¹∇L` | 二阶泰勒展开求驻点 | 二次收敛的代价是 O(N³) 的矩阵求逆 |

---

## 8. 代码示例（完整可运行）

### 数值梯度验证 (中央差分)

```python
import numpy as np
import matplotlib.pyplot as plt

def numerical_gradient(f, x, eps=1e-6):
    """central difference: O(ε²) 精度"""
    grad = np.zeros_like(x)
    for i in range(len(x)):
        x_plus = x.copy(); x_plus[i] += eps
        x_minus = x.copy(); x_minus[i] -= eps
        grad[i] = (f(x_plus) - f(x_minus)) / (2 * eps)
    return grad

# 验证: f(x,y) = x² + 3y² + xy
def f(x):
    return x[0]**2 + 3*x[1]**2 + x[0]*x[1]

def analytical_grad(x):
    return np.array([2*x[0] + x[1], 6*x[1] + x[0]])

x_test = np.array([2.0, 3.0])
num_grad = numerical_gradient(f, x_test)
ana_grad = analytical_grad(x_test)
print(f"Num: {num_grad}")
print(f"Ana: {ana_grad}")
print(f"Error: {np.linalg.norm(num_grad - ana_grad):.2e}")
# 精度 ≈ ε² = 1e-12
```

### 数值积分对比 (Riemann vs Monte Carlo)

```python
def riemann(f, a, b, n=1000):
    dx = (b - a) / n
    xs = np.linspace(a + dx/2, b - dx/2, n)  # 中点法
    return np.sum(f(xs)) * dx

def monte_carlo(f, a, b, n=10000):
    xs = np.random.uniform(a, b, n)
    return (b - a) * np.mean(f(xs))

# ∫₀^π sin(x)dx = 2
exact = 2.0
print(f"Riemann:    {riemann(np.sin, 0, np.pi):.6f} (err: {abs(riemann(np.sin, 0, np.pi)-exact):.2e})")
print(f"Monte Carlo:{monte_carlo(np.sin, 0, np.pi):.6f} (err: {abs(monte_carlo(np.sin, 0, np.pi)-exact):.2e})")
# Riemann 精度 O(1/n²)，Monte Carlo O(1/√n)
# 但 Monte Carlo 在高维不败！维度诅咒对 Riemann 是指数的
```

### 泰勒级数逼近 exp(x) 精度比较

```python
def taylor_exp(x, N):
    """用递推算泰勒展开，避免幂运算"""
    result = 1.0
    term = 1.0
    for k in range(1, N+1):
        term *= x / k
        result += term
    return result

xs = [0.1, 1.0, 5.0, -5.0]
for x in xs:
    exact = np.exp(x)
    for N in [1, 3, 5, 10, 15]:
        approx = taylor_exp(x, N)
        rel_err = abs(approx - exact) / abs(exact)
        print(f"exp({x:4.1f}), N={N:2d}: approx={approx:.6e}, rel_err={rel_err:.2e}")

# 你会看到: 小 x (0.1) → 几项就够
#           大 x (5.0) → 需要很多项
#           负 x (-5.0) → 交替级数收敛慢，数值误差大
# 这就是为什么 numerical stability 在 deep learning 中如此关键！
```

### 雅可比矩阵验证 backprop

```python
def numerical_jacobian(f, x, eps=1e-6):
    """f: ℝᵐ → ℝⁿ, x: ℝᵐ, 返回 n×m 雅可比"""
    f0 = f(x)
    n_out = len(f0)
    n_in = len(x)
    J = np.zeros((n_out, n_in))
    for i in range(n_in):
        dx = np.zeros(n_in)
        dx[i] = eps
        J[:, i] = (f(x + dx) - f(x - dx)) / (2 * eps)
    return J

# 构建一个简单网络: z = W@x + b, y = σ(z), loss = 0.5*(y-t)²
np.random.seed(42)
x = np.random.randn(3)
W = np.random.randn(2, 3)
b = np.random.randn(2)
t = np.array([1.0, 0.0])

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

def network(x):
    z = W @ x + b
    y = sigmoid(z)
    return y

def loss(x):
    y = network(x)
    return np.array([0.5 * np.sum((y - t)**2)])  # 标量输出

J_num = numerical_jacobian(loss, x)
print("Numerical Jacobian (1×3):\n", J_num)

# 用标量链式法验证: dL/dx = (dL/dy)·(dy/dz)·(dz/dx)
y = network(x)
dL_dy = y - t  # d/dy [0.5*(y-t)²]
dy_dz = y * (1 - y)  # sigmoid 导数
dz_dx = W  # dz/dx = W

# 手动链式
dL_dx_manual = dL_dy.T @ (dy_dz[:, None] * W)  # 等价于雅可比-向量积！
print("Manual chain rule:\n", dL_dx_manual.reshape(1, -1))
print("Match?", np.allclose(J_num.flatten(), dL_dx_manual.flatten()))
```

---

## 总结：下一步是什么？

这节课建立了微积分的**视角**，下节课我们会用这个视角去理解**概率论与信息论**：KL 散度为什么是"距离"但不是度量、Fisher 信息为什么是海森矩阵的变体、为什么最大似然估计等价于最小化 KL 散度。

**核心心法**：不要把数学看作"需要证明的定理"，而是看作"你在代码中已经使用的直觉的形式化"。每次写 `loss.backward()`，你都在执行雅可比-向量积；每次算 `np.mean(log_likelihood)`，你都在做 Monte Carlo 积分；每次用 Adam，你都在用一个对角化的近似海森矩阵。

你已经是微积分的使用者——现在是时候成为理解者了。
