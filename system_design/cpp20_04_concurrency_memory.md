# C++20 并发与内存模型深度解析

> jthread、StopToken、Atomic、内存序、无锁编程 — 从基础到实战的全部

---

## 1. `std::jthread` — 可联接线程（C++20）

C++20 引入 `jthread` 解决了 `std::thread` 最大的两个痛点：**必须在析构前显式 join/detach** 和 **缺乏协作式取消机制**。

### 1.1 jthread 自动 join

```cpp
#include <thread>
#include <iostream>

void worker(int id) {
    for (int i = 0; i < 5; ++i) {
        std::cout << "Worker " << id << ": " << i << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

int main() {
    {
        std::jthread jt(worker, 1);
        // jt 析构时自动 join()！
        // 不再需要显式 jt.join() 或处理异常情况
    }
    std::cout << "Thread joined automatically\n";
    
    {
        // 对比旧方式
        std::thread t(worker, 2);
        // 如果这里抛出异常，t.detach() 没执行 → 程序 terminate
        // 必须用 ScopeGuard 或 try/catch
        t.join();
    }
}
```

### 1.2 StopToken — 优雅线程取消

这是 `jthread` 最大的价值——它内置了一个协作式取消机制。

```cpp
#include <thread>
#include <iostream>
#include <chrono>
#include <syncstream>

void cancellable_worker(std::stop_token st) {
    int count = 0;
    while (!st.stop_requested()) {
        // 定期检查是否被请求停止
        std::osyncstream(std::cout) 
            << "Working... iteration " << ++count << "\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    std::osyncstream(std::cout) << "Cancelled gracefully\n";
}

void cancellable_worker_with_callback(std::stop_token st) {
    // 注册停止回调
    auto callback = st.register_callback([] {
        std::osyncstream(std::cout) << "Stop requested! Cleaning up...\n";
    });
    
    while (!st.stop_requested()) {
        // 工作...
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    std::cout << "Exited cleanly\n";
}

int main() {
    {
        std::jthread jt(cancellable_worker);
        std::this_thread::sleep_for(std::chrono::seconds(1));
        jt.request_stop();  // 发送停止请求
        // jt 析构时自动 join，检测到 stop 已请求
    }
    std::cout << "---\n";
    
    {
        std::jthread jt(cancellable_worker_with_callback);
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        jt.request_stop();
    }
}
```

### 1.3 传递外部 stop_source

```cpp
#include <thread>
#include <chrono>
#include <iostream>

void worker_a(std::stop_token st) {
    while (!st.stop_requested()) {
        std::cout << "A working\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void worker_b(std::stop_token st) {
    while (!st.stop_requested()) {
        std::cout << "B working\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(150));
    }
}

int main() {
    // 共享 stop_source：一个信号停止多个线程
    std::stop_source shared_source;
    
    std::jthread jt_a(worker_a, shared_source.get_token());
    std::jthread jt_b(worker_b, shared_source.get_token());
    
    std::this_thread::sleep_for(std::chrono::seconds(1));
    shared_source.request_stop();  // 同时停止 A 和 B
    std::cout << "Both threads stopped\n";
}
```

**适用场景**：后台服务、池化线程、长时间运行的计算任务。

---

## 2. `std::atomic` 与内存序

### 2.1 基本 atomic 操作

```cpp
#include <atomic>
#include <iostream>
#include <thread>
#include <vector>

std::atomic<int> counter{0};

void increment(int n) {
    for (int i = 0; i < n; ++i) {
        counter.fetch_add(1, std::memory_order_relaxed);
    }
}

int main() {
    std::vector<std::jthread> threads;
    for (int i = 0; i < 10; ++i)
        threads.emplace_back(increment, 10000);
    
    // 所有线程自动 join
    std::cout << "Counter: " << counter.load() << "\n";  // 100000
}
```

### 2.2 atomic 支持的类型

