# 数据库内核 #1：InnoDB存储引擎架构

> 前置知识：数据库 16 课系列（B+树 / ACID / MVCC / InnoDB 架构 / Redo Log 等）
> 本系列深入源码级别，每个概念都追踪到 MySQL 源码行为、配置参数及性能影响

---

## 引言

InnoDB 是 MySQL 默认的存储引擎，其架构设计深受 Oracle 影响但又深度融合了 MySQL 的开源生态。理解 InnoDB 的内核架构是掌握数据库内核的起点，也是后续理解事务、恢复、并发控制等机制的基础。

本文从**整体架构 → 页管理 → 行记录 → 索引 → 锁 → Buffer Pool** 六个维度，逐层深入 InnoDB 源码实现。核心源码目录：`storage/innobase/`（约 30 万行 C/C++ 代码）。

---

## 1. InnoDB 整体架构

InnoDB 的体系结构可划分为三大块：**内存结构**、**线程结构**、**磁盘结构**。三者通过 Buffer Pool 和 Redo Log 形成闭环。

### 1.1 内存结构

#### 1.1.1 Buffer Pool

Buffer Pool 是 InnoDB 最核心的内存区域，用于缓存数据页、索引页、undo 页等。它本质上是一片连续内存划分为固定大小的页（默认 16KB）。

```c
// 源码位置：storage/innobase/include/buf0buf.h
// buf_pool_t 结构体核心定义
struct buf_pool_t {
    ulint           curr_size;    // 当前大小（pages）
    ulint           instance_no;  // 实例编号（多实例）
    buf_page_t     *pages;        // 页数组基址
    UT_LIST_BASE_NODE_T(buf_page_t) free;    // Free 链表
    UT_LIST_BASE_NODE_T(buf_page_t) LRU;     // LRU 链表
    UT_LIST_BASE_NODE_T(buf_page_t) flush_list; // Flush 链表
    // ... 约 50+ 成员
};
```

**核心链表**：
- **Free List**：空闲页链表，新页从这取
- **LRU List**：已使用的页，按访问时间排序
- **Flush List**：脏页链表，由 Page Cleaner 负责刷盘

**关键配置**：
| 参数 | 默认值 | 作用 |
|------|--------|------|
| `innodb_buffer_pool_size` | 128MB | Buffer Pool 总大小，通常设为物理内存的 60-80% |
| `innodb_buffer_pool_instances` | 8（≥1GB时） | 多实例数，减少锁竞争 |
| `innodb_old_blocks_pct` | 37 | LRU old 子列表占比 |
| `innodb_old_blocks_time` | 1000 | 首次访问到移至 young 的等待时间（ms） |

#### 1.1.2 Change Buffer

Change Buffer（MySQL 5.5+ 之前叫 Insert Buffer）用于缓存**对非唯一二级索引页的修改操作**（INSERT/UPDATE/DELETE），等目标页被读到 Buffer Pool 时再合并。

**三种缓存操作**：
- `IBUF_OP_INSERT`：插入缓存
- `IBUF_OP_DELETE_MARK`：删除标记缓存
- `IBUF_OP_DELETE`：删除缓存（purge 操作）

**源码行为**：`ibuf_insert()` 会判断目标页是否在 BP 中，如果不在则写入 Change Buffer（B+树结构），同时记录 redo log。当页被读入时，`ibuf_merge_page()` 将缓存的操作回放。

**性能影响**：
- ✅ 大幅减少离散写入（尤其是大量 INSERT 到非唯一二级索引的场景）
- ❌ 唯一二级索引不能用（必须实时检查冲突）
- ❌ merge 阶段可能引起激烈的 I/O 抖动

| 参数 | 说明 |
|------|------|
| `innodb_change_buffering` | all/none/inserts/deletes/changes |
| `innodb_change_buffer_max_size` | 占 BP 百分比，默认 25% |

#### 1.1.3 Adaptive Hash Index (AHI)

AHI 是 InnoDB 对热点 B+ 树索引页构建的哈希索引，加速等值查询。**注意**：AHI 是 B+ 树的索引缓存，不是独立的索引结构。

**构建条件**（源码 `btr_search_build_page_hash_index()`）：
1. 页被访问超过 `N` 次（`N = 页行数 / 16`）
2. 查询模式为等值匹配（而非范围扫描）
3. 索引树的「查询模式」稳定

**AHI 的代价**：
- 占用 Buffer Pool 外的额外内存
- DDL/大量写入时维护成本高
- 分区锁（`btr_search_latch`）在 MySQL 5.7 前是全局锁，8.0 改进了分区策略

| 参数 | 说明 |
|------|------|
| `innodb_adaptive_hash_index` | ON/OFF，默认 ON |
| `innodb_adaptive_hash_index_parts` | 8（哈希表分区数，8.0+） |

#### 1.1.4 Log Buffer

Redo Log 写入日志文件的缓冲区，大小由 `innodb_log_buffer_size` 控制（默认 16MB）。

**写入时机**：
1. 事务提交（`innodb_flush_log_at_trx_commit=1` 时）
2. Log Buffer 满约 50%
3. 后台线程每秒刷盘

### 1.2 线程结构

InnoDB 启动后创建多个后台线程协同工作。

#### Master Thread
主循环线程，每秒 + 每 10 秒执行任务：
- **每秒**：日志缓冲刷盘、合并 Change Buffer（最多 5% IOPS）、刷新脏页、检查当前 I/O 容量
- **每 10 秒**：强迫刷脏页（若脏页比例超过 `innodb_max_dirty_pages_pct`）、合并 Change Buffer（最多 100% IOPS）、删除无用的 Undo 页

源码入口：`srv_master_thread()` → `srv_master_do_active_tasks()`

#### IO Thread
处理异步 I/O 请求，包括读、写、redo log 写等。根据 `innodb_read_io_threads` 和 `innodb_write_io_threads` 设置（默认 4+4）。

