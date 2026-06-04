# 信息论基础：熵、交叉熵与KL散度

> 日期：2026-05-07 13:00 | 课程：ML/DL路线 Phase 1-4
> 目标：理解信息论为什么是分类损失和模型蒸馏的底层逻辑

## 核心直觉

信息论回答三个ML关键问题：
1. 一个事件包含多少信息？ → **信息量**
2. 一个系统的不确定性多大？ → **熵**
3. 两个分布有多"远"？ → **KL散度**

## 三个核心概念

### 1. 信息量 — I(x) = -log₂ P(x)
- **越不可能的事件，信息量越大**
- 必然事件（P=1）：信息量=0
- 二分硬币（P=0.5）：1 bit
- 完全意外（P=0.001）：~10 bits
- 单位选择：log₂ → bits，ln → nats

### 2. 熵 — H(X) = -Σ P(x)·log₂ P(x)
- **系统的平均信息量 = 不确定性度量**
- 二分类：P=0.5 时熵最大（1 bit）→ 完全不确定
- P=0.999时熵≈0 → 几乎确定
- 意义：分类任务中，当模型不确定时（输出≈0.5→0.5），熵高，loss大

### 3. KL散度 — KL(P||Q) = Σ P(x)·log(P(x)/Q(x))
- **衡量预测分布Q离真实分布P有多远**
- KL≥0恒成立，P=Q时KL=0
- 不对称：KL(P||Q) ≠ KL(Q||P)
- 意义：知识蒸馏（Distillation）中用KL散度让student模仿teacher的分布

### 4. 交叉熵 — H(P,Q) = -Σ P(x)·log Q(x)
```
H(P,Q) = H(P) + KL(P||Q)
       = 真实熵 + 预测误差
```
- 分类任务中，P是one-hot（熵=0）
- **所以交叉熵 = KL散度**（因为H(P)=0）
- **最小化交叉熵 = 最小化KL散度**
- **最小化KL散度 = 最大似然估计（MLE）**

## 可视化解释

![信息论](04_information_theory.png)

**左图**：概率vs信息量——越罕见的事件携带越多信息
**中图**：二分类熵——P=0.5时最不确定（熵最大1bit）
**右图**：交叉熵与KL散度对比
- 预测好(good)时：CE=0.15, KL=0.15（接近0）
- 预测差(bad)时：CE=1.32, KL=1.32（相差很大）
- 实际交叉熵 = KL散度（因为真实分布是one-hot，H(P)=0）

## 在ML中的具体位置

### 交叉熵损失（分类任务的标准选择）
```python
# PyTorch中 nn.CrossEntropyLoss 实际上做了两件事：
# 1. Softmax: 将logits转为概率分布
# 2. 交叉熵: -Σ y_true · log(y_pred)
# 
# 等价于：LogSoftmax + NLLLoss

loss = -np.sum(y_true * np.log(softmax(logits) + 1e-8))
```

### 知识蒸馏
```python
# Teacher输出的概率分布（软标签）比one-hot包含更多信息
# Student不仅要拟合真实标签，还要拟合Teacher的分布
# KL散度衡量Student分布和Teacher分布的差异
loss = alpha * CE(student, true_labels) + \
       (1-alpha) * KL(soft(student/T), soft(teacher/T))
```

### 变分自编码器（VAE）
```python
# VAE的损失 = 重构损失 + KL散度
# KL(q(z|x) || p(z))：让编码后的隐变量接近先验
# 这是"正则化"，防止隐空间坍塌
```

## 纯numpy实现

```python
import numpy as np

def entropy(p):
    p = np.clip(p, 1e-10, 1)
    return -np.sum(p * np.log2(p))

def cross_entropy(y_true, y_pred):
    y_pred = np.clip(y_pred, 1e-10, 1)
    return -np.sum(y_true * np.log2(y_pred))

def kl_divergence(p, q):
    p, q = np.clip(p, 1e-10, 1), np.clip(q, 1e-10, 1)
    return np.sum(p * np.log2(p / q))

# 验证：one-hot 真值下 CE = KL
y_true = np.array([1, 0, 0])
y_pred = np.array([0.8, 0.15, 0.05])
print(entropy(y_true))       # ≈ 0（one-hot的熵=0）
print(cross_entropy(y_true, y_pred))  # ≈ 0.32
print(kl_divergence(y_true, y_pred))  # ≈ 0.32
```

## 与ML的关键连接

| 信息论概念 | ML中位置 |
|-----------|---------|
| 信息量 | 直观理解罕见事件 |
| 熵 | 决策树分裂（信息增益）、模型不确定性 |
| 交叉熵 | **分类损失函数（几乎都用它）** |
| KL散度 | VAE损失、知识蒸馏、GAN |
| 互信息 | 特征选择、ICA独立成分分析 |

## 今日收获
- **交叉熵 = 分类器的默认损失**，本质是MLE视角+信息论视角
- KL散度衡量两个分布的差异，不对称但有界
- one-hot标签的熵=0，所以此时交叉熵=KL散度
- 信息论把"不确定性"变成了可计算的数学量
- **所有的分类模型训练 = 缩小预测分布和真实分布的KL散度**
