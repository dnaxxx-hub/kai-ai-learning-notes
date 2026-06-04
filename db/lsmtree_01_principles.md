# 存储引擎 #1：LSM-Tree 原理与设计

> 2026-05-17
> 前置：数据库基础（B+Tree、WAL、ACID）

## 1. LSM-Tree 的诞生动机

### 1.1 磁盘性能的演进矛盾

传统 B+Tree 的优势在于**读**（按树高 O(log N) 找到数据），但随着 SSD 成为主流，瓶颈从**寻道延迟**转向了**写入放大**：

```
HDD 时代：随机写 ≈ 10ms，顺序写 ≈ 10ms（寻道瓶颈）
   → B+Tree 需要大量随机写（页分裂、刷新）
   → 但 HDD 上随机写本身就很慢？

SSD 时代：随机写快了很多，但带来写入放大
   → B+Tree 页更新 → 写 4KB 数据实际写 16KB+（GC+擦除）
   → LSM-Tree 只做顺序写 → 减少写放大
```

结论：SSD 上 LSM-Tree 的写入性能远优于 B+Tree。

### 1.2 LSM-Tree 的核心思想

"数据先写内存（MemTable），内存满了再批量顺序刷盘"——把随机写转为顺序写。

```
LevelDB / RocksDB 的核心架构：

┌─────────────┐   写操作 → WAL → MemTable (内存)
│  MemTable 1  │                               ↓ (满了)
└──────┬──────┘                          Immutable MemTable
       │ flush                               ↓ (刷盘)
       ▼                               SSTable (Level 0)
┌─────────────┐   读操作 → MemTable → Level 0 → Level 1 → ... → Level N
│    WAL      │
└─────────────┘
```

## 2. LSM-Tree 的核心组件

### 2.1 MemTable（内存表）

```
写入流程：
  Put(key, value) → 追加到 WAL → 写入 MemTable（跳表/红黑树）

MemTable 数据结构选型：
  跳表（SkipList）：LevelDB / RocksDB 的选择
    ✅ 无锁并发读（多线程友好）
    ✅ O(log N) 插入/查询
    ❌ 内存开销略大

  红黑树（RBTree）：HBase 的选择
    ✅ O(log N) 插入/查询
    ❌ 写入过程需要加锁

  哈希表（HashTable）：Bitcask 的选择
    ✅ O(1) 查询
    ❌ 范围查询慢
```

**MemTable 满 → 冻结为 Immutable MemTable → 后台线程 flush 为 SSTable**。

### 2.2 WAL（预写日志）

```
写操作 → 先写 WAL（顺序写，append-only）
       → 写成功后才写入 MemTable
       → 这样即使崩溃，重启时 Replay WAL 重建 MemTable

WAL 文件结构：
  [Block 32KB]
    ┌─────────────┐
    │ Record Type  │ = Full / First / Middle / Last (支持跨块记录)
    │ CRC32        │ 校验
    │ Length       │ 数据长度
    │ Data         │ key-value 数据
    └─────────────┘
```

### 2.3 SSTable（排序字符串表）

SSTable 是不可变的、分层的、有序的键值存储文件：

```
SSTable 文件结构（简化）：
┌─────────────────────────────────────┐
│ Data Blocks                          │ ← 键值对，按 key 排序
│   Block 0: key range [a, d]         │   每块默认 4KB-64KB
│   Block 1: key range [e, h]         │
│   ...                                │
├─────────────────────────────────────┤
│ Meta Blocks                          │ ← 布隆过滤器（可选）
│   Bloom Filter: [a..z] hash         │
├─────────────────────────────────────┤
│ Meta Index Block                     │ ← Meta Block 索引
├─────────────────────────────────────┤
│ Index Block                          │ ← Data Block 索引
│   Block 0: last_key="d", offset=0   │   （加速二分查找定位块）
│   Block 1: last_key="h", offset=4096│
├─────────────────────────────────────┤
│ Footer                               │ ← 指向 Index + MetaIndex
└─────────────────────────────────────┘
```

### 2.4 Manifest（元数据）

记录所有 SSTable 的层级关系和 key 范围，以及正在进行的合并操作。

```
Manifest 中的一条记录示例：
  Current Version:
    Level 0: [a.sst, b.sst, c.sst]  (3 files, key may overlap)
    Level 1: [d.sst, e.sst]          (2 files, no overlap)
    Level 2: [f.sst, g.sst, h.sst]   (3 files, no overlap)
```

## 3. LSM-Tree 的合并策略

### 3.1 为什么需要合并

