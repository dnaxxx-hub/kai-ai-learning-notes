# 移动语义 (Move Semantics)

## C++11 之前的值类型问题

```cpp
std::vector<int> create() {
    std::vector<int> v(1'000'000);
    return v;  // 完整深拷贝整个数组！
}
```

C++03 的解决方式（NRVO）不保证生效。C++11 引入移动语义，将资源"偷"过来而非复制。

## 右值引用 (T&&)

**左值 vs 右值**：
- 左值：有地址、可取址的表达式（`x`, `*p`, `a[i]`）
- 右值：临时对象、字面量（`42`, `f()` 返回值）

```cpp
int a = 42;
int& lref = a;   // 左值引用
int&& rref = 42; // 右值引用（只能绑定到右值）
// int& ref = 42; // ❌ 非常量左值引用不能绑右值
```

**引用折叠 (Reference Collapsing)**：

```
T&  &  → T&
T&  && → T&
T&& &  → T&
T&& && → T&&
```

## 完美转发 (std::forward)

保持参数的左右值属性：

```cpp
template<typename T>
void wrapper(T&& arg) {              // 万能引用（不是右值引用！）
    target(std::forward<T>(arg));    // 保持 arg 的左右值性
}
```

当 `T` 推导为 `int&` → `T&&` 折叠为 `int&`（左值）  
当 `T` 推导为 `int` → `T&&` 为 `int&&`（右值）

## 移动构造函数 / 移动赋值

```cpp
class Buffer {
    int* data_;
    size_t size_;
public:
    // 移动构造
    Buffer(Buffer&& other) noexcept
        : data_(other.data_), size_(other.size_) {
        other.data_ = nullptr;
        other.size_ = 0;
    }
    
    // 移动赋值
    Buffer& operator=(Buffer&& other) noexcept {
        if (this != &other) {
            delete[] data_;           // 释放当前资源
            data_ = other.data_;      // 窃取指针
            size_ = other.size_;
            other.data_ = nullptr;    // 源置空
            other.size_ = 0;
        }
        return *this;
    }
};
```

**Rule of Five**：如果自定义了析构/拷贝构造/拷贝赋值之一，则应考虑全部五个（+ 移动构造 + 移动赋值）。

## Move-Only 类型

**std::unique_ptr** — 唯一所有权，不可复制：

```cpp
auto u1 = std::make_unique<int>(42);
// auto u2 = u1;           // ❌ 拷贝禁用
auto u2 = std::move(u1);   // ✅ 移动转移所有权
```

其他 move-only 类型：
- `std::thread` — 执行线程
- `std::future<T>` — 异步结果
- `std::unique_lock` — 锁的所有权
- `std::fstream` — 文件流
- `std::promise<T>` — 异步通道

## 常见陷阱

### auto&&

`auto&&` 是万能引用，不是右值引用！

```cpp
auto&& x = expr;  // 保持 expr 的左右值性（范围 for 中常见）
for (auto&& item : vec) { /* 完美转发元素 */ }
```

### return move

```cpp
// ❌ 画蛇添足（阻止 NRVO）
std::vector<int> f() {
    std::vector<int> v = {1,2,3};
    return std::move(v);  // 禁止编译器做 RVO！
}

// ✅ 相信编译器
std::vector<int> f() {
    std::vector<int> v = {1,2,3};
    return v;  // 编译器自动做 RVO 或隐式移动
}
```

## Small String Optimization (SSO)

```cpp
std::string s1 = "hi";           // 栈上存储（<=15 字节）
std::string s2 = "very long string that exceeds SSO capacity"; // 堆上
```

SSO 原理：
- `std::string` 内部包含一个固定大小的缓冲区（通常 15-22 字节）
- 短字符串直接存在栈上缓冲区，无需堆分配
- 长字符串才动态分配

**移动语义对 SSO 的影响**：移动短字符串是 O(1) memcpy，移动长字符串也只需复制指针。现代实现中 `std::string` 的移动几乎是常量时间。
