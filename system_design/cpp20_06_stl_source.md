# STL 源码分析：核心容器的实现与性能

> 理解 STL 背后是如何工作的——从 vector 的动态数组到 map 的红黑树

---

## 1. `std::vector` — 动态数组深度解剖

### 1.1 内存布局

```
堆内存：[   |   |   |   |   |   |   |   ]
        ^                   ^           ^
      begin()             end()       end_of_storage()
```

vector 用三个指针管理内存：
- `begin` — 起始地址
- `end` — 最后一个元素的下一个位置
- `end_of_storage` — 分配内存的末尾

相当于 `T* start_, *finish_, *end_of_storage_`。

### 1.2 扩容策略

```cpp
#include <vector>
#include <iostream>

// 不同编译器实现不同的扩容因子
void growth_factor_demo() {
    std::vector<int> v;
    size_t prev_cap = 0;
    
    for (int i = 0; i < 100; ++i) {
        v.push_back(i);
        if (v.capacity() != prev_cap) {
            std::cout << "Size: " << v.size() 
                      << ", Cap: " << v.capacity()
                      << ", Growth: " 
                      << (prev_cap ? (double)v.capacity()/prev_cap : 0)
                      << "x\n";
            prev_cap = v.capacity();
        }
    }
}
/*
典型输出（GCC/MSVC）：
Size: 1, Cap: 1
Size: 2, Cap: 2, Growth: 2.0x
Size: 3, Cap: 4, Growth: 2.0x  ← GCC/MSVC 用 2x
Size: 5, Cap: 8, Growth: 2.0x
...
*/

// Clang (libc++) 用 1.5x~2x 之间，更保守
```

**扩容流程：**
1. 检测 `end == end_of_storage`
2. 分配新内存（大小为 `capacity * factor`）
3. 将旧元素 **移动** 到新内存（如果移动是 noexcept，否则复制）
4. 销毁旧元素
5. 释放旧内存

### 1.3 `push_back` vs `emplace_back`

```cpp
#include <vector>
#include <string>

struct Expensive {
    std::string s;
    int id;
    
    Expensive(const char* str, int i) : s(str), id(i) {
        std::cout << "Constructor: " << s << "\n";
    }
    Expensive(const Expensive& other) : s(other.s), id(other.id) {
        std::cout << "Copy: " << s << "\n";
    }
    Expensive(Expensive&& other) noexcept 
        : s(std::move(other.s)), id(other.id) {
        std::cout << "Move: " << s << "\n";
    }
};

void push_vs_emplace() {
    std::vector<Expensive> v;
    
    std::cout << "--- push_back with temporary ---\n";
    v.push_back(Expensive("temp", 1));  
    // 1) 构造临时对象
    // 2) 移动/复制到vector中
    // 3) 析构临时对象
    
    std::cout << "\n--- emplace_back ---\n";
    v.emplace_back("direct", 2);
    // 1) 在vector内存中直接构造（零临时对象）
}
```

**经验法则：** 当 push_back/emplace_back 的参数需要类型转换时，emplace_back 更优。当参数已经是右值临时对象时，push_back 和 emplace_back 等价（因为编译器会优化）。

### 1.4 `reserve` 的正确使用

```cpp
#include <vector>

// ❌ 不当使用：频繁扩容
void bad_usage() {
    std::vector<int> v;
    for (int i = 0; i < 1000000; ++i)
        v.push_back(i);  // 可能扩容 20 次！
}

// ✅ 正确：预先分配
void good_usage() {
    std::vector<int> v;
    v.reserve(1000000);  // 一次分配
    for (int i = 0; i < 1000000; ++i)
        v.push_back(i);
}
```

### 1.5 异常安全

```cpp
#include <vector>

// vector::push_back 提供强异常安全保证：
// 如果 push_back 失败，vector 保持原状

struct MightThrow {
    MightThrow() = default;
    MightThrow(const MightThrow&) {
        throw std::runtime_error("copy failed");
    }
    MightThrow(MightThrow&&) noexcept = default;
};

void exception_safety() {
    std::vector<MightThrow> v(5);  // 5个默认构造
    MightThrow obj;
    
    try {
        v.push_back(std::move(obj));  // 使用移动（noexcept）
        // 成功
    } catch (...) {
        // 不会进入这里，因为移动是 noexcept
    }
}
```

---

## 2. `std::string` — 小字符串优化

