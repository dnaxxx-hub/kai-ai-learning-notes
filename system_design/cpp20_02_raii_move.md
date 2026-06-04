# RAII、移动语义与智能指针深度解析

> C++ 资源管理的终极武器 — 从零异常安全到现代所有权的全面理解

---

## 1. RAII 核心原理

### 1.1 什么是 RAII

RAII（Resource Acquisition Is Initialization）是 C++ 中最核心的范型——资源在构造函数中获取，在析构函数中释放。编译器保证局部对象的析构函数在作用域退出时被调用，这使得 RAII 成为**异常安全**的基石。

```cpp
#include <iostream>
#include <stdexcept>

class FileHandle {
    FILE* fp_;
public:
    explicit FileHandle(const char* path, const char* mode)
        : fp_(fopen(path, mode)) {
        if (!fp_) throw std::runtime_error("Cannot open file");
    }
    
    // 析构函数保证释放
    ~FileHandle() {
        if (fp_) {
            fclose(fp_);
            std::cout << "File closed automatically\n";
        }
    }
    
    // 禁止复制（资源不能复制）
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
    
    // 允许移动
    FileHandle(FileHandle&& other) noexcept : fp_(other.fp_) {
        other.fp_ = nullptr;
    }
    
    void write(const char* data) {
        if (fp_) fputs(data, fp_);
    }
};

void process_file() {
    FileHandle fh("test.txt", "w");
    fh.write("Hello RAII");
    // 抛出异常也无妨 —— fh 的析构仍会运行
    throw std::runtime_error("Unexpected error");
    // fh.~FileHandle() 仍会被调用 ✅
}

int main() {
    try {
        process_file();
    } catch (...) {
        std::cout << "Exception caught, but file was closed safely\n";
    }
}
```

### 1.2 三条/五条规则（Rule of Three/Five）

如果一个类需要自定义析构函数、复制构造函数或复制赋值运算符中的任何一个，那么它很可能需要全部三个（C++98 的三条规则）。C++11 加入移动语义后扩展为五条规则。

```cpp
class RuleOfFive {
    int* data_;
    size_t size_;
public:
    // 1) 构造函数
    explicit RuleOfFive(size_t n) : data_(new int[n]()), size_(n) {}
    
    // 2) 析构函数
    ~RuleOfFive() { delete[] data_; }
    
    // 3) 复制构造函数 — 深拷贝
    RuleOfFive(const RuleOfFive& other) 
        : data_(new int[other.size_]), size_(other.size_) {
        std::copy(other.data_, other.data_ + size_, data_);
    }
    
    // 4) 复制赋值 — Copy-and-Swap 惯用法
    RuleOfFive& operator=(const RuleOfFive& other) {
        if (this != &other) {
            auto* tmp = new int[other.size_];
            std::copy(other.data_, other.data_ + other.size_, tmp);
            delete[] data_;
            data_ = tmp;
            size_ = other.size_;
        }
        return *this;
    }
    
    // 5) 移动构造函数
    RuleOfFive(RuleOfFive&& other) noexcept 
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;
        other.size_ = 0;
    }
    
    // 6) 移动赋值
    RuleOfFive& operator=(RuleOfFive&& other) noexcept {
        if (this != &other) {
            delete[] data_;
            data_ = other.data_;
            size_ = other.size_;
            other.data_ = nullptr;
            other.size_ = 0;
        }
        return *this;
    }
};
```

**优化版：Copy-and-Swap**

