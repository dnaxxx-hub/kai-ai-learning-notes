# 模板元编程 (Template Metaprogramming)

## 函数模板 & 类模板

**函数模板** — 编译器根据调用参数推导具体类型：

```cpp
template<typename T>
T max(T a, T b) { return a > b ? a : b; }

max(3, 5);       // T=int
max(3.0, 5.0);   // T=double
max<int>(3, 5);  // 显式指定
```

**类模板** — 类型参数化为类：

```cpp
template<typename T>
class Box {
    T value;
public:
    explicit Box(T v) : value(v) {}
    T get() const { return value; }
};

Box<int> b(42);
```

## 特化 (Specialization) & 偏特化 (Partial Specialization)

**全特化** — 对特定类型手写特殊实现：

```cpp
template<>
class Box<bool> {
    // 对 bool 的优化实现
};
```

**偏特化** — 对部分模板参数特化（仅类模板支持）：

```cpp
template<typename T>
class Box<T*> {       // 对指针类型的特化
    T* ptr;
    // 专门处理指针
};

template<typename T, typename U>
struct Pair {};

template<typename T>        // 偏特化：U 固定为 T
struct Pair<T, T> {};
```

## SFINAE (Substitution Failure Is Not An Error)

替换失败不是错误——匹配失败只是从重载集合中移除，不导致编译失败。

**std::enable_if** — 条件性启用/禁用重载：

```cpp
template<typename T>
typename std::enable_if<std::is_integral<T>::value, bool>::type
is_even(T n) { return n % 2 == 0; }

template<typename T>
typename std::enable_if<std::is_floating_point<T>::value, bool>::type
is_even(T n) { return std::fmod(n, 2) == 0; }
```

**void_t** (C++17) — 检测特定表达式是否合法：

```cpp
template<typename, typename = void>
struct has_value_type : std::false_type {};

template<typename T>
struct has_value_type<T, std::void_t<typename T::value_type>> 
    : std::true_type {};
```

## constexpr if (C++17)

编译期分支，未选中分支不实例化：

```cpp
template<typename T>
auto get_value(T t) {
    if constexpr (std::is_pointer_v<T>)
        return *t;        // T 为指针时编译
    else
        return t;         // T 为非指针时编译
}
```

对比运行时 `if`：`if constexpr` 在编译期求值，未选分支的代码不会被编译。

## Type Traits

编译期类型查询与转换：

```cpp
#include <type_traits>

// 查询
static_assert(std::is_same_v<int, int>);           // true
static_assert(std::is_pointer_v<int*>);            // true
static_assert(std::is_integral_v<int>);            // true

// 转换
using T = std::remove_reference_t<int&>;            // int
using T2 = std::remove_const_t<const int>;           // int
using T3 = std::decay_t<const int&>;                 // int（去掉 cv 和引用）
```

`decay` = `remove_cv` + `remove_reference` + 数组/函数转指针。

## 变参模板 (Variadic Templates)

**Pack Expansion** — `...` 展开参数包：

```cpp
template<typename... Args>
void print(Args... args) {
    (std::cout << ... << args) << '\n';  // 一元左折叠
}

template<typename... Args>
auto sum(Args... args) {
    return (args + ...);                  // 二元左折叠
}
```

**Fold Expression** (C++17) — 四种折叠：

| 语法 | 含义 |
|------|------|
| `(op ...)` | 一元右折叠 |
| `(... op)` | 一元左折叠 |
| `(init op ...)` | 二元右折叠 |
| `(... op init)` | 二元左折叠 |

**递归展开** (C++11/14 方式)：

```cpp
void print() {}  // 终止条件

template<typename T, typename... Args>
void print(T first, Args... rest) {
    std::cout << first << ' ';
    print(rest...);  // 递归调用
}
```

## 编译期计算

**编译期斐波那契**：

```cpp
template<size_t N>
struct Fib : std::integral_constant<size_t, Fib<N-1>::value + Fib<N-2>::value> {};

template<>
struct Fib<0> : std::integral_constant<size_t, 0> {};

template<>
struct Fib<1> : std::integral_constant<size_t, 1> {};

// C++14 constexpr 版本（更优雅）
constexpr size_t fib(size_t n) {
    if (n <= 1) return n;
    return fib(n-1) + fib(n-2);
}
```

**编译期平方根** (牛顿迭代法)：

```cpp
template<double N, double Low, double High>
struct SqrtImpl {
    static constexpr double Mid = (Low + High) / 2;
    static constexpr double value = 
        (Mid * Mid > N) ? 
        SqrtImpl<N, Low, Mid>::value : 
        SqrtImpl<N, Mid, High>::value;
};

template<double N, double Low>
struct SqrtImpl<N, Low, Low> {
    static constexpr double value = Low;
};

template<double N>
struct Sqrt : SqrtImpl<N, 0, N> {};
```

**C++17 constexpr 版本 sqrtsqrt**：

```cpp
constexpr double sqrt_cp(double n, double low, double high) {
    auto mid = (low + high) / 2;
    if constexpr (high - low < 1e-10) return mid;
    if (mid * mid > n) return sqrt_cp(n, low, mid);
    else return sqrt_cp(n, mid, high);
}
```
