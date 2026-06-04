# 分布式系统第10课：分布式计算框架（MapReduce & Spark）

> 学习日期：2025-07-17
> 核心主题：从 MapReduce 到 Spark 的分布式计算范式演进

---

## 一、MapReduce（Google, 2004）

### 1.1 核心思想

> 分治思想：把大规模数据处理抽象为 `Map` + `Shuffle` + `Reduce` 三个阶段的编程模型。

### 1.2 编程模型

```
Map:    (k1, v1) → list(k2, v2)
Shuffle: 分区 + 排序 + 合并（框架自动完成）
Reduce: (k2, list(v2)) → list(k3, v3)
```

**输入/输出约束：**
- **Map：** 对输入的每个 `<k1, v1>` 对，输出 0 到多个 `<k2, v2>` 中间键值对
- **Shuffle：** 对 Map 输出的中间键值对按 key 分区，每个分区内部按 key 排序、分组、合并
- **Reduce：** 对每个 key 及其对应的 value 列表，输出最终结果 `<k3, v3>`

### 1.3 经典案例：WordCount

```
输入文本 → Map: (行号, 文本) → (单词, 1) 的 list
       → Shuffle: 按单词分区排序合并 → (单词, [1,1,1,...])
       → Reduce: (单词, count) → 输出
```

### 1.4 执行流程详解

```
[输入文件分片]
       ↓
[Map Task] × N   ← 每个分片一个 Map
       ↓
[中间数据: 本地磁盘]
  (每个 Map 输出被分区函数分成 R 个分区，写入本地磁盘)
       ↓
[Shuffle]  ← 框架拉取：Reduce 从每个 Map 节点拉取属于自己的分区
  - 分区（Partitioning）
  - 排序（Sorting per partition）
  - 合并（Combining：可选，可提前在 Map 端做局部合并）
       ↓
[Reduce Task] × R
       ↓
[输出文件] × R  ← 最终输出到 GFS（或 HDFS）
```

### 1.5 容错机制

| 机制 | 说明 |
|------|------|
| **任务重试** | Worker 崩溃（心跳超时）→ Master 重新调度到另一个健康的 Worker |
| **Master 单点故障** | 原始 MapReduce 未解决（可做周期性 checkpoint） |
| **推测执行（Speculative Execution）** | 检测到慢任务（straggler）→ 在另一个节点启动备份任务，谁先完成取谁的结果 |
| **数据本地性** | 调度 Map 任务时优先在数据所在的节点执行（移动计算而非移动数据） |

### 1.6 关键设计原则

**数据本地性（Data Locality）：**
- HDFS 将文件分块（128MB）复制到多个节点
- Master 调度 Map Task 时，**优先选择数据所在的节点**，其次是同机架
- 核心理念：**把计算移动到数据所在的位置**——网络传输代码比传输数据便宜得多

**推测执行（Speculative Execution / Backup Task）：**
- 分布式系统中的"木桶效应"——一个慢任务拖慢整体进度
- Master 监控每个 Task 的进度，落后平均进度的某个阈值时，在空闲节点启动备份
- 谁先完成就杀死另一个，避免资源浪费

---

## 二、Spark 核心

### 2.1 RDD（Resilient Distributed Dataset）

> **RDD** = 弹性分布式数据集，是 Spark 最核心的抽象。

**三大特性：**
1. **不可变（Immutable）**：RDD 一旦创建不能修改，只能通过 transformation 生成新的 RDD
2. **分区（Partitioned）**：数据分布在集群的多个节点上
3. **可并行操作**：所有算子自动并行

**RDD 的两种创建方式：**
- 从外部存储读取（HDFS、HBase、本地文件等）
- 从已有 RDD 做 transformation（map、filter、flatMap 等）

### 2.2 窄依赖 vs 宽依赖

这是理解 Spark DAG 调度和容错的关键概念。

```
窄依赖（Narrow Dependency）:
  - 每个父 RDD 分区**最多**被一个子 RDD 分区使用
  - 例：map, filter, union, mapPartitions
  - 特点：可以**管道化**执行（pipelined），无需 Shuffle
  - 容错：只需重新计算丢失的分区

宽依赖（Wide Dependency / Shuffle Dependency）:
  - 每个父 RDD 分区可被**多个**子 RDD 分区使用
  - 例：groupByKey, reduceByKey, join（非 co-partitioned）
  - 特点：需要 **Shuffle**（跨节点数据重分布）
  - 容错：重新计算需要所有父分区
```

