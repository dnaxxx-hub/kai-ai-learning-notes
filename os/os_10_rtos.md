# 第10课：实时操作系统（RTOS）与嵌入式系统基础

> 学习日期：2025-07-15
> 标签：`#os` `#rtos` `#embedded` `#scheduling`

---

## 1. 实时系统分类

### 1.1 硬实时（Hard Real-Time）

**定义**：错过截止时间（deadline）等同于系统失败，可能导致灾难性后果。

**特点**：
- 必须严格保证截止时间
- 系统设计必须做最坏情况分析（WCET — Worst-Case Execution Time）
- 调度算法需要提供**确定性的**可调度性保证

**典型场景**：
| 领域 | 示例 | 截止时间 |
|------|------|----------|
| 航空电子 | 飞控系统 | 1-10 ms |
| 汽车 | 安全气囊触发 | < 5 ms |
| 医疗 | 心脏起搏器 | 精确节拍 |
| 工业控制 | 机器人关节控制 | 1-20 ms |

> 如果安全气囊在碰撞后 20ms 才触发——乘客已经撞上方向盘了。硬实时**不是性能问题，是安全问题**。

### 1.2 软实时（Soft Real-Time）

**定义**：错过截止时间会导致性能下降/服务质量降低，但**系统不会崩溃**。

**特点**：
- 偶尔超时可接受，均值延迟更重要
- 通常采用统计保证而非确定性保证
- 系统过载时优雅降级

**典型场景**：
| 领域 | 示例 | 容忍度 |
|------|------|--------|
| 音视频 | 视频播放器 | 偶尔丢帧可接受 |
| 游戏 | 渲染管线 | 偶尔掉帧不影响整体体验 |
| 通信 | VoIP 通话 | 小的抖动缓冲可补偿 |

### 1.3 固实时（Firm Real-Time）

**定义**：介于硬实时和软实时之间。偶尔错过可接受，但**会有代价**（后果累积）。

**特点**：
- 超时的结果**没用**了（丢弃），但系统不崩溃
- 错过率超过阈值会导致系统不可接受

**典型场景**：
- 在线交易系统：错过撮合窗口 → 订单作废
- 流媒体直播：超时的数据包直接丢弃

### 实时系统对比矩阵

| 特性 | 硬实时 | 固实时 | 软实时 |
|------|--------|--------|--------|
| deadline 错过后果 | 灾难 | 价值归零 | 质量下降 |
| 确定性要求 | 绝对 | 统计保证 | 尽力而为 |
| 调度分析 | WCET 必须 | 概率分析 | 均值分析 |
| 典型应用 | 安全系统 | 交易系统 | 多媒体 |

---

## 2. 调度算法

### 2.1 RMS（Rate-Monotonic Scheduling）

**核心思想**：任务的**周期越短**（频率越高），优先级越高。

- **优先级分配**：静态/固定优先级（任务创建时确定，运行期不变）
- **调度方式**：抢占式（高优先级任务可打断低优先级）
- **最优性**：在**固定优先级**调度算法中，RMS 是**最优**的（如果有一种固定优先级算法能调度，RMS 也能）

#### 可调度性分析 — Liu-Layland 条件

RMS 可调度性的**充分条件**（Liu & Layland, 1973）：

$$U = \sum_{i=1}^{n} \frac{C_i}{T_i} \leq n(2^{1/n} - 1)$$

其中：
- $U$ = CPU 总利用率
- $C_i$ = 任务 $i$ 的最坏执行时间（WCET）
- $T_i$ = 任务 $i$ 的周期
- $n$ = 任务数量

**边界值表**：

| n | $n(2^{1/n} - 1)$ |
|---|-------------------|
| 1 | 1.000 |
| 2 | 0.828 |
| 3 | 0.779 |
| 4 | 0.756 |
| 5 | 0.743 |
| ∞ | $\ln 2 \approx 0.693$ |

> 当 $n \to \infty$，LL 边界趋近于 $\ln 2 \approx 69.3\%$。这意味着在任务数很多时，RMS 最多只能保证约 69% 的 CPU 利用率。

**注意**：
- LL 条件是**充分但不必要**的（满足则一定可调度，不满足也可能可调度）
- 更精确的**必要充分条件**需要做 Response Time Analysis（RTA）

### 2.2 EDF（Earliest Deadline First）

**核心思想**：**截止时间越早**的任务优先级越高。

- **优先级分配**：动态（每个调度点重新计算）
- **调度方式**：抢占式
- **最优性**：在**动态优先级**算法中，EDF 是**最优**的

#### 可调度性条件

EDF 的充分必要条件比 RMS 简单：

$$U = \sum_{i=1}^{n} \frac{C_i}{T_i} \leq 1$$

