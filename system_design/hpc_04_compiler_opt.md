# 性能优化 #4：编译优化与 JIT

> 2026-05-17
> 前置：Profiling #3

## 1. 编译器优化的层次

### 1.1 优化级别

```bash
# GCC/Clang 优化级别
-O0  # 不优化（调试用）
-O1  # 基本优化（体积小、编译快）
-O2  # 充分优化（生产常见）
-O3  # 激进优化（可能增大体积）
-Ofast # O3 + 不严格的浮点语义（可能导致精度变化）
```

不同级别在量化代码中的效果：

```c
// 示例：sum of array
double sum_array(const double* arr, size_t n) {
    double sum = 0;
    for (size_t i = 0; i < n; i++) sum += arr[i];
    return sum;
}

// -O0: 逐条执行，每次循环都读内存
// -O1: 保持 sum 在寄存器，不写回内存 → 5x 快
// -O2: 自动向量化（AVX 一次 4 个 double）→ 15x 快
// -O3: 循环展开（一次 8 次迭代）→ 18x 快
```

### 1.2 Profile Guided Optimization（PGO）

编译时无法预知哪个分支会频繁执行——用实际运行数据指导优化：

```bash
# 1. 产生 profile
gcc -O2 -fprofile-generate -o backtest_pgo backtest.c
./backtest_pgo sample_data.csv    # 运行实际场景，产生 .gcda 文件

# 2. 优化编译
gcc -O2 -fprofile-use -o backtest backtest.c
# 编译器现在知道：
#   - 哪个 if 分支更常执行 → 优化布局
#   - 哪个循环被多次调用 → 更激进的内联
#   - 哪个函数是热的 → 更积极的优化
```

在量化引擎中：用代表的历史数据做 PGO 训练，用真实数据做 run。

### 1.3 Link Time Optimization（LTO）

跨编译单元的内联优化：

```bash
# 没有 LTO：每个 .c 文件单独编译，函数只能在内被 inline
# 有 LTO：链接阶段再做一次全局分析和内联

# Cargo.toml
[profile.release]
lto = "fat"          # 全链路（最激进）
# lto = "thin"      # 部分链路（编译更快，优化接近 fat）

codegen-units = 1    # 单代码生成单元（减少跨文件优化限制）
```

LTO 在 Rust 中特别有用——跨 crate 的内联可以让零成本抽象落到实处。

## 2. Python 加速方案

### 2.1 Numba（JIT 编译）

不需要改语言，加装饰器即可：

```python
from numba import jit, njit, prange
import numpy as np

# ❌ 慢：纯 Python 循环
def compute_sma_py(prices, window=14):
    result = np.zeros_like(prices)
    for i in range(window-1, len(prices)):
        result[i] = prices[i-window+1:i+1].mean()
    return result

# ✅ 快：Numba JIT 编译
@njit(cache=True, fastmath=True)  # cache=True: 重复运行不重编译
def compute_sma_jit(prices, window=14):
    n = len(prices)
    result = np.zeros(n)
    for i in range(window-1, n):
        s = 0.0
        for j in range(i-window+1, i+1):
            s += prices[j]
        result[i] = s / window
    return result

# 速度对比：
#   Python 循环:    150 ms
#   Numba JIT:      0.5 ms  ← 300x 加速
#   Numpy rolling:  1.2 ms  ← 还算不错
```

**重要**：Numba 本身不支持 pandas，需要用 `.values` 提取 numpy 数组。

### 2.2 并行化

```python
from numba import njit, prange

@njit(parallel=True)
def multi_strategy_scores(close: np.ndarray, params: np.ndarray) -> np.ndarray:
    """同时计算多个参数组合的策略评分"""
    n_strategies = params.shape[0]
    results = np.zeros(n_strategies)
    
    for i in prange(n_strategies):
        window = params[i, 0]
        threshold = params[i, 1]
        # 每个策略独立计算（无数据依赖 → 自动并行）
        sma = np.zeros_like(close)
        for j in range(window-1, len(close)):
            s = 0.0
            for k in range(j-window+1, j+1):
                s += close[k]
            sma[j] = s / window
        # 计算评分
        results[i] = np.sum(close[window:] > sma[window:] + threshold)
    
    return results

# 并行化在参数搜索时特别有用（策略间无依赖）
```

### 2.3 Cython

把 Python 代码转为 C 扩展：

```cython
# signal.pyx
cimport numpy as np
import numpy as np

def compute_signal_cy(double[:] close, int window):
    cdef int n = close.shape[0]
    cdef np.ndarray[double, ndim=1] result = np.zeros(n)
    cdef double s = 0.0
    cdef int i, j
    
    for i in range(n):
        s += close[i]
        if i >= window:
            s -= close[i - window]
        # 这里写条件分支→ Cython 编译为 C ，速度接近原生
    return result
```

但 Cython 的语法不如 Numba 简单，对原型开发不合适。

## 3. Rust 编译优化

### 3.1 Release Profile

```toml
# Cargo.toml
[profile.release]
lto = "fat"              # 全链接时代优化
codegen-units = 1        # 单代码生成单元
opt-level = 3            # 最大优化
target-cpu = "native"    # 为当前 CPU 优化（启用所有支持的指令集）

# → 等价于: -march=native -O3 -flto
```

### 3.2 内联控制

```rust
// #[inline(always)] — 强制内联（减少函数调用开销）
// #[inline(never)]  — 阻止内联（减少代码膨胀）

#[inline(always)]
fn fast_sma(values: &[f64], window: usize) -> f64 {
    values.iter().take(window).sum()
}

// 对热点的内联策略：
// 1. 写代码时不加 inline（让编译器自己判断）
// 2. profile 发现热点函数后 → #[inline(always)]
// 3. 如果代码膨胀 → 撤销一部分 inline
```

### 3.3 边界检查消除

Rust 默认做边界检查（安全特性，不像 C 直接越界）：

```rust
fn compute(values: &[f64], out: &mut [f64]) {
    // 有边界检查
    for i in 0..values.len() {
        out[i] = values[i] * 2.0;
    }

    // 消除边界检查的惯用方式
    for (v, o) in values.iter().zip(out.iter_mut()) {
        *o = *v * 2.0;  // 迭代器保证长度一致 → 编译器消除检查
    }
}
```

`.get_unchecked(index)` 可以强制跳过边界检查（性能 1-2% 提升，通常不值得冒 UB 风险）。

## 4. 编译器不能优化的地方

即使编译器再强，也有些地方无能为力：

```
编译器能优化：
  常量折叠、循环展开、自动向量化、内联
  死代码消除、指令重排、寄存器分配

编译器不能优化：
  数据库查询（I/O 瓶颈你指望编译器？）
  不必要的序列化和反序列化
  不必要的数据复制
  算法复杂度本身
  锁竞争
```

**编译优化是锦上添花，算法优化是雪中送炭**。

## 总结

```
编译优化层次：
  -O2  → 充分的通用优化
  -O3  → 激进优化（量化引擎）
  LTO  → 跨文件内联
  PGO  → 运行时数据驱动的优化
  target-cpu=native → 为本机 CPU 最大化 SIMD

语言级优化：
  Python: Numba JIT（300x），Cython（<2x over Numba）
  Rust: lto=fat, codegen-units=1, target-cpu=native

核心原则：先 profile 找热点，再针对性优化
```
