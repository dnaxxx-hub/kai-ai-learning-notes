# 量子机器学习

> 量子计算第6课 — VQE到QAOA的变分量子算法

## 变分量子算法（VQA）

### 核心范式
利用经典-量子混合架构解决优化和机器学习问题。

```
┌────────────────────────────────────┐
│ 经典优化器（CPU/GPU）              │
│ 更新参数 θ ← θ - η · ∇L(θ)        │
└──────────────┬─────────────────────┘
               │ 参数 θ
               ▼
┌────────────────────────────────────┐
│ 量子电路（QPU）                    │
│ 制备 |ψ(θ)⟩ = U(θ)|0⟩              │
│ 测量 ⟨ψ(θ)|H|ψ(θ)⟩                 │
└──────────────┬─────────────────────┘
               │ 期望值
               ▼
        重复直到收敛
```

### 为什么需要混合架构
- 当前量子设备是 NISQ（含噪声中等规模）
- 短量子电路 + 经典优化 = 比纯量子更稳定
- 参数化电路可表达复杂函数，但用经典优化训练

## VQE（变分量子特征求解器）

### 问题定义
找到哈密顿量 H 的最小特征值（基态能量）。

### VQE 步骤
```python
import numpy as np

def vqe_circuit(theta, n_qubits):
    """参数化量子电路 ansatz"""
    # 初始化 |0⟩ 态
    # 应用参数化旋转门
    # 返回 |ψ(θ)⟩ = U(θ)|0⟩
    pass

def compute_expectation(theta, hamiltonian, n_shots=1000):
    """计算 ⟨ψ(θ)|H|ψ(θ)⟩"""
    # 执行量子电路 n_shots 次
    # 测量每个 Pauli 项
    # 加权求和
    expectation = 0.0
    for pauli_string, coefficient in hamiltonian:
        # 测量 ⟨Pauli⟩
        exp_val = measure_pauli(theta, pauli_string, n_shots)
        expectation += coefficient * exp_val
    return expectation

def vqe_optimize(hamiltonian, n_qubits, max_iter=100):
    """VQE 优化循环"""
    theta = np.random.randn(n_params)
    
    for i in range(max_iter):
        energy = compute_expectation(theta, hamiltonian)
        
        # 参数偏移法则计算梯度
        grad = parameter_shift(theta, hamiltonian)
        
        # 梯度下降
        theta -= 0.01 * grad
        
        if i % 10 == 0:
            print(f"Step {i}: Energy = {energy:.6f}")
    
    return theta, energy
```

### VQE 的优势
- 浅电路（NISQ友好）
- 不需要量子纠错
- 物理化学模拟的应用前景

## QAOA（量子近似优化算法）

### 问题框架
解决组合优化问题（MaxCut、TSP、图着色）。

### QAOA 电路结构
```
|+⟩⊗ⁿ → e^{-iγ·H_C} → e^{-iβ·H_B} → ... → 重复 p 层 → 测量

H_C = Cost Hamiltonian（编码目标函数）
H_B = Mixer Hamiltonian（驱动探索）
p = QAOA 深度（越深质量越高）
```

### MaxCut 示例

```python
def qaoa_maxcut(graph, p_layers=1):
    """QAOA 求解 MaxCut"""
    n_qubits = len(graph.nodes)
    
    # Cost Hamiltonian: H_C = sum_{(i,j)∈E} Z_i ⊗ Z_j
    h_cost = 0
    for i, j in graph.edges:
        h_cost += Z_i @ Z_j
    
    # Mixer Hamiltonian: H_B = sum_i X_i
    h_mixer = sum(X_i for i in range(n_qubits))
    
    # QAOA 参数
    gamma = np.random.randn(p_layers)
    beta = np.random.randn(p_layers)
    
    # 电路执行 + 优化
    for epoch in range(100):
        # 制备 |γ,β⟩ = U_B(β_p)U_C(γ_p)...U_B(β_1)U_C(γ_1)|+⟩
        # 测量 ⟨γ,β|H_C|γ,β⟩
        expectation = measure_qaoa(gamma, beta, graph)
        
        # 更新参数（经典优化）
        gamma, beta = classical_optimizer(expectation, gamma, beta)
    
    return gamma, beta
```

## 量子核方法

### 思想
用量子态特征空间替代经典核函数。

```
经典核：K(x_i, x_j) = ⟨φ(x_i), φ(x_j)⟩
量子核：K_Q(x_i, x_j) = |⟨0|U†(x_i)U(x_j)|0⟩|²
```

### 量子核SVM
```python
def quantum_kernel(x1, x2, n_qubits):
    """量子核函数计算"""
    # 制备 |ψ(x1)⟩ = U(x1)|0⟩
    # 应用 U†(x2) 逆电路
    # 测量 |0⟩ 概率
    circuit = create_encoding(x1, n_qubits)
    circuit += create_encoding_inv(x2, n_qubits)
    
    # P(|0...0⟩) = |⟨ψ(x1)|ψ(x2)⟩|²
    kernel_value = measure_all_zero(circuit)
    return kernel_value
```

## 变分量子分类器

### 架构
```
输入 x → 编码电路 S(x) → 变分层 V(θ) → 测量 → 分类
```

### 编码方式
| 编码 | 比特数 | 表示能力 | 示例 |
|------|--------|---------|------|
| 角度编码 | n | 线性 | x → R_y(πx) |
| 幅度编码 | log₂(d) | 指数 | 归一化向量作为幅度 |
| IQP编码 | n | 强 | 多层纠缠 |

### 测量与决策
```python
def variational_classifier(x, theta):
    """变分量子分类器"""
    # 数据编码
    circuit = angle_encoding(x)
    
    # 变分层（硬件高效 ansatz）
    circuit += variational_layer(theta)
    
    # 测量单比特
    prob_0 = measure_qubit(circuit, qubit=0, outcome=0)
    
    # 决策边界
    return 1 if prob_0 > 0.5 else 0
```

## 量子GAN

### 生成器-判别器框架（量子化）
```
真实数据 → Discriminator (Quantum) → 真/假
                                   ↑
生成样本 ← Generator (Quantum) ← Z (噪声)
```

## 当前局限与前沿

### NISQ 时代的限制
1. **噪声**：2-3层变分电路后噪声占主导
2. **贫瘠高原**：随机初始化导致梯度指数级消失（Barren Plateau）
3. **测量开销**：需要 10⁴-10⁶ 次测量才能获得可靠的期望值
4. **数据搬移**：经典-量子间通信速度限制

### 突破方向
- **错误缓解**：零噪声外推、概率错误消除
- **参数初始化**：避免贫瘠高原的策略
- **特殊结构**：QCNN结构减少参数
- **量子优势算法**：寻找量子不可替代的场景

## 总结
- VQE和QAOA是最成熟的两个变分量子算法
- 量子核方法提供指数级特征空间但不保证量子优势
- NISQ时代的主要挑战是噪声、贫瘠高原和测量开销
- 量子机器学习的实际优势仍在探索中，量子化学和优化是当前最有希望的应用方向
