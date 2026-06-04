# C++20 模板元编程与 Concepts 深度解析

> 现代 C++ 模板技术：从传统元编程到 Concept 约束、折叠表达式、CRTP、Variadic Templates

---

## 1. Concepts 约束系统（C++20 核心改进）

Concepts 将模板约束从晦涩的 SFINAE 提升为声明式、可复用的类型谓词。

### 1.1 Concept 的四种用法

```cpp
#include <concepts>
#include <type_traits>
#include <iostream>
#include <vector>

// 1) 作为函数模板的模板参数约束
template<std::integral T>
T double_it(T value) { return value * 2; }

// 2) 简写形式（auto 参数）
void print(std::integral auto value) {
    std::cout << value << " is integral\n";
}

// 3) requires 子句
template<typename T>
    requires std::is_arithmetic_v<T>
T add(T a, T b) {
    return a + b;
}

// 4) 缩写 trailing requires
template<typename T>
T multiply(T a, T b)
    requires std::is_arithmetic_v<T>
{
    return a * b;
}

int main() {
    std::cout << double_it(42) << "\n";    // 84
    print(123);                              // 123 is integral
    // print("hello"); // ❌ string 不是 integral
    
    std::cout << add(3.14, 2.86) << "\n";   // 6.0
    // add(std::vector{1,2}, std::vector{3}); // ❌ vector 不是 arithmetic
}
```

### 1.2 定义自定义 Concept

```cpp
#include <concepts>
#include <ranges>
#include <iterator>
#include <vector>

// 简单的类型特性 Concept
template<typename T>
concept Numeric = std::is_arithmetic_v<T> && !std::is_same_v<T, bool>;

// requires 表达式 — 检查语法约束
template<typename T>
concept Incrementable = requires(T x) {
    ++x;           // 支持前置++
    x++;           // 支持后置++
    { x++ } -> std::same_as<T>; // 后置++返回类型为 T
};

// 复合 requires — 检查表达式类型
template<typename T>
concept Hashable = requires(T value) {
    { std::hash<T>{}(value) } -> std::convertible_to<std::size_t>;
};

// 嵌套 requires
template<typename T>
concept SortableContainer = requires(T& c) {
    requires std::ranges::range<T>;      // 是 range
    std::ranges::sort(c);                // 可排序
};

template<typename T>
concept Printable = requires(T value, std::ostream& os) {
    os << value;  // 支持 operator<<
};

// 组合 Concept
template<typename T>
concept PrintableNumeric = Numeric<T> && Printable<T>;

// 验证
static_assert(Numeric<int>);
static_assert(!Numeric<bool>);  // bool 被排除
static_assert(!Numeric<std::string>);

template<Hashable T>
void store_in_unordered_map(T key) {
    std::cout << "Type " << typeid(T).name() << " is hashable\n";
}

int main() {
    store_in_unordered_map(42);     // ✅ int is hashable
    store_in_unordered_map("hello"s); // ✅ string is hashable
    // store_in_unordered_map(std::vector<int>{}); // ❌ vector is not hashable
}
```

### 1.3 Concept 与函数重载

```cpp
template<typename T>
concept Integral = std::is_integral_v<T>;

template<typename T>
concept Floating = std::is_floating_point_v<T>;

// 重载：不同 Concept 自动选择最佳匹配
std::string process(Integral auto value) {
    return std::format("Integral: {}", value);
}

std::string process(Floating auto value) {
    return std::format("Floating: {:.3f}", value);
}

std::string process(auto value) {
    return std::format("Other: {}", value);
}

int main() {
    std::cout << process(42) << "\n";     // Integral: 42
    std::cout << process(3.14) << "\n";   // Floating: 3.140
    std::cout << process("hello") << "\n";// Other: hello
}
```

### 1.4 Concept 替代 SFINAE

**旧方式（C++17 SFINAE）：**

```cpp
template<typename T, 
         std::enable_if_t<std::is_integral_v<T>, int> = 0>
T old_sfinae(T value) { return value; }
```

