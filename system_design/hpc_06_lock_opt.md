# 性能优化 #6：锁优化与并发

> 2026-05-17
> 前置：异步 I/O #5

## 1. 锁的代价

### 1.1 无锁 vs 有锁

```python
# ❌ 有锁版本
import threading

lock = threading.Lock()
shared_counter = 0

def worker():
    global shared_counter
    for _ in range(1000000):
        with lock:
            shared_counter += 1

# ✅ 无锁版本
import threading

shared_counter = threading.AtomicInteger(0)  # 需要 c++11 atomic

# Python 压根没有线程安全的原子整数——GIL 让它"看似"安全
# 但在 C/Rust 中区别很大：
#   有锁：1000 万次累加 ≈ 500ms
#   无锁：1000 万次累加 ≈ 50ms
```

### 1.2 锁竞争的成本

```
单线程：    1 次累加 = 1ns
无锁多线程： 1 次累加 = 5-10ns（原子操作 CAS）
有锁多线程： 1 次累加 = 50-300ns（含锁争抢/上下文切换）
```

当锁争抢真正发生时，线程可能被 OS 挂起——一个 lock 操作可能花费 10μs+。

## 2. 锁优化策略

### 2.1 减少锁持有时间

```python
# ❌ 长时间持锁
def process_trades(trades):
    with db_lock:
        new_trades = validate_trades(trades)  # 验证（计算密集）
        save_to_db(new_trades)                 # I/O
        notify_listeners(new_trades)           # 通知

# ✅ 缩短锁持有时间
def process_trades(trades):
    new_trades = validate_trades(trades)       # 无锁计算
    with db_lock:
        save_to_db(new_trades)                  # 只锁关键部分
    notify_listeners(new_trades)                # 无锁发送
```

### 2.2 读-写锁

当读远多于写时使用：

```cpp
#include <shared_mutex>

// 读多写少的策略参数表
class StrategyRegistry {
    std::shared_mutex rw_mutex_;
    std::unordered_map<std::string, StrategyParams> params_;
    
    const StrategyParams& get(const std::string& name) {
        std::shared_lock lock(rw_mutex_);  // 多个读者共享
        return params_[name];
    }
    
    void set(const std::string& name, const StrategyParams& p) {
        std::unique_lock lock(rw_mutex_);  // 写者独占
        params_[name] = p;
    }
};
```

效果：10 个读者并发 → 接近 10x 加速（写者遇到等待概率低）

### 2.3 无锁数据结构

```rust
use std::sync::atomic::{AtomicU64, Ordering};

// 无锁计数器
let counter = AtomicU64::new(0);
counter.fetch_add(1, Ordering::Relaxed);  // CAS 循环，无锁

// 无锁链表（简单实现，实际用 crossbeam 库）
//   适用：线程安全的生产者-消费者队列
//   不适用：复杂的数据结构（红黑树等）
```

**Rust 的无锁编程**：`crossbeam` 库提供了无锁队列和 `Arc` 的优化版本。

### 2.4 分槽（Sharding）

本质是多把锁分担争抢：

```python
class ShardedCounter:
    """分槽计数器（减少锁争抢）"""
    def __init__(self, n_shards=64):
        self.shards = [threading.Lock() for _ in range(n_shards)]
        self.values = [0] * n_shards
    
    def increment(self, key_hash: int):
        shard_id = key_hash % len(self.shards)
        with self.shards[shard_id]:
            self.values[shard_id] += 1
    
    def total(self) -> int:
        return sum(self.values)
```

64 个锁 vs 1 个锁 → 争抢概率降低到 1/64。

## 3. 量化引擎中的并发模型

### 3.1 当前架构的并发瓶颈

```
量化引擎 VS 多线程

信号计算：
  多个策略可以并行（无依赖）
  ⚠️ 但共享行情数据 → 需要锁保护

I/O 操作：
  日志写入 → 可能被锁
  行情接收 → 共享缓冲区

交易执行：
  防止重复下单 → 需要锁
```

### 3.2 工作线程模型

