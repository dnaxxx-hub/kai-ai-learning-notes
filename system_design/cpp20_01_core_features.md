# C++20 核心特性深度解析

> 现代C++编程 — 从C++11/14/17到C++20的关键演进

## 概览

C++20 是自 C++11 以来最大的标准版本，引入了四大核心语言特性（Modules、Concepts、Coroutines、Ranges）以及大量实用改进。本笔记聚焦**非协程**的核心语言和库特性，协程在后续笔记单独展开。

---

## 1. Concepts — 概念与约束

### 为什么需要 Concepts

模板编程的错误信息以"呕吐式"著称——当模板参数不满足要求时，编译器在实例化深处爆出数十页错误。Concepts 让模板约束成为**第一公民**，在调用点给出清晰错误，同时支持重载决议。

### 基本语法

```cpp
#include <concepts>
#include <type_traits>
#include <iostream>

// 1) 简单 Concept：类型为整型
template<typename T>
concept Integral = std::is_integral_v<T>;

// 2) 复合 Concept：可调用且返回 int
template<typename F, typename... Args>
concept IntCallable = requires(F f, Args... args) {
    { f(args...) } -> std::convertible_to<int>;
};

// 3) 类型约束的 auto 参数（精简函数模板）
void print_integral(Integral auto value) {
    std::cout << value << " (integral)\n";
}

// 4) requires 子句
template<typename T>
    requires std::is_floating_point_v<T>
T half(T value) { return value / 2.0; }

// 5) 带 Concept 的类模板
template<typename T>
concept Addable = requires(T a, T b) { a + b; };

template<Addable T>
T sum(T a, T b) { return a + b; }

int main() {
    print_integral(42);      // ✅ ok
    // print_integral(3.14); // ❌ 编译错误：double 不是 Integral
    
    std::cout << half(3.14) << "\n";    // 1.57 (double)
    std::cout << sum(1, 2) << "\n";     // 3
    // half(42); // ❌ int 不是 floating_point
}
```

### 实战：Concept 约束现有 libkds

```cpp
#include <concepts>
#include <span>

// 约束动态数组的数据类型必须可平凡复制
template<typename T>
concept TriviallyCopyable = std::is_trivially_copyable_v<T>;

template<TriviallyCopyable T>
class dynamic_array {
    T* data_;
    size_t size_, capacity_;
public:
    // ...
    std::span<T> view() { return {data_, size_}; }
};
```

这个约束防止将`std::string`等非平凡类型存入底层`memcpy`操作的数组，在编译期杜绝误用。

---

## 2. Modules — 模块系统

### 为何替代头文件

头文件的三大痼疾：
- **宏污染**：`#define` 影响所有 include 者
- **ODR 违规**：跨翻译单元的重复定义
- **编译慢**：头文件在每处 include 都重新解析

### 基本用法

```cpp
// math.cppm — 模块接口单元
export module math;

export namespace math {
    int add(int a, int b) { return a + b; }
    
    // 只声明不导出实现细节
    export int factorial(int n);
}

// 实现细节不导出
int math::factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}
```

```cpp
// main.cpp — 使用者
import math;  // ✅ 无宏污染，无 ODR

int main() {
    return math::add(1, 2);
}
```

### 子模块与分区

```cpp
// container.cppm
export module container;

export import :vector;    // 暴露分区
export import :map;
// :detail 分区不导出，对外隐藏
```

### 注意事项
- 编译器支持仍在追赶：MSVC 最成熟，GCC 13+/Clang 17+ 逐步支持
- 不建议在项目中全面迁移，新模块可采用
- 构建系统需升级：CMake 3.28+ 支持

---

## 3. Ranges — 范围库

Ranges 将算法和容器的组合从「迭代器对」提升为「视图+管道」范式，极大提高代码表达力。

### 从迭代器到 Range