### 2.1 SSO（Small String Optimization）

```cpp
#include <string>
#include <iostream>

void sso_demo() {
    std::string s1 = "short";      // 5字符
    std::string s2 = "this is a long string that should exceed SSO buffer";
    
    std::cout << "s1 capacity: " << s1.capacity() << "\n";  // 通常 15 (GCC)
    std::cout << "s2 capacity: " << s2.capacity() << "\n";  // > SSO阈值
    
    // GCC libstdc++ 的 SSO 缓冲区是 15 字节
    // MSVC 是 16 字节（含 null 终止符）
    // Clang libc++ 是 22 字节
}
```

**SSO 的内存布局：**

```
短字符串（≤ 15字符）：
[  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  ]
 ^                  ^
 data + size        inline buffer (union with pointer)

长字符串（> 15字符）：
[ ptr | size | capacity ] → [  |  |  | ... ] 堆分配
```

### 2.2 COW（Copy-on-Write）已被废弃

C++11 前，某些实现（如 GCC 旧版）使用 COW：复制字符串时共享同一份堆内存，只在写入时才真正复制。C++11 后，COW 被禁止（因为移动语义和线程安全要求），所有现代实现都使用 SSO。

### 2.3 string 操作的性能特征

```cpp
// O(1) 操作
s.size(); s.empty(); s.c_str(); s.data();

// O(n) 操作
s = other;           // 深拷贝（SSO 内或外）
s + "world";         // 拼接
s.substr(0, 5);      // 子串（C++17 起可能 SSO）
s.find('x');         // 查找
s += "hello";        // 扩容
```

### 2.4 string_view 与 SSO

```cpp
#include <string_view>

// std::string_view 不拥有数据，没有 SSO
// 是 string 的"只读指针+大小"

void process(std::string_view sv) {
    // 无论传入的字符串大小，string_view 总是 16 字节（ptr+size）
    // 避免了 string 的 SSO 判断和可能的堆分配
}
```

---

## 3. `std::map` / `std::set` — 红黑树

### 3.1 红黑树的属性

`std::map` 和 `std::set` 通常用红黑树实现。红黑树的五个约束：

1. 每个节点是红色或黑色
2. 根节点是黑色
3. 叶子节点（NIL）是黑色
4. 红色节点的子节点必须是黑色（无连续红色）
5. 任意节点到其所有叶子节点的路径包含相同数量的黑色节点

```cpp
#include <map>
#include <set>
#include <iostream>

// GCC libstdc++ 的 _Rb_tree 节点结构
/*
struct _Rb_tree_node_base {
    _Rb_tree_color _M_color;  // _S_red 或 _S_black
    _Base_ptr _M_parent;
    _Base_ptr _M_left;
    _Base_ptr _M_right;
};

template<typename T>
struct _Rb_tree_node : _Rb_tree_node_base {
    T _M_storage;  // 实际数据
};
*/
```

### 3.2 map 的内存访问模式

```cpp
#include <map>
#include <chrono>

// map 的元素在堆上单独分配（每个节点一次 new）
// 这导致：
// 1. 内存不连续 → cache miss 更高
// 2. 每个节点额外开销：3个指针 + 颜色 = 约 24-32 字节
// 3. 插入 O(log n)、查找 O(log n)

void map_vs_vector() {
    const int N = 1000000;
    
    // map: 每个元素独立分配
    std::map<int, int> m;
    for (int i = 0; i < N; ++i)
        m[i] = i;  // N 次内存分配
    
    // vector pair sorted: 一次分配，连续内存
    std::vector<std::pair<int, int>> v;
    v.reserve(N);
    for (int i = 0; i < N; ++i)
        v.emplace_back(i, i);
    std::sort(v.begin(), v.end());  // 排序后可用 binary_search
    
    // 查找性能对比
    // map: O(log N) 但每次访问不同内存地址 → cache miss
    // sorted vector: O(log N) 但连续内存 → cache friendly
}
```

### 3.3 自定义比较器与透明查找（C++14）

