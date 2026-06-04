# 📘 09 - C/C++ 互操作与 Python 绑定

> 量化系统的黄金组合：Python（快速原型 + 数据分析） + C++（性能热点加速）
> 核心：`extern "C"` + `pybind11` + AVX 向量化

---

## 1. extern "C" 与链接规范

### C 和 C++ 的 ABI 差异

```cpp
// C++: 函数名会被 name mangling (修饰)
void foo(int x);     // → _Z3fooi  (Itanium ABI)
void foo(double x);  // → _Z3food

// C: 函数名就是符号名
void foo(int x);     // → foo
void foo(double x);  // → foo (C 不支持同名重载 → 链接错误)
```

### extern "C" 用法

```cpp
// 告诉 C++ 编译器：用 C 的链接规范
extern "C" {
    void c_function(int x);
    int calc_factor(double price, double volume);
}

// 在 C++ 中定义 C 可调用的函数
extern "C" int quant_factor(double price, double volume) {
    return static_cast<int>(price * volume);
}
```

### 头文件兼容技巧

```cpp
// quant_interface.h —— C 和 C++ 都可用
#ifdef __cplusplus
extern "C" {
#endif

    int quant_factor(double price, double volume);
    void* create_context();
    void destroy_context(void* ctx);

#ifdef __cplusplus
}
#endif
```

### 可移植性注意事项

| 问题 | C | C++ |
|------|---|-----|
| 结构体 | `struct Foo f;` | `Foo f;` (可省略 struct) |
| bool | C23 有 `bool`，以前用 int | `true`/`false` |
| NULL vs nullptr | `NULL` / `(void*)0` | `nullptr` |
| 异常 | 不支持 | 支持（跨边界需捕获） |
| 函数指针 | `void (*f)(int)` | 同左，但 mangling 不同 |

---

## 2. pybind11 高级用法

### 快速回顾——基础绑定

```python
# CMakeLists.txt (简化)
# pybind11_add_module(quant_core quant_bindings.cpp)
```

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
namespace py = pybind11;

// 基础函数
int add(int a, int b) { return a + b; }

PYBIND11_MODULE(quant_core, m) {
    m.doc() = "Quant core acceleration module";

    m.def("add", &add, "Add two numbers");
}
```

### NumPy 数组绑定

```cpp
#include <pybind11/numpy.h>

// 接受 numpy array，返回处理后的 numpy array
py::array_t<double> vector_mul(py::array_t<double> input, double factor) {
    auto buf = input.request();  // 获取底层 buffer
    double* ptr = static_cast<double*>(buf.ptr);
    size_t size = buf.size;

    // 创建输出数组
    auto result = py::array_t<double>(buf.size);
    auto rbuf = result.request();
    double* rptr = static_cast<double*>(rbuf.ptr);

    // 向量化计算
    for (size_t i = 0; i < size; ++i) {
        rptr[i] = ptr[i] * factor;
    }

    return result;
}

// 就地修改（零拷贝）
void vector_mul_inplace(py::array_t<double> arr, double factor) {
    auto buf = arr.request();
    double* ptr = static_cast<double*>(buf.ptr);
    for (size_t i = 0; i < buf.size; ++i)
        ptr[i] *= factor;
}
```

### STL 容器绑定

```cpp
#include <pybind11/stl.h>

// 自动转换 std::vector ↔ Python list
std::vector<double> process_prices(const std::vector<double>& prices) {
    std::vector<double> result;
    result.reserve(prices.size());
    for (auto p : prices)
        result.push_back(p * 1.1);
    return result;
}

// std::map ↔ Python dict
std::map<std::string, double> compute_metrics(
        const std::map<std::string, std::vector<double>>& data) {
    std::map<std::string, double> metrics;
    for (auto& [name, values] : data) {
        double sum = 0;
        for (auto v : values) sum += v;
        metrics[name] = values.empty() ? 0.0 : sum / values.size();
    }
    return metrics;
}
```

### 自定义数据类型的绑定

```cpp
// C++ 结构体
struct Trade {
    std::string symbol;
    double price;
    int64_t volume;
    int64_t timestamp;
};

py::class_<Trade>(m, "Trade")
    .def(py::init<>())
    .def(py::init<const std::string&, double, int64_t, int64_t>())
    .def_readwrite("symbol", &Trade::symbol)
    .def_readwrite("price", &Trade::price)
    .def_readwrite("volume", &Trade::volume)
    .def_readwrite("timestamp", &Trade::timestamp)
    .def("__repr__", [](const Trade& t) {
        return "<Trade " + t.symbol + " $" + std::to_string(t.price) + ">";
    });

// C++ 类
class FactorEngine {
    std::vector<double> prices_;
public:
    void add_price(double p) { prices_.push_back(p); }
    double calc_ma(int window);
    void reset() { prices_.clear(); }
};

py::class_<FactorEngine>(m, "FactorEngine")
    .def(py::init<>())
    .def("add_price", &FactorEngine::add_price)
    .def("calc_ma", &FactorEngine::calc_ma)
    .def("reset", &FactorEngine::reset);
