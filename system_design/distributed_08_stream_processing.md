# 分布式系统 第8课：有状态流处理与实时计算

> **学习日期**: 2026-05-10
> **前置知识**: 分布式系统基础、消息队列(分布式05)、批处理概念
> **本课覆盖**: 流处理 vs 批处理 / 有状态流处理 / 时间语义 / Flink架构 / 极简流处理引擎实现

---

## 大纲

1. [流处理 vs 批处理](#1-流处理-vs-批处理)
2. [有状态流处理](#2-有状态流处理)
3. [时间语义与 Watermark](#3-时间语义与-watermark)
4. [Flink 核心架构](#4-flink-核心架构)
5. [极简有状态流处理引擎实现](#5-极简有状态流处理引擎实现)

---

## 1. 流处理 vs 批处理

### 1.1 两种范式的本质差异

| 维度 | 流处理 (Stream) | 批处理 (Batch) |
|------|----------------|----------------|
| **数据访问** | 每条记录到达即处理 | 全量数据先落地再处理 |
| **延迟** | 毫秒级 | 分钟~小时级 |
| **吞吐量** | 较低（逐条处理开销大） | 高（批量I/O+批计算优化） |
| **容错** | 复杂（状态一致性） | 简单（重跑即可） |
| **典型框架** | Flink, Kafka Streams, Storm | MapReduce, Spark Batch, Hive |
| **适用场景** | 实时监控、风控、推荐、IoT | 离线报表、ETL、模型训练 |

### 1.2 处理语义 (Processing Semantics)

流处理系统在故障恢复时需要保证数据处理的一致性，有三种级别：

**At-Most-Once（最多一次）**
- 每条记录最多被处理一次，丢数据也不管
- 性能最好，容错最差
- 适用于：监控指标采样（丢几个点无所谓）

**At-Least-Once（至少一次）**
- 每条记录至少被处理一次，可能重复
- 故障时重新发送/重算，下游需要幂等去重
- 大多数系统默认保证

**Exactly-Once（精确一次）**
- 每条记录恰好被处理一次，不丢不重
- 需要分布式快照 + 事务输出
- Flink、Kafka Streams 支持

> **关键洞察**：精确一次实际上是"看起来精确一次"——系统在内部可能执行了多次，但结果是幂等的。

---

## 2. 有状态流处理

批处理天然无状态（每次都读全量数据从头算），但流处理中每条记录到达时，如果想做**聚合、计数、Join、去重**等操作，就必须**记住之前的信息**——这就是**状态**。

### 2.1 无状态 vs 有状态

```
无状态算子：filter(x -> x > 100)     // 只看当前记录
有状态算子：count(key)                // 需要按 key 累加
有状态算子：sum(sliding_window)       // 需要维护窗口内数据
有状态算子：join(stream_A, stream_B)  // 需要缓冲两个流
```

### 2.2 状态类型

**Keyed State（分键状态）**
- 按 key（如 userId、deviceId）分区维护状态
- 每个 key 有独立的状态副本
- 示例：每个用户的最近10次点击记录、每个传感器的当前累计温度

```
伪代码：
state = get_keyed_state(userId)
state.click_count += 1
```

**Operator State（算子级状态）**
- 算子的所有并发实例共享（每个TaskManager的slot一个实例）
- 与 key 无关，不分区
- 示例：Kafka 的 offset 位置（每个分区记录读到哪了）、Bloom Filter 位图

### 2.3 状态后端 (State Backends)

| 后端 | 存储位置 | 特点 |
|------|---------|------|
| **MemoryStateBackend** | JVM Heap | 极快，但不持久，大状态 OOM |
| **FsStateBackend** | 本地文件 + DFS | 状态存本地，checkpoint 刷到 HDFS |
| **RocksDBStateBackend** | RocksDB (LSM-Tree) | 磁盘存储，支持超大状态，保持较快读写 |

Flink 的 RocksDB 后端最流行——写入先写 MemTable（内存），然后再 flush 到 SST 文件（磁盘），读时先查 MemTable 再查 SST。

### 2.4 状态 Checkpoint：精确一次的核心

**Checkpoint（检查点）** 是 Flink 实现 exactly-once 语义的关键机制：

1. JobManager 周期性向所有 Source 注入 **Barrier**（栅栏）
2. Barrier 随数据流传播，下游算子收到后暂停处理
3. 算子把当前状态快照保存到持久化存储（HDFS/S3）
4. Barrier 继续传播到下一个算子
5. 所有算子完成快照后，Checkpoint 完成

**Barrier 对齐（Barrier Alignment）：**
- 当算子有多个输入流（如 join 操作）时，需要等待所有分区的 Barrier 都到达
- 先到的 Barrier 对应的流暂停处理（buffer 起来）
- 等所有 Barrier 到齐后，做快照，然后释放 buffer 恢复处理
- 代价是**增加延迟**（等待对齐的时间）
- Flink 1.11+ 支持 **unaligned checkpoints**（不对齐，适合背压场景）

### 2.5 Chandy-Lamport 分布式快照算法

Flink 的 checkpoint 实质上是 **Chandy-Lamport 分布式快照算法**的变体：

**算法核心：**

```
1. 协调者发送 Marker（Flink 中的 Barrier）到所有初始节点
2. 节点收到 Marker 后：
   a. 记录本地状态（当前进程状态 + 信道状态）
   b. 将 Marker 转发到所有下游节点
3. 所有节点记录完成后，全局快照完成
```

**关键性质：**
- **不暂停全局处理**——只有正在对齐的算子会阻塞，其他部分继续运行
- **一致性**——快照捕获的是一致全局状态（without cycles of partial states）
- **异步**——快照存储与数据处理并行

---

## 3. 时间语义与 Watermark

时间语义是流处理中最容易混淆也是最关键的概念。

### 3.1 三种时间

```
         日志记录       Kafka收到        Flink处理
       ──────●─────────────●───────────────●──────▶
        Event Time    Ingestion Time    Processing Time
        (事件时间)      (摄入时间)         (处理时间)
```

| 时间类型 | 定义 | 确定性 | 对乱序鲁棒性 |
|---------|------|--------|------------|
| **Event Time** | 数据实际发生的时间（嵌入在数据中） | 确定（已经发生） | 需要 Watermark 处理乱序 |
| **Ingestion Time** | 数据进入系统的时间（Source 打戳） | 大致确定 | 乱序小（网络延迟可控） |
| **Processing Time** | 算子处理数据的系统时钟 | 不确定 | 最差（取决于系统负载） |

**为什么 Event Time 重要？**
- 金融交易：以交易实际发生时间为准，不是系统处理时间
- IoT传感器：传感器可能离线后批量上报，处理时间远晚于事件时间
- 日志分析：服务器宕机恢复后重新发送日志

### 3.2 Watermark（水位线）

Watermark 是 **Event Time 进展的度量**，本质是一个时间戳断言：

> **"Watermark(t) 表示：不会再有任何事件时间 < t 的数据到达"**

```
时间轴（Event Time）：
                     Watermark
                        ↓
──┬──┬──┬──┬──┬──┬──┬──●──────────▶
  e1 e2 e3 e4 e5 e6 e7              （事件到达，按事件时间排列）
  
此时事件时间 < Watermark 的记录都已全部到达
```

**Watermark 的策略（Flink）：**

```python
# 固定延迟 Watermark
def watermark_strategy(max_out_of_orderness=5000):
    """假设最多乱序 5 秒"""
    def extract_watermark(event_time):
        return event_time - max_out_of_orderness
```

**实战中 Watermark 的产生：**
- **Periodic Watermark**：周期性（如每 200ms）根据当前最大事件时间生成 Watermark
- **Punctuated Watermark**：遇到特殊记录（如EOF标记）才生成

### 3.3 乱序数据处理

现实世界中，数据到达顺序和产生顺序不一致：

```
事件时间顺序：  1    2    3    4    5    6    7    8
实际到达顺序：  1    4    2    5    8    3    6    7
                ↑         ↑              ↑
               迟到      迟到           迟到
```

**处理乱序的三板斧：**

1. **Watermark**：系统知道有一个容忍窗口，在这个窗口内数据可以被接受
2. **Allowed Lateness（允许延迟）**：Watermark 触发窗口计算后，再等一段时间
3. **Side Output（侧输出）**：超出 allowed lateness 的数据发到侧输出流做特殊处理

```
场景：5秒的滑动窗口，Watermark延迟5秒，Allowed Lateness 2秒

事件时间 0  1  2  3  4  5  6  7  8  9  10 11 12
到达顺序 0  1  4  2  5  3  8  6  7  9 10    11
                   ↑     ↑     ↑
Watermark          -5    -4    -3   ...   (max_ts - 5)

窗口[0-5)：数据0,1,2,3,4 → Watermark=5时触发计算 → 输出结果
        迟到3 → 在allowedLateness(2秒)内 → 重新计算窗口[0-5)
```

---

## 4. Flink 核心架构

### 4.1 主从架构

```
┌─────────────────────────────────────────────────────┐
│                    JobManager                       │
│  ┌────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Scheduler  │  │Checkpoint│  │  ResourceMgr   │  │
│  │  (调度任务)  │  │Coordinator│  │  (资源管理/HA)  │  │
│  └────────────┘  └──────────┘  └────────────────┘  │
└────────────────────────┬────────────────────────────┘
                         │ RPC (Akka)
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ TaskManager  │  │ TaskManager  │  │ TaskManager  │
│ ┌───┬───┬───┐│  │ ┌───┬───┬───┐│  │ ┌───┬───┬───┐│
│ │S1 │S2 │S3 ││  │ │S4 │S5 │S6 ││  │ │S7 │S8 │S9 ││
│ └───┴───┴───┘│  │ └───┴───┴───┘│  │ └───┴───┴───┘│
└─────────────┘  └─────────────┘  └─────────────┘
```

| 组件 | 职责 |
|------|------|
| **JobManager** | 主节点，负责任务调度、Checkpoint 协调、故障恢复 |
| **TaskManager** | 工作节点，执行 Dataflow 算子、维护状态 |
| **Slot** | TaskManager 中的执行槽位，每个 Slot 执行一个 Task 线程 |

### 4.2 Slot（槽位）

- Slot 是 TaskManager 的最小资源单位（内存隔离，CPU共享）
- 每个 Slot 可以执行一个 Task（算子子任务）
- Slot 数量 = TaskManager 的任务并行度上限
- 同一 Job 的不同 Task 可以**共享 Slot**（Slot Sharing），前提是来自同一个 Job

### 4.3 算子链（Operator Chaining）

Flink 优化手段：**多个算子合并到一个任务中执行**。

```
无链优化：
  Source ─→ Map ─→ KeyBy ─→ Window ─→ Sink
  │Task1│  │Task2│  │Task3│  │Task4│   │Task5│
  每条记录需要 5 次序列化/反序列化 + 4 次网络传输

有链优化：
  Source ─→ Map ─→ KeyBy ─→ Window ─→ Sink
  │      Task1      ││      Task2      ││Task3│
  链内直接函数调用，零序列化开销
```

**链化条件：**
- 上下游算子之间是 One-to-One 转发（不是 KeyBy/Rebalance）
- 算子在同一个 Slot 内
- 算子有相同的并行度

### 4.4 容错机制

Flink 使用 **Checkpoint + 部分重启** 实现容错：

1. Checkpoint 定期保存所有算子的状态快照（见 2.4 节）
2. 故障时，JobManager 重启所有 TaskManager
3. 从最近的 Checkpoint 恢复状态
4. Source 从 Checkpoint 记录的位置重新消费数据

**Savepoint**：手动触发的 Checkpoint，用于版本升级、代码修改后的恢复。

---

## 5. 极简有状态流处理引擎实现

> 代码文件：`memory/learning/code/stream_processor.py`

### 5.1 设计概要

用 Python 实现一个单线程有状态流处理引擎，展示：

1. **Watermark 机制** — 固定延迟 + 周期性推进
2. **Keyed State** — 按 key 维护累计值
3. **滑动窗口** — 时间窗口聚合
4. **乱序数据处理** — 允许迟到数据重新计算
5. **三种处理语义模拟** — at-most-once / at-least-once / exactly-once

### 5.2 架构

```
StreamProcessor
├── Source (数据源/事件流)
│   └── Event: {key, value, event_time}
├── WatermarkGenerator (水位线生成)
│   └── 周期性: watermark = max_event_time - delay
├── WindowOperator (窗口算子)
│   ├── KeyedState (每个key独立维护)
│   └── SlideWindow (滑动窗口聚合)
└── Sink (输出/结果)
```

### 5.3 核心实现逻辑

```python
class StreamProcessor:
    def __init__(self, watermark_delay=5, window_size=10, window_step=5):
        self.watermark_delay = watermark_delay  # 允许的乱序延迟
        self.window_size = window_size
        self.window_step = window_step
        self.watermark = -float('inf')
        self.max_event_time = -float('inf')
        self.buffer = []  # 乱序缓冲区
        self.keyed_state = {}  # {key: {window_id: aggregated_value}}
```

### 5.4 关键流程

```
1. 每条事件到达 → 更新 max_event_time
2. 事件加入 buffer（可能乱序）
3. 周期性生成 Watermark = max_event_time - delay
4. Watermark 推进 → 触发窗口计算：
   - 找到所有结束时间 <= Watermark 且未计算的窗口
   - 从 buffer 中筛选窗口内数据
   - 按 key 聚合 → 输出结果
   - 标记窗口已计算
5. 迟到数据（事件时间 < Watermark）：在 allowedLateness 内触发窗口更新
```

### 5.5 处理语义模拟

| 语义 | 实现方式 |
|------|---------|
| **At-Most-Once** | 不维护任何状态，每次读到直接处理，丢就丢了 |
| **At-Least-Once** | 设置水位后只前推不后退，但产出结果不幂等 |
| **Exactly-Once** | 保持状态快照 + 幂等输出（用窗口+去重保证） |

### 5.6 运行示例

```
输入事件流（故意乱序）：
  Event("A", 10, 100)    # key=A, value=10, event_time=100
  Event("A", 20, 105)
  Event("B", 15, 102)
  Event("A", 5,  95)     # 乱序！事件时间95 < 之前的105
  Event("A", 30, 110)
  ... (更多数据)
  [Watermark推进到105] → 触发 [100,110) 窗口计算
  
输出结果：
  Window [100,110): A=30, B=15    (key聚合)
  迟到95：Window [90,100): A=5    (窗口更新)
```

---

## 总结

| 概念 | 核心要点 |
|------|---------|
| **流 vs 批** | 逐条低延迟 vs 批量高吞吐；三种处理语义 |
| **状态** | Keyed State / Operator State；内存/RocksDB 后端 |
| **Checkpoint** | Barrier对齐 + Chandy-Lamport快照 = Exactly-Once |
| **时间** | Event Time > Processing Time；Watermark 解决乱序 |
| **Flink** | JobManager ↔ TaskManager；Slot执行单元；算子链优化 |
| **乱序处理** | Watermark + Allowed Lateness + Side Output 三板斧 |

---

## 参考

- Flink 官方文档：Checkpoint、State、Time 机制
- Chandy, K.M. and Lamport, L., "Distributed Snapshots: Determining Global States of Distributed Systems" (1985)
- Google Dataflow Model (2015): Watermark 与乱序处理的理论基础
