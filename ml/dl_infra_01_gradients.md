# 课时1：自动微分——深度学习框架的数学引擎

## 概述

自动微分（Automatic Differentiation, AD）是深度学习框架的核心基础。与数值微分（有限差分）和符号微分不同，自动微分通过将复杂函数分解为基本操作，并精确应用链式法则来计算导数。现代框架（PyTorch、TensorFlow、JAX）均基于反向模式自动微分实现梯度计算。

## 核心概念

### 1. 计算图与 Wengert 列表

**计算图**（Computation Graph）是自动微分的核心数据结构。它将复杂的数值计算表示为有向无环图（DAG），其中节点是操作（算子），边是数据依赖关系（张量流）。每个节点接收输入，产生输出，并保存足够的信息以在反向传播时计算梯度。

**Wengert 列表**（又称"求值踪迹"）是计算图的线性化表示。当我们前向执行程序时，框架记录下所有执行过的原始操作及其输入输出，形成一条线性序列。这个序列既包含了前向计算的结果，也包含了反向传播所需的所有中间状态。

区分两种计算图构建方式：

- **静态图（Define-and-Run）**：TensorFlow 1.x / Caffe。先定义完整的计算图，然后执行。优点是可以全局优化，缺点是调试困难。
- **动态图（Define-by-Run）**：PyTorch / TensorFlow Eager。每执行一次前向就构建一次图。灵活、易调试，但优化空间较小。

```python
# 计算图构建的简化模拟
class Tensor:
    def __init__(self, data, requires_grad=False):
        self.data = np.array(data, dtype=np.float32)
        self.grad = None
        self.requires_grad = requires_grad
        self._ctx = None  # 保存生成本张量的操作上下文
    
    def backward(self, grad_output=None):
        if grad_output is None:
            grad_output = np.ones_like(self.data)
        self.grad = grad_output
        
        # 按照 Wengert 列表的逆序执行反向传播
        if self._ctx is not None:
            # 调用保存的 forward 函数的 backward 方法
            grads = self._ctx.backward(grad_output)
            for t, g in zip(self._ctx.inputs, grads):
                if isinstance(t, Tensor) and t.requires_grad:
                    # 梯度累加：一个张量可能被多个下游节点使用
                    if t.grad is not None:
                        t.grad += g
                    else:
                        t.grad = g
                    t.backward(g)

class Add:
    @staticmethod
    def forward(a, b):
        out = Tensor(a.data + b.data, requires_grad=a.requires_grad or b.requires_grad)
        out._ctx = AddContext(a, b)
        return out

class AddContext:
    def __init__(self, a, b):
        self.inputs = [a, b]
    def backward(self, grad):
        # z = a + b  →  dz/da = 1, dz/db = 1
        return [grad, grad]

class Mul:
    @staticmethod
    def forward(a, b):
        out = Tensor(a.data * b.data, requires_grad=a.requires_grad or b.requires_grad)
        out._ctx = MulContext(a, b)
        return out

class MulContext:
    def __init__(self, a, b):
        self.inputs = [a, b]
    def backward(self, grad):
        # z = a * b  →  dz/da = b, dz/db = a
        return [grad * self.inputs[1].data, grad * self.inputs[0].data]
```

上例展示了二元操作（加法和乘法）的自动微分核心逻辑。关键在于每个操作都保存了它的前向上下文（`_ctx`），包含输入引用和反向函数。

### 2. 前向模式 vs 反向模式

自动微分有两种主要模式：

**前向模式（Forward Mode）**：同时计算函数值和导数。对每个输入变量维护一个"导数种子"，随前向传播一起传递。适合输入少、输出多的场景（如雅可比向量积，JVP）。

**反向模式（Reverse Mode）**：先计算函数值（前向传播），再反向传播梯度。适合输入多、输出少的场景（如标量损失函数对海量参数的梯度 —— 这正是深度学习需要的）。

| 特性 | 前向模式 | 反向模式 |
|------|----------|----------|
| 计算成本 | O(n) 次前向，n=输入维度 | O(1) 次前向 + O(1) 次反向 |
| 存储成本 | O(1) | O(n)（需保存中间激活值） |
| 适用场景 | 输入少、输出多 | 输入多、输出少 |
| 框架应用 | JAX 的 `jacfwd` | PyTorch/TF/JAX `grad` |

