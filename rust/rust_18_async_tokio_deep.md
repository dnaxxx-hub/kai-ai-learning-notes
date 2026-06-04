# Rust 异步运行时深入：Tokio 内部机制

## 1. Tokio 架构全景

### 1.1 四大核心组件

```
┌─────────────────────────────────────────────┐
│                  Tokio Runtime               │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Scheduler │  │ I/O Driver│  │ Timer Driver│  │
│  │ (work-steal)│  │(epoll/kq)│  │(timing wheel)│  │
│  └─────┬────┘  └────┬─────┘  └─────┬─────┘  │
│        └────────────┼──────────────┘         │
│              ┌──────┴──────┐                 │
│              │  Async Prims│                 │
│              │(chan/mutex/ │                 │
│              │ barrier/... )│                 │
│              └─────────────┘                 │
└─────────────────────────────────────────────┘
```

### 1.2 与 OS 线程的关系

```
OS Thread 1 ── Worker 1 ── Local Queue (256 环形缓冲)
OS Thread 2 ── Worker 2 ── Local Queue
OS Thread 3 ── Worker 3 ── Local Queue
                     │
             Global Injection Queue (MPSC 链表)
```

- **M:N 模型**：M 个异步任务映射到 N 个 OS 线程
- Tokio 任务 ≈ 几百字节（vs OS 线程数 MB 栈空间）
- 一个 worker 线程可管理**数十万**个任务

---

## 2. 工作窃取调度器（Work-Stealing Scheduler）

### 2.1 核心数据结构

```
struct LocalQueue {
    head: AtomicU32,          // 多线程读取
    tail: UnsafeCell<u32>,    // 仅生产者线程写入
    mask: usize,              // buffer 大小掩码
    buffer: Box<[MaybeUninit<Task>]>,  // 256 项固定大小
}

struct GlobalQueue {
    head: UnsafeCell<Pointer>, // 加锁
    tail: UnsafeCell<Pointer>, // 加锁
}
```

### 2.2 Push 操作（低同步）

```rust
// push 到本地队列（只有当前 worker 调用）
fn push(&self, task: Task) {
    let head = self.head.load(Acquire);
    let tail = unsafe { self.tail.unsync_load() };

    if tail - head < 256 {
        // 快速路径：只需 store
        let idx = tail & mask;
        buffer[idx].write(task);
        self.tail.store(tail + 1, Release);
        return;
    }
    // 慢速路径：搬一半到全局队列
    self.push_overflow(task, head, tail, &global_queue);
}
```

**关键优化**：快速路径只有 **两个原子操作**（load + store），无 read-modify-write。

### 2.3 Pop 操作（本地 worker）

```rust
fn pop(&self) -> Option<Task> {
    let head = self.head.load(Acquire);
    let tail = unsafe { self.tail.unsync_load() };

    if head == tail { return None; }

    let idx = head & mask;
    let task = buffer[idx].read();

    // CAS 竞争获取
    if self.head.compare_and_swap(head, head + 1, Release) == head {
        Some(task.assume_init())
    } else {
        // 被 steal 走了，重试
        self.pop()
    }
}
```

### 2.4 Steal 操作

- 随机选一个 victim worker
- 一次性 steal **一半** 任务（减少后续 steal 频率）
- 只 steal 一次，找不到就尝试下一个 worker

### 2.5 Next-Task 优化

关键优化：**"next-task" 槽位**

```
Worker 处理流程：
1. 检查 next-task 槽位 → 有则直接执行
2. 检查本地队列 head
3. 检查全局队列
4. 尝试从其他 worker steal
5. 休眠等待通知
```

当一个任务唤醒另一个任务（如 channel send → receiver），直接放入 next-task 槽：
- 减少延迟（receiver 立刻执行）
- 利用 CPU 缓存（message 数据仍在缓存中）

### 2.6 搜索状态限流

```rust
struct Scheduler {
    num_searching: AtomicU32,
    // 限制最大搜索线程 = num_workers / 2
}
```

- 只有 `num_searching < limit` 时才通知其他 worker
- 一个 worker 找到任务后递减 `num_searching` 并通知下一个
- **平滑启动**：batch 任务到达时，worker 按需一个个唤醒

---

## 3. I/O Driver（事件驱动引擎）

### 3.1 跨平台抽象层

| 平台 | 系统调用 | Tokio 封装 |
|------|----------|------------|
| Linux | epoll | mio::Poll |
| macOS | kqueue | mio::Poll |
| Windows | IOCP | mio::Poll |
| wasm | — | 需 poll 驱动 |

### 3.2 异步读写的完整流程

```
1. socket.read(&mut buf).await
2. Future::poll() → 尝试非阻塞 read()
3. 数据未就绪 → 在 I/O driver 注册 interest
                 → 存储 Waker
                 → 返回 Poll::Pending
4. Worker 切换到下一个任务
5. epoll_wait 返回 → 数据已到达
6. I/O driver 通过 Waker 唤醒等待的任务
7. 任务放入 run queue
8. Worker 重新 poll → 此时 read 成功
```

### 3.3 mio 的注册机制

```rust
struct IoDriver {
    registry: mio::Registry,
    // 存储 interest 和 waker 的映射
    inner: Mutex<HashMap<RawFd, Registration>>,
}

impl IoDriver {
    fn register(&self, fd: RawFd, waker: Waker, interest: Interest) {
        let mut inner = self.inner.lock();
        inner.entry(fd).or_insert(Registration {
            waker, interest,
        });
        self.registry.register(&mut source, token, interest, opts);
    }
}
```

---

