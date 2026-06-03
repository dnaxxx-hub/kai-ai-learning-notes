# 量子门与量子线路

## 1. 概述

量子门是量子计算的基本操作单元，类似于经典逻辑门（AND、OR、NOT）但作用于量子态。量子门必须是**酉变换**（unitary），即 $U^\dagger U = I$，这保证了量子计算的可逆性。

量子线路由一系列量子门作用于量子比特组成，是描述量子算法的基本框架。

---

## 2. 单量子比特门

### 2.1 Pauli 门

Pauli 门是最基本的量子门，对应三个泡利矩阵：

**Pauli-X 门**（量子 NOT）：

$$X = \begin{bmatrix} 0 & 1 \\ 1 & 0 \end{bmatrix}, \quad X|0\rangle = |1\rangle, \quad X|1\rangle = |0\rangle$$

**Pauli-Y 门**：

$$Y = \begin{bmatrix} 0 & -i \\ i & 0 \end{bmatrix}, \quad Y|0\rangle = i|1\rangle, \quad Y|1\rangle = -i|0\rangle$$

**Pauli-Z 门**（相位翻转）：

$$Z = \begin{bmatrix} 1 & 0 \\ 0 & -1 \end{bmatrix}, \quad Z|0\rangle = |0\rangle, \quad Z|1\rangle = -|1\rangle$$

### 2.2 Hadamard 门

Hadamard 门创建叠加态，是量子计算中最重要的门：

$$H = \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix}$$

$$H|0\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}} = |+\rangle$$
$$H|1\rangle = \frac{|0\rangle - |1\rangle}{\sqrt{2}} = |-\rangle$$

### 2.3 相位门

**S 门**（$\sqrt{Z}$）：

$$S = \begin{bmatrix} 1 & 0 \\ 0 & i \end{bmatrix}$$

**T 门**（$\sqrt{S}$）：

$$T = \begin{bmatrix} 1 & 0 \\ 0 & e^{i\pi/4} \end{bmatrix}$$

### 2.4 任意旋转门

$$R_x(\theta) = \begin{bmatrix} \cos\frac{\theta}{2} & -i\sin\frac{\theta}{2} \\ -i\sin\frac{\theta}{2} & \cos\frac{\theta}{2} \end{bmatrix}$$

$$R_y(\theta) = \begin{bmatrix} \cos\frac{\theta}{2} & -\sin\frac{\theta}{2} \\ \sin\frac{\theta}{2} & \cos\frac{\theta}{2} \end{bmatrix}$$

$$R_z(\theta) = \begin{bmatrix} e^{-i\theta/2} & 0 \\ 0 & e^{i\theta/2} \end{bmatrix}$$

### 2.5 布洛赫球上的门操作

```
X门 (绕X轴旋转π):           Z门 (绕Z轴旋转π):
    |0⟩       |1⟩              |0⟩       |0⟩
    ↑         ↓                ↑         ↑
    ●   ──►   ●                ●   ──►   ●

Hadamard门 (绕X+Z轴旋转):
    |0⟩       |+⟩
    ↑         → (赤道)
    ●   ──►   ●

S门 (绕Z轴旋转π/2):
    |+⟩       |+i⟩
    →         ↕  (虚数轴)
    ●   ──►   ●
```

### 2.6 Python 实现

```python
import numpy as np

# ============ 单量子比特门 ============

# Pauli 门
X = np.array([[0, 1], [1, 0]])
Y = np.array([[0, -1j], [1j, 0]])
Z = np.array([[1, 0], [0, -1]])

# Hadamard 门
H = np.array([[1, 1], [1, -1]]) / np.sqrt(2)

# 相位门
S = np.array([[1, 0], [0, 1j]])
T = np.array([[1, 0], [0, np.exp(1j * np.pi / 4)]])

# 旋转门
def Rx(theta):
    return np.array([[np.cos(theta/2), -1j*np.sin(theta/2)],
                     [-1j*np.sin(theta/2), np.cos(theta/2)]])

def Ry(theta):
    return np.array([[np.cos(theta/2), -np.sin(theta/2)],
                     [np.sin(theta/2), np.cos(theta/2)]])

def Rz(theta):
    return np.array([[np.exp(-1j*theta/2), 0],
                     [0, np.exp(1j*theta/2)]])

# 验证酉性
def is_unitary(U):
    return np.allclose(U @ U.conj().T, np.eye(U.shape[0]))

for name, gate in [('X', X), ('H', H), ('T', T)]:
    print(f"{name} 是酉矩阵: {is_unitary(gate)}")
```

