# 📘 08 - 内存模型与无锁编程

> 无锁编程 = 在并发访问共享数据时，不用互斥锁(mutex)，而是用原子操作 + 内存序保证正确性。
> 核心：`std::atomic` + `memory_order` + Cache 一致性协议

---

## 1. 为什么需要无锁？

### 问题：锁的代价

```
线程 A 持有锁 → 线程 B 等待 → 内核态上下文切换 (~1μs)
→ 缓存丢失 → 锁争用剧烈时性能断崖下跌
```

无锁的优势：
- 无内核态切换（用户态 CAS 自旋）
- 无死锁/优先级反转
- 更细粒度的并发

---

## 2. std::atomic 全原语

### 基本类型

```cpp
#include <atomic>

std::atomic<int> counter{0};
std::atomic<bool> flag{false};
std::atomic<double> value{3.14};     // C++20: atomic<double> 完全支持
std::atomic<uint64_t> ts{0};         // 64位原子

// 指针
std::atomic<int*> ptr{nullptr};

// 共享指针 (C++20)
std::atomic<std::shared_ptr<int>> sp;  // 无锁实现（平台支持时）
```

### 核心操作

```cpp
std::atomic<int> x{0};

x.store(42);              // 写 = 42
int v = x.load();         // 读 = 42
int old = x.exchange(10); // 交换：x=10, old=42

// CAS (Compare-And-Swap) — 无锁编程核心
int expected = 10;
bool ok = x.compare_exchange_weak(expected, 100);
// 如果 x == expected → x = 100, 返回 true
// 否则 → expected = x, 返回 false

// compare_exchange_strong vs weak
// weak: 可能伪失败（x86 不会，ARM 可能），适用于循环重试
// strong: 保证不伪失败，适合单次尝试

// 算术操作
x.fetch_add(5);   // x += 5, 返回旧值
x.fetch_sub(3);   // x -= 3
x.fetch_or(0xFF);
x.fetch_and(0x00);
```

### atomic_flag — 最简单的自旋锁

```cpp
std::atomic_flag lock{ATOMIC_FLAG_INIT};  // 初始 false

void spin_lock() {
    while (lock.test_and_set(std::memory_order_acquire)) {
        // 忙等
    }
}

void spin_unlock() {
    lock.clear(std::memory_order_release);
}
```

---

## 3. memory_order —— 六种内存序

### 为什么需要内存序？

CPU 和编译器会**重排指令**（为了性能），多核下导致一个核看到的"顺序"和另一个核不同。

```
Thread 1              Thread 2
data = 42;            while (!ready) spin();
ready = true;         print(data);  // 可能不是 42？！
```

内存序告诉编译器和 CPU：**哪些顺序不能乱**。

### 六种内存序

| 排序 | 含义 | 开销 |
|------|------|------|
| `relaxed` | 无顺序保证，仅保证原子性 | 0 |
| `consume` | 数据依赖排序（C++17 不建议用，几乎等同 relaxed） | 0~1 |
| `acquire` | 之后的读写不能被重排到本操作之前 | 1 |
| `release` | 之前的读写不能被重排到本操作之后 | 1 |
| `acq_rel` | acquire + release | 2 |
| `seq_cst` | 全局一致顺序（默认） | 3 |

```
  Thread 1                    Thread 2
  ┌──────────────────┐        ┌──────────────────┐
  │ data = 42        │        │ while (!flag)    │
  │ flag.store(true, │        │   .load(acquire) │
  │   release)       │        │                   │
  └────────┬─────────┘        └────────┬──────────┘
           │                           │
           └───── release-acquire ─────┘
           保证 data=42 对 Thread 2 可见
```

### 完整示例

```cpp
std::atomic<int> flag{0};
int data = 0;

// Thread 1 (生产者)
void producer() {
    data = 42;                      // 1
    flag.store(1, std::memory_order_release);  // 2
    // release: 1 不会被重排到 2 之后
}

// Thread 2 (消费者)
void consumer() {
    while (flag.load(std::memory_order_acquire) != 1) {}  // 3
    // acquire: 3 之后的操作不会被重排到 3 之前
    // 所以一定能看到 data == 42
    assert(data == 42);  // 一定成立
}
```

### relaxed 的用途

```cpp
std::atomic<int> counter{0};

// 多个线程递增计数器——只需要原子性，不需要顺序
void work() {
    counter.fetch_add(1, std::memory_order_relaxed);
}
// 最终 counter 一定是正确的，但每个线程看到的中间值可能不同
```

---

## 4. 自旋锁

