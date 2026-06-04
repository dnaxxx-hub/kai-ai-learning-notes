# HPC Lesson 6: CUDA 内存模型 — 全局/共享/常量/寄存器与 Bank Conflict

## 概述

CUDA 性能的核心不在于计算，而在于**内存访问模式**。合理的利用各级内存可将吞吐量提升 10-100 倍。

## CUDA 内存层次

```
Host (CPU) RAM  ←cudaMemcpy→  Global Memory  ← 大、慢 (~200 GB/s GDDR7)
                                    │
                               L2 Cache  (~40MB)
                                    │
         ┌──────────────────────────┼──────────────────────────┐
     Shared Mem (48-128KB)    Registers (256K per SM)    Constant Mem (64KB)
     ┌── per SM, ~100 cycles ──┐  ┌ per thread, 0 cycles ┐   ┌ cached, read-only
     │ 手动管理的用户 L1缓存      │   │ ~255 regs/thread max │   │ 广播给所有线程
     │ 同一 block 内所有线程共享  │   │ 超限→spill 到 local   │   │ 16KB 常量缓存
     └──────────────────────────┘   └──────────────────────┘   └────────────────┘
```

### 性能对比 (RTX 5070 Ti 近似)

| 内存类型 | 带宽 | 延迟 | 范围 | 生命周期 |
|----------|------|------|------|----------|
| 全局 | ~900 GB/s | ~200-400 cycles | 所有线程 | 应用级 |
| 共享 | ~10 TB/s | ~20-30 cycles | 单个 block | block 内 |
| 寄存器 | 无瓶颈 | 0 cycles | 单个线程 | 线程内 |
| 常量 | 广播快 | ~20 cycles (cached) | 所有线程 | 应用级 |

## 全局内存 (Global Memory)

```cpp
// 分配
float *d_data;
cudaMalloc(&d_data, N * sizeof(float));
cudaMemcpy(d_data, h_data, N * sizeof(float), cudaMemcpyHostToDevice);

// 关键优化: 合并访问 (Coalesced Access)
// warp 内 32 个线程访问连续的 128 字节 → 一次事务

// ✅ 合并: thread i 访问 data[i]
int idx = blockIdx.x * blockDim.x + threadIdx.x;
float v = data[idx];  // 连续访问

// ❌ 不合并: thread i 访问 data[i * stride]
float v = data[idx * 64];  // 每次间隔 64 个 float，需多个事务
```

## 共享内存 (Shared Memory)

```cpp
// 声明: 每个 block 有一份私有副本
__shared__ float cache[256];  // 静态分配

// 动态大小 (运行时确定)
extern __shared__ float cache[];
kernel<<<blocks, threads, shared_mem_bytes>>>(...);
```

### 经典应用: 矩阵转置

```cpp
#define TILE 32
__global__ void transpose_shared(float *in, float *out, int n) {
    __shared__ float tile[TILE][TILE];

    int x = blockIdx.x * TILE + threadIdx.x;
    int y = blockIdx.y * TILE + threadIdx.y;

    if (x < n && y < n)
        tile[threadIdx.y][threadIdx.x] = in[y * n + x];

    __syncthreads();  // 等待所有线程写完共享内存

    int x2 = blockIdx.y * TILE + threadIdx.x;
    int y2 = blockIdx.x * TILE + threadIdx.y;

    if (x2 < n && y2 < n)
        out[y2 * n + x2] = tile[threadIdx.x][threadIdx.y];
}
// 全局内存的读和写都是合并的，速度远超 naive 非合并访问
```

## Bank Conflict

共享内存分为 **32 个 bank**（4 字节宽），每个 bank 每周期只能响应一个请求。

```
Bank:  0  1  2  ... 30 31
访问: [0] [1] [2] ... [30] [31]  ✅ 无冲突
      [0] [0] [0] ...  ❌ 32 路冲突 → 串行化
      [0] [1] [0] ...  ❌ thread 0 和 2 抢 bank 0
```

### 无冲突 vs 有冲突

```cpp
// 无冲突: 连续访问
__shared__ float s[1024];
float v = s[threadIdx.x];   // 每个线程访问不同 bank

// 无冲突: 跨步非 2 的幂
float v = s[threadIdx.x * 3];  // 3 是奇数 → 分布不同 bank

// 有冲突: 间隔 32
float v = s[threadIdx.x * 32];  // 全落在 bank 0 → 32 路冲突

// 避免: 加 padding
__shared__ float s[33][33];  // 每行 [33] 而非 [32]
// 同一列元素落在不同 bank 上
```

## 常量内存 (Constant Memory)

```cpp
// 适合所有线程访问相同值：参数、查表
__constant__ float lookup[256];

cudaMemcpyToSymbol(lookup, host_lookup, 256 * sizeof(float));

// 访问: 所有线程在同一地址 → 广播给整个 warp (1次事务)
__global__ void kernel(float *data) {
    int idx = threadIdx.x;
    float val = lookup[data[idx] & 0xFF];  // 广播，免费
}
```

## 寄存器

```cpp
// 寄存器是每个线程私有的，最快
// 但过多会限制 SM 并发 block 数 (occupancy ↓)
// 使用 nvcc --ptxas-options=-v 查看寄存器使用量

// 减少寄存器使用技巧：
// - 拆分 kernel 为多个小 kernel
// - 使用 __launch_bounds__ 提示
__global__ __launch_bounds__(256, 4)  // max 256 threads, min 4 blocks/SM
void my_kernel(...) { ... }
```

## 量化场景: K线滚动窗口

```cpp
// 用共享内存加速 50-bar 滑动窗口计算
// (Lesson 8 的实际项目基础)
```

## 总结表格

| 优化技术 | 目标 | 手段 |
|----------|------|------|
| 合并访问 | 全局内存 | 线程连续访问相邻地址 |
| 共享内存 | 片上加速 | 手动管理数据复用 |
| 无 bank conflict | 共享内存 | padding + 合理索引 |
| 常量内存 | 只读广播 | 参数/查找表 |
| 寄存器 | 零延迟 | 本地变量 + 避免 spilling |