```cpp
#include <atomic>
#include <cstdint>

// 内置类型
std::atomic<int> atomic_int;
std::atomic<long long> atomic_ll;
std::atomic<bool> atomic_flag;
std::atomic<double> atomic_double;  // C++20 之前不是所有平台支持

// 指针
struct Data { int x, y; };
std::atomic<Data*> atomic_ptr;

// C++20 新增：std::atomic<std::shared_ptr<T>>
// 允许无锁地读写 shared_ptr
std::atomic<std::shared_ptr<Data>> atomic_shared;

// C++20 新增：atomic_ref — 对非 atomic 对象的原子操作
struct Config {
    int timeout;
    int retries;
};
Config global_config{30, 3};
std::atomic_ref<int> atomic_timeout(global_config.timeout);
// 可以对 atomic_timeout 进行原子操作
// 注意：确保全局 config 的生命周期大于所有访问线程
```

### 2.3 C++20 原子等待与通知

C++20 为 `atomic` 增加了类似条件变量的等待/通知机制，但更轻量：

```cpp
#include <atomic>
#include <thread>
#include <iostream>

std::atomic<int> data{0};

void producer() {
    std::this_thread::sleep_for(std::chrono::seconds(1));
    data.store(42, std::memory_order_release);
    data.notify_one();  // 唤醒等待的线程
}

void consumer() {
    int old = 0;
    data.wait(old);  // 等待 data != old
    std::cout << "Got: " << data.load(std::memory_order_acquire) << "\n";
}

int main() {
    std::jthread p(producer), c(consumer);
}
```

**优势**：相比条件变量，不需要 `mutex`、不需要 `predicate`，不需要 `notify_all`/`notify_one` 判断。

---

## 3. 内存模型与六种内存序

### 3.1 为什么需要内存序

现代 CPU 和编译器会**重排指令**以提高性能，多线程编程中这种重排可能导致不可预期的结果。内存序用来**控制可见性和顺序**。

```cpp
#include <atomic>
#include <thread>
#include <iostream>

// 错误的示例：两个线程同时读写同一变量
void demonstrate_reordering() {
    int x = 0;
    bool ready = false;
    
    std::thread writer([&] {
        x = 42;             // Store 1
        ready = true;       // Store 2
    });
    
    std::thread reader([&] {
        while (!ready);     // Load 1
        std::cout << x;     // Load 2 — 可能看到 0！
    });
    
    writer.join();
    reader.join();
}
```

在没有 atomic 的情况下，编译器可能将 `x = 42` 和 `ready = true` 重排。

### 3.2 六种内存序详解

```cpp
#include <atomic>
#include <thread>
#include <cassert>

std::atomic<int> data{0};
std::atomic<bool> flag{false};

// 1) RELAXED — 只保证原子性，不保证顺序
//    用于计数器、统计等无顺序依赖的场景
void relaxed_example() {
    data.store(42, std::memory_order_relaxed);
    int v = data.load(std::memory_order_relaxed);
    // 不同线程可能看到不同顺序
}

// 2) CONSUME — 已弃用，不要使用（C++17 起建议用 acquire 替代）
//    语义：依赖链上的顺序性

// 3) ACQUIRE — 防止其后的读写重排到此操作之前
//    用于读取操作：确保看到 release 之前的所有写入
void acquire_release_example() {
    // 线程 A
    data.store(42, std::memory_order_release);
    flag.store(true, std::memory_order_release);
    
    // 线程 B
    while (!flag.load(std::memory_order_acquire));
    assert(data.load(std::memory_order_acquire) == 42);  // ✅ 保证
}

// 4) RELEASE — 防止其前的读写重排到此操作之后
//    用于写入操作：确保所有之前的写入对 acquire 的线程可见

// 5) ACQ_REL — acquire + release 的组合
//    用于 RMW 操作（如 fetch_add）
std::atomic<int> counter{0};
void acq_rel_example() {
    int prev = counter.fetch_add(1, std::memory_order_acq_rel);
    // 既获取之前的值，又发布新值
}

// 6) SEQ_CST — 顺序一致性（默认）
//    所有线程看到完全一致的执行顺序，最严格但最慢
std::atomic<int> a{0}, b{0};
int result1, result2;

void seq_cst_example() {
    // 线程 1
    a.store(1, std::memory_order_seq_cst);
    result1 = b.load(std::memory_order_seq_cst);
    
    // 线程 2
    b.store(1, std::memory_order_seq_cst);
    result2 = a.load(std::memory_order_seq_cst);
    
    // 不会出现 result1 == 0 && result2 == 0
}
```

