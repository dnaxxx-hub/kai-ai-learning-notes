# C++20 核心特性 — 从"C with Classes"到现代C++

**目标**: 理解 C++20 的关键新特性，把现有 C 项目（libkds）和 C++17 项目（KVStore）的知识升级到现代实践。

---

## 1. Concepts（概念）

### 为什么 Concept ≠ 模板约束

很多人把 Concept 当成"更优雅的模板约束"，但这个理解太浅了。Concept 的本质是**谓词**（predicate）——它描述类型应该具有的**语义能力**，而约束（constraint）只是语法层面的要求。

```cpp
// 语法约束：能写 "a + b" 就行
template<typename T> concept Addable = requires(T a, T b) { a + b; };

// 概念：不仅要有 +，还要满足交换律、结合律等语义
// 遗憾的是 C++20 无法表达完整语义，只能通过命名约定
template<typename T>
concept MathVector = requires(T a, T b, double s) {
    typename T::value_type;        // 必须有 value_type 类型别名
    a + b;                         // 支持加法
    a * b;                         // 支持点乘
    a * s;                         // 支持标量乘法
    { a.size() } -> std::same_as<size_t>;  // size() 返回 size_t
};
```

### SFINAE 时代 vs Concept 时代

C++17 的写法——读代码 5 分钟，等编译 2 分钟，看错误 10 页：

```cpp
// C++17 SFINAE 写法
template<typename T,
    std::enable_if_t<std::is_arithmetic_v<T>, int> = 0>
auto sum(const std::vector<T>& v) {
    // ...
}

// C++20 Concept 写法
template<MathVector T>
auto sum(const std::vector<T>& v);
```

Concept 的最大优势不是"少打字"，而是**错误信息从 500 行降到 5 行**。当 `std::vector<std::string>` 传入时，编译器直接说"`std::string` 不满足 `MathVector`，因为没有 `value_type`"，而不是洪水般的模板实例化回溯。

### 实战：Concept-driven sum()

```cpp
#include <concepts>
#include <ranges>
#include <numeric>

template<typename T>
concept Numeric = std::is_arithmetic_v<T>;

// constrained function template
template<Numeric T>
T sum(const std::vector<T>& v) {
    T init{};
    for (const auto& x : v) init += x;
    return init;
}

// 或者用 auto 参数（更"概念化"的语法）
auto sum2(const std::ranges::range auto& v) -> std::ranges::range_value_t<decltype(v)> {
    // 但需要运行时保证 operator+= 存在，不如上面严格
}
```

**与 libkds 的关系**: libkds 的 hash_map 用 `void*` 和 `size_t elem_size` 实现泛型。C++20 的 Concept 让你在编译期就说清楚"这个类型必须可哈希、可比较"，而不是运行时 `memcmp` + `assert`。

---

## 2. Ranges（范围）

### 从迭代器对到整个范围

```cpp
// C++17 两个迭代器
std::sort(v.begin(), v.end());

// C++20 一个范围
std::ranges::sort(v);       // 自动推导 begin/end
std::ranges::sort(v, std::greater{});  // 自定义比较器
```

这不仅仅是少打几个字。Ranges 的核心贡献是**组合能力**——通过 View 实现惰性求值的管道。

### View: 惰性求值的管道

```cpp
#include <ranges>
#include <vector>

auto odd = [](int x) { return x % 2 == 1; };
auto square = [](int x) { return x * x; };

std::vector<int> v = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

// 管道操作：编译期组合，运行时惰性求值
auto r = v | std::views::filter(odd)
           | std::views::transform(square)
           | std::views::take(3);
// r 不是 vector，是一个 view
// 直到遍历 r（或调用 std::ranges::distance/ranges::to）才真正求值

for (int x : r) {
    fmt::print("{}\n", x);  // 输出: 1, 9, 25
}
```

### 与 Python Generator 的对比

| 特性 | C++20 Ranges | Python Generator |
|------|-------------|------------------|
| 求值时点 | 编译期管道路由，遍历时求值 | 运行时 yield 逐个生成 |
| 类型安全 | 强类型，编译期检查 | 动态类型 |
| 性能 | 零开销抽象（通常不会生成中间容器） | 有解释器开销 |
| 错误 | 编译期 | 运行时 |
| 表达能力 | 必须闭合成容器才能 everywhere 用 | 天然惰性序列 |

### 实战：用 Ranges 重写环形缓冲区遍历

