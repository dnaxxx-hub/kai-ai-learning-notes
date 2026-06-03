# 量子比特

## 1. 概述

量子比特（qubit）是量子信息的基本单位。与经典比特（0 或 1）不同，量子比特可以处于 $|0\rangle$ 和 $|1\rangle$ 的叠加态，还具有纠缠和测量坍缩等独特性质。

量子比特的物理实现多种多样：光子偏振、电子自旋、超导电路中的能级、离子阱中的能级等。

---

## 2. 量子态与狄拉克符号

### 2.1 狄拉克符号

量子力学中广泛使用狄拉克符号（bra-ket notation）：

- **右矢** $|\psi\rangle$：表示量子态
- **左矢** $\langle\psi|$：右矢的共轭转置
- **内积** $\langle\phi|\psi\rangle$：两个态的重叠程度
- **外积** $|\phi\rangle\langle\psi|$：投影算符

### 2.2 量子比特的基本态

一个量子比特在二维复希尔伯特空间 $\mathbb{C}^2$ 中：

$$|\psi\rangle = \alpha|0\rangle + \beta|1\rangle$$

其中 $\alpha, \beta \in \mathbb{C}$，且满足归一化条件：

$$|\alpha|^2 + |\beta|^2 = 1$$

基矢的矩阵表示：

$$|0\rangle = \begin{bmatrix} 1 \\ 0 \end{bmatrix}, \quad |1\rangle = \begin{bmatrix} 0 \\ 1 \end{bmatrix}$$

---

## 3. 布洛赫球

单位向量 $|\psi\rangle$ 可以用布洛赫球直观表示。

### 3.1 参数化

$$|\psi\rangle = \cos\frac{\theta}{2}|0\rangle + e^{i\phi}\sin\frac{\theta}{2}|1\rangle$$

其中 $\theta \in [0, \pi]$，$\phi \in [0, 2\pi)$。

### 3.2 布洛赫球图示

```
                    |0⟩ (z↑)
                      ▲
                      │
                      │
                      │   ● (量子态)
                      │  /|
                      │ /θ│
                      │/  │
          ────────────●───●───────→ 实轴 (x)
                     /│   │
                    / │   │
                   /  │   │
                  /   │   │
                 ●    │   │
              y(虚轴)  │   │
                      │   │
                      │   │
                      ▼   │
                    |1⟩ (z↓)
```

布洛赫球上的点 $(x, y, z)$ 与密度矩阵的关系：

$$\rho = \frac{1}{2}(I + xX + yY + zZ)$$

其中 $X, Y, Z$ 为泡利矩阵。

### 3.3 布洛赫球上的重要态

| 态 | $\theta$ | $\phi$ | 布洛赫向量 | 对应 |
|----|----------|--------|------------|------|
| $|0\rangle$ | 0 | — | $(0,0,1)$ | 北极 |
| $|1\rangle$ | $\pi$ | — | $(0,0,-1)$ | 南极 |
| $|+\rangle$ | $\pi/2$ | 0 | $(1,0,0)$ | X+ |
| $|-\rangle$ | $\pi/2$ | $\pi$ | $(-1,0,0)$ | X- |
| $|+i\rangle$ | $\pi/2$ | $\pi/2$ | $(0,1,0)$ | Y+ |
| $|-i\rangle$ | $\pi/2$ | $3\pi/2$ | $(0,-1,0)$ | Y- |

---

## 4. 量子测量

### 4.1 投影测量

测量一个量子比特时，结果以概率方式出现：

$$P(0) = |\langle 0|\psi\rangle|^2 = |\alpha|^2$$
$$P(1) = |\langle 1|\psi\rangle|^2 = |\beta|^2$$

测量后，态坍缩到对应的本征态。

### 4.2 测量基

可以在任意方向上进行测量：

- **Z 基** $\{|0\rangle, |1\rangle\}$ — 标准基
- **X 基** $\{|+\rangle, |-\rangle\}$ — 对角基
- **Y 基** $\{|+i\rangle, |-i\rangle\}$ — 圆基

### 4.3 Python 模拟量子测量