**新方式（C++20 Concept）：**

```cpp
std::integral auto new_concept(std::integral auto value) { 
    return value; 
}
```

可读性提升是量级级别的。

---

## 2. Variadic Templates 与折叠表达式

### 2.1 参数包基础

```cpp
#include <iostream>

// 基本递归展开
void print_all() {}  // 终止递归

template<typename T, typename... Args>
void print_all(T first, Args... rest) {
    std::cout << first << " ";
    print_all(rest...);
}

// C++17 折叠表达式 — 更简洁
template<typename... Args>
void print_all_fold(Args... args) {
    // 一元右折叠：从左到右逐个调用运算符
    // (std::cout << ... << args) 等价于 (((std::cout << arg1) << arg2) << ...)
    (std::cout << ... << args) << "\n";
}

template<typename... Args>
void print_spaced(Args... args) {
    // 逗号折叠 + 初始化列表保证求值顺序
    ((std::cout << args << " "), ...);
    std::cout << "\n";
}

int main() {
    print_all(1, 2.5, "hello", 'x');      // 1 2.5 hello x
    print_spaced(1, 2.5, "hello", 'x');   // 1 2.5 hello x
    print_all_fold(1, 2.5, "hello", 'x'); // 12.5hellox（无空格）
}
```

### 2.2 四种折叠模式

```cpp
#include <iostream>

// 1) 一元右折叠：(... op args) → (arg1 op (arg2 op (arg3 op ...)))
template<typename... Args>
auto sum_right(Args... args) {
    return (... + args);  // (arg1 + (arg2 + (arg3 + ...)))
}

// 2) 一元左折叠：(args op ...) → (((arg1 op arg2) op arg3) op ...)
template<typename... Args>
auto sum_left(Args... args) {
    return (args + ...);  // (((arg1 + arg2) + arg3) + ...)
}

// 注意：对于 +，左右折叠结果相同。但 - 不同：
// sum_right(1,2,3) = 1 - (2 - 3) = 2
// sum_left(1,2,3)  = (1 - 2) - 3 = -4

// 3) 二元右折叠：(init op ... op args)
template<typename... Args>
auto sum_with_init(Args... args) {
    return (0 + ... + args);  // 0 作为初始值，折叠为 (0 + (1 + (2 + 3)))
}

// 4) 二元左折叠：(args op ... op init)
template<typename... Args>
auto sum_with_init_left(Args... args) {
    return (args + ... + 0);  // (((1 + 2) + 3) + 0)
}
```

### 2.3 实用折叠模式

```cpp
#include <iostream>
#include <vector>
#include <concepts>

// 检查所有参数是否都满足某个谓词
template<typename Predicate, typename... Args>
    requires (std::predicate<Predicate, Args> && ...)
bool all_of(Predicate pred, Args... args) {
    return (pred(args) && ...);
}

// 是否至少有一个参数满足
template<typename Predicate, typename... Args>
bool any_of(Predicate pred, Args... args) {
    return (pred(args) || ...);
}

// 多参数 push_back
template<typename Container, typename... Args>
void push_all(Container& c, Args&&... args) {
    (c.push_back(std::forward<Args>(args)), ...);
}

// 多参数 emplace
template<typename Container, typename... Args>
void emplace_all(Container& c, Args&&... args) {
    (c.emplace_back(std::forward<Args>(args)), ...);
}

int main() {
    std::cout << std::boolalpha;
    
    std::cout << all_of([](auto x) { return x > 0; }, 1, 2, 3, 4) << "\n";  // true
    std::cout << all_of([](auto x) { return x > 0; }, 1, -2, 3) << "\n";    // false
    std::cout << any_of([](auto x) { return x < 0; }, 1, -2, 3) << "\n";    // true
    
    std::vector<int> v;
    push_all(v, 1, 2, 3, 4, 5);
    std::cout << "size: " << v.size() << "\n";  // 5
}
```

---

## 3. CRTP (Curiously Recurring Template Pattern)

