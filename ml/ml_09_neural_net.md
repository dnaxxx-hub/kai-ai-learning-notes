# 神经网络基础：感知机、反向传播与激活函数

> 日期：2026-05-07 15:30 | 课程：ML/DL路线 Phase 3-1
> 目标：理解"神经网络"到底是怎样一个东西

## 核心直觉

### 一个神经元 = 逻辑回归
```python
# 单个神经元做的事:
z = w·x + b        # 1. 线性加权求和
a = σ(z)            # 2. 非线性激活
# 和逻辑回归一模一样!
```

### 多层 = 特征提取器
```
第一层：学低层特征（边、角）
中间层：学中层特征（形状、纹理）
最后一层：做分类/回归
```
**层数越深，学到的特征越抽象。**

## 三大激活函数

### Sigmoid — σ(x) = 1/(1+e⁻ˣ)
- 输出范围 [0, 1]，适合做概率
- **问题**：两端梯度≈0（梯度消失）
- 现在只用在**最后一层输出概率**

### Tanh — tanh(x)
- 输出范围 [-1, 1]，零中心
- 梯度消失仍然存在
- 比Sigmoid好一点，但已被ReLU取代

### ReLU — max(0, x)
- **现在默认选择**
- 正区间梯度恒为1（无梯度消失）
- 问题：负区间梯度=0（神经元死亡）
- 变体：Leaky ReLU / ELU / GELU

## 反向传播（BP）— 核心算法

### 为什么叫"反向"？
```
前向: X → W1 → ReLU → W2 → Sigmoid → 输出
        ↓        ↓        ↓        ↓
损失:   ← dW1  ← dz1  ← dW2  ← dL/dz   ← 计算损失
```
- 前向传播：**输入→输出**（做预测）
- 反向传播：**输出→输入**（更新权重）

### 链式法则的实际应用
```python
# 对于第l层:
# forward:  z[l] = W[l]·a[l-1] + b[l]
#           a[l] = activation(z[l])
#
# backward: dL/dW[l] = dL/da[l] · da[l]/dz[l] · dz[l]/dW[l]
#            ↓损失梯度   ↓激活的导数    ↓  a[l-1]
#             = δ[l]   ·                 a[l-1].T
# 其中 δ[l] = 从输出层传回来的"误差信号"
```

### 简单实现
```python
class TwoLayerNN:
    def forward(self, X):
        self.z1 = X @ self.W1 + self.b1     # 隐藏层
        self.a1 = np.maximum(0, self.z1)     # ReLU
        self.z2 = self.a1 @ self.W2 + self.b2  # 输出层
        self.a2 = 1/(1+np.exp(-self.z2))     # Sigmoid
        return self.a2
    
    def backward(self, X, y, lr):
        m = len(X)
        # 输出层梯度
        dz2 = self.a2 - y.reshape(-1, 1)     # sigmoid + CE的梯度
        dW2 = self.a1.T @ dz2 / m
        db2 = dz2.mean(axis=0)
        # 隐藏层梯度（通过转置回传）
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (self.z1 > 0)            # ReLU函数导数
        dW1 = X.T @ dz1 / m
        db1 = dz1.mean(axis=0)
        # 更新
        self.W1 -= lr * dW1
        self.W2 -= lr * dW2
```

## 初始化为什么重要

| 初始化方法 | 适用激活 | 原理 |
|-----------|---------|------|
| Xavier/Glorot | Sigmoid/Tanh | 方差=2/(n_in+n_out) |
| He/Kaiming | ReLU | 方差=2/n_in |
| 全零 | 不行 | 所有神经元对称，学到相同东西 |

**初始化不对=梯度消失/爆炸**

## 今日收获
- 一个神经元 = 逻辑回归，多个神经元堆叠 = 神经网络
- 反向传播 = 链式法则在计算图上的应用
- 激活函数的关键：引入非线性
- ReLU > Sigmoid/Tanh（解决了梯度消失，虽然带来死亡神经元）
- **XOR是"多层网络必要性"的经典例证**——单层无法解决（线性不可分），两层就够