```
行情接收线程 → (无锁环形缓冲区) → 信号计算线程池
                                      ↓
                                 策略决策
                                      ↓
                                 交易执行线程

用无锁队列解耦各阶段：
  1. 行情接收线程只写 ring buffer（无锁）
  2. 信号计算线程批量读取（无锁）
  3. 交易执行上锁（低频，争抢少）
```

无锁环形缓冲区：

```python
class LockFreeRingBuffer:
    """单生产者-单消费者无锁环形缓冲区"""
    def __init__(self, capacity: int):
        self.buffer = [None] * capacity
        self.capacity = capacity
        self.head = 0  # 写位置
        self.tail = 0  # 读位置
    
    def push(self, item) -> bool:
        next_head = (self.head + 1) % self.capacity
        if next_head == self.tail:  # buffer 满
            return False
        self.buffer[self.head] = item
        self.head = next_head  # 先写再移 head（可见性保证）
        return True
    
    def pop(self):  # 返回 item 或 None
        if self.tail == self.head:  # buffer 空
            return None
        item = self.buffer[self.tail]
        self.tail = (self.tail + 1) % self.capacity
        return item
```

单生产者-单消费者场景下完全无锁（Rust 的原子操作）。

## 4. Python 中特殊的 "锁" 问题

### 4.1 GIL 的悖论

Python 的 GIL 让多线程对 CPU 密集型任务反而更慢：

```python
# CPython 的 GIL 保证：
#   任何时候只有一个线程在执行 Python 字节码

# 多线程 CPU 密集型（GIL 导致串行化 → 甚至更慢）
t1 = Thread(target=compute_signals, args=(data,))
t2 = Thread(target=compute_signals, args=(data,))
t1.start(); t2.start()
# t1 + t2 时间 ≈ 2x 单线程（GIL 切换开销）

# 多进程 CPU 密集型（真正并行）
from multiprocessing import Process
p1 = Process(target=compute_signals, args=(data,))
p2 = Process(target=compute_signals, args=(data,))
p1.start(); p2.start()
# p1 + p2 时间 ≈ 1x（多核真正并行）
```

### 4.2 GIL 的释放点

当 Python 执行 C 扩展（numpy 操作、I/O、sleep）时会释放 GIL：

```python
# ❌ 纯 Python loop（GIL 一直持有）
for i in range(1000000):
    total += i  # 全程持有 GIL，其他线程不能并行

# ✅ numpy 操作（释放 GIL，底层 C 并行）
result = np.sum(data)  # numpy 运行时不持有 GIL

# 在 thread/process 选择策略：
#   numpy/scipy 为主 → 多线程（GIL 自动释放，共享内存无拷贝开销）
#   Python 循环为主 → 多进程（需要显式共享数据）
```

### 4.3 asyncio 与锁

asyncio 的锁和 threading 的锁不同——它只在同一个线程内协调协程：

```python
import asyncio

lock = asyncio.Lock()

async def worker(name):
    async with lock:    # 不会阻塞 EventLoop，只阻塞其他协程
        await do_io()
        await do_cpu_bound()  # 这行不会 release GIL（Python loop 继续持有）
```

## 5. 量化引擎的锁策略

```
行情数据：
  读取频率极高 → 无锁（只用最新值，不关心精确时序的锁）
  用内存屏障保证可见性

策略参数：
  读极高，写极低 → 读写锁 / Arc<RwLock>

交易日志：
  追加写入，极少读取 → 无锁环形缓冲区
  批量写入数据库

策略同步：
  尽量避免 → 解耦为独立工作单元
  需要共享数据 → 消息传递 > 共享内存
```

## 总结

```
锁的代价：50ns(无锁CAS) vs 300ns+(有锁争抢) × 高频

优化策略：
  减少持有时间 → 只锁关键路径
  读写锁分离 → 读者不阻塞
  分槽(Sharding) → 分散争抢
  无锁数据结构 → CAS + RingBuffer

Python 特殊性：
  GIL 使 CPU 密集型多线程无效 → 用多进程
  numpy 释放 GIL → 操作数据时多线程可用
  asyncio 锁只协调协程，不跨线程

量化引擎的最佳模型：
  数据 → 无锁 RingBuffer → 工作线程(多进程)
  → 独立策略执行 → 结果聚合(最后一个环节上锁)
```