```cpp
// 假设 libkds 的 ring_buffer（简化版）
template<typename T>
class ring_buffer {
    std::vector<T> data_;
    size_t head_ = 0;
    size_t tail_ = 0;
    size_t count_ = 0;
public:
    // C++20: 通过 ranges 提供惰性视图
    auto view() {
        return std::views::counted(data_.begin(), count_);
    }

    // 直接获取最新 N 个元素
    auto last_n(size_t n) {
        // 注意环形缓冲区连续遍历需要处理 wrap-around
        // 这里简化：假设 data_ 已排序，非环形
        return data_
            | std::views::reverse
            | std::views::take(n);
    }
};

// 用法：取最后 100 个 tick 求平均值
auto avg = std::ranges::fold_left(
    ring | std::views::drop(tick_count - 100),
    0.0, std::plus<>{}
) / 100.0;
```

**与 libkds 的关系**: libkds 的 ring buffer 遍历依靠 `while (idx != tail) { ... idx = (idx+1)%cap; }`。用 Ranges 后可以声明式地表达"取最后 N 个"、"过滤有效数据"、"映射到价格"。

---

## 3. Coroutines（协程）

### C++20 协程模型

C++20 的协程是**栈无关的**（stackless）——每次切换只保存几个寄存器和 promise 对象，不涉及完整栈帧切换。这是它和 Python/Go 协程最根本的区别。

三个关键词：
- `co_await` — 挂起等待某个异步操作
- `co_yield` — 产生一个值（挂起，返回给调用者）
- `co_return` — 结束协程

### Generator\<T\> 模式

C++23 才有 `std::generator`，但 C++20 可以用自己写一个很简单的 Generator：

```cpp
#include <coroutine>
#include <optional>
#include <concepts>

template<typename T>
class Generator {
public:
    struct promise_type {
        T current_value;
        auto get_return_object() {
            return Generator{std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        auto initial_suspend() { return std::suspend_always{}; }
        auto final_suspend() noexcept { return std::suspend_always{}; }
        auto yield_value(T value) {
            current_value = std::move(value);
            return std::suspend_always{};
        }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };

    std::coroutine_handle<promise_type> handle;
    explicit Generator(auto h) : handle(h) {}
    ~Generator() { if (handle) handle.destroy(); }

    // 禁止拷贝，允许移动
    Generator(const Generator&) = delete;
    Generator(Generator&& other) noexcept : handle(std::exchange(other.handle, {})) {}

    // 迭代器
    struct iterator {
        std::coroutine_handle<promise_type> h;
        T operator*() const { return h.promise().current_value; }
        iterator& operator++() { h.resume(); return *this; }
        bool operator!=(std::default_sentinel_t) const {
            return h && !h.done();
        }
    };

    iterator begin() {
        if (handle) handle.resume();
        return iterator{handle};
    }
    std::default_sentinel_t end() { return {}; }
};
```

### 实战：Fibonacci 生成器

```cpp
Generator<size_t> fibonacci(size_t n) {
    size_t a = 0, b = 1;
    for (size_t i = 0; i < n; ++i) {
        co_yield a;          // 产生一个值，挂起
        auto next = a + b;
        a = b;
        b = next;
    }
    // co_return 隐式调用 return_void()
}

// 使用
for (auto x : fibonacci(10)) {
    fmt::print("{} ", x);   // 0 1 1 2 3 5 8 13 21 34
}
```

### 与 Python 协程的对比

| 特性 | C++20 | Python async/await |
|------|-------|-------------------|
| 栈 | 栈无关（stackless） | 基于栈 |
| 切换开销 | ~1ns（函数调用级别） | ~50-100ns（Python 对象操作） |
| 内存 | 编译期确定大小 | 动态 |
| 线程对比 | 协程 ~1ns vs 线程 ~1μs | 差距缩小但仍有数量级差异 |
| 适用场景 | 高性能泛型生成器/异步 | IO bound 网络应用 |

**与量化系统的关系**: 回测中经常需要生成海量 tick 数据流。用协程 generator 可以写成 `Generator<Tick> replay_ticks(const std::string& csv_path)`，惰性逐行读取，不把整个历史加载到内存。C 里同样的逻辑得手写状态机。

---

## 4. Modules（模块）

### 从 .h 到 .cppm

传统头文件的痛点：
1. `#include` 文本粘贴 —— `a.h` 包含 `b.h`，`b.h` 包含 `c.h`，最终 `a.cpp` 编译处理了几万行
2. 宏污染 —— `#define min(a,b) ((a)<(b)?(a):(b))` 摧毁一切
3. ODR（单一定义规则）违例 —— 两个头文件定义了同名函数，链接报错

Modules 解决所有问题：**符号导出是显式的，导入是编译期缓存的，没有宏泄漏**。

