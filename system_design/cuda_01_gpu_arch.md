# CUDA 01 — GPU 架构与 CUDA 编程模型

## GPU vs CPU 架构差异

| 维度 | CPU | GPU |
|------|-----|-----|
| 核心 | 少量大核心（4-16核），每个核强 | 大量小核心（数千），每个核轻量 |
| 设计目标 | 低延迟，单线程性能 | 高吞吐，并行计算 |
| 缓存 | 大缓存（MB级），复杂控制逻辑 | 小缓存，简单控制逻辑 |
| 适用 | 串行任务、分支密集 | 数据并行、计算密集 |
| 内存带宽 | 窄（50-100 GB/s） | 宽（500-1000+ GB/s） |

**关键 insight**：GPU 用更多晶体管做计算单元而非控制/缓存，所以适合大规模并行任务。

## CUDA 编程模型

### 层次结构

```
Grid（网格）
  └── Block（线程块）
        └── Thread（线程）
```

- **Thread**：最小的执行单元
- **Block**：一组线程，可共享内存，可同步
- **Grid**：一组 Block，构成整个任务

### 硬件映射

```
Thread → CUDA Core
Block  → SM（Streaming Multiprocessor）
Grid   → GPU Device
```

### 内存层次

| 内存 | 作用域 | 速度 | 大小 |
|------|--------|------|------|
| 全局内存 | 所有线程 | 慢（~400 GB/s） | 大（GB） |
| 共享内存 | Block内 | 快（~TB/s） | 小（48KB-228KB） |
| 寄存器 | 单线程 | 最快 | 极小 |
| 常量内存 | 所有线程只读 | 快（有缓存） | 64KB |
| 纹理内存 | 特定访问模式 | 快（有缓存） | 全局内存大小 |

### 典型 Kernel 结构

```cuda
__global__ void vector_add(float *a, float *b, float *c, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        c[idx] = a[idx] + b[idx];
    }
}

// 调用
vector_add<<<ceil(n/256.0), 256>>>(d_a, d_b, d_c, n);
```

## 你的 5070Ti

- 架构：Blackwell
- SM 数：待查
- CUDA Core 数：待查
- 显存：16GB GDDR7
- 显存带宽：~700 GB/s+

## 关键概念

1. **Warp**：32个线程为一组，SM 以 warp 为单位调度
2. **Warp Divergence**：同一个 warp 内分支不同 → 串行化执行
3. **Memory Coalescing**：连续的线程访问连续的地址 → 合并为一次大传输
4. **Occupancy**：SM 上活跃 warp 数 / 最大 warp 数，越高越好
5. **Bank Conflict**：共享内存分32个bank，多线程访问同一bank冲突
