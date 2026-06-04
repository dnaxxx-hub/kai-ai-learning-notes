# 课时2：算子注册与内核——框架的计算积木

## 概述

深度学习框架中，**算子（Operator）**是计算图的基本组成单元。每个算子对应一种数学操作（如卷积、矩阵乘法、激活函数），而**内核（Kernel）**是算子在特定硬件上的具体实现。本课深入探讨算子注册机制、内存布局对性能的影响、广播语义以及融合算子的设计。

## 核心概念

### 1. 算子注册机制与 NYC（Not Your Common）

现代深度学习框架的一个重要特征是**解耦算子定义与内核实现**。算子注册系统允许框架在运行时根据输入张量的设备类型、数据类型自动派发到合适的核函数。

**三层抽象架构**：

```
API 层（Python）         →  torch.nn.functional.conv2d(...)
算子定义层（C++ Schema）  →  OperatorSchema { name, inputs, outputs }
内核实现层（Kernel）      →  ConvKernel<CUDA, float>, ConvKernel<CPU, float>
```

**算子注册模式**（以 PyTorch 为例）：

```python
# 简化版算子注册系统的概念演示

# 1. 全局算子注册表
class OpRegistry:
    def __init__(self):
        self._schemas = {}       # op_name → Schema
        self._kernels = {}       # op_name → { (device, dtype): Kernel }
    
    def register_op(self, schema):
        self._schemas[schema.name] = schema
    
    def register_kernel(self, op_name, device, dtype, kernel_fn):
        if op_name not in self._kernels:
            self._kernels[op_name] = {}
        self._kernels[op_name][(device, dtype)] = kernel_fn
    
    def dispatch(self, op_name, *inputs, device='cpu', dtype='float32'):
        """运行时派发：根据设备和数据类型选择合适的内核"""
        kernel = self._kernels.get(op_name, {}).get((device, dtype))
        if kernel is None:
            raise RuntimeError(f"No kernel for {op_name} on {device}/{dtype}")
        return kernel(*inputs)

registry = OpRegistry()

# 注册一个 ReLU 算子
registry.register_op({
    'name': 'relu',
    'inputs': [('input', 'tensor')],
    'outputs': [('output', 'tensor')],
})

# 注册 CPU 和 CUDA 内核
@registry.register_kernel('relu', 'cpu', 'float32')
def relu_cpu(x):
    return np.maximum(0, x)

@registry.register_kernel('relu', 'cuda', 'float32')
def relu_cuda(x):
    # 实际会调用 CUDA kernel (cuda.relu)
    return cuda.relu(x)
```

**Not Your Common（NYC）** 指的是寄存器（Register）/ NYC 在编译优化中的应用：
- 在 CUDA kernel 中，充分使用寄存器存储中间结果，减少全局内存访问
- 在算子注册系统中，"NYC" 也暗示高效的内存访问模式和缓存友好的数据布局

### 2. 内存布局与 Strides

张量在内存中的存储方式对性能有决定性的影响。**Stride**（步幅）是描述张量维度到内存偏移量的映射：对于形状为 (d₀, d₁, ..., dₙ₋₁) 的张量，其 strides 是一个长度为 n 的数组 s，元素 s[i] 表示沿维度 i 增加一个索引时，在内存中需要跳过的元素数。

```
元素 (i₀, i₁, ..., iₙ₋₁) 的偏移量 = Σ iⱼ · sⱼ
```

**行优先（Row-Major / C-style）** 是 Python/Numpy/PyTorch 的默认布局：
```python
shape = (3, 4)
row_major_strides = (4, 1)  # 先走完一行（4个元素），才换行
```

**列优先（Column-Major / Fortran-style）**：
```python
col_major_strides = (1, 3)  # 先走完一列（3个元素），才换列
```

**strides 的魔力**：通过调整 strides 可以实现零拷贝的视图操作（transpose、slice、squeeze 等）：