CRTP 是一种静态多态技术——派生类将自身作为模板参数传给基类，实现编译期虚函数。

### 3.1 基本 CRTP

```cpp
#include <iostream>

// 基类模板
template<typename Derived>
class Base {
public:
    void interface() {
        // 编译期虚调用
        static_cast<Derived*>(this)->impl();
    }
    
    // 提供默认实现
    void impl() {
        std::cout << "Base::impl (default)\n";
    }
};

class DerivedA : public Base<DerivedA> {
public:
    void impl() {
        std::cout << "DerivedA::impl\n";
    }
};

class DerivedB : public Base<DerivedB> {
public:
    void impl() {
        std::cout << "DerivedB::impl\n";
    }
};

template<typename T>
void call_interface(Base<T>& b) {
    b.interface();  // 编译期解析到正确的 impl
}

int main() {
    DerivedA a;
    DerivedB b;
    
    call_interface(a);  // DerivedA::impl
    call_interface(b);  // DerivedB::impl
    
    // 零虚函数开销！没有 vtable，没有间接调用
}
```

### 3.2 混合类（Mixins）与 CRTP

```cpp
#include <iostream>
#include <string>

// 启用比较操作的 Mixin
template<typename Derived>
struct Comparable {
    friend bool operator!=(const Derived& a, const Derived& b) {
        return !(a == b);
    }
};

// 启用打印的 Mixin
template<typename Derived>
struct Printable {
    void print() const {
        static_cast<const Derived*>(this)->print_impl(std::cout);
    }
};

// 组合使用
class Point : public Comparable<Point>, public Printable<Point> {
    int x_, y_;
public:
    Point(int x, int y) : x_(x), y_(y) {}
    
    bool operator==(const Point& other) const {
        return x_ == other.x_ && y_ == other.y_;
    }
    
    void print_impl(std::ostream& os) const {
        os << "Point(" << x_ << ", " << y_ << ")";
    }
};

int main() {
    Point p1(1, 2), p2(1, 3);
    std::cout << std::boolalpha;
    std::cout << (p1 != p2) << "\n";  // true（来自 Comparable Mixin）
    p1.print();  // Point(1, 2)（来自 Printable Mixin）
}
```

### 3.3 CRTP 实现对象计数

```cpp
#include <iostream>

template<typename T>
struct ObjectCounter {
    static inline int objects_created = 0;
    static inline int objects_alive = 0;
    
    ObjectCounter() { 
        ++objects_created; 
        ++objects_alive; 
    }
    
    ~ObjectCounter() { 
        --objects_alive; 
    }
    
    static int created() { return objects_created; }
    static int alive()   { return objects_alive; }
};

class Widget : public ObjectCounter<Widget> {
    int id_;
public:
    Widget(int id) : id_(id) {}
    ~Widget() = default;
};

class Gadget : public ObjectCounter<Gadget> {
    std::string name_;
public:
    Gadget(std::string name) : name_(name) {}
    ~Gadget() = default;
};

int main() {
    Widget w1(1), w2(2);
    {
        Widget w3(3);
        std::cout << "Widget alive: " << Widget::alive() << "\n";  // 3
    }
    std::cout << "Widget alive: " << Widget::alive() << "\n";    // 2
    std::cout << "Widget created: " << Widget::created() << "\n"; // 3
    
    Gadget g("test");
    std::cout << "Gadget created: " << Gadget::created() << "\n"; // 1
    std::cout << "Widget created: " << Widget::created() << "\n"; // 3（独立计数）
}
```

### 3.4 应用于 libkds：类型安全容器

