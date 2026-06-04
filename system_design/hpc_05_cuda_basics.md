# HPC Lesson 5: CUDA 基础 — GPU 架构与 Kernel 编程

## 概述

CUDA (Compute Unified Device Architecture) 是 NVIDIA GPU 的并行计算平台。RTX 5070 Ti 基于 Blackwell 架构，CUDA Core ≈ 8960，显存 16GB GDDR7。

对比 x86 SIMD (数倍加速) 与 CUDA (数百倍加速)：SIMD 适合小批量低延迟，CUDA 适合大批量高吞吐。

## GPU 架构概览

```
GPU (Device)
└── GPC (Graphics Processing Cluster)
    └── TPC (Texture Processing Cluster)
        └── SM (Streaming Multiprocessor)  ← 核心执行单元
            ├── CUDA Core (32-128 per SM)
            ├── Shared Memory (48-128 KB)
            ├── Register File (64K+ 32-bit)
            ├── Warp Scheduler (4 per SM)
            └── Tensor Core (Blackwell 新增 5th gen)
```

### 关键术语
| 术语 | 含义 |
|------|------|
| **Host** | CPU 端，控制逻辑 |
| **Device** | GPU 端，执行 kernel |
| **Kernel** | GPU 上运行的函数 (`__global__`) |
| **Thread** | 最小执行单元 |
| **Warp** | 32 个线程一组，SIMT 执行 |
| **Block** | 线程块，在同一个 SM 上执行 |
| **Grid** | Block 的集合，构成整个 kernel |

## Hello World: 向量加法

```cpp
#include <cuda_runtime.h>
#include <stdio.h>

// GPU Kernel: 每个线程处理一个元素
__global__ void vec_add_kernel(float *a, float *b, float *c, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n)
        c[idx] = a[idx] + b[idx];
}

int main() {
    int n = 1 << 20;    // 1M 元素
    size_t bytes = n * sizeof(float);

    // 1. 分配 device 内存
    float *d_a, *d_b, *d_c;
    cudaMalloc(&d_a, bytes);
    cudaMalloc(&d_b, bytes);
    cudaMalloc(&d_c, bytes);

    // 2. host 数据 → device
    float *h_a = new float[n];
    float *h_b = new float[n];
    // ... 初始化 h_a, h_b ...
    cudaMemcpy(d_a, h_a, bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_b, h_b, bytes, cudaMemcpyHostToDevice);

    // 3. 启动 kernel
    int threads_per_block = 256;
    int blocks = (n + threads_per_block - 1) / threads_per_block;
    vec_add_kernel<<<blocks, threads_per_block>>>(d_a, d_b, d_c, n);

    // 4. 等待完成 + 取回结果
    cudaDeviceSynchronize();
    cudaMemcpy(h_c, d_c, bytes, cudaMemcpyDeviceToHost);

    // 5. 清理
    cudaFree(d_a); cudaFree(d_b); cudaFree(d_c);
    delete[] h_a; delete[] h_b;
    return 0;
}
```

## 线程层次 (Thread Hierarchy)

```
Grid  (<<<gridDim, blockDim>>>)
└── Block(0,0)  ← 最多 1024 threads
    ├── Thread(0,0,0)
    ├── Thread(0,1,0)
    └── ... (3D 索引，但通常用 1D)

索引计算:
  threadIdx  — 线程在 block 内的索引
  blockIdx   — block 在 grid 内的索引
  blockDim   — block 的维度 (线程数)
  gridDim    — grid 的维度 (block 数)

  全局 ID = blockIdx.x * blockDim.x + threadIdx.x
```

## 线程块配置策略

```cpp
// 获取 device 属性
cudaDeviceProp prop;
cudaGetDeviceProperties(&prop, 0);

// 关键参数
printf("Max threads per block: %d\n", prop.maxThreadsPerBlock);    // 1024
printf("Max block dims: %d x %d x %d\n",
    prop.maxThreadsDim[0], prop.maxThreadsDim[1], prop.maxThreadsDim[2]);
printf("Max grid dims: %d x %d x %d\n",
    prop.maxGridSize[0], prop.maxGridSize[1], prop.maxGridSize[2]);
printf("Warp size: %d\n", prop.warpSize);  // 32

// 常用: block 大小选 128/256/512 (warp 数的倍数)
// 太小 → SM 利用率不足；太大 → 寄存器占用限制并发 block 数
```

## 错误处理

```cpp
#define CUDA_CHECK(call) do {                                      \
    cudaError_t err = call;                                        \
    if (err != cudaSuccess) {                                      \
        fprintf(stderr, "CUDA error %s:%d: %s\n",                  \
                __FILE__, __LINE__, cudaGetErrorString(err));       \
        exit(EXIT_FAILURE);                                        \
    }                                                              \
} while(0)

// 使用
CUDA_CHECK(cudaMalloc(&d_a, bytes));
CUDA_CHECK(cudaMemcpy(d_a, h_a, bytes, cudaMemcpyHostToDevice));
vec_add_kernel<<<blocks, threads>>>(d_a, d_b, d_c, n);
CUDA_CHECK(cudaGetLastError());  // kernel 启动参数错误检查
CUDA_CHECK(cudaDeviceSynchronize());  // kernel 执行错误检查
```

## 在量化中的适用性

CUDA 最适合 **数据并行** 且 **计算密集** 的任务：
- ✅ 大规模矩阵运算（多标的相关性矩阵）
- ✅ 蒙特卡洛模拟（期权定价、VaR）
- ✅ 批处理信号计算（数千只股票同时处理）
- ❌ 低延迟单笔交易决策（PCIe 传输 5-10μs 成本太高）

## 编译

```bash
# Windows + Visual Studio
nvcc -arch=sm_50 -O3 vec_add.cu -o vec_add.exe

# RTX 5070 Ti → Blackwell, compute capability 12.x (推测)
# 现阶段用 -arch=sm_90 (Ada) 或 sm_100 (Blackwell SDK 出后)
```
