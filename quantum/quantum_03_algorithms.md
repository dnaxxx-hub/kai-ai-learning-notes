# 量子算法

## 1. 概述

量子算法利用量子叠加和纠缠特性，在某些问题上实现了超越经典算法的加速。本章介绍最重要的几个量子算法，从概念到实现全面覆盖。

**量子加速分类：**

| 加速类型 | 示例 | 加速比 |
|----------|------|--------|
| 指数级加速 | Shor 因式分解 | $O(e^{n^{1/3}}) \to O(n^3)$ |
| 平方根加速 | Grover 搜索 | $O(N) \to O(\sqrt{N})$ |
| 多项式加速 | 量子模拟 | 各问题不同 |

---

## 2. Deutsch-Jozsa 算法

### 2.1 问题

判断一个布尔函数 $f: \{0,1\}^n \to \{0,1\}$ 是**常函数**（所有输出相同）还是**平衡函数**（一半输出 0 一半输出 1）。

经典算法：最坏情况需要 $2^{n-1}+1$ 次查询。
量子算法：**1 次查询**！

### 2.2 算法流程

```
            ┌───┐                     ┌───┐
|0⟩^n: ────┤ H ├──●───────────────────┤ H ├──●── 测量
           └───┘  │                  └───┘  │
                  │          Oracle         │
|1⟩: ──── X ── H ──⊕───────────────────────⊕────

Oracle U_f 作用: |x⟩|y⟩ → |x⟩|y ⊕ f(x)⟩
```

### 2.3 原理

1. 将 $n+1$ 个量子比特初始化为 $|0\rangle^{\otimes n}|1\rangle$
2. 对所有量子比特应用 Hadamard 门
3. 应用 Oracle $U_f$
4. 对 $n$ 个量子比特应用 Hadamard 门
5. 测量：全部为 $|0\rangle$ → 常函数，否则 → 平衡函数

### 2.4 实现

```python
import numpy as np

def deutsch_jozsa(f, n=2):
    """
    Deutsch-Jozsa 算法
    f: 布尔函数，输入整数 0..2^n-1，输出 0 或 1
    """
    N = 2**n
    state = np.zeros(N * 2, dtype=complex)
    state[0] = 1 / np.sqrt(2)     # |0...0⟩ ⊗ (|0⟩ - |1⟩)/√2
    state[N] = -1 / np.sqrt(2)
    
    # 这实际上用了相位反冲技巧
    # 简化模拟：直接应用 H⊗n ⊕ phase
    phase = np.array([(-1)**f(x) for x in range(N)])
    state[:N] *= phase
    
    # 应用 H⊗n（在 n-qubit 部分）
    H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    H_n = H
    for _ in range(n - 1):
        H_n = np.kron(H_n, H)
    
    # 只作用于前 N 个振幅
    amplitude = state[:N]
    amplitude = H_n @ amplitude
    state[:N] = amplitude
    
    # 测量前 n 个 qubit
    probs = np.abs(state[:N])**2
    result = np.random.choice(range(N), p=probs / probs.sum())
    
    if result == 0:
        return "constant"  # 常函数
    else:
        return "balanced"  # 平衡函数

# 测试
def constant_zero(x):
    return 0

def balanced_parity(x):
    return bin(x & 1).count('1') % 2

for _ in range(10):
    r1 = deutsch_jozsa(constant_zero, n=3)
    r2 = deutsch_jozsa(balanced_parity, n=3)
    assert r1 == "constant"
    assert r2 == "balanced"
print("Deutsch-Jozsa 测试通过 ✅")
```

---

## 3. Grover 搜索算法

### 3.1 问题

在无序数据库 $N$ 个元素中找到标记元素。经典算法需要 $O(N)$ 次查询，Grover 算法仅需 $O(\sqrt{N})$ 次。

### 3.2 核心思想

Grover 算法通过**振幅放缩**（amplitude amplification）增大目标态的概率振幅：