```

### 自定义操作 (Operator Overloads)

```cpp
py::class_<Trade>(m, "Trade")
    .def(py::self + py::self)    // operator+
    .def(py::self == py::self)   // operator==
    .def("__lt__", &Trade::operator<);
```

---

## 3. ctypes vs pybind11 性能对比

| 维度 | ctypes | pybind11 |
|------|--------|----------|
| 类型检查 | 手动 | 自动（模板推导） |
| NumPy 支持 | `numpy.ctypeslib` | 原生 `py::array_t` |
| **调用开销** | **~200-500 ns** | **~30-80 ns** |
| 异常传递 | 需 C 错误码 | 自动 C++↔Python 异常 |
| 代码量 | 大（类型声明） | 小（模板自动） |
| 编译要求 | 无（仅共享库） | 需要 C++ 编译 |

```
Benchmark (1M calls, empty function):
  pybind11:     52 ms   (52 ns/call)
  ctypes:      340 ms   (340 ns/call)
  纯 Python:  1200 ms   (1200 ns/call)

→ pybind11 比 ctypes 快 ~6.5x，比纯 Python 快 ~23x
```

### ctypes 示例（对比用）

```python
# ctypes 绑定
import ctypes
lib = ctypes.CDLL("./quant_core.dll")

lib.vector_mul.argtypes = [ctypes.POINTER(ctypes.c_double),
                           ctypes.c_int, ctypes.c_double]
lib.vector_mul.restype = ctypes.POINTER(ctypes.c_double)

# 需要手动管理内存！
def vector_mul_ctypes(arr, factor):
    n = len(arr)
    c_arr = (ctypes.c_double * n)(*arr)
    result_ptr = lib.vector_mul(c_arr, n, factor)
    return [result_ptr[i] for i in range(n)]
```

---

## 4. AVX 加速器复用/增强

基于已有的 AVX pybind11 量化加速器，增强因子计算：

```cpp
#include <immintrin.h>

// 单精度 SIMD 向量乘法
void avx_mul_ps(float* out, const float* in, float factor, size_t n) {
    __m256 factor_vec = _mm256_set1_ps(factor);
    size_t i = 0;

    // 主循环: 每次处理 8 个 float
    for (; i + 7 < n; i += 8) {
        __m256 data = _mm256_loadu_ps(in + i);
        __m256 result = _mm256_mul_ps(data, factor_vec);
        _mm256_storeu_ps(out + i, result);
    }

    // 剩余元素: 标量处理
    for (; i < n; ++i)
        out[i] = in[i] * factor;
}

