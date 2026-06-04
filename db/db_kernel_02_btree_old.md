# B+树与LSM-Tree：索引结构的核心对决

## 一、B+树基础

B+树是关系型数据库（MySQL InnoDB、PostgreSQL）最核心的索引结构。

### 1.1 B+树结构

```
              [M3, M7]              ← 根节点（内部节点，只有键）
             /    |    \
     [M1,M2]   [M4,M5,M6]  [M8,M9] ← 内部节点
      /  |  \    /  |  \     /  |  \
   [1,2][3,4][5,6][7,8][9,10]...   ← 叶子节点（键+值/指针）
```

**核心特性**：
- 所有数据存储在叶子节点
- 内部节点只存储键（路由信息）
- 叶子节点形成有序双向链表
- 每个节点存储 M 个键（通常 M 是 page 大小 ÷ 键大小）

### 1.2 节点结构

```c
struct BPlusTreeNode {
    bool is_leaf;
    int num_keys;         // 当前键数量
    Key keys[MAX_KEYS];    // 键数组
    union {
        BPlusTreeNode* children[MAX_KEYS + 1];  // 内部节点：子指针
        Value values[MAX_KEYS];                  // 叶子节点：值
    } data;
    BPlusTreeNode* next;   // 叶子节点的右兄弟指针
    BPlusTreeNode* prev;   // 叶子节点的左兄弟指针
};
```

---

## 二、B+树核心操作

### 2.1 查找

```c
Value* btree_search(BPlusTree* tree, Key key) {
    BPlusTreeNode* node = tree->root;
    
    while (!node->is_leaf) {
        // 二分查找找到大于等于 key 的最小子节点
        int i = lower_bound(node->keys, node->num_keys, key);
        node = node->data.children[i];
    }
    
    // 在叶子节点中查找
    int i = lower_bound(node->keys, node->num_keys, key);
    if (i < node->num_keys && node->keys[i] == key) {
        return &node->data.values[i];
    }
    return NULL; // 未找到
}
```

**时间复杂度**：O(log_m n)，其中 m 是阶数，n 是记录数。对于实际数据库，通常 3-4 层。

### 2.2 插入与 Split

当节点已满时，需要分裂（Split）：

```
插入 key=8 到已满节点 [1,3,5,7,9]

Step 1: 插入后 [1,3,5,7,8,9]（超出容量）
Step 2: 分裂为 [1,3,5] 和 [7,8,9]
Step 3: 将中值 7 提升到父节点
Step 4: 如果父节点也满了，递归分裂
```

**分裂策略**：
- 总是分裂为两个大小约相等的节点
- 中值键提升到父节点
- 分裂传播可能直到根节点（树高度 +1）

### 2.3 删除与 Merge

当节点键数量少于最小值（通常为 M/2）时，需要合并或借用：

```
节点不足的情况：
1. 先尝试从兄弟节点借用（Redistribution）
2. 如果兄弟也少，则合并（Coalesce）

合并：
[2,4] 和 [6,8] → 合并为 [2,4,6,8]
并从父节点删除分隔键
```

---

## 三、并发 B-Link Tree

### 3.1 传统 B+树的并发问题

B+树的分裂/合并操作需要加锁。最朴素的做法是对整棵树加锁，但并发度极差。

### 3.2 B-Link Tree 的核心思想

B-Link Tree 通过**右兄弟指针**和**链式搜索**实现了高效的并发访问：

```c
// B-Link Tree 插入（带右链）
void btree_insert_concurrent(BTree* tree, Key key, Value value) {
    BPlusTreeNode* node = tree->root;
    lock(node);  // 加锁
    
    while (!node->is_leaf) {
        int i = lower_bound(node->keys, node->num_keys, key);
        BPlusTreeNode* child = node->data.children[i];
        lock(child);
        
        if (!child->is_safe()) {  // 可能分裂
            // 预分裂 unsafe 节点
            if (child->is_full()) {
                split_child(node, child, i);
            }
        }
        
        unlock(node);  // 父节点释放锁
        node = child;  // 继续向下
    }
    
    // 到达叶子节点
    // ...
}
```

**关键点**：
- 父节点锁可以在子节点安全后释放（SX-lock 协议）
- 右兄弟指针保证搜索始终能找到正确的路径
- 即使分裂未完全更新父节点，通过右链也能到达

**对比**：

| 特性 | 传统 B+树 + 锁 | B-Link Tree |
|------|---------------|-------------|
| 并发度 | 低（整树锁或节点锁） | 高（只锁相邻节点） |
| 死锁风险 | 高 | 低 |
| 实现复杂度 | 低 | 高 |
| PostgreSQL 使用 | B-Link Tree style | - |

---

## 四、LSM-Tree（Log-Structured Merge-Tree）

LSM-Tree 是 NoSQL 数据库（LevelDB、RocksDB、Cassandra）的核心索引结构。

### 4.1 核心架构

```
[内存]
    MemTable (Sorted, 可写)   ← 写入先到这里
        ↓ 满后切换
    Immutable MemTable (只读)   ← 准备刷盘
        ↓ Flush
[磁盘]
    L0: SSTable文件集合 (无序，有重叠)
        ↓ Compaction
    L1: SSTable文件集合 (有序，无重叠)
        ↓ Compaction
    L2: SSTable文件集合 (有序，无重叠)
        ↓ Compaction
    L3: ...
```