```
初始状态:     每个状态的振幅 ≈ 1/√N

Oracle后:     目标态振幅反号
              ┌─────────────────────┐
振幅:  ████ ████████ ████ ████ ████
                    ↓ (-1倍)
      ████ ████████ ████ ████ ████
                    ↑ (反色)
扩散后:       所有振幅围绕平均值翻转
              → 目标态振幅增大
```

### 3.3 算法流程

```
1. 准备均匀叠加态: |s⟩ = H⊗n|0⟩
2. 重复 O(√N) 次:
   a. Oracle: U_f|x⟩ = (-1)^{f(x)}|x⟩
   b. 扩散算子: U_s = 2|s⟩⟨s| - I
3. 测量
```

### 3.4 可视化

```
振幅演化（N=16, 4 qubits）:

迭代 0:  ■■■■■■■■■■■■■■■■  (所有振幅=0.25)
         ↓                  目标态反号
迭代 1:  ■■■■■■■■■■■■■■▼■  (目标态=-0.25)
         ↓                  扩散
迭代 1后: ■■■■■■■■■■■■■■■   (目标态≈0.47)
         ↓
迭代 2:  ■■■■■■■■▼■■■■■■■  (目标态≈0.66)
         ↓
迭代 3:  ■■■■■■■■■■■■■■■■  (目标态≈0.83)

最佳迭代次数 ≈ ⌊π√N/4⌋ = ~3次 (N=16)
```

### 3.5 实现

```python
import numpy as np
import math

def grover_search(n_qubits, marked_item):
    """
    Grover 搜索算法
    marked_item: 标记元素的索引
    """
    N = 2**n_qubits
    state = np.ones(N, dtype=complex) / np.sqrt(N)  # 均匀叠加
    
    # Hadamard 算子
    H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    H_n = H
    for _ in range(n_qubits - 1):
        H_n = np.kron(H_n, H)
    
    # Oracle
    def oracle(state, target):
        state[target] *= -1
        return state
    
    # 扩散算子 = H⊗n (2|0⟩⟨0| - I) H⊗n
    def diffusion(state):
        state[:] = 2 * np.mean(state) - state
        return state
    
    # 迭代次数
    n_iter = int(np.pi * np.sqrt(N) / 4)
    
    for _ in range(n_iter):
        # Oracle
        state = oracle(state, marked_item)
        # 扩散
        state = diffusion(state)
    
    # 测量
    probs = np.abs(state)**2
    result = np.random.choice(range(N), p=probs)
    return result, probs

# 测试
n = 5  # N=32
marked = 23
result, probs = grover_search(n, marked)
print(f"标记元素: {marked}, 搜索结果: {result}")
print(f"目标态概率: {probs[marked]:.3f} (> 1/{2**n} = {1/2**n:.3f})")
# 目标态概率远高于平均
```

---

## 4. 量子傅里叶变换

### 4.1 定义

QFT 是离散傅里叶变换的量子版本：

$$QFT|j\rangle = \frac{1}{\sqrt{N}}\sum_{k=0}^{N-1} e^{2\pi i jk/N}|k\rangle$$

### 4.2 线路

```
QFT 线路（3 qubits）：

|j₁⟩ ── H ── R₂ ── R₃ ────●──────────────────────
                           │
|j₂⟩ ────────────● ── H ── ⊕ ── R₂ ─────────────●
                  │                   │
|j₃⟩ ──────────────────────● ──────────● ── H ──⊕

          交换输出顺序
```

其中 $R_k = \begin{bmatrix} 1 & 0 \\ 0 & e^{2\pi i/2^k} \end{bmatrix}$

### 4.3 实现

