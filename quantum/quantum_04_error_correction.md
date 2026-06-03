# 量子纠错

## 1. 概述

量子纠错（Quantum Error Correction, QEC）是构建实用量子计算机的**必要条件**。量子比特极其脆弱——任何与环境相互作用都会导致退相干和错误。不同于经典纠错，量子纠错面临三大挑战：

1. **不可克隆定理**：不能复制量子态（不能做备份）
2. **测量破坏性**：测量会坍缩量子态
3. **错误连续**：量子错误是连续的（不只是比特翻转）

### 错误分类

| 类型 | 经典类比 | 量子变换 | 说明 |
|------|----------|----------|------|
| 比特翻转 | 0↔1 | $X|\psi\rangle$ | Pauli X 错误 |
| 相位翻转 | - | $Z|\psi\rangle$ | Pauli Z 错误 |
| 比特+相位 | - | $Y|\psi\rangle$ | Y = iXZ |
| 振幅阻尼 | 能量损失 | $|1\rangle\to\sqrt{\gamma}|0\rangle$ | T1 过程 |
| 退极化 | 完全随机化 | $\rho \to (1-p)\rho + pI/2$ | 混合 |

---

## 2. 重复码

### 2.1 经典重复码

经典纠错最简单的思想：重复。$0 \to 000$，$1 \to 111$。多数投票纠正错误。

### 2.2 量子比特翻转码

编码：$|0\rangle_L = |000\rangle$，$|1\rangle_L = |111\rangle$

但量子态是叠加的！$\alpha|0\rangle + \beta|1\rangle$ 如何编码？

**编码线路：**

```
|ψ⟩ ── ● ── ● ──
        │    │
|0⟩ ── ⊕ ── │ ──
              │
|0⟩ ──────── ⊕ ──

输入 α|0⟩+β|1⟩ → 输出 α|000⟩+β|111⟩
```

**纠错过程：**

```
1. 编码: α|0⟩+β|1⟩ → α|000⟩+β|111⟩
2. 某比特翻转: α|010⟩+β|101⟩ (第二个比特翻转)
3. 综合征测量: 比较相邻比特 (不破坏叠加!)
        测量 (q₀⊕q₁) 和 (q₁⊕q₂)
        syndrome = 10 → 第二个比特出错
4. 纠正: 对第二个比特应用 X 门
5. 恢复: α|000⟩+β|111⟩
```

```python
import numpy as np

class BitFlipCode:
    """三量子比特翻转码"""
    def __init__(self):
        self.n = 3
    
    def encode(self, state):
        """编码: α|0⟩+β|1⟩ → α|000⟩+β|111⟩"""
        alpha, beta = state
        encoded = np.zeros(8, dtype=complex)
        encoded[0] = alpha   # |000⟩
        encoded[7] = beta    # |111⟩
        return encoded
    
    def syndrome_measurement(self, state):
        """测量误差综合征（不破坏编码态）"""
        # 使用辅助量子比特测量 (q0⊕q1) 和 (q1⊕q2)
        # 返回 syndrome 值 0-3
        probs = np.abs(state)**2
        
        # 计算 P(q0≠q1) 和 P(q1≠q2)
        p01_diff = sum(probs[i] for i in range(8) 
                      if (i>>2 & 1) != (i>>1 & 1))
        p12_diff = sum(probs[i] for i in range(8)
                      if (i>>1 & 1) != (i & 1))
        
        syndrome = 0
        if p01_diff > 0.5: syndrome |= 1  # Z₁
        if p12_diff > 0.5: syndrome |= 2  # Z₂
        
        return syndrome
    
    def correct(self, state, syndrome):
        """应用纠正"""
        corrected = state.copy()
        if syndrome == 1:  # 第一个比特
            # 交换 qubit 0 和 qubit 1 的振幅
            perm = [i ^ 4 for i in range(8)]
            corrected = corrected[perm]
        elif syndrome == 2:  # 第二个比特
            perm = [i ^ 2 for i in range(8)]
            corrected = corrected[perm]
        elif syndrome == 3:  # 第三个比特
            perm = [i ^ 1 for i in range(8)]
            corrected = corrected[perm]
        return corrected

# 测试
code = BitFlipCode()
original = np.array([0.6, 0.8])  # α=0.6, β=0.8
encoded = code.encode(original)

# 模拟错误：翻转第二个比特
error_state = encoded.copy()
# flip qubit 1 (index 2): 交换 (0,2), (1,3), (4,6), (5,7)
perm = [2, 3, 0, 1, 6, 7, 4, 5]
error_state = error_state[perm]

syndrome = code.syndrome_measurement(error_state)
corrected = code.correct(error_state, syndrome)

# 验证
fidelity = np.abs(np.dot(corrected.conj(), encoded))**2
print(f"错误综合征: {syndrome}")
print(f"纠正保真度: {fidelity:.4f}")
```

---

## 3. Shor 码

### 3.1 原理

