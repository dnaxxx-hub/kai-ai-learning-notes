# 数据库内核 — 路线图

## 8课全景

| 课时 | 主题 | 核心内容 |
|:----:|------|----------|
| 1 | 存储引擎 | 行存/列存/页管理/Buffer Pool/WAL/Checkpoint |
| 2 | B+树与LSM-Tree | 分裂/合并/并发B-Link Tree/Leveled+Tiered Compaction |
| 3 | 事务与MVCC | ACID/隔离级别/快照读/可见性检查/事务ID |
| 4 | 锁与并发 | 行锁/间隙锁/意向锁/死锁检测/2PL |
| 5 | 查询执行 | Volcano/向量化/HashJoin/SortMerge/物化 |
| 6 | 查询优化 | CBO/统计信息/基数估计/JoinOrder/DPccp |
| 7 | 复制与分布式 | 主从/Gtid/Raft/2PC/Percolator/CockroachDB |
| 8 | 迷你DB | Parser→Binder→Optimizer→Executor→Storage (Python) |

## 进阶路径

### 存储深度
- 新型存储介质（Optane/ZNS SSD）适配
- 压缩算法（ZSTD/Brotli/字典压缩）
- 自动VACUUM与GC策略

### 分布式数据库
- Calvin/Percolator事务模型
- 全局死锁检测
- 跨DC复制与时钟同步

### 查询优化
- 基数估计（直方图/采样/Sampling-based）
- Learned Cost Model
- ML驱动的索引推荐

## 推荐学习顺序
- 第1-2课存储打底，第3-4课并发控制，第5-6课查询处理
- 第7课理解分布式，第8课是动手实践
- 配合 CMU 15-445 课程使用更佳
