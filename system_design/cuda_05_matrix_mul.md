# CUDA 05 — 矩阵乘法（经典优化案例）

矩阵乘法 M × N = P 对 GPU 来说是最经典的 benchmark。

## 朴素实现

```python
@cuda.jit
def matmul_naive(A, B, C):
    """C = A @ B, 每个线程算一个元素"""
    row, col = cuda.grid(2)
    if row < A.shape[0] and col < B.shape[1]:
        total = 0.0
        for k in range(A.shape[1]):
            total += A[row, k] * B[k, col]
        C[row, col] = total
```

**问题**：每个线程独立从全局内存读取 A 的行和 B 的列，全局内存带宽成为瓶颈。

## 共享内存分块（Tiled）

```python
TILE_SIZE = 16

@cuda.jit
def matmul_tiled(A, B, C):
    """分块矩阵乘法：利用共享内存减少全局内存访问"""
    # 共享内存 tiles
    sA = cuda.shared.array((TILE_SIZE, TILE_SIZE), dtype=np.float32)
    sB = cuda.shared.array((TILE_SIZE, TILE_SIZE), dtype=np.float32)
    
    row = cuda.blockIdx.y * TILE_SIZE + cuda.threadIdx.y
    col = cuda.blockIdx.x * TILE_SIZE + cuda.threadIdx.x
    
    total = 0.0
    n_tiles = (A.shape[1] + TILE_SIZE - 1) // TILE_SIZE
    
    for t in range(n_tiles):
        # 协作加载 tile 到共享内存
        if row < A.shape[0] and t * TILE_SIZE + cuda.threadIdx.x < A.shape[1]:
            sA[cuda.threadIdx.y, cuda.threadIdx.x] = A[row, t * TILE_SIZE + cuda.threadIdx.x]
        else:
            sA[cuda.threadIdx.y, cuda.threadIdx.x] = 0.0
        
        if col < B.shape[1] and t * TILE_SIZE + cuda.threadIdx.y < B.shape[0]:
            sB[cuda.threadIdx.y, cuda.threadIdx.x] = B[t * TILE_SIZE + cuda.threadIdx.y, col]
        else:
            sB[cuda.threadIdx.y, cuda.threadIdx.x] = 0.0
        
        cuda.syncthreads()  # 确保 tile 加载完成
        
        # 计算这个 tile 的部分积
        for k in range(TILE_SIZE):
            total += sA[cuda.threadIdx.y, k] * sB[k, cuda.threadIdx.x]
        
        cuda.syncthreads()  # 确保 tile 使用完再被覆盖
    
    if row < C.shape[0] and col < C.shape[1]:
        C[row, col] = total
```

**核心优化**：每个元素从全局内存读 1 次，被 TILE_SIZE 个线程复用。

## 进一步优化

### 1. 向量化加载

```python
# 用 float4 一次加载 4 个 float
@cuda.jit
def matmul_vec4(A, B, C):
    # ... 基本逻辑同上，但加载使用 float4
```

### 2. Bank Conflict 避免

共享内存每行 16 个 float = 64 字节，32 个 bank 每 bank 4 字节。
- `sA[ty, tx]` 访问模式：同一 warp 的不同 tx → 不同 bank ✅
- `sB[ty, tx]` 同理 ✅

### 3. 双缓冲

```python
# 用两块共享内存交替加载
sA0, sA1 = shared.array(...), shared.array(...)
# 流水线：计算当前 tile 的同时加载下一个 tile
```

## 性能预期（1000×1000 矩阵）

| 方法 | 时间 | GFLOPS |
|------|:----:|:------:|
| CPU NumPy | ~10ms | ~200 |
| CUDA Naive | ~5ms | ~400 |
| CUDA Tiled 16×16 | ~1ms | ~2000 |
| CUDA Tiled 32×32 | ~0.5ms | ~4000 |
| cuBLAS (库实现) | ~0.3ms | ~6700 |

> 5070Ti 黑架构应该有更高数字
