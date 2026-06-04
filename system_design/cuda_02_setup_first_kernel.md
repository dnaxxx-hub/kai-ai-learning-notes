# CUDA 02 — 环境搭建与第一个 CUDA Kernel

## 环境

- **显卡**：NVIDIA RTX 5070Ti (Blackwell)
- **驱动**：595.97（CUDA 13.2 兼容）
- **Python**：3.14（PyTorch CUDA 暂不支持，使用 numba 或 pycuda）

## 方案选择

| 方案 | 工具 | 适合场景 |
|------|------|----------|
| **numba** | `from numba import cuda` | Python 生态，写 CUDA 内核 |
| **pycuda** | `pycuda.compiler.SourceModule` | 裸 CUDA C 内核，Python 包装 |
| **cupy** | `cupy.array` | NumPy 替代，自动 GPU |
| **nvcc + Python ctypes** | 编译 .cu → .dll → Python | 最高性能 |

## numba CUDA 测试

```python
from numba import cuda
import numpy as np

@cuda.jit
def vector_add(a, b, c):
    idx = cuda.grid(1)
    if idx < a.size:
        c[idx] = a[idx] + b[idx]

# 数据
n = 1024 * 1024
a = np.random.randn(n).astype(np.float32)
b = np.random.randn(n).astype(np.float32)
c = np.zeros_like(a)

# 拷贝到设备
d_a = cuda.to_device(a)
d_b = cuda.to_device(b)
d_c = cuda.device_array_like(c)

# 启动 kernel
threads_per_block = 256
blocks_per_grid = (n + threads_per_block - 1) // threads_per_block
vector_add[blocks_per_grid, threads_per_block](d_a, d_b, d_c)

# 拷回主机
d_c.copy_to_host(c)

# 验证
assert np.allclose(c, a + b)
print(f"✅ 向量加法验证通过，{n} 个元素")
```

## 性能对比基准

| 操作 | CPU (Python) | CPU (NumPy) | GPU (CUDA) | 加速比 |
|------|-------------|-------------|------------|--------|
| 向量加法 1M | ~50ms | ~2ms | ~0.1ms | 20-500x |
| 矩阵乘法 1000x1000 | ~500ms | ~10ms | ~0.5ms | 20-1000x |
| 规约求和 1M | ~30ms | ~1ms | ~0.05ms | 20-600x |

> 注意：小数据量 GPU 无优势（数据搬运开销 > 计算加速）

## 常见错误

1. **CUDA_ERROR_OUT_OF_MEMORY**：显存不够，降低 batch size
2. **CUDA_ERROR_ILLEGAL_ADDRESS**：越界访问，检查 `if (idx < n)`
3. **kernel 没报错但结果不对**：没同步 `cuda.synchronize()`
4. **numba 不支持的操作**：如字符串、动态内存分配
