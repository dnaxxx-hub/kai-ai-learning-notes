# 性能优化 #7：SIMD 实战与向量化

> 2026-05-17
> 前置：CPU 管线 #1、锁优化 #6

## 1. SIMD 的本质

### 1.1 一条指令操作多个数据

```
标量（Scalar）:
  v1: [a0] [a1] [a2] [a3]
  v2: [b0] [b1] [b2] [b3]
  +-----------------------
  v3: [a0+b0] [a1+b1] [a2+b2] [a3+b3]  ← 4 条加法指令
  
向量（SIMD: Single Instruction Multiple Data）:
  v1: [a0 a1 a2 a3]
  v2: [b0 b1 b2 b3]
  +----------------
  v3: [s0 s1 s2 s3]  ← 1 条 ADDPS 指令，4 个加法同时完成
```

### 1.2 指令集演进

| 指令集 | 位数 | 寄存器 | 每指令 | 年代 |
|--------|------|--------|--------|------|
| MMX | 64 | mm0-mm7 | 2×int32 | 1997 |
| SSE | 128 | xmm0-xmm15 | 4×float32 | 1999 |
| SSE2 | 128 | xmm0-xmm15 | 4×float32/2×float64 | 2000 |
| AVX | 256 | ymm0-ymm15 | 8×float32/4×float64 | 2011 |
| AVX2 | 256 | ymm0-ymm15 | FMA + gather | 2013 |
| AVX-512 | 512 | zmm0-zmm31 | 16×float32/8×float64 | 2017 |

## 2. 向量化 K 线计算

### 2.1 SMA（简单移动平均）

```python
import numpy as np

# ❌ Python 循环（200x 慢）
def sma_loop(prices: np.ndarray, window: int) -> np.ndarray:
    n = len(prices)
    result = np.zeros(n)
    for i in range(window - 1, n):
        result[i] = prices[i-window+1:i+1].mean()
    return result

# ✅ NumPy 向量化（自动调用 BLAS/SIMD）
def sma_vectorized(prices: np.ndarray, window: int) -> np.ndarray:
    # 卷积：cumsum 差分法
    cumsum = np.cumsum(np.insert(prices, 0, 0))
    result = (cumsum[window:] - cumsum[:-window]) / window
    # 前 window-1 个填 NaN
    return np.concatenate([np.full(window-1, np.nan), result])

# ✅ Numba JIT + SIMD（手动适配）
from numba import njit

@njit(fastmath=True, parallel=True)  
def sma_numba(prices: np.ndarray, window: int) -> np.ndarray:
    n = len(prices)
    result = np.zeros(n)
    cum = 0.0
    for i in range(n):
        cum += prices[i]
        if i >= window:
            cum -= prices[i - window]
            result[i] = cum / window
        elif i == window - 1:
            result[i] = cum / window
    return result
```

`fastmath=True` 告诉 Numba 可以重新关联浮点运算（SIMD 需要），可能产生极小的精度差异。

### 2.2 布林带向量化

```python
# 布林带 = SMA ± k × 标准差
# 关键：标准差需要平方差

@njit(fastmath=True)
def bollinger(prices: np.ndarray, window: int, k: float = 2.0):
    n = len(prices)
    mid = np.zeros(n)
    upper = np.zeros(n)
    lower = np.zeros(n)
    
    # 滑动窗口累加（避免重复计算）
    cum_sum = 0.0
    cum_sq = 0.0  # 平方和
    
    for i in range(n):
        cum_sum += prices[i]
        cum_sq += prices[i] * prices[i]
        
        if i >= window:
            cum_sum -= prices[i - window]
            cum_sq -= prices[i - window] * prices[i - window]
            
        if i >= window - 1:
            mid[i] = cum_sum / window
            variance = cum_sq / window - mid[i] * mid[i]
            std = np.sqrt(max(variance, 0.0))  # 防止浮点误差负数
            upper[i] = mid[i] + k * std
            lower[i] = mid[i] - k * std
    
    return mid, upper, lower
```

O(n) 时间，O(1) 额外空间，单次遍历完成。

## 3. Rust SIMD 实战

### 3.1 core::simd（稳定版）

