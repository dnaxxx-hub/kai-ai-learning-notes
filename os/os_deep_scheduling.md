# OS 进程调度深度解析

> 学习笔记 - 从调度基础到 Linux CFS 实现，从经典算法到实时调度

---

## 1. 调度基础

### 1.1 三态模型与调度队列

进程在生命周期中处于三种基本状态：

- **运行（Running）**：进程正在 CPU 上执行
- **就绪（Ready）**：进程已具备运行条件，等待 CPU
- **阻塞（Blocked/Waiting）**：进程等待 I/O 或某事件完成

操作系统维护三类调度队列：
- **就绪队列（Ready Queue）**：所有可运行进程的链表/树结构
- **阻塞队列（Device Queue）**：等待特定 I/O 设备的进程
- **运行队列**：实际占用 CPU 的进程（通常每个 CPU 1 个）

队列操作抽象：`enqueue(dequeue)` 完成进程入队出队。现代内核支持多级队列（如 Linux 的优先级数组）。

### 1.2 调度时机

调度发生的两种方式：

| 类型 | 触发条件 | 示例 |
|------|----------|------|
| **自愿（Voluntary）** | 进程主动让出 CPU | `sleep()`, `wait()`, `read()` 阻塞 |
| **非自愿（Involuntary）** | 时钟中断强制抢占 | 时间片耗尽，更高优先级进程就绪 |

现代 Linux 采用 **完全抢占式内核**，在以下时机检查调度：
1. 时钟 tick 中断（`timer interrupt`）
2. 进程从系统调用返回用户态
3. 中断/异常处理返回
4. 进程状态变更（`wake_up()` 唤醒高优先级进程）

### 1.3 上下文切换开销

上下文切换（Context Switch）是调度中最昂贵的操作：

```
切换开销 = TLB 刷新 + 缓存污染 + 寄存器保存/恢复 + 内核栈切换
         ≈ 1-10 µs（现代硬件）
```

**关键开销分布：**
- **TLB 失效**：进程切换导致页表切换，TLB 全部失效 → 后续访问产生大量缺页
- **L1/L2 缓存丢失**：新进程的缓存尚未预热，大量 cache miss
- **内核栈切换**：从用户栈切换到内核栈再切换回新进程的用户栈
- **寄存器保存/恢复**：通用寄存器、FPU/向量寄存器

优化方向：`RCU`、大页减少 TLB miss、`sched_migrate` 避免跨 CPU 迁移。

### 1.4 O(1) 调度器 vs CFS

| 特性 | O(1) Scheduler | CFS (Completely Fair Scheduler) |
|------|---------------|--------------------------------|
| 引入版本 | Linux 2.6（2001） | Linux 2.6.23（2007） |
| 数据结构 | 双优先级数组（140级） | 红黑树 |
| 时间复杂度 | O(1) 查找 | O(log N) 查找 |
| 核心思想 | 固定优先级 + 时间片 | 虚拟运行时间公平 |
| 交互性 | 启发式检测交互进程 | 基于睡眠时间自动判定 |
| 弱点 | 启发式复杂、交互判定不准 | 大核数下负载均衡复杂 |

**O(1) 的精髓**：每个优先级对应一个 FIFO 链表。`active` 和 `expired` 两个数组，当 active 全部用完时交换指针。140个优先级中 0-99 为 RT，100-139 为普通。

**CFS 的革命**：不再用固定时间片，而是按权重分配 CPU 时间比例。目标——每个进程获得 `1/n` 的 CPU 时间。

---

## 2. 经典调度算法

### 2.1 算法详解

| 算法 | 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| **FCFS** | 先到先服务 | 简单公平 | 护航效应（长进程阻塞短进程） | 批处理 |
| **SJF** | 最短作业优先 | 最小平均等待时间 | 饥饿（长进程可能永远得不到 CPU） | 批处理（已知执行时间） |
| **SRTF** | 最短剩余时间优先 | SJF 的抢占版本，更优 | 需要预知剩余时间，短进程饥饿 | 理论上最优 |
| **优先级** | 高优先级先执行 | 灵活 | 无限饥饿、优先级反转 | 实时系统 |
| **RR(Round Robin)** | 时间片轮转 | 响应快，无饥饿 | 时间片选择困难 | 分时系统 |
| **MLFQ** | 多级反馈队列 | 兼顾交互和批处理 | 参数调优复杂 | 通用 OS（Linux/Mach） |

### 2.2 评价指标