```cpp
#include <vector>
#include <algorithm>

template<typename Derived, typename T>
struct ContiguousContainer {
    T* data() {
        return static_cast<Derived*>(this)->data_impl();
    }
    
    size_t size() {
        return static_cast<Derived*>(this)->size_impl();
    }
    
    // 通用算法（一次实现，所有派生类复用）
    void sort() {
        std::sort(data(), data() + size());
    }
    
    T& operator[](size_t i) {
        return data()[i];
    }
};

// 栈数组容器
template<typename T, size_t N>
class StackArray : public ContiguousContainer<StackArray<T, N>, T> {
    T data_[N] = {};
    friend class ContiguousContainer<StackArray<T, N>, T>;
    T* data_impl() { return data_; }
    size_t size_impl() { return N; }
};

// 堆容器
template<typename T>
class HeapArray : public ContiguousContainer<HeapArray<T>, T> {
    std::vector<T> vec_;
    friend class ContiguousContainer<HeapArray<T>, T>;
    T* data_impl() { return vec_.data(); }
    size_t size_impl() { return vec_.size(); }
public:
    void push_back(T value) { vec_.push_back(value); }
};
```

---

## 4. 类型萃取与编译期编程

### 4.1 C++11~20 的类型萃取

```cpp
#include <type_traits>
#include <iostream>

template<typename T>
struct TypeInfo {
    static void print() {
        std::cout << "Type: " << typeid(T).name() << "\n";
        std::cout << "  is_void: "       << std::is_void_v<T> << "\n";
        std::cout << "  is_integral: "    << std::is_integral_v<T> << "\n";
        std::cout << "  is_floating: "    << std::is_floating_point_v<T> << "\n";
        std::cout << "  is_pointer: "     << std::is_pointer_v<T> << "\n";
        std::cout << "  is_const: "       << std::is_const_v<T> << "\n";
        std::cout << "  is_reference: "   << std::is_reference_v<T> << "\n";
        std::cout << "  is_trivially_copyable: " 
                  << std::is_trivially_copyable_v<T> << "\n";
        std::cout << "  size: "           << sizeof(T) << "\n";
    }
};

// 条件类型选择
template<bool Cond, typename T, typename F>
struct conditional { using type = T; };

template<typename T, typename F>
struct conditional<false, T, F> { using type = F; };

// 或者直接用 std::conditional
template<typename T>
using CString = std::conditional_t<std::is_same_v<T, char>, 
                                    const char*, 
                                    const wchar_t*>;

int main() {
    TypeInfo<int>::print();
    TypeInfo<const double&>::print();
    
    // type_traits 实战：安全转换
    auto result = static_cast<CString<char>>("hello");
    std::cout << result << "\n";
}
```

### 4.2 SFINAE 与 enable_if

虽然 Concepts 已取代大部分 SFINAE 用途，理解其原理对阅读旧代码和复杂场景仍然重要。

```cpp
#include <type_traits>
#include <iostream>
#include <vector>

// SFINAE：模板替换失败不是错误
// 当模板参数推导失败时，编译器不报错，而是从重载集中移除该候选

// C++17 之前的典型用法
template<typename T>
auto size_in_bytes(const T& container)
    -> decltype(container.size(), container.data(), void(), sizeof(typename T::value_type) * container.size())
{
    return sizeof(typename T::value_type) * container.size();
}

// 对于没有 .size()/.data() 的类型，这个重载会被静默移除

// enable_if 替代方案
template<typename T>
std::enable_if_t<std::is_integral_v<T>, T>
twice(T value) {
    return value * 2;
}

// C++20 Concept 替代
template<std::integral T>
T twice_concept(T value) {
    return value * 2;
}
```

### 4.3 constexpr if (C++17)

```cpp
#include <type_traits>
#include <iostream>

template<typename T>
auto process(T value) {
    // 编译期分支，不会生成未使用分支的代码
    if constexpr (std::is_integral_v<T>) {
        return value * 2;
    } else if constexpr (std::is_floating_point_v<T>) {
        return value / 2.0;
    } else if constexpr (std::is_same_v<T, std::string>) {
        return value + value;
    } else {
        static_assert(false, "Unsupported type");
    }
}

template<typename T>
void serialize(T& obj) {
    if constexpr (std::is_trivially_copyable_v<T>) {
        // 平凡类型可直接 memcpy
        std::cout << "Fast path: memcpy serialization\n";
    } else {
        // 复杂类型需要逐字段序列化
        std::cout << "Slow path: field-by-field\n";
    }
}

struct Trivial { int x, y; };
struct Complex { 
    std::string name;
    std::vector<int> data; 
};

int main() {
    std::cout << process(42) << "\n";       // 84
    std::cout << process(3.14) << "\n";     // 1.57
    
    Trivial t{1, 2};
    serialize(t);  // Fast path
    
    Complex c{"hello", {1,2,3}};
    serialize(c);  // Slow path
}
```