```cpp
// math_utils.cppm
export module math_utils;

import <concepts>;
import <type_traits>;

// 导出概念（模块内的概念可以被外界使用）
export template<typename T>
concept Numeric = std::is_arithmetic_v<T>;

// 导出函数（只导出显式标记的内容）
export template<Numeric T>
T clamped(T value, T lo, T hi) {
    return std::min(std::max(value, lo), hi);
}

// 不导出 —— 模块私有，外部不可见
template<Numeric T>
T internal_helper(T x) { return x * 2; }

// 导出带约束的类
export template<Numeric T>
struct Stats {
    T sum, mean, stddev;
};
```

### 使用模块

```cpp
// main.cpp
import math_utils;
import <iostream>;

int main() {
    auto x = clamped(42.5, 0.0, 100.0);  // OK
    
    // internal_helper(1.0);  // ❌ 编译错误，未导出
    
    std::cout << x << "\n";
}
```

### 与 libkds 现有 .h + .c 结构的关系

libkds 是纯 C，所以 modules 不直接适用。但如果你在未来用 C++ 包装 libkds 的组件（比如 `kds_dynarray` 包装成 `kds::array<T>`），Modules 提供比头文件更干净的接口：

```
// kds/array.cppm
export module kds.array;
import <cstddef>;

// 内部仍链接 C 实现
extern "C" {
    #include "kds_dynarray.h"    // 只在这里 include
}

// 导出 C++ 接口
export template<typename T>
class dynarray {
    // ...
};
```

模块内部包含 C 头文件，但外部使用者只看到干净的 `import kds.array`。

---

## 5. 其他关键特性

### std::span — 不拥有所有权的数组视图

你写过多少次 `void process(double* data, size_t len)`？C 风格的指针+长度传参的痛点：
- 调用者可能传 `nullptr` 和 `0`
- 没有边界检查
- 语义上分不清"修改缓冲区"还是"只读"

```cpp
#include <span>

// C 风格
void legacy_process(double* data, size_t len);

// C++20 span
void modern_process(std::span<double> data);
void modern_process(std::span<const double> data);  // 只读

std::vector<double> v = {1.0, 2.0, 3.0};
double arr[] = {4.0, 5.0, 6.0};

modern_process(v);             // vector → span（自动）
modern_process(arr);           // C array → span（自动）
modern_process({arr + 1, 2});  // 手动构造子视图（但不拷贝）
```

**与 libkds 的关系**: `kds_dynarray` 的 `data` 和 `size` 字段天然就是 `std::span` 的 C 形态。包装后可以写 `kds_dynarray_process(std::span(data, size))`，边界安全+迭代器支持。

### std::format — 类型安全格式化

```cpp
#include <format>

// C 风格
char buf[256];
snprintf(buf, sizeof(buf), "price=%.2f, qty=%d, symbol=%s", price, qty, sym);

// C++20 风格
auto msg = std::format("price={:.2f}, qty={}, symbol={}", price, qty, sym);
// 不需要缓冲区大小计算，不需要担心 buffer overflow
// 类型不匹配 → 编译错误，不是运行时 segfault
```

**与 KVStore 的关系**: 日志从 `fprintf(log_fp, "op=%s key=%s\n", op_name, key)` 改为 `std::format("op={} key={}", op_name, key)`，类型安全，还能格式化为 JSON。

### std::optional / std::expected — 错误处理

```cpp
#include <optional>
#include <expected>

// optional：可能没有值
std::optional<double> parse_price(const std::string& s) {
    double d;
    auto [ptr, ec] = std::from_chars(s.data(), s.data() + s.size(), d);
    if (ec == std::errc()) return d;
    return std::nullopt;
}

// expected：错误或值（C++23 std::expected，但很多库已实现）
// enum class Error { NotFound, ParseError, OutOfRange };
// std::expected<Value, Error> get(const std::string& key);

// 使用示例
auto price = parse_price("42.5");
if (price.has_value()) {
    fmt::print("price = {}\n", *price);
}
```

**与 KVStore 的关系**: 当前 KVStore 的 `get()` 可能抛 `std::out_of_range`。改用 `std::expected<Value, Error>` 后，调用者必须显式处理错误，编译器不会让你忽略。

### constexpr 增强

```cpp
constexpr std::vector<int> compute_fibonacci(size_t n) {
    std::vector<int> v = {0, 1};
    while (v.size() < n) v.push_back(v.back() + v[v.size() - 2]);
    return v;
}

// 编译期计算！
static constexpr auto fibs = compute_fibonacci(20);

// C++20 允许 vector/string 在 constexpr 上下文中动态分配
// 限制：分配的内存不能在运行时泄漏（必须匹配 delete）
```

---

## 6. 与现有项目桥接

### libkds 动态数组 → std::span

```
// 之前（C 风格）
void trade_batch_process(kds_dynarray* trades, double* prices_out, size_t* count_out);

// 之后（C++20 桥接）
void trade_batch_process(std::span<Trade> trades, std::span<double> prices_out);
```