```python
def qft(state):
    """量子傅里叶变换（状态向量模拟）"""
    n = int(np.log2(len(state)))
    N = len(state)
    result = np.zeros(N, dtype=complex)
    
    for k in range(N):
        for j in range(N):
            result[k] += state[j] * np.exp(2j * np.pi * j * k / N)
    
    return result / np.sqrt(N)

def inverse_qft(state):
    """逆量子傅里叶变换"""
    n = int(np.log2(len(state)))
    N = len(state)
    result = np.zeros(N, dtype=complex)
    
    for j in range(N):
        for k in range(N):
            result[j] += state[k] * np.exp(-2j * np.pi * j * k / N)
    
    return result / np.sqrt(N)

# 测试
test_state = np.zeros(8)
test_state[3] = 1  # |011⟩
transformed = qft(test_state)
recovered = inverse_qft(transformed)
print(f"原始: {np.argmax(np.abs(test_state))}")
print(f"恢复: {np.argmax(np.abs(recovered))}")
```

---

## 5. Shor 因式分解算法

### 5.1 问题

找到整数 $N$ 的非平凡因子。经典算法（数域筛法）复杂度 $O(\exp(c (\log N)^{1/3}(\log\log N)^{2/3}))$，Shor 算法多项式时间 $O((\log N)^3)$。

### 5.2 核心原理

Shor 算法将因式分解归约为**周期查找问题**：

1. 随机选择 $a < N$
2. 计算 $f(x) = a^x \mod N$
3. 找出 $a^x \mod N$ 的周期 $r$
4. 如果 $r$ 为偶数，则 $\gcd(a^{r/2} \pm 1, N)$ 是因子

**周期查找使用 QFT 实现指数级加速！**

### 5.3 量子部分

```
|0⟩ ── H ── ──── QFT† ── 测量
           │
|0⟩ ── H ── a^x mod N ── QFT† ── 测量
           │        │
|1⟩ ── ───── ──────────┼──────
                       │
量子寄存器 1: 存储 x
量子寄存器 2: 存储 f(x)
```

### 5.4 实现

```python
import math
import random
from fractions import Fraction

def shor_factor(N):
    """Shor 因式分解算法（经典部分 + 量子模拟）"""
    if N % 2 == 0:
        return 2, N // 2
    
    # 检查 N 是否为质数幂
    for a in range(2, int(math.log2(N)) + 1):
        b = int(N ** (1/a))
        if b**a == N:
            return b, N // b
    
    while True:
        # 随机选择 a
        a = random.randint(2, N - 2)
        if math.gcd(a, N) > 1:
            return math.gcd(a, N), N // math.gcd(a, N)
        
        # 量子部分：计算 f(x) = a^x mod N 的周期
        # 这里模拟量子计算的结果
        r = quantum_period_finding(a, N)
        
        if r is None or r % 2 != 0:
            continue
        
        # 检查因子
        c1 = a**(r//2) % N
        if c1 == N - 1 or c1 == 1:
            continue
        
        p = math.gcd(c1 - 1, N)
        if p > 1 and p < N:
            return p, N // p

def quantum_period_finding(a, N):
    """模拟量子周期查找（QFT 部分）"""
    # 实践中使用 QFT，这里简化模拟
    x = 1
    for r in range(1, N * 2):
        x = (x * a) % N
        if x == 1:
            return r
    return None

# 测试
# N = 15 → 3 × 5
N = 15
p, q = shor_factor(N)
print(f"{N} = {p} × {q}, 正确: {p*q == N}")
```

---

## 6. 量子相位估计（QPE）

### 6.1 问题

给定酉算子 $U$ 和其特征向量 $|\psi\rangle$，满足 $U|\psi\rangle = e^{2\pi i\theta}|\psi\rangle$，估计 $\theta$。

QPE 是许多量子算法的核心子程序（Shor、HHL、量子化学模拟等）。

### 6.2 线路

```
|0⟩ ── H ── ● ── ● ── ── ──── QFT† ── 测量 (高位)
             │    │     │
|0⟩ ── H ── │ ── ⊕ ── ── ──── QFT† ── 测量
             │    │     │
|0⟩ ── H ── │ ── │ ── ⊕─── QFT† ── 测量
             │    │     │
|ψ⟩ ──────── U─── U²─── U⁴────────────
```