## 4. Timer Driver（定时器系统）

### 4.1 分层时间轮（Hierarchical Timing Wheel）

```
Level 0: 1ms 精度, 64 槽 (0-63ms)
Level 1: 64ms 精度, 64 槽 (64ms - 4s)
Level 2: 4s  精度, 64 槽 (4s - 256s)
Level 3: 256s 精度, 64 槽
```

- **O(1)** 插入和删除
- 定时器精度 1ms
- 按需推进，与 I/O driver 共享同一个事件循环

### 4.2 sleep 实现

```rust
pub fn sleep(duration: Duration) -> Sleep {
    Sleep { deadline: Instant::now() + duration }
}

impl Future for Sleep {
    fn poll(self: Pin<&mut Self>, cx: &Context) -> Poll<()> {
        if Instant::now() >= self.deadline {
            Poll::Ready(())
        } else {
            // 注册到 timer wheel
            timer.register(self.deadline, cx.waker());
            Poll::Pending
        }
    }
}
```

---

## 5. 异步原语

### 5.1 Channels 类型对比

| 类型 | 语义 | 用途 |
|------|------|------|
| `oneshot` | 1 producer → 1 receiver，仅发送1次 | 任务间传递结果 |
| `mpsc` | 多 producer → 1 receiver，bounded | 数据流、任务分发 |
| `broadcast` | 多 producer → 多 receiver | 广播通知 |
| `watch` | 1 producer → 多 receiver，保留最新值 | 配置更新监控 |

### 5.2 JoinSet — 结构化并发

```rust
let mut set = JoinSet::new();

for url in urls {
    set.spawn(async { fetch(url).await });
}

// 逐项收集结果
while let Some(res) = set.join_next().await {
    // 进程结果
}

// drop JoinSet 时自动取消所有未完成任务
```

### 5.3 spawn_blocking

用于无法异步化的**阻塞操作**（文件 I/O、同步数据库查询、CPU 密集计算）：

```rust
let result = tokio::task::spawn_blocking(|| {
    std::fs::read_to_string("large_file.txt")
}).await;
```

内部维护独立的**阻塞线程池**（默认 512 线程上限），不会影响异步 worker。

---

## 6. Future 和 Waker 的零成本设计

### 6.1 Future 状态机

`async fn` 被编译器编译为**状态机枚举**：

```rust
// async { /* code */ } 编译为：
enum MyFuture {
    State0 { val: i32 },
    State1 { fut: SomeInnerFuture },
    Done,
}
```

这种方法**不分配堆内存**、**无动态分发表**。

### 6.2 Waker 结构

```
Waker (2 指针宽) = RawWaker = { data: *const (), vtable: *const RawWakerVTable }

RawWakerVTable {
    clone:   fn(*const ()) -> RawWaker,
    wake:    fn(*const ()),
    wake_by_ref: fn(*const ()),
    drop:    fn(*const ()),
}
```

**wake() vs wake_by_ref() 的关键区别：**

```rust
// wake(self) — 消耗 Waker，零原子增量
fn wake(self) {
    // 直接把 Waker 内部的任务指针放入 run queue
    // 不需要 Arc::clone（原子增）
}

// wake_by_ref(&self) — 不消耗，需要 Arc::clone
fn wake_by_ref(&self) {
    let task = self.task.clone(); // 原子增
    self.scheduler.schedule(task);
}
```

Tokio 通过维护一个**任务活跃列表**来避免 `wake_by_ref` 的原子增开销。

---

## 7. 性能优化汇总

| 优化 | 效果 |
|------|------|
| 固定大小本地队列 + 全局溢出 | 避免 Chase-Lev deque 的 epoch 回收 |
| Acquire/Release 而非 SeqCst | x86 上零额外的 CPU 同步 |
| 搜索状态限流 | 减少 thundering herd |
| next-task 槽位 | 减少消息传递延迟 ~50% |
| 单次分配 Task | 减少 50% 分配（之前需分配两次） |
| 0 原子增 wake | 减少 2 个 atomic ops 每 wake |

**实验结果**（从 v0.1 到 v0.2）：
```
chained_spawn:  2,019,796 ns → 168,854 ns  (12x)
ping_pong:      1,279,948 ns → 562,659 ns  (2.3x)
spawn_many:    10,283,608 ns → 7,320,737 ns (1.4x)
```

**Hyper 基准**："hello world" HTTP 服务器：
- 旧调度器：~114K req/s
- 新调度器：~153K req/s（**+34%**）

---

## 8. Loom — 并发测试工具

Loom 使用**动态偏序归约**来系统性地探索所有可能的并发执行路径：

```rust
loom::model(|| {
    let pool = ThreadPool::new();
    // ... 并发操作 ...
});
```

对每个原子操作，尝试 C11 内存模型下的所有**合法重排序**。捕获了 **10+ 个 bug** 在调度器开发过程中。

---

## 9. 实战注意事项

1. **永远不要阻塞 worker 线程** — 会冻结整个 runtime
2. **CPU 密集任务使用 `spawn_blocking`**
3. **被动的文件 I/O** 也属于阻塞操作（Linux AIO 除外）
4. **tokio-console** 用于诊断：`task states, poll times, waker counts`
5. **Benchmark 时使用 `#[tokio::test]`** 而非 `#[test]`

### 选择合适的 Runtime

| 场景 | 推荐 |
|------|------|
| 高性能 web 服务 | `multi_thread`, worker = num_cpus |
| CLI 工具 | `current_thread` |
| 嵌入式 | embassy |
| 简单 HTTP 请求 | `reqwest::blocking` |
