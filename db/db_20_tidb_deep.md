# 数据库 #20：TiDB 深度

## 整体架构（计算存储分离）
```
SQL Layer (TiDB Server) — 无状态 SQL 层
    ↓
PD (Placement Driver) — 元数据 + 时间戳分配
    ↓
TiKV 节点 (行存, Raft)    TiFlash 节点 (列存, Raft Learner)
```
- TiDB：MySQL 兼容，SQL 解析/优化/执行
- PD：集群管理、Region 调度、TSO 分配
- TiKV：行存 KV 引擎（RocksDB + Raft），按 Region 分片
- TiFlash：列存副本，Raft Learner（异步复制）
- HTAP：同一份数据，行存 OLTP + 列存 OLAP

## Percolator 事务模型
- Google Percolator 论文实现
- 乐观事务：先执行后冲突检查
- Big 3 列：lock / write / data（每个 key 三个 CF）
- Primary Lock 机制：一个事务的一个 key 作为主锁
- 冲突检测：写写冲突回滚，读写由 MVCC 版本读

## Region 分片与调度
- 默认每 96MB 自动分裂
- 各 Region 独立 Raft group
- PD 根据 store 负载 + 容量调度 Region 迁移
- 热点检测：读写 hot key 自动分裂/迁移

## 在线 DDL
- TiDB 并行 DDL 框架
- 不阻塞读写
- Schema 版本管理 + lease

## Coprocessor 下推
- 支持下推：聚合(count/sum/avg)、过滤(WHERE)、索引查询
- 下推不了：复杂 Join、排序、子查询

## TiFlash
- 列存，HTAP 查询自动路由到 TiFlash
- Raft Learner 异步复制，最终一致
- 适合大范围分析查询