#### Purge Thread
清理已提交事务的 Undo 记录，使它们可被物理删除。多线程配置：`innodb_purge_threads`（默认 1，MySQL 8.0 建议 4）。

#### Page Cleaner Thread
负责将 Flush List 中的脏页刷入磁盘。8.0 中由 `srv_do_page_cleaners()` 管理多个 cleaner 线程。

```c
// 源码：storage/innobase/buf/buf0flu.cc
// 脏页刷新的核心判断逻辑
static ulint af_get_pct_for_dirty() {
    // 脏页比例超过阈值后，线性增加刷新速度
    if (srv_max_buf_pool_modified_pct == 0)
        return 0;
    double dirty_pct = buf_get_modified_ratio_pct();
    if (dirty_pct >= srv_max_buf_pool_modified_pct)
        return 100;
    return (ulint)((dirty_pct * 100) / srv_max_buf_pool_modified_pct + 0.5);
}
```

### 1.3 磁盘结构

#### 表空间类型

| 空间ID | 类型 | 文件 | 用途 |
|--------|------|------|------|
| 0 | 系统表空间 | ibdata1 | 数据字典、Doublewrite Buffer、Change Buffer、Undo logs |
| 1- | 用户表空间 | tablename.ibd | 用户表数据和索引 |
| 通用表空间 | 自定义 | .ibd | 多表共享 |
| undo表空间 | undo_xxx | undo_001, undo_002 | Undo 日志 |
| 临时表空间 | temp_xxx | ibtmp1 | 临时表和排序 |

**系统表空间文件布局（ibdata1）**：
```
+-------------------+-------------------+-------------+-------------------+
| FSP_HDR (page 0)  | ibuf bitmap(page1)| Inode(page2)| SDI Index(page3)  |
+-------------------+-------------------+-------------+-------------------+
| SDI Data(page 4)  | Data Dictionary   | Undo Space  | Change Buffer     |
+-------------------+-------------------+-------------+                   +
| Doublewrite Buffer(128 pages)          | ...         |                   |
+----------------------------------------+-------------+-------------------+
```

#### .ibd 文件内部布局

InnoDB 的 .ibd 文件是自描述的 B+ 树森林。

**页（Page，默认 16KB）↔ 区（Extent，1MB=64页）↔ 段（Segment）↔ 表空间（Tablespace）**

```c
// 源码：storage/innobase/include/fsp0types.h
// 页内部偏移常量
#define FIL_PAGE_DATA      38     // 页数据开始偏移
#define FIL_PAGE_PREV      4      // 上一页指针
#define FIL_PAGE_NEXT      8      // 下一页指针
#define FIL_PAGE_LSN       16     // 页最近修改的 LSN
#define FIL_PAGE_TYPE      24     // 页类型
#define FIL_PAGE_SPACE_ID  34     // 表空间 ID
```

### 1.4 文件格式简史

| MySQL 版本 | 文件格式 | 新特性 | 行格式默认 |
|------------|----------|--------|-----------|
| 5.5 | Antelope | 无 | COMPACT |
| 5.6 | Barracuda | DYNAMIC, COMPRESSED 行格式 | COMPACT |
| 5.7 | Barracuda | 支持 COMPRESSED | **DYNAMIC** |
| 8.0 | Barracuda（淘汰 Antelope）| 移除 REDUNDANT 部分 | **DYNAMIC** |

---

## 2. 页（Page）管理

页是 InnoDB 磁盘和内存交互的最小单位，也是理解 InnoDB 的钥匙。

### 2.1 Page 结构

一个 16KB 的数据页布局如下：

```
+----------------------------------+  <- offset 0
| FIL Header (38 bytes)            |
|   · Checksum (4B)                |
|   · Page Number (4B)             |  （空间中的偏移）
|   · Previous Page Pointer (4B)   |  ← 链表指针
|   · Next Page Pointer (4B)       |  ← 链表指针
|   · LSN (8B)                     |
|   · Page Type (2B)               |
|   · File Flush LSN (8B)          |
|   · Space ID (4B)                |
+----------------------------------+  <- offset 38
| Page Header (56 bytes)           |
|   · n_dir_slots (2B)             |  页目录槽数
|   · heap_top (2B)                |  空闲空间开始偏移
|   · n_heap (2B)                  |  记录数
|   · free (2B)                    |  空闲记录链表
|   · deleted (2B)                 |  已删除记录链表
|   · last_insert (2B)             |  最后插入位置
|   · direction (2B)               |  插入方向
|   · n_direction (2B)             |  连续插入数
|   · n_recs (2B)                  | 有效用户记录数
|   · max_trx_id (8B)              | 最大事务ID
|   · level (2B)                   | B+树层数（0=叶子）
|   · index_id (8B)                | 索引ID
+----------------------------------+  <- offset 94
| Infimum (13 bytes)               |  伪记录（最小值哨兵）
+----------------------------------+  <- offset 107
| Supremum (13 bytes)              |  伪记录（最大值哨兵）
+----------------------------------+  <- offset 120
| User Records                     |
|  (实际行记录，按顺序插入)          |
|                                   |
+----------------------------------+  <- heap_top
| Free Space                       |
|  (空闲空间，新记录从此分配)        |
|                                   |
+----------------------------------+  <- page_directory 指向的底部
| Page Directory (变长)            |
|   · slot[0] → Infimum            |
|   · slot[1] → 某记录             |
|   · slot[2] → 另一记录           |
|   · slot[n-1] → Supremum         |
+----------------------------------+  <- page trailer 开始
| FIL Trailer (8 bytes)            |
|   · Checksum (4B, 冗余校验)      |
|   · LSN (4B, 低32位)            |
+----------------------------------+  <- offset 16384 (16KB)
```

### 2.2 Page 类型（FIL_PAGE_TYPE）