```cpp
class RuleOfFiveBetter {
    int* data_;
    size_t size_;
public:
    explicit RuleOfFiveBetter(size_t n) : data_(new int[n]()), size_(n) {}
    ~RuleOfFiveBetter() { delete[] data_; }
    
    // 复制构造
    RuleOfFiveBetter(const RuleOfFiveBetter& other) 
        : data_(new int[other.size_]), size_(other.size_) {
        std::copy(other.data_, other.data_ + size_, data_);
    }
    
    // 移动构造
    RuleOfFiveBetter(RuleOfFiveBetter&& other) noexcept 
        : data_(std::exchange(other.data_, nullptr)), 
          size_(std::exchange(other.size_, 0)) {}
    
    // 统一赋值：复制+移动二合一（参数传值触发复制或移动）
    RuleOfFiveBetter& operator=(RuleOfFiveBetter other) noexcept {
        swap(*this, other);
        return *this;
    }
    
    friend void swap(RuleOfFiveBetter& a, RuleOfFiveBetter& b) noexcept {
        using std::swap;
        swap(a.data_, b.data_);
        swap(a.size_, b.size_);
    }
};
```

**关键点**：`operator=` 的参数是**传值**而非传引用。当传入左值时调用复制构造创建 `other`，传入右值时调用移动构造。然后与 `*this` 交换，`other` 析构时自动释放旧资源。

---

## 2. 移动语义详解

### 2.1 左值、右值与引用

```cpp
#include <utility>
#include <string>
#include <iostream>

// 左值：有地址、有名字、可取地址的表达式
// 右值：临时对象、字面量、即将销毁的值

void check(std::string& s)  { std::cout << "lvalue ref\n"; }
void check(std::string&& s) { std::cout << "rvalue ref\n"; }

int main() {
    std::string s = "hello";
    
    check(s);            // lvalue ref
    check("world");      // rvalue ref（字面量是右值）
    check(std::move(s)); // rvalue ref（std::move 转换为右值）
}
```

### 2.2 `std::move` 的本质

`std::move` 不做任何移动——它只是一个**强制类型转换**：

```cpp
// std::move 的参考实现
template<typename T>
constexpr std::remove_reference_t<T>&& move(T&& t) noexcept {
    return static_cast<std::remove_reference_t<T>&&>(t);
}
```

**理解：** `std::move(s)` 说"请把 s 当右值用"，s 本身不会被销毁，但移动后处于**有效但未指定**状态。

### 2.3 `std::forward` — 完美转发

```cpp
#include <utility>
#include <memory>

template<typename T>
void wrapper(T&& arg) {
    // T&& 是万能引用（Universal Reference）
    // 当传入左值时 T 推导为 T&，传入右值时 T 推导为 T
    // std::forward 保持左右值属性
    actual_function(std::forward<T>(arg));
}

// 必须用 forward，不能直接传 arg：
// 如果 arg 原本是右值，直接传会变成左值（有名字就是左值）
// forward 根据 T 的类型决定是否转换为右值引用
```

**实战：完美转发的工厂函数**

```cpp
template<typename T, typename... Args>
std::unique_ptr<T> make_unique(Args&&... args) {
    return std::unique_ptr<T>(new T(std::forward<Args>(args)...));
}

// 使用
auto p = make_unique<std::string>(10, 'x');  // 完美转发参数到 string 构造
```

---

## 3. 智能指针详解

### 3.1 `std::unique_ptr` — 独有所有权

```cpp
#include <memory>
#include <vector>
#include <iostream>

struct TreeNode {
    int value;
    std::unique_ptr<TreeNode> left, right;
    
    explicit TreeNode(int v) : value(v) {}
};

TreeNode* insert(TreeNode* root, int value) {
    if (!root) return new TreeNode(value);
    
    if (value < root->value) {
        if (!root->left) {
            root->left = std::make_unique<TreeNode>(value);
        } else {
            insert(root->left.get(), value);
        }
    }
    // 注意：这里用裸指针返回，所有权仍在 unique_ptr 中
    return root;
}

// 定制删除器
struct FileDeleter {
    void operator()(FILE* fp) const {
        if (fp) {
            fclose(fp);
            std::cout << "Custom deleter: file closed\n";
        }
    }
};

using UniqueFile = std::unique_ptr<FILE, FileDeleter>;

UniqueFile open_file(const char* path) {
    FILE* fp = fopen(path, "w");
    if (!fp) throw std::runtime_error("open failed");
    return UniqueFile(fp);
}

int main() {
    auto root = std::make_unique<TreeNode>(5);
    insert(root.get(), 3);
    insert(root.get(), 7);
    // 树在作用域结束时自动释放（递归析构）
    
    auto file = open_file("test.txt");
    // 自动调用 fclose
}
```

