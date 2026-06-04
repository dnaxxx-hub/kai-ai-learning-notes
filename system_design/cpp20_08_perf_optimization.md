# C++20 性能优化实战

> 从编译期计算到内存布局，每纳秒都很重要

---

## 1. 编译期计算

### 1.1 constexpr 与 consteval

C++20 大幅扩展了编译期计算的能力。

```cpp
#include <array>
#include <algorithm>
#include <iostream>

// constexpr 函数可以在编译期和运行时执行
constexpr int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// consteval 保证只在编译期执行
consteval int compile_time_only(int n) {
    return factorial(n);  // 必须在编译期有定义
}

// 编译期查找表
template<int N>
struct LookupTable {
    std::array<int, N> data;
    
    constexpr LookupTable() : data{} {
        for (int i = 0; i < N; ++i) {
            data[i] = factorial(i);
        }
    }
    
    constexpr int get(int i) const { return data[i]; }
};

// 全局编译期查找表（零运行时开销）
constexpr auto fact_table = LookupTable<12>();

// 编译期排序
consteval auto sorted_primes() {
    std::array<int, 9> primes = {7, 2, 13, 3, 11, 5, 17, 19, 23};
    std::sort(primes.begin(), primes.end());
    return primes;
}
constexpr auto primes = sorted_primes();  // 编译期完成

int main() {
    // 运行时：查表 O(1)
    for (int i = 0; i < 10; ++i)
        std::cout << fact_table.get(i) << " ";
    // 1 1 2 6 24 120 720 5040 40320 362880
    
    for (auto p : primes)
        std::cout << p << " ";  // 2 3 5 7 11 13 17 19 23
}
```

### 1.2 编译期字符串哈希

```cpp
#include <cstdint>
#include <string_view>

// FNV-1a 编译期哈希
consteval uint64_t fnv1a(const char* str, size_t len) {
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < len; ++i) {
        hash ^= static_cast<uint64_t>(str[i]);
        hash *= 1099511628211ULL;
    }
    return hash;
}

consteval uint64_t operator""_hash(const char* str, size_t len) {
    return fnv1a(str, len);
}

// 编译期 switch（替代运行时 strcmp）
struct ConfigKey {
    uint64_t hash;
    
    consteval ConfigKey(const char* key) : hash(fnv1a(key, strlen(key))) {}
    
    friend bool operator==(const ConfigKey& a, uint64_t b) {
        return a.hash == b;
    }
};

int get_config_value(std::string_view key) {
    switch (fnv1a(key.data(), key.size())) {
        case "timeout"_hash:  return 30;
        case "retries"_hash:  return 3;
        case "verbose"_hash:  return 1;
        default:              return 0;
    }
    // 编译期生成完美哈希，运行时 O(1)
}
```

### 1.3 编译期正则表达式（C++20 受限）

```cpp
// C++20 可以在 constexpr 上下文中使用 std::regex
//（但不同编译器支持程度不同，GCC 13+ 支持较好）

#include <regex>

constexpr bool is_valid_format(const char* s) {
    // GCC 13+ 支持
    constexpr std::regex pattern(R"(\d{4}-\d{2}-\d{2})");
    return std::regex_match(s, pattern);
}
// static_assert(is_valid_format("2026-05-16")); // GCC 13+ 可编译
```

---

## 2. SIMD 向量化

### 2.1 auto-vectorization 基础

```cpp
#include <vector>
#include <algorithm>

// 编译器会自动向量化简单的循环
void vector_add_auto(const float* a, const float* b, float* c, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        c[i] = a[i] + b[i];  // 编译器生成 SIMD 指令
    }
}

// 阻止向量化的坏习惯
float sum_bad(const std::vector<float>& v) {
    float s = 0;
    for (size_t i = 0; i < v.size(); ++i) {
        s += v[i];  // 可以向量化（使用 SIMD 归约）
    }
    return s;
}

// ❌ 指针混叠阻止向量化
void bad_alias(float* a, float* b, float* c, bool condition) {
    for (int i = 0; i < 1000; ++i) {
        if (condition)
            a[i] = b[i] + c[i];  // condition 不变但编译器不确定
        else
            a[i] = b[i] - c[i];  // 循环内分支可能阻止向量化
    }
}

// ✅ 帮助编译器向量化
void good_alias(float* __restrict__ a, 
                const float* __restrict__ b, 
                const float* __restrict__ c) {
    // __restrict__ 告诉编译器指针不重叠
    for (int i = 0; i < 1000; ++i) {
        a[i] = b[i] + c[i];  // 编译器可以向量化
    }
}
```

### 2.2 使用编译器内置 SIMD

