# 第3课：分布式计算

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 分布式计算模型

### 核心问题
- 数据太大，单机放不下
- 计算太慢，单机跑不完
- 失败是常态，必须容错

### 两种模式
- **数据并行（Data Parallelism）**：相同计算，不同数据分片（MapReduce、Spark）
- **任务并行（Task Parallelism）**：不同计算，相同/不同数据（DAG调度）

## 2. MapReduce

Google 2004年论文，开创性的大数据处理框架。

### 计算模型
```
Input → Map → Shuffle → Reduce → Output
```
- **Map**：处理输入键值对，生成中间键值对
- **Shuffle**：按Key分组，把所有相同Key的Value发到同一Reducer
- **Reduce**：对每个Key的Value列表做聚合

### WordCount示例
```python
def map(line):
    for word in line.split():
        emit(word, 1)

def reduce(word, counts):
    emit(word, sum(counts))
```

### 架构
```
Client ←→ JobTracker（主节点）
  ↓              ↓
TaskTracker — TaskTracker — TaskTracker
(工作节点)   (工作节点)   (工作节点)
```

### 容错
- **Task粒度容错**：失败的任务在其他节点重跑
- **推测执行（Speculative Execution）**：慢任务启动备份，谁先完成用谁
- **数据本地性**：尽量在数据所在的节点上调度任务

### 局限性
- 所有中间结果写磁盘（慢）
- Map和Reduce之间严格barrier
- 不适合迭代计算（ML训练）
- 不适合实时处理

## 3. Spark

改进MapReduce的DAG计算引擎。

### 核心抽象：RDD（Resilient Distributed Dataset）
- 只读、分区、可并行操作
- 血统（Lineage）：通过转换操作追溯数据来源
- 内存计算：中间结果优先放内存
- 惰性求值：transformation延迟，action触发

### RDD操作
```
Transformations（惰性）:
  map, filter, flatMap, groupByKey,
  reduceByKey, sortByKey, join, union
  
Actions（触发计算）:
  reduce, collect, count, first,
  take, saveAsTextFile
```

### WordCount对比
```python
# MapReduce: 两次写磁盘 + shuffle
# Spark: 一次shuffle，中间结果在内存
sc.textFile("input.txt") \
  .flatMap(lambda l: l.split()) \
  .map(lambda w: (w, 1)) \
  .reduceByKey(lambda a, b: a + b) \
  .saveAsTextFile("output")
```

### DAG调度
```
Stage 1                   Stage 2
flatMap → map     →     reduceByKey → save
   ↓        ↓              ↓
分区A    分区B          分区C(结果)
```

- **宽依赖（Shuffle）**：多个父分区被多个子分区依赖 → 需要shuffle
- **窄依赖**：一个父分区被一个子分区依赖 → 可流水线执行

### 内存管理
- 执行内存（shuffle/buffer）+ 存储内存（cache/RDD）
- 两者共享统一内存池，可动态调整

## 4. Flink（流式计算）

### 批 vs 流
```
批处理：数据有界，处理完出结果        （MapReduce/Spark Batch）
流处理：数据无界，持续处理不断输出结果   （Flink/Spark Streaming）
```

### Flink核心概念
- **DataStream**：无界数据流
- **窗口（Window）**：将无界流切分成有限块
  - 滚动窗口（Tumbling）：不重叠，每10s一次
  - 滑动窗口（Sliding）：可重叠，每5s一次，窗口10s
  - 会话窗口（Session）：不活动期间隔分组
- **时间语义**：
  - Event Time：事件实际发生时间（正确但需处理乱序）
  - Processing Time：处理机器的当前时间（简单但不准确）
- **水位线（Watermark）**：标记Event Time的进度，用于触发窗口计算

### Exactly-Once语义
- 分布式快照（Chandy-Lamport算法）
- 定期保存状态快照
- 失败时从最近快照恢复

### 处理模型对比

| 特性 | MapReduce | Spark | Flink |
|------|-----------|-------|-------|
| 处理模式 | 批 | 批/微批 | 流/批 |
| 中间结果 | 磁盘 | 内存(优先) | 内存 |
| 延迟 | 分钟级 | 秒级(微批) | 毫秒级(逐条) |
| Exactly-Once | 有 | 有 | 有 |
| 迭代计算 | 差 | 好 | 好 |
| 乱序处理 | 不支持 | 支持(结构化流) | 原生支持 |

## 5. DAG调度框架

通用DAG调度系统，用于工作流编排。

### 核心概念
- **DAG（有向无环图）**：节点=任务，边=依赖
- **拓扑排序**：确定任务执行顺序
- **任务调度器**：按依赖关系分配执行资源

### 调度策略
1. **贪心调度**：可执行的任务立即分配
2. **公平调度**：在作业间公平分配资源
3. **延迟调度**：等待数据本地性更好的节点

### 调度器实现要点
```python
class DAGScheduler:
    def submit(self, dag):
        ready = get_nodes_with_no_deps(dag)
        while ready:
            # 选择优先级最高的任务
            task = max(ready, key=priority)
            ready.remove(task)
            # 分配执行
            execute(task)
            # 更新ready队列
            for n in task.dependents:
                if all_deps_done(n):
                    ready.append(n)
```

## 6. 总结

| 框架 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| MapReduce | 简单、可靠、大规模 | 慢、不适合迭代 | ETL、日志分析 |
| Spark | 快、内存计算、统一API | 内存消耗大、延迟非极致 | ML、SQL、批处理 |
| Flink | 低延迟、Exactly-Once | 学习曲线陡峭 | 实时监控、欺诈检测 |
| DAG调度 | 灵活、可定制 | 非专门优化 | 工作流编排、ETL |
