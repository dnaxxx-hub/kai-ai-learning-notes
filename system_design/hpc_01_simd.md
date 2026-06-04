# HPC Lesson 1: SIMD Basics — SSE/AVX 指令集与向量化编程

## 概述

SIMD (Single Instruction, Multiple Data) 是现代 CPU 核心加速手段之一。一条指令同时对多个数据元素执行相同操作，是量化交易引擎中批量计算 OHLCV、波动率、协方差矩阵的基石。

## x86 SIMD 指令集演进

| 拓展 | 位宽 | 寄存器 | 元素数(float) | 引入 |
|------|------|--------|--------------|------|
| MMX  | 64b  | mm0-mm7 | 2 | 1997 |
| SSE  | 128b | xmm0-xmm15 | 4 | 1999 |
| AVX  | 256b | ymm0-ymm15 | 8 | 2011 |
| AVX2 | 256b | (同上) + gather | 8 | 2013 |
| AVX-512 | 512b | zmm0-zmm31 | 16 | 2016 |

**关键头文件**（x64 MSVC/GCC/Clang 通用）：
- `<xmmintrin.h>` — SSE
- `<emmintrin.h>` — SSE2
- `<pmmintrin.h>` — SSE3
- `<tmmintrin.h>` — SSSE3
- `<smmintrin.h>` — SSE4.1
- `<nmmintrin.h>` — SSE4.2
- `<immintrin.h>` — **全部包含**（AVX/AVX2/AVX-512），推荐只包含这一个

## 数据类型

```c
// SSE (128-bit)
__m128   // 4 × float
__m128d  // 2 × double
__m128i  // 整数 (16×byte / 8×short / 4×int / 2×long long)

// AVX (256-bit)
__m256   // 8 × float
__m256d  // 4 × double
__m256i  // 整数

// AVX-512 (512-bit)
__m512   // 16 × float
```

## 核心操作模式

```
数据布局: [a0 a1 a2 a3]  [b0 b1 b2 b3]
         \_______________/ \_______________/
              xmm0              xmm1
                     \           /
                  addps (packed single)
                     \         /
                   [a0+b0 a1+b1 a2+b2 a3+b3]
```

## 常用指令示例

```c
#include <immintrin.h>

// SSE: 4 × float 加法
__m128 a = _mm_set_ps(4.0f, 3.0f, 2.0f, 1.0f);
__m128 b = _mm_set_ps(8.0f, 7.0f, 6.0f, 5.0f);
__m128 c = _mm_add_ps(a, b);  // {12,10,8,6}

// AVX: 8 × float 加法
__m256 va = _mm256_set_ps(8,7,6,5,4,3,2,1);
__m256 vb = _mm256_set_ps(16,14,12,10,8,6,4,2);
__m256 vc = _mm256_add_ps(va, vb);

// AVX: FMA (fused multiply-add) — 一条指令完成 a*b+c
__m256 vd = _mm256_fmadd_ps(va, vb, vc);

// AVX: 水平求和 (把所有元素加在一起)
// 先做一半的纵向 add，然后做 permute + add 的归约
__m256 sum = va;
__m128 hi = _mm256_extractf128_ps(sum, 1);
__m128 lo = _mm256_castps256_ps128(sum);
__m128 sum128 = _mm_add_ps(hi, lo);
sum128 = _mm_hadd_ps(sum128, sum128);
sum128 = _mm_hadd_ps(sum128, sum128);
float result = _mm_cvtss_f32(sum128);  // 8个数之和
```

## 实战：向量化点积 (Dot Product)

```c
// 标量版本
float dot_scalar(const float *a, const float *b, int n) {
    float sum = 0.0f;
    for (int i = 0; i < n; i++)
        sum += a[i] * b[i];
    return sum;
}

// AVX 向量化版本 (n 为 8 的倍数)
float dot_avx(const float *a, const float *b, int n) {
    __m256 sum = _mm256_setzero_ps();
    for (int i = 0; i < n; i += 8) {
        __m256 va = _mm256_loadu_ps(a + i);
        __m256 vb = _mm256_loadu_ps(b + i);
        sum = _mm256_fmadd_ps(va, vb, sum);  // sum += a[i]*b[i]
    }
    // 归约求 sum
    __m128 hi = _mm256_extractf128_ps(sum, 1);
    __m128 lo = _mm256_castps256_ps128(sum);
    __m128 sum128 = _mm_add_ps(hi, lo);
    sum128 = _mm_hadd_ps(sum128, sum128);
    sum128 = _mm_hadd_ps(sum128, sum128);
    return _mm_cvtss_f32(sum128);
}
```

## 对齐与加载

| 指令 | 要求对齐 | 用途 |
|------|---------|------|
| `_mm_load_ps` / `_mm256_load_ps` | 16B / 32B 对齐 | 已知对齐时更高效 |
| `_mm_loadu_ps` / `_mm256_loadu_ps` | 不对齐 | 通用，性能损失很小 |
| `_mm_store_ps` / `_mm256_store_ps` | 对齐写 | |
| `_mm_storeu_ps` / `_mm256_storeu_ps` | 不对齐写 | |

## 自动向量化 (Auto-Vectorization)

现代编译器 (MSVC `/arch:AVX2`, GCC `-mavx2`, Clang `-mavx2`) 能自动将简单循环向量化。但以下情况仍需手动：
- 循环依赖 / 归约模式复杂
- 数据布局非 AoS → SoA 转换
- 特殊 shuffle / permute 操作

## 在量化中的典型应用

- **OHLCV 滚动计算**: 8 个 bar 同时计算最高/最低价
- **协方差矩阵**: 并行计算多个股票的 pairwise 乘积
- **波动率**: 收益率序列的平方和向量化
- **信号处理**: 多个时间序列的同时归一化

## 编译

```bash
# MSVC (Windows)
cl /O2 /arch:AVX2 /fp:fast program.c

# GCC
gcc -O3 -mavx2 -mfma -ffast-math program.c

# Clang
clang -O3 -mavx2 -mfma -ffast-math program.c
```

*RTX 5070 Ti 上的 GPU 是 CUDA 的任务，但 x86 CPU 上的 AVX 是 HPC 优化第一道防线。*
