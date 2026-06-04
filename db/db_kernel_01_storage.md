# 数据库内核第1课：存储引擎

> 日期：2026-05-11 | 实践代码：`code/db_kernel_01_storage_engine.py`

---

## 一、存储模型

### 1.1 行存（Row-Oriented / NSM）

N-ary Storage Model：一条记录的所有属性连续存放。

```
Row: [id:1, name:Alice, age:30, salary:5000]
```

**优点**：点查快（WHERE id=42），整行更新高效
**缺点**：聚合查询需读取大量无用列
**场景**：OLTP（MySQL InnoDB、PostgreSQL）

### 1.2 列存（Column-Oriented / DSM）

Decomposition Storage Model：同一列的所有值连续存放。

```
Column 'salary': [5000, 5200, 4800, ...]
Column 'name':   [Alice, Bob, Charlie, ...]
```

**优点**：聚合查询只扫描需要列，压缩比高（同类型数据）
**缺点**：点查需多次离散读取，写开销大
**场景**：OLAP（ClickHouse、Parquet）

### 1.3 混合存（PAX / Hybrid）

垂直分区组合，取折衷。

---

## 二、页管理

数据库的最小 I/O 单位通常是**页（Page）**，典型大小 4KB ~ 16KB。

```
┌─────────────────────┐
│ Page Header (24B)   │ ← page_id, lsn, free_offset, checksum
├─────────────────────┤
│ Record Slots        │ ← 槽数组（指针/长度）
├─────────────────────┤
│ Free Space          │
├─────────────────────┤
│ Record Data         │ ← 实际数据（从底部向上生长）
└─────────────────────┘
```

### 页内查找策略
- **Slotted Page**：每行一个 slot 指向数据，删除只需标记
- **Append-Only**：新数据追加，旧的用 Tombstone 标记

---

## 三、Buffer Pool

缓冲池管理内存中的页副本，减少磁盘 I/O。

### 核心数据结构
```
Page Table: page_id → Page (内存中的副本)
Free List:  空闲页帧
LRU List:   最近使用顺序（实现 LRU/K-Clock 淘汰）
```

### 关键操作
- **Pin/Unpin**：并发控制，引用计数
- **Dirty Flag**：脏页标记，刷盘后清除
- **Flush**：将脏页写回磁盘
- **Evict**：淘汰策略（LRU、LRU-K、CLOCK）

### Page 生命周期
```
DISK → (Read) → IN_MEMORY → (Modified) → DIRTY → (Flush) → CLEAN → (Evict) → DISK
```

---

## 四、WAL（Write-Ahead Log）

WAL 是实现事务持久性和崩溃恢复的核心机制。

### 基本原则：WAL 日志必须先于数据页刷盘

### STEAL vs NO-FORCE
| 策略 | Buffer Pool | 提交时 | 恢复 |
|------|-------------|--------|------|
| STEAL + NO-FORCE (主流) | 允许未提交事务的脏页刷盘 | 不需刷脏页 | Redo + Undo |
| NO-STEAL + FORCE | 禁止未提交脏页出池 | 需刷所有脏页 | 只需 Redo |
| STEAL + FORCE | 允许未提交脏页 | 需刷脏页 | 只需 Undo |

### 日志格式
```
[LSN | PrevLSN | TxnID | Type | PageID | Offset | OldData | NewData]
```

### 恢复过程（ARIES 算法）
1. **Analysis Phase**: 扫描日志找到 dirty_pages 和 active_txns
2. **Redo Phase**: 从最早的 checkpoint 开始重放，使数据恢复到崩溃前
3. **Undo Phase**: 回滚未提交事务（从最新 LSN 反向扫描）

---

## 五、Checkpoint

检查点用于截断 WAL，加速恢复。

### Fuzzy Checkpoint
- 不阻塞正常操作
- 记录 active_txn 快照和 dirty_pages
- 周期性执行

### Mini-Checkpoint（MySQL InnoDB）
- 每次刷一批脏页
- Adaptive Flushing: 根据 Redo Log 生成速率动态调整

---

## 六、综合理解

存储引擎层是数据库的基石：

```
SQL → Parser → Optimizer → Executor → Storage Engine
                                         ├── Buffer Pool （内存加速）
                                         ├── B+ Tree    （索引加速）
                                         ├── WAL        （持久保证）
                                         └── Checkpoint （恢复加速）
```

### 关键 Trade-offs

| 维度 | 选型 | 典型引擎 |
|------|------|----------|
| 存储模型 | 行存 | InnoDB, Heap File |
| 存储模型 | 列存 | ClickHouse, Redshift |
| 并发控制 | MVCC | InnoDB, PostgreSQL |
| 持久策略 | STEAL+NO-FORCE | 主流引擎 |
| 淘汰算法 | LRU-K | InnoDB |
| 页大小 | 16KB | InnoDB |

### 实践代码

配套代码 `db_kernel_01_storage_engine.py` 演示了：
1. 行存 vs 列存模型
2. 页结构管理（Page Header + Record Layout）
3. Buffer Pool 带 LRU 淘汰
4. WAL 日志 + Redo/Undo 恢复
5. Mini 存储引擎整合示例

运行：`python code/db_kernel_01_storage_engine.py`