### 3.3 性能对比

```cpp
#include <atomic>
#include <benchmark/benchmark.h>

std::atomic<int> counter{0};

// relaxed 最快
void relaxed_increment() {
    counter.fetch_add(1, std::memory_order_relaxed);
}

// seq_cst 最慢
void seq_cst_increment() {
    counter.fetch_add(1, std::memory_order_seq_cst);
}

// x86 上差异很小（x86 硬件保证强序）
// ARM/PowerPC 上差异可达 5-10x
```

**经验法则：**
- 尽量用默认 `seq_cst`，只在 profiling 证明有瓶颈时才优化
- 99% 的场景 `seq_cst` 足够了
- 需要极致性能时：`relaxed` → `acquire/release` → `seq_cst`

---

## 4. 无锁编程基础

### 4.1 无锁栈

```cpp
#include <atomic>
#include <iostream>

template<typename T>
class LockFreeStack {
    struct Node {
        T data;
        Node* next;
    };
    
    std::atomic<Node*> head_{nullptr};
    
public:
    void push(const T& value) {
        Node* new_node = new Node{value, nullptr};
        Node* old_head = head_.load(std::memory_order_relaxed);
        
        do {
            new_node->next = old_head;
            // CAS：如果 head_ == old_head，就更新为 new_node
        } while (!head_.compare_exchange_weak(
            old_head, new_node,
            std::memory_order_release,
            std::memory_order_relaxed));
    }
    
    bool pop(T& value) {
        Node* old_head = head_.load(std::memory_order_relaxed);
        
        while (old_head && !head_.compare_exchange_weak(
            old_head, old_head->next,
            std::memory_order_acquire,
            std::memory_order_relaxed));
        
        if (!old_head) return false;
        
        value = old_head->data;
        delete old_head;
        return true;
    }
    
    ~LockFreeStack() {
        Node* node = head_.load();
        while (node) {
            Node* next = node->next;
            delete node;
            node = next;
        }
    }
};

int main() {
    LockFreeStack<int> stack;
    stack.push(1);
    stack.push(2);
    stack.push(3);
    
    int value;
    while (stack.pop(value)) {
        std::cout << value << " ";  // 3 2 1
    }
}
```

**注意**：上面的实现有 ABA 问题，生产环境建议使用 hazard pointer 或 RCU（Read-Copy-Update）。

### 4.2 无锁队列