```
窄依赖示意图：
  [P1]──→[P1']      每个父分区对应一个子分区
  [P2]──→[P2']
  [P3]──→[P3']

宽依赖示意图：
  [P1]──→[P1'][P2'][P3']   每个父分区对应多个子分区
  [P2]──→[P1'][P2'][P3']   （需要 Shuffle 重新分配）
  [P3]──→[P1'][P2'][P3']
```

### 2.3 DAG 调度器（DAG Scheduler）

Spark 的核心调度机制，分为三步：

**Stage 划分算法：**
1. 从最后一个 RDD 开始反向遍历
2. 遇到**窄依赖**→合并到当前 Stage
3. 遇到**宽依赖**（Shuffle）→ 切分为新的 Stage
4. 每个 Stage 内部可**管道化执行**（narrow transformations 连续执行无需等待）

```
   textFile("hdfs://...")                     Stage 0
       │ flatMap                               │
       │ map          ← 全部窄依赖，管道化      │
       │ filter                                │
       ├────────────── ← groupByKey 触发 Shuffle ←-- Stage 边界
       │ reduceByKey                          Stage 1
       │ map                                  │
       └── 输出文件                              │
```

**Task 调度：**
- 每个 Stage 内部生成一批 Task（每个分区一个 Task）
- TaskScheduler 将 Task 分发到各 Executor 执行
- 失败重试：Task 失败自动重试（默认 4 次）

### 2.4 Lineage（血统图）

> **核心思想：** 根据 RDD 的血统图重新计算，而不是复制数据备份。

```
RDD_A (从 HDFS 读取)
   └── map() → RDD_B
         └── filter() → RDD_C
               └── groupByKey() → RDD_D
                     └── mapValues() → RDD_E
```

- 每个 RDD 都记录了它的**父 RDD 和变换函数**
- 当某个 RDD 分区丢失时，只需从血统图中找到它的祖先，重新计算丢失的那个分区
- **窄依赖**：重新计算 1 个父分区即可
- **宽依赖**：可能需要重新计算多个父分区（代价更大）

> 对比：MapReduce 容错需要重跑整个 Job，Spark 可以只重算丢失的分区。

### 2.5 Cache / Persist（缓存机制）

Spark 可以将 RDD 缓存到内存，避免重复计算。

**缓存级别：**

| 级别 | 含义 | 空间 | CPU | 内存压力 |
|------|------|------|-----|---------|
| `MEMORY_ONLY` | 内存缓存，不序列化 | 大 | 小 | 大 |
| `MEMORY_ONLY_SER` | 内存缓存，Java 序列化 | 小（压缩）| 大 | 中 |
| `MEMORY_AND_DISK` | 内存+磁盘 | 可溢出到磁盘 | — | 小 |
| `MEMORY_AND_DISK_SER` | 内存序列化+磁盘 | 最小 | 大 | 最小 |
| `DISK_ONLY` | 仅磁盘 | 最小 | N/A | 无 |

**为何重要：**
- 迭代算法（如 ML、PageRank）反复使用同一数据集
- 交互式查询（Ad-hoc 分析）
- 不使用 Cache 时，每次 action 都会从头计算

### 2.6 Spark 执行模式

```
Driver Program (main)
   ├── SparkContext
   │     ├── DAG Scheduler → 划分 Stage
   │     └── Task Scheduler → 分发 Task
   │
   └── Cluster Manager (Standalone / YARN / Mesos)
         ├── Executor 1 (Worker Node 1)
         │     ├── Task
         │     ├── Task
         │     └── Cache (Block Manager)
         ├── Executor 2 (Worker Node 2)
         │     ├── Task
         │     └── Cache ...
         └── ...
```

---

## 三、MapReduce vs Spark 对比

