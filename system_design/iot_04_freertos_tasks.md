# IoT 嵌入式第 4 课：FreeRTOS 任务调度系统

## 1. 最小内核结构

### 任务控制块 (TCB)

TCB 是 FreeRTOS 内核的最小调度单元，每个任务对应一个 TCB。

```c
// FreeRTOS TCB 精简结构 (Source/tasks.c)
typedef struct tskTaskControlBlock {
    volatile StackType_t  *pxTopOfStack;    // 栈顶指针
    ListItem_t            xStateListItem;   // 状态链表节点（就绪/阻塞/挂起）
    ListItem_t            xEventListItem;   // 事件链表节点
    UBaseType_t           uxPriority;       // 优先级 (0~configMAX_PRIORITIES-1)
    StackType_t           *pxStack;         // 栈起始地址
    char                  pcTaskName[16];   // 任务名
} tskTCB;
```

### 任务状态机

```
              ┌─────────────────────────────────────┐
              │                                     │
    vTaskCreate() → Ready ──vTaskSuspend()──→ Suspended
       ↑            │        ←──vTaskResume()──┘
       │            │ vTaskDelay / 等待事件
       │            ↓
       │         Blocked ─────────→ Deleted (vTaskDelete)
       │            │                    ↑
       └────────────┘          vTaskDelete()
       (延时/事件超时 → Ready)
```

状态       | 含义                          | 主要操作
-----------|-------------------------------|-----------------------
**Ready**  | 就绪态，等待 CPU              | 调度器按优先级选择运行
**Blocked**| 阻塞态，等待时间或事件         | `vTaskDelay`, 队列/信号量
**Suspended**| 挂起态，不参与调度          | `vTaskSuspend`, `vTaskResume`
**Deleted**| 已删除，待空闲任务回收         | `vTaskDelete`

---

## 2. 任务创建

### xTaskCreate — 动态创建

```c
// FreeRTOS: 动态创建任务（自动分配 TCB + 栈）
void vTask1(void *pvParameters) {
    for (;;) {
        printf("Task1: priority=%d\n", uxTaskPriorityGet(NULL));
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

void app_main(void) {
    xTaskCreate(
        vTask1,           // 任务函数
        "Task1",          // 任务名
        2048,             // 栈深度（word）
        NULL,             // 参数
        2,                // 优先级 (0 最低)
        NULL              // 任务句柄
    );
    vTaskStartScheduler(); // 启动调度器
}
```

### xTaskCreateStatic — 静态创建

```c
// 静态创建: 栈和 TCB 由开发者分配
StaticTask_t taskBuffer;
StackType_t  stackBuffer[1024];

void vTask2(void *pv) { for (;;) vTaskDelay(100); }

void start(void) {
    xTaskCreateStatic(
        vTask2, "Task2", 1024,
        NULL, 1,
        stackBuffer, &taskBuffer
    );
    vTaskStartScheduler();
}
```

**区别**：

函数                | TCB 分配 | 栈分配 | 适用场景
--------------------|----------|--------|----------
`xTaskCreate`       | 自动堆   | 自动堆 | 大多数场景
`xTaskCreateStatic` | 用户给定 | 用户给定 | 安全关键/无堆

---

## 3. 优先级抢占 + 时间片轮转

### 配置宏

```c
// FreeRTOSConfig.h
#define configUSE_PREEMPTION     1   // 1=抢占式调度, 0=协作式调度
#define configUSE_TIME_SLICING   1   // 1=同优先级时间片轮转
#define configTICK_RATE_HZ       100 // 系统节拍 (Hz)
```

### 抢占调度示例

```
高优先级任务就绪时，立即抢占低优先级任务:

    TaskA (prio=2)  ████████████░░░░░░░░
    TaskB (prio=1)  ░░░░████████████████
                    ↑ TaskA 就绪 → 抢占

configUSE_PREEMPTION=1 时:
  - Tick ISR 检查更高优先级就绪任务
  - 有则立即切换，无则继续当前任务

configUSE_PREEMPTION=0 时:
  - 任务主动调用 taskYIELD() 或阻塞才让出 CPU
```

### 时间片轮转

```c
// configUSE_TIME_SLICING=1 时，同优先级任务轮流运行
void vTaskA(void *pv) { for (;;) { /* 运行一个 tick */ } }
void vTaskB(void *pv) { for (;;) { /* 下一个 tick */ } }
// 两个任务优先级相同，每个 tick 切换一次
```

**总结**：

配置                           | 行为
-------------------------------|---------------------------------------------
`PREEMPTION=1, TIME_SLICING=1` | 抢占 + 轮转（默认，推荐）
`PREEMPTION=1, TIME_SLICING=0` | 抢占，同优先级不自动切换
`PREEMPTION=0`                 | 协作式，taskYIELD() 显式让出

---

## 4. 任务状态切换 API

### 状态转换图