```cpp
#include <cstdint>

// SSE/AVX 内置函数（x86）
#ifdef __SSE2__
#include <emmintrin.h>  // SSE2
#endif

#ifdef __AVX2__
#include <immintrin.h>  // AVX2
#endif

void vector_add_sse(const float* a, const float* b, float* c, size_t n) {
    size_t i = 0;
    
#ifdef __AVX2__
    // AVX2 一次处理 8 个 float
    for (; i + 8 <= n; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        __m256 vc = _mm256_add_ps(va, vb);
        _mm256_storeu_ps(&c[i], vc);
    }
#elif defined(__SSE2__)
    // SSE2 一次处理 4 个 float
    for (; i + 4 <= n; i += 4) {
        __m128 va = _mm_loadu_ps(&a[i]);
        __m128 vb = _mm_loadu_ps(&b[i]);
        __m128 vc = _mm_add_ps(va, vb);
        _mm_storeu_ps(&c[i], vc);
    }
#endif
    
    // 剩余元素用普通循环
    for (; i < n; ++i) {
        c[i] = a[i] + b[i];
    }
}

// C++20 提案中的 std::simd（尚未标准化）
// #include <experimental/simd>
// void vector_add_simd(const float* a, const float* b, float* c, size_t n) {
//     // 未来的标准方式
//     std::experimental::native_simd<float> va, vb, vc;
//     // ...
// }
```

### 2.3 对量化策略的 SIMD 加速

```cpp
#include <cstdint>
#include <cstring>

// 计算SMA（简单移动平均）的向量化版本
void sma_simd(const double* prices, double* output, size_t n, int period) {
    size_t i = period - 1;
    
    // 初始窗口和
    double sum = 0;
    for (int j = 0; j < period; ++j) sum += prices[j];
    output[i] = sum / period;
    
    // 滑动窗口：O(1) each
    for (++i; i < n; ++i) {
        sum += prices[i] - prices[i - period];
        output[i] = sum / period;
    }
    // 自动被编译器向量化
}

// K线数据的批量归一化
void normalize_batch_simd(float* data, size_t n) {
    // 寻找最大最小值（可向量化）
    float min_val = data[0], max_val = data[0];
    for (size_t i = 1; i < n; ++i) {
        min_val = std::min(min_val, data[i]);  // 编译器会向量化
        max_val = std::max(max_val, data[i]);
    }
    
    float range = max_val - min_val;
    if (range == 0) range = 1;
    
    // 归一化
    for (size_t i = 0; i < n; ++i) {
        data[i] = (data[i] - min_val) / range;  // 自动 SIMD
    }
}
```

---

## 3. 内存对齐与缓存优化

### 3.1 对齐控制

```cpp
#include <cstdint>
#include <cstdlib>
#include <new>

// C++11: alignas 关键字
struct alignas(64) CacheLine {
    uint8_t data[64];  // 恰好一个缓存行
};

// 对齐分配
void* aligned_malloc(size_t size, size_t alignment) {
#ifdef _WIN32
    return _aligned_malloc(size, alignment);
#else
    return std::aligned_alloc(alignment, size);
#endif
}

// C++17: aligned_new
struct alignas(std::hardware_destructive_interference_size) PaddedCounter {
    std::atomic<int> value{0};
    char padding[std::hardware_destructive_interference_size - sizeof(std::atomic<int>)];
};
static_assert(sizeof(PaddedCounter) == 64);

// C++17: std::hardware_destructive_interference_size
// 一个缓存行的大小（通常 64 字节）
// 两个对象如果在同一缓存行，导致伪共享
struct alignas(std::hardware_destructive_interference_size) CounterPad {
    std::atomic<int> value;
};
```

### 3.2 缓存局部性优化

```cpp
#include <vector>
#include <chrono>

constexpr int N = 10000;

// ❌ 缓存不友好：按列遍历
void col_major_bad(const std::vector<std::vector<int>>& matrix) {
    long long sum = 0;
    for (int col = 0; col < N; ++col) {
        for (int row = 0; row < N; ++row) {
            sum += matrix[row][col];  // 每步跨一大段内存
        }
    }
}

// ✅ 缓存友好：按行遍历
void row_major_good(const std::vector<std::vector<int>>& matrix) {
    long long sum = 0;
    for (int row = 0; row < N; ++row) {
        for (int col = 0; col < N; ++col) {
            sum += matrix[row][col];  // 连续遍历
        }
    }
}

// 结构体数组 vs 数组结构体
// ❌ AoS: 每个元素包含不同字段，只访问一个字段时浪费带宽
struct ParticleAoS {
    float x, y, z;  // 位置
    float vx, vy, vz;  // 速度
    float mass;
};
std::vector<ParticleAoS> particles(1000000);

// ✅ SoA: 同类数据连续存储
struct ParticlesSoA {
    std::vector<float> x, y, z;
    std::vector<float> vx, vy, vz;
    std::vector<float> mass;
};
// 更新位置时只加载 x/y/z 数组，缓存效率提高 3x
```