即：只要总 CPU 利用率不超过 100%，EDF 就能保证所有任务都被调度。

#### RMS vs EDF 对比

| 特性 | RMS | EDF |
|------|-----|-----|
| 优先级 | 固定优先级 | 动态优先级 |
| 实现复杂度 | 低（静态分析） | 高（运行时排序） |
| 利用率上限 | $n(2^{1/n} - 1)$ → 69% | 100% |
| 过载行为 | 低优先级任务全饿死 | 多米诺骨牌效应 |
| 适用场景 | 任务数少、周期稳定 | 利用率高、变化大 |

> **过载行为的区别**：RMS 过载时，只影响低优先级任务（高优先级任务仍正常）；EDF 过载时，所有任务都可能错过截止时间（称为"多米诺效应"）。

### 2.3 优先级反转（Priority Inversion）

**经典问题**：三个任务 T1（高）、T2（中）、T3（低），共享一把锁。

**场景**：
1. T3 获得锁，开始执行
2. T1 被唤醒，抢占 T3，尝试获取锁 → 阻塞
3. T2 抢占 T3（因为 T3 优先级低）→ T3 无法释放锁
4. T1 等待 T2 执行完 → T2 执行完 T3 继续 → T3 释放锁 → T1 才拿到锁

**结果**：**高优先级任务 T1 被中优先级任务 T2 间接阻塞**，这是反直觉的。

### 2.4 优先级继承（Priority Inheritance）

**解法**：当低优先级任务持有高优先级任务等着的锁时，**临时提升**低优先级任务的优先级到等待者的级别。

**上述场景的解决**：
1. T3 获得锁，执行
2. T1 被唤醒，尝试获取锁 → 阻塞
3. 此时 T3 继承 T1 的优先级（提升到高优先级）
4. T2 无法抢占 T3（T3 现在是高优先级）
5. T3 尽快执行完临界区 → 释放锁 → 恢复原优先级
6. T1 获取锁，正常运行

**问题**：不能避免**死锁**和**链式阻塞**（多个高优先级等同一个锁）。

### 2.5 优先级天花板（Priority Ceiling Protocol）

**进一步加强**：每个锁有一个"天花板优先级"（可能获取该锁的最高任务优先级）。

**规则**：
- 任务只能获取优先级**低于**它自身优先级的锁
- 如果锁的天花板 >= 当前任务的优先级，则任务被阻塞

**优点**：避免死锁，减少链式阻塞。

---

## 3. RTOS 常见内核

### 3.1 FreeRTOS

最广泛使用的开源 RTOS，专为微控制器（MCU）设计。

**核心组件**：

```
┌─────────────────────────────────────┐
│           FreeRTOS Kernel            │
├───────────────────┬─────────────────┤
│     Task Mgmt     │   IPC & Sync    │
├───────────────────┼─────────────────┤
│  • 任务创建/删除  │  • 队列(Queue)  │
│  • 优先级调度     │  • 二值信号量   │
│  • 时间片轮转     │  • 计数信号量   │
│  • 任务通知       │  • 互斥量(Mutex)│
├───────────────────┼─────────────────┤
│  Memory Mgmt      │   Timers        │
├───────────────────┼─────────────────┤
│  • heap_1~heap_5  │  • 软件定时器   │
│  • 静态/动态分配  │  • 回调函数     │
└───────────────────┴─────────────────┘
```

**任务状态机**：

```
                 ┌──────────┐
   创建任务 ──→  │  Ready   │ ←── 恢复
                 └────┬─────┘
                      │ 调度器选择
                      ↓
                 ┌──────────┐
                 │ Running  │
                 └────┬─────┘
                      │
                 ┌────┴─────┐
                 ↓          ↓
           ┌─────────┐  ┌─────────┐
           │ Blocked │  │Suspended│
           └─────────┘  └─────────┘
```

- **Ready**：可运行，等待调度器分配 CPU
- **Running**：正在执行
- **Blocked**：等待某事件（延迟、信号量、队列消息）
- **Suspended**：被 vTaskSuspend() 挂起，只能通过 vTaskResume() 恢复

**代码示例**（C语言，FreeRTOS API）：

```c
// 任务函数
void vTask1(void *pvParameters) {
    for (;;) {
        // 等待队列消息
        xQueueReceive(xQueue, &data, portMAX_DELAY);
        // 处理数据...
    }
}

// 创建任务
xTaskCreate(vTask1, "Task1", 256, NULL, 2, NULL);

// 创建信号量
SemaphoreHandle_t xSem = xSemaphoreCreateBinary();

// 创建队列
QueueHandle_t xQueue = xQueueCreate(10, sizeof(uint32_t));
```