### 6.3 实现

```python
def quantum_phase_estimation(U, eigenvector, n_control=4):
    """
    量子相位估计
    U: 酉算子函数 U(k, state)
    eigenvector: 特征向量
    n_control: 控制量子比特数
    """
    N = len(eigenvector)
    dim = 2**n_control * N
    state = np.zeros(dim, dtype=complex)
    
    # 初始化控制 qubit 为均匀叠加
    for i in range(2**n_control):
        state[i * N : (i+1) * N] = eigenvector / np.sqrt(2**n_control)
    
    # 应用控制 U^(2^k)
    for k in range(n_control):
        for i in range(2**n_control):
            if i & (1 << k):  # 如果第 k 位为 1
                idx = i * N
                target = state[idx:idx+N]
                state[idx:idx+N] = U(2**k, target)
    
    # QFT† 作用于控制寄存器
    for k, vec in enumerate(range(0, dim, N)):
        # 简化：对每个控制状态的振幅应用逆 QFT
        ...
    
    # 测量控制寄存器
    control_state = np.zeros(2**n_control, dtype=complex)
    for i in range(2**n_control):
        control_state[i] = np.linalg.norm(state[i*N:(i+1)*N])
    
    probs = np.abs(control_state)**2
    measured = np.random.choice(range(2**n_control), p=probs/probs.sum())
    
    theta = measured / (2**n_control)
    return theta

# 测试：估计 T 门的相位
# T|1⟩ = e^{iπ/4}|1⟩ → θ = π/8
T = np.array([[1, 0], [0, np.exp(1j * np.pi / 4)]])
eigenvector = np.array([0, 1])  # |1⟩
theta = quantum_phase_estimation(lambda k, v: np.linalg.matrix_power(T, k) @ v, eigenvector)
print(f"估计相位: {theta:.4f} × 2π, 实际: {1/8:.4f} × 2π")
```

---

## 7. 算法复杂度对比

| 算法 | 经典复杂度 | 量子复杂度 | 加速比 |
|------|-----------|-----------|--------|
| 因式分解 | $O(e^{n^{1/3}})$ | $O(n^3)$ | 指数级 |
| 无序搜索 | $O(N)$ | $O(\sqrt{N})$ | 平方根 |
| 函数平衡性 | $O(N)$ | $O(1)$ | 指数级 |
| 模拟量子系统 | $O(2^n)$ | $O(n)$ | 指数级 |
| 线性方程组(HHL) | $O(N)$ | $O(\log N)$ | 指数级 |

### 当前量子算法生态

```
                    ┌──────────────────┐
                    │    Shor (因数分解)  │
                    │    Grover (搜索)    │
                    │    Deutsch-Jozsa   │
                    │    QPE (相位估计)   │
                    └────────┬─────────┘
                             │
             ┌───────────────┼───────────────┐
             │               │               │
        ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
        │ 量子化学 │    │ 量子优化 │    │ 机器学习 │
        │ VQE     │    │ QAOA    │    │ QSVM    │
        │ HHL     │    │ QUBO    │    │ QNN     │
        └─────────┘    └─────────┘    └─────────┘
```

---

## 总结

| 算法 | 核心技巧 | 关键创新 | 实用化程度 |
|------|----------|----------|-----------|
| Deutsch-Jozsa | 相位反冲 | 证明量子优势 | 教学意义 |
| Grover | 振幅放大 | $\sqrt{N}$ 加速 | 实用（需容错） |
| Shor | QFT+周期查找 | 指数级加速 | RSA威胁（需大规模） |
| QFT | 量子并行 | 傅里叶变换 | 算法基础 |
| QPE | 控制酉+QFT | 特征值估计 | 算法基础 |

**核心洞见：** 量子算法的强大来自于利用量子干涉（通过 QFT/振幅放大）来聚合有用信息、抵消无用信息。所有指数级加速的量子算法某种意义上都是 QFT 的应用。