```
     ┌─── vTaskDelay()/xQueueReceive() ───┐
     │                                     │
     ▼                                     │
  Ready ────────────────────────────→ Blocked
     ▲                                     │
     │    超时/事件发生/中断给信号          │
     └─────────────────────────────────────┘
     │
     ├── vTaskSuspend() ──→ Suspended
     │                       │
     │                       └── vTaskResume() → Ready
     │
     └── vTaskDelete() ──→ Deleted
```

### 核心 API

```c
// 延时: 当前任务进入 Blocked, n 个 tick 后回到 Ready
void vTaskDelay(const TickType_t xTicksToDelay);

// 精确周期性延时: 适合固定周期调用
BaseType_t xTaskDelayUntil(TickType_t *pxPreviousWakeTime,
                           const TickType_t xTimeIncrement);

// 挂起: 任务进入 Suspended, 不参与调度
void vTaskSuspend(TaskHandle_t xTask);

// 恢复: 从 Suspended 回到 Ready (可在 ISR 中使用)
void vTaskResume(TaskHandle_t xTask);
void vTaskResumeFromISR(TaskHandle_t xTask); // ISR 版

// 删除: 任务进入 Deleted, 资源由 Idle 任务回收
void vTaskDelete(TaskHandle_t xTaskToDelete);
```

### xTaskDelayUntil 使用模式

```c
// 固定 100ms 周期调用, 不受任务执行时间影响
void vPeriodicTask(void *pv) {
    TickType_t xLastWakeTime = xTaskGetTickCount();

    for (;;) {
        vTaskDelayUntil(&xLastWakeTime, pdMS_TO_TICKS(100));

        /* 此处代码每 100ms 精确执行一次 */
        sensor_read_and_report();
    }
}
```

---

## 5. 闲置任务钩子

### vApplicationIdleHook

```c
// 1. 在 FreeRTOSConfig.h 中启用
#define configUSE_IDLE_HOOK 1

// 2. 实现钩子函数
void vApplicationIdleHook(void) {
    // 闲置时运行: CPU 有空闲时才调用
    // 可用于: 低功耗模式、背景统计、看门狗喂狗
    __WFI(); // ARM 等待中断指令（省电）
}

// 空闲任务优先级为 0 (最低)
// 当所有其他任务阻塞/挂起时，空闲任务运行
```

**典型用途**：

| 用途 | 代码 |
|------|------|
| 进入休眠 | `__WFI();` 或 `__WFE();` |
| 计算 CPU 利用率 | 统计 idle hook 被调用的 tick 数 |
| 回收已删除任务 | FreeRTOS 内核在 Idle 任务中释放 TCB 和栈 |

---

## 6. Windows 模拟: Python 线程模拟 FreeRTOS 调度

```python
"""用 Python threading 模拟 FreeRTOS 任务调度"""
import threading
import time
import queue

class FreeRTOS_Sim:
    def __init__(self):
        self.tasks = {}          # name -> {func, priority, handle, suspended}
        self.running = True
        self._lock = threading.Lock()

    def xTaskCreate(self, func, name, priority):
        t = threading.Thread(target=self._runner, args=(func, name), daemon=True)
        with self._lock:
            self.tasks[name] = {"func": func, "priority": priority,
                                "thread": t, "suspended": False}
        t.start()
        return t

    def _runner(self, func, name):
        while self.running:
            with self._lock:
                info = self.tasks.get(name)
                if info and info["suspended"]:
                    continue  # 挂起态: 不执行
            func()  # 模拟任务函数循环

    def vTaskSuspend(self, name):
        with self._lock:
            if name in self.tasks:
                self.tasks[name]["suspended"] = True

    def vTaskResume(self, name):
        with self._lock:
            if name in self.tasks:
                self.tasks[name]["suspended"] = False

    def stop(self):
        self.running = False

# ---- 使用示例 ----
sim = FreeRTOS_Sim()
sim.xTaskCreate(lambda: print("High prio", end=" "), "High", 2)
sim.xTaskCreate(lambda: time.sleep(0.1), "Low", 0)
time.sleep(0.5)
sim.vTaskSuspend("High")
print("\nHigh suspended")
time.sleep(0.3)
sim.vTaskResume("High")
time.sleep(0.3)
sim.stop()
```

**Python 模拟与真实 FreeRTOS 对比**：

| 概念 | 真实 FreeRTOS | Python 模拟 |
|------|--------------|-------------|
| 栈 | 用户分配 | 系统分配 |
| 调度 | 中断驱动 + Tick | threading 调度 |
| 优先级 | 硬件抢占 | 线程优先级（非实时） |
| 延时 | `vTaskDelay` | `time.sleep` |
| 挂起 | TCB 状态位 | 线程标记 + 循环跳过 |

---

## 7. libkds 集成: slist + bheap 管理任务