### 3.2 Zephyr

Linux 基金会维护的 RTOS，面向 IoT 和可穿戴设备。

**特点**：
- 支持多种架构（ARM, RISC-V, x86, Xtensa 等）
- 类似 Linux 的设备驱动模型（Device Tree）
- 支持 POSIX 接口子集
- 蓝牙/BLE、WiFi 协议栈集成
- 安全分区（TF-M/TrustZone 支持）

### 3.3 RT-Thread

中国主导的国产 RTOS，功能丰富。

**特点**：
- 支持**标准版**（面向 MCU）和**Smart 版**（面向带 MMU 的应用处理器）
- 支持动态加载（dlmodule）
- 兼容 POSIX 和 Linux 网络 API
- 组件丰富：文件系统（DFS）、网络协议栈（lwIP）、GUI（Persimmon）

### RTOS 内核对比

| 特性 | FreeRTOS | Zephyr | RT-Thread |
|------|----------|--------|-----------|
| 许可证 | MIT | Apache 2.0 | Apache 2.0 |
| 最小 RAM | ~1 KB | ~8 KB | ~4 KB |
| 架构支持 | 广泛 | 广泛 | 广泛 |
| 设备驱动模型 | 简单 | Linux-like | 分层 |
| POSIX 支持 | 有限 | 中等 | 中等 |
| 动态加载 | ✗ | ✗ | ✓（Smart） |

---

## 4. 实时 Linux（PREEMPT_RT）

### 4.1 为什么普通 Linux 不是实时的？

普通 Linux 内核的延迟来源：

| 延迟来源 | 原因 | 时间量级 |
|----------|------|----------|
| 中断禁用 | spinlock 临界区关中断 | 10-100 μs |
| 软中断(softirq) | 不可抢占 | 100-1000 μs |
| 大内核锁 | 访问共享数据结构 | 100-500 μs |
| 调度器 | O(1) 或 CFS 的调度延迟 | 10-100 μs |
| 页面分配 | 内存回收（kswapd） | 100-5000 μs |

### 4.2 PREEMPT_RT 补丁集

**目的**：将 Linux 改造成硬实时系统（最坏情况延迟 < 100 μs）。

**核心改造**：

```
     ╔══════════════════════════════════════╗
     ║        PREEMPT_RT 改造               ║
     ╠══════════════════════════════════════╣
     ║ ① 内核可抢占 (PREEMPT_FULL)          ║
     ║ ② 中断线程化 (IRQ Threads)           ║
     ║ ③ spinlock → rt_mutex 替换          ║
     ║ ④ 高精度定时器 (HRT)                 ║
     ║ ⑤ RCU 非抢占化                      ║
     ╚══════════════════════════════════════╝
```

### 4.3 中断线程化（IRQ Threads）

**动机**：中断处理程序运行在中断上下文中——**不可抢占**，且优先级高于任何任务。

**改造**：
1. 中断处理程序的**上半部**（hardirq）尽可能短
2. **下半部**（threaded IRQ）变成内核线程，可被实时任务抢占
3. 非实时设备的中断可设置为低优先级

```
传统 Linux:
  硬件中断 → [关中断] → ISR (不可抢占) → softirq → 任务

PREEMPT_RT:
  硬件中断 → [开中断] → ISR (极短) → irq_thread (可抢占)
                                         ↓
                                   实时任务可以抢占它
```

### 4.4 RCU（Read-Copy-Update）

RCU 是一种**无锁**的同步机制，读操作几乎零开销。

**核心思想**：
- 读端**不阻塞**，直接读（通过读侧临界区声明）
- 写端：先复制一份 → 修改 → 更新指针 → 等待所有读端退出 → 释放旧副本

**在 PREEMPT_RT 中的变化**：
- 标准 Linux：RCU 读侧临界区**可被阻塞**（非抢占的）
- PREEMPT_RT：RCU 读侧临界区**不可阻塞**（加了抢占点保护）

---

## 5. Python 实现 RTOS 任务调度模拟

> 完整代码见 `memory/learning/code/rtos_scheduler.py`

### 5.1 RMS 调度器

```python
class RMSTask:
    """RMS 任务：周期越短，优先级越高"""
    def __init__(self, pid, period, exec_time, deadline=None):
        self.pid = pid
        self.T = period       # 周期
        self.C = exec_time    # 最坏执行时间
        self.D = deadline or period  # 截止时间
        self.deadline = self.D
        self.remaining = 0
        self.next_release = 0
    
    @property
    def priority(self):
        return -self.T  # 越小周期 → 越高优先级 → 数值越小
```

**可调度性检查**：