Shor 码是第一个量子纠错码，可以纠正任意单量子比特错误（比特翻转 + 相位翻转 + 两者同时）。使用 **9 个物理量子比特**编码 1 个逻辑量子比特。

**编码结构：**

```
相位翻转编码               比特翻转编码
  ↓                        ↓
|0⟩L = (|000⟩+|111⟩)(|000⟩+|111⟩)(|000⟩+|111⟩) / √8
|1⟩L = (|000⟩-|111⟩)(|000⟩-|111⟩)(|000⟩-|111⟩) / √8

  逻辑比特 = 3组(相位码) × 每组3个物理比特(比特码)
```

### 3.2 编码线路

```
|ψ⟩ ── ● ── ── ● ── ── ● ────────────
        │       │       │
|0⟩ ── ⊕ ── H ─⊕ ───────⊕ ────────────
        │       │       │
|0⟩ ── ⊕ ── H ─⊕ ───────⊕ ────────────
                │       │
|0⟩ ────────────⊕ ── H ─⊕ ────────────
                │       │
|0⟩ ────────────⊕ ── H ─⊕ ────────────
                        │
|0⟩ ────────────────────⊕ ── H ────────
                        │
|0⟩ ────────────────────⊕ ── H ────────
```

### 3.3 纠错能力

```
Shor 码纠正能力：
  ✓ 任何单比特 X 错误
  ✓ 任何单比特 Z 错误
  ✓ 任何单比特 Y 错误 (X 和 Z 同时)
  ✗ 不能纠正两比特或更多错误
```

---

## 4. Steane 码

### 4.1 原理

Steane 码是 [[7, 1, 3]] 量子纠错码，用 7 个物理比特编码 1 个逻辑比特，可以纠正任意单个错误。

基于经典 [7, 4, 3] Hamming 码：

```
Steane 码的校验矩阵：
H = [0 0 0 1 1 1 1]    X 稳定子
    [0 1 1 0 0 1 1]
    [1 0 1 0 1 0 1]
    [0 0 0 1 1 1 1]    Z 稳定子
    [0 1 1 0 0 1 1]
    [1 0 1 0 1 0 1]

逻辑态：
|0⟩L = (|0000000⟩ + |1010101⟩ + |0110011⟩ + |1100110⟩ 
       + |0001111⟩ + |1011010⟩ + |0111100⟩ + |1101001⟩) / √8

|1⟩L = X_L|0⟩L, 其中 X_L = X⊗X⊗X⊗X⊗X⊗X⊗X
```

### 4.2 稳定子测量

```python
class SteaneCode:
    """Steane [[7,1,3]] 码"""
    def __init__(self):
        self.n = 7
        # X 稳定子
        self.X_stabilizers = [
            [3, 4, 5, 6],    # X₃X₄X₅X₆
            [1, 2, 5, 6],    # X₁X₂X₅X₆
            [0, 2, 4, 6],    # X₀X₂X₄X₆
        ]
        # Z 稳定子（索引同上）
        self.Z_stabilizers = self.X_stabilizers
    
    def measure_syndrome(self, state):
        """测量稳定子获取错误综合征"""
        # 实际中通过辅助比特测量，这里简化
        syndrome = {
            'X': [],  # Z 错误的综合征
            'Z': [],  # X 错误的综合征
        }
        
        # 检查每个稳定子的期望值
        for stab in self.X_stabilizers:
            # 对 7 量子比特态应用稳定子并检查符号
            # 简化：直接检查振幅分布
            syndrome['X'].append(1)  # 占位
        
        return syndrome
    
    def decode(self, syndrome):
        """根据综合征确定错误位置和类型"""
        # 使用查找表（ syndrome → 纠错操作）
        decode_table = {
            (0, 0, 0, 0, 0, 0): None,       # 无错误
            (1, 0, 0, 0, 0, 0): (0, 'X'),   # 位置 0, X 错误
            # ... 完整表有 21 种单错误组合
        }
        # 实际中 syndromes 和错误位置一一对应
        pass
```

---

## 5. 表面码

### 5.1 原理

表面码（Surface Code）是目前最主流的量子纠错方案，被 Google、IBM 等采用。

**拓扑结构：**

```
数据比特 (●) 和测量比特 (■, ▲):

     ● ── ■ ── ● ── ■ ── ●
     │    │    │    │    │
     ▲ ── ● ── ▲ ── ● ── ▲
     │    │    │    │    │
     ● ── ■ ── ● ── ■ ── ●
     │    │    │    │    │
     ▲ ── ● ── ▲ ── ● ── ▲
     │    │    │    │    │
     ● ── ■ ── ● ── ■ ── ●

■ = X 稳定子测量 (4个相邻数据比特的X乘积)
▲ = Z 稳定子测量 (4个相邻数据比特的Z乘积)
● = 数据比特
```

### 5.2 优势