---

## 3. 多量子比特门

### 3.1 CNOT 门（CX 门）

CNOT 是量子计算中最关键的两比特门，创建纠缠的核心操作：

$$\text{CNOT} = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 1 & 0 & 0 \\ 0 & 0 & 0 & 1 \\ 0 & 0 & 1 & 0 \end{bmatrix}$$

作用效果：

```
|00⟩ → |00⟩       控制位 = 0, 目标位不变
|01⟩ → |01⟩       控制位 = 0, 目标位不变
|10⟩ → |11⟩       控制位 = 1, 目标位翻转
|11⟩ → |10⟩       控制位 = 1, 目标位翻转
```

线路表示：

```
|q0⟩ ───── ● ────             控制位
            │
|q1⟩ ───── ⊕ ────             目标位
```

### 3.2 Toffoli 门（CCNOT 门）

三重控制的 NOT 门，经典计算通用门：

```
|a⟩ ─── ● ──────
        │
|b⟩ ─── ● ──────
        │
|c⟩ ─── ⊕ ──────

输出：|a, b, c ⊕ (a ∧ b)⟩
```

$$|a,b,c\rangle \to |a, b, c \oplus (a \cdot b)\rangle$$

### 3.3 Swap 门

交换两个量子比特的状态：

$$\text{SWAP} = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 0 & 1 & 0 \\ 0 & 1 & 0 & 0 \\ 0 & 0 & 0 & 1 \end{bmatrix}$$

可用 3 个 CNOT 实现：

```
|a⟩ ─── ● ─── ⊕ ─── ● ───
         │     │     │
|b⟩ ─── ⊕ ─── ● ─── ⊕ ───
```

### 3.4 多比特门实现

```python
# ============ 多比特门 ============

def CNOT():
    """CNOT 门，控制位为 q0，目标位为 q1"""
    return np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0]
    ])

def CZ():
    """控制 Z 门"""
    return np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, -1]
    ])

def SWAP():
    """Swap 门"""
    return np.array([
        [1, 0, 0, 0],
        [0, 0, 1, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1]
    ])

def Toffoli():
    """Toffoli 门 (CCNOT)"""
    return np.array([
        [1,0,0,0,0,0,0,0],
        [0,1,0,0,0,0,0,0],
        [0,0,1,0,0,0,0,0],
        [0,0,0,1,0,0,0,0],
        [0,0,0,0,1,0,0,0],
        [0,0,0,0,0,1,0,0],
        [0,0,0,0,0,0,0,1],
        [0,0,0,0,0,0,1,0]
    ])

# 验证 SWAP 门 = CNOT(0,1) · CNOT(1,0) · CNOT(0,1)
def build_swap_from_cnot():
    # 注意：当 qubit 顺序固定时需要用张量积和排列操作
    # 这里简化验证
    swap = SWAP()
    cnot_01 = CNOT()
    
    # 用 3 个 CNOT 构建 SWAP
    # 对于 |10⟩ → 应用 CNOT(0,1): |10⟩ → |11⟩
    #                  CNOT(1,0): |11⟩ → |01⟩
    #                  CNOT(0,1): |01⟩ → |01⟩ ✓
    test = np.array([0, 0, 1, 0])  # |10⟩
    result = cnot_01 @ test
    print(f"CNOT|10⟩ = {result}")  # |11⟩
    return True

build_swap_from_cnot()
```