```c
// 源码：storage/innobase/include/fil0fil.h
#define FIL_PAGE_INDEX     17855  // B+树索引页（数据/索引）
#define FIL_PAGE_RTREE     17856  // R树索引页（空间索引）
#define FIL_PAGE_SDI       17853  // 序列化字典信息
#define FIL_PAGE_UNDO_LOG   2     // Undo日志页
#define FIL_PAGE_INODE      3     // 索引节点（段管理）
#define FIL_PAGE_IBUF_FREE_LIST 4 // Change Buffer空闲列表
#define FIL_PAGE_TYPE_ALLOCATED 0 // 已分配但未格式化
#define FIL_PAGE_BLOB       10    // BLOB 页（DYNAMIC行）
#define FIL_PAGE_ZBLOB      11    // 压缩BLOB页
#define FIL_PAGE_TYPE_FSP_HDR 8   // 表空间头部
#define FIL_PAGE_TYPE_XDES  9     // Extent描述符页
```

### 2.3 Page 分裂与合并

#### 分裂触发条件

B+ 树叶子节点页满时触发分裂，但 InnoDB 不是等页 100% 满才分裂。

```c
// 源码：storage/innobase/btr/btr0btr.cc
// btr_page_split_and_insert() — 关键分裂函数
// 分裂触发条件：
// 1. 页可用空间不足以插入当前记录
// 2. 如果 page_zip_available() 返回 false（压缩表还有空间时受压缩限制）
// 3. 页填充率超过 innodb_page_size 约束

// 分裂决策：
// - 从当前页中间位置分裂（约 50% 原则）
// - 若新记录很大（如 blob），会特殊处理避免浪费空间
```

**分裂过程（5步）**：
1. `btr_page_get_split_rec()` — 确定分裂点（中位记录或新记录）
2. 分配新页（从 Free List 或 Extent 中分配）
3. 将后半部分记录搬到新页
4. 调整 B+ 树父节点的指针，可能递归分裂
5. `btr_page_set_prev_next()` — 维护双向链表

#### 合并条件

当相邻页的**有效记录利用率低于 50%** 时尝试合并。

```c
// 源码：storage/innobase/btr/btr0btr.cc  
// btr_page_merge() — 合并逻辑
// 合并触发场景：
// 1. 删除记录后，页使用率低
// 2. 作为分裂的逆操作
// 
// 合并条件（近似）：
// 该页记录数 + 相邻页记录数 < 单页最大记录数 × 50%
```

**性能影响**：
- 频繁分裂导致：页碎片增加、写入延迟抖、B+树高度增长
- 频繁合并导致：额外的查找和修改、X-latch 竞争
- 优化手段：`innodb_merge_threshold_set_all_debug`（调试用）、合适的 `innodb_fill_factor`（8.0 新增，控制页填充率）

### 2.4 Page 压缩（COMPRESSED 行格式）

Barracuda 文件格式引入的 COMPRESSED 行格式，使用页级压缩而非行级压缩。

**压缩算法**：zlib（`page_zip_compress()` / `page_zip_decompress()`）

```c
// 源码：storage/innobase/page/page0zip.cc
// 压缩页结构（用 1KB~8KB 的压缩页代替 16KB 页）
// 实际存储：压缩后数据 + 修改日志（modification log）
//
// +----------------------------+
// | 压缩后的数据（可能 < 16KB）  |
// |   zlib 压缩整页内容          |
// +----------------------------+
// | Modification Log           |
// |   记录未压缩部分的修改        |
// +----------------------------+

// page_zip_compress() 核心流程
void page_zip_compress(..., buf_block_t *block) {
    // 1. 对脏页进行 zlib 压缩
    // 2. 如果压缩到目标大小，存为 compressed page
    // 3. 如果无法压缩（数据太随机），存为 uncompressed 但标记
    // 4. 写入 modification log 记录未压缩的信息    
}
```

**性能影响**：
- ✅ 节省磁盘空间（通常 40-50%）
- ❌ 增加 CPU 消耗（压缩/解压）
- ❌ 更新时需要写 mod log，增加复杂度
- ❌ `BUFFER POOL` 中存的是压缩页 + 可能存在的解压页，内存消耗不可忽略

| 参数 | 说明 |
|------|------|
| `innodb_compression_level` | zlib 压缩级别，1-9（默认 6） |
| 关键字 KEY_BLOCK_SIZE | 指定压缩页大小（1,2,4,8KB） |

### 2.5 预读（Read Ahead）

InnoDB 的预读机制在发现顺序访问模式时，提前将后续页面加载到 Buffer Pool，减少同步 I/O 等待。

#### 线性预读（Linear Read-Ahead）

当按顺序读取一个 Extent（64页=1MB）中的页达到 `innodb_read_ahead_threshold`（默认 56）时，触发整个 Extent 的异步预读。

```c
// 源码：storage/innobase/buf/buf0rea.cc
// buf_read_ahead_linear() — 线性预读
// 核心检查逻辑：
// 1. 当前页在 Extent 中的位置（是否达到阈值）
// 2. 检查相邻页是否在 Access Pattern 计数器中有记录
// 3. 若连续命中，发起异步预读请求（os_aio_func())
```

#### 随机预读（Random Read-Ahead）

当同一个 Extent 中有 13 个随机页被访问时，自动预读该 Extent 中剩余页。MySQL 5.5 默认为 ON，**5.7 后默认 OFF**（因为实际测试中收益不高，且可能浪费大量 I/O）。

```c
// buf_read_ahead_random()
// 收敛条件：同一 Extent 内的随机 page_no 访问达到阈值
```

**性能影响**：
- ✅ 顺序扫描性能大幅提升（如全表扫描、range scan）
- ❌ 随机预读可能造成 I/O 浪费（特别是有大量非热点随机查询时）
- ❌ 预读可能赶走 Buffer Pool 中真正有用的热页