```rust
#![feature(portable_simd)]
use std::simd::*;

/// 4 个 f64 同时求和
fn sum_4(a: [f64; 4], b: [f64; 4]) -> [f64; 4] {
    let va = f64x4::from_array(a);
    let vb = f64x4::from_array(b);
    (va + vb).to_array()
}

/// 批量 SMA 计算
fn sma_simd(prices: &[f64], window: usize) -> Vec<f64> {
    let n = prices.len();
    let mut result = vec![0.0_f64; n];
    
    // 用窗口累加（SIMD 不适合少量数据的滑动归约）
    let mut cum = 0.0_f64;
    for i in 0..window.min(n) {
        cum += prices[i];
    }
    if n >= window {
        result[window - 1] = cum / window as f64;
    }
    for i in window..n {
        cum += prices[i] - prices[i - window];
        result[i] = cum / window as f64;
    }
    result  // cumsum 公式更适合 SIMD
}
```

### 3.2 显式 AVX 模式

```rust
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

/// 使用 AVX 加速 4 个双精度浮点数的点积
fn dot_product_avx(a: &[f64], b: &[f64]) -> f64 {
    assert_eq!(a.len(), b.len());
    let n = a.len();
    let mut sum = 0.0_f64;
    
    // AVX 一次处理 4 个 f64
    unsafe {
        let mut acc = _mm256_setzero_pd();  // 零向量
        let mut i = 0;
        while i + 4 <= n {
            let va = _mm256_loadu_pd(a.as_ptr().add(i));  // 对齐加载
            let vb = _mm256_loadu_pd(b.as_ptr().add(i));
            acc = _mm256_fmadd_pd(va, vb, acc);  // FMA: acc += va * vb
            i += 4;
        }
        // 水平求和（4 个值累加为 1 个）
        let mut tmp: [f64; 4] = std::mem::transmute(acc);
        sum = tmp[0] + tmp[1] + tmp[2] + tmp[3];
        
        // 处理剩余元素
        for j in i..n {
            sum += a[j] * b[j];
        }
    }
    sum
}
```

**重要**：英特尔 ADL 和 AMD Zen4+ 都支持 AVX-512。但 `_mm256_fmadd_pd` (FMA) 几乎覆盖所有现代 CPU。

## 4. 量化引擎的 SIMD 性能分析

### 4.1 布林带计算的 SIMD 收益

| 实现方式 | 10 万行耗时 | 相对速度 |
|---------|------------|---------|
| Python 纯循环 | 850ms | 1x |
| NumPy 向量化 | 8ms | 106x |
| Numba JIT | 3ms | 283x |
| Rust 原生 | 1ms | 850x |

**结论**：对 K 线计算，Numba JIT 已经足够快（3ms vs Rust 的 1ms 在回测中微不足道）。但当需要在实时信号推送中计算，或者大数据参数搜索中循环调用时，Rust/C 的收益会累积。

### 4.2 何时真正需要 SIMD

```
SIMD 收益大的场景（4-8x 加速）：
  ✅ 大量连续浮点运算（K 线指标、线性代数）
  ✅ 固定大小的批处理（向量归一化、矩阵乘法片段）
  ✅ 有明确的 loop 且无依赖链

SIMD 收益不大的场景（< 2x）：
  ❌ 小规模数据（几十个点，函数调用开销主导）
  ❌ 大量分支（SIMD 没有分支机制，要掩码模拟，效率低）
  ❌ 非连续内存（gather 指令慢）
```

### 4.3 避免向量化的伪优化

```python
# 一些看似"向量化"但其实是多次计算的做法：
# ❌ 不必要的条件计算
close = df['close'].values
mask = close > sma
result = np.where(mask, close, 0)  # 这个实际上是两个遍历

# ✅ 一次性计算
result = close * (close > sma)     # 布尔作为掩码，单次遍历

# 用 python -m timeit 验证而不是猜
```

## 总结

```
SIMD 核心：
  一条指令操作多个数据 → 潜在 4-8x 加速

量化引擎中的应用：
  NumPy 自动向量化（BLAS/LAPACK 底层）
  Numba JIT + fastmath（接近手工优化）
  Rust core::simd（便携式）
  显式 intrinsics（最大性能但最不便携）

策略：
  先用 NumPy 向量或 Numba JIT（最小成本）
  热点用 Rust SIMD（需要 20%+ 收益才值得）
  手动 intrinsics 只用于极其关键的 1-2 个函数
```