// 双精度 SIMD（每次 4 个 double）
void avx_mul_pd(double* out, const double* in, double factor, size_t n) {
    __m256d factor_vec = _mm256_set1_pd(factor);
    size_t i = 0;
    for (; i + 3 < n; i += 4) {
        __m256d data = _mm256_loadu_pd(in + i);
        __m256d result = _mm256_mul_pd(data, factor_vec);
        _mm256_storeu_pd(out + i, result);
    }
    for (; i < n; ++i)
        out[i] = in[i] * factor;
}
```

### 完整 pybind11 + AVX 因子计算器

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <immintrin.h>
#include <cstdint>
#include <cmath>
#include <vector>

namespace py = pybind11;

// ========== SIMD 内核 ==========

// 向量化加法: out[i] = a[i] + b[i]
py::array_t<double> simd_add(py::array_t<double> a, py::array_t<double> b) {
    auto buf_a = a.request(), buf_b = b.request();
    auto n = buf_a.size;
    auto result = py::array_t<double>(n);
    auto rbuf = result.request();

    double* pa = static_cast<double*>(buf_a.ptr);
    double* pb = static_cast<double*>(buf_b.ptr);
    double* pr = static_cast<double*>(rbuf.ptr);

    size_t i = 0;
    for (; i + 3 < n; i += 4) {
        __m256d va = _mm256_loadu_pd(pa + i);
        __m256d vb = _mm256_loadu_pd(pb + i);
        _mm256_storeu_pd(pr + i, _mm256_add_pd(va, vb));
    }
    for (; i < n; ++i) pr[i] = pa[i] + pb[i];
    return result;
}

// 向量化移动平均
py::array_t<double> simd_sma(py::array_t<double> prices, int window) {
    auto buf = prices.request();
    double* p = static_cast<double*>(buf.ptr);
    size_t n = buf.size;
    auto result = py::array_t<double>(n);
    auto rbuf = result.request();
    double* r = static_cast<double*>(rbuf.ptr);

    // 前缀和实现 O(n)
    std::vector<double> prefix(n + 1, 0.0);
    for (size_t i = 0; i < n; ++i)
        prefix[i + 1] = prefix[i] + p[i];

    for (size_t i = 0; i < n; ++i) {
        if (i + 1 < static_cast<size_t>(window)) {
            r[i] = prefix[i + 1] / (i + 1);
        } else {
            r[i] = (prefix[i + 1] - prefix[i + 1 - window]) / window;
        }
    }
    return result;
}

// 向量化计算收益率
py::array_t<double> simd_returns(py::array_t<double> prices) {
    auto buf = prices.request();
    double* p = static_cast<double*>(buf.ptr);
    size_t n = buf.size;
    auto result = py::array_t<double>(n);
    auto rbuf = result.request();
    double* r = static_cast<double*>(rbuf.ptr);

    r[0] = 0.0;
    size_t i = 1;
    #pragma GCC ivdep  // 告诉编译器数据无依赖
    for (; i + 3 < n; i += 4) {
        __m256d curr = _mm256_loadu_pd(p + i);
        __m256d prev = _mm256_loadu_pd(p + i - 1);
        __m256d ret = _mm256_div_pd(
            _mm256_sub_pd(curr, prev), prev);
        _mm256_storeu_pd(r + i, ret);
    }
    for (; i < n; ++i)
        r[i] = (p[i] - p[i-1]) / p[i-1];

    return result;
}

// ========== 量化因子 ==========

// 计算多个因子一次性返回
struct Factors {
    std::vector<double> sma5;
    std::vector<double> sma20;
    std::vector<double> returns;
    std::vector<double> volatility;
};

Factors compute_all_factors(py::array_t<double> prices) {
    auto buf = prices.request();
    double* p = static_cast<double*>(buf.ptr);
    size_t n = buf.size;

    // 用 py::array 接收 SIMD 结果（虽然这里有拷贝，但演示完整流程）
    auto sma5_arr = simd_sma(prices, 5);
    auto sma20_arr = simd_sma(prices, 20);
    auto ret_arr = simd_returns(prices);

    auto b5 = sma5_arr.request();
    auto b20 = sma20_arr.request();
    auto br = ret_arr.request();

    Factors f;
    f.sma5.assign(static_cast<double*>(b5.ptr),
                  static_cast<double*>(b5.ptr) + n);
    f.sma20.assign(static_cast<double*>(b20.ptr),
                   static_cast<double*>(b20.ptr) + n);
    f.returns.assign(static_cast<double*>(br.ptr),
                     static_cast<double*>(br.ptr) + n);
    f.volatility.resize(n, 0.0);

    // 波动率: 滚动标准差
    for (size_t i = 20; i < n; ++i) {
        double sum = 0, sum_sq = 0;
        for (size_t j = i - 20; j < i; ++j) {
            sum += f.returns[j];
            sum_sq += f.returns[j] * f.returns[j];
        }
        double mean = sum / 20;
        f.volatility[i] = std::sqrt(sum_sq / 20 - mean * mean);
    }

    return f;
}

// ========== 绑定 ==========
PYBIND11_MODULE(quant_factors, m) {
    m.doc() = "Quantitative factor computation with AVX acceleration";

    m.def("simd_add", &simd_add, "SIMD vector addition");
    m.def("simd_sma", &simd_sma, "SIMD simple moving average");
    m.def("simd_returns", &simd_returns, "SIMD returns computation");

    py::class_<Factors>(m, "Factors")
        .def_readonly("sma5", &Factors::sma5)
        .def_readonly("sma20", &Factors::sma20)
        .def_readonly("returns", &Factors::returns)
        .def_readonly("volatility", &Factors::volatility)
        .def("__repr__", [](const Factors& f) {
            return "<Factors with " + std::to_string(f.sma5.size()) + " entries>";
        });

    m.def("compute_all_factors", &compute_all_factors,
          "Compute all factors from price array");
}
```

---

## 5. Python 测试脚本

```python
# test_quant_factors.py
import quant_factors
import numpy as np
import time

# 生成测试数据
np.random.seed(42)
prices = 100.0 + np.cumsum(np.random.randn(100000) * 0.5)

# C++ AVX 加速
t1 = time.time()
factors = quant_factors.compute_all_factors(prices)
t2 = time.time()
print(f"C++ AVX: {t2-t1:.3f}s")

# Python 纯版本对比
def sma_py(prices, w):
    result = np.zeros_like(prices)
    for i in range(len(prices)):
        result[i] = prices[max(0,i-w+1):i+1].mean()
    return result

t1 = time.time()
sma5_py = sma_py(prices, 5)
sma20_py = sma_py(prices, 20)
t2 = time.time()
print(f"Python: {t2-t1:.3f}s")

# 验证一致性
print(f"C++ sma5[:5]: {factors.sma5[:5]}")
print(f"Py  sma5[:5]: {sma5_py[:5]}")
print(f"Max diff: {np.max(np.abs(np.array(factors.sma5) - sma5_py)):.2e}")
```

---

## 总结

| 技术 | 适用场景 | 开销/优势 |
|------|---------|----------|
| `extern "C"` | C 库的 C++ 调用 / C ABI 兼容 | 0 开销 |
| ctypes | 简单封装、无 C++ 环境 | 调用延迟 ~300ns |
| pybind11 | **主力**：高性能、复杂类型 | 调用延迟 ~50ns |
| pybind11+NumPy | 数组数据处理 | 零拷贝 buffer access |
| pybind11+AVX | 量化因子向量化计算 | 4-8x 加速 |
| 自定义类型 | 结构体/类传递 | 自动序列化 |