---

## 5. 实战：编译期分发与策略

### 5.1 编译期策略模式

```cpp
#include <iostream>
#include <concepts>

// 策略概念
template<typename T>
concept CompressionStrategy = requires(T t, const char* data, size_t len, std::vector<char>& out) {
    { t.compress(data, len, out) } -> std::same_as<void>;
    { t.decompress(data, len, out) } -> std::same_as<void>;
};

struct NoCompression {
    void compress(const char* data, size_t len, std::vector<char>& out) {
        out.assign(data, data + len);
    }
    void decompress(const char* data, size_t len, std::vector<char>& out) {
        out.assign(data, data + len);
    }
};

struct RunLengthEncoding {
    void compress(const char* data, size_t len, std::vector<char>& out);
    void decompress(const char* data, size_t len, std::vector<char>& out);
};

// 编译期策略绑定
template<CompressionStrategy Strategy>
class Storage {
    Strategy strategy_;
public:
    void store(const char* data, size_t len) {
        std::vector<char> compressed;
        strategy_.compress(data, len, compressed);
        // 写入存储...
    }
    
    void retrieve(std::vector<char>& out) {
        std::vector<char> raw;
        strategy_.decompress(nullptr, 0, out);
    }
};

// 使用
Storage<NoCompression> fast_store;
// Storage<RunLengthEncoding> compact_store;
```

### 5.2 编译期注册表

```cpp
#include <tuple>
#include <iostream>
#include <string_view>

// 编译期工厂注册表（不需要运行时初始化）
template<typename... Strategies>
struct StrategyRegistry {
    std::tuple<Strategies...> strategies;
    
    template<typename F>
    void for_each(F&& func) {
        std::apply([&](auto&... strat) {
            (func(strat), ...);
        }, strategies);
    }
    
    template<typename T>
    auto& get() {
        return std::get<T>(strategies);
    }
};

struct FastAlgo { 
    void run() { std::cout << "Fast\n"; } 
};
struct SafeAlgo { 
    void run() { std::cout << "Safe\n"; } 
};
struct BalancedAlgo { 
    void run() { std::cout << "Balanced\n"; } 
};

int main() {
    StrategyRegistry<FastAlgo, SafeAlgo, BalancedAlgo> registry;
    
    registry.for_each([](auto& algo) {
        algo.run();
    });
    // Fast
    // Safe
    // Balanced
    
    registry.get<FastAlgo>().run();  // Fast
}
```

---

## 6. C++20 模板元编程的新工具

### 6.1 模板 lambda（C++20）

```cpp
#include <iostream>
#include <vector>
#include <concepts>

// 模板 lambda：lambda 参数可以为 auto（已经是模板）
// 但 C++20 允许在需要的地方显式写模板参数

int main() {
    // 多态 lambda（一直是模板）
    auto add = [](auto a, auto b) { return a + b; };
    std::cout << add(1, 2) << "\n";     // 3
    std::cout << add(1.5, 2.5) << "\n"; // 4.0
    std::cout << add(std::string("a"), std::string("b")) << "\n"; // ab
    
    // 概念约束的 lambda（C++20）
    auto integral_square = [](std::integral auto n) {
        return n * n;
    };
    std::cout << integral_square(5) << "\n";  // 25
    // integral_square(3.14); // ❌ double 不是 integral
    
    // 编译期 lambda
    constexpr auto compile_check = []<typename T>(T value) {
        if constexpr (std::is_integral_v<T>) {
            return value * 2;
        } else {
            return value;
        }
    };
    static_assert(compile_check(21) == 42);
    
    // lambda 作为元函数
    constexpr auto is_integral = []<typename T>(T) {
        return std::is_integral_v<T>;
    };
    static_assert(is_integral(42));
    static_assert(!is_integral(3.14));
}
```

