# 第4课：分布式协调

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 分布式协调要解决的问题

- **配置管理**：所有节点获取同一份配置
- **服务发现**：服务在哪里，地址是什么
- **分布式锁**：多个节点互斥访问共享资源
- **Leader选举**：集群选出一个主节点
- **分布式队列**：任务分发

## 2. ZooKeeper

### 核心概念
- **ZNode**：树形结构的节点（类似文件系统目录）
  - 持久节点：创建后一直存在
  - 临时节点（Ephemeral）：创建它的session断开后自动删除
  - 顺序节点（Sequential）：名字带递增序号
  - 组合：持久顺序、临时顺序
- **Watch**：监听ZNode变化（通知机制）

### 数据模型
```
/zookeeper
  /config/db_url        ← 持久节点，存配置
  /servers/app01        ← 临时节点，代表在线服务
  /locks/resource_001   ← 临时顺序节点，用于分布式锁
  /election/master      ← 临时顺序节点，用于Leader选举
```

### Paxos & ZAB协议
- **Paxos**：分布式共识算法（难实现，只能证明正确性）
- **ZAB（ZooKeeper Atomic Broadcast）**：ZooKeeper专用共识协议
  - Leader写入Proposal → 广播给Follower → Quorum确认 → 提交
  - 崩溃恢复：选新Leader + 同步未提交事务

### 分布式锁实现（临时顺序节点）
```
1. 在 /locks/lock_ 下创建临时顺序节点
2. 获取 /locks/ 下所有子节点
3. 如果自己的序号最小 → 获得锁
4. 否则监听前一个节点，等它释放
5. 释放：删除自己的节点
```
- **优势**：公平锁（FIFO），不会惊群效应
- **羊群效应**：监听前一个节点而非所有节点

### Leader选举实现（临时顺序节点）
```
思路同分布式锁：谁序号最小谁是Leader
```

## 3. etcd（云原生ZooKeeper）

### vs ZooKeeper
| 特性 | ZooKeeper | etcd |
|------|-----------|------|
| 协议 | ZAB | Raft |
| 数据格式 | 字节数组 | Key-Value |
| API | 自定义 | gRPC |
| 存储 | 内存+快照 | Bbolt（持久化） |
| Watch | 有 | 有（流式） |
| 易用性 | 较差 | 良好 |
| 典型场景 | Hadoop/HBase/Kafka | Kubernetes |

### etcd核心（Raft协议）

Raft通俗解释：
1. **Leader选举**：Follower超时未收到心跳 → 变成Candidate → 投票 → 成为Leader
2. **日志复制**：Leader收到写入 → 追加到日志 → 复制到Follower → 多数确认 → 提交
3. **安全性**：选出的Leader一定拥有所有已提交日志
4. **成员变更**：两阶段（Joint Consensus）

```
三个角色：Leader（主） → Follower（从） → Candidate（候选）
Term（任期）：每次选举递增
心跳：Leader定期发AppendEntries RPC保活
```

## 4. 分布式锁——其他实现

### Redis RedLock
- 向多个Redis实例申请锁
- 多数(N/2+1)实例成功 → 获得锁
- 有争议（依赖时间假设，存在脑裂风险）

### 数据库悲观锁
```sql
SELECT ... FOR UPDATE;  -- 行级锁，但性能差
```

### 对比

| 方案 | 强一致 | 性能 | 可靠性 | 实现复杂 |
|------|--------|------|--------|---------|
| ZooKeeper锁 | ✅ | 中 | 高 | 中 |
| etcd + Raft | ✅ | 高 | 高 | 低（库封装好） |
| Redis RedLock | ⚠️（有争议） | 最高 | 中 | 中 |
| DB行锁 | ✅ | 低 | 中 | 低 |

## 5. 分布式队列

### ZooKeeper实现
```
/enqueue: 创建临时顺序节点
/dequeue: 取序号最小的节点
```

### 专业消息队列
Kafka/RocketMQ（见第5课）

## 6. 核心原则

1. **共识是分布式系统的基石** — 没有共识，就没有一致的数据视图
2. **ZooKeeper不存业务数据** — 只存元数据/配置/状态，数据量小但重要
3. **Leader是用来写不是用来读的** — 读可以走Follower（Follower可能读到旧数据）
4. **etcd = ZK + Raft + gRPC** — 云原生生态的首选
