# 分布式系统 #9：Kafka 核心原理与高性能消息系统深度剖析

> 分布式系统深度课程 | 日期：2026-05-13
> 先行课：第5课（Kafka基础架构、Topic/Partition、Segment、生产者ACK、消费者组）
> 本课专注深度：存储引擎、可靠性、客户端机制、KRaft、运维调优、生产配置实战

---

## 目录

1. [副本机制与 ISR 深度](#1-副本机制与-isr-深度)
2. [生产端深度：幂等与事务](#2-生产端深度幂等与事务)
3. [消费端深度：Rebalance 协议与 Offset 控制](#3-消费端深度rebalance-协议与-offset-控制)
4. [高性能存储引擎](#4-高性能存储引擎)
5. [数据可靠性保证](#5-数据可靠性保证)
6. [KRaft：自研共识替代 ZooKeeper](#6-kraft自研共识替代-zookeeper)
7. [生产者/消费者配置实战](#7-生产者消费者配置实战)
8. [运维与调优](#8-运维与调优)
9. [Kafka + Flink 精确一次语义](#9-kafka--flink-精确一次语义)
10. [Kafka vs RocketMQ vs Pulsar 核心设计差异](#10-kafka-vs-rocketmq-vs-pulsar-核心设计差异)

---

## 1. 副本机制与 ISR 深度

### 1.1 Leader / Follower / ISR / OSR

```
Partition-0 (replication-factor=3)
┌──────────────────────────────────┐
│ Leader (Broker-1)   ← 读写入口   │
│ ISR: [Broker-1, Broker-2,       │
│       Broker-3]                  │
│ OSR: []                         │
│                                  │
│ Follower (Broker-2) ← 从Leader   │
│ Follower (Broker-3)   拉取同步    │
└──────────────────────────────────┘
```

**ISR (In-Sync Replicas)：** 与 Leader 保持同步的副本集合。同步标准由 `replica.lag.time.max.ms`（默认 30s）决定——Follower 在超时内未拉取最新消息，则被踢出 ISR → OSR。

**OSR (Out-of-Sync Replicas)：** 落后 Leader 过多的副本。OSR 中的副本**不会**参与 Leader 选举（默认配置下）。

**关键参数：**
- `replica.lag.time.max.ms` = 30000（Follower 最大落后时间，超过则移出 ISR）
- `unclean.leader.election.enable` = false（禁止 OSR 副本成为 Leader，保证不丢已确认数据）

**Leader 选举流程：**
```
1. Controller 检测到 Leader 所在的 Broker 宕机
2. Controller 从 ISR 中选第一个副本作为新 Leader
3. 如果 ISR 为空且 unclean.leader.election.enable=false → 分区不可用
4. 如果 ISR 为空且 unclean.leader.election.enable=true → 从 OSR 中选
   （此时可能丢数据，但分区可用）
```

### 1.2 Follower 拉取与副本同步协议

Follower 不是被动接收 Push，而是主动向 Leader 发起 `FetchRequest`：

```
Follower → Leader: FetchRequest(offset=1000)
Leader    → Follower: [msg(1000), msg(1001), ...] + 水位信息
```

**HW (High Watermark) 与 LEO (Log End Offset)：**

```
每个 Partition 维护：
  LEO = 最后一条消息的 offset + 1（本地日志末端）
  HW  = min(Leader.LEO, all ISR Follower.LEO)  → 消费者可见的最大 offset

示例：
  Leader LEO = 10
  Follower-1 LEO = 10
  Follower-2 LEO = 8
  HW = min(10, 10, 8) = 8
  
  → offset 0-7 对消费者可见
  → offset 8-9 已写入 Leader 但未全部同步完
```

**ACK=all 的完整流程：**
```
1. Producer → Leader 写入 offset=5
2. Follower-1 拉取 offset=5, LEO=6
3. Follower-2 拉取 offset=5, LEO=6
4. Leader 检测所有 ISR LEO ≥ 6 → HW 推进到 6
5. Leader 返回 ACK 给 Producer
6. offset=5 对消费者可见
```

---

## 2. 生产端深度：幂等与事务

### 2.1 幂等生产者 (enable.idempotence=true)

**核心机制：PID + Sequence Number**

```
Producer 初始化 → Broker 分配 Producer ID (PID)
每个 Partition 维护一个序列号（从 0 开始递增）
Producer 发送每条消息携带 (PID, Partition, SeqNum)
Broker 端去重：若收到重复的 (PID, Partition, SeqNum) → 丢弃
```

**限制：**
- 单 PID 单会话内有效（Producer 重启后 PID 重新分配）
- 跨会话无法去重 → 需要事务
- `max.in.flight.requests.per.connection` 必须 ≤ 5（Kafka 3.0+ 已自动处理）

### 2.2 事务性生产者

**架构组件：**

```
Transaction Coordinator（事务协调器）：
  - 每个 Producer 对应一个 TC（通过 transaction_id 哈希确定）
  - 存储事务状态到 __transaction_state topic
  - 管理事务生命周期

流程：
1. initTransactions() → Producer 注册 transaction_id，获取 PID
2. beginTransaction() → 本地标记事务开始
3. send(record) → 发送数据到目标 Partition
4. sendOffsetsToTransaction() → 消费-处理-生产模式中提交 offset
5. commitTransaction() / abortTransaction()
   → TC 协调两阶段提交：
     a. PREPARE_COMMIT → 写入事务日志
     b. COMMIT → 写入事务 marker 到每个 Partition
```

**事务隔离级别：**
```
isolation.level = read_committed:
  消费者过滤掉未提交的事务消息（通过 LSO - Last Stable Offset）
  LSO = 第一个未完成事务开始的 offset
  消费者只能读到 < LSO 的数据（所有事务已提交或中止）

isolation.level = read_uncommitted（默认）:
  读到所有消息（包括未提交的）
```

**事务 + 幂等的关系：**
```
enable.idempotence=true   → 单个会话内去重
transactional.id 设置后   → 跨会话容错 + 原子跨分区写入
幂等是事务的"子集"——开启事务自动开启幂等
```

---

## 3. 消费端深度：Rebalance 协议与 Offset 控制

### 3.1 GroupCoordinator 与 ConsumerCoordinator

```
Consumer Group "my-group" 的协调架构：
                                    ZooKeeper/KRaft
                                        │
GroupCoordinator (Broker 中的一个模块)   │
  ├── 管理组成员（心跳 + 成员列表）      │
  ├── 管理 __consumer_offsets topic      │
  ├── 触发 Rebalance                     │
  └── 分配分区                           │
                                        │
ConsumerCoordinator (Consumer 客户端）    │
  ├── 心跳 → GroupCoordinator            │
  ├── JoinGroup → 参与 Rebalance         │
  └── SyncGroup → 接收分区分配结果        │
```

**协调协议（简化）：**

```
正常运行时：
  Consumer → GroupCoordinator: Heartbeat(metadata)
  GroupCoordinator → Consumer: HeartbeatResponse

Rebalance 触发：
  1. 新 Consumer 加入 / 旧 Consumer 超时 / Partition 数变化
  2. GroupCoordinator 标记组为 "PreparingRebalance"
  3. 下次心跳时 Consumer 收到 "REBALANCE_IN_PROGRESS"

Rebalance 流程（新版 Cooperative 协议）：
  1. JoinGroup — 所有 Consumer 发送分区订阅信息
  2. GroupCoordinator 选举 Leader Consumer（第一个加入的）
  3. Leader Consumer 执行分区分配算法
  4. SyncGroup — 所有 Consumer 拉取分配结果
```

### 3.2 StickyAssignor vs EagerAssignor vs CooperativeStickyAssignor

| 分配器 | 协议 | 再平衡方式 | 停顿时间 |
|--------|------|-----------|---------|
| RangeAssignor | Eager | 全部 Stop-the-world | 全部 |
| RoundRobinAssignor | Eager | 全部 Stop-the-world | 全部 |
| StickyAssignor | Eager | 尽量维持已有分配 | 全部但重分配少 |
| CooperativeStickyAssignor | Cooperative | 分阶段，只动必要分区 | 局部 |

**CooperativeStickyAssignor 的分阶段协议：**

```
阶段 1：
  所有 Consumer 上报已分配分区
  Leader Consumer 计算"变动集合"（需要从哪迁移到哪）
  返回 → Consumer 释放这些分区（revoke）

阶段 2（等所有 Consumer 完成释放后）：
  重新 JoinGroup + SyncGroup
  被释放的分区分配给新的 Consumer
  未变化的分区完全不受影响
```

**生产建议：`partition.assignment.strategy=CooperativeStickyAssignor` 或 `StickyAssignor`**

### 3.3 Offset 提交深度

**自动提交的陷阱：**
```
enable.auto.commit = true
auto.commit.interval.ms = 5000

问题场景：
  1. Consumer poll() 获得 records
  2. 处理过程中 crash
  3. 5s 后该 Consumer 重新加入组（或同 group 其他 consumer）
  4. offset 已自动提交 → 消息丢失！
```

**手动提交最佳实践：**
```java
// Java 示例
while (true) {
    ConsumerRecords records = consumer.poll(Duration.ofMillis(1000));
    for (ConsumerRecord record : records) {
        process(record);  // 处理完再提交
    }
    consumer.commitSync();  // 同步提交（阻塞，保证成功）
    // 或 consumer.commitAsync((offsets, exception) -> {
    //     if (exception != null) retry...
    // });
}
```

**三种语义保证：**

| 语义 | 实现方式 | 风险 |
|------|---------|------|
| at-most-once | 先提交 offset，再处理消息 | 处理失败则消息丢失 |
| at-least-once | 先处理消息，再提交 offset | 可能重复处理 |
| exactly-once | 处理结果 + offset 原子提交（事务） | 实现复杂，性能开销 |

---

## 4. 高性能存储引擎

### 4.1 PageCache + 顺序写

Kafka 写入磁盘的速度≈内存写入速度，关键在于：

```
传统随机写入（MySQL InnoDB）：
  磁盘寻道 ~10ms + 旋转 ~4ms + 传输 ~0.1ms = ~14ms/I/O

Kafka 顺序写入：
  磁盘顺序写 ~200MB/s（HDD） ~2000MB/s（SSD）
  无寻道开销（类似日志 append-only）
```

**PageCache 的魔法：**

```
Producer → Socket → Broker Network Thread
                    ↓
              Request Queue
                    ↓
              I/O Thread
                    ↓  （写入 PageCache，立即 ACK）
              OS PageCache
                    ↓  （异步刷盘，由 pdflush/flusher 决定）
              Physical Disk (.log segment)

关键：消息先写到 PageCache（内存），由 OS 决定何时刷盘
参数：flush.messages 和 flush.ms（建议保持默认=不主动刷盘，依赖 OS）
```

**为什么 Kafka 不主动 fsync？**
- PageCache 命中率高：刚写的数据很可能会再次读取
- OS 的 I/O 调度 + 电梯算法比应用层更高效
- 副本机制本身提供数据安全保障（ACK=all + 多副本）

### 4.2 零拷贝 (Zero-Copy)

**传统 4 次拷贝方案：**

```
磁盘 → PageCache （DMA 读）
PageCache → 应用缓冲区 （CPU 拷贝）
应用缓冲区 → Socket Buffer （CPU 拷贝）
Socket Buffer → NIC Buffer （DMA 写）
合计：2 次 DMA + 2 次 CPU 拷贝，4 次上下文切换
```

**Kafka 的零拷贝（sendfile）：**

```
磁盘 → PageCache （DMA 读）
PageCache → NIC Buffer （DMA 写，由 DMA 引擎直接从 PageCache 到网卡）
合计：2 次 DMA，0 次 CPU 拷贝
```

**Java 实现：**
```java
// FileChannel.transferTo() → 内核调用 sendfile()
FileChannel fileChannel = new RandomAccessFile("segment.log", "r").getChannel();
fileChannel.transferTo(position, count, socketChannel);
```

**性能收益：** 零拷贝使 Kafka 在消费场景几乎达到网卡带宽上限（对比传统方案消耗大量 CPU）

### 4.3 索引文件的深入结构

```
.log 文件（数据）：
  [offset=0, len=100] [offset=1, len=80] [offset=2, len=120] ...

.index 文件（稀疏索引，每 4KB 数据建一条索引）：
  offset=0 → position=0
  offset=4 → position=300
  offset=8 → position=620

查找 offset=5：
  1. 二分查找 .index → 找到 offset=4, position=300
  2. 从 .log 的 position=300 开始顺序扫描
  3. 找到 offset=5（最多扫描 4KB 数据）
  → 每次查找约 2-8 次 I/O

.timeindex 文件（时间戳索引）：
  timestamp=1000000 → offset=0
  timestamp=2000000 → offset=4
  timestamp=3000000 → offset=8

按时间戳查找：
  1. 二分 .timeindex → 找到最大时间戳 ≤ 目标时间的记录
  2. 获取对应 offset
  3. 用 .index 定位 .log 中的物理位置
```

### 4.4 压缩与批量

**压缩：生产者端配置 `compression.type`**

| 压缩算法 | CPU 开销 | 压缩比 | 备注 |
|---------|---------|-------|------|
| gzip | 高 | 极高 | CPU 敏感场景慎用 |
| snappy | 低 | 中等 | 推荐，平衡之选 |
| lz4 | 低 | 中等 | 比 snappy 略快，相似压缩比 |
| zstd | 中 | 高 | Facebook 出品，Kafka 3.0+ 推荐 |

**批量发送机制：**

```
batch.size = 16384 (16KB)
linger.ms = 0

生产流程：
  1. Producer 累计消息到 batch（按目标 Partition 分桶）
  2. 两个触发条件：
     a. batch 填满 → 立即发送（batch.size 阈值）
     b. linger.ms 超时 → 即使不饱满也发送
     
Trade-off:
  batch.size ↑  → 吞吐 ↑（更大批量，更少请求）
  linger.ms  ↑  → 延迟 ↑（等更久才凑够 batch）
  
经验值：
  追求吞吐：batch.size=32-64KB, linger.ms=5-10
  追求低延迟：batch.size=16KB, linger.ms=0
```

---

## 5. 数据可靠性保证

### 5.1 ACK 与 min.insync.replicas 组合

```
ACK=all 不保证绝对不丢！还要配合 min.insync.replicas

场景：复制因子=3，ISR=2，min.insync.replicas=2
  → Producer 写入时要求至少 2 个 ISR 副本确认
  → 如果 ISR 只剩 1 个（另外两个挂了或落后）→ 写入失败（NotEnoughReplicasException）

配置组合：
┌────────────────────┬────────────────────┬──────────────────┐
│ acks               │ min.insync.replicas │ 可靠性           │
├────────────────────┼────────────────────┼──────────────────┤
│ 1                  │ —                  │ 可能丢（Leader挂）│
│ all                │ 1                  │ ISR全挂时丢      │
│ all                │ 2 (复制因子≥3)     │ 安全（容忍1副本挂）│
│ all                │ 复制因子数        │ 最安全但最脆弱    │
└────────────────────┴────────────────────┴──────────────────┘
```

### 5.2 unclean.leader.election.enable

```
设置 = false（默认，推荐生产）：
  当 Leader 挂且 ISR 全部挂 → 分区不可用
  直到最后一个 ISR 副本恢复上线
  保证：已 ACK 的数据绝不会丢

设置 = true：
  Leader 挂 → 从 OSR（数据可能不全）中选新 Leader
  分区可用，但数据可能丢失（落后太多的 Follower 当 Leader）
  适合：高可用 > 数据一致性的场景

生产建议：
  使用 ACK=all + min.insync.replicas=2 + unclean.leader.election=false
  → 此时整个集群在"多数副本存活"前提下保证不丢数据
```

---

## 6. KRaft：自研共识替代 ZooKeeper

### 6.1 为什么弃用 ZooKeeper

- ZK 的强一致性不适合 Kafka 高吞吐元数据场景
- 双集群架构（Kafka + ZK）运维复杂
- ZK 的 read/write 模型限制 Kafka Controller 扩展
- 单点瓶颈——Controller 故障切换依赖 ZK

### 6.2 KRaft 设计

**KRaft != Raft：Kafka 自研的 Raft 变体**

```
Raft 标准：Leader 处理所有写入，日志复制到 Follower
KRaft 变体：
  ├── 使用 Quorum 机制（多数派确认）
  ├── 元数据存储为 Event Log（而不是状态机）
  ├── 支持 Controller 与 Broker 分离 / 合并部署
  └── 选举算法与 Raft 相同但状态机是 Kafka 元数据
```

**架构变化：**

```
旧架构（ZooKeeper）：
  Broker → ZooKeeper（元数据 + Controller 选举）
  Controller 将元数据分发到其他 Broker

新架构（KRaft）：
  Controller Quorum（配置 3 或 5 个节点）
  ├── Active Controller（类似 Raft Leader）
  ├── Standby Controller（类似 Raft Follower）
  ├── Observer Controller（只读，不参与投票）
  └── 元数据写入 __cluster_metadata log → Quorum 复制
```

**KRaft 优势：**
- 减少一个外部依赖（ZK）
- 元数据变更延迟降低（从 ZK 几十 ms 到 KRaft 几 ms）
- 支持更多分区（ZK 限制约 20 万分区，KRaft 可支持 100 万+）
- 单节点元数据管理更简洁

### 6.3 迁移与现状

- **Kafka 2.8** — KRaft 预览（仅元数据，生产不推荐）
- **Kafka 3.3** — KRaft 生产就绪（KIP-833）
- **Kafka 4.0** — 计划移除 ZooKeeper 依赖

---

## 7. 生产者/消费者配置实战

### 7.1 高吞吐生产端配置

```properties
# 高吞吐生产端配置
bootstrap.servers=broker1:9092,broker2:9092,broker3:9092
acks=all
enable.idempotence=true
compression.type=zstd
batch.size=65536            # 64KB batch
linger.ms=10                # 最多等 10ms
buffer.memory=134217728     # 128MB 发送缓冲区
max.request.size=1048576    # 1MB 最大消息
retries=2147483647          # Integer.MAX_VALUE（无限重试）
retry.backoff.ms=100        # 重试间隔
max.in.flight.requests.per.connection=5
request.timeout.ms=30000
delivery.timeout.ms=120000  # 最长 2min 投递
```

### 7.2 低延迟生产端配置

```properties
# 低延迟生产端配置（如金融交易类场景）
bootstrap.servers=broker1:9092,broker2:9092,broker3:9092
acks=all
enable.idempotence=true
compression.type=none       # 压缩引入延迟
batch.size=16384            # 16KB 小 batch
linger.ms=0                 # 立即发送
buffer.memory=67108864      # 64MB
max.in.flight.requests.per.connection=1  # 严格 FIFO
request.timeout.ms=5000
delivery.timeout.ms=15000
```

### 7.3 生产级消费端配置

```properties
# 生产级消费端配置
bootstrap.servers=broker1:9092,broker2:9092,broker3:9092
group.id=payment-service-v2
enable.auto.commit=false                    # 手动提交
isolation.level=read_committed              # 只读已提交事务消息
auto.offset.reset=earliest                  # 新 group 从最早开始消费
fetch.min.bytes=1                           # 有一个 byte 就返回
fetch.max.wait.ms=500                       # 最多等 500ms
max.poll.records=500                        # 一次 poll 最多 500 条
max.poll.interval.ms=300000                 # 两次 poll 最大间隔 5min
max.partition.fetch.bytes=1048576           # 单分区拉取 1MB
session.timeout.ms=45000                    # session 超时 45s
heartbeat.interval.ms=15000                 # 心跳间隔 15s
partition.assignment.strategy=\
  org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

**关键参数说明：**

| 参数 | 作用 | 调优建议 |
|------|------|---------|
| `fetch.min.bytes` | 最少拉取字节数 | 提高吞吐：设大（如 1MB）；降低延迟：设小（1） |
| `fetch.max.wait.ms` | 最大等待时间 | 与 fetch.min.bytes 配合：先满足任一条即返回 |
| `max.poll.records` | 单次 poll 最大条数 | 防止处理超时导致 rebalance；根据处理耗时调整 |
| `max.poll.interval.ms` | 两次 poll 最大间隔 | 超过则认为消费者 dead → rebalance |
| `session.timeout.ms` | 心跳超时 | 网络不稳时适当加大（30-60s） |

---

## 8. 运维与调优

### 8.1 分区副本分配策略

**无感知分配（默认）：**
```
分区 0 → [Broker-1, Broker-2, Broker-3]
分区 1 → [Broker-2, Broker-3, Broker-1]
分区 2 → [Broker-3, Broker-1, Broker-2]
```

**Rack 感知分配：**
```
rack 1: Broker-1, Broker-2
rack 2: Broker-3, Broker-4

分区 0：Leader=Broker-1(rack1), Follower=Broker-3(rack2)
分区 1：Leader=Broker-2(rack1), Follower=Broker-4(rack2)
→ 副本分散在不同机架，容忍机架级故障
```

**Leader 再平衡：**
```
auto.leader.rebalance.enable=true
leader.imbalance.per.broker.percentage=10
# 当 Broker 上 Leader 数量偏差超过 10% 时触发重新均衡
```

### 8.2 日志清理策略

**delete（默认）：基于时间和大小删除**

```
log.cleanup.policy=delete
log.retention.hours=168    # 保留 7 天
log.retention.bytes=-1     # 不限制大小
log.segment.bytes=1073741824  # 1GB 滚 Segment
log.retention.check.interval.ms=300000  # 5min 检查一次
```

**compact：Log Compaction（基于 Key 保留最新值）**

```
log.cleanup.policy=compact
min.cleanable.dirty.ratio=0.5    # 脏数据 > 50% 时触发 compact
# 典型场景：用户画像、配置数据、状态变更表
```

**compact 的工作方式：**

```
Before compact:
  offset 0: key=user1, value=Alice
  offset 1: key=user2, value=Bob
  offset 2: key=user1, value=Alice_v2   ← 覆盖
  offset 3: key=user3, value=Charlie
  offset 4: key=user2, value=Bob_v2     ← 覆盖

After compact:
  offset 2: key=user1, value=Alice_v2   ← 保留最新
  offset 3: key=user3, value=Charlie
  offset 4: key=user2, value=Bob_v2     ← 保留最新
```

### 8.3 关键监控指标

| 指标 | MBean | 健康阈值 | 含义 |
|------|-------|---------|------|
| UnderReplicatedPartitions | kafka.server:type=ReplicaManager | =0 | 存在同步落后分区 |
| ActiveControllerCount | kafka.controller:type=KafkaController | =1 | 异常：>1（脑裂）或 =0（无Controller） |
| RequestQueueSize | kafka.network:type=RequestChannel | <1000 | 请求队列积压 |
| TotalTimeMs (p99) | kafka.server:type=BrokerTopicMetrics | <100ms | Broker 端处理延迟 |
| BytesInPerSec | kafka.server:type=BrokerTopicMetrics | 吞吐量基线 ±20% | 流量突增/突降告警 |
| OfflinePartitions | kafka.controller:type=KafkaController | =0 | 分区副本全部不可用 |
| ISRShrinkRate | kafka.server:type=ReplicaManager | 接近0 | ISR 频繁缩小 → 集群不稳定 |

### 8.4 集群容量规划

**分区数上限：**
```
单台 Broker 推荐分区数：5000-10000（具体取决于硬件）
限制因素：
  ┌────────────────────┬──────────────────────────┐
  │ 限制因素           │ 说明                     │
  ├────────────────────┼──────────────────────────┤
  │ 文件句柄数         │ 每个分区 3 文件（log/index/timeindex）× 副本数 │
  │ Controller 压力    │ Leader 选举 + 元数据操作   │
  │ 内存               │ 每个分区约 1MB 元数据      │
  │ Rebalance 时间     │ 分区越多 rebalance 越长    │
  └────────────────────┴──────────────────────────┘
```

**吞吐量估算：**

```
单条消息 1KB，100 万 msg/s → ~1GB/s 吞吐

磁盘吞吐要求：
  写入：= 生产吞吐 × 复制因子
  读取：= 消费吞吐（可能追上写入）
  合计：约 2-3× 生产吞吐

网络带宽要求：
  写入带宽 = 生产吞吐（压缩前）
  读取带宽 = 消费吞吐 × 消费者组数
  复制带宽 = 生产吞吐 × (复制因子 - 1)
  合计：写入 + 读取 + 复制 → 一般为 3-5× 生产吞吐

经验公式：
  所需服务器数 = max(生产吞吐MB/s / 单台写吞吐,
                     (生产吞吐 + 消费总吞吐 + 复制流量) / 单台网卡带宽)

  例：生产 500MB/s，复制因子 3，消费 300MB/s，
      单台磁盘顺序写 500MB/s，网卡 10Gbps
      → 磁盘瓶颈: 500/(500/3) ≈ 3台
      → 网络瓶颈: (500 + 300 + 1000) × 8/10000 ≈ 1.5台
      取 max → 至少 3 台
```

---

## 9. Kafka + Flink 精确一次语义

### 9.1 端到端精确一次架构

```
Flink Job 启用 checkpointing:

Kafka Source (read_committed)
    │
    │ Flink 算子（带状态）
    │ checkpoint 时保存 offset + 状态
    │
Kafka Sink (两阶段提交 Sink)

FlinkKafkaProducer 用 Semantic.EXACTLY_ONCE:
  ├── preCommit() → 开启事务（checkpoint 开始时）
  ├── commit()   → 提交事务（checkpoint 完成时）
  └── abort()    → 回滚事务（checkpoint 失败时）
```

### 9.2 配置示例

```java
// Flink Kafka Source — 支持 Exactly-Once
FlinkKafkaConsumer<String> source = new FlinkKafkaConsumer<>(
    "input-topic",
    new SimpleStringSchema(),
    props
);
source.setStartFromLatest();
source.setCommitOffsetsOnCheckpoints(true);  // Checkpoint 时提交 offset

// Flink Kafka Sink — Exactly-Once
FlinkKafkaProducer<String> sink = new FlinkKafkaProducer<>(
    "output-topic",
    new SimpleStringSchema(),
    props,
    FlinkKafkaProducer.Semantic.EXACTLY_ONCE   // 启用两阶段提交
);

// Checkpoint 配置
env.enableCheckpointing(60000);         // 每 60s 一次 checkpoint
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30000);
env.getCheckpointConfig().setCheckpointTimeout(120000);
env.getCheckpointConfig().enableExternalizedCheckpoints(
    CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION
);
```

### 9.3 精确一次的代价

```
开启事务 vs 不开启事务的性能影响：
┌─────────────┬──────────────┬─────────────┐
│              │ 无事务        │ 精确一次事务  │
├─────────────┼──────────────┼─────────────┤
│ 吞吐         │ 100%         │ 70-85%      │
│ 延迟（p99）  │ 100ms        │ 200-300ms   │
│ Broker 负载  │ 低           │ 中（事务日志）│
└─────────────┴──────────────┴─────────────┘

经验：
  - 大部分业务场景使用 at-least-once（幂等去重即可）
  - 仅在跨多个 Topic 的原子写入场景使用精确一次事务
  - 启用事务后 checkpoint 间隔不宜过短（建议 ≥ 60s）
```

---

## 10. Kafka vs RocketMQ vs Pulsar 核心设计差异

### 10.1 架构核心理念

| 维度 | Kafka | RocketMQ | Pulsar |
|------|-------|----------|--------|
| **存储模型** | 分布式日志（本地磁盘） | 本地磁盘（CommitLog + ConsumeQueue） | 计算存储分离（BookKeeper 集群） |
| **消费模型** | Pull 模式 | Pull 模式（长轮询优化） | Push + Pull 结合（Broker 做中转） |
| **高可用** | Leader/Follower + ISR | Master/Slave + DLedger（Raft） | 分段存储 + 自动恢复（BookKeeper） |
| **消息模型** | Topic → Partition → Segment | Topic → MessageQueue → ConsumeQueue | Topic → Partition → Ledger |
| **延迟消息** | 不支持原生（需自实现） | 原生支持（18个等级） | 原生支持 |
| **死信队列** | 需手动配置 DLT | 自带死信队列 | 自带 |
| **消息过滤** | Broker 端不支持，需 Consumer 端 | Broker 端支持 Tag/Key 过滤 | Broker 端支持 |
| **优先级** | 不支持 | 不支持 | 消费延迟区分（部分支持） |
| **多租户** | 弱（靠 Topic 命名空间模拟） | 弱 | 原生多租户（Namespace 隔离） |
| **地域复制** | MirrorMaker / MM2 | 需自建 | 原生跨地域复制 |
| **客户端语言** | Java 为主，多语言生态成熟 | Java 优先 | Java 为主，多语言全面 |
| **运维复杂度** | 中 | 中 | 高（组件多） |

### 10.2 关键设计差异详解

**1. 存储模型：本地 vs 分层**

```
Kafka：数据在 Broker 本地磁盘，顺序写 + PageCache
  Pros：极简架构，全链路零拷贝
  Cons：Broker 故障需重新同步数据

Pulsar：数据在 BookKeeper（独立存储集群），Broker 无状态
  Pros：Broker 故障无数据再同步，弹性扩缩
  Cons：多一次网络跳转，反熵复杂

RocketMQ：CommitLog 统一写入 + ConsumeQueue 逻辑索引
  Pros：读写分离，消费性能好
  Cons：CommitLog 文件巨大，冷数据回收复杂
```

**2. 消费模型差异**

```
Kafka：每个 Consumer 拉取多个 Partition
  问题：单 Partition 只能由一个 Consumer 消费
  解法：增加 Partition → 增加并行度

RocketMQ：Consumer 通过 PullRequest 拉取 MessageQueue
  改进：支持长轮询（类似 Push 的延迟）
  特性：支持广播消费

Pulsar：Consumer 订阅 Partition
  改进：支持 Exclusive/Failover/Shared/Key_Shared 四种订阅模式
  Shared：多个 Consumer 共享 Partition 内的消息（非严格有序）
  Key_Shared：按 Key 分组到不同 Consumer
```

**3. 一致性协议**

```
Kafka：自研 Leader/Follower + ISR（不做 Paxos/Raft，通过 min.insync 保证）
RocketMQ：DLedger（Raft 实现）用于主从切换
Pulsar：BookKeeper（基于 Quorum + ZK 的 WAL 协议）
```

**4. 性能对比（典型压测）**

```
单机单 Topic、3 副本、1KB 消息：

              Kafka        RocketMQ      Pulsar
写入 (msg/s)  ~1,500,000   ~700,000     ~1,000,000
延迟 p99      ~5ms         ~3ms         ~8ms
消费 (msg/s)  ~3,000,000   ~1,000,000   ~1,500,000

注：具体性能因硬件、配置、场景差异很大
```

**5. 选型建议**

| 场景 | 推荐 | 原因 |
|------|------|------|
| 日志/埋点/事件总线 | Kafka | 高吞吐、堆积能力强 |
| 金融交易、订单 | RocketMQ | 原生态消息支持、事务成熟 |
| 云原生/多租户 | Pulsar | 计算存储分离、弹性好 |
| IoT 边缘 | Pulsar | 地域复制、分层存储 |
| 简单消息、中小规模 | RabbitMQ | 轻量、路由灵活 |

---

> **延伸阅读：**
> - [KIP-500] Replace ZooKeeper with Self-Managed Metadata Quorum
> - [KIP-848] New Consumer Group Protocol
> - [Kafka 官方文档] Exactly Once Semantics
> - 《Kafka: The Definitive Guide》 第 5-8 章
