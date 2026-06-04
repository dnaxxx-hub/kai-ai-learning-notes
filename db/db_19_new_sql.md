# NewSQL 架构三巨头：Spanner vs CockroachDB vs TiDB

## Google Spanner

### F1 架构
- **F1**: SQL 层(分布式 SQL 引擎 + 客户端协议转换)
- **Spanner**: 存储层(全球分布式 KV 存储 + 同步复制)
- 分离设计: F1 无状态可水平扩展；Spanner 负责强一致复制

### TrueTime
- 基于 GPS + 原子钟的全球时钟 API: `TT.now()` 返回 `[earliest, latest]`
- **Commit Wait**: 写入后等待 `TT.after(now().latest)`，保证所有 replica 的物理时钟已超过 commit timestamp
- 实现 **外部一致性** (External Consistency): 等价于可线性化 + 单调读

### 外部一致性
- 事务 A 在时间 t 提交 → 事务 B 在 t 之后开始 → B 一定能看到 A 的结果
- 使用 TrueTime 保证 commit timestamp 严格递增且跨数据中心顺序正确

## CockroachDB

### HLC (Hybrid Logical Clock)
- 物理时间 + 逻辑计数器；无需 GPS/原子钟
- 节点间 RPC 通信时捎带 HLC 时间戳自动同步
- 保证因果序: 如果 A 发生在 B 之前，则 HLC(A) < HLC(B)

### 事务模型
- **可序列化隔离**(默认): 使用 SerializableSnapshotIsolation + 写冲突检测
- **并行事务 (Parallel Commits)**: 写操作异步并行提交，减少 2PC 延迟
- 事务 aborted 后自动重试(客户端透明)

### 架构特点
- 每个节点对等(P2P gossip 组网)，无强 Leader；Range 自动分裂/合并
- KV 存储上构建 PostgreSQL 兼容 SQL

## TiDB

### PD (Placement Driver)
- 集群元数据管理 + 全局时间戳分配 (TSO 中心化时钟)
- Region 调度: 均衡负载、热点迁移、节点故障时补副本
- 支持 Placement Rules 配置数据位置约束(如跨 AZ 部署)

### TiKV
- 分布式 KV 存储，每个 Region = Raft Group (Multi-Raft)
- 数据按 Range 分片，Region 大小默认 96MB，自动分裂/合并

### TiFlash
- 列存副本 (Raft Learner，异步复制)
- 行列混合: TiKV (行存) + TiFlash (列存) 同集群

### 计算存储分离
- **TiDB Server**: 无状态 SQL 层(SQL 解析/优化/执行)；接收 MySQL 协议
- **TiKV/TiFlash**: 有状态存储层
- 独立扩缩容: SQL 层按 QPS 扩，存储层按数据量 + QPS 分别扩
