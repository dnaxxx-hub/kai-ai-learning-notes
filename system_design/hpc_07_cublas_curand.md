# HPC Lesson 7: cuBLAS / cuRAND — 在量化中的实战使用

## 概述

NVIDIA 提供了高度优化的 GPU 加速库：cuBLAS (线性代数) 和 cuRAND (随机数生成)。量化交易中常用的矩阵运算、蒙特卡洛模拟、协方差计算都可以直接调用。

## cuBLAS 基础

### 命名规范
```
cublas<T><operation>
T: S=float, D=double, C=cuComplex, Z=cuDoubleComplex
```

### 向量点积 (dot)

```cpp
#include <cublas_v2.h>

cublasHandle_t handle;
cublasCreate(&handle);

float *d_x, *d_y;  // device 指针，已用 cudaMalloc 分配
float result;

// sdot = float dot product
cublasSdot(handle, N, d_x, 1, d_y, 1, &result);
// 最后一个参数是 device 指针，放结果
```

### 矩阵乘法 — SGEMM (量化核心)

```cpp
// C = α*A*B + β*C
// A: M×K, B: K×N, C: M×N
cublasStatus_t cublasSgemm(
    cublasHandle_t handle,
    cublasOperation_t transa,  // CUBLAS_OP_N / CUBLAS_OP_T
    cublasOperation_t transb,
    int m, int n, int k,
    const float *alpha,        // α ∈ [0,1]
    const float *A, int lda,   // lda = leading dimension
    const float *B, int ldb,
    const float *beta,         // β ∈ [0,1]
    float *C, int ldc
);

// 实战：计算多个标的的协方差矩阵
// 输入: returns[N_stocks][N_days]  收益率矩阵
// 输出: cov[N_stocks][N_stocks]     协方差矩阵
// 计算: cov = (1/N) * returns * returns^T

float alpha = 1.0f / N_days;
float beta  = 0.0f;

// cuBLAS 默认列主序 (Fortran order)
// 处理行主序矩阵时需要交换参数
cublasSgemm(handle,
    CUBLAS_OP_N, CUBLAS_OP_T,  // C = A * B^T
    N_stocks, N_stocks, N_days,
    &alpha,
    d_returns, N_stocks,   // A: [N_stocks × N_days]
    d_returns, N_stocks,   // B^T: [N_days × N_stocks]
    &beta,
    d_cov, N_stocks        // C: [N_stocks × N_stocks]
);
// GPU 上一行搞定的协方差矩阵！~1ms 处理 1000 只股票 500 天
```

## cuRAND 基础

### 生成正态随机数 (蒙特卡洛期权定价)

```cpp
#include <curand_kernel.h>

// 在 kernel 中生成随机数
__global__ void monte_carlo_kernel(float *paths, int n_paths,
                                   float S0, float mu, float sigma, float dt) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= n_paths) return;

    curandState state;
    curand_init(clock64(), tid, 0, &state);  // 用时间+线程id 做种子

    float S = S0;
    for (int t = 0; t < N_STEPS; t++) {
        float z = curand_normal(&state);         // N(0,1)
        S *= expf((mu - 0.5f*sigma*sigma)*dt + sigma*sqrtf(dt)*z);
        paths[tid * N_STEPS + t] = S;
    }
}

// 或使用 host API 批量生成 (更高效)
#include <curand.h>

curandGenerator_t gen;
curandCreateGenerator(&gen, CURAND_RNG_PSEUDO_MTGP32);  // Mersenne Twister
curandSetPseudoRandomGeneratorSeed(gen, time(NULL));

float *d_random;
cudaMalloc(&d_random, N * sizeof(float));

// 一次生成 N 个正态随机数
curandGenerateNormal(gen, d_random, N, 0.0f, 1.0f);  // μ=0, σ=1

curandDestroyGenerator(gen);
```

## 量化实战：协方差矩阵 + 蒙特卡洛

```cpp
// 1. 用 cuBLAS 快速计算协方差矩阵 (如上)

// 2. 用 cuRAND 生成随机收益率场景
// 3. 矩阵乘法: 场景权重 × 协方差分解
// 4. 得到模拟的 portfolio 收益率分布
// 5. 计算 VaR (Value at Risk)

// 整个 pipeline 完全在 GPU 上完成，无需 CPU 回拷
// 10000 次蒙特卡洛模拟计算 portfolio VaR: < 10ms
```

## cuSOLVER — Cholesky 分解

```cpp
// 协方差矩阵的 Cholesky 分解 (蒙特卡洛需要)
#include <cusolverDn.h>

cusolverDnHandle_t solver;
cusolverDnCreate(&solver);

int Lwork = 0;
cusolverDnSpotrf_bufferSize(solver, CUBLAS_FILL_MODE_LOWER, N, d_cov, N, &Lwork);

float *d_work;
cudaMalloc(&d_work, Lwork * sizeof(float));

// Cholesky: cov = L * L^T
cusolverDnSpotrf(solver, CUBLAS_FILL_MODE_LOWER, N, d_cov, N, d_work, Lwork, NULL);

// 然后用 L 做白化: 相关场景 = L * 独立正态

// 清理
cusolverDnDestroy(solver);
```

## 性能数据 (参考 RTX 5070 Ti)

| 操作 | 数据量 | 耗时 |
|------|--------|------|
| SGEMM | 500×1000 × 1000×500 | ~0.5ms |
| 协方差矩阵 | 1000 stocks × 500 days | ~1ms |
| 正态随机数生成 | 10M 个 | ~3ms |
| Cholesky 分解 | 1000×1000 | ~0.3ms |

## 编译

```bash
# Windows + MSVC + CUDA
nvcc -O3 -arch=sm_90 -lcublas -lcurand -lcusolver quant_gpu.cu -o quant_gpu.exe
```

## 关键经验

1. **批量处理**: 一次提交几百/几千只股票的计算，分摊 kernel launch 开销
2. **就地计算**: 尽量重用 device 内存，避免 cudaMalloc 频繁调用
3. **流 (Stream)**: 用多个 CUDA stream 重叠计算与数据传输
4. **cuBLAS > 手写**: 千万别手写矩阵乘法，cuBLAS 经过极致调优
