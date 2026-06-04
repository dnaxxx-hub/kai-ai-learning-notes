# C++20/23 新特性

## Concept (C++20)

编译期约束模板参数，替代 SFINAE 的意图表达：

```cpp
template<typename T>
concept Integral = std::is_integral_v<T>;

template<typename T>
concept Hashable = requires(T a) {
    { std::hash<T>{}(a) } -> std::same_as<size_t>;
    // requires 表达式：检查表达式合法且返回类型匹配
};

template<typename T>
concept Comparable = requires(T a, T b) {
    { a < b } -> std::convertible_to<bool>;
    a == b;
};

// 三种使用方式
template<Integral T>             // 方式1
T add(T a, T b) { return a + b; }

template<typename T>             // 方式2
    requires Hashable<T>
void process(const T& v);

auto multiply = [](Comparable auto a, Comparable auto b) { // 方式3
    return a * b;
};
```

### Concept vs SFINAE

| 对比 | SFINAE | Concept |
|------|--------|---------|
| 可读性 | 模板套模板，晦涩 | 自然语言级 |
| 错误信息 | 几百行模板错误 | 清晰的约束违反提示 |
| 表达力 | 间接 | 直接（requires 表达式） |
| 编译性能 | 增加实例化重载 | 更优（提前否决） |

## Range (C++20)

惰性视图和管道操作：

```cpp
#include <ranges>
namespace rv = std::views;

std::vector vec = {1, 2, 3, 4, 5, 6, 7, 8};

auto result = vec
    | rv::filter([](int n) { return n % 2 == 0; })
    | rv::transform([](int n) { return n * n; })
    | rv::take(3);

for (int v : result) std::cout << v << ' ';  // 4 16 36
```

常见 view：
- `views::filter` — 过滤
- `views::transform` — 映射
- `views::take/drop` — 取/丢前 N 个
- `views::join` — 展平嵌套范围
- `views::reverse` — 反转
- `views::zip` (C++23) — 并行迭代

## Coroutine (C++20)

协程：可挂起/恢复的函数，零开销抽象。

```cpp
// generator<T> — 简化版
template<typename T>
struct Generator {
    struct promise_type {
        T value_;
        Generator get_return_object() { return Generator{this}; }
        std::suspend_always initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        std::suspend_always yield_value(T v) {
            value_ = v;
            return {};
        }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
    // ...
};

Generator<int> fib() {
    int a = 0, b = 1;
    while (true) {
        co_yield a;
        auto t = a + b;
        a = b;
        b = t;
    }
}

// 使用
for (int v : fib()) {
    if (v > 100) break;
    std::cout << v << ' ';
}
```

## Module (C++20)

替代 `#include` 的模块化编译模型：

```cpp
// math.ixx — 模块接口
export module math;

export int add(int a, int b) { return a + b; }
export namespace detail {
    int internal_helper(int);
}

// main.cpp
import math;  // 不是 #include "math.h"

int main() {
    return add(3, 4);  // 快速编译
}
```

优势：无头文件、无宏泄露、无重复编译、编译速度提升 5-10x。

## std::span & std::format (C++20)

**std::span** — 连续内存的非拥有视图：

```cpp
void process(std::span<int> data) {
    for (int& v : data) v *= 2;
}

int arr[] = {1, 2, 3, 4};
std::vector vec = {5, 6, 7, 8};
process(arr);          // 数组 → span
process(vec);          // vector → span
process({arr, 2});     // 前两个元素
```

替代 `(int* data, size_t size)` 参数对。

**std::format** — Python 风格格式化：

```cpp
std::string s = std::format("Hello, {}! You are {} years old.", name, age);
std::string s2 = std::format("{:.2f} {:#x}", 3.14159, 255);
// → "3.14 0xff"
```

## C++23 特性一览

```cpp
#include <expected>
#include <print>
#include <flat_map>

// std::expected — 带错误码的返回值
std::expected<int, std::error_code> parse_int(std::string_view s) {
    if (auto val = std::from_chars(s.data(), ...); val.ec)
        return std::unexpected(val.ec);
    return 42;
}

// std::print — 类型安全的输出
std::println("Hello, {}!", "C++23");  // → "Hello, C++23!\n"

// std::flat_map — 连续存储的有序映射
std::flat_map<std::string, int> fm = {{"a", 1}, {"c", 3}, {"b", 2}};
// 底层用两个 vector 存储，插入 O(n)，遍历极快

// std::optional 改进
auto opt = std::optional("hello");  // CTAD 推导

// std::mdspan — 多维数组视图（类似 numpy）
// stacktrace — 可编程栈回溯
// std::generator — 标准库协程生成器
```