### 3.3 小对象优化

```cpp
#include <variant>
#include <string>

// 对比三种方案

// 方案1: union（C 风格）
union Value {
    int i;
    double d;
    const char* s;  // 只能存一个
};

// 方案2: variant（C++17 类型安全 union）
using ValueVariant = std::variant<int, double, std::string>;
// 分配在栈上，大小 = max(各类型大小) + discriminator
// 对小类型无堆分配

// 方案3: 小字符串优化
// std::string 自身已经实现了 SSO（~15 字符内无堆分配）
```

---

## 4. 分支预测优化

### 4.1 likely/unlikely

```cpp
#include <cstdint>

// C++20: [[likely]] / [[unlikely]] 属性
int binary_search(const int* data, size_t size, int target) {
    size_t lo = 0, hi = size;
    
    while (lo < hi) {
        size_t mid = (lo + hi) / 2;
        
        if (data[mid] == target) [[likely]] {
            return mid;  // 命中是常见情况
        } else if (data[mid] < target) [[unlikely]] {
            lo = mid + 1;  // 较小值较少见
        } else {
            hi = mid;
        }
    }
    
    return -1;  // [[unlikely]] 未找到
}

// 异常路径标注
int process_data(int* data, size_t size) {
    if (data == nullptr) [[unlikely]] {
        return -1;  // 很少发生
    }
    
    if (size == 0) [[unlikely]] {
        return 0;  // 边界情况
    }
    
    // 正常路径
    for (size_t i = 0; i < size; ++i) {
        // ...
    }
    return 1;
}
```

### 4.2 分支消除（Branchless Programming）

```cpp
#include <algorithm>
#include <cstdint>

// ❌ 有分支版本
int clamp_branch(int value, int lo, int hi) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

// ✅ 无分支版本（使用条件移动）
int clamp_branchless(int value, int lo, int hi) {
    // 现代编译器会自动优化为 cmov 指令
    return std::min(std::max(value, lo), hi);
}

// ❌ 分支：绝对值
int abs_branch(int x) {
    return x < 0 ? -x : x;
}

// ✅ 无分支：绝对值（使用位运算）
int abs_branchless(int x) {
    int mask = x >> (sizeof(int) * 8 - 1);  // 符号位扩展
    return (x + mask) ^ mask;  // 等同于 (x ^ mask) - mask
}

// 条件赋值
int conditional_branch(bool condition, int a, int b) {
    return condition ? a : b;  // 通常被优化为 cmov
}
```

---

## 5. 分配器优化

### 5.1 PMR 实战

```cpp
#include <memory_resource>
#include <vector>
#include <iostream>
#include <array>

// pmr::monotonic_buffer_resource — 最快的分配器
// 只增不减，一次性释放

void pmr_benchmark() {
    constexpr size_t BUFFER_SIZE = 1 << 20;  // 1MB
    
    // 栈上缓冲（零碎片，无锁）
    std::array<char, BUFFER_SIZE> buffer;
    std::pmr::monotonic_buffer_resource pool{
        buffer.data(), buffer.size(), 
        std::pmr::null_memory_resource()
    };
    
    // 所有分配都在栈上
    std::pmr::vector<int> vec(&pool);
    for (int i = 0; i < 100000; ++i) {
        vec.push_back(i);
    }
    // 零 malloc，零碎片，零 deallocate
}

// pmr::unsynchronized_pool_resource — 批量分配池
// 适合频繁分配/释放不同大小的对象

void pool_resource_demo() {
    std::pmr::unsynchronized_pool_resource pool;
    
    // 从池中分配
    std::pmr::vector<int> vec(&pool);
    vec.reserve(1000);
    // 实际分配由 pool 管理
}

// 选择策略：
// - monotonic_buffer_resource: 一次性生成所有数据后销毁（极快）
// - unsynchronized_pool_resource: 需要重用且单线程
// - synchronized_pool_resource: 多线程版本
```

### 5.2 自定义 arena 分配器

```cpp
#include <cstddef>
#include <cassert>

template<size_t ArenaSize = 1024 * 1024>
class ArenaAllocator {
    char arena_[ArenaSize];
    size_t offset_ = 0;
    
public:
    using value_type = char;
    
    ArenaAllocator() = default;
    
    // 永远不释放单个对象（一次性释放全部）
    void deallocate(void*, size_t) {}
    
    char* allocate(size_t n) {
        // 对齐到 8 字节
        n = (n + 7) & ~7;
        
        if (offset_ + n > ArenaSize)
            throw std::bad_alloc();
        
        char* ptr = arena_ + offset_;
        offset_ += n;
        return ptr;
    }
    
    void reset() { offset_ = 0; }
    
    // 所有 ArenaAllocator 实例不等
    bool operator==(const ArenaAllocator& other) const {
        return &arena_ == &other.arena_;
    }
    bool operator!=(const ArenaAllocator& other) const {
        return !(*this == other);
    }
};

// 使用
template<typename T>
using ArenaVector = std::vector<T, ArenaAllocator<>>;

void arena_demo() {
    ArenaVector<int> vec;
    vec.reserve(100000);  // 全部在栈上
}
```