### 3.2 `std::shared_ptr` — 共享所有权

```cpp
#include <memory>
#include <iostream>

struct SharedResource {
    int id;
    explicit SharedResource(int i) : id(i) {
        std::cout << "Resource " << id << " created\n";
    }
    ~SharedResource() {
        std::cout << "Resource " << id << " destroyed\n";
    }
};

int main() {
    // make_shared 更高效（一次分配同时放控制块和数据）
    auto p1 = std::make_shared<SharedResource>(1);
    
    {
        auto p2 = p1;  // 引用计数 2
        auto p3 = p2;  // 引用计数 3
        std::cout << "use_count: " << p1.use_count() << "\n";  // 3
    }
    // p2, p3 销毁，计数回到 1
    
    std::cout << "Still alive\n";
    // p1 销毁，计数为 0，资源释放
}
```

### 3.3 `std::weak_ptr` — 打破循环引用

```cpp
#include <memory>
#include <iostream>

// 树/图结构中的双向引用容易导致循环引用
struct Node : std::enable_shared_from_this<Node> {
    int value;
    std::shared_ptr<Node> parent;    // 子→父：weak_ptr 更合适
    std::weak_ptr<Node> weak_parent; // 用 weak_ptr 打破循环
    std::vector<std::shared_ptr<Node>> children;
    
    explicit Node(int v) : value(v) {}
    
    void add_child(std::shared_ptr<Node> child) {
        child->weak_parent = shared_from_this();  // weak_ptr 赋值
        children.push_back(child);
    }
    
    std::shared_ptr<Node> get_parent() const {
        return weak_parent.lock();  // 如果父节点已销毁返回 nullptr
    }
};

int main() {
    auto root = std::make_shared<Node>(0);
    auto child = std::make_shared<Node>(1);
    root->add_child(child);
    
    // 安全访问父节点
    if (auto parent = child->get_parent()) {
        std::cout << "Parent value: " << parent->value << "\n";
    }
    
    // 如果 root 先被销毁，child->get_parent() 返回 nullptr
}
```

### 3.4 性能对比

| 智能指针 | 内存开销 | 线程安全 | 使用场景 |
|----------|----------|----------|----------|
| `unique_ptr` | 与裸指针相同 | 不适用（不可复制） | 独占所有权，默认选择 |
| `shared_ptr` | 2×指针大小（控制块+数据） | 引用计数原子操作 | 真正需要共享所有权 |
| `weak_ptr` | 与 shared_ptr 同 | 隐式线程安全 | 观察者/缓存/打破循环 |

**推荐顺序：** 裸指针/引用 → `unique_ptr` → `shared_ptr`（只在确实需要共享时）

---

## 4. 异常安全保证

### 4.1 三个级别

| 级别 | 含义 | 实现方式 |
|------|------|----------|
| **基本保证** | 异常时资源不泄漏，对象处于有效但不可预测状态 | RAII 管理器 |
| **强保证** | 异常时状态回滚到操作前 | Copy-and-Swap |
| **不抛保证** | 永远不会抛出异常 | noexcept + 避免分配 |

### 4.2 异常安全容器操作