```cpp
#include <atomic>
#include <optional>

template<typename T>
class LockFreeQueue {
    struct Node {
        T data;
        std::atomic<Node*> next{nullptr};
    };
    
    // 哨兵节点：始终有一个空节点在队首
    std::atomic<Node*> head_;
    std::atomic<Node*> tail_;
    
public:
    LockFreeQueue() : head_(new Node{}), tail_(head_.load()) {}
    
    void push(const T& value) {
        Node* new_node = new Node{value, nullptr};
        Node* old_tail;
        
        while (true) {
            old_tail = tail_.load(std::memory_order_acquire);
            Node* next = old_tail->next.load(std::memory_order_acquire);
            
            if (old_tail == tail_.load()) {  // 一致性检查
                if (next == nullptr) {
                    // 尝试链接新节点
                    if (old_tail->next.compare_exchange_weak(
                            next, new_node,
                            std::memory_order_release,
                            std::memory_order_relaxed)) {
                        break;  // 链接成功
                    }
                } else {
                    // 尾指针滞后，帮它前进
                    tail_.compare_exchange_weak(
                        old_tail, next,
                        std::memory_order_release,
                        std::memory_order_relaxed);
                }
            }
        }
        
        // 移动尾指针
        tail_.compare_exchange_strong(
            old_tail, new_node,
            std::memory_order_release,
            std::memory_order_relaxed);
    }
    
    std::optional<T> pop() {
        Node* old_head;
        
        while (true) {
            old_head = head_.load(std::memory_order_acquire);
            Node* tail = tail_.load(std::memory_order_acquire);
            Node* next = old_head->next.load(std::memory_order_acquire);
            
            if (old_head == head_.load()) {
                if (old_head == tail) {
                    if (next == nullptr) return std::nullopt;  // 空队列
                    tail_.compare_exchange_weak(
                        tail, next,
                        std::memory_order_release,
                        std::memory_order_relaxed);
                } else {
                    T value = next->data;
                    if (head_.compare_exchange_weak(
                            old_head, next,
                            std::memory_order_acquire,
                            std::memory_order_relaxed)) {
                        delete old_head;  // 释放旧的哨兵
                        return value;
                    }
                }
            }
        }
    }
};
```

### 4.3 Compare-and-Swap (CAS) 详解

```cpp
#include <atomic>
#include <iostream>

// compare_exchange_weak vs compare_exchange_strong

std::atomic<int> value{0};

void cas_demo() {
    // CAS 的语义：如果 current == expected，设置为 desired；否则 expected = current
    
    int expected = 0;
    
    // weak：允许伪失败（spurious failure），但在循环中效率更高
    // 适用于循环 CAS（ABA 问题在循环中被重试吸收）
    while (!value.compare_exchange_weak(expected, 42)) {
        // expected 已被更新为当前值
        // 在这里检查 expected 决定是否重试
        expected = 0;  // 重置期望值
    }
    
    expected = 0;
    // strong：保证不伪失败
    // 适用于只需要一次尝试的场景
    bool success = value.compare_exchange_strong(expected, 100);
    std::cout << "CAS " << (success ? "succeeded" : "failed") 
              << ", current = " << expected << "\n";
}
```

---

## 5. 互斥原语

### 5.1 C++20 新互斥

```cpp
#include <mutex>
#include <shared_mutex>
#include <iostream>
#include <syncstream>

// C++20 新增：std::counting_semaphore, std::latch, std::barrier

// 信号量
std::counting_semaphore<5> sem{3};  // 最多 3 个并发

void semaphore_worker(int id) {
    sem.acquire();  // 请求许可证（阻塞）
    {
        std::osyncstream(std::cout) << "Worker " << id << " acquired\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
    sem.release();
}

void test_semaphore() {
    std::vector<std::jthread> workers;
    for (int i = 0; i < 10; ++i)
        workers.emplace_back(semaphore_worker, i);
    // 最多 3 个 worker 同时运行
}

// Latch — 一次性的倒计数屏障
void test_latch() {
    std::latch latch{3};  // 必须 3 次 arrive 才能通过
    
    std::jthread t1([&]{ 
        std::this_thread::sleep_for(200ms); 
        latch.arrive_and_wait();  // 到达并等待
        std::cout << "T1 passed\n";
    });
    
    std::jthread t2([&]{ 
        std::this_thread::sleep_for(300ms); 
        latch.arrive_and_wait();
        std::cout << "T2 passed\n";
    });
    
    std::cout << "Main waiting...\n";
    latch.arrive_and_wait();  // 所有 3 个都到达后才能继续
    std::cout << "All passed\n";
}

// Barrier — 可复用的屏障
// C++20 引入 std::barrier
void test_barrier() {
    std::barrier barrier{3};  // 3 个线程同步
    
    std::vector<std::jthread> threads;
    for (int phase = 0; phase < 3; ++phase) {
        threads.clear();
        for (int i = 0; i < 3; ++i) {
            threads.emplace_back([&, i] {
                std::cout << "Phase " << phase << ", worker " << i << " before\n";
                std::this_thread::sleep_for(std::chrono::milliseconds(i * 100));
                barrier.arrive_and_wait();  // 等所有 3 个线程都到达
                std::cout << "Phase " << phase << ", worker " << i << " after\n";
            });
        }
        for (auto& t : threads) t.join();
    }
}
```