| 参数 | 说明 |
|------|------|
| `innodb_read_ahead_threshold` | 线性预读阈值（0-64，默认56） |
| innodb_random_read_ahead | 随机预读开关，默认 OFF |

---

## 3. 行记录格式

InnoDB 支持 4 种行格式：REDUNDANT、COMPACT、DYNAMIC、COMPRESSED。MySQL 5.7+ 默认使用 DYNAMIC。

### 3.1 COMPACT 行格式

COMPACT 在 MySQL 5.0 引入，是 Antelope 文件格式的默认格式。每条记录在页内存储如下：

```
+------------------------------+  ← 记录起始
| 变长字段长度列表（逆序）      |
|   每个变长字段占 1-2 字节     |
|   （字段实际长度 < 255: 1B)  |
|   （字段实际长度 ≥ 255: 2B)  |
+------------------------------+
| NULL 位图（逆序）            |
|   每个 nullable 字段占 1 bit |
|   总位数 = nullable 字段数   |
|   向上取整到字节             |
+------------------------------+
| 记录头信息（40 bits = 5B）   |
|   · deleted_flag (1 bit)    |  已删除标记
|   · min_rec_flag (1 bit)    |  最小记录标记
|   · n_owned (4 bits)        |  拥有的记录数（页目录用）
|   · heap_no (13 bits)       |  堆中位置编号
|   · n_field (10 bits)       |  记录中字段数
|   · n_null (8 bits)         |  NULL 字段数（冗余）
|   · info_bits (2 bits)      |  信息位
|   · next_record (16 bits)   |  下一条记录的相对偏移
+------------------------------+
| 事务ID（DB_TRX_ID, 6B）     |
+------------------------------+
| 回滚指针（DB_ROLL_PTR, 7B） |
+------------------------------+
| 列数据（按创建顺序存储）     |
|   · 非空字段的实际值         |
|   · 定长字段直接存储         |
|   · 变长字段按长度存储       |
+------------------------------+
```

**源码行为**：`rec_init_offsets()` 会在解析记录时计算字段偏移，`rec_get_converted()` 完成记录格式转换。

### 3.2 DYNAMIC 行格式

MySQL 5.7 后的默认行格式。与 COMPACT 的核心区别在于**大字段溢出处理**。

**溢出策略对比**：

| 行格式 | 大字段 VARCHAT/BLOB/TEXT | 处理方式 |
|--------|--------------------------|----------|
| COMPACT | 768 字节前缀 + 剩余溢出页 | 页内含部分数据 |
| **DYNAMIC** | **完全溢出，仅存 20 字节指针** | 页内仅存溢出指针 |
| COMPRESSED | 完全溢出，溢出页压缩 | 页内仅存溢出指针 |

```c
// 源码：storage/innobase/include/rem0rec.h
// DYNAMIC 行：大字段的溢出标志
// 当一行总长度 > (page_size / 2) = 8192 字节时触发溢出
#define REC_OFFS_OFF     0x1   // 该字段值在溢出页中

// 溢出指针结构（20字节）
// +----------+----------+------------+
// | space_id | page_no  | data_len   |
// | (4B)     | (4B)     | (4B)       |
// +----------+----------+------------+
// | ext_len  | ext_offset | ext_len2 |
// | (4B)     | (4B)       | (4B)     |
// +----------+------------+----------+
// 
// 解释：指向溢出页中的具体偏移和数据长度
```

**DYNAMIC 的溢出流程**：
1. 当前行总长度 > `page_size / 2` 时，触发溢出
2. 将最长的变长字段移出到外部存储页（BLOB page）
3. 原位置仅保留 20 字节的溢出指针
4. BLOB 页通过链表连接（多页溢出时）

**性能影响**：
- ✅ 页内能存放更多行（小字段场景更紧凑）
- ✅ 不浪费前缀空间（COMPACT 的 768 字节前缀经常浪费）
- ❌ 大字段读取需要额外 I/O 访问 BLOB 页
- ❌ 频繁访问大字段时更贵（每次都需通过指针查找）

### 3.3 COMPRESSED 行格式

基于 DYNAMIC，但在存储层面加了 zlib 压缩。压缩粒度为**页级**（详见 2.4 节）。

### 3.4 REDUNDANT 行格式

MySQL 5.0 之前的旧格式，兼容 MySQL 3.23/4.0。

**特点**：
- 变长字段长度列表在列数据之前（非逆序）
- 记录头多 1 字节（共 6B）
- 用 `n_fields` 和 `n_null` 标记替代 COMPACT 的偏移计算
- 大字段同样使用 768 前缀 + 溢出

**不支持**：
- 不支持的索引特性：索引前缀压缩、索引合并
- `innodb_file_format=Antelope` 时使用

### 3.5 行溢出处理深入

InnoDB 的行溢出策略在不同行格式下表现各异，但核心逻辑在 `row_ins_clust_index_entry_low()` 中。

**BLOB 页结构**：

```c
// 源码：storage/innobase/include/blob0blob.h
// BLOB 页存储结构（DYNAMIC 行格式）
struct blob_page_t {
    // 前 38 字节：FIL Header
    // 后续数据：
    //   BLOB_HDR_PART_LEN (4B): 该页中数据长度
    //   BLOB_HDR_NEXT_PAGE_NO (4B): 下一溢出页指针（链表）
    //   BLOB_HDR_TRX_ID (6B): 事务ID
    //   实际数据...
};
```

**溢出页处理关键源码**：

```c
// storage/innobase/row/row0ins.cc
// row_ins_clust_index_entry_low() 中：
// 1. 计算行总长度
// 2. 如 > page_size/2，调用 btr_store_big_rec()
// 3. btr_store_big_rec() 分配 BLOB 页
// 4. 写入数据到 BLOB 页链
// 5. 在行中只存 20B 指针
```

