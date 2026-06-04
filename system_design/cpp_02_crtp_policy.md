# CRTP & Policy-Based Design

## CRTP (Curiously Recurring Template Pattern)

基类以派生类为模板参数，实现编译期多态：

```cpp
template<typename Derived>
class Base {
public:
    void interface() {
        static_cast<Derived*>(this)->implementation();
    }
};

class Derived : public Base<Derived> {
public:
    void implementation() {
        std::cout << "Derived impl\n";
    }
};

// 使用
Derived d;
d.interface();  // 调用 Derived::implementation()
```

### 静态多态 vs 虚函数

| 特性 | 虚函数（动态多态） | CRTP（静态多态） |
|------|------------------|------------------|
| 分发时机 | 运行时 | 编译时 |
| 性能 | 虚表间接调用 | 直接调用（可内联） |
| 灵活性 | 运行时多态容器 | 需要模板容器 |
| 二进制体积 | 一个虚表 | 每个派生类一个实例 |

**性能对比场景**：循环 1000 万次调用，CRTP 无虚表开销，通常比虚函数快 2-5 倍。

### Mixin 混入

通过 CRTP 组合多个行为：

```cpp
template<typename T>
struct Printable {
    void print() const {
        auto& self = static_cast<const T&>(*this);
        for (const auto& v : self) std::cout << v << ' ';
    }
};

template<typename T>
struct Serializable {
    void serialize(std::ostream& os) const {
        auto& self = static_cast<const T&>(*this);
        os << "{\"data\":[" << self << "]}";
    }
};

template<typename T>
class MyVec : public Printable<MyVec<T>>,
              public Serializable<MyVec<T>> {
    std::vector<T> data;
public:
    auto begin() const { return data.begin(); }
    auto end() const { return data.end(); }
};
```

### 对象计数器

```cpp
template<typename T>
class ObjectCounter {
    static inline size_t count_ = 0;
    static inline size_t alive_ = 0;
protected:
    ObjectCounter() { ++count_; ++alive_; }
    ~ObjectCounter() { --alive_; }
public:
    static size_t total_created() { return count_; }
    static size_t alive() { return alive_; }
};

class Widget : public ObjectCounter<Widget> { /* ... */ };
// 可独立统计每种类型的实例数
```

## Policy-Based Design

源自 Andrei Alexandrescu 的 *Modern C++ Design* (Loki 库)：
将类的行为分解为可组合的策略类。

```cpp
// 策略：线程安全
struct SingleThread {
    struct Lock { Lock(...) {} };
};

struct MultiThread {
    struct Lock {
        std::mutex mtx;
        Lock(...) { /* lock */ }
        ~Lock() { /* unlock */ }
    };
};

// 策略：存储
struct HeapStorage { /* malloc/free */ };
struct PoolStorage { /* 内存池 */ };

// 策略：序列化
struct JSONFormat;
struct BinaryFormat;

// 组合使用
template<typename T,
         template<typename> class Threading = SingleThread,
         typename Storage = HeapStorage,
         typename Format = JSONFormat>
class SmartPtr {
    // 通过策略组合不同的行为
};
```

### std::enable_shared_from_this 源码剖析

核心思路：CRTP 让类能从内部安全获得 `shared_ptr`。

```cpp
template<typename T>
class enable_shared_from_this {
    mutable weak_ptr<T> weak_this_;
protected:
    enable_shared_from_this() = default;
    
    shared_ptr<T> shared_from_this() {
        return shared_ptr<T>(weak_this_);  // weak_ptr::lock()
    }
    
    // 由 shared_ptr 构造函数调用
    void _internal_accept_owner(shared_ptr<T>* owner) const {
        if (!weak_this_.expired()) return;
        weak_this_ = *owner;  // 存储弱引用
    }
};
```

⚠️ 陷阱：在构造函数中调用 `shared_from_this()` 会导致未定义行为，因为此时 `shared_ptr` 尚未构造完成，`weak_this_` 为空。