| 维度 | MapReduce | Spark |
|------|-----------|-------|
| **计算模型** | Map → Shuffle → Reduce（固定 2 阶段） | DAG（任意多阶段） |
| **中间结果** | 每次 Shuffle 必然**落盘**到 HDFS | 尽量**内存计算**，Shuffle 可选磁盘 |
| **编程接口** | Map + Reduce 两个接口 | RDD transformation + action 丰富 API |
| **迭代支持** | 差（每次迭代都要读写磁盘） | 好（内存缓存 RDD） |
| **交互式查询** | 不支持 | 支持（Spark SQL, DataFrame） |
| **实时流处理** | 不支持 | 支持（Spark Streaming） |
| **容错** | 重算整个 Job | Lineage 重算丢失的分区 |
| **数据本地性** | 同（思想一致） | 同（思想一致） |
| **推测执行** | 支持 | 支持 |
| **性能** | 磁盘 I/O 瓶颈 | 内存计算，快 10~100x |
| **语言** | Java | Scala, Java, Python, R |

### 核心差异总结

```
MapReduce:  落盘 → 落盘 → 落盘 → ...（每个中间步骤都写磁盘）
Spark:     [内存流水线] → 落盘（Shuffle）→ [内存流水线] → ...

MapReduce:  容错 = 重算整个 Job
Spark:      容错 = Lineage 增量重算丢失分区

MapReduce:  "用磁盘换简单"
Spark:      "用内存换速度"
```

---

## 四、Python 实现：简化分布式计算框架

详见代码文件：`code/distributed_compute.py`

### 功能说明

1. **MapReduce WordCount 模拟**
   - 输入：文本数据列表
   - Map 阶段：flatMap 分词 → map 生成 (word, 1)
   - Shuffle 阶段：分组 + 排序 key
   - Reduce 阶段：汇总求和

2. **Shuffle + Sort + Reduce 全流程**
   - 分区函数（hash partition）
   - 分区内排序
   - 分组合并

3. **容错重试模拟**
   - 随机模拟 Worker 故障
   - Master 检测到失败后重新调度 Task
   - 最多重试次数控制

### 架构设计

```
                        Master
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
   Worker[0]         Worker[1]         Worker[2]
   ┌───────┐         ┌───────┐         ┌───────┐
   │Task 0 │         │Task 2 │         │Task 1 │
   │(Map)  │         │(Map)  │         │(Map)  │
   ├───────┤         ├───────┤         ├───────┤
   │Task 0 │         │Task 1 │         │Task 2 │
   │(Reduce)│        │(Reduce)│        │(Reduce)│
   └───────┘         └───────┘         └───────┘
```

---

## 五、总结与思考

### 从 MapReduce 到 Spark 的演进逻辑

| 时间 | 系统 | 突破点 |
|------|------|--------|
| 2004 | MapReduce | 将分布式数据处理抽象为统一编程模型 |
| 2008 | HDFS + Hadoop | 开源实现，降低了大规模数据处理的门槛 |
| 2012 | Spark | DAG + 内存计算 + RDD 解决迭代问题 |

### 设计哲学对比

```
MapReduce 设计哲学：简单可靠
  - 编程模型极简（只有 2 个阶段）
  - 容错模型极简（重启整个 Job）
  - 依赖磁盘保证可靠

Spark 设计哲学：通用高效
  - DAG 表达任意计算图
  - 内存优先，磁盘为辅
  - Lineage 精确定位需要恢复的数据
```

### 实际工程中的权衡

1. **MapReduce 仍然有以下优势场景：**
   - 超大规模离线 ETL（对延迟不敏感）
   - 硬件资源有限（内存不足）时
   - 需要极强稳定性保障

2. **Spark 适合：**
   - 迭代计算（ML、Graph）
   - 交互式分析
   - 对延迟敏感的场景
   - 内存资源充足

### 学习要点回顾

- ✅ MapReduce 的三阶段模型：Map → Shuffle → Reduce
- ✅ 数据本地性：计算向数据移动
- ✅ 推测执行：备胎机制应对慢任务
- ✅ RDD 不可变、分区、可并行操作
- ✅ 窄依赖（管道化） vs 宽依赖（Shuffle 边界）
- ✅ DAG 调度器 Stage 划分原理
- ✅ Lineage 血统容错机制
- ✅ Cache/Persist 内存缓存
- ✅ MR vs Spark 的核心差异
- ✅ Python 实现 WordCount、Shuffle、容错重试

---

*本文为分布式系统学习笔记第 10 课。参考：Google MapReduce 论文 (Dean & Ghemawat 2004), Spark: Resilient Distributed Datasets (Zaharia et al. 2012)*