**前缀索引与行溢出**：
- 前缀索引（`col_name(N)`）虽然只索引前 N 字节，但读取行时仍需完整读取大字段（确定前缀值是否正确）
- 因此前缀索引对大字段的**回表代价仍然很高**
- Just for 索引覆盖扫描：前缀索引可以避免读取完整 BLOB

---

## 4. 索引内部实现

### 4.1 聚簇索引（Clustered Index）

InnoDB 的聚簇索引 = 主键 B+ 树。叶子节点存整行数据，非叶子节点存索引键 + 子页指针。

```c
// 本质：所有 InnoDB 表都是索引组织表（IOT）
// 表 = 1 个聚簇索引 + N 个二级索引

// 源码：storage/innobase/include/dict0dict.h
// dict_index_t 是索引的内存表示
struct dict_index_t {
    ulint       type;       // 索引类型：CLUSTERED / SECONDARY / UNIQUE
    ulint       n_fields;   // 索引列数
    dict_field_t *fields;    // 索引列定义
    ulint       n_uniq;     // 唯一键列数（主键定义列数）
    ulint       n_def;      // 所有列数（含隐藏列）
    // B+ 树信息
    page_no_t   page;       // 根页号
    ulint       n_root_estimates; // 根节点估算
    ...
};
```

**非主键二级索引回表**：

```sql
CREATE TABLE t (id INT PRIMARY KEY, name VARCHAR(10), age INT, INDEX idx_name(name));
SELECT age FROM t WHERE name = 'kai';
```

执行流程：
1. 通过 `idx_name` B+ 树找到 `name='kai'` 的叶子节点
2. 叶子节点存储 `(name, id)` = `('kai', 42)`
3. 获取 `id=42`，回聚簇索引查找 `(42, 'kai', 18)` → 返回 `age=18`
4. **一次回表**增加一次 B+ 树搜索（约 2-4 次 I/O）

**覆盖索引优化**：

```sql
-- 如果索引包含 age，则不需要回表
CREATE INDEX idx_name_age ON t(name, age);
SELECT age FROM t WHERE name = 'kai';  -- 完全从二级索引返回！
```

### 4.2 二级索引（Secondary Index）

二级索引的叶子节点存储：`(索引键, 主键值)`。

```c
// 写入逻辑：当向聚簇索引插入记录时，row_ins_sec_index_entry()
// 同时更新所有相关二级索引
// 
// 二级索引不存行数据，所以更新二级索引不需要访问聚簇索引
// 但二级索引读取时必须回表（除非是覆盖索引）

// 源码：storage/innobase/row/row0ins.cc
// row_ins_sec_index_entry() 对每个二级索引依次插入
```

**重要**：二级索引不包含事务信息（DB_TRX_ID），所以在 MVCC 判断时需要回聚簇索引检查可见性。

### 4.3 自适应哈希索引（AHI）

AHI 是对 B+ 树索引的热点页建立哈希索引，加速等值查询。详见 1.1.3 节。

```c
// 源码：storage/innobase/btr/btr0sea.cc
// btr_search_guess_on_hash() — AHI 查找入口
//
// AHI 的 key 组成：space_id + page_no + offset（精确匹配）
// 注意：AHI 需要**完整匹配查询条件**才能命中
//
// 例如：WHERE a=1 AND b=2 → 需要 a 和 b 都是索引列且完全匹配
// WHERE a > 1 → 范围查询，AHI 不起作用

// 监控 AHI 使用率：
// SHOW ENGINE INNODB STATUS → "Hash table size ..." 
// 关注 hash searches/s 和 non-hash searches/s
```

**性能影响**：
- ✅ 等值查询加速显著（匹配查找变为 O(1)）
- ✅ 对只读/读多写少工作负载友好
- ❌ 高并发写入场景下 AHI 维护成本高（需要加锁更新 hash table）
- ❌ 分区不够时（`innodb_adaptive_hash_index_parts` 太小，默认 8）可能成为锁瓶颈

### 4.4 全文索引（FTS）

InnoDB 从 MySQL 5.6 开始支持全文索引，使用**倒排索引**结构。

```c
// 核心结构：FTS Index Cache（内存） + FTS Auxiliary Tables（磁盘）
// 倒排列表 = 单词 → 文档ID列表

// 源码：storage/innobase/fts/fts0fts.cc

// FTS 索引写入流程：
// 1. DML 操作 → 记录到 FTS Index Cache（红黑树+哈希表）
// 2. Cache 满（innodb_ft_cache_size, 默认32MB）→ 同步到 Aux Table
// 3. OPTIMIZE TABLE / COMMIT（视innodb_ft_num_word_optimize设置）
// 4. 最终所有数据进入磁盘 Aux Table

// 分词器（parser）：
// 内置 parser：按空格+标点分词
// 中文支持需用 ngram parser（MySQL 5.7+）
// 配置：ngram_token_size=2（默认 2 元分词）
```

**性能影响**：
- ✅ 全文搜索性能远超 LIKE '%keyword%'
- ❌ DML 开销大（每次插入都需分词 + 写入倒排索引）
- ❌ FTS Index Cache 占用额外内存
- ❌ 中文 ngram 需 `ngram_token_size=2`，对大文本分词量巨大

### 4.5 索引合并（Index Merge）

MySQL 5.0+ 引入，允许一个查询同时使用多个索引。

```c
// 源码：storage/innobase/sql/sql_optimizer.cc（优化器层面）
// 不完全是 InnoDB 层，属于 Server 层优化器行为

// 三种策略：
// 1. Union：                   SELECT ... WHERE a=1 OR b=2
//    从 idx_a 和 idx_b 分别获取 rowid → UNION 去重 → 回表
//
// 2. Intersection：            SELECT ... WHERE a=1 AND b=2
//    分别获取 rowid → INTERSECT → 回表
//
// 3. Sort-Union：              SELECT ... WHERE a>1 OR b>2
//    先按 rowid 排序后再 UNION（OR + 范围查询）
```