```cpp
#include <map>
#include <string>

// 普通 map：用 std::string 做 key，每次查找都要构造 string
void normal_map() {
    std::map<std::string, int> m;
    m["hello"] = 42;
    
    // 下面这句会构造一个 std::string 临时对象！
    auto it = m.find("hello");  // const char* → string 隐式构造
}

// 透明比较器（C++14）：允许用任意类型查找
struct TransparentCompare {
    using is_transparent = void;  // 标识为透明
    
    bool operator()(const std::string& a, const std::string& b) const {
        return a < b;
    }
    // 允许 string vs const char* 的比较
    bool operator()(const std::string& a, const char* b) const {
        return a < b;
    }
    bool operator()(const char* a, const std::string& b) const {
        return a < b;
    }
};

void transparent_map() {
    std::map<std::string, int, TransparentCompare> m;
    m["hello"] = 42;
    
    // 不构造 string 临时对象！
    auto it = m.find("hello");  // OK，直接比较 const char*
}
```

---

## 4. `std::unordered_map` — 哈希表

### 4.1 分桶结构

```cpp
#include <unordered_map>
#include <iostream>

void hash_structure() {
    std::unordered_map<int, std::string> m;
    
    // 底层结构：
    // bucket array: [  |  |  |  |  |  |  |  ]
    //                 ↓     ↓
    //            链表节点  链表节点
    //            ↓
    //           链表节点
    
    std::cout << "bucket_count: " << m.bucket_count() << "\n";  // 通常是素数
    std::cout << "max_load_factor: " << m.max_load_factor() << "\n";  // 默认 1.0
    
    // 当 size/bucket_count > max_load_factor 时 rehash
    // rehash 导致全部重新分布：O(n)
}
```

### 4.2 自定义哈希

```cpp
#include <unordered_map>
#include <functional>

struct Point {
    int x, y;
    
    bool operator==(const Point& other) const {
        return x == other.x && y == other.y;
    }
};

// 自定义哈希函数
struct PointHash {
    std::size_t operator()(const Point& p) const noexcept {
        // 黄金分割哈希组合
        return std::hash<int>{}(p.x) ^ (std::hash<int>{}(p.y) << 1);
    }
};

// 使用
std::unordered_map<Point, std::string, PointHash> point_map;

// 或者用 lambda（C++20）
auto hasher = [](const Point& p) {
    return std::hash<int>{}(p.x) ^ (std::hash<int>{}(p.y) << 1);
};
std::unordered_map<Point, std::string, decltype(hasher)> map2(0, hasher);
```

### 4.3 性能优化

```cpp
#include <unordered_map>

void hash_optimizations() {
    std::unordered_map<int, int> m;
    
    // 预分配桶（避免多次 rehash）
    m.reserve(1000000);  // 相当于 rehash 到能容纳 1M 元素
    
    // 控制装载因子
    m.max_load_factor(0.7);  // 更低 = 更少冲突 = 更快但更多内存
    // m.max_load_factor(0.9);  // 更高 = 更多冲突 = 更慢但更省内存
}
```

---

## 5. 分配器的深入理解

### 5.1 默认分配器

```cpp
#include <memory>
#include <vector>

// std::allocator<T> 只是 operator new/delete 的简单包装

template<typename T>
struct MyAllocator {
    using value_type = T;
    
    MyAllocator() = default;
    
    template<typename U>
    MyAllocator(const MyAllocator<U>&) {}
    
    T* allocate(std::size_t n) {
        std::cout << "Allocate " << n * sizeof(T) << " bytes\n";
        return static_cast<T*>(::operator new(n * sizeof(T)));
    }
    
    void deallocate(T* p, std::size_t n) noexcept {
        std::cout << "Deallocate " << n * sizeof(T) << " bytes\n";
        ::operator delete(p);
    }
    
    // 所有 MyAllocator<T> 实例都相等
    template<typename U>
    bool operator==(const MyAllocator<U>&) const { return true; }
    
    template<typename U>
    bool operator!=(const MyAllocator<U>&) const { return false; }
};

// 使用自定义分配器的 vector
std::vector<int, MyAllocator<int>> custom_vec;
custom_vec.push_back(42);  // 会打印分配信息
```

### 5.2 有状态分配器（C++11）

