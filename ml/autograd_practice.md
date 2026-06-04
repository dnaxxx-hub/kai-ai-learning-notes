# AutoDiff 实践笔记

## 概述
本次实现了一个迷你自动微分框架 mini_autograd.py，包含 Tensor 类、计算图构建、反向传播、nn 模块和优化器。

## 计算图设计

### 图结构
- 每个 Tensor 记录 _depends_on（父节点列表）和 _backward（局部梯度传播函数）
- 前向运算构建 DAG，反向传播通过拓扑排序遍历执行
- 拓扑排序使用 DFS 后序遍历（先子节点后父节点），然后逆转得到正确的反向顺序

### 关键设计决策
1. **立即执行模式**（而非 tape/记录模式）：每个运算立即计算结果，同时注册 backward 闭包
2. **梯度累积**：if self.grad is None: self.grad = g else: self.grad += g
3. **Broadcasting 处理**：_sum_to_shape() 函数将梯度从输出形状缩减到输入形状

## 各算子的梯度推导

### 基础运算
- **加法** z = x + y: dz/dx = 1, dz/dy = 1
- **减法** z = x - y: dz/dx = 1, dz/dy = -1
- **乘法** z = x * y: dz/dx = y, dz/dy = x
- **除法** z = x / y: dz/dx = 1/y, dz/dy = -x/y²

### 矩阵乘法
- z = x @ w
- dz/dx = grad @ w^T
- dz/dw = x^T @ grad

### 非线性函数
| 函数 | 前向 | 梯度 |
|------|------|------|
| exp | e^x | e^x |
| log | ln(x) | 1/x |
| sin | sin(x) | cos(x) |
| cos | cos(x) | -sin(x) |
| tanh | tanh(x) | 1 - tanh²(x) |
| sigmoid | 1/(1+e^{-x}) | sigmoid(x) * (1 - sigmoid(x)) |
| relu | max(0, x) | 1 if x > 0 else 0 |
| sqrt | √x | 0.5/√x = 0.5/output |
| pow(n) | x^n | n * x^{n-1} |

### 约减运算
- **sum**：梯度为 1，需扩展到原始形状（插入被约减的维度）
- **mean**：梯度为 1/n，同 sum 扩展方式

### Reshape
梯度直接 reshape 回原始形状

## nn 模块

### Linear
- Xavier/Glorot 初始化：Uniform(-√(6/(in+out)), √(6/(in+out)))
- 前向：y = x @ W + b

### MSELoss
- L = mean((pred - target)²)

### CrossEntropyLoss
- 从 logits 直接计算，内部做 softmax
- dL/dlogits = softmax - one_hot(class)

## 优化器

### SGD + Momentum
- v = momentum * v - lr * grad
- param += v

### Adam
- m = β₁*m + (1-β₁)*g
- v = β₂*v + (1-β₂)*g²
- m̂ = m/(1-β₁ᵗ), v̂ = v/(1-β₂ᵗ)
- param -= lr * m̂/(√v̂ + ε)

## 关键教训
1. **梯度累积必须用 +=**：多个路径汇聚到同一节点时梯度相加
2. **Broadcasting 的梯度处理**：需要 _sum_to_shape 将梯度沿广播维度求和
3. **CrossEntropyLoss 不能只用自动微分**：softmax + crossentropy 组合需要用数值稳定的手工 backward
4. **拓扑排序**：用 visited set + 后序遍历构建，反转后得到 backward 顺序
5. **测试策略**：数值梯度验证（finite difference）是保证正确性的金标准
