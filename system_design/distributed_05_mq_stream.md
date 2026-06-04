# 第5课：消息队列与流处理

> 分布式系统核心课程 | 日期：2026-05-12
> 学习目标：理解消息队列核心模型、Kafka 架构深入、流处理概念及主流 MQ 对比

---

## 目录

1. [消息队列核心模型](#1-消息队列核心模型)
2. [Kafka 架构深入](#2-kafka-架构深入)
3. [流处理概念](#3-流处理概念)
4. [消息队列对比](#4-消息队列对比)
5. [Python 代码实现](#5-python-代码实现)

---

## 1. 消息队列核心模型

### 1.1 点对点（Queue）vs 发布订阅（Topic）

| 模型 | 点对点（Queue） | 发布订阅（Topic） |
|------|-----------------|-------------------|
| 消费者关系 | 竞争消费 | 订阅模式 |
| 消息路由 | 一条消息 -> 一个消费者 | 一条消息 -> 所有订阅者 |
| 典型代表 | RabbitMQ Queue | Kafka Topic |
| 示例场景 | 任务分发、负载均衡 | 日志广播、事件通知 |

**点对点模型：**
```
Producer --> [Queue] --> Consumer1
                      --> Consumer2 (不会收到同一消息)
```

**发布订阅模型：**
```
Producer --> [Topic]
            /    |    \
         Sub1  Sub2  Sub3  (每个消费者组都会收到)
```

**实现对比：**

| 特性 | Queue | Topic |
|------|-------|-------|
| 消息消费后是否删除 | 是（删除确认） | 否（保留 / 可重放） |
| 消费进度管理 | Broker 端 | 消费者端（Offset） |
| 水平扩展 | 加 Queue 实例 | Topic 分区（Partition） |
| 顺序保证 | 单 Queue 有序 | 单 Partition 有序 |

### 1.2 Push vs Pull 模型

| 维度 | Push 模型 | Pull 模型 |
|------|-----------|-----------|
| 实时性 | 高（Broker 主动推送） | 中（消费者轮询） |
| 消费者压力 | 可能被压垮（背压问题） | 控制节奏（自主拉取） |
| Broker 复杂度 | 需维护推送状态 | 简单（只存不推） |
| 适用场景 | 低延迟、小规模 | 高吞吐、大规模 |
| 典型代表 | RabbitMQ（部分实现） | Kafka |
| 流量控制 | 难（Broker 决定） | 易（消费者决定） |

**Push 模型问题：**
- 慢消费者导致 Broker 内存堆积
- Broker 需要跟踪消费者状态
- 网络拥塞时难以调节

**Pull 模型优势：**
- 消费者自主控制拉取速率
- 批量拉取提升吞吐
- Broker 实现简洁

---

## 2. Kafka 架构深入

### 2.1 Topic / Partition / Offset

```
Topic: "orders"
┌──────────────────────────────────────┐
│ Partition-0                          │
│ ┌─────┬─────┬─────┬─────┬─────┬────┐│
│ │ M0  │ M1  │ M2  │ M3  │ M4  │ M5 ││
│ │off0 │off1 │off2 │off3 │off4 │off5││
│ └─────┴─────┴─────┴─────┴─────┴────┘│
│ Partition-1                          │
│ ┌─────┬─────┬─────┬─────┬─────┬────┐│
│ │ M0  │ M1  │ M2  │ M3  │ M4  │ M5 ││
│ └─────┴─────┴─────┴─────┴─────┴────┘│
│ Partition-2                          │
│ ┌─────┬─────┬─────┬─────┬─────┬────┐│
│ │ M0  │ M1  │ M2  │ M3  │ M4  │ M5 ││
│ └─────┴─────┴─────┴─────┴─────┴────┘│
└──────────────────────────────────────┘
```

**核心概念：**

- **Topic** — 消息的逻辑分类（类似数据库的表）
- **Partition** — Topic 的分片单位，每个 Partition 是一个有序不可变的消息序列
- **Offset** — 消息在 Partition 内的唯一序号（单调递增）
- **Leader / Follower** — 每个 Partition 有多个副本，Leader 处理读写，Follower 同步

**分区数选择经验：**
- 分区数 ≤ Broker 数 × 副本因子
- 分区数影响：并行度、文件句柄数、Leader 选举时间
- 经验值：建议每分区吞吐量 10MB/s，根据总吞吐估算

### 2.2 生产者：分区策略 + ACK 级别

**分区策略：**

| 策略 | 方式 | 特点 |
|------|------|------|
| 轮询（Round-Robin） | 均匀分配到各分区 | 负载均匀，无序 |
| Key 哈希 | hash(key) % numPartitions | 相同 key 到同一分区 |
| 自定义分区器 | 实现 Partitioner 接口 | 灵活控制 |
| 粘性分区（Sticky） | 先填满 batch 再切分区 | 高吞吐 |

**ACK 级别：**

```
acks = 0       ─── 发送即算成功（可能丢数据）
acks = 1       ─── Leader 写入成功即 ACK（默认）
acks = all(-1) ─── 所有 ISR 副本写入成功才 ACK
```

| ACK 级别 | 延迟 | 吞吐 | 安全 |
|----------|------|------|------|
| 0 | 最低 | 最高 | 可能丢数据（Leader 崩溃） |
| 1 | 低 | 高 | Leader 写成功，Follower 未同步可能丢 |
| all | 高 | 低 | 最安全（容忍 Follower 故障） |

**生产者重试机制：**
```python
# 幂等生产者（enable.idempotence=true）
# 自动处理：网络重传导致的消息重复
# 保证：至少一次 + 去重 = 精确一次
props = {
    'bootstrap.servers': 'localhost:9092',
    'acks': 'all',
    'enable.idempotence': True,
    'retries': 3,
    'max.in.flight.requests.per.connection': 5,
}
```

### 2.3 消费者：消费者组 + 再平衡（Rebalance）

**消费者组模型：**
```
Topic: "orders" (3 partitions)
Consumer Group: "order-service"
                    │
    ┌──────────────┼──────────────┐
    │              │              │
 Partition-0  Partition-1  Partition-2
    │              │              │
 Consumer-A    Consumer-B    Consumer-C
（一个 Partition 只能被组内一个消费者消费）
```

**分配策略：**

| 策略 | 方式 | 特点 |
|------|------|------|
| Range（默认） | 按主题范围分配 | 分区数不均匀时可能倾斜 |
| RoundRobin | 轮询分配 | 负载均衡，需订阅相同 Topic |
| Sticky | 尽可能保持现有分配 | 再平衡影响最小 |
| Cooperative（合作式） | 增量再平衡 | 分阶段，减少 Stop-The-World |

**再平衡（Rebalance）触发条件：**
1. 消费者加入或离开组
2. Topic 分区数变化
3. 消费者心跳超时（session.timeout.ms）

**再平衡协议演进：**
```
Eager Rebalance（旧版）:
  所有消费者停止消费 --> 全体重新分配 --> 恢复消费
  (Stop-The-World，影响大)

Cooperative Rebalance（新版）:
  识别需要调整的分区 --> 只重新分配受影响分区
  (增量再平衡，影响小)
```

**Offset 管理：**
```python
# 自动提交（默认）
enable.auto.commit = True
auto.commit.interval.ms = 5000

# 手动提交（推荐生产环境）
def consume():
    records = poll()
    process(records)
    commit_sync()  # 或 commit_async()
```

### 2.4 日志存储：Segment + 索引文件

**Segment 文件结构：**
```
Partition 目录：topic-0/
├── 00000000000000000000.log       # 第一个 Segment（数据文件）
├── 00000000000000000000.index     # 偏移量索引
├── 00000000000000000000.timeindex # 时间戳索引
├── 00000000000000234567.log       # 第二个 Segment
├── 00000000000000234567.index
├── 00000000000000234567.timeindex
└── leader-epoch-checkpoint
```

**日志写入流程：**
```
1. Producer → Leader Partition
2. 追加到当前活跃 Segment（.log 文件）
3. 更新索引（.index + .timeindex）
4. Follower 从 Leader 拉取同步
5. 达到 ACK 条件后返回
```

**Segment 滚动条件：**
- 文件大小达到 `log.segment.bytes`（默认 1GB）
- 时间达到 `log.roll.hours`（默认 7天）
- 索引文件满（`log.index.size.max.bytes`）

**索引文件格式：**
```
.index（稀疏索引）:
  offset 0 → position 0
  offset 4 → position 2048
  offset 8 → position 4096
  ...

查找 offset=5:
  1. 二分查找索引: 4 ≤ 5 ≤ 8
  2. 从 position 2048 开始顺序扫描
  3. 找到 offset=5 的消息位置
```

**清理策略：**
| 策略 | 说明 | 参数 |
|------|------|------|
| delete | 删除过期 Segment | retention.ms, retention.bytes |
| compact | 保留每个 Key 的最新值 | cleanup.policy=compact |

---

## 3. 流处理概念

### 3.1 事件时间 vs 处理时间

```
                  事件发生    到达系统    处理完成
                   │          │          │
事件时间 ──────────┘          │          │
摄取时间 ──────────────────────┘          │
处理时间 ──────────────────────────────────┘
```

| 时间概念 | 含义 | 特点 |
|----------|------|------|
| 事件时间（Event Time） | 事件实际发生的时间 | 不可变，但可能乱序到达 |
| 摄取时间（Ingestion Time） | 消息到达系统的时间 | 由系统分配，单调递增 |
| 处理时间（Processing Time） | 算子处理记录的时钟时间 | 易变，依赖系统负载 |

**事件时间的重要性：**
- 反映业务真实时间线
- 对离线/实时结果一致性至关重要
- 数据重放时事件时间不变

### 3.2 Watermark / 窗口

**Watermark（水位线）：**
```
事件时间轴：
──┬──────┬──────┬──────┬──────┬──────┬───►
  E1(1s) E2(3s) E3(2s) E4(4s) E5(5s) E6(3s)
                              ▲
                        水位线=4s
                   （保证 ≤4s 的事件已到达）

含义：水位线 = max(已观察到的事件时间) - 允许延迟
用途：触发窗口计算，处理乱序事件
```

**Watermark 策略：**
```python
# 周期性 Watermark（每 N ms 更新一次）
# 常用：BoundedOutOfOrderness
WatermarkStrategy
    .forBoundedOutOfOrderness(Duration.ofSeconds(5))
    .withTimestampAssigner((event, timestamp) -> event.eventTime)
```

**三种窗口类型：**

```
1. Tumbling Window（滚动窗口）—— 固定大小，不重叠
   [0s, 10s)  [10s, 20s)  [20s, 30s)  ...
   适用于：每10s统计一次

2. Sliding Window（滑动窗口）—— 固定大小，有重叠
   size=10s, slide=5s
   [0s, 10s)
      [5s, 15s)
         [10s, 20s)
   适用于：平滑统计（如移动平均）

3. Session Window（会话窗口）—— 按活动间隔分组
   gap=5s（超时5s关闭会话）
   事件: A---B---C         D---E
   会话: [会话1]          [会话2]
   适用于：用户行为分析
```

**窗口触发时机（Event Time 下）：**
1. Watermark 超过窗口结束时间
2. 允许迟到的元素更新窗口（allowedLateness）
3. 最终清理（Watermark > 窗口结束 + allowedLateness）

### 3.3 Exactly-Once 语义

| 语义 | 含义 | 实现代价 |
|------|------|----------|
| At-Most-Once | 最多一次（可能丢） | 最低 |
| At-Least-Once | 至少一次（可能重复） | 中 |
| Exactly-Once | 精确一次（不丢不重） | 最高 |

**Kafka Exactly-Once 实现：**

```
生产者端：
  enable.idempotence=true
  ─── 通过 Producer ID + 序列号去重

事务性写入：
  事务协调器 + 事务日志
  原子提交多个 Partition

流处理（Kafka Streams）：
  原子写入 + 状态存储
  消费-处理-生产的 EOS 闭环
```

**关键机制：**
1. **幂等生产者** — 使用 PID + seq 编号去重
2. **事务** — `BEGIN -> WRITE -> COMMIT/ABORT` 原子化
3. **消费者事务隔离** — `isolation.level=read_committed` 只读已提交

---

## 4. 消息队列对比

| 维度 | Kafka | Pulsar | RabbitMQ | RocketMQ |
|------|-------|--------|----------|----------|
| **诞生** | LinkedIn → Apache | Yahoo → Apache | Rabbit → VMware | 阿里巴巴 → Apache |
| **消息模型** | Topic + Partition | Topic + Partition | Queue / Exchange | Topic + Queue |
| **存储模型** | 本地日志文件 | 计算/存储分离（BookKeeper） | 内存/磁盘 | 本地文件 |
| **消费模型** | Pull | 兼容 Push/Pull | Push（Consumer 也支持 Pull） | Pull |
| **吞吐** | 极高（百万/s） | 高（百万/s） | 中（万级/s） | 高（十万级/s） |
| **延迟** | 中（ms 级） | 低（ms 级） | 极低（μs 级） | 低（ms 级） |
| **消息顺序** | 单分区有序 | 单分区有序 | 单队列有序 | 单队列有序 |
| **消息堆积** | 强（磁盘堆积） | 强 | 弱 | 强 |
| **死信队列** | 需配置 DLT | 自带 | 自带 | 自带 |
| **延迟消息** | 需实现 | 自带 | 插件支持 | 自带 |
| **重试机制** | 消费者重试 | 自带 | 自带 ACK 重试 | 自带重试队列 |
| **事务消息** | 支持 | 支持 | 支持 | 支持 |
| **多租户** | 弱 | 强（原生） | 弱 | 弱 |
| **运维复杂度** | 中 | 高（多组件） | 低 | 中 |

### 选型建议

| 场景 | 推荐方案 |
|------|----------|
| 日志收集 / 埋点数据 | Kafka（高吞吐、堆积能力强） |
| 金融交易 / 需强一致 | Pulsar / RocketMQ（事务支持好） |
| 微服务异步调用 | RabbitMQ（低延迟、灵活路由） |
| 流处理 / ETL | Kafka + Kafka Streams / Flink |
| IoT / 边缘计算 | Pulsar（计算存储分离、地域复制） |
| 订单 / 支付等业务 | RocketMQ（事务消息成熟） |

### 架构对比示意图

```
Kafka 架构：
Producer → Broker (Partition Log) → Consumer
           ├── Partition-0
           ├── Partition-1
           └── Partition-2

Pulsar 架构：
Producer → Broker → BookKeeper (存储层)
         └── 元数据 → ZooKeeper
Consumer ← Broker ← BookKeeper (读取)

RabbitMQ 架构：
Producer → Exchange → Binding → Queue → Consumer
           ├── Direct
           ├── Topic
           ├── Fanout
           └── Headers

RocketMQ 架构：
Producer → NameServer → Broker (CommitLog + ConsumeQueue) → Consumer
           ├── Master
           └── Slave (读写分离)
```

---

## 5. Python 代码实现

本实现包含：
1. **简化版 Kafka 分区日志存储** — Segment 文件模拟、索引查找、Partition 追加
2. **消费者组再平衡模拟** — Range / RoundRobin / Sticky 策略实现

### 运行代码

```bash
python memory/learning/distributed_05_mq_stream.py
```
