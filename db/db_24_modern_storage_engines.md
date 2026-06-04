# 数据库 #24：现代存储引擎

## LSM-Tree 深度（RocksDB）
```
内存：MemTable (跳表) → 写满变 Immutable
                           ↓ flush
磁盘：SSTable 层级 (L0→L1→L2→...) → 每层容量指数增大

写：直接写 MemTable + WAL （顺序写，极快）
读：MemTable → L0 → L1 → ...（可能有多次 I/O）
Compaction：后台合并 SSTable（写放大问题）
```

### RocksDB 调优参数
```cpp
Options options;
options.write_buffer_size = 64 * 1024 * 1024;      // MemTable 大小
options.max_write_buffer_number = 3;                // 最大 MemTable 数
options.target_file_size_base = 64 * 1024 * 1024;  // SSTable 大小
options.level_compaction_dynamic_level_bytes = true; // 动态 level 大小
```

## B+Tree vs LSM-Tree 对比

| 特性 | B+Tree | LSM-Tree |
|------|--------|----------|
| 写入吞吐 | 低（随机写 + 页分裂）| 高（顺序写 + WAL）|
| 读取速度 | 高（定位准确）| 低（多层合并）|
| 写放大 | ~2-5x | ~10-30x（可调）|
| 空间放大 | 低 | 高（过期数据待合并）|
| 适合场景 | OLTP 读多写少 | 日志/时序/写多读少 |

## WiredTiger（MongoDB）
- B-Tree + LSM 混合引擎
- 默认 B-Tree（支持压缩、前缀压缩）
- 可选 LSM 模式（写入密集型场景）
- 行锁级别并发

## 选型矩阵

| 场景 | 推荐引擎 | 原因 |
|------|----------|------|
| 高并发 OLTP | B+Tree（InnoDB） | 读快 |
| 时序/日志 | LSM-Tree（RocksDB） | 写快 |
| 混合负载 | WiredTiger | 可配置 |
| 大键值对 | LSM-Tree | 写入友好 |