```c
// 假设使用 libkds: slist 管理就绪队列, bheap 管理延时队列
#include <kds/slist.h>
#include <kds/bheap.h>

// 就绪任务队列: 每个优先级一个 slist
typedef struct {
    slist_head_t tasks;
    int          priority;
} ready_list_t;

#define MAX_PRIO 5
static ready_list_t ready_queues[MAX_PRIO];
static bheap_t     delay_queue;  // 最小堆, key = 唤醒 tick

// 任务节点结构
typedef struct {
    slist_node_t  run_node;
    bheap_node_t  delay_node;
    const char   *name;
    int           priority;
    TickType_t    wake_tick;
    void        (*entry)(void*);
} task_t;

// 就绪队列插入（按优先级）
void task_ready_enqueue(task_t *t) {
    ready_list_t *rq = &ready_queues[t->priority];
    slist_push_back(&rq->tasks, &t->run_node);
}

// 延时队列插入（用 bheap 按唤醒时间排序）
void task_delay_enqueue(task_t *t, TickType_t tick) {
    t->wake_tick = tick;
    bheap_insert(&delay_queue, &t->delay_node, tick);
}

// 选出最高优先级就绪任务
task_t *scheduler_pick(void) {
    for (int i = MAX_PRIO - 1; i >= 0; i--) {
        if (!slist_empty(&ready_queues[i].tasks)) {
            slist_node_t *n = slist_pop_front(&ready_queues[i].tasks);
            return container_of(n, task_t, run_node);
        }
    }
    return NULL; // 空闲任务
}
```

**数据结构对比**：

| 队列 | 数据结构 | 用途 |
|------|----------|------|
| 就绪队列 | `slist` (单向链表) | 每个优先级一个，O(1) 入队出队 |
| 延时队列 | `bheap` (二叉堆) | 按唤醒 tick 排序，O(log n) 插入/弹出 |
| 事件等待 | `slist` | 挂队列/信号量等待列表 |

---

## 8. FreeRTOS vs 裸机轮询对比

| 维度 | 裸机轮询 (Super Loop) | FreeRTOS |
|------|----------------------|----------|
| **CPU 利用率** | 无空闲 — while(1) 持续跑 | 空闲任务可休眠省电 |
| **响应延迟** | 取决于轮询周期 | 抢占式，高优先级任务立即响应 |
| **代码耦合** | 高：所有逻辑在一个循环 | 低：每个任务独立函数 |
| **扩展性** | 加功能需重构整个 loop | 加 xTaskCreate 即可 |
| **实时性** | 无保证 | 优先级驱动，可预测延迟 |
| **调试** | 简单（单线程思维） | 需要理解任务切换 |
| **内存开销** | 极小 (≈栈 + 全局变量) | 每任务 TCB + 栈 (≈ 200B + 栈) |
| **适用场景** | 极简传感器读取 | 多外设/协议栈/复杂逻辑 |

### 何时选择 FreeRTOS

```
裸机轮询 ←────────── 系统复杂度 ──────────→ FreeRTOS

  简单                        复杂
  单传感器 →→ 传感器+WiFi+显示屏 →→ 多任务协议栈
  1个循环      状态机还行            必须 RTOS
```

---

## 代码片段集锦

### C 版: 3 任务演示

```c
/* 完整演示：创建3个任务展示抢占 + 延时 + 挂起 */
void vHi(void *pv) {
    for (;;) { printf("H"); vTaskDelay(pdMS_TO_TICKS(200)); }
}
void vMed(void *pv) {
    for (;;) { printf("M"); vTaskDelay(pdMS_TO_TICKS(300)); }
}
void vLow(void *pv) {
    for (;;) { printf("L"); vTaskDelay(pdMS_TO_TICKS(500)); }
}

void main(void) {
    xTaskCreate(vHi,  "High", 100, NULL, 3, NULL);
    xTaskCreate(vMed, "Med",  100, NULL, 2, NULL);
    xTaskCreate(vLow, "Low",  100, NULL, 1, NULL);
    vTaskStartScheduler(); // 永不返回
}
```

### Python 版: 优先级模拟

```python
"""模拟 FreeRTOS 优先级抢占 + 时间片"""
import threading, time, random

class SimTask:
    tasks = []

    def __init__(self, name, prio, fn):
        self.name = name
        self.prio = prio
        self.fn = fn
        self.blocked = False
        SimTask.tasks.append(self)

    @classmethod
    def scheduler(cls):
        """模拟抢占式调度器"""
        ready = [t for t in cls.tasks if not t.blocked]
        if not ready: return None
        ready.sort(key=lambda t: t.prio, reverse=True)
        return ready[0]  # 最高优先级

def worker(task):
    for _ in range(3):
        current = SimTask.scheduler()
        assert current == task, f"preempted! {current.name} runs"
        task.fn()
        time.sleep(random.uniform(0.01, 0.05))

t1 = SimTask("LED",  2, lambda: print("LED blink"))
t2 = SimTask("UART", 1, lambda: print("UART send"))

threads = [threading.Thread(target=worker, args=(t,), daemon=True)
           for t in SimTask.tasks]
for t in threads: t.start()
time.sleep(0.3)
```

---

## 参考

- FreeRTOS 源码: `tasks.c` / `list.c` / `FreeRTOSConfig.h`
- libkds: [https://github.com/torvalds/kds](https://github.com/torvalds/kds)
- 官方手册: [FreeRTOS Task Management](https://www.freertos.org/Documentation/RTOS_book.html)
