# 线性回归 & 逻辑回归：从连续到分类

> 日期：2026-05-07 13:30 | 课程：ML/DL路线 Phase 2-1
> 目标：掌握第一个完整ML算法从理论到实现的全过程

## 线性回归（Linear Regression）

### 问题定义
```
给定 (x_i, y_i)，找到 y = wx + b 使得预测误差最小
```

### 两种解法

#### 方法1：解析解（OLS — 普通最小二乘法）
```
w = (X^T X)^(-1) X^T y
```
- 一次计算，精确解
- 当 X^T X 可逆时直接求出
- 大数据集时求逆很慢 O(n³)

#### 方法2：梯度下降（数值解）
```python
for _ in range(steps):
    pred = X @ w
    grad = 2/n * X.T @ (pred - y)
    w = w - lr * grad
```
- 逐步逼近，不保证精确但足够好
- 可以处理海量数据（SGD）
- 是深度学习训练的基础

### 正则化（防止过拟合）

| 类型 | 惩罚项 | 效果 |
|------|--------|------|
| 无 | MSE | 可能过拟合 |
| L1 (Lasso) | λ·|w| | 产生稀疏解（自动特征选择） |
| L2 (Ridge) | λ·w² | 权重均匀缩小 |
| ElasticNet | λ₁|w| + λ₂w² | 两者结合 |

```python
# 目标函数：MSE + 正则化
# Ridge:       J = MSE + λ * sum(w²)
# Lasso:       J = MSE + λ * sum(|w|)
# ElasticNet:  J = MSE + λ₁|w| + λ₂w²

# 梯度更新时加入正则项
# Ridge:   w = w - lr * (grad + 2λ*w)
# Lasso:   w = w - lr * (grad + λ*sign(w))
```

## 逻辑回归（Logistic Regression）

### 核心思想
线性回归输出连续值 → 经过sigmoid → 变成概率(0~1)

```python
# 线性部分: z = wx + b
# 非线性映射: p = σ(z) = 1 / (1 + e^(-z))
# 决策: y_hat = 1 if p > 0.5 else 0
```

### 为什么不用MSE？
MSE会导致非凸优化（有多个局部极小值）
→ 改用**交叉熵损失**（凸函数，保证收敛到全局最优）

```python
# 二分类交叉熵
loss = -y * log(p) - (1-y) * log(1-p)

# 梯度非常简单
grad = X.T @ (p - y) / n  # 跟线性回归几乎一样！
```

### 多分类拓展：Softmax
```python
# K个类别 => 输出K个概率
softmax(z_i) = exp(z_i) / sum(exp(z_j))

# 损失 = Categorical CrossEntropy
# 梯度 = softmax输出 - one-hot标签  （极其简洁！）
```

## 可视化

![线性回归](05_linear_regression.png)

**左图**：OLS拟合结果 y = 1.97x + 1.05（真值 y=2x+1）
**中图**：MSE损失曲面——只有一个全局最小值（凸函数）
**右图**：梯度下降优化轨迹——从起点到最优点的收敛过程

## 代码实现

```python
import numpy as np

class LinearRegression:
    def fit(self, X, y):
        # OLS解析解
        X = np.column_stack([np.ones(len(X)), X])
        self.w = np.linalg.inv(X.T @ X) @ X.T @ y
        
    def predict(self, X):
        X = np.column_stack([np.ones(len(X)), X])
        return X @ self.w

class LogisticRegression:
    def __init__(self, lr=0.01, steps=1000):
        self.lr = lr
        self.steps = steps
    
    def _sigmoid(self, z):
        return 1 / (1 + np.exp(-np.clip(z, -100, 100)))
    
    def fit(self, X, y):
        n, d = X.shape
        self.w = np.zeros(d)
        self.b = 0
        
        for i in range(self.steps):
            z = X @ self.w + self.b
            p = self._sigmoid(z)
            grad_w = X.T @ (p - y) / n
            grad_b = np.mean(p - y)
            self.w -= self.lr * grad_w
            self.b -= self.lr * grad_b
    
    def predict_proba(self, X):
        return self._sigmoid(X @ self.w + self.b)
    
    def predict(self, X, threshold=0.5):
        return (self.predict_proba(X) >= threshold).astype(int)
```

## 与深度学习的关键桥接

| 概念 | 线性回归 | 神经网络 |
|------|---------|---------|
| 线性层 | y = wx + b | y = Wx + b 全连接层 |
| 激活 | 无（恒等） | ReLU/Sigmoid/Tanh |
| 损失 | MSE | 交叉熵/CosFace |
| 优化 | 梯度下降 | Adam/SGD/Momentum |
| 正则化 | L1/L2 | Dropout/BatchNorm |

**逻辑回归 = 单层神经网络 = 没有隐藏层的神经网络**
**Softmax分类器 = 逻辑回归的多分类版本**

## 今日收获
- 线性回归是**第一个ML算法**，也是理解所有监督学习的基础
- OLS解析解 = 矩阵求逆，梯度下降 = 逐步逼近
- 逻辑回归 = 线性回归 + Sigmoid + 交叉熵
- 正则化的本质：对过大权重施加惩罚
- **线性模型是神经网络的基础**——加一层非线性激活就成了NN