### 6.2 应用于 libkds：类型安全的 C++ wrapper

```cpp
#include <concepts>
#include <span>
#include <vector>
#include <functional>

// 将 libkds 的 C 动态数组用 C++ 封装

template<typename T>
concept KDSType = std::is_trivially_copyable_v<T> && !std::is_pointer_v<T>;

template<KDSType T>
class KDSDynamicArray {
    // 实际存储使用 C 结构体
    struct kds_darr* darr_;
public:
    explicit KDSDynamicArray(size_t initial_cap = 16);
    ~KDSDynamicArray();
    
    void push_back(const T& value);
    void pop_back();
    
    T& operator[](size_t index);
    const T& operator[](size_t index) const;
    
    size_t size() const;
    bool empty() const;
    
    // 迭代器支持
    T* begin() { return data(); }
    T* end()   { return data() + size(); }
    const T* begin() const { return data(); }
    const T* end()   const { return data() + size(); }
    
    // 视图
    std::span<T> view() { return {data(), size()}; }
    
private:
    T* data();
    
    // C 函数的函数指针封装
    using resize_fn = int(*)(struct kds_darr**, size_t);
    resize_fn kds_resize;
};
```

---

## 7. 性能注意事项

### 7.1 模板实例化膨胀

```cpp
// ❌ 不良实践：每个类型都实例化完整函数
template<typename T>
void sort_bad(T* data, size_t n) {
    // 完整排序实现
    for (size_t i = 0; i < n; ++i)
        for (size_t j = i + 1; j < n; ++j)
            if (data[j] < data[i])
                std::swap(data[i], data[j]);
}
// int* 和 double* 生成两份完全相同的代码

// ✅ 良好实践：非模板外层 + 比较器模板化
void sort_good(void* data, size_t n, size_t elem_size, 
               bool(*cmp)(const void*, const void*));
```

### 7.2 编译时间优化

```cpp
// ❌ 重模板导致长编译
template<typename T>
struct DeepNesting {
    using type = typename DeepNesting<typename std::conditional<
        std::is_same_v<T, int>, float, 
        typename std::conditional<std::is_same_v<T, float>, double, T>::type
    >::type>::type;
};

// ✅ 用 if constexpr 减少实例化深度
template<typename T>
struct DeepNestingV2 {
    using type = T;
};

template<>
struct DeepNestingV2<int> { using type = float; };

template<>
struct DeepNestingV2<float> { using type = double; };
```

### 7.3 模板与虚函数的选择

| 场景 | 选择 | 原因 |
|------|------|------|
| 类型固定，编译期已知 | 模板 | 零开销抽象，inline |
| 类型运行时确定 | 虚函数 | 运行时多态 |
| 容器/算法 | 模板 | STL 就是例子 |
| 插件/动态加载 | 虚函数 | 享元模式 |
| 极端性能要求 | 模板 + CRTP | 编译期静态分发 |

---

## 总结

| 技术 | 能力 | C++ 版本 | 推荐度 |
|------|------|----------|--------|
| Concepts | 声明式类型约束 | C++20 | ⭐⭐⭐⭐⭐ |
| 折叠表达式 | 参数包化简 | C++17 | ⭐⭐⭐⭐⭐ |
| CRTP | 编译期多态 | C++98+ | ⭐⭐⭐⭐ |
| constexpr if | 编译期分支 | C++17 | ⭐⭐⭐⭐⭐ |
| Variadic Templates | 变长参数 | C++11 | ⭐⭐⭐⭐⭐ |
| 类型萃取 | 编译期类型查询 | C++11+ | ⭐⭐⭐⭐ |
| Template Lambda | 多态 lambda | C++20 | ⭐⭐⭐ |
| SFINAE | 模板约束（旧方式） | C++98+ | ❌ 用 Concepts 替代 |