### 5.2 锁升级模式

```cpp
#include <shared_mutex>
#include <map>
#include <string>

class ThreadSafeCache {
    mutable std::shared_mutex mtx_;
    std::map<std::string, std::string> cache_;
    
public:
    // 读操作：共享锁
    std::string get(const std::string& key) const {
        std::shared_lock lock(mtx_);
        auto it = cache_.find(key);
        return it != cache_.end() ? it->second : "";
    }
    
    // 写操作：独占锁
    void set(const std::string& key, std::string value) {
        std::unique_lock lock(mtx_);
        cache_[key] = std::move(value);
    }
    
    // 批量更新：事务性保证
    void update_batch(const std::map<std::string, std::string>& updates) {
        std::unique_lock lock(mtx_);
        for (const auto& [key, value] : updates)
            cache_[key] = value;
    }
};
```

---

## 6. 实战：KVStore 并发增强

### 6.1 多线程安全 KVStore 设计

```cpp
#include <shared_mutex>
#include <map>
#include <span>
#include <vector>
#include <optional>

class ConcurrentKVStore {
    mutable std::shared_mutex mtx_;
    std::map<std::string, std::vector<std::byte>> store_;
    
public:
    // 读操作
    std::optional<std::span<const std::byte>> get(std::string_view key) const {
        std::shared_lock lock(mtx_);
        auto it = store_.find(std::string(key));
        if (it == store_.end()) return std::nullopt;
        return std::span<const std::byte>(it->second);
    }
    
    // 写操作
    void put(std::string_view key, std::span<const std::byte> value) {
        std::unique_lock lock(mtx_);
        store_[std::string(key)] = {value.begin(), value.end()};
    }
    
    // 批量读（快照一致性）
    std::vector<std::pair<std::string, std::vector<std::byte>>> 
    get_many(std::span<const std::string> keys) const {
        std::shared_lock lock(mtx_);
        std::vector<std::pair<std::string, std::vector<std::byte>>> result;
        for (const auto& key : keys) {
            auto it = store_.find(key);
            if (it != store_.end())
                result.emplace_back(it->first, it->second);
        }
        return result;
    }
    
    // 原子更新（CAS 语义）
    bool compare_and_swap(std::string_view key, 
                          std::span<const std::byte> expected,
                          std::span<const std::byte> desired) {
        std::unique_lock lock(mtx_);
        auto it = store_.find(std::string(key));
        if (it == store_.end()) return false;
        
        if (it->second.size() != expected.size()) return false;
        if (memcmp(it->second.data(), expected.data(), expected.size()) != 0) 
            return false;
        
        it->second.assign(desired.begin(), desired.end());
        return true;
    }
    
    // 写后快照
    std::map<std::string, std::vector<std::byte>> snapshot() const {
        std::shared_lock lock(mtx_);
        return store_;  // 深拷贝快照
    }
};
```

### 6.2 使用 jthread 的后台管理器

```cpp
#include <thread>
#include <functional>
#include <queue>
#include <condition_variable>

class BackgroundTaskManager {
    std::vector<std::jthread> workers_;
    std::queue<std::function<void()>> tasks_;
    std::mutex mtx_;
    std::condition_variable cv_;
    
public:
    explicit BackgroundTaskManager(size_t count = 4) {
        for (size_t i = 0; i < count; ++i) {
            workers_.emplace_back([this](std::stop_token st) {
                while (!st.stop_requested()) {
                    std::function<void()> task;
                    {
                        std::unique_lock lock(mtx_);
                        cv_.wait(lock, [&] { 
                            return st.stop_requested() || !tasks_.empty();
                        });
                        if (st.stop_requested()) return;
                        task = std::move(tasks_.front());
                        tasks_.pop();
                    }
                    task();  // 执行任务
                }
            });
        }
    }
    
    void enqueue(std::function<void()> task) {
        std::unique_lock lock(mtx_);
        tasks_.push(std::move(task));
        cv_.notify_one();
    }
    
    void stop() {
        for (auto& w : workers_)
            w.request_stop();
        cv_.notify_all();  // 唤醒所有等待中的线程
    }
};
```