```python
def rms_schedulable(tasks):
    """Liu-Layland 充分条件"""
    n = len(tasks)
    U = sum(t.C / t.T for t in tasks)
    bound = n * (2 ** (1 / n) - 1)
    return U <= bound, U, bound
```

### 5.2 EDF 调度器

```python
class EDFTask:
    """EDF 任务：截止时间越早，优先级越高"""
    def __init__(self, pid, period, exec_time, deadline=None):
        self.pid = pid
        self.T = period
        self.C = exec_time
        self.D = deadline or period
        self.deadline = self.D
        self.remaining = 0
        self.next_release = 0
```

**EDF 可调度性检查**（充分必要条件）：

```python
def edf_schedulable(tasks):
    """EDF 调度条件：U <= 1"""
    U = sum(t.C / t.T for t in tasks)
    return U <= 1.0, U
```

### 5.3 优先级继承模拟

```python
class Resource:
    def __init__(self):
        self.holder = None
        self.ceiling = float('inf')
    
    def request(self, task, all_tasks):
        if self.holder is None:
            self.holder = task
            return True
        # 优先级继承
        if self.holder.priority > task.priority:
            self.holder.inherited_priority = task.priority
        return False
    
    def release(self, task):
        self.holder = None
        task.inherited_priority = task.base_priority
```

### 5.4 模拟器主循环

```python
def simulate(scheduler_type, tasks, total_time=100):
    """通用调度模拟器"""
    time = 0
    schedule = []
    
    while time < total_time:
        # 释放新周期任务
        for t in tasks:
            if time >= t.next_release:
                t.remaining = t.C
                t.deadline = time + t.D
                t.next_release = time + t.T
        
        # 选择下一个运行的任务
        if scheduler_type == 'rms':
            ready = [t for t in tasks if t.remaining > 0]
            if not ready:
                schedule.append((time, time+1, 'idle'))
                time += 1
                continue
            # RMS: 周期短的优先 (priority = -T)
            current = min(ready, key=lambda t: t.T)
        else:  # EDF
            ready = [t for t in tasks if t.remaining > 0]
            if not ready:
                schedule.append((time, time+1, 'idle'))
                time += 1
                continue
            # EDF: 截止时间早的优先
            current = min(ready, key=lambda t: t.deadline)
        
        schedule.append((time, time+1, f'Task-{current.pid}'))
        current.remaining -= 1
        time += 1
    
    return schedule
```

---

## 总结

### 关键记忆点

1. **实时 ≠ 快速**：实时是**确定性的时序保证**，不是性能
2. **三类实时**：硬（灾难）、固（代价）、软（降质）
3. **RMS vs EDF**：固定 vs 动态优先级；RMS 69% 利用率瓶颈 vs EDF 100%
4. **优先级反转**：低优先级间接阻塞高优先级 → 需要优先级继承/天花板协议
5. **FreeRTOS**：嵌入式事实标准，轻量（1KB+ RAM），丰富的 IPC 原语
6. **PREEMPT_RT**：改造 Linux 成为硬实时系统（中断线程化、lock 替换、HRT）
7. **任务状态机**：Ready → Running → Blocked/Suspended

### 核心公式

| 算法 | 可调度性条件 | 性质 |
|------|-------------|------|
| RMS | $U \leq n(2^{1/n} - 1)$ | 充分但不必要 |
| EDF | $U \leq 1$ | 充要条件 |
| 优先级继承 | — | 防止无界优先级反转 |

### 面试常问题

> **Q**：RMS 和 EDF 哪个更好？
> **A**：RMS 实现简单、可预测性好（过载时只影响低优先级任务），适合安全关键系统。EDF 利用率和灵活性更高，但过载时行为难预测。

> **Q**：为什么 Linux 需要 PREEMPT_RT？
> **A**：因为普通 Linux 内核不可抢占——spinlock 临界区、中断处理程序、软中断都会导致不可预测的延迟。PREEMPT_RT 通过中断线程化、spinlock 替换为 rt_mutex 等手段消除了这些延迟源。

> **Q**：FreeRTOS 的任务调度原理？
> **A**：固定优先级抢占式调度（类似 RMS），同优先级时间片轮转。通过队列/信号量实现同步，Binary Semaphore 可在 ISR 中释放，Mutex 含优先级继承机制。

---

## 参考

- Liu, C. L., & Layland, J. W. (1973). "Scheduling algorithms for multiprogramming in a hard-real-time environment"
- FreeRTOS 官方文档：https://www.freertos.org/
- PREEMPT_RT Wiki：https://wiki.linuxfoundation.org/realtime/
- Zephyr Project：https://www.zephyrproject.org/
- RT-Thread：https://www.rt-thread.org/
