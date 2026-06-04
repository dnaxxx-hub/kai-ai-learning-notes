# 数据库存储引擎：行存/列存/页管理/Buffer Pool/WAL

## 一、存储模型概览

数据库存储引擎的核心任务是在磁盘和内存之间高效地组织数据。不同的存储模型决定了不同的访问模式性能。

### 1.1 行存（Row-Oriented / N-ary Storage Model, NSM）

行存将完整的一行数据连续存储。这是 OLTP（在线事务处理）场景的首选。

**结构示意**：
```
Page 1: [Row1:id, name, age | Row2:id, name, age | Row3:id, name, age]
```

**优点**：
- 单行读写高效：一次 I/O 即可读取整行
- 插入友好：追加一行直接写入
- 适合 Point Query：SELECT * FROM users WHERE id=?

**缺点**：
- 扫描全表读取大量列时浪费 I/O
- 不适合聚合查询（只需要少数列）

**代表数据库**：MySQL InnoDB、PostgreSQL（默认）、SQLite

### 1.2 列存（Column-Oriented / Decomposition Storage Model, DSM）

列存将同一列的数据连续存储。这是 OLAP（在线分析处理）场景的首选。

**结构示意**：
```
Page 1: [id_1, id_2, id_3, ...]  ← id 列
Page 2: [name_1, name_2, name_3, ...]  ← name 列
Page 3: [age_1, age_2, age_3, ...]  ← age 列
```

**优点**：
- 只读取查询需要的列，大幅减少 I/O
- 同一列数据类型相同，压缩率极高（Run-Length Encoding, Delta Encoding）
- 向量化执行友好（连续内存中 SIMD 处理）

**缺点**：
- 单行写入涉及多个 Page，写放大严重
- 点查询需要跨列拼接

**代表数据库**：ClickHouse、Apache Parquet、Snowflake

### 1.3 PAX（Partition Attributes Across）

PAX 是行存和列存的混合体。在 Page 级别内部做列式组织。

```
Page Layout:
[Page Header]
[Column Groups: id段 | name段 | age段]
[Slot Array]
```

每个 Page 内部存储完整的多行，但行内的列被分组连续存储。兼顾了行存的"单页完整性"和列存的"列式压缩优势"。

---

## 二、页管理（Page Management）

### 2.1 Page 结构

页是存储的最小逻辑单元，通常是 4KB、8KB 或 16KB。

```
┌─────────────────────────┐
│   Page Header (~100B)   │  ← page_id、checksum、lsn、flags
├─────────────────────────┤
│                         │
│        Data Area        │  ← 实际的记录数据
│                         │
├─────────────────────────┤
│   Slot Array (逆向生长)  │  ← 记录指针（offset, length）
└─────────────────────────┘
```

**空闲空间追踪**：
- **Slotted Page**：数据从底向上生长，Slot 数组从顶向下生长
- 空闲空间 = 二者之间
- 当空闲空间不足时，触发碎片整理（compact）或申请新页

### 2.2 页类型

| 页类型 | 用途 |
|--------|------|
| 数据页 | 存储表记录 |
| 索引页 | B+树节点 |
| 元数据页 | 表结构、统计信息 |
| Undo 页 | MVCC 撤销日志 |
| Redo 页 | WAL 预写日志 |

---

## 三、Buffer Pool（缓冲池）

Buffer Pool 是内存中的页缓存，所有读写操作都通过 Buffer Pool 进行。

### 3.1 架构

```
[Query Executor]
      ↓
[Buffer Pool Manager]
      ↓ 命中？→ 直接返回
      ↓ 未命中 → 从磁盘加载
[Page Table] ← frame_id 到 page_id 的映射
      ↓
[Pages Array] ← 固定大小的帧数组
      ↓
[Disk Storage]
```

### 3.2 替换策略

| 策略 | 原理 | 特点 |
|------|------|------|
| LRU | 淘汰最久未使用的页 | 简单但扫描操作污染缓存 |
| Clock | 近似 LRU，环形指针+引用位 | 实现简单，大多数数据库使用 |
| LRU-K | 记录最后 K 次访问历史 | 更精确，PostgreSQL 使用 |
| ARC | 自适应替换 | 自动平衡频率和近因 |

**MySQL InnoDB 的改进 LRU**：
```
[ Young (5/8) | Old (3/8) ]  ← 中间有分隔点
```
新页插入 Old 区头部，经过一定时间后再移到 Young 区，避免一次全表扫描把整个缓存污染。

### 3.3 脏页与刷盘

```c
// 脏页写入触发条件
1. Buffer Pool 满 → 驱逐脏页前先写回
2. Checkpoint 触发 → 强制写入所有脏页到指定 LSN
3. 后台线程定时刷入
4. WAL 大小超过阈值
```

