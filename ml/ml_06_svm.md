# SVM：从最大间隔到核技巧

> 日期：2026-05-07 14:00 | 课程：ML/DL路线 Phase 2-2
> 目标：理解SVM"用一条尽可能宽的马路分开两类数据"

## 核心直觉

### SVM的哲学
> **不是找一个能分开的线，而是找一个分开得最开的线**

- 线性回归：最小化预测误差
- 逻辑回归：最大化似然
- **SVM：最大化间隔（Margin）**

### 间隔（Margin）
- 间隔 = 决策边界到最近数据点的距离
- **大间隔 = 更好的泛化能力**
- 离边界最近的那些点 = **支持向量（Support Vectors）**

## 三种情况

### 1. 硬间隔（Perfectly Separable）
```
数据线性可分 → 严格让所有点都在margin外
最大化: margin = 2/||w||
约束: y_i(w·x_i + b) ≥ 1  对所有i
```
这是SVM的原始形式，但现实中很少能用。

### 2. 软间隔（Soft Margin）— 最常用
```
允许一些点越过margin（甚至越过决策边界）
引入松弛变量 ξ_i ≥ 0 表示"违规程度"
目标: margin + C·sum(ξ_i)
```
- C 控制惩罚强度
- C大 → 严格分类（可能过拟合）
- C小 → 允许更多错误（泛化更好）

### 3. 核技巧（Kernel Trick）— 非线性
```
数据不是线性可分 → 映射到高维空间再分

常用核函数:
- 线性核: K(x,z) = x·z
- 多项式核: K(x,z) = (x·z + c)^d
- RBF核: K(x,z) = exp(-γ||x-z||²)  ← 最常用
```

**核技巧的魔法**：不需要真的把数据映射到高维，只需要计算**核函数**。因为SVM的优化只依赖**点积**，而核函数可以隐式给出高维空间的点积。

## 可视化

![SVM决策边界](06_svm.png)

- **实线**：决策边界（最大间隔超平面）
- **虚线**：margin边界
- **黄色圈**：支持向量（决定边界的关键点）
- **绿色/红色点**：两类数据

注意：只有黄色圈起来的点决定了边界的位置，其他点移动了也不影响。

## 纯numpy实现

```python
import numpy as np

class SVM:
    def __init__(self, C=1.0, lr=0.001, steps=5000):
        self.C = C
        self.lr = lr
        self.steps = steps
    
    def fit(self, X, y):
        # 用次梯度下降训练SVM
        n, d = X.shape
        self.w = np.zeros(d)
        self.b = 0.0
        
        for _ in range(self.steps):
            margins = y * (X @ self.w + self.b)
            mask = margins < 1  # 只有这些点贡献梯度
            grad_w = self.w - self.C * (X[mask] * y[mask, None]).sum(axis=0) / n
            grad_b = -self.C * y[mask].sum() / n
            self.w -= self.lr * grad_w
            self.b -= self.lr * grad_b
    
    def predict(self, X):
        return np.sign(X @ self.w + self.b)
```

## 与ML的关键连接

| 概念 | SVM中的作用 | DL中的类似物 |
|------|------------|-------------|
| 间隔最大化 | SVM核心目标 | 对比学习(Contrastive) |
| Hinge Loss | 目标函数 | Hinge loss用在某些NN中 |
| 支持向量 | 关键数据点 | Attention的key tokens |
| 核技巧 | 隐式高维映射 | 深层网络=显式的逐层映射 |
| 对偶问题 | 高效求解 | 某些优化器使用 |

## 今日收获
- SVM = 找一条**最宽的马路**分开两类数据
- 支持向量 = 离边界最近的点，**只有它们决定边界**
- 软间隔 = 容忍一些错误（C参数控制容忍度）
- 核技巧 = 把数据映射到高维，但不需要真的计算映射
- **SVM在深度学习兴起前是最好的通用分类器**
- 逻辑回归输出概率，SVM输出距离边界的"信心分数"