---

## 6. 诊断工具

### 6.1 Sanitizers

```cmake
# 在 CMake 中启用：
# AddressSanitizer
add_compile_options(-fsanitize=address -fno-omit-frame-pointer)
add_link_options(-fsanitize=address)

# UndefinedBehaviorSanitizer
add_compile_options(-fsanitize=undefined)
add_link_options(-fsanitize=undefined)

# LeakSanitizer（自动包含在 ASan 中）
# ThreadSanitizer（数据竞争检测）
add_compile_options(-fsanitize=thread)
add_link_options(-fsanitize=thread)

# MemorySanitizer（未初始化内存）
add_compile_options(-fsanitize=memory)
```

```cpp
// 检测到的常见问题
void sanitizer_examples() {
    // ASan: 堆缓冲区溢出
    auto* arr = new int[10];
    arr[10] = 42;  // ASan 报错
    
    // UBSan: 未定义行为
    int x = INT32_MIN;
    int y = -x;  // UBSan: 有符号整数溢出
    
    // TSan: 数据竞争
    int shared = 0;
    std::thread t1([&] { shared++; });
    std::thread t2([&] { shared++; });
    t1.join(); t2.join();  // TSan 报竞争
}
```

### 6.2 性能分析

```cpp
#include <chrono>
#include <iostream>

// 简单计时器
struct Timer {
    std::string name_;
    std::chrono::high_resolution_clock::time_point start_;
    
    Timer(const char* name) : name_(name) {
        start_ = std::chrono::high_resolution_clock::now();
    }
    
    ~Timer() {
        auto end = std::chrono::high_resolution_clock::now();
        auto us = std::chrono::duration_cast<std::chrono::microseconds>(end - start_);
        std::cout << name_ << ": " << us.count() << " us\n";
    }
};

#define PROFILE_FUNCTION() Timer timer(__FUNCTION__)

void slow_function() {
    PROFILE_FUNCTION();
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```

---

## 7. 量化性能优化要点

### 7.1 实时行情处理

```cpp
// 1. K 线数据尽量用 SoA
struct BarsSoA {
    std::vector<double> open, high, low, close;
    std::vector<uint64_t> volume;
    std::vector<int64_t> timestamp;
};

// 2. 计算指标时用循环展开
void compute_rsi_unrolled(const double* prices, double* rsi, int n) {
    double gain = 0, loss = 0;
    
    // 初始窗口
    for (int i = 1; i < 14; ++i) {
        double diff = prices[i] - prices[i-1];
        if (diff > 0) gain += diff;
        else loss -= diff;
    }
    rsi[13] = 100 - 100 / (1 + gain / (loss / 14));
    
    // 流式更新
    for (int i = 14; i < n; ++i) {
        gain = (gain * 13 + std::max(0.0, prices[i] - prices[i-1])) / 14;
        loss = (loss * 13 + std::max(0.0, prices[i-1] - prices[i])) / 14;
        rsi[i] = 100 - 100 / (1 + gain / loss);
    }
}
```

### 7.2 对 libkds 的性能增强

```cpp
// 1. 用对齐的内存分配加速
auto* buf = static_cast<Bar*>(std::aligned_alloc(64, n * sizeof(Bar)));

// 2. 使用 PMR 减少策略参数分配
std::pmr::monotonic_buffer_resource param_pool;
std::pmr::vector<StrategyParam> params(&param_pool);

// 3. 编译期策略参数表
consteval auto make_param_table() {
    std::array<StrategyParam, 5> params{{
        {"SMA_FAST", 10},
        {"SMA_SLOW", 30},
        {"BOLL_PERIOD", 20},
        {"RSI_OVERSOLD", 30},
        {"RSI_OVERBOUGHT", 70}
    }};
    return params;
}
constexpr auto PARAM_TABLE = make_param_table();
```

---

## 总结

| 优化方向 | 技术 | 效果 |
|----------|------|------|
| 编译期计算 | consteval/constexpr/查找表 | 消除运行时计算 |
| 向量化 | 自动向量化/SIMD 内置 | 4-8x 吞吐 |
| 缓存优化 | SoA/对齐/Cache Line Padding | 2-10x 内存带宽 |
| 分支优化 | [[likely]]/Branchless | 减少流水线停顿 |
| 分配器 | PMR/Arena | 消除 malloc 开销 |
| 诊断 | Sanitizers/Profiling | 精确定位瓶颈 |
| 并发 | atomic/jthread/memory_order | 正确且高效 |
