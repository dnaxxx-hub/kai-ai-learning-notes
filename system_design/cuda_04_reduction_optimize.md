# CUDA 04 — 规约（Reduction）与优化技巧

## 什么是规约

将一个数组聚合为单值：求和、求最大值、点积等。

**串行**：O(n)
**并行**：O(log n) 树形规约

## 基础实现

```python
@cuda.jit
def reduce_sum(arr, out):
    """Tree reduction: 每个 block 归约自己的部分"""
    sdata = cuda.shared.array(256, dtype=np.float32)
    tid = cuda.threadIdx.x
    bid = cuda.blockIdx.x
    bidx = cuda.blockDim.x
    
    idx = bid * bidx + tid
    sdata[tid] = arr[idx] if idx < arr.size else 0.0
    cuda.syncthreads()
    
    # Tree reduction
    s = bidx // 2
    while s > 0:
        if tid < s:
            sdata[tid] += sdata[tid + s]
        cuda.syncthreads()
        s //= 2
    
    if tid == 0:
        out[bid] = sdata[0]
```

## 优化技巧

### 1. 减少 warp divergence

```python
# ❌ 如果 bidx 不是 2 的幂，某些线程会在中间层空闲
# ✅ 使用整块连续线程
s = bidx // 2
while s > 0:
    if tid < s:
        sdata[tid] += sdata[tid + s]
    cuda.syncthreads()
    s //= 2
```

关键在于 `tid < s` 的判断 — 每次迭代只有前 s 个线程活跃，减少分支。

### 2. 避免 bank conflict

```python
# 将 sdata[tid] 和 sdata[tid + s] 的访问设计到不同 bank
# 跨步 s 为 2 的幂时，tid 和 tid + s 通常在同一个 warp 内不同 bank
```

### 3. 展开循环（Unrolling）

```python
@cuda.jit
def reduce_unrolled(arr, out):
    sdata = cuda.shared.array(256, dtype=np.float32)
    tid = cuda.threadIdx.x
    idx = cuda.blockIdx.x * cuda.blockDim.x * 4 + tid  # 每个线程处理4个元素
    
    # 每个线程积攒4个元素
    acc = 0.0
    for i in range(4):
        if idx + i * cuda.blockDim.x < arr.size:
            acc += arr[idx + i * cuda.blockDim.x]
    sdata[tid] = acc
    cuda.syncthreads()
    
    s = cuda.blockDim.x // 2
    while s > 0:
        if tid < s:
            sdata[tid] += sdata[tid + s]
        cuda.syncthreads()
        s //= 2
    
    if tid == 0:
        out[cuda.blockIdx.x] = sdata[0]
```

### 4. 多级规约

第一次：每个 block 归约到单个值
第二次：CPU 或单 block 归约 block 结果

```python
# 第一次：n 个 block → n 个值
reduce_sum[n_blocks, 256](arr, partial)
# 第二次：n 个值 → 1 个值
reduce_sum_one_block[1, 256](partial, result)
# 或直接在 CPU 上对 n 个值求和
```

## 性能对比（预计）

| 方法 | 时间(1M元素) | 加速比 vs Python |
|------|:----------:|:--------------:|
| Python loop | ~30ms | 1x |
| Numpy sum | ~1ms | 30x |
| CUDA (naive) | ~0.1ms | 300x |
| CUDA (optimized) | ~0.03ms | 1000x |

> 实测数据需要你 5070Ti 跑一下才知道真正数字
