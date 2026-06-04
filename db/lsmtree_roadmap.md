# 存储引擎（LSM-Tree）学习路线图

> 创建：2026-05-17
> 前置：数据库基础（B+Tree、ACID、MVCC）

## 范围

LSM-Tree 原理、B+Tree 对比、WAL、SSTable、Compaction 策略、LevelDB 源码。

## Roadmap

| # | 课程 | 状态 | 日期 |
|---|------|------|------|
| 1 | LSM-Tree 原理与设计动机 | ✅ | 05-17 |
| 2 | B+Tree vs LSM-Tree 深度对比 | ✅ | 05-17 |
| 3 | WAL、恢复与崩溃安全 | ✅ | 05-17 |
| 4 | SSTable 格式与编码 | ✅ | 05-17 |
| 5 | Compaction 策略深度解析 | ✅ | 05-17 |
| 6 | LevelDB 源码实战分析 | ✅ | 05-17 |

## 全部完成 🎉

LSM-Tree / 存储引擎 6/6 课收官。

## 后续方向

- **RocksDB 深度**：列族、Merge Operator、事务、PinnableSlice
- **LSM-Tree 写放大优化**：PeBBLeS / WiscKey / SlimDB 等论文
- **其他存储引擎**：WiredTiger、Bitcask、BTree v2 (SQLite)
- **量化系统集成**：用 RocksDB 做实时行情 tick 存储
