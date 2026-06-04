# 现代 C++ 设计模式

## Type Erasure (类型擦除)

把不同类型的对象通过统一接口管理，消除具体类型依赖。

**std::function** 实现原理：

```cpp
// 简化版 std::function
class function_base {
    struct concept_t {
        virtual ~concept_t() = default;
        virtual concept_t* clone() const = 0;
    };
    template<typename F>
    struct model_t : concept_t {
        F f;
        model_t(F&& func) : f(std::forward<F>(func)) {}
        concept_t* clone() const override { return new model_t(*this); }
    };
    concept_t* storage_;
public:
    template<typename F>
    function_base(F&& f) : storage_(new model_t<F>(std::forward<F>(f))) {}
    ~function_base() { delete storage_; }
};
```

**std::any** — 类似 void* 但类型安全：

```cpp
std::any a = 42;
std::any b = std::string("hello");
int val = std::any_cast<int>(a);  // 抛出 bad_any_cast 如果类型不匹配
```

实际实现使用 "small buffer optimization"（小对象避免堆分配）+ 虚函数擦除。

## 工厂模式 (Factory)

```cpp
// 抽象产品
struct Shape { virtual void draw() = 0; virtual ~Shape() = default; };
struct Circle : Shape { void draw() override { /* ... */ } };
struct Square : Shape { void draw() override { /* ... */ } };

// 工厂
struct ShapeFactory {
    using Creator = std::unique_ptr<Shape>(*)();
    static std::unordered_map<std::string, Creator> registry;
    
    static std::unique_ptr<Shape> create(std::string_view type) {
        return registry.at(std::string(type))();
    }
};
```

## Observer (信号-槽)

```cpp
template<typename... Args>
class Signal {
    std::vector<std::function<void(Args...)>> slots_;
public:
    void connect(std::function<void(Args...)> slot) {
        slots_.push_back(std::move(slot));
    }
    
    void emit(Args... args) {
        for (auto& slot : slots_) 
            slot(args...);
    }
};

// 使用
Signal<int> sig;
sig.connect([](int x) { std::cout << x << '\n'; });
sig.emit(42);
```

## CRTP Singleton (线程安全 + DCLP)

```cpp
template<typename T>
class Singleton {
protected:
    Singleton() = default;
    ~Singleton() = default;
public:
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
    
    static T& instance() {
        static T inst;  // C++11 起：静态局部变量初始化是线程安全的
        return inst;
    }
};

class Logger : public Singleton<Logger> {
    friend class Singleton<Logger>;  // 允许基类调用私有构造
    // ... 
};
```

**DCLP (Double-Checked Lock Pattern)** — C++11 之前的手动实现，现在被线程安全的静态局部变量取代。

## Builder (流式接口)

```cpp
class SQLQuery {
    std::string select_, from_, where_;
public:
    SQLQuery& Select(std::string_view s) { select_ = s; return *this; }
    SQLQuery& From(std::string_view f)   { from_ = f;  return *this; }
    SQLQuery& Where(std::string_view w)  { where_ = w; return *this; }
    std::string build() const {
        return "SELECT " + select_ + " FROM " + from_ 
               + (where_.empty() ? "" : " WHERE " + where_);
    }
};

// 使用
auto query = SQLQuery()
    .Select("name, age")
    .From("users")
    .Where("age > 18")
    .build();
```

## Proxy (代理模式 via 智能指针)

智能指针本身就是 Proxy 模式：通过 `operator*` 和 `operator->` 透明代理底层对象。

```cpp
template<typename T>
class LoggingProxy {
    std::unique_ptr<T> target_;
public:
    LoggingProxy() : target_(std::make_unique<T>()) {}
    T* operator->() {
        std::cout << "accessing " << typeid(T).name() << '\n';
        return target_.get();
    }
};
```

## Visitor (std::variant + std::visit)

```cpp
using Shape = std::variant<Circle, Square, Triangle>;

struct AreaVisitor {
    double operator()(const Circle& c)   { return π * c.r * c.r; }
    double operator()(const Square& s)   { return s.a * s.a; }
    double operator()(const Triangle& t) { return 0.5 * t.b * t.h; }
};

// 使用
Shape s = Circle{10};
double area = std::visit(AreaVisitor{}, s);
// 或 lambda 重载
auto area2 = std::visit([](auto& shape) { return shape.area(); }, s);
```

`std::variant` 是类型安全的 union，`std::visit` 对其做编译期 dispatch，不需虚函数表。