```cpp
#include <vector>
#include <string>
#include <cassert>

class SafeVector {
    std::vector<int> data_;
public:
    // 强异常安全保证
    void push_back(int value) {
        // std::vector::push_back 自身提供强保证
        //（但注意：对于 non-noexcept 移动的类，vector 会退化为复制）
        data_.push_back(value);
    }
    
    // 批量插入 — 自己实现强保证
    void insert_range(const std::vector<int>& values) {
        // 先确保容量足够（可能失败，但不影响现有数据）
        if (values.size() > data_.capacity() - data_.size()) {
            auto copy = data_;
            copy.reserve(data_.size() + values.size());
            copy.insert(copy.end(), values.begin(), values.end());
            // swap 保证不抛异常
            data_.swap(copy);
        } else {
            // 容量足够，直接插入（vector 保证强保证）
            data_.insert(data_.end(), values.begin(), values.end());
        }
    }
};

// noexcept 的重要性
struct NoExceptMoved {
    std::vector<int> data;
    // 移动构造标注 noexcept = vector 可以安全移动
    NoExceptMoved(NoExceptMoved&& other) noexcept : data(std::move(other.data)) {}
};
```

### 4.3 事务性操作模式

```cpp
#include <map>
#include <string>

class Account {
    std::map<std::string, double> balances_;
public:
    // 事务性转账 — 要么全成功，要么全回滚
    bool transfer(const std::string& from, const std::string& to, double amount) {
        if (amount < 0) return false;
        
        auto it_from = balances_.find(from);
        if (it_from == balances_.end() || it_from->second < amount)
            return false;
        
        // 先将金额减少（如果是强保证的，副本事务更保险）
        it_from->second -= amount;
        
        auto it_to = balances_.find(to);
        if (it_to == balances_.end()) {
            // 如果接收方不存在，需要回滚
            it_from->second += amount;
            return false;
        }
        
        try {
            it_to->second += amount;
        } catch (...) {
            // 异常时回滚转出方
            it_from->second += amount;
            throw;
        }
        return true;
    }
};
```

---

## 5. 现代 RAII 实战模式

### 5.1 Scope Guard

```cpp
#include <functional>

class ScopeGuard {
    std::function<void()> cleanup_;
    bool active_ = true;
public:
    explicit ScopeGuard(std::function<void()> cleanup) 
        : cleanup_(std::move(cleanup)) {}
    
    ~ScopeGuard() {
        if (active_ && cleanup_) cleanup_();
    }
    
    void dismiss() { active_ = false; }
    
    ScopeGuard(const ScopeGuard&) = delete;
    ScopeGuard& operator=(const ScopeGuard&) = delete;
};

// 使用：在任意作用域结束时执行清理
void process_with_cleanup() {
    allocate_resource();
    
    ScopeGuard guard([&] {
        release_resource();
    });
    
    // 即使中间抛出异常，guard 的析构也会运行
    do_something_risky();
    
    guard.dismiss();  // 正常完成时取消清理
}
```

### 5.2 RAII 锁

```cpp
#include <mutex>

// std::lock_guard 已提供 RAII 锁，这里演示封装原理
template<typename Mutex>
class LockGuard {
    Mutex& mutex_;
public:
    explicit LockGuard(Mutex& mtx) : mutex_(mtx) {
        mutex_.lock();
    }
    ~LockGuard() { mutex_.unlock(); }
    
    LockGuard(const LockGuard&) = delete;
    LockGuard& operator=(const LockGuard&) = delete;
};
```

### 5.3 应用于 libkds/KVStore

**KVStore 可以使用 RAII 管理 mmap：**

```cpp
#include <sys/mman.h>
#include <unistd.h>
#include <cstring>

class MappedFile {
    void* addr_;
    size_t length_;
public:
    MappedFile(int fd, size_t len) 
        : addr_(mmap(nullptr, len, PROT_READ, MAP_SHARED, fd, 0)),
          length_(len) {
        if (addr_ == MAP_FAILED)
            throw std::runtime_error("mmap failed: " + std::string(strerror(errno)));
    }
    
    ~MappedFile() {
        if (addr_ && addr_ != MAP_FAILED)
            munmap(addr_, length_);
    }
    
    // 禁止复制，允许移动
    MappedFile(MappedFile&& other) noexcept : addr_(other.addr_), length_(other.length_) {
        other.addr_ = nullptr;
    }
    
    std::span<const std::byte> view() const {
        return {static_cast<const std::byte*>(addr_), length_};
    }
    
    MappedFile(const MappedFile&) = delete;
    MappedFile& operator=(const MappedFile&) = delete;
};
```