**性能影响**：
- ✅ 避免建立复合索引也能高效处理多列过滤
- ✅ Intersection 可减少回表次数
- ❌ Union 场景下临时表和排序的开销
- ❌ 不如复合索引高效（需要多次索引查找 + 合并）

**优化建议**：
- `EXPLAIN` 中看到 `Using union(idx_a,idx_b)` → 考虑建复合索引
- Intersection 路径通常是优化器的次优选择，检查 index_merge 是否真正高效
- 可通过 `optimizer_switch='index_merge=off'` 禁用测试

---

## 5. 事务与锁

InnoDB 的锁系统是并发控制的核心。锁机制在存储引擎层实现，Server 层（如表锁）是另一套体系。

### 5.1 锁类型总览

```c
// 源码：storage/innobase/include/lock0types.h
// 锁模式（lock_mode）
#define LOCK_IS      0   // 意向共享锁（Intention Shared）
#define LOCK_IX      1   // 意向排他锁（Intention Exclusive）
#define LOCK_S       2   // 共享锁（Shared）
#define LOCK_X       3   // 排他锁（eXclusive）
#define LOCK_AUTO_INC 4  // 自增锁（AUTO-INC）

// 锁类型（lock_type）
#define LOCK_TABLE   16   // 表锁
#define LOCK_REC     32   // 行锁

// 行锁变体（与 LOCK_REC 组合使用）
#define LOCK_GAP     512   // Gap 锁（间隙锁）
#define LOCK_ORDINARY 0    // Next-Key Lock = RECORD + GAP
#define LOCK_INSERT_INTENTION 2048  // 插入意向锁
```

#### Record Lock（记录锁）

对索引记录加锁。`LOCK_S | LOCK_REC` 或 `LOCK_X | LOCK_REC`。

```c
// 锁住 B+ 树中某条索引记录
// 注意：即使表没有显式定义索引，InnoDB 也会在隐藏主键上加记录锁
```

#### Gap Lock（间隙锁）

对索引记录之间的间隙加锁。`LOCK_GAP | LOCK_REC`。

```c
// 作用区间：(上一条记录, 当前记录)
// 防止幻读（Phantom Read）

// 举例：WHERE id BETWEEN 10 AND 20 FOR UPDATE
// 如果存在 id=10 和 id=20 的记录，Gap Lock 锁定 (10,20)
// 不允许 INSERT id=15

// 注意：Gap Lock 仅在 REPEATABLE READ 隔离级别下生效
// READ COMMITTED 下 Gap Lock 被禁用
```

#### Next-Key Lock

`LOCK_ORDINARY` = Record Lock + Gap Lock。

```c
// 锁定区间：[上一条记录, 当前记录]（左闭右开）
// 即：锁定记录本身 + 记录前面的间隙

// SELECT ... FOR UPDATE 在 RR 级别下的默认行为
```

#### Insert Intention Lock（插入意向锁）

特殊的 Gap Lock，表示**等待插入到某个 Gap 中**。

```c
// 多个事务可以同时持有同一个 Gap 的 Insert Intention Lock
// 但不允许与真正的 Gap Lock 冲突
// 
// 场景：
// T1: SELECT * FROM t WHERE id > 100 FOR UPDATE  → 持有 (100, +∞) 的 Gap Lock
// T2: INSERT INTO t VALUES(200)                   → 请求 Insert Intention Lock
//     → T2 等待。等待期间持有 Insert Intention Lock
// T1: COMMIT
// T2: Insert Intention Lock 获取成功，完成插入
```

### 5.2 锁内存结构（Lock_sys）

```c
// 源码：storage/innobase/include/lock0lock.h
// 锁系统全局结构
struct lock_sys_t {
    hash_table_t *rec_hash;      // 行锁哈希表（space_id + page_no → 锁对象）
    hash_table_t *prdt_hash;     // 谓词锁哈希表
    hash_table_t *prdt_page_hash;
    ib_mutex_t    mutex;         // 锁系统互斥量
    // 等待队列
    lock_t       *wait_lock;     // 正在等待的锁请求
    srv_slot_t   *last_slot;     // 最后等待 slot
    // 死锁检测
    ibool         rollback_complete; // 是否在回滚中
};

// 单个锁对象的结构
struct lock_t {
    trx_t        *trx;           // 所属事务
    lock_t       *trx_locks;     // 事务锁链表
    hash_cell_t  *index;         // 哈希表单元（指向索引对象）
    ulint         type_mode;     // 锁类型 + 模式（LOCK_S/LOCK_X/LOCK_GAP...）
    // 行锁具体信息
    union {
        // 表锁
        struct {
            dict_table_t *table; // 表对象
        } tab_lock;
        // 行锁
        struct {
            dict_index_t *index;       // 索引对象
            lock_rec_bitmap_t *bitmap;  // 行级位图
        } rec_lock;
    } un_member;
    // 等待信息
    lock_t        *hash;         // 哈希链
    lock_t        *next;         // 等待队列
};
```

### 5.3 行锁实现：Bitmap 位图 + 锁对象链表

InnoDB 的行锁不是对"某一行"加锁，而是对**一个页内的某一行集合**加锁。

```c
// 核心数据结构：lock_rec_bitmap_t
// 每个 lock_t 对象关联一个页，用位图标记哪些行被锁

// 锁查找过程（lock_rec_get_first()）：
// 1. 计算哈希：hash_calc(space_id, page_no) → hash_value
// 2. 定位 hash cell
// 3. 遍历 hash cell 上的锁对象链表
// 4. 对每个锁对象检查 bitmap 中对应位是否置位

// 位图大小：一个页的最大行数（约 16KB / 最小行大小）
// 例如：page_size=16KB, 最小行约 50B → max_recs ≈ 327
// bitmap 需要 327 bits = 41 字节

// 源码：storage/innobase/lock/lock0lock.cc
// lock_rec_add() — 添加行锁
// 1. 计算 page_no 的 hash
// 2. 查找现有锁对象（同一事务对同一页已有锁时合并）
// 3. 如果没有则创建新的 lock_t，设置 bitmap
// 4. 插入 hash 表
```