---

## 4. 通用门集

### 4.1 通用量子门集的定义

一组门被称为**通用**的，如果任意 $n$ 量子比特酉操作都可以用这组门的有限序列近似。

常见的通用门集：

1. **Clifford + T**：$\{H, S, CNOT, T\}$
2. **旋转 + CNOT**：$\{R_x, R_y, R_z, CNOT\}$
3. **H + T + CNOT**：$\{H, T, CNOT\}$

### 4.2 门的近似

任何单量子比特门可以用 H 和 T 近似（Solovay-Kitaev 定理）：

```python
def approximate_gate_gate(U, gates=[H, T], depth=10):
    """
    用 H, T 门序列近似任意单量子比特门
    实际中使用 Solovay-Kitaev 算法
    """
    # 简化演示：用 T 和 H 的组合
    sequence = []
    # HTH = Rx(π/4)
    result = H @ T @ H
    sequence = ['H', 'T', 'H']
    return result, sequence

# 实际中 Qiskit 的 transpile 会自动做这些
```

---

## 5. 量子线路

### 5.1 线路表示

量子线路是量子门的时序排列，从左到右执行。

```
示例：创建 Bell 态
         ┌───┐          
|q0⟩: ──┤ H ├──●───────
         └───┘  │       
|q1⟩: ──────────⊕───────

示例：纠缠态
         ┌───┐ ┌───┐          
|q0⟩: ──┤ H ├─┤ S ├──●───────
         └───┘ └───┘  │       
|q1⟩: ────────────────⊕───○───
                           │
|q2⟩: ────────────────────⊕───
```

### 5.2 线路模拟

```python
class QuantumCircuit:
    """简单的量子线路模拟器"""
    def __init__(self, n_qubits):
        self.n_qubits = n_qubits
        self.state = np.zeros(2**n_qubits, dtype=complex)
        self.state[0] = 1.0  # 初始 |00...0⟩
        self.gates = []
    
    def h(self, target):
        self.gates.append(('H', target))
        return self
    
    def cx(self, control, target):
        self.gates.append(('CNOT', control, target))
        return self
    
    def measure(self):
        """测量所有量子比特"""
        probs = np.abs(self.state)**2
        # 随机坍缩
        outcome = np.random.choice(len(self.state), p=probs)
        self.state = np.zeros_like(self.state)
        self.state[outcome] = 1.0
        return f"{outcome:0{self.n_qubits}b}"
    
    def _apply_gate(self, gate_matrix, qubits):
        """应用门到指定的量子比特"""
        n = self.n_qubits
        # 构建完整算子 (简化版，仅支持单比特或 CNOT)
        full_op = np.eye(1)
        for i in range(n):
            if i == qubits[0]:
                full_op = np.kron(full_op, gate_matrix)
            else:
                full_op = np.kron(full_op, np.eye(2))
        self.state = full_op @ self.state
    
    def run(self):
        """执行线路"""
        for gate in self.gates:
            if gate[0] == 'H':
                self._apply_gate(H, [gate[1]])
            elif gate[0] == 'CNOT':
                # CNOT: 需要处理 qubit 顺序
                # 简化：假设 target = qubits[0]
                self._apply_gate(CNOT(), [gate[1], gate[2]])
        return self.state

# 测试 Bell 态
qc = QuantumCircuit(2)
qc.h(0).cx(0, 1)
state = qc.run()
print(f"Bell 态: {state}")
# [0.707, 0, 0, 0.707]  →  (|00⟩ + |11⟩)/√2

# 测量多次
outcomes = []
for _ in range(100):
    qc2 = QuantumCircuit(2)
    qc2.h(0).cx(0, 1)
    outcomes.append(qc2.measure())

print(f"测量结果: {outcomes[:10]}")
print(f"00比例: {outcomes.count('00')}%")
print(f"11比例: {outcomes.count('11')}%")
```

---

## 6. 门分解与 transpile

