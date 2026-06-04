# CUDA 03 — 内存模型与优化

## 内存层次详解

### 1. 全局内存 (Global Memory)

- 最大（GB级），最慢（~400-900 GB/s 带宽）
- 所有线程可读写
- 需要 `cuda.memcpy` 或 `cuda.to_device` 显式传数据
- 优化核心：**Memory Coalescing**

### 2. 共享内存 (Shared Memory)

- Block 内所有线程共享
- 速度接近寄存器（~TB/s）
- 容量小（48KB/SM 默认，可配置到 164KB）
- 典型用途：block内数据复用、规约

```python
@cuda.jit
def shared_memory_example(arr):
    tid = cuda.threadIdx.x
    bid = cuda.blockIdx.x
    bidx = cuda.blockDim.x
    
    # 声明共享内存（大小在编译时确定）
    sdata = cuda.shared.array(256, dtype=np.float32)
    
    # 加载到共享内存
    sdata[tid] = arr[bid * bidx + tid]
    cuda.syncthreads()  # 同步：所有线程加载完成
    
    # 使用共享内存做计算...
```

### 3. 寄存器 (Registers)

- 每个线程私有
- 零延迟
- 每个 SM 寄存器总数有限（~65536）
- 每个线程分到的寄存器数 = 总数 / (block数 × thread数)
- 太多局部变量 → 寄存器溢出到本地内存（变慢）

### 4. 常量内存 (Constant Memory)

- 只读，64KB
- 有缓存（constant cache）
- 适合所有线程访问相同数据的场景

```python
# 声明常量（编译时确定大小）
@cuda.jit
def kernel_with_const(arr):
    # 直接用字面量
    if arr[cuda.grid(1)] > 3.14:
        arr[cuda.grid(1)] = 0
```

### 5. 本地内存 (Local Memory)

- 线程私有的后备内存（实际在全局内存中）
- 寄存器溢出时自动使用
- 性能差，要避免

## 优化模式

### Memory Coalescing

```python
# ❌ 非合并访问（跨步访问，带宽损失严重）
@cuda.jit
def bad_access(mat):
    x, y = cuda.grid(2)
    val = mat[y * 1024 + x]  # OK，行主序连续
    # 但下面的访问跨步...
    
# ✅ 合并访问：连续线程访问连续地址
@cuda.jit
def good_access(arr):
    idx = cuda.grid(1)
    if idx < arr.size:
        val = arr[idx]  # 完美合并
```

### 共享内存 Bank Conflict

- 共享内存被分为 32 个 bank（4字节/ bank）
- 同一 warp 多个线程访问同一 bank → 冲突串行化
- **无冲突条件**：每个线程访问不同 bank
- `cuda.shared.array` 默认 4 字节对齐

### Occupancy 优化

Occupancy = 活跃 warp 数 / SM 最大 warp 数

影响因素：
1. **每线程寄存器数**：寄存器多 → 活跃线程少
2. **共享内存用量**：共享内存大 → block 数少
3. **block 大小**：太小则 warp 数不够，太大则受寄存器/共享内存限制

```python
# 通过调整 block 大小优化 occupancy
block_sizes = [64, 128, 256, 512, 1024]
for bs in block_sizes:
    # 实测性能
    kernel[grid_size, bs](data)
```

## 性能分析三件套

1. **numba.cuda.profile_start() / stop()**：基本计时
2. **nvidia-smi**：显存占用、GPU 利用率
3. **Nsight (NVIDIA Nsight Systems)**：详细 profiling