```python
import numpy as np

# 量子态
alpha = 1/np.sqrt(2)  # 复数振幅
beta = 1/np.sqrt(2)

# 归一化确认
norm = np.abs(alpha)**2 + np.abs(beta)**2
assert abs(norm - 1.0) < 1e-10, f"状态未归一化: {norm}"

# 单次测量模拟
def measure_qubit(psi, n_shots=1000):
    """测量量子比特 n_shots 次，返回统计结果"""
    alpha, beta = psi[0], psi[1]
    p0 = np.abs(alpha)**2
    p1 = np.abs(beta)**2
    
    outcomes = np.random.choice(['0', '1'], size=n_shots, p=[p0, p1])
    count_0 = np.sum(outcomes == '0')
    count_1 = np.sum(outcomes == '1')
    
    return {'0': count_0, '1': count_1,
            'P(0)': count_0/n_shots, 'P(1)': count_1/n_shots}

# 在 Z 基下测量 |+⟩ = (|0⟩ + |1⟩)/√2
psi_plus = np.array([1/np.sqrt(2), 1/np.sqrt(2)])
result = measure_qubit(psi_plus, n_shots=10000)
print(f"测量 |+⟩ 态: {result}")
# 输出: {'0': 5003, '1': 4997, 'P(0)': 0.5003, 'P(1)': 0.4997}
# 各占50%
```

---

## 5. 纠缠与 Bell 态

### 5.1 什么是纠缠

如果两个量子比特的联合态不能写成各自态的直积：

$$|\psi\rangle_{AB} \neq |\phi\rangle_A \otimes |\chi\rangle_B$$

则称为**纠缠态**。纠缠态是量子计算的核心资源。

### 5.2 Bell 态（EPR 对）

四个 Bell 态构成了两量子比特的最大纠缠态：

$$|\Phi^+\rangle = \frac{1}{\sqrt{2}}(|00\rangle + |11\rangle)$$
$$|\Phi^-\rangle = \frac{1}{\sqrt{2}}(|00\rangle - |11\rangle)$$
$$|\Psi^+\rangle = \frac{1}{\sqrt{2}}(|01\rangle + |10\rangle)$$
$$|\Psi^-\rangle = \frac{1}{\sqrt{2}}(|01\rangle - |10\rangle)$$

### 5.3 纠缠的特性

对 Bell 态 $|\Phi^+\rangle$ 测量其中一个比特：

$$
\begin{aligned}
\text{测量 A→0} &\Rightarrow |\Phi^+\rangle \to |00\rangle \;(\text{概率 } \frac{1}{2}) \\
\text{测量 A→1} &\Rightarrow |\Phi^+\rangle \to |11\rangle \;(\text{概率 } \frac{1}{2})
\end{aligned}
$$

无论距离多远，A 和 B 的测量结果总是**完全相关**。

### 5.4 创建 Bell 态

```
|0⟩ ──────── H ───── ● ────────
                      │
|0⟩ ───────────────── ⊕ ────────

H = Hadamard门，●─⊕ = CNOT门
```

```python
def create_bell_state():
    """创建 Bell 态 |Φ⁺⟩"""
    # 初始态 |00⟩
    psi = np.zeros(4)
    psi[0] = 1  # |00⟩
    
    # 应用 Hadamard 门到第一个 qubit
    H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    I = np.eye(2)
    H_I = np.kron(H, I)
    psi = H_I @ psi
    
    # 应用 CNOT 门
    CNOT = np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0]
    ])
    psi = CNOT @ psi
    
    return psi  # |Φ⁺⟩ = (|00⟩ + |11⟩)/√2

psi_bell = create_bell_state()
print(f"Bell 态: {psi_bell}")
# [0.707, 0, 0, 0.707]  →  (|00⟩ + |11⟩)/√2
```

---

## 6. 密度矩阵

### 6.1 纯态 vs 混态

- **纯态**：可以用单一态向量描述的量子态
- **混态**：经典概率混合的量子态（无法用单一态向量描述）

```python
# 纯态 |+⟩
psi_plus = np.array([1, 1]) / np.sqrt(2)
rho_pure = np.outer(psi_plus, psi_plus.conj())
print(rho_pure)
# [[0.5, 0.5],
#  [0.5, 0.5]]

# 混态（等概率混合 |0⟩ 和 |1⟩）
rho_mixed = 0.5 * np.outer([1,0], [1,0]) + 0.5 * np.outer([0,1], [0,1])
print(rho_mixed)
# [[0.5, 0  ],
#  [0  , 0.5]]
```

### 6.2 密度矩阵的性质

$$\rho = \sum_i p_i |\psi_i\rangle\langle\psi_i|$$

- **迹**：$\text{Tr}(\rho) = 1$
- **半正定**：$\rho \geq 0$
- **纯态判据**：$\text{Tr}(\rho^2) = 1$（纯态），$< 1$（混态）

```python
def is_pure_state(rho):
    """判断是否为纯态"""
    purity = np.trace(rho @ rho).real
    return abs(purity - 1.0) < 1e-10

print(is_pure_state(rho_pure))   # True
print(is_pure_state(rho_mixed))  # False
print(f"纯度: {np.trace(rho_pure @ rho_pure):.3f}")    # 1.0
print(f"纯度: {np.trace(rho_mixed @ rho_mixed):.3f}")  # 0.5
```