**重要优化**：同一事务对同一页的多次加锁会**合并**为一个 lock_t 对象，多个行的位图叠加。

### 5.4 意向锁（Intention Lock）

实现多粒度锁定的桥梁。在加行锁之前，必须先加意向锁（表级）。

```c
// LOCK_IS（意向共享锁）：
//   表上"准备加共享行锁"的声明
//   兼容性：IS × IS ✅, IS × IX ✅（互不阻塞！）
//          IS × X  ❌, IS × S  ✅

// LOCK_IX（意向排他锁）：
//   表上"准备加排他行锁"的声明
//   兼容性：IX × IX ✅, IX × IS ✅
//          IX × X  ❌, IX × S  ❌

// 意义：如果没有意向锁，
// 事务 T2 想 LOCK TABLES ... WRITE 就得扫描所有行锁才能判断
// 有了意向锁，只需快速检查表级意向锁即可

// 加意向锁的源码路径：
// lock_table() → lock_table_enqueue() → 创建 LOCK_IS/LOCK_IX 表锁
```

**意向锁互斥矩阵**：

| 当前\请求 | IS | IX | S | X |
|-----------|----|----|---|---|
| IS | ✅ | ✅ | ✅ | ❌ |
| IX | ✅ | ✅ | ❌ | ❌ |
| S  | ✅ | ❌ | ✅ | ❌ |
| X  | ❌ | ❌ | ❌ | ❌ |

### 5.5 死锁检测

InnoDB 使用 **wait-for graph（等待图）** 进行死锁检测。

```c
// 源码：storage/innobase/lock/lock0lock.cc
// lock_deadlock_occurs() — 死锁检测核心函数
//
// 算法：DFS 遍历等待图，找环
// 1. 每个节点 = 事务
// 2. 每条边 = T1 → T2（T1 等待 T2 释放锁）
// 3. 从当前请求锁的事务开始 DFS
// 4. 如果发现已经访问过的节点（有环），即死锁

// 死锁代价计算（选择回滚的事务）：
// - 优先回滚修改量小的事务
// - 优先回滚锁数量少的事务
// - 如果有 UNDO 较少的，优先回滚（回滚成本低）

// 相关参数：
// innodb_deadlock_detect = ON（默认）
// innodb_lock_wait_timeout = 50（秒）

// 关闭死锁检测的风险：
// innodb_deadlock_detect = OFF 时
// 高并发场景下锁超时可能导致大量事务回滚
// 但 8.0.18+ 优化了这种情况，引入 innodb_use_native_aio
```

**检测时机**：每次尝试加锁但发现冲突时，将当前事务加入等待队列前触发死锁检测。

```sql
-- 查看最近一次死锁信息
SHOW ENGINE INNODB STATUS\G
-- 关注 LATEST DETECTED DEADLOCK 部分
```

**经典死锁示例**：

```sql
-- 事务 T1                    事务 T2
UPDATE t SET x=1 WHERE id=1;
                              UPDATE t SET x=2 WHERE id=2;
UPDATE t SET x=3 WHERE id=2;
                              UPDATE t SET x=4 WHERE id=1;
-- T1: 持有 id=1 锁，等待 id=2 锁
-- T2: 持有 id=2 锁，等待 id=1 锁
-- → 死锁！InnoDB 会选择 T1 或 T2 回滚
```

---

## 6. Buffer Pool 深入

Buffer Pool 是 InnoDB 性能的基石，理解其内部机制对 MySQL 调优至关重要。

### 6.1 内存管理：三大链表

#### LRU 链表

InnoDB 的 LRU 不是简单的最近最少使用，而是**冷热 LRU（Midpoint Insertion Strategy）**。

```
[young sublist: 63%] [---  midpoint ---] [old sublist: 37%]
    ↑ 热数据              分割线               ↓ 冷数据
    new→old 转换                         新页插入点
```

```c
// 源码：storage/innobase/buf/buf0lru.cc
// buf_LRU_add_block() — 新页插入逻辑
//
// 新页总是插入到 old 子列表的头部（midpoint 附近）
// 只有再次被访问且超过 innodb_old_blocks_time（默认1秒）后，
// 才被移到 young 子列表

// buf_LRU_make_block_young() — old→young 晋升
// 晋升条件：
// 1. 当前在 old 子列表中
// 2. 距上次访问时间 > innodb_old_blocks_time (ms)
// 3. 有空间移到 young 子列表头部

// 为什么用冷热 LRU？
// 防止全表扫描冲垮热数据！
// 全表扫描的页只在 old 区停留，不会被移到 young 区
// 除非被反复访问且时间跨度超过 innodb_old_blocks_time
```

#### Free 链表

空闲页链表，由 `buf_buddy_t` 管理页的分配与释放。

```c
// buf0buddy.cc — 伙伴分配器
// 注意：InnoDB 使用伙伴分配器管理 1x ~ 16KB 的大小分配
// 用于压缩页、blob 页等非标准大小的分配
```

#### Flush 链表

脏页链表，记录了所有被修改但未写入磁盘的页。

```c
// 当某页被修改（如 UPDATE/INSERT），在修改时：
// 1. 写入 redo log（WAL）
// 2. 标记页为 dirty
// 3. 将页加入 Flush List（按 oldest_modification 排序）

// Flush List 按 LSN 排序（最早修改的在前）
// 有利于 Checkpoint 时选择最老的脏页刷盘
```

### 6.2 预读与预写

**预读**已在 2.5 节详述，此处补充预写：