```cpp
#include <ranges>
#include <vector>
#include <iostream>
#include <algorithm>

namespace rv = std::views;
namespace ra = std::ranges;

int main() {
    std::vector<int> nums = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

    // 旧方式：迭代器对 + 算法嵌套
    std::vector<int> even;
    std::copy_if(nums.begin(), nums.end(), 
                 std::back_inserter(even), 
                 [](int n) { return n % 2 == 0; });
    std::vector<int> result_old;
    std::transform(even.begin(), even.end(),
                   std::back_inserter(result_old),
                   [](int n) { return n * n; });

    // 新方式：Ranges 管道
    auto result_new = nums 
        | rv::filter([](int n) { return n % 2 == 0; })
        | rv::transform([](int n) { return n * n; });

    for (int n : result_new)
        std::cout << n << " ";  // 4 16 36 64 100
}
```

### 关键 View 适配器

| 适配器 | 作用 | 示例 |
|--------|------|------|
| `filter` | 满足谓词的元素 | `v \| filter(is_even)` |
| `transform` | 映射变换 | `v \| transform(square)` |
| `take` | 取前N个 | `v \| take(5)` |
| `drop` | 跳过前N个 | `v \| drop(3)` |
| `reverse` | 反向 | `v \| reverse` |
| `join` | 展平嵌套 | `vec_of_vec \| join` |
| `split` | 分割 | `str \| split(',')` |
| `stride` | 步进 | `v \| stride(2)` |
| `common` | 转普通范围 | `v \| common` |
| `zip` | 打包多个范围(C++23) | `zip(v1, v2)` |

### 惰性求值

View 是**惰性求值**的——不拥有数据，迭代时才计算：

```cpp
auto view = nums | rv::filter(is_prime) | rv::transform(square);
// 此时无任何计算
for (int n : view) {  // 迭代时才逐个过滤+映射
    // ...
}
```

### 实战：量化数据流

```cpp
#include <ranges>
#include <vector>
#include <numeric>

struct Bar { double open, high, low, close, volume; };

// 从K线数据提取收盘价并计算简单移动平均
auto sma(const std::vector<Bar>& bars, int period) {
    auto closes = bars | rv::transform(&Bar::close);
    
    // 滑动窗口计算SMA
    // 注意：C++20 Ranges 没有内置 sliding_window，C++23 有
    // 这里展示用 accumulate 在有限场景替代
    auto window = closes | rv::drop(bars.size() - period);
    double sum = std::accumulate(window.begin(), window.end(), 0.0);
    return sum / period;
}

// 生成交易信号：收盘价突破布林带上轨
auto bollinger_bands(const std::vector<Bar>& bars, int period, double k) {
    auto closes = bars | rv::transform(&Bar::close);
    // ... 组合视图管道处理
}
```

---

## 4. Spans — 连续内存视图

`std::span<T>` 是一个**非拥有**的连续内存序列视图（类似于 `std::string_view` 但针对任意连续容器）。

```cpp
#include <span>
#include <vector>
#include <array>
#include <iostream>

// 函数参数用 span 代替 (T*, size_t) 或 const vector&
double average(std::span<const double> values) {
    double sum = 0;
    for (auto v : values) sum += v;
    return sum / values.size();
}

int main() {
    std::vector vec = {1.0, 2.0, 3.0, 4.0};
    std::array  arr = {5.0, 6.0, 7.0};
    double      raw[] = {8.0, 9.0};
    
    // 三种连续容器都可用
    std::cout << average(vec) << "\n";  // 2.5
    std::cout << average(arr) << "\n";  // 6.0
    std::cout << average(raw) << "\n";  // 8.5
    
    // 子范围视图（不复制）
    auto sub = std::span(vec).subspan(1, 2);
    std::cout << average(sub) << "\n";  // (2.0+3.0)/2 = 2.5
    
    // 动态扩展
    std::span<int> s1;                       // 空 span
    std::span<int, 4> s2;                    // 固定大小
    std::span<int> s3(vec.data(), vec.size()); // 从指针+大小
}
```

### 与 string_view 对比

| 特性 | `span<T>` | `string_view` |
|------|-----------|---------------|
| 元素类型 | 任意 T | `char`/`wchar_t` |
| 可写性 | `span<T>` 可写/`span<const T>` 只读 | 只读 |
| 来源 | 连续容器/数组 | 字符串 |
| 子串 | `subspan()` | `substr()` |

---