### 4.2 SSTable 结构

```
SSTable 文件布局：
┌──────────────┐
│ Data Blocks   │  ← 键值对，按 key 排序
├──────────────┤
│ Filter Block  │  ← Bloom Filter，快速判断 key 是否存在
├──────────────┤
│ Index Block   │  ← 每个 Data Block 的最小 key 和 offset
├──────────────┤
│ Footer        │  ← Index/Filter 的 offset 和长度
└──────────────┘
```

**Bloom Filter**：用少量空间回答"key 一定不存在"或"key 可能存在"，大幅减少不必要的 I/O。

### 4.3 Compaction 策略

#### Leveled Compaction（LevelDB/RocksDB 默认）

```
L0: [a-z] [c-f] [x-z]     ← 无序，有重叠
  ↓ 合并到 L1
L1: [a-c] [d-g] [h-m] [n-z]  ← 有序，无重叠
  ↓ 当 L1 文件太多时合并到 L2
L2: [a-b] [c-e] ...
```

**特点**：
- 每层是上一层的 10 倍大小（默认放大因子）
- 写入放大：1 次写入 = 多次 Compaction
- 读放大：最坏情况需要检查所有层
- 空间放大：SSTable 不可变性导致旧版本数据滞留

#### Tiered Compaction（Cassandra 默认）

```
L0: [a-z]          ← 一个文件
    [a-z]          ← 另一个全量文件（重叠）
  ↓ 当有 4 个文件时合并
L1: [a-z]          ← 合并为一个文件
```

**特点**：
- 写入放大更小（延迟 Compaction）
- 读放大更大（需要检查更多文件）
- 空间放大也更大

### 4.4 LSM-Tree 读写路径

**写入**：
```c
void write(Key key, Value value) {
    // 1. 先写 WAL（持久化保证）
    write_wal(key, value);
    
    // 2. 写入活跃 MemTable（SkipList 保持有序）
    current_memtable->insert(key, value);
    
    // 3. 如果 MemTable 满，切换为 Immutable
    if (current_memtable->size > threshold) {
        switch_memtable();
        background_flush();  // 后台刷盘
    }
}
```

**读取**：
```c
Value* read(Key key) {
    // 1. 先查 MemTable
    Value* v = current_memtable->get(key);
    if (v) return v;
    
    // 2. 查 Immutable MemTable
    v = immutable_memtable->get(key);
    if (v) return v;
    
    // 3. 查 L0 （检查所有文件，用 Bloom Filter 加速）
    for (sst in L0_files) {
        if (sst.bloom_filter->may_contain(key)) {
            v = sst.get(key);
            if (v) return v;
        }
    }
    
    // 4. 查 L1-LN （二分查找确定目标文件）
    for (level in L1..LN) {
        sst = binary_search(level, key);
        if (sst && sst.bloom_filter->may_contain(key)) {
            v = sst.get(key);
            if (v) return v;
        }
    }
    
    return NULL; // 不存在
}
```

---

## 五、B+树 vs LSM-Tree 对比

| 维度 | B+树 | LSM-Tree |
|------|------|----------|
| 读性能 | ★★★★★（稳定 O(log n)） | ★★★☆☆（需查多层，有 Bloom Filter 优化） |
| 写性能 | ★★★☆☆（随机写，页分裂开销） | ★★★★★（顺序写，无更新） |
| 写放大 | 低（~1x） | 高（10-50x，取决于 Compaction 策略） |
| 空间放大 | 低 | 高（旧版本数据） |
| 范围查询 | ★★★★★（叶子链表遍历） | ★★★★☆（跨 SSTable 合并） |
| 磁盘碎片 | 有（页分裂后） | 无（顺序写入） |
| 持久化 | WAL + 脏页刷盘 | WAL + SSTable 刷盘 |
| 并发控制 | 复杂（分裂/合并锁） | 简单（SSTable 不可变） |
| 典型数据库 | MySQL, PostgreSQL, SQLite | LevelDB, RocksDB, Cassandra, HBase |

### 5.1 选择策略

```
场景偏向：
- 读密集型、数据量中等 → B+树（MySQL, PostgreSQL）
- 写密集型、数据量大 → LSM-Tree（RocksDB, Cassandra）
- 需要强实时性 → B+树
- 批量写入、日志类 → LSM-Tree
```

---

## 六、总结

- **B+树**通过平衡树结构提供稳定的 O(log_m n) 查询性能
- 节点**分裂（Split）**和**合并（Merge）**是 B+树维护平衡的核心操作
- **B-Link Tree** 通过右兄弟指针和链式搜索实现高并发
- **LSM-Tree** 通过内存缓存 + 顺序写 + Compaction 实现了极高的写性能
- **Leveled Compaction** 读性能更好（每层有序），**Tiered Compaction** 写放大更小
- **Bloom Filter** 是 LSM-Tree 读性能的关键优化手段
- B+树和 LSM-Tree 没有绝对好坏，取决于负载特征

下一课将探讨事务隔离与 MVCC 的实现机制。