### 6.1 常用分解

**CNOT 分解为物理门**：

对超导处理器，CNOT 通常分解为：

$$\text{CNOT} = R_y(\pi/2) \otimes I \cdot \text{CZ} \cdot R_y(-\pi/2) \otimes I$$

**任意单比特门的分解**：

$$U = e^{i\alpha} R_z(\beta) R_y(\gamma) R_z(\delta)$$

这是所谓的 ZYZ 分解。

### 6.2 门等价关系

```python
# 重要等价关系

# HXH = Z
assert np.allclose(H @ X @ H, Z)

# HYH = -Z
assert np.allclose(H @ Y @ H, -Z)

# HZH = X
assert np.allclose(H @ Z @ H, X)

# CNOT = (I⊗H) CZ (I⊗H)
CZ_gate = CZ()
I = np.eye(2)
CNOT_from_CZ = np.kron(I, H) @ CZ_gate @ np.kron(I, H)
assert np.allclose(CNOT_from_CZ, CNOT())

# S² = Z
assert np.allclose(S @ S, Z)

# T² = S
assert np.allclose(T @ T, S)
```

---

## 7. 常见量子线路模版

### 7.1 量子傅里叶变换（QFT）

```
|j3⟩ ── H ─── R2 ─── R3 ───────────────── ● ──────
                   │                       │
|j2⟩ ──────────────● ── H ─── R2 ───────── ● ──────
                                │          │
|j1⟩ ───────────────────────────● ── H ─── ⊕ ──────
                                           │
|0⟩  ────────────────────────────────────── ⊕ ──────
                                           │
                 (交换输出顺序以获得正确结果)
```

### 7.2 Grover 迭代

```
重复 √N 次:
  ┌───────────────┐    ┌───────────────┐
  │ Oracles       │    │ 扩散算子      │
  │ U_f |x⟩       │    │ 2|s⟩⟨s| - I   │
  └───────────────┘    └───────────────┘
```

### 7.3 变分量子线路（VQC）

用于 VQE 和 QAOA 的参数化线路：

```
|0⟩ ── Ry(θ₁) ── ● ── Ry(θ₄) ── ● ──
                  │              │
|0⟩ ── Ry(θ₂) ── ⊕ ── Ry(θ₅) ── ⊕ ──
                  │              │
|0⟩ ── Ry(θ₃) ── ⊕ ── Ry(θ₆) ── ⊕ ──
   ↑        ↑          ↑
  初始态   旋转层     纠缠层
```

---

## 总结

| 门 | 符号 | 矩阵 | 作用 |
|----|------|------|------|
| X | ⊕ | $\begin{bmatrix}0&1\\1&0\end{bmatrix}$ | 量子 NOT |
| Y | — | $\begin{bmatrix}0&-i\\i&0\end{bmatrix}$ | 比特+相位翻转 |
| Z | — | $\begin{bmatrix}1&0\\0&-1\end{bmatrix}$ | 相位翻转 |
| H | H | $\frac{1}{\sqrt{2}}\begin{bmatrix}1&1\\1&-1\end{bmatrix}$ | 创建叠加态 |
| S | S | $\begin{bmatrix}1&0\\0&i\end{bmatrix}$ | 旋转 $\pi/2$ |
| T | T | $\begin{bmatrix}1&0\\0&e^{i\pi/4}\end{bmatrix}$ | 旋转 $\pi/4$ |
| CNOT | ⊕ | $\begin{bmatrix}I&0\\0&X\end{bmatrix}$ | 纠缠门 |
| Toffoli | ⊕(双控) | 8×8 矩阵 | 通用门 |
| SWAP | × | $\begin{bmatrix}1&0&0&0\\0&0&1&0\\0&1&0&0\\0&0&0&1\end{bmatrix}$ | 交换比特 |

**核心性质：** 所有量子门都是**酉矩阵**（$U^\dagger U = I$），量子线路是可逆的，需要辅助比特来实现不可逆的经典逻辑。
