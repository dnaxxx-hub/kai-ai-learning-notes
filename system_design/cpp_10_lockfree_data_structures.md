# 锁无关数据结构：无锁编程深入

## 1. 基础理论

### 1.1 乐观同步 vs 悲观同步

```
悲观锁（Mutex）:
线程 A: lock → 访问 → unlock
线程 B:         wait → lock → 访问 → unlock
                   ↑ 上下文切换/休眠浪费

乐观锁（CAS循环）:
线程 A:           CAS(cmp, new) → 成功 → 访问
线程 B:   CAS(cmp, new) → 失败 → 重试
                   ↑ 忙等待（低延迟场景更好）
```

### 1.2 三种无锁等级

| 等级 | 描述 | 保证 | 复杂度 |
|------|------|------|--------|
| **Obstruction-Free** | 单个线程执行时保证完成 | 最弱 | 低 |
| **Lock-Free** | 至少一个线程始终推进 | 系统级别 | 中 |
| **Wait-Free** | 每个线程有限步骤内完成 | 最强 | 极高 |

### 1.3 核心硬件原语

```c
// x86 上的 CAS（compare-and-swap）
bool __sync_bool_compare_and_swap(
    type* ptr, type oldval, type newval
);

// x86 上的 FAA（fetch-and-add）
type __sync_fetch_and_add(type* ptr, type val);

// ARM 上的 LL/SC
loop:
    ldrex rd, [addr]       // load-linked
    // ... 检查/修改 ...
    strex status, val, [addr] // store-conditional
    cmp status, 0
    bne loop              // 失败重试
```

---

## 2. 内存序与原子操作

### 2.1 C11/C++11 内存模型

| 内存序 | 保证 | 开销 |
|--------|------|------|
| `memory_order_relaxed` | 仅保证原子性 | 0 |
| `memory_order_consume` | 数据依赖有序（已弃用） | 低 |
| `memory_order_acquire` | 读操作后的所有访问不重排 | 中 |
| `memory_order_release` | 写操作前的所有访问不重排 | 中 |
| `memory_order_acq_rel` | acquire + release | 中 |
| `memory_order_seq_cst` | 全局单序 | 高 |

### 2.2 ABA 问题

核心问题：CAS 比较的值从 A → B → A，但 CAS 认为没变。

```c
// ABA 示例
Thread 1: 读取 head = NodeA (addr 0x1000)
Thread 2: pop NodeA
Thread 2: free(NodeA)
Thread 2: alloc → 得到 NodeX (恰好也在 0x1000)
Thread 2: push NodeX
Thread 1: CAS(head, NodeA, NodeA->next)  // 成功！但 head 已不是 NodeA
```

**解决方案：**
1. **标签计数器**（tagged pointer）：指针+ABA计数
2. **Hazard Pointer**：延迟回收（见下文）
3. **RCU**：再引用保护

### 2.3 伪共享（False Sharing）

```
CPU Core 0 写变量 A     CPU Core 1 写变量 B
         │                       │
         └────────┬──────────────┘
                  ↓
            同一缓存行 (64 bytes)
                  ↓
           缓存一致性协议触发
           整行标记为 dirty
           两个 core 都必须失效
```

**解法：** 使用 `alignas(64)` 隔离热点变量。

---

## 3. 关键无锁数据结构

### 3.1 无锁栈（Treiber Stack）

最简单的无锁数据结构：

```c
struct Node {
    void* data;
    struct Node* next;
};

struct Stack {
    struct Node* head;  // 使用 CAS 原子操作
};

void push(struct Stack* s, struct Node* n) {
    do {
        n->next = s->head;
    } while (!CAS(&s->head, n->next, n));
}

struct Node* pop(struct Stack* s) {
    struct Node* n;
    do {
        n = s->head;
        if (n == NULL) return NULL;
    } while (!CAS(&s->head, n, n->next));
    return n;
}
```

**问题：** ABA 问题 + 内存回收。

### 3.2 无锁队列（Michael-Scott Queue）

```c
struct Queue {
    struct Node* head;    // 消费者端
    struct Node* tail;    // 生产者端
};

// 入队（尾插）
void enqueue(struct Queue* q, struct Node* n) {
    n->next = NULL;
    while (1) {
        struct Node* tail = q->tail;
        struct Node* next = tail->next;
        if (tail != q->tail) continue;  // stale

        if (next != NULL) {
            // 尾指针滞后，帮助推进
            CAS(&q->tail, tail, next);
        } else {
            if (CAS(&tail->next, NULL, n)) {
                CAS(&q->tail, tail, n);  // 推进尾指针
                return;
            }
        }
    }
}
```