```
Level 0：多个 SSTable 的 key 范围可能重叠（因为直接 flush）
Level 1+：每个 SSTable 不重叠 key 范围
  → 读操作需要检查所有 SSTable → Level 0 检查所有，Level 1+ 二分定位

如果不合并：
  Level 0 的 SSTable 数量持续增长
  → 每次读都要检查多个文件
  → 读性能急剧下降
```

### 3.2 各数据引擎的合并策略

**LevelDB：Size-Tiered Compaction**

```
Level 0 → Level 1: 4 个 SST → 合并为 1 个 SST
Level 1 → Level 2: Level 1 总大小超过 10MB × 10^1 = 100MB 时触发
Level N → Level N+1: 大小超过 10MB × 10^N 时触发
```

**RocksDB：Level Compaction（分层）+ Universal Compaction（全量排序）+ FIFO（时间窗口）**

**Cassandra：Size-Tiered，同层级大小差不多时合并**

### 3.3 Level vs Size-Tiered Compaction

| | Level（分层） | Size-Tiered（同层） |
|---|--------------|-------------------|
| SST 重叠 | Level 1+ 不重叠 | 同层可重叠 |
| 读放大 | 小（二分定位） | 大（检查多个） |
| 写放大 | 较大（多次合并） | 较小（一次整理） |
| 空间放大 | 小 | 较大 |
| 代表 | LevelDB, RocksDB | Cassandra, HBase |

## 4. LSM-Tree 的三大代价

### 4.1 写放大（Write Amplification）

写入 1KB 数据，引擎实际写入磁盘的量：

```
B+Tree（有 buffer）：写放大 ≈ 2-4x
LSM-Tree（LevelDB）：写放大 ≈ 10-40x
LSM-Tree（RocksDB tuned）：写放大 ≈ 4-10x
```

为什么 LSM-Tree 写放大更大：一份数据在 MemTable 写一次，flush 到 L0 写一次，合并到 L1 写一次，逐级下推继续合并……

### 4.2 读放大（Read Amplification）

读到 1 个 key，引擎实际读取的数据量：

```
B+Tree：树高（通常 3-4）个页 = 读放大 3-4x
LSM-Tree（LevelDB 默认）：要检查 MemTable + Immutable + L0 全部 + 每级 1 个 SST
  = 最多 2 (mem) + 4 (L0) + 6 (L1~L6 各一) = 12x
```

### 4.3 空间放大（Space Amplification）

有效数据 vs 磁盘实际占用：

```
B+Tree：近乎 1:1
LSM-Tree（LevelDB）：合并前可能有 1.1 ~ 1.5 倍的临时空间占用
```

## 5. LSM-Tree 的优化技术

### 5.1 布隆过滤器（Bloom Filter）

SSTable 的"栅栏"——快速跳过不可能包含目标 key 的文件：

```python
class BloomFilter:
    def __init__(self, n: int, fp_rate: float = 0.01):
        # k = -log2(fp_rate), m = -n * ln(fp_rate) / (ln2)^2
        self.k = 7   # 7 个哈希函数 ≈ 1% 假阳率
        self.m = int(-n * (0.01).log() / (0.693**2))  # bits
        self.bits = bitarray(self.m)

    def add(self, key: bytes):
        for seed in self.k_hashes:
            self.bits[hash(key, seed) % self.m] = 1

    def may_contain(self, key: bytes) -> bool:
        for seed in self.k_hashes:
            if not self.bits[hash(key, seed) % self.m]:
                return False    # ✅ 肯定不存在
        return True             # ⚠️ 可能存
```

**效果**：减少 90%+ 不必要的 SSTable 读取（读放大显著降低）。

### 5.2 缓存

```
Block Cache（RocksDB）：
  ≈ InnoDB Buffer Pool
  缓存热门 Data Block / Index Block

Row Cache：
  缓存最近读的 key-value（热点数据不走 SSTable）

Table Cache：
  缓存已打开的文件句柄

分页：Block Cache 用 LRU，Row Cache 用 Clock
```

### 5.3 前缀压缩

同一 SSTable 中相邻 key 通常共享前缀：

```
原始 key:  "abcdef001"  "abcdef002"  "abcdef003"  "bcdef001"
压缩存储:  "abcdef001"  "002"        "003"         "bcdef001"
             9 bytes   3 bytes      3 bytes       8 bytes
             节省了 4+4+1=9 字节
```

## 总结

```
LSM-Tree = 顺序写入 + 分层合并

优点：
  ✅ 写入吞吐极高（顺序写 ≈ 随机写的 10x）
  ✅ 写放大可控（优化后可到 3-5x）
  ✅ 天然支持压缩

代价：
  ⚠️ 读放大比 B+Tree 大（Bloom Filter + Cache 缓解）
  ⚠️ 合并可能会干扰前台性能（RocksDB 用子压缩缓解）
  ⚠️ 空间放大比 B+Tree 略大
```