```cpp
// C++11 前分配器必须是无状态的（stateless）
// C++11 后分配器可以有状态
// 容器必须根据 `allocator_traits` 判断分配器是否有状态

#include <memory>

template<typename T, int ID>
struct StatefulAllocator {
    using value_type = T;
    
    int id = ID;
    
    StatefulAllocator() = default;
    
    template<typename U>
    StatefulAllocator(const StatefulAllocator<U, ID>& other) : id(other.id) {}
    
    T* allocate(std::size_t n) {
        return static_cast<T*>(::operator new(n * sizeof(T)));
    }
    
    void deallocate(T* p, std::size_t n) noexcept {
        ::operator delete(p);
    }
    
    // 不同的 id 是不相等的——容器在重新分配时需要考虑
    template<typename U, int OtherID>
    bool operator==(const StatefulAllocator<U, OtherID>&) const { return ID == OtherID; }
    
    template<typename U, int OtherID>
    bool operator!=(const StatefulAllocator<U, OtherID>&) const { return ID != OtherID; }
};
```

### 5.3 PMR 分配器（C++17）

```cpp
#include <memory_resource>
#include <vector>
#include <iostream>

void pmr_demo() {
    // 栈缓冲区（monotonic_buffer_resource 是最快的分配器之一）
    char buffer[1024];  // 1KB 栈内存
    std::pmr::monotonic_buffer_resource pool{
        buffer, sizeof(buffer), std::pmr::null_memory_resource()
    };
    
    // 使用 PMR 分配器的 vector
    std::pmr::vector<int> v(&pool);
    
    // 分配都在栈上进行——零碎片，分配 O(1)
    for (int i = 0; i < 100; ++i)
        v.push_back(i);
    
    std::cout << "Used " << v.size() * sizeof(int) << " bytes from stack\n";
    // 用完一次性释放（不用逐个 deallocate）
}
```

---

## 6. 容器性能对比

| 操作 | vector | deque | list | map | unordered_map |
|------|--------|-------|------|-----|---------------|
| 插入头部 | O(n) | O(1) amortized | O(1) | O(log n) | O(1) avg |
| 插入尾部 | O(1) amortized | O(1) amortized | O(1) | O(log n) | O(1) avg |
| 查找 | O(n) | O(n) | O(n) | O(log n) | O(1) avg |
| 随机访问 | O(1) | O(1) | O(n) | O(log n) | - |
| 删除（已知位置） | O(n) | O(n) | O(1) | O(log n) | O(1) avg |
| 内存连续性 | 连续 | 分块连续 | 分散 | 分散 | 分散 |

### 6.1 选择指南

```cpp
// 默认容器
std::vector<T> v;  // 99% 情况够用

// 需要频繁在头部插入/删除
std::deque<T> d;    // 比 vector 好，但比 list 差

// 需要在中间频繁插入/删除
std::list<T> l;     // 但 cache miss 严重，小数据可能 vector 更快

// 需要有序键值对
std::map<K, V> m;   // 有顺序要求时唯一选择

// 只需要键值对，不需要顺序
std::unordered_map<K, V> um;  // 比 map 快 O(log n) vs O(1)

// 数据固定且需要排序查找
// std::vector + std::sort + std::lower_bound 比 map 更快
// 因为内存连续
```

---

## 7. 在 libkds/KVStore 中的实战建议

### 7.1 用连续内存代替离散

```cpp
// KVStore 当前用 std::map（离散节点）
// 大量小 KV 对时，cache miss 严重

// 优化方案1：分离存储
struct KVStoreOptimized {
    // 键和值分别连续存储
    std::vector<std::string> keys_;
    std::vector<std::span<const std::byte>> values_;
    // 查找时遍历 keys_（线性扫描对少量数据更快）
};
```

### 7.2 SSO 对小 value 的优化

```cpp
// 对小型 value（< 15字节），利用 string 的 SSO 避免堆分配
struct SmallValue {
    std::string data;  // < 16 字节时无需堆分配
};
```

### 7.3 PMR 的应用

```cpp
// KVStore 的临时查询可以用 PMR 减少分配
std::pmr::monotonic_buffer_resource query_pool;
std::pmr::vector<std::byte> temp_result(&query_pool);
// 查询完成后一次性释放
```

---

## 总结

| 容器 | 核心实现 | 最佳使用场景 |
|------|----------|-------------|
| `vector` | 动态数组 + 2x 扩容 | 默认选择，尾部插入+随机访问 |
| `string` | SSO + 堆分配（COW 已废弃） | 任何字符串，注意 SSO 阈值 |
| `map/set` | 红黑树 | 需要排序的关联容器 |
| `unordered_map/set` | 哈希表 + 链表冲突链 | 不需要排序的关联容器 |
| `deque` | 分块数组 | 双端插入删除 |
| `list/forward_list` | 双向/单向链表 | 仅需异常删除/插入时 |