```cpp
class SpinLock {
    std::atomic<bool> locked_{false};
public:
    void lock() noexcept {
        while (locked_.exchange(true, std::memory_order_acquire)) {
            // 等待锁释放
            while (locked_.load(std::memory_order_relaxed)) {
                // 让 CPU 暂停（x86 pause 指令）
                __builtin_ia32_pause();
                // MSVC: _mm_pause()
            }
        }
    }

    void unlock() noexcept {
        locked_.store(false, std::memory_order_release);
    }
};
```

### 自旋锁 vs mutex

| 场景 | 自旋锁 | std::mutex |
|------|--------|------------|
| 临界区极短 (<100ns) | ⭐ 最佳 | ❌ 开销太大 |
| 临界区可能阻塞 | ❌ 浪费 CPU | ⭐ 内核级等待 |
| 单核 CPU | ❌ 死锁 (没人释放) | ⭐ 正常工作 |
| 多核竞争激烈 | ❌ 总线风暴 | ⭐ 公平调度 |

---

## 5. 读写锁（共享锁）

```cpp
class RWSpinLock {
    std::atomic<int> readers_{0};  // 读者计数
    std::atomic<bool> writer_{false};
public:
    void lock_read() noexcept {
        while (true) {
            while (writer_.load(std::memory_order_acquire)) {}
            readers_.fetch_add(1, std::memory_order_acquire);
            if (!writer_.load(std::memory_order_acquire)) break;
            readers_.fetch_sub(1, std::memory_order_relaxed);
        }
    }

    void unlock_read() noexcept {
        readers_.fetch_sub(1, std::memory_order_release);
    }

    void lock_write() noexcept {
        bool expected = false;
        while (!writer_.compare_exchange_weak(expected, true,
                std::memory_order_acquire)) {
            expected = false;
        }
        // 等待所有读者完成
        while (readers_.load(std::memory_order_acquire) > 0) {}
    }

    void unlock_write() noexcept {
        writer_.store(false, std::memory_order_release);
    }
};
```

---

## 6. 无锁队列

### 原理：Michael-Scott 队列（链表版）

```cpp
template<typename T>
class LockFreeQueue {
    struct Node {
        T data;
        std::atomic<Node*> next{nullptr};
        Node() = default;
        Node(const T& val) : data(val) {}
    };

    std::atomic<Node*> head_;
    std::atomic<Node*> tail_;
    std::atomic<size_t> size_{0};

public:
    LockFreeQueue() {
        Node* sentinel = new Node();
        head_.store(sentinel, std::memory_order_relaxed);
        tail_.store(sentinel, std::memory_order_relaxed);
    }

    ~LockFreeQueue() {
        while (Node* n = head_.load()) {
            head_.store(n->next.load());
            delete n;
        }
    }

    void push(const T& val) {
        Node* node = new Node(val);
        while (true) {
            Node* tail = tail_.load(std::memory_order_acquire);
            Node* next = tail->next.load(std::memory_order_acquire);
            if (tail == tail_.load(std::memory_order_acquire)) {
                if (next == nullptr) {
                    if (tail->next.compare_exchange_weak(next, node,
                            std::memory_order_release,
                            std::memory_order_relaxed)) {
                        tail_.compare_exchange_strong(tail, node,
                            std::memory_order_release,
                            std::memory_order_relaxed);
                        size_.fetch_add(1, std::memory_order_relaxed);
                        break;
                    }
                } else {
                    // 帮助完成插入
                    tail_.compare_exchange_weak(tail, next,
                        std::memory_order_release,
                        std::memory_order_relaxed);
                }
            }
        }
    }

    bool pop(T& out) {
        while (true) {
            Node* head = head_.load(std::memory_order_acquire);
            Node* tail = tail_.load(std::memory_order_acquire);
            Node* next = head->next.load(std::memory_order_acquire);

            if (head == head_.load(std::memory_order_acquire)) {
                if (head == tail) {
                    if (next == nullptr) return false;  // 空队列
                    // 帮助完成插入
                    tail_.compare_exchange_weak(tail, next,
                        std::memory_order_release,
                        std::memory_order_relaxed);
                } else {
                    out = next->data;
                    if (head_.compare_exchange_weak(head, next,
                            std::memory_order_release,
                            std::memory_order_relaxed)) {
                        delete head;
                        size_.fetch_sub(1, std::memory_order_relaxed);
                        return true;
                    }
                }
            }
        }
    }

    size_t size() const noexcept {
        return size_.load(std::memory_order_relaxed);
    }
};
```

---

## 7. 伪共享 (False Sharing) + Cache Line Padding

### 问题

```
// 两个线程写不同变量，但它们在同一个 cache line 上！
struct Bad {
    int x;  // Thread 1 写
    int y;  // Thread 2 写
};
// x 和 y 在相邻地址 → 同一个 64B cache line
// 每个写操作都会导致另一个线程的 cache line 失效
// 性能 → 比 mutex 还差！
```