- **周转时间（Turnaround Time）**：`T_completion - T_arrival`。衡量作业的总体完成效率
- **等待时间（Waiting Time）**：进程在就绪队列中等待的总时间。不包含 I/O 等待
- **响应时间（Response Time）**：从提交到首次获得 CPU 的时间。交互性关键指标
- **吞吐量（Throughput）**：单位时间内完成的进程数。批处理系统核心指标

**调度目标权衡**：
```
最小化周转时间 → SJF/SRTF（长进程受罚）
最小化响应时间 → RR/MLFQ（上下文切换增加）
最大化吞吐量 → FCFS（上下文切换最少）
```

### 2.3 优先级反转与继承

**优先级反转（Priority Inversion）**：高优先级进程因低优先级进程持有锁而被间接阻塞，中优先级进程抢占 CPU，导致高优先级进程无限等待。

经典火星探路者事故中：
1. 低优先级进程 L 持有锁
2. 高优先级进程 H 等待锁 → 阻塞
3. 中优先级进程 M（不争锁）抢占 L → H 被 M 间接饿死

**解决方案：**
- **优先级继承（Priority Inheritance / PI）**：当 H 等待 L 持有的锁时，L 临时继承 H 的优先级，直到释放锁
- **优先级天花板（Priority Ceiling）**：锁设置最高可能优先级，持有者自动提升

Linux 内核 `futex` 支持 PI 协议，`pthread_mutexattr_setprotocol()` 可配置。

---

## 3. Linux CFS 深度解析

### 3.1 红黑树结构

CFS 使用红黑树（Red-Black Tree）作为就绪队列，键值为 `vruntime`。

```
         黑节点 (vruntime_x)
        /                \
  红节点                 红节点
(vruntime_small)     (vruntime_large)
```

- 最左节点 = vruntime 最小的进程 = 下一个运行的进程
- 插入/删除：O(log N)
- CFS 限制树大小：`min_vruntime` 与进程 vruntime 差值超过 `sysctl_sched_latency` 时入树，否则入 `cfs_rq->runnable` 链表

### 3.2 vruntime 计算与权重

vruntime（虚拟运行时间）是 CFS 的核心：

```c
vruntime += 实际运行时间 * NICE_0_LOAD / weight;
```

其中 weight 由 nice 值查表得到：

| nice | weight | CPU 份额 |
|------|--------|----------|
| 0    | 1024   | 1/n (基准) |
| -20  | 88761  | 最高优先级 |
| +19  | 15     | 最低优先级 |

每差 1 个 nice 值，权重变化约 1.25 倍。公式：
```
Δweight_factor ≈ 1.25^|nice_diff|
```

**关键代码流程：**
```c
// kernel/sched/fair.c
static void update_curr(struct cfs_rq *cfs_rq) {
    struct sched_entity *curr = cfs_rq->curr;
    u64 delta_exec = calc_delta_fair(now - curr->exec_start, curr);
    curr->vruntime += delta_exec;
    /* 更新 min_vruntime */
    update_min_vruntime(cfs_rq);
}
```

### 3.3 调度类体系

Linux 内核按优先级顺序执行五类调度类：

```
stop_sched_class      → 最高优先级，不可被抢占（stop_machine）
  deadline_sched_class  → EDF + CBS（SCHED_DEADLINE）
    rt_sched_class        → 实时进程（SCHED_FIFO / SCHED_RR）
      fair_sched_class      → 普通进程（SCHED_NORMAL / SCHED_BATCH / SCHED_IDLE）
        idle_sched_class      → 空闲线程（per-CPU idle task）
```

策略选择：

| 调度策略 | 调度类 | 优先级范围 | 适用 |
|----------|--------|-----------|------|
| `SCHED_NORMAL` | fair | 0 (nice) | 普通用户进程 |
| `SCHED_BATCH` | fair | 0 (nice) | CPU 密集型批处理 |
| `SCHED_IDLE` | fair | 非常低 | 后台低优先级 |
| `SCHED_FIFO` | rt | 1-99 | 实时 FIFO |
| `SCHED_RR` | rt | 1-99 | 实时轮转 |
| `SCHED_DEADLINE` | deadline | - | 硬实时 |

### 3.4 组调度与 cgroup

**组调度（Group Scheduling）**：将进程组织成层级结构，CPU 时间按组分配。

```
CPU 时间
  ├── system.slice (50%)
  │     ├── sshd (20% × 50% = 10%)
  │     └── cron (80% × 50% = 40%)
  └── user.slice (50%)
        ├── user1 (50% × 50% = 25%)
        └── user2 (50% × 50% = 25%)
```