---

## 四、WAL（Write-Ahead Logging）

WAL 是实现事务持久性（Durability）的核心机制。

### 4.1 基本原则

**WAL 协议**：在将数据页写入磁盘前，必须先写入日志。

```
事务流程：
1. 修改 Buffer Pool 中的页（标记脏页）
2. 将修改记录写入 WAL Buffer
3. 事务提交时，强制 flush WAL Buffer 到磁盘
4.（之后某个时间点）将脏页写入数据文件
```

### 4.2 WAL 记录格式

```
[LSN | PrevLSN | TxID | Type | PageID | Data | Checksum]
├──── ─────────────────────────────────────────────────────┤
│ LSN (Log Sequence Number)：单调递增的日志序号
│ PrevLSN：同一事务的上一条日志，形成链表
│ TxID：事务 ID
│ Type：INSERT/UPDATE/DELETE/COMMIT/ABORT
│ PageID：涉及的数据页
│ Data：redo 信息（新旧值）
│ Checksum：校验和
```

### 4.3 Steal + No-Force 策略

| 策略 | 是否允许将未提交事务的脏页写入磁盘 | 是否要求提交时将脏页写入磁盘 |
|------|-----------------------------------|------------------------------|
| Steal | 允许（内存压力时驱逐未提交的脏页） | - |
| No-Force | - | 不需要（WAL 保证了持久性） |

**Steal + No-Force** 是主流数据库的选择（MySQL、PostgreSQL）：
- **Steal**：允许 Buffer Pool 驱逐未提交事务的脏页 → 需要 Undo Log 回滚
- **No-Force**：提交时只需要写 WAL，数据页可以稍后写入 → 加速提交

### 4.4 ARIES 恢复算法

ARIES（Algorithms for Recovery and Isolation Exploiting Semantics）是工业标准的恢复算法：

```
崩溃恢复三阶段：
1. Analysis Pass：从 Checkpoint 向后扫描 WAL
   - 构建脏页表（Dirty Page Table）
   - 确定事务状态（进行中/已提交/已回滚）
   
2. Redo Pass：从最早的脏页 LSN 开始重放所有操作
   - 仅重放已持久化的操作（幂等性保证）
   - 完成后数据库回到崩溃时的状态
   
3. Undo Pass：回滚所有未提交的事务
   - 使用事务的历史记录（Undo Log）还原
   - 记录 Compensation Log Records（CLR）防止重复撤销
```

---

## 五、Checkpoint

Checkpoint 是为了缩短崩溃恢复时间而引入的机制。

### 5.1 工作原理

```
Redo 的范围 = [CheckpointLSN, CurrentLSN]
```

每次 Checkpoint 记录：
1. 所有活跃事务列表
2. 脏页表（page_id → 最早的 LSN）
3. 当前的 LSN

**Fuzzy Checkpoint**（模糊检查点）：
- 不要求立即刷入所有脏页
- 只需记录 Checkpoint 时的状态，刷脏页在后台上进行
- 允许在 Checkpoint 过程中继续处理新事务

### 5.2 Checkpoint 触发条件

- 日志大小达到阈值（如 InnoDB 的 `innodb_log_file_size` 的 75%）
- 时间间隔（如每 30 秒）
- 应用手动触发（`CHECKPOINT` 命令）
- 正常关闭时

---

## 六、存储模型对比总结

| 维度 | 行存（NSM） | 列存（DSM） | PAX |
|------|------------|------------|-----|
| OLTP 点查询 | ★★★★★ | ★★☆☆☆ | ★★★★☆ |
| OLAP 聚合 | ★★☆☆☆ | ★★★★★ | ★★★★☆ |
| 写性能 | ★★★★★ | ★★☆☆☆ | ★★★☆☆ |
| 压缩率 | 低 | 高 | 中 |
| 向量化支持 | 差 | 优秀 | 中等 |
| 典型场景 | 订单系统、账户 | 报表、分析 | 混合负载 |

## 七、总结

- **行存**适合 OLTP（点查询、频繁写入），**列存**适合 OLAP（大范围扫描、聚合）
- **页**是存储的最小逻辑单元，通过 Slot 数组管理空闲空间
- **Buffer Pool** 作为磁盘和内存之间的缓存，使用 LRU 变体管理替换策略
- **WAL** 通过先写日志再写数据实现了持久性和原子性
- **Steal + No-Force** 是主流策略，允许提前刷脏页，提交只写 WAL
- **ARIES** 是标准的崩溃恢复算法，三阶段（Analysis→Redo→Undo）
- **Checkpoint** 缩短恢复时间，Fuzzy Checkpoint 允许并发

理解存储引擎是深入数据库内核的第一步。下一课将探讨 B+树和 LSM-Tree 索引结构。