## 5. 三路比较运算符 `<=>` (Spaceship Operator)

"三路比较"返回一个可以比较的对象，自动生成所有比较运算符（`<`, `>`, `<=`, `>=`, `==`, `!=`）。

```cpp
#include <compare>
#include <iostream>

struct Point {
    int x, y;
    
    // 自动生成所有比较运算符
    auto operator<=>(const Point&) const = default;
};

// 手动实现（复杂类型）
struct Version {
    int major, minor, patch;
    
    auto operator<=>(const Version& other) const {
        if (auto cmp = major <=> other.major; cmp != 0) return cmp;
        if (auto cmp = minor <=> other.minor; cmp != 0) return cmp;
        return patch <=> other.patch;
    }
    
    bool operator==(const Version&) const = default; // 需要显式提供 ==
};

int main() {
    Point a{1, 2}, b{1, 3};
    std::cout << std::boolalpha;
    std::cout << (a <  b) << "\n";  // true  (1<1? no, 2<3? yes)
    std::cout << (a <= b) << "\n";  // true
    std::cout << (a == Point{1,2}) << "\n"; // true
    
    Version v1{1,2,3}, v2{1,3,0};
    std::cout << (v1 < v2) << "\n";  // true (major=1, minor=2 < 3)
}
```

**三类返回类型：**
- `std::strong_ordering` — 可替换相等（如果 `a <=> b == 0` 则 `a == b` 完全等价）
- `std::weak_ordering` — 不等价但可比（如大小写不敏感字符串）
- `std::partial_ordering` — 部分可比（如浮点数 NaN）

---

## 6. 格式化库 `std::format`

C++20 终于迎来了类似 Python f-string 的类型安全格式化。

```cpp
#include <format>
#include <iostream>
#include <vector>
#include <ranges>

int main() {
    // 基本用法
    std::string s = std::format("Hello, {}! You are {} years old.", "World", 42);
    std::cout << s << "\n";  // Hello, World! You are 42 years old.
    
    // 位置参数
    std::cout << std::format("{1} + {0} = {2}", 2, 3, 5) << "\n";  // 3 + 2 = 5
    
    // 格式化说明
    std::cout << std::format("Pi = {:.4f}", 3.1415926) << "\n";     // Pi = 3.1416
    std::cout << std::format("{:+05d}", 42) << "\n";                 // +0042
    std::cout << std::format("|{:<10}|{:>10}|{:^10}|", "left", "right", "center") << "\n";
    // |left      |     right|  center  |
    
    // 二进制/十六进制
    std::cout << std::format("0x{:X} {:b}", 255, 255) << "\n";      // 0xFF 11111111
    
    // 自定义类型的格式化支持
    struct Point { int x, y; };
    template<>
    struct std::formatter<Point> {
        constexpr auto parse(auto& ctx) { return ctx.begin(); }
        auto format(const Point& p, auto& ctx) const {
            return std::format_to(ctx.out(), "({}, {})", p.x, p.y);
        }
    };
    std::cout << std::format("Point: {}", Point{3, 4}) << "\n";  // Point: (3, 4)
}
```

**优势 vs `printf`/`iostream`：**
- 类型安全（不会 `%d` 传 `double` 导致 UB）
- 性能优于 `iostream`（接近 `printf`）
- 无宏/无全局状态污染
- 编译期格式化字符串检查

---

## 7. 日历与时区 `<chrono>` 扩展