cgroup v1 cpu 子系统：
- `cpu.shares`：相对权重（类似 nice 的组级别版本）
- `cpu.cfs_quota_us / cpu.cfs_period_us`：绝对 CPU 上限
- `cpu.rt_runtime_us`：实时任务限制

### 3.5 调度域与负载均衡

**调度域（Scheduling Domain）**：CPU 的层级拓扑结构，帮助选择迁移目标。

```
NUMA Node 0          NUMA Node 1
├── Core 0            ├── Core 2
│   ├── HT 0 (CPU0)   │   ├── HT 0 (CPU2)
│   └── HT 1 (CPU1)   │   └── HT 1 (CPU3)
└── Core 1            └── Core 3
    ├── HT 0 (CPU...) │       ...
    └── HT 1 (CPU...) │       ...
```

负载均衡流程：
1. `tick` 触发 `trigger_load_balance()`
2. 检查当前 CPU 是否有过载（超过 `avg_load + imbalance_pct`）
3. 从最繁忙的调度组拉取进程
4. 使用 `find_busiest_group()` → `find_busiest_queue()` → 迁移

**迁移代价考虑**：同核不同线程（成本最低）> 同 Node 不同核 > 跨 Node（成本最高，NUMA 内存访问慢）。

---

## 4. 实时调度

### 4.1 RM (Rate Monotonic)

- 静态优先级，周期越短的进程优先级越高
- **可调度性测试（充分条件）**：
  ```
  U = Σ(Ci / Ti) ≤ n(2^(1/n) - 1)
  ```
  当 n→∞ 时，上限 ≈ ln2 ≈ 69.3%
- **精确测试**：响应时间分析（Response Time Analysis）

### 4.2 EDF (Earliest Deadline First)

- 动态优先级，截止时间越早优先级越高
- **可调度性测试**：
  ```
  U = Σ(Ci / Ti) ≤ 1  (充分必要条件)
  ```
- 理论上优，但实现复杂（需要排序截止时间）

| 特性 | RM | EDF |
|------|-----|-----|
| 优先级 | 静态 | 动态 |
| 利用率上限 | 69.3%（n→∞） | 100% |
| 实现复杂度 | 简单 | 中等 |
| 过载行为 | 低优先级进程错过截止时间 | 不可预测 |

### 4.3 Linux RT 与 PREEMPT_RT

Linux 标准内核不是完全可抢占的：
- 中断处理程序不可被抢占
- 自旋锁临界区不可被抢占

**PREEMPT_RT (Real-Time Linux)** 补丁集：
1. **中断线程化**：中断处理程序成为内核线程，可被抢占
2. **自旋锁替换**：`spin_lock()` 替换为 `rt_mutex`（支持优先级继承）
3. **高精度定时器**：`hrtimer` 用于精确调度
4. **RCU 抢占**：RCU 读侧临界区可被抢占

```
主线内核：    中断 → 不可抢占临界区 → 硬实时任务
PREEMPT_RT：  中断线程 → 可抢占内核 → 硬实时任务 (< 100µs 响应)
```

---

## 5. 设计要点总结

### 核心矛盾
- **公平 vs 吞吐量**：CFS 公平但上下文切换多；FCFS 吞吐高但交互差
- **灵活 vs 可预测**：MLFQ 参数多适应性好但难以优化；RM 简单但利用率有限

### 实际系统中的组合
- **Linux**：CFS（普通）+ RT（实时）+ Deadline（硬实时）+ 组调度（cgroup）
- **Windows**：基于优先级的抢占式调度 + 虚拟化优先级提升
- **RTOS**：固定优先级 + 优先级继承（VxWorks, QNX）

### 学习建议
1. 阅读 `kernel/sched/fair.c` 中的 `__schedule()` 和 `pick_next_task_fair()`
2. 使用 `perf sched record/latency/timehist` 分析实际调度行为
3. 动手实现调度算法模拟器（见配套代码）
4. 用 `taskset` 和 `chrt` 控制进程亲缘性和调度策略

---

## 参考资料

- Linux 内核源码 `kernel/sched/`
- 《Modern Operating Systems》A.S. Tanenbaum
- 《Linux Kernel Development》Robert Love
- CFS 论文：http://people.cs.ksu.edu/~kbt582/cis732/cfs-design.pdf
- PREEMPT_RT 官网：https://wiki.linuxfoundation.org/realtime/start