---

## 7. 性能注意事项

### 7.1 伪共享（False Sharing）

```cpp
#include <atomic>
#include <thread>

struct alignas(64) PaddedCounter {  // 64 字节对齐 = 通常的缓存行大小
    std::atomic<int> value{0};
    char padding[60];  // 填充到完整缓存行
};

void false_sharing_demo() {
    // ❌ 伪共享：两个 counter 在同一缓存行，每次更新都导致缓存行震荡
    std::atomic<int> bad_a{0}, bad_b{0};
    
    // ✅ 正确：各自独立缓存行
    PaddedCounter good_a, good_b;
    
    std::jthread t1([&] { for (int i = 0; i < 10000000; ++i) bad_a++; });
    std::jthread t2([&] { for (int i = 0; i < 10000000; ++i) bad_b++; });
}
```

**经验法则：**
- `alignas(std::hardware_destructive_interference_size)` 避免伪共享
- `alignas(std::hardware_constructive_interference_size)` 促进共享

### 7.2 锁 vs 无锁 vs 线程局部

```cpp
// 场景：每个线程自己的计数器，最后合并
// ✅ 最佳方案：thread_local

struct ThreadLocalCounter {
    static int get_and_increment() {
        thread_local int counter = 0;
        return counter++;
    }
};

// 不需要锁，不需要 atomic，不需担心伪共享
```

| 方案 | 延迟 | 吞吐量 | 适用场景 |
|------|------|--------|----------|
| `thread_local` | 0 同步开销 | 最高 | 线程独立数据 |
| `atomic relaxed` | ~2-5 ns x86 | 高 | 简单计数器 |
| 无锁 CAS | ~10-20 ns | 高 | 高竞争 CAS |
| 有锁 mutex | ~25-100 ns | 中 | 复杂操作/公平性 |
| `shared_mutex` 读 | ~10-30 ns | 高（读多） | 读远多于写 |

### 7.3 C++20 并发编程建议

```cpp
// 1) 默认使用 jthread
std::jthread t([](std::stop_token st) {
    while (!st.stop_requested()) { /* work */ }
});

// 2) 用 atomic wait 替代条件变量（更轻量）
std::atomic<int> state{0};
// 等待：
state.wait(0);
// 唤醒：
state.store(1);
state.notify_one();

// 3) 用 std::latch/barrier 替代手写同步
std::latch sync_point{3};

// 4) 用 syncstream 替代 cout 加锁
std::osyncstream(std::cout) << "Thread-safe output\n";

// 5) 内存序经验法则：先写 seq_cst，profile 后优化
```

---

## 总结

| 特性 | C++ 版本 | 用途 | 推荐 |
|------|----------|------|------|
| `jthread` | C++20 | 自动 join + 取消机制 | ⭐⭐⭐⭐⭐ |
| `stop_token` | C++20 | 优雅线程停止 | ⭐⭐⭐⭐⭐ |
| Atomic 等待 | C++20 | 轻量同步 | ⭐⭐⭐⭐ |
| `osyncstream` | C++20 | 线程安全输出 | ⭐⭐⭐ |
| `latch`/`barrier` | C++20 | 多线程同步 | ⭐⭐⭐⭐ |
| `shared_mutex` | C++17 | 读写锁 | ⭐⭐⭐⭐⭐ |
| atomic CAS | C++11+ | 无锁编程 | ⭐⭐⭐⭐ |
| `thread_local` | C++11 | 线程独立数据 | ⭐⭐⭐⭐⭐ |