```cpp
#include <chrono>
#include <format>
#include <iostream>

namespace chr = std::chrono;

int main() {
    using namespace std::literals;
    
    // 日期字面量
    auto d1 = 2026y / std::May / 16d;
    auto d2 = chr::March/15/2026;
    
    std::cout << std::format("Date: {}\n", d1);  // 2026-05-16
    
    // 星期几
    chr::weekday wd{d1};
    std::cout << std::format("Weekday: {}\n", wd);  // Sat
    
    // 年/月/日 分解
    auto [y, m, d] = chr::year_month_day{d1};
    std::cout << std::format("Year={}, Month={}, Day={}\n", 
                              static_cast<int>(y), 
                              static_cast<unsigned>(m), 
                              static_cast<unsigned>(d));
    
    // 时间点计算
    auto now = chr::system_clock::now();
    auto today = chr::floor<chr::days>(now);
    auto days_since_epoch = chr::sys_days{today}.time_since_epoch().count();
    std::cout << "Days since epoch: " << days_since_epoch << "\n";
    
    // 时长
    auto dur = 42min + 15s;
    std::cout << std::format("Duration: {} ms\n", 
                              chr::duration_cast<chr::milliseconds>(dur));
    
    // 时区（需要 IANA 数据库）
    try {
        auto zt = chr::zoned_time{"Asia/Shanghai", now};
        std::cout << std::format("Shanghai time: {:%F %T %Z}\n", zt);
    } catch (const std::exception& e) {
        std::cout << "Timezone unavailable: " << e.what() << "\n";
    }
}
```

---

## 8. 协程基础（预览）

协程是 C++20 的重磅特性之一，但**库支持在 C++20 中最小**（`<coroutine>` 提供底层原语），**完全可用的生成器在 C++23**。这里只展示基本轮廓：

```cpp
#include <coroutine>
#include <iostream>

// 极简协程框架（生产环境用 cppcoro 或 C++23 标准生成器）
struct Generator {
    struct promise_type {
        int current_value;
        
        Generator get_return_object() {
            return Generator{
                std::coroutine_handle<promise_type>::from_promise(*this)
            };
        }
        std::suspend_always initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        std::suspend_always yield_value(int value) {
            current_value = value;
            return {};
        }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
    
    std::coroutine_handle<promise_type> handle;
    
    explicit Generator(auto h) : handle(h) {}
    ~Generator() { if (handle) handle.destroy(); }
    
    bool next() {
        handle.resume();
        return !handle.done();
    }
    int value() { return handle.promise().current_value; }
};

Generator fibonacci() {
    int a = 0, b = 1;
    while (true) {
        co_yield a;
        auto next = a + b;
        a = b;
        b = next;
    }
}

int main() {
    auto gen = fibonacci();
    for (int i = 0; i < 10; ++i) {
        gen.next();
        std::cout << gen.value() << " ";  // 0 1 1 2 3 5 8 13 21 34
    }
}
```

---

## 9. 其他重要新特性

### 9.1 `constexpr` 扩展

C++20 允许 `constexpr` 函数中包含：
- `try/catch`（但不触发异常）
- `dynamic_cast`/`typeid`
- `std::vector`/`std::string`（有限制）
- `new`/`delete`（在常量求值上下文中）

```cpp
#include <array>
#include <algorithm>

constexpr int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

constexpr std::array<int, 5> make_array() {
    std::array<int, 5> arr{};
    for (int i = 0; i < 5; ++i)
        arr[i] = factorial(i + 1);
    std::ranges::sort(arr);  // 编译期排序！
    return arr;
}

constexpr auto arr = make_array();  // 编译期计算
static_assert(arr[0] == 1);
static_assert(arr[4] == 120);
```

### 9.2 `consteval` — 立即函数

```cpp
consteval int square(int n) {
    return n * n;
}

int main() {
    constexpr int x = square(5);  // ✅ 编译期计算
    // int y = square(5);            // ✅ 也可以（consteval 保证总是编译期）
    
    int runtime = 6;
    // int z = square(runtime);     // ❌ 编译错误！运行时变量不能传给 consteval
}
```

### 9.3 `constinit` — 保证静态初始化

```cpp
#include <mutex>

constinit int global_counter = 0;           // 保证编译期初始化
constinit std::mutex mtx{};                 // 保证无动态初始化顺序问题

// constinit std::string msg = "hello";     // ❌ 编译错误：string 不是编译期可初始化
```

这解决了 C++ 中著名的"静态初始化顺序的灾难"（Static Initialization Order Fiasco）。

### 9.4 指定初始化（Designated Initializers）

C 风格指定初始化进入 C++（但更严格）：

```cpp
struct Config {
    int timeout = 30;
    int retries = 3;
    bool verbose = false;
};

Config cfg = {
    .timeout = 60,
    .verbose = true
    // .retries 保持默认值 3
};
```

