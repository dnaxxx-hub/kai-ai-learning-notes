# RAII 高级 & 智能指针

## RAII vs GC

| 特性 | RAII (C++) | GC (Java/Go) |
|------|-----------|--------------|
| 释放时机 | 确定（作用域结束） | 不确定（GC 周期） |
| 性能开销 | 零（栈对象） | 停顿 + 标记 |
| 资源类型 | 内存/锁/文件/网络 | 内存为主 |
| 异常安全 | 天然支持（栈展开） | 需 finally |
| 控制权 | 程序员控制 | 运行时决定 |

C++ 的核心哲学：资源获取即初始化，析构函数确保释放。

## unique_ptr

独占所有权，不可复制，可移动。

```cpp
// 基础使用
auto ptr = std::make_unique<int>(42);
// auto ptr2 = ptr;            // ❌ 禁止拷贝
auto ptr3 = std::move(ptr);    // ✅ 移动语义

// 自定义删除器
auto file_deleter = [](FILE* f) { if (f) fclose(f); };
std::unique_ptr<FILE, decltype(file_deleter)> file(
    fopen("test.txt", "r"), file_deleter);

// 数组特化
auto arr = std::make_unique<int[]>(100);
arr[0] = 42;  // unique_ptr<T[]> 重载了 operator[]

// 工厂模式
template<typename T, typename... Args>
std::unique_ptr<T> make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}
```

## shared_ptr

引用计数共享所有权。

```cpp
auto p1 = std::make_shared<int>(42);
auto p2 = p1;  // 引用计数 +1

// 控制块结构
// [int_data] [control_block]
// control_block 包含：引用计数、弱引用计数、删除器、分配器
```

### make_shared vs new

```cpp
// make_shared: 一次分配（控制块 + 对象连续）
auto p = std::make_shared<int>(42);

// new: 两次分配（对象 + 控制块分离）
std::shared_ptr<int> p2(new int(42));
```

| | make_shared | new |
|--|-----------|-----|
| 内存分配 | 1 次（合并） | 2 次 |
| 异常安全 | ✅ | ⚠️ 裸指针可能泄露 |
| 自定义删除器 | ❌ | ✅ |
| 弱引用存活 | 对象内存释放延迟 | 独立控制块 |

### weak_ptr & 循环引用

```cpp
struct Node {
    std::shared_ptr<Node> next;  // ❌ 循环引用
    // std::weak_ptr<Node> next; // ✅ 打破循环
    ~Node() { std::cout << "dtor\n"; }
};

// 形成环：两个 Node 都不会析构
auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;
b->next = a;  // a 和 b 泄露！

// weak_ptr 介入: lock() 返回 shared_ptr 或空
auto sp = weak.lock();
if (sp) { /* safely use */ }
```

## scope_guard 实现

```cpp
class scope_guard {
    std::function<void()> cleanup_;
public:
    explicit scope_guard(std::function<void()> f) : cleanup_(f) {}
    ~scope_guard() { if (cleanup_) cleanup_(); }
    void dismiss() { cleanup_ = nullptr; }
};

// 使用
{
    auto guard = scope_guard([&] { release_resource(); });
    // ... 可能抛出异常
    guard.dismiss();  // 正常结束则抑制
}
```

## copy-and-swap 惯用法

统一的异常安全赋值操作符：

```cpp
class String {
    char* data_;
    size_t size_;
    
    void swap(String& other) noexcept {
        using std::swap;
        swap(data_, other.data_);
        swap(size_, other.size_);
    }
public:
    // 拷贝赋值 = 传值 + swap（异常安全！）
    String& operator=(String other) noexcept {
        swap(other);
        return *this;
    }
    
    // 传值形参自动处理：左值拷贝，右值移动
};
```

**核心思想**：值语义参数接收副本 → swap 入局 → 原对象自动析构。天然同时支持拷贝和移动赋值。