### 6.3 约化密度矩阵

对纠缠态的部分求迹：

```python
# Bell 态 |Φ⁺⟩
psi_bell = np.array([1, 0, 0, 1]) / np.sqrt(2)
rho_bell = np.outer(psi_bell, psi_bell)
print(f"Bell态密度矩阵:\n{rho_bell}")

# 对 B 求迹，得到 A 的约化密度矩阵
rho_A = np.zeros((2, 2), dtype=complex)
for i in range(2):
    for j in range(2):
        # 对 |ij⟩⟨kl| 中 j=l 的部分求和
        rho_A[i, j] = rho_bell[i*2:i*2+1, j*2:j*2+1].sum()
print(f"A的约化密度矩阵:\n{rho_A}")
# [[0.5, 0 ],   → 混态！
#  [0,   0.5]]
```

单看子系统 A，它是完全混态——**纠缠意味着每个子系统的信息是不完全的**。

---

## 7. 量子态的可视化

### 7.1 使用 Qiskit 可视化

```python
from qiskit import QuantumCircuit
from qiskit.visualization import plot_bloch_multivector, plot_histogram
import numpy as np

# 创建叠加态
qc = QuantumCircuit(1)
qc.h(0)                    # |0⟩ → |+⟩
qc.s(0)                    # 添加相位 → |+i⟩

# 获取态向量
from qiskit.quantum_info import Statevector
state = Statevector.from_instruction(qc)
```

### 7.2 参数空间可视化

```python
import matplotlib.pyplot as plt
import numpy as np

def plot_bloch_vectors(states, labels):
    """绘制布洛赫球上的多个态"""
    # 3D 球体投影（x-z 平面）
    theta = np.linspace(0, 2*np.pi, 100)
    circle_x = np.cos(theta)
    circle_z = np.sin(theta)
    
    plt.figure(figsize=(8, 8))
    plt.plot(circle_x, circle_z, 'gray', alpha=0.5)  # 圆
    plt.axhline(0, color='gray', alpha=0.3)
    plt.axvline(0, color='gray', alpha=0.3)
    
    colors = ['red', 'blue', 'green', 'purple']
    for i, (s, label) in enumerate(zip(states, labels)):
        # s = (theta, phi)
        t, p = s
        x = np.sin(t) * np.cos(p)
        z = np.cos(t)
        plt.scatter(x, z, c=colors[i], s=100, label=label)
        plt.annotate(label, (x, z), xytext=(5, 5),
                    textcoords='offset points')
    
    plt.xlim(-1.2, 1.2)
    plt.ylim(-1.2, 1.2)
    plt.axhline(0, color='k', lw=0.5)
    plt.axvline(0, color='k', lw=0.5)
    plt.xlabel('x')
    plt.ylabel('z')
    plt.title('布洛赫球投影 (x-z平面)')
    plt.axis('equal')
    plt.grid(alpha=0.3)
    plt.show()

# |0⟩, |1⟩, |+⟩, |+i⟩ 在 x-z 平面
states = [(0, 0), (np.pi, 0), (np.pi/2, 0), (np.pi/2, np.pi/2)]
labels = ['|0⟩', '|1⟩', '|+⟩', '|+i⟩']
plot_bloch_vectors(states, labels)
```

---

## 8. 物理实现对比

| 物理系统 | 相干时间 | 门保真度 | 可扩展性 | 优势 |
|----------|----------|----------|----------|------|
| 超导电路 | 10-100μs | 99.9%+ | ★★★★ | 门速度快，集成度高 |
| 离子阱 | 数秒 | 99.99%+ | ★★★ | 保真度最高 |
| 光量子 | 毫秒级 | 99%+ | ★★ | 室温操作 |
| NV色心 | 毫秒级 | 99%+ | ★★ | 室温，固态 |
| 拓扑量子 | 理论较长 | 受保护 | 待验证 | 天然容错 |

---

## 总结

| 概念 | 关键点 |
|------|--------|
| 量子比特 | 二维复向量 $\alpha|0\rangle + \beta|1\rangle$，$|\alpha|^2 + |\beta|^2 = 1$ |
| 布洛赫球 | 所有单量子比特纯态的一一对应 |
| 测量 | 概率坍缩，$P(0) = |\alpha|^2$ |
| 纠缠 | 不可分解的联合态，非局域关联 |
| Bell态 | 最大纠缠态，量子通信的基础 |
| 密度矩阵 | 描述混态，$\text{Tr}(\rho^2) \leq 1$ |