**限制：**
- 必须按声明顺序（C 允许乱序）
- 不能嵌套
- 不能与普通初始化混合

### 9.5 `std::source_location`

```cpp
#include <source_location>
#include <iostream>

void log(const std::string& msg, 
         const std::source_location& loc = std::source_location::current()) {
    std::cout << std::format("[{}:{}] {}: {}", 
                              loc.file_name(), loc.line(),
                              loc.function_name(), msg) << "\n";
}

void foo() {
    log("hello");  // [main.cpp:15] foo: hello
}
```

### 9.6 `std::bit_cast` — 类型双关

安全地进行类型双关（替代 `reinterpret_cast` 和 `memcpy` 未定义行为）：

```cpp
#include <bit>
#include <iostream>

int main() {
    float f = 3.14f;
    int i = std::bit_cast<int>(f);  // 符合标准，不破坏严格别名
    std::cout << std::format("Float {} as int: 0x{:08X}\n", f, i);
    
    // 等价于但安全于：
    // int i; memcpy(&i, &f, sizeof(f));
    // int i = *reinterpret_cast<int*>(&f); // UB!
}
```

### 9.7 `std::to_array`

```cpp
#include <array>

// 从 C 数组或初始化列表创建 std::array（自动推导大小）
auto arr1 = std::to_array({1, 2, 3, 4, 5});
// std::array<int, 5>

auto arr2 = std::to_array("hello");
// std::array<char, 6>（含 null 终止符）
```

### 9.8 `std::lerp` 与 `std::midpoint`

```cpp
#include <numeric>
#include <iostream>

int main() {
    // 线性插值
    double v = std::lerp(0.0, 100.0, 0.75);  // 75.0
    
    // 安全的中点（无溢出）
    int a = std::numeric_limits<int>::max();
    int b = a - 10;
    // int mid1 = (a + b) / 2;  // ❌ 溢出！
    int mid2 = std::midpoint(a, b);  // ✅ int 的上界附近安全计算
}
```

---

## 10. 在 libkds/KVStore 中的实战建议

### 10.1 用 Concepts 增强类型安全

当前 libkds 的 `kds.h` 宏实现完全没有类型约束。C++20 wrapper 可以：

```cpp
template<typename T>
concept Hashable = requires(T v) {
    { std::hash<T>{}(v) } -> std::convertible_to<size_t>;
};

template<Hashable K, TriviallyCopyable V>
class kds_hashmap {
    // 类型安全的哈希表封装
};
```

### 10.2 用 Span 替代指针+大小

KVStore 的 `get()` 返回 `std::span<const byte>` 而不是裸指针：

```cpp
std::span<const std::byte> get(std::string_view key) const;
```

### 10.3 用 Ranges 处理批量数据

批量查询结果用 Ranges 管道处理：

```cpp
auto results = store.scan("prefix_*");
auto filtered = results 
    | std::views::filter([](auto& kv) { return kv.second.size() > 10; })
    | std::views::transform([](auto& kv) { return parse_value(kv.second); });
```

### 10.4 用 format 替代 iostream 输出

KDS 的 `kds_print` 等调试函数可以使用 `std::format` 获得更好的格式控制和性能。

---

## 总结

| 特性 | 用途 | 推荐度 |
|------|------|--------|
| Concepts | 模板约束代替 SFINAE | ⭐⭐⭐⭐⭐ |
| Modules | 替代头文件（新项目） | ⭐⭐⭐ |
| Ranges | 数据流管道式处理 | ⭐⭐⭐⭐⭐ |
| Span | 函数参数接收连续内存 | ⭐⭐⭐⭐⭐ |
| `<=>` | 自动比较运算符生成 | ⭐⭐⭐⭐ |
| `format` | 替代 printf/iostream | ⭐⭐⭐⭐⭐ |
| Chrono 扩展 | 日期/时区处理 | ⭐⭐⭐⭐ |
| `source_location` | 日志/调试 | ⭐⭐⭐ |
| `bit_cast`/`lerp`/`midpoint` | 数值安全 | ⭐⭐⭐ |
| `constexpr` 扩展 | 编译期计算 | ⭐⭐⭐⭐ |
