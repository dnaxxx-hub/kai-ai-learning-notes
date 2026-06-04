# 数据库内核第7课：复制与分布式

> 日期：2026-05-11 | 实践代码：`code/db_kernel_07_replication_dist.py`

---

## 一、复制基础

### 1.1 三种复制模型

| 模型 | 延迟 | 一致性 | 写可用性 |
|------|------|--------|----------|
| 同步复制 | 高 | 强一致 | 低 |
| 异步复制 | 低 | 最终一致 | 高 |
| 半同步复制 | 中 | 多数一致 | 中 |

### 1.2 复制拓扑

```
主从 (Master-Slave):
  写入 → Master → Binlog → Slave1、Slave2...
  读取 → Slave（或 Master）

主主 (Multi-Master):
  Master1 ↔ Master2（冲突检测）
  
去中心化 (Raft/Paxos):
  Node1 ↔ Node2 ↔ Node3（共识算法）
```

### 1.3 Binlog 格式

| 格式 | 内容 | 特点 |
|------|------|------|
| STATEMENT | SQL 语句 | 简单但可能结果不同 |
| ROW | 修改的具体行 | 最安全 |
| MIXED | 根据情况自动选择 | 折衷 |

---

## 二、GTID（Global Transaction ID）

格式：`{server_uuid}:{transaction_id}`

```
M1-1, M1-2, M1-3, ...  ← 主节点分配
```

优势：
- 无需手动定位 binlog 位置
- 自动故障切换
- 避免重复执行

---

## 三、2PC（两阶段提交）

### 3.1 流程

```
协调者                    参与者
    │                        │
    ├── PREPARE ──────────→  │  (Phase 1)
    │   ←──────── YES/NO ──  │
    │                        │
    ├── COMMIT/ABORT ──────→ │  (Phase 2)
    │   ←──────── ACK ────  │
```

### 3.2 阻塞问题

如果协调者在 Phase 2 崩溃：
- 已 PREPARE 的参与者会阻塞（等待协调者恢复）
- 需要 3PC 或 PAXOS 来解决

---

## 四、Raft 共识算法

### 4.1 节点状态

```
Follower →（超时未收到心跳）→ Candidate →（获得多数票）→ Leader
```

### 4.2 核心流程

```
1. Leader Election：选举 Leader
2. Log Replication：Leader 复制日志到 Follower
3. Safety：保证同一个 term 只有一个 Leader
```

### 4.3 日志复制

```
Leader 收到客户端请求
  → 追加到本地日志（uncommitted）
  → 发送 AppendEntries RPC 到所有 Follower
  → 多数确认 → 提交（apply to state machine）
  → 通知 Follower 提交
```

---

## 五、分布式事务模型

### 5.1 Percolator（Google）
- 使用 2PC + 分布式锁
- 主锁 + 从锁机制
- 支持跨行事务（Bigtable 之上）

### 5.2 CockroachDB 模型
- 使用 Parallel Commits 优化 2PC
- 混合逻辑时钟（HLC）处理时间戳
- Write Intent = 未提交的写入

### 5.3 关键挑战

| 挑战 | 解决方案 |
|------|----------|
| 时钟同步 | HLC / TrueTime（Spanner） |
| 全局死锁 | 分布式死锁检测 |
| 读一致性 | Lease Read / Read Index |
| 网络延迟 | Pre-vote / Pipeline |

---

## 六、实践代码

`db_kernel_07_replication_dist.py` 包含：

| 模块 | 内容 |
|------|------|
| `Master / Slave` | Binlog 主从复制 |
| `Coordinator / Participant` | 2PC 两阶段提交 |
| `RaftNode / RaftCluster` | Raft 共识选举 + 日志复制 |
| `PercolatorTxn` | 分布式事务冲突检测 |

### 运行

```bash
python code/db_kernel_07_replication_dist.py
```