```python
class TensorStridesDemo:
    """演示 strides 如何实现高效视图操作"""
    
    @staticmethod
    def transpose_view(x, dim0=0, dim1=1):
        """转置：交换两个维度的 stride，无需复制数据"""
        new_strides = list(x.strides)
        new_strides[dim0], new_strides[dim1] = new_strides[dim1], new_strides[dim0]
        
        # 创建视图张量（共享底层数据）
        new_shape = list(x.shape)
        new_shape[dim0], new_shape[dim1] = new_shape[dim1], new_shape[dim0]
        
        return ViewTensor(x.data_ptr, new_shape, new_strides)
    
    @staticmethod
    def slice_view(x, dim, start, end):
        """切片：调整起始偏移量和对应维度的长度"""
        # 计算起始偏移量
        offset = start * x.strides[dim]
        new_shape = list(x.shape)
        new_shape[dim] = end - start
        
        return ViewTensor(x.data_ptr + offset, new_shape, x.strides)
    
    @staticmethod
    def broadcast_strides(shape_a, shape_b):
        """计算广播后的 strides"""
        # 广播：维度为 1 的轴对应的 stride 为 0（读取时在该维度重复）
        strides_a = list(shape_a_to_strides(shape_a))
        strides_b = list(shape_b_to_strides(shape_b))
        
        # 对齐维度
        while len(strides_a) < len(shape_b):
            strides_a.insert(0, 0)  # 新插入维度 strides=0
        while len(strides_b) < len(shape_a):
            strides_b.insert(0, 0)
        
        return strides_a, strides_b
```

**Contiguous 与非 Contiguous 张量**：当 transpose/slice 等操作创建了非连续内存视图时，很多 CUDA kernel 不能直接处理。需要使用 `contiguous()` 创建一份内存连续拷贝。

### 3. 广播语义（Broadcasting）

广播是让形状不同的张量进行运算的机制。Numpy 和 PyTorch 遵循相同的广播规则：

**规则**：
1. 从尾部维度开始对齐
2. 两个维度相等，或其中一个为 1，或其中一个缺失
3. 维度为 1 的轴会被"复制"以匹配对方

```python
def broadcast_shapes(shape_a, shape_b):
    """计算两个张量广播后的形状"""
    result = []
    # 从尾部开始对齐
    for dim_a, dim_b in zip(reversed(shape_a), reversed(shape_b)):
        if dim_a == dim_b:
            result.append(dim_a)
        elif dim_a == 1 or dim_b == 1:
            result.append(max(dim_a, dim_b))
        else:
            raise ValueError(f"Shapes {shape_a} and {shape_b} are not broadcastable")
    
    # 处理未对齐的剩余维度
    remaining = len(shape_a) if len(shape_a) > len(shape_b) else len(shape_b)
    longer_shape = shape_a if len(shape_a) > len(shape_b) else shape_b
    extra_dims = longer_shape[:len(longer_shape) - len(result)]
    
    return tuple(extra_dims + tuple(reversed(result)))

# 广播示例
# A: (3, 1, 5)  B: (4, 1)  →  Result: (3, 4, 5)
# (3, 1, 5)     →  广播后 (3, 4, 5)
#    (4, 1)     →  广播后 (3, 4, 5)
```

**隐式广播的代价**：广播不复制内存（strides=0），但在实际计算时，CUDA kernel 需要处理 strides=0 的情况，导致额外的地址计算开销。

### 4. 融合算子（Fused Operators）

融合算子是框架优化的核心手段。将多个连续的操作合并为一个 kernel 执行，可以显著减少：
1. **内核启动开销**：每个 CUDA kernel 启动都有固定开销（~5-10μs）
2. **全局内存访问**：减少中间结果在全局内存的读写