### 解决方案：Cache Line Padding

```cpp
#include <cstddef>

// 方法1：alignas
struct alignas(64) Good {
    int x;           // cache line 1
    char pad[60];    // 填充到 64B
    int y;           // cache line 2
};

// 方法2：分离结构体
struct alignas(64) ThreadLocalData {
    int value;
    // 自动填充到 64B
};

// 方法3：最简单的 padding
struct alignas(64) PaddedCounter {
    std::atomic<int64_t> value;
    // 编译器自动 padding 到 64B
};
```

### 性能对比

```
False Sharing (同 cache line):        ~800ms for 10M ops
Cache Line Padded (不同 cache line):  ~120ms for 10M ops
Mutex:                                 ~3000ms for 10M ops
单线程:                                ~50ms for 10M ops
```

---

## 8. 性能对比：mutex vs atomic vs 无锁

```python
# 示意数据（实际测量值）
Benchmark                   Time/op
mutex_increment             85 ns     # 锁争用
atomic_fetch_add           12 ns     # 原子递增
lockfree_queue_push        45 ns     # 无锁队列入队
lockfree_queue_pop         52 ns     # 无锁队列出队
mutex_queue_push+pop      350 ns     # mutex 版
seq_cst_load                5 ns     # 默认序读
relaxed_load                2 ns     # relaxed 读
```

### 选择指南

```
数据只本线程访问？        → 啥都不用
偶尔跨线程共享？           → std::atomic (默认 seq_cst)
高频读、低频写？           → 读写锁 / RCU
高频读写、极短操作？        → 无锁 + relaxed/aquire-release
操作可能阻塞(IO/malloc)？   → std::mutex
代码需要清晰可维护？         → std::mutex (可读性优先)
追求极致性能？              → 无锁 + cache line padding + profiling
```

---

## 9. 🎯 量化系统中的应用场景

### LR/RL 模型共享状态

```
┌──────────────────────────────────────────┐
│          量化系统架构                      │
│                                          │
│  ┌──────────┐    ┌──────────┐            │
│  │ 行情线程  │    │ 信号线程  │            │
│  │ (生产者)  │───→│ (消费者)  │            │
│  └──────────┘    └──────────┘            │
│       │                │                  │
│       ▼                ▼                  │
│  ┌──────────────────────────┐             │
│  │   无锁共享状态 RingBuffer             │
│  │   - 行情快照 (atomic<Snapshot*>)      │
│  │   - 模型权重版本 (atomic<uint64_t>)   │
│  │   - 信号输出 (lockfree queue)         │
│  └──────────────────────────┘             │
└──────────────────────────────────────────┘
```

### 具体场景

**1. 共享模型参数（读多写少）**

```cpp
struct alignas(64) ModelState {
    double weights[256];       // 模型权重
    double bias;               // 偏置
    int64_t version;           // 版本号
    std::atomic<int64_t> seq;  // 序列号——双缓冲切换
};
```

**2. 行情 RingBuffer（SPSC——单生产者单消费者）**

```cpp
template<typename T, size_t N>
struct SPSCRingBuffer {
    alignas(64) std::atomic<size_t> head_{0};
    alignas(64) std::atomic<size_t> tail_{0};
    alignas(64) T data_[N];

    bool push(const T& item) {
        size_t tail = tail_.load(std::memory_order_relaxed);
        size_t next = (tail + 1) % N;
        if (next == head_.load(std::memory_order_acquire))
            return false;  // 满
        data_[tail] = item;
        tail_.store(next, std::memory_order_release);
        return true;
    }

    bool pop(T& item) {
        size_t head = head_.load(std::memory_order_relaxed);
        if (head == tail_.load(std::memory_order_acquire))
            return false;  // 空
        item = data_[head];
        head_.store((head + 1) % N, std::memory_order_release);
        return true;
    }
};
```

**3. 信号聚合（多生产者单消费者）**

- 多个因子计算线程将信号推入无锁队列
- 回测引擎/交易线程消费
- 延迟 ≤ 微秒级

---

## 总结

| 概念 | 一句话 |
|------|--------|
| `std::atomic` | 线程安全的变量读写（无锁原语） |
| `memory_order` | 控制可见性和重排边界 |
| `CAS/cmpxchg` | 无锁编程的"if-then-atomic" |
| 自旋锁 | 极短临界区的轻量锁（用户态） |
| 无锁队列 | Michael-Scott / SPSC RingBuffer |
| False Sharing | 不同线程写同一 cache line → 性能雪崩 |
| Cache Line Padding | `alignas(64)` 隔离线程数据 |
| **量化场景** | SPSC RingBuffer / 双缓冲模型参数 / 无锁信号聚合 |