| 特性 | 表面码 |
|------|--------|
| 物理需求 | 仅需要**最近邻耦合** |
| 错误阈值 | 高达 ~1%（技术上可行！） |
| 扩展性 | 只需增加网格规模 |
| 逻辑错误 | $p_L \propto (p/p_{th})^{d/2}$（指数级压制） |

### 5.3 解码

```python
class SurfaceCode:
    """表面码简化模拟"""
    def __init__(self, distance=3):
        """
        distance = 码距
        需要的物理量子比特 = 2*d² - 1
        """
        self.d = distance
        self.n_data = distance**2 + (distance-1)**2
        self.n_ancilla = distance**2 - 1
        
    def simulate_error_correction(self, physical_error_rate):
        """模拟一轮纠错"""
        # 数据比特上的错误
        errors = np.random.binomial(1, physical_error_rate, self.n_data)
        
        # 稳定子测量（检测到错误奇偶）
        syndromes = []
        for stabilizer in self.stabilizers:
            parity = sum(errors[i] for i in stabilizer) % 2
            syndromes.append(parity)
        
        # 解码（匹配奇偶性 → 最可能的错误模式）
        # MWPM（最小权重完美匹配）
        corrections = self.minimum_weight_matching(syndromes)
        
        # 应用纠正
        corrected = np.bitwise_xor(errors, corrections)
        
        # 检查剩余错误（逻辑错误）
        logical_qubit = np.sum(corrected[::2]) % 2
        has_logical_error = logical_qubit == 1
        
        return has_logical_error
    
    def minimum_weight_matching(self, syndromes):
        """最小权重完美匹配解码"""
        # Blossom 算法实现（简略）
        # 将 syndrome 作为图中的顶点
        # 找最小权重的匹配
        return np.zeros(self.n_data)
    
    def compute_threshold(self):
        """计算错误阈值"""
        # 对不同物理错误率做仿真
        # 找到逻辑错误率开始低于物理错误率的点
        pass
```

---

## 6. 稳定子形式主义

### 6.1 基本概念

稳定子（Stabilizer）是现代量子纠错的理论基石。

**定义：** 稳定子群 $S$ 是所有使逻辑态不变的 Pauli 算符集合：

$$S|\psi\rangle_L = |\psi\rangle_L, \quad \forall S \in \mathcal{S}$$

### 6.2 稳定子码的要素

$$
\begin{aligned}
&\text{稳定子生成元: } \{g_1, g_2, ..., g_m\} \\
&[g_i, g_j] = 0 \quad (\text{所有稳定子对易}) \\
&g_i^2 = I \quad (\text{Pauli 算符的平方是恒等})
\end{aligned}
$$

- $n$ 个物理量子比特
- $m = n - k$ 个独立稳定子
- $k$ 个逻辑量子比特

### 6.3 稳定子测量

```python
def measure_stabilizer_gate(ancilla, data_qubits, stabilizer_type='Z'):
    """
    测量稳定子（Pauli 乘积）
    使用辅助比特做奇偶校验
    """
    # Z 稳定子测量：对每个数据比特做 CNOT(ancilla, data)
    # X 稳定子测量：先用 H 门，再 CNOT(data, ancilla)，再 H
    
    if stabilizer_type == 'Z':
        for q in data_qubits:
            CNOT(ancilla, q)
    else:  # X
        H(ancilla)
        for q in data_qubits:
            CNOT(q, ancilla)
        H(ancilla)
    
    return measure(ancilla)  # 用于检查错误
```

---

## 7. 错误阈值与容错

### 7.1 阈值定理

> **阈值定理**：如果物理错误率低于某个阈值 $p_{th}$，可以通过量子纠错实现任意低的逻辑错误率。

### 7.2 常见码的阈值

```
              阈值(p_th)
表面码:        ~1%         ← 最高，最实用
Steane码:      ~0.1%
Shor码:        ~0.01%
重复码:        ~10%        （仅对抗比特翻转）
```

### 7.3 资源估算

实现一个实用的逻辑量子比特需要：

```
物理比特    码距    逻辑错误率
  ~1000       d=7     10^-10  (表面码)
  ~10^5       d=30    10^-15  (Shor 算法需要)
  ~10^6       d=50    10^-18  (高保真计算)
```

---

## 总结

| 编码 | 物理比特 | 逻辑比特 | 码距 | 可纠正错误 | 阈值 |
|------|----------|----------|------|-----------|------|
| 重复码 | 3 | 1 | 2 | 1个比特翻转 | ~10% |
| Shor码 | 9 | 1 | 3 | 任意单比特 | ~0.01% |
| Steane码 | 7 | 1 | 3 | 任意单比特 | ~0.1% |
| 表面码 | $2d^2$ | 1 | $d$ | $\lfloor(d-1)/2\rfloor$ | ~1% |

**核心洞察：** 表面码是目前最实用的方案，因为它只需要最近邻耦合、具有高阈值，并且随着码距 $d$ 增加，逻辑错误率指数级下降。Google 的 Willow 芯片和 IBM 的路线图均采用表面码。