### KVStore 错误处理 → std::expected

```
// 之前
Value get(const std::string& key) {
    // 不存在就抛出
    if (!map.count(key)) throw std::out_of_range("key not found");
    return map.at(key);
}

// 之后
std::expected<Value, Error> get(const std::string& key) {
    if (!map.count(key)) return std::unexpected(Error::NotFound);
    return map.at(key);
}
```

### 量化回测参数 → consteval（编译期常量）

```cpp
consteval double risk_free_rate() { return 0.03; }  // 编译期确定
consteval size_t max_positions() { return 100; }

// 回测参数如果算出来是编译期常量，零运行时开销
template<typename Strategy>
consteval auto validate_strategy() {
    // 编译期检查策略参数有效性
}
```

### 日志输出 → std::format

```
// 之前
fprintf(log_fp, "[%s] %s: %s\n", timestamp, level, message);

// 之后
log_fp << std::format("[{}] {}: {}\n", timestamp, level, message);
```

---

## 7. 代码示例汇总

### 7.1 Concept 定义 + 约束函数

```cpp
#include <concepts>
#include <vector>
#include <ranges>

template<typename T>
concept Scalar = std::is_arithmetic_v<T>;

template<typename T>
concept VectorLike = requires(T v) {
    typename T::value_type;
    v.size();
    v[0];
};

template<VectorLike V>
    requires Scalar<typename V::value_type>
auto dot(const V& a, const V& b) {
    using T = typename V::value_type;
    T result{};
    for (size_t i = 0; i < a.size(); ++i)
        result += a[i] * b[i];
    return result;
}
```

### 7.2 Ranges Pipeline

```cpp
#include <ranges>
#include <vector>
#include <format>
#include <print>  // C++23

std::vector<int> ticks = {101, 102, 99, 103, 98, 104, 97};

// 取最近 5 个价格，过滤异常值，映射为收益率
auto returns = ticks
    | std::views::reverse
    | std::views::take(5)
    | std::views::filter([](int p) { return p > 0; });
    // | std::views::transform([](int p) -> double { return (p - 100.0) / 100.0; });
```

### 7.3 Coroutine Generator (Fibonacci)

```cpp
Generator<size_t> fibonacci(size_t n) {
    size_t a = 0, b = 1;
    for (size_t i = 0; i < n; ++i) {
        co_yield a;
        auto next = a + b;
        a = b;
        b = next;
    }
}

// 量化场景：生成 tick 数据流
Generator<Tick> tick_generator(const std::span<const std::string> csv_lines) {
    for (const auto& line : csv_lines) {
        Tick t = parse_tick(line);
        co_yield t;
    }
}
```

### 7.4 Module 声明与导入

```cpp
// === kds_wrap.cppm ===
export module kds_wrap;
import <span>;
import <concepts>;

export template<typename T>
concept Mappable = requires(T v) {
    v[0];
};

export template<Mappable M>
auto process_data(std::span<int> data) {
    // C++ 包装 C 实现
}
```

### 7.5 span / format / optional 用法

```cpp
#include <span>
#include <format>
#include <optional>
#include <print>

void analyze(std::span<const double> prices) {
    if (prices.empty()) return;

    auto mean = std::ranges::fold_left(prices, 0.0, std::plus<>{}) / prices.size();
    std::print("mean price = {:.2f}\n", mean);
}

std::optional<double> safe_divide(double a, double b) {
    if (b == 0.0) return std::nullopt;
    return a / b;
}

auto ratio = safe_divide(3.0, 4.0);
std::print("ratio = {}\n", ratio.value_or(0.0));
```

---

## 快速备忘卡

| 特性 | C++17 (你现在的做法) | C++20 (升级方向) |
|------|---------------------|-----------------|
| 类型约束 | `enable_if` / SFINAE | `concept` / `requires` |
| 排序 | `std::sort(b, e)` | `std::ranges::sort(v)` |
| 迭代器组合 | 手写 for + if | `views::filter \| transform` |
| 惰性序列 | `for` 循环 + push_back | `Generator<T>` 协程 |
| 组织代码 | .h + .cpp 包含 | .cppm 模块 |
| 数组视图 | `T* + size_t` | `std::span<T>` |
| 格式化 | `printf` / `sprintf` | `std::format` |
| 错误处理 | 异常 / 错误码 | `std::optional` / `std::expected` |
| 编译期计算 | `constexpr` (有限) | `constexpr vector/string` + `consteval` |
| 协程 | 第三方库 (libco, Boost.Coroutine) | `co_await` / `co_yield` / `co_return` |

---

**下一步**: `cpp_02_ranges_deep.md` 深入 Ranges 的适配器模式、自定义 View、以及用 Ranges 重写 libkds 的 hash_map 迭代器。