### 3.3 读-拷贝-更新（RCU）

**原理：** 读取无需锁，更新时复制一份再替换指针。

```
读路径：
reader: ptr = rcu_ptr;  // 原子读
reader: 通过 ptr 访问数据
reader: rcu_read_unlock();  // 退出临界区

更新路径：
writer: 分配新数据 new_data
writer: 将 old_data 复制到 new_data 并修改
writer: rcu_assign_pointer(rcu_ptr, new_data)  // 发布新指针
writer: synchronize_rcu()  // 等待所有在读取的 reader 完成
writer: free(old_data)     // 安全删除
```

**RCU 核心思想：**
- 读路径无锁、无原子操作（RCU 禁用抢占即可）
- 写路径有锁
- 通过"宽限期"（所有 reader 都退出临界区后）才释放旧数据

**适用场景：** 读多写远远少的数据结构（路由表、配置、安全策略）。

### 3.4 Hazard Pointer（危险指针）

一种内存回收协议，用于解决 ABA 问题：

```c
#define MAX_THREADS 64
#define HP_RETIRED_LIMIT 256

struct HazardPointer {
    std::atomic<void*> hp[MAX_THREADS];
};

// 线程 x 保护地址 p
void* hp_protect(struct HazardPointer* hp_table,
                 int thread_id, void* p) {
    hp_table->hp[thread_id].store(p, relaxed);
    // 需要 memory-barrier
    return p;
}

// 尝试回收
void hp_retire(struct HazardPointer* hp_table, void* ptr) {
    // 检查所有线程的 hazard pointer
    // 如果没有线程保护此地址，可以 free
    // 否则加入退役列表稍后再试
}
```

**Facebook Folly 中的 Hazptr：**
- `hazptr_obj_base`：需要管理回收的基类
- `hazptr_holder`：线程局部保护者
- `hazptr_domain`：跨线程管理退役对象

---

## 4. 无锁数据结构工程实践

### 4.1 常见陷阱

| 陷阱 | 现象 | 修复 |
|------|------|------|
| ABA | 逻辑错误 | tagged pointer |
| 内存回收 | use-after-free | RCU/HazardPtr/epoch |
| 伪共享 | 性能下降 10x | cache line padding |
| seq_cst 滥用 | 性能下降 5x | 使用 acquire/release |
| double-CAS | CPU 不支持 | 需要特殊指令 |

### 4.2 测试与验证

```c
// 1. 压力测试：多线程长时间运行
void stress_test() {
    const int THREADS = 8;
    const int OPS = 10000000;
    // 同时运行 push/pop，验证最终状态
}

// 2. 系统化测试：使用 CDSChecker / Loom
// 穷举所有可能的时间交错

// 3. 模拟弱内存序
// 使用 genmc / herd 工具
```

### 4.3 何时用无锁

**适合：**
- 高频交易系统
- 实时音视频处理
- 内核、驱动
- 对延迟一致性要求高的场景

**不适合：**
- 临界区较大（锁竞争开销相对小）
- 复杂数据结构（设计难度剧增）
- 读少写多
- 调试成本 > 性能收益

### 4.4 性能数据

```
典型无锁队列 vs mutex 队列（8线程，256字节消息）：

无锁队列 (MSQueue):
  Enqueue: ~40ns
  Dequeue: ~45ns
  吞吐量: ~2000万 msg/s

Mutex 队列:
  Enqueue: ~80ns (有竞争)
  Dequeue: ~85ns
  吞吐量: ~1000万 msg/s
```

---

## 5. C++20 支持

```cpp
#include <atomic>

struct Node {
    int data;
    Node* next;
};

class LockFreeStack {
    std::atomic<Node*> head{nullptr};

public:
    void push(Node* n) {
        n->next = head.load(std::memory_order_relaxed);
        while (!head.compare_exchange_weak(
            n->next, n,
            std::memory_order_release,
            std::memory_order_relaxed));
    }

    Node* pop() {
        Node* n = head.load(std::memory_order_acquire);
        while (n && !head.compare_exchange_weak(
            n, n->next,
            std::memory_order_acquire,
            std::memory_order_relaxed));
        return n;
    }
};
```

C++20 新特性：
- `std::atomic_ref`：使已有变量原子化
- `std::atomic<SharedPtr>`：原子智能指针
- `std::atomic::wait/notify`：替代 futex
