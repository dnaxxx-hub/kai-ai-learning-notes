# 第5课：消息队列

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 消息队列的作用

- **解耦**：生产者消费者不直接依赖
- **削峰填谷**：突发流量缓冲到队列，平滑处理
- **异步**：非核心操作异步处理（如发邮件）
- **广播**：一条消息多个消费者接收
- **可靠**：消息持久化，崩了也能恢复

## 2. 核心概念

### 消息模型

| 模型 | 一对多 |
|------|--------|
| 点对点（Queue） | 每条消息一个消费者消费 |
| 发布订阅（Topic） | 每条消息所有订阅者都收到 |

### 关键概念
- **Broker**：消息队列服务器
- **Producer**：消息生产者
- **Consumer**：消息消费者
- **Topic**：消息主题分类
- **Partition**：Topic的分区（并行度）
- **Offset**：消息在分区内的序号

## 3. Kafka

### 架构
```
Producer → Topic1-Partition0 (Leader) → Consumer Group A
           Topic1-Partition1 (Leader) → Consumer Group A
           Topic1-Partition2 (Leader) → Consumer Group B
              ↓(副本)
           Topic1-Partition0 (Follower) — 同步复制
           Topic1-Partition1 (Follower)
```

- **Partition**：Kafka的并行单位，每个分区是有序的
- **Consumer Group**：组内负载均衡消费，每条消息仅组内一个消费者处理
- **多Consumer Group**：实现发布订阅（每个Group都收到）

### 存储设计
```
Topic
  └── Partition（目录）
        └── Segment（文件段）
              ├── .log（消息数据）
              └── .index（偏移量索引）
              └── .timeindex（时间戳索引）
```

- **顺序写磁盘**：比随机写快1000倍
- **零拷贝**：磁盘→内核页缓存→socket→网卡（不需要经过应用内存）
- **日志段（Segment）**：分区再切段，每个段固定大小，可删除/压缩

### 生产端
- **ACKS配置**：
  - acks=0：发完不管（最快，可能丢）
  - acks=1：Leader确认就行（默认）
  - acks=all：所有副本确认（最安全最慢）
- **分区策略**：key哈希 / 轮询 / 自定义
- **批次发送**：攒一批再发（提高吞吐量）

### 消费端
- **At-least-once**：处理完后提交offset（可能重复）
- **Exactly-once**：事务+幂等生产者+消费者幂等处理
- **Rebalance**：Group内消费者增减时重新分配分区
  - Eager Rebalance：全部暂停重新分配（STW)
  - Cooperative：逐步重新分配（不停顿）

### 消费语义对比
| 语义 | 实现 | 代价 |
|------|------|------|
| At-most-once | 先提交offset再处理 | 可能丢 |
| At-least-once | 先处理再提交offset | 可能重复 |
| Exactly-once | 事务+幂等+原子提交 | 性能开销 |
| Exactly-Once(In Kafka) | 事务API + 幂等Producer | 生产端保证，消费端需自己幂等 |

## 4. RocketMQ

阿里开源的分布消息队列。

### 差异点
| 特性 | Kafka | RocketMQ |
|------|-------|---------|
| 延迟 | 中（微秒级） | 低（毫秒级） |
| 有序消息 | 分区内有序 | 全局有序/分区有序 |
| 延迟消息 | ❌ | ✅（18个等级） |
| 事务消息 | ✅（v0.11+） | ✅（两阶段提交） |
| 消息回溯 | ✅（按offset） | ✅（按时间） |
| 批量消息 | ✅ | ✅ |
| 协议 | 自定义TCP | 自定义TCP/HTTP |

## 5. 消息可靠投递

### 端到端保障

```
Producer → Broker → Consumer
   │          │         │
   └─ retries  └─ acks   └─ commit offset
```

- **Producer端**：重试+幂等ID
- **Broker端**：同步复制+ISR（In-Sync Replicas）
- **Consumer端**：业务处理后再提交offset

### 死信队列（DLQ）
- 消费失败的消息 → 移入DLQ
- 人工或自动重试

## 6. 分区机制深入

### 为什么分区
- 并行度：N个分区 = N个消费者并行消费
- 水平扩展：分区是存储的基本单元
- 顺序保证：**分区内有序，分区间无序**

### 分区分配算法
1. **RoundRobin**：轮询分配
2. **Range**：按范围分配
3. **Sticky**：尽量保留已有分配（减少变动）

## 7. 实战选型

| 场景 | 推荐 |
|------|------|
| 日志收集、监控数据 | Kafka（高吞吐） |
| 业务消息、订单处理 | RocketMQ（低延迟+事务） |
| 简单解耦 | Redis Pub/Sub（不持久） |
| 延迟/定时消息 | RocketMQ |
| IoT数据涌入 | Kafka（批量写入） |

## 8. 总结

```
消息队列本质是：
  生产者←[持久化缓冲区]→消费者

核心挑战：
  1. 顺序保证（分区内有序）
  2. 不丢不重（Exactly-Once）
  3. 高吞吐（顺序写+零拷贝+批次）
  4. 故障恢复（ISR + Rebalance）
```