预写（Pre-Flush/Warming）：在 MySQL 正常关闭（`innodb_fast_shutdown=0`）时会将所有脏页刷入磁盘。重启时 Warm Buffer Pool 可加载上次关闭时的热页。

```c
// 8.0 新增：Buffer Pool Dump/Load
// innodb_buffer_pool_dump_at_shutdown = ON（默认）
// 关闭时将 BP 中的 page_no 列表 dump 到文件
// 启动时：innodb_buffer_pool_load_at_startup = ON
// 从文件读取 page_no 列表，异步加载热页到 BP

// SHOW STATUS 查看进度：
// Innodb_buffer_pool_load_status
// Innodb_buffer_pool_dump_status
```

### 6.3 页面淘汰策略

当 Free List 中页数不足时触发页面淘汰。

```c
// buf_LRU_scan_and_free_block() — 淘汰入口
//
// 核心逻辑：
// 1. 从 LRU old 尾部开始扫描
// 2. 最多扫 innodb_lru_scan_depth（默认1024）个页
// 3. 对每个页检查：
//    a) 是否被 pin（其他线程正在使用）→ 跳过
//    b) 是否为脏页 → 需要刷盘后才能踢出
//    c) 干净页 → 直接踢出
// 4. 脏页通过 Page Cleaner 异步刷盘

// 当系统内存不足时（Page Cleaner 赶不上），
// 用户线程也会参与脏页刷新（buf_flush_single_page_from_LRU()）
// 这是造成 SQL 响应时间抖动的一大原因！
```

**性能影响**：
- 单页刷盘（用户线程参与）是最大延迟来源
- `innodb_lru_scan_depth` × `innodb_buffer_pool_instances` 控制每次扫描量
- Page Cleaner 跟不上时 ⇒ 用户线程被迫刷脏页 ⇒ 响应时间冒尖

### 6.4 Checkpoint 技术

Checkpoint 的目的是缩小崩溃恢复时的 Redo Log 回放范围。

```c
// Fuzzy Checkpoint（模糊检查点）
// 特点：不等待所有脏页刷完，而是持续刷新最老的脏页
// 
// 两个关键标记：
// - oldest_lsn：Flush List 中最老的脏页 LSN
// - checkpoint_age = log_sys->lsn - oldest_lsn
//
// 触发模糊 Checkpoint 的条件：
// 1. 脏页比例超过 innodb_max_dirty_pages_pct（默认 75%）
// 2. Redo Log 使用量达到 innodb_log_file_size 的 75%
// 3. innodb_adaptive_flushing 自适应刷新（默认 ON）

// 适应性刷新（Adaptive Flushing）：
// af_get_pct_for_dirty() — 基于脏页比例计算刷新速度
// af_get_pct_for_lsn() — 基于 LSN 增量计算刷新速度
// 两者取较大值决定刷新速率

// 源码：storage/innobase/buf/buf0flu.cc
// buf_flush_page_cleaner() — Page Cleaner 主循环
// 每秒唤醒，检查是否需要刷脏页
```

**Checkpoint 类型**：

| 类型 | 触发条件 | 特点 |
|------|----------|------|
| Fuzzy Checkpoint | 脏页/日志超阈值 | 持续异步刷新，默认方式 |
| Flush LRU | BP 空闲页不足 | 用户线程可能参与 |
| Sync Checkpoint | DROP TABLE / FLUSH TABLES | 强制同步刷脏 |
| Sharp Checkpoint | 正常关闭 | 刷干净所有脏页 |

### 6.5 多 Buffer Pool 实例

当 `innodb_buffer_pool_size ≥ 1GB` 时，默认拆分为 8 个实例。

```c
// 每个实例拥有独立的：
// 1. LRU list
// 2. Free list  
// 3. Flush list
// 4. mutex（本实例锁）
// 5. pages 数组（本实例管理的页）

// 页到实例的映射：page_id % instance_count
// 简单哈希，性能开销极低

// 优点：
// - 锁竞争大幅降低（各个实例互不干扰）
// - 单个实例扫 LRU 耗时更短
// - 方便 NUMA 亲和性优化

// 配置：
// innodb_buffer_pool_instances = N
// 建议：每个实例 ≥ 1GB，通常设为 CPU 核心数
```

**监控多实例**：

```sql
SELECT POOL_ID, HIT_RATE, PAGES_FREE, PAGES_DATA
FROM performance_schema.innodb_buffer_pool_stats;
```

---

## 结论

本文从源码层面深入剖析了 InnoDB 存储引擎的六大核心机制：

| 维度 | 核心要点 | 关键配置 |
|------|----------|----------|
| 整体架构 | 内存-线程-磁盘三层闭环 | `innodb_buffer_pool_size` |
| 页管理 | 16KB 页结构、分裂合并、预读 | `innodb_page_size`, `innodb_read_ahead_threshold` |
| 行记录 | COMPACT/DYNAMIC/COMPRESSED 行格式 | `innodb_default_row_format` |
| 索引 | 聚簇索引、二级索引回表、AHI | `innodb_adaptive_hash_index` |
| 事务锁 | Record/Gap/Next-Key/意向锁，死锁检测 | `innodb_deadlock_detect` |
| Buffer Pool | 冷热LRU、三大链表、Checkpoint | `innodb_buffer_pool_instances` |

**调优黄金法则**：
1. BP 大小 = 物理内存的 60-80%（留 OS + 排序 + 连接内存）
2. BP 实例数 = min(CPU核数, BP大小/1GB)
3. `innodb_old_blocks_time=1000`（防止全表扫描冲击）
4. `innodb_flush_log_at_trx_commit=1`（ACID，除非性能特别敏感）
5. `innodb_io_capacity` 和 `innodb_io_capacity_max` 根据磁盘性能配置

下期预告：**数据库内核 #2：Redo Log 与崩溃恢复** — 深入 WAL 机制、Mini-Transaction、Group Commit、Recovery 三个阶段。
