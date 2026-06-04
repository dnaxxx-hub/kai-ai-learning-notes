# 线性代数基础：向量空间与线性变换

> 日期：2026-05-07 | 课程：ML/DL路线 Phase 1-1
> 目标：从ML视角理解线性代数，而非纯数学

## 核心概念

### 1. 向量 = 数据的基本单位
在ML中，**每个样本就是一个向量**。
- 一张 28×28 的图片 = 784维向量
- 一句话的 word embedding = 300~768维向量
- 一个交易日的特征 = 多个维度的数值向量

### 2. 矩阵 = 数据变换器
```
y = Wx + b
```
这行代码是**神经网络层的本质**：
- `x` = 输入向量（上一层）
- `W` = 权重矩阵（可学习的变换）
- `b` = 偏置向量
- `y` = 输出向量（下一层）

### 3. 线性变换 = 神经网络每层的操作
- 旋转（Rotation）
- 缩放（Scaling）
- 投影（Projection）
- 剪切（Shear）

## 可视化示例

![线性变换](01_linear_transforms.png)

左图：原始向量 v(2,1) 和 w(1,2)
右图：经旋转矩阵 R = [[cos45°, -sin45°], [sin45°, cos45°]] 变换后的结果

这就是神经网络每层在做的事：**将输入向量空间映射到另一个向量空间**。

## 关键公式

### 矩阵乘法（神经网络核心）
```python
# 全连接层: y = W @ x + b
# 输入 x: shape (n,)   权重 W: shape (m, n)   输出 y: shape (m,)
y = W.dot(x) + b
```

### 点积 = 相似度度量
```python
similarity = np.dot(v1, v2)  # 越大越相似
# 归一化版本 = cos相似度
cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
```

### 矩阵转置（反向传播关键）
```python
# 反向传播时梯度通过转置矩阵回传
# forward: y = W @ x
# backward: grad_x = W.T @ grad_y
```

## 与ML的关键连接

| 线性代数概念 | ML中的应用 |
|-------------|-----------|
| 向量空间 | 特征空间、embedding空间 |
| 矩阵乘法 | 全连接层、卷积(im2col) |
| 特征值/特征向量 | PCA降维、图拉普拉斯 |
| 奇异值分解(SVD) | 矩阵分解、推荐系统、模型压缩 |
| 范数(Norm) | 正则化(L1/L2)、梯度裁剪 |
| 矩阵求逆 | 线性回归解析解: β = (XᵀX)⁻¹Xᵀy |

## 代码练习

```python
import numpy as np

# 1. 向量运算
v = np.array([1, 2, 3])
w = np.array([4, 5, 6])
print(f"点积: {np.dot(v, w)}")           # 1*4 + 2*5 + 3*6 = 32
print(f"叉积: {np.cross(v[:2], w[:2])}")  # 1*5 - 2*4 = -3

# 2. 线性变换 = 神经网络层
def linear_layer(x, W, b):
    return W @ x + b

x = np.array([0.5, -0.3, 0.8])
W = np.random.randn(2, 3)  # 随机初始化权重
b = np.zeros(2)
y = linear_layer(x, W, b)
print(f"输入 {x.shape} → 输出 {y.shape}: {y}")

# 3. 矩阵的秩 = 有效维度
A = np.array([[1, 2], [2, 4]])  # 第二行是第一行的2倍
print(f"秩1矩阵: {np.linalg.matrix_rank(A)}")  # 输出：1（退化）
```

## 今日收获
- 向量在ML中是"数据单位"，矩阵是"变换器"
- 神经网络层的本质就是线性变换 + 非线性激活
- 矩阵的秩决定了变换后的有效维度（退化=信息丢失）
- 反向传播依赖转置矩阵回传梯度