```python
# 前向模式自动微分的简化实现
class DualNumber:
    """对偶数的简单实现：x + ε * dx"""
    def __init__(self, val, deriv=0.0):
        self.val = val
        self.deriv = deriv
    
    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = DualNumber(other, 0.0)
        return DualNumber(
            self.val + other.val,
            self.deriv + other.deriv
        )
    
    def __mul__(self, other):
        if isinstance(other, (int, float)):
            other = DualNumber(other, 0.0)
        return DualNumber(
            self.val * other.val,
            self.deriv * other.val + self.val * other.deriv
        )

# 前向模式求导示例
x1 = DualNumber(2.0, 1.0)  # x1 的种子设为 1
x2 = DualNumber(3.0, 0.0)  # x2 的种子设为 0
y = x1 * x2 + x1
print(f"y.val = {y.val}, dy/dx1 = {y.deriv}")  # → y.val=9, dy/dx1=4

# 要同时求两个偏导，需执行两次前向传播
x1_2 = DualNumber(2.0, 0.0)  # x1 种子为 0
x2_2 = DualNumber(3.0, 1.0)  # x2 种子为 1
y2 = x1_2 * x2_2 + x1_2
print(f"dy/dx2 = {y2.deriv}")  # → dy/dx2=2
```

### 3. 梯度累加（Gradient Accumulation）

当一个张量作为多个下游操作的输入时，其梯度来自多条路径。这就是多变量链式法则中的求和：

$$\frac{\partial L}{\partial x} = \sum_{i} \frac{\partial L}{\partial f_i} \cdot \frac{\partial f_i}{\partial x}$$

反向传播必须将这些梯度**累加**（不是覆盖）。这在以下场景尤为重要：

- **多分支网络**：如 ResNet 的跳跃连接
- **梯度累积训练**：模拟更大的 batch size

```python
# 梯度累积的两种场景

# 场景1：计算图中的 Fan-out（一个张量被多个操作使用）
def gradient_accumulation_demo():
    """模拟 ResNet 跳跃连接中的梯度累加"""
    x = Tensor(np.array([1.0, 2.0, 3.0]), requires_grad=True)
    
    # 主路径
    a = linear(x, W1)  
    b = relu(a)
    
    # 跳跃连接 —— x 同时流入两个分支
    c = linear(x, W2)   # x 的第二个使用者
    d = linear(b, W3)
    
    y = c + d
    loss = y.sum()
    loss.backward()
    
    # x.grad 应该是两个分支梯度的和
    # d(loss)/dx = d(c)/dx + d(d)/db * d(b)/da * d(a)/dx
    print(f"x.grad = {x.grad}")  # 已经累加了两个路径的梯度

# 场景2：训练时的梯度累积（模拟更大的 batch size）
class GradientAccumulator:
    """
    小 batch 训练，累积多次梯度后统一更新参数。
    适用于 GPU 显存不足以容纳大 batch 的情况。
    """
    def __init__(self, model, accumulation_steps=4):
        self.model = model
        self.acc_steps = accumulation_steps
        self.step_count = 0
    
    def backward_and_accumulate(self, loss):
        # 反向传播：梯度会自动累加到 .grad 属性
        loss.backward()
        self.step_count += 1
        
        if self.step_count % self.acc_steps == 0:
            # 累积到足够步数后，执行参数更新
            for param in self.model.parameters():
                param.data -= 0.01 * param.grad
                # 手动归零梯度（准备下一轮累积）
                param.grad = None
```

## 实用技巧

### 检查点（Checkpointing）与内存权衡

反向模式自动微分需要在内存中保存所有中间激活值，内存消耗与计算图深度成正比。梯度检查点技术通过"丢弃部分中间结果，反向传播时重算"来交换时间换空间：

```python
class CheckpointWrapper:
    """
    梯度检查点的朴素实现：
    前向时不保存中间值，反向时重新执行前向以恢复中间值。
    """
    def __init__(self, fn):
        self.fn = fn
        self.saved_input = None
    
    def forward(self, x):
        self.saved_input = x
        return self.fn(x)
    
    def backward(self, grad_output):
        # 重新执行前向来重建计算图
        x = self.saved_input
        with enable_grad():
            out = self.fn(x)
            # 重建的图和原来的图结构完全一致
        return torch.autograd.grad(out, x, grad_output)
```

**权衡总结**：
- 无检查点：前向 O(n) 时间，O(n) 内存，反向 O(n) 时间
- 有检查点：前向 O(n) 时间，O(√n) 内存，反向 O(n+√n) 时间
- PyTorch 提供 `torch.utils.checkpoint.checkpoint()` API

## 延伸阅读

- [Automatic Differentiation in Machine Learning: a Survey (Baydin et al., 2018)](https://arxiv.org/abs/1502.05767)
- PyTorch Autograd 源码：`torch/csrc/autograd/`
- JAX 自动微分文档：https://jax.readthedocs.io/en/latest/autodidax.html

## 关键总结

1. **计算图**是自动微分的骨架，节点是算子，边是数据流
2. **Wengert 列表**记录前向执行的操作序列，反向沿逆序回传梯度
3. **反向模式**是深度学习的默认选择（输出标量、参数多）
4. **梯度累加**是多路径链式法则的必然结果，框架自动处理
5. **内存和时间的权衡**是优化自动微分性能的核心课题