```python
# 融合算子 vs 分离执行

def unfused_forward(x, w, b):
    """分离执行：4次 kernel 启动 + 2次中间张量读写"""
    # Kernel 1: matmul  →  temp1 (写回全局内存)
    temp1 = torch.matmul(x, w)
    # Kernel 2: add     →  temp2
    temp2 = temp1 + b
    # Kernel 3: relu    →  temp3
    temp3 = torch.relu(temp2)
    # Kernel 4: softmax →  output
    output = torch.softmax(temp3, dim=-1)
    return output

def fused_forward(x, w, b):
    """
    融合执行：1次 kernel 启动，无中间张量。
    所有操作在寄存器/共享内存中完成。
    """
    # 手写融合 CUDA kernel 的示意
    cuda_fused_linear_relu_softmax(x, w, b)

# 融合 kernel 的 CUDA 伪代码
CUDA_KERNEL_FUSED = """
__global__ void fused_linear_relu_softmax(
    float* x, float* w, float* b, float* out,
    int M, int N, int K  // x: [M,K], w: [K,N]
) {
    // 每个线程计算输出矩阵中的一个元素
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    int col = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (row >= M || col >= N) return;
    
    // 计算线性层（保持在寄存器中）
    float sum = 0.0f;
    for (int k = 0; k < K; k++) {
        sum += x[row * K + k] * w[k * N + col];
    }
    sum += b[col];  // 加偏置
    
    // ReLU（在寄存器中）
    sum = max(0.0f, sum);
    
    // 注意：softmax 需要跨行通信，通常使用 warp shuffle 或共享内存
    // 这里简化处理，实际需要先写入共享内存计算整个行的 softmax
    out[row * N + col] = sum;  // 可进一步优化为 softmax 计算
}
"""
```

**框架层次的融合策略**：

| 框架 | 融合方式 |
|------|---------|
| PyTorch JIT | `torch.jit.script` → 图级别的算子融合 |
| TorchScript + NNC | 针对 CPU 的循环融合（Tea协议） |
| TorchInductor | PyTorch 2.0 编译器，自动融合 Triton kernel |
| TensorRT | 构建时为推理图做层融合 |
| TVM | AutoTVM 搜索最优融合策略 |

## 实用技巧

### 手写融合算子的负载均衡

融合算子设计时需要特别注意寄存器压力和内存带宽的平衡：

```python
def analyze_register_pressure(ops, reg_per_thread=255):
    """
    分析融合算子是否超出 GPU 寄存器限制。
    超出时会发生"寄存器溢出"（register spill），
    性能显著下降。
    """
    estimated_regs = 0
    for op in ops:
        if op == 'matmul':
            estimated_regs += 8  # 累加器+Ktiles
        elif op == 'relu':
            estimated_regs += 0  # 原地操作
        elif op == 'softmax':
            estimated_regs += 4  # 临时统计量
    
    if estimated_regs > reg_per_thread:
        print(f"警告：估计 {estimated_regs} 寄存器，超出上限 {reg_per_thread}")
        print("GPU 会将溢出寄存器存储到 local memory（L1缓存），延迟增加 10-20x")
    
    return estimated_regs
```

### 使用 torch.compile 自动融合

```python
# PyTorch 2.0+ 编译器自动处理算子融合
@torch.compile
def compiled_forward(x, w, b):
    return torch.softmax(torch.relu(x @ w + b), dim=-1)

# torch.compile 内部会：
# 1. 捕获计算图（TorchDynamo）
# 2. 应用融合优化（分析哪些 op 可以合并）
# 3. 生成 Triton/TorchInductor kernel
```

## 延伸阅读

- [PyTorch Custom Operators Tutorial](https://pytorch.org/tutorials/advanced/custom_ops_tutorial.html)
- [NVIDIA CUDA C++ Best Practices Guide - Memory Access Patterns](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
- [TVM Tensor Expression and AutoTVM](https://tvm.apache.org/docs/tutorials/autotvm/tune_relay_x86.html)

## 关键总结

1. **算子注册系统**将算子定义与内核实现解耦，支持灵活的 device/dtype 派发
2. **Strides** 是非连续视图操作的核心机制，transpose/slice 等操作通过修改 strides 实现零拷贝
3. **广播** 通过 strides=0 避免内存复制，但可能带来计算开销
4. **融合算子** 是性能优化的黄金策略：减少 kernel 启动次数和全局内存带宽消耗
5. **寄存器压力** 是融合算子设计中必须考虑的关键约束
