# Qiskit 实战

> 量子计算第8课 — 从电路搭建到真实量子设备

## Qiskit 架构

```
Qiskit
├── Terra          # 核心：电路/编译/后端
├── Aer            # 模拟器：状态向量/密度矩阵/噪声
├── IBM Runtime    # 运行后端设备
├── Nature         # 量子化学/物理模拟
├── Optimization   # 优化问题求解
└── Machine Learning # 量子ML
```

## 量子电路搭建

```python
from qiskit import QuantumCircuit

# 创建 3 量子比特电路
qc = QuantumCircuit(3, 3)  # 3 量子比特 + 3 经典比特

# 量子门
qc.h(0)              # Hadamard
qc.cx(0, 1)          # CNOT (控制比特0, 目标比特1)
qc.rz(0.5, 2)        # 旋转 Z
qc.barrier()         # 编译屏障
qc.measure([0,1,2], [0,1,2])  # 测量

print(qc.draw())
```

### 常用门速查

| 方法 | 门 | 参数 |
|------|-----|------|
| `qc.h(q)` | Hadamard | — |
| `qc.x(q)` | Pauli-X (NOT) | — |
| `qc.y(q)` | Pauli-Y | — |
| `qc.z(q)` | Pauli-Z | — |
| `qc.rx(θ, q)` | 绕X轴旋转 | θ (弧度) |
| `qc.ry(θ, q)` | 绕Y轴旋转 | θ |
| `qc.rz(θ, q)` | 绕Z轴旋转 | θ |
| `qc.cx(c, t)` | CNOT | 控制, 目标 |
| `qc.swap(a,b)` | Swap | — |
| `qc.ccx(a,b,c)` | Toffoli | — |

## 模拟器

### StatevectorSimulator

```python
from qiskit_aer import AerSimulator
from qiskit.quantum_info import Statevector

# 状态向量模拟
sim = AerSimulator()
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)

# 获取状态向量
qc.save_statevector()
result = sim.run(qc).result()
statevector = result.get_statevector(qc)
print(f"状态向量: {statevector}")
# 输出: 1/√2|00⟩ + 1/√2|11⟩
```

### 噪声模拟

```python
from qiskit_aer.noise import NoiseModel, depolarizing_error, thermal_relaxation_error

# 创建噪声模型
noise_model = NoiseModel()

# 单比特退极化噪声
dep_error = depolarizing_error(0.01, 1)  # 1% 错误率
noise_model.add_all_qubit_quantum_error(dep_error, ['u3'])

# 热弛豫噪声 (T1/T2)
t1 = 50e-6   # 50μs
t2 = 30e-6   # 30μs  
gate_time = 0.1e-6  # 100ns
thermal_error = thermal_relaxation_error(t1, t2, gate_time)
noise_model.add_all_qubit_quantum_error(thermal_error, ['id'])

# 有噪声的模拟
sim_noisy = AerSimulator(noise_model=noise_model)
result = sim_noisy.run(qc.measure_all(inplace=False)).result()
counts = result.get_counts()
print(counts)
```

## 编译与优化

### Transpile 管线

```python
from qiskit.transpiler import PassManager, PassManagerConfig
from qiskit.transpiler.passes import *

# 编译到特定后端
from qiskit_ibm_runtime import QiskitRuntimeService

service = QiskitRuntimeService()
backend = service.backend('ibm_sherbrooke')  # 127比特处理器

# transpile：将电路映射到物理拓扑
from qiskit import transpile

qc_compiled = transpile(
    qc,
    backend=backend,
    optimization_level=3,  # 0(最快)-3(最优)
    routing_method='sabre',
    scheduling_method='asap'
)
```

### 优化级别

| 级别 | 操作 | 适用 |
|------|------|------|
| 0 | 无优化 | 调试 |
| 1 | 轻量优化 | 浅电路 |
| 2 | 中等优化（默认） | 大多数 |
| 3 | 重优化 | 关键运行 |

## 真实设备运行

```python
# 初始化 IBM 量子服务
from qiskit_ibm_runtime import QiskitRuntimeService, Session, Sampler, Estimator

service = QiskitRuntimeService(
    channel='ibm_quantum',
    token='YOUR_IBMQ_TOKEN'
)

# 使用 Session
with Session(service=service, backend='ibm_sherbrooke') as session:
    # Sampler：获取测量结果
    sampler = Sampler()
    job = sampler.run([qc_compiled], shots=10000)
    result = job.result()
    print(f"Quasi-distribution: {result.quasi_dists[0]}")
    
    # Estimator：获取期望值
    estimator = Estimator()
    job2 = estimator.run([qc_compiled], [hamiltonian])
    energy = job2.result().values[0]
    print(f"Energy: {energy}")
```

## 误差缓解

### 测量误差缓解

```python
from qiskit_ibm_runtime.utils import safe_zip

# 通过校准矩阵测量缓解
# 运行简单的 |0...0⟩ 和 |1...1⟩ 电路来构建校准矩阵

from qiskit.utils import mitigation

# 使用 M3 (Matrix-free Measurement Mitigation)
m3_mitigator = Mitigation()
mitigated_counts = m3_mitigator.apply(counts, calibration_matrix)
```

### 零噪声外推
```python
# 在不同的噪声放大倍数下运行
noise_factors = [1, 2, 3, 5]
results = []

for factor in noise_factors:
    # 通过插入噪声门模拟更高的噪声
    noisy_circuit = amplify_noise(qc, factor)
    job = estimator.run([noisy_circuit], [hamiltonian])
    results.append(job.result().values[0])

# 外推得到零噪声期望值
extrapolated = extrapolate_to_zero_noise(results, noise_factors)
```

## 实际示例：Grover算法

```python
from qiskit.algorithms import Grover, AmplificationProblem
from qiskit.circuit.library import GroverOperator

# 定义 Oracle
oracle = QuantumCircuit(2)
oracle.cz(0, 1)  # 标记 |11⟩ 态

# Grover 算法
grover = Grover()
result = grover.amplify(AmplificationProblem(oracle))
print(result.top_measurement)  # 应为 '11'
```

## 总结
- Qiskit 是 IBM 的量子开发框架，Terra + Aer 是最核心的组件
- Aer 提供带噪声和无噪声两种模拟模式
- transpile 将逻辑电路映射到物理拓扑，optimization_level=3 最高
- 真实设备运行需要创建 Session→Sampler/Estimator API
- 误差缓解（测量缓解/零噪声外推）是NISQ时代的必需品
- 真实设备访问需要通过 IBM Quantum 平台获取 token
