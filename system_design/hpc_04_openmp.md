# HPC Lesson 4: OpenMP — 多线程并行编程

## 概述

OpenMP 是 C/C++/Fortran 的多线程并行编程标准，通过编译器指令(pragma) 实现渐进式并行化。对量化引擎来说，是快速将串行循环变为多核并行的捷径。

在 Windows 上，MSVC 和 Clang 均支持 OpenMP 2.0/3.0+。

## 基本使用

```c
#include <omp.h>

int main() {
    // 设置线程数（环境变量 OMP_NUM_THREADS 优先级更高）
    omp_set_num_threads(8);  // 5070Ti 系统配16线程+GPU

    #pragma omp parallel
    {
        int tid = omp_get_thread_num();
        printf("Hello from thread %d\n", tid);
    }
    return 0;
}
```

## 核心构造

### parallel for — 最简单的向量循环并行

```c
// 标量
for (int i = 0; i < N; i++)
    result[i] = a[i] + b[i];

// 并行
#pragma omp parallel for
for (int i = 0; i < N; i++)
    result[i] = a[i] + b[i];
```

### reduction — 并行归约

```c
float total_pnl = 0.0f;
#pragma omp parallel for reduction(+:total_pnl)
for (int i = 0; i < N_TRADES; i++)
    total_pnl += trades[i].pnl;
// 每个线程有私有副本，最后合并
```

### sections — 任务级并行

```c
#pragma omp parallel sections
{
    #pragma omp section
    { calc_volatility(prices); }

    #pragma omp section
    { calc_correlation(asset_a, asset_b); }

    #pragma omp section
    { calc_moving_average(prices, 20); }
}
```

## 调度策略 (Schedule)

| 调度 | 行为 | 适用 |
|------|------|------|
| `static` | 编译时分块，每线程固定 | 负载均匀 |
| `dynamic` | 运行时动态分配 | 负载不均 |
| `guided` | 递减块大小 | 类似 dynamic 但开销更小 |
| `auto` | 编译器自行决定 | 默认 |

```c
#pragma omp parallel for schedule(static, 64)  // 每块64个迭代
for (int i = 0; i < N; i++)
    process(data[i]);
```

## 数据共享与私有

```c
int shared_val = 0;           // 默认 shared (所有线程共享)
#pragma omp parallel for private(local_buf) firstprivate(init_val) \
    shared(shared_val) lastprivate(final_result)
for (int i = 0; i < N; i++) {
    local_buf = init_val;     // firstprivate: 每个线程得到初始值拷贝
    local_buf += data[i];
    if (i == N-1) final_result = local_buf;  // lastprivate: 最后一轮的值
}
```

## 实战：多标的波动率计算

```c
// 并行计算多只股票的滚动波动率
void calc_rolling_volatility(float *returns, int n_returns,
                             float *vol, int n_stocks, int window) {
    #pragma omp parallel for schedule(dynamic)
    for (int s = 0; s < n_stocks; s++) {
        float *r = returns + s * n_returns;
        float *v = vol + s * n_returns;

        // 每个股票独立计算（不同股票数据量接近，但可动态分配）
        for (int t = window; t < n_returns; t++) {
            float sum = 0.0f, sum2 = 0.0f;
            for (int w = t - window; w < t; w++) {
                sum  += r[w];
                sum2 += r[w] * r[w];
            }
            v[t] = sqrtf((sum2 - sum*sum/window) / (window - 1));
        }
    }
}
```

## OpenMP 与 SIMD 组合

```c
// #pragma omp simd — 在单线程内向量化 (C++11/OpenMP 4.0+)
#pragma omp parallel for
for (int i = 0; i < N; i++) {
    #pragma omp simd
    for (int j = 0; j < M; j++) {
        c[i] += a[i * M + j] * b[j];
    }
}
// 外层线程级并行 × 内层 SIMD 向量化 = 双重加速
```

## Windows 编译

```bash
# MSVC
cl /O2 /openmp /arch:AVX2 program.c

# Clang-cl (LLVM)
clang-cl /O2 /openmp /arch:AVX2 program.c

# MinGW GCC
gcc -O3 -fopenmp -mavx2 program.c
```

## 注意事项

- **原子操作**: `#pragma omp atomic` 比 `critical` 更轻量
- **线程安全**: OpenMP 不自动保护共享资源，需自己管理锁
- **工作窃取**: dynamic/guided 有调度开销，块大小>=64 为宜
- **嵌套并行**: OpenMP 默认不支持嵌套，需要用 `omp_set_nested(1)`
- **核心数上限**: 8-16 核通常收益最高，更多核可能受内存带宽限制