**shared_ptr 在 libkds 共享缓存场景：**

```cpp
class SharedCache {
    struct CacheEntry {
        std::vector<std::byte> data;
        std::chrono::steady_clock::time_point expires_at;
    };
    
    std::map<std::string, std::shared_ptr<CacheEntry>> entries_;
public:
    std::shared_ptr<CacheEntry> get(std::string_view key) {
        auto it = entries_.find(std::string(key));
        if (it != entries_.end() && 
            it->second->expires_at > std::chrono::steady_clock::now()) {
            return it->second;
        }
        return nullptr;
    }
};
```

---

## 6. 性能与陷阱

### 6.1 移动构造必须 noexcept

```cpp
struct BadMoved {
    std::vector<int> data;
    // 没有 noexcept！
    BadMoved(BadMoved&& other) : data(std::move(other.data)) {}
};

struct GoodMoved {
    std::vector<int> data;
    GoodMoved(GoodMoved&& other) noexcept : data(std::move(other.data)) {}
};

void test() {
    std::vector<BadMoved> bad_vec(10);
    // 当 vector 扩容时，BadMoved 没有 noexcept 移动
    // vector 会使用复制而非移动，代价 O(n) vs O(1)
    
    std::vector<GoodMoved> good_vec(10);
    // 有 noexcept，vector 使用移动，O(1) per element
}
```

### 6.2 自赋值安全

```cpp
// 错误：未处理自赋值
class SelfAssignBad {
    int* data_;
public:
    SelfAssignBad& operator=(const SelfAssignBad& other) {
        delete[] data_;                         // 先释放自身
        data_ = new int[other.size_];           // 如果 other 就是 *this
        // 此时 data_ 已释放，other.size_ 访问已释放内存！UB
        return *this;
    }
};

// 正确：Copy-and-Swap 天然处理自赋值
// 因为 swap 在临时对象上，不影响 *this
```

### 6.3 返回 local unique_ptr 的正确方式

```cpp
std::unique_ptr<int> create() {
    auto p = std::make_unique<int>(42);
    // return p;          // ❌ 编译错误？不，这里OK！
    return p;              // ✅ 编译器会自动使用移动
}

std::unique_ptr<int> create_explicit() {
    return std::make_unique<int>(42);  // ✅ 直接构造在返回值中（RVO/NRVO）
}
```

### 6.4 make_shared 的内存碎片陷阱

```cpp
// make_shared 一次分配控制块+数据在一起
auto p = std::make_shared<LargeObject>(args);
// 即使所有 shared_ptr 都销毁了，只要还有一个 weak_ptr 存在
// 控制块就必须保留，LargeObject 的内存就不能释放
// 所以：如果有 long-lived weak_ptr，考虑 new shared_ptr

// 用 new 时控制块和数据分离
auto p = std::shared_ptr<LargeObject>(new LargeObject(args));
weak_ptr 释放后，控制块独立存在，数据内存可以回收
```

---

## 总结

| 概念 | 关键点 | 实战建议 |
|------|--------|----------|
| RAII | 构造获取/析构释放 | 默认资源管理方式 |
| 三条/五条规则 | 自定义一个就需要五个 | 优先用 =default |
| 移动语义 | 右值引用 && + std::move + std::forward | noexcept 是必须的 |
| unique_ptr | 独占所有权，零开销 | 优先选 unique_ptr |
| shared_ptr | 引用计数，2×内存 | 只在需要共享时用 |
| weak_ptr | 打破循环引用 | 配合 enable_shared_from_this |
| 异常安全 | 基本/强/不抛 | Copy-and-Swap 是强保证利器 |
| ScopeGuard | 任意资源 RAII 封装 | 替代 try/catch 的扁平原语 |
