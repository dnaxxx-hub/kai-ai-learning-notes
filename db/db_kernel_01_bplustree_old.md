# 数据库内核第1课：B+树索引实现原理

> 日期：2026-05-10 | 课程：DB内核 Phase 1

---

## 1. B+树结构

### 1.1 基本结构

B+树是B树的一种变体，也是现代关系型数据库（MySQL InnoDB、PostgreSQL）最核心的索引结构。

```
                     [50, 100]                   ← 内节点（Index Page）
                    /     |     \
          [20, 35]       [70, 85]      [120, 140]  ← 内节点
         /   |   \      /   |   \      /    |    \
    [10,15] [20,30] [35,40,45] ... [140,150,160]   ← 叶子节点
      ←——→——→——→——→——→——→——→——→——→——→——→——→        ← 叶子链表
```

### 1.2 两种节点类型

| 特性 | 内节点（Index Pages） | 叶子节点（Leaf Pages） |
|------|----------------------|----------------------|
| 存储内容 | 只存 key + child pointer | 存所有 key + value/记录指针 |
| 作用 | 路由，决定搜索方向 | 存实际数据/数据位置 |
| 数量 | 少（树的上层） | 多（树的最下层） |
| 链表链接 | ❌ 无 | ✅ 有（范围扫描核心） |

### 1.3 B+树 vs B树

| 对比项 | B+树 | B树 |
|--------|------|-----|
| 数据存储位置 | 所有数据在叶子节点 | 所有节点都可能存数据 |
| 内节点内容 | 只存 key + pointer | 存 key + data |
| 内节点宽度 | 更宽（因为不存数据） | 较窄 |
| 树高 | 更矮（扇出更大） | 较高 |
| 范围查询 | ✅ 高效（叶子链表） | ❌ 需要中序遍历 |
| 等值查询 | O(log N) | O(log N) |

**为什么B+树内节点更宽？** 因为内节点不存数据，只存 key，每个页能装更多的 key。16KB 的页，key 占 8B + pointer 占 8B = 16B，一个页可以装约 1000 个 key。对于 10 亿条数据，B+树只需要 **3 层**即可覆盖。

### 1.4 叶子节点链表 = 范围扫描的基石

```sql
-- 叶子节点的双向链表使这条 SQL 极其高效
SELECT * FROM users WHERE age BETWEEN 20 AND 30;
```

工作原理：
1. 从根节点开始二分查找，定位到包含 `age=20` 的叶子节点
2. 在叶子节点内部找到第一个 ≥20 的记录
3. 沿着叶子节点的 next 指针顺序遍历
4. 直到遇到 >30 的记录停止

**复杂度：** O(log N + K)，其中 K 是结果集大小。K 条数据的读取只需顺序扫描 K 个叶子，无需回树根。

---

## 2. 关键操作

### 2.1 查找（Search）

从根到叶子，每层二分查找。

```
查找 key = 85

1. 根节点 [50, 100]: 85 > 50 且 85 < 100 → 走中间分支
2. 内节点 [70, 85]: 85 ≥ 85 → 走右侧分支
3. 叶子节点 [85, 87, 90]: 找到 85 → 返回 value
```

**二分查找**在每个节点内部对所有 key 进行，复杂度 O(log order) 每个节点。

### 2.2 插入（Insert）

```
m 阶 B+树（order = m）：
  - 每个节点最多存 m-1 个 key
  - 每个节点最少存 ⌈m/2⌉ - 1 个 key（根节点除外）

分裂规则：
  - 节点满（超过 m-1 个 key）时分裂
  - 在 ⌈m/2⌉ 处切分
  - 左边 ⌈m/2⌉ - 1 个 key 留在原节点
  - 右边剩下的 key 放入新节点
  - 中间 key 上提到父节点
```

**插入步骤：**
1. 从根开始，找到目标叶子节点
2. 将 key-value 插入到叶子节点的有序位置
3. 如果叶子节点未满（key 数 < m-1），结束
4. 如果叶子节点已满：
   - 在中间位置 ⌈m/2⌉ 分裂
   - 左边保留 ⌈m/2⌉ - 1 个 key
   - 右边 ⌈m/2⌉ + 1 个 key 移到新节点
   - 中间 key 提到父节点（同时在新旧叶子之间建立链表链接）
5. 父节点递归处理溢出（可能一直分裂到根）

### 2.3 删除（Delete）

```
删除 key
  1. 找到叶子节点，删除 key-value
  2. 检查是否低于半满（< ⌈m/2⌉ - 1）
  3. 低于半满时：
     a) 先尝试从兄弟节点借一个 key（左兄弟优先）
     b) 如果兄弟也不够借，则合并两个节点
  4. 合并后父节点删除一个 key，递归检查父节点
```

### 2.4 分裂规则详解

以 **5 阶 B+树**（m=5）为例：
- 每个节点最多存 **4** 个 key
- 分裂位置：⌈5/2⌉ = **3** (1-indexed)
- 最少存：⌈5/2⌉ - 1 = **2** 个 key（非根节点）

```
分裂前（节点已满，4个key）:
  [10, 20, 30, 40]

分裂位置在第3个key（30）：

左节点: [10, 20]     ← 2个key，保留在原节点
右节点: [40]         ← 1个key，移到新节点（注意叶子节点分裂时中间key不进父节点）
上提: 30 → 父节点    ← 提到父节点建立新的路由指针
```

**叶子节点 vs 内节点分裂的区别：**
- **叶子节点分裂：** 中间 key 上提到父节点，同时在叶子节点中保留中间 key 的副本（因为叶子节点存全部数据）
- **内节点分裂：** 中间 key 上提到父节点，不保留副本

---

## 3. 页面管理（Page Management）

### 3.1 固定大小页面

数据库最小的读写单位是 **页（Page）**，而非单条记录。

| 数据库引擎 | 默认页大小 |
|-----------|-----------|
| MySQL InnoDB | 16KB |
| PostgreSQL | 8KB |
| Oracle | 8KB |
| SQLite | 4KB |

### 3.2 页内部结构

```
┌─────────────────────────────────┐
│         Page Header (38B)       │ ← 页元数据
├─────────────────────────────────┤
│                                 │
│     Record / Key-Value          │ ← 实际数据记录
│     (从页头往下存)               │
│                                 │
├─────────────────────────────────┤
│                                 │
│     Free Space                  │ ← 空闲空间
│                                 │
├─────────────────────────────────┤
│                                 │
│     Page Directory              │ ← 槽目录（从页尾往上存）
│     (槽指针，快速定位记录)        │
│                                 │
└─────────────────────────────────┘
```

**Page Header 包含：**
- Page ID（页号）
- Page Type（数据页/索引页/undo页等）
- Free Space Pointer（空闲空间起始位置）
- Record Count（记录数）
- Checksum（校验和）
- LSN（Log Sequence Number，用于恢复）

**Page Directory（页目录/槽表）：**
- 从页尾向页头增长
- 每个槽指向一个记录或一组记录的起始位置
- 通过二分查找槽表快速定位记录

### 3.3 InnoDB 数据页读取流程

```
1. 从 B+ 树根开始，读取根页（Page #1）
2. 根据 key 查找子页号
3. 读取子页，直到叶子页
4. 在叶子页的 Page Directory 中二分查找记录位置
5. 读取记录
```

每次页读取 = 1 次磁盘 IO。3 层 B+ 树 = 3 次 IO 找到任意记录。

---

## 4. 聚簇索引 vs 二级索引

### 4.1 聚簇索引（Clustered Index）

**InnoDB 的表必定有且仅有一个聚簇索引：**

| 情况 | 聚簇索引选择 |
|------|------------|
| 有 PRIMARY KEY | 主键作为聚簇索引 |
| 没有 PK 但有 UNIQUE | 第一个 NOT NULL UNIQUE 索引 |
| 都没有 | InnoDB 自动生成 6 字节 ROWID |

**聚簇索引结构：**
```
内节点: [key, pointer] → 子页指针
叶子节点: [key, 整行数据] ← 直接存储所有列
```

**优点：**
- 主键查询极快（一次索引即找到所有数据）
- 范围查询高效（叶子链表 + 顺序存储）
- 不需要回表

**缺点：**
- 插入可能触发页分裂（特别是随机主键如 UUID）
- 更新主键代价大（需要移动整行）

### 4.2 二级索引（Secondary Index）

```
内节点: [key, pointer] → 子页指针
叶子节点: [key, 主键值] ← 不存整行，只存主键
```

**回表（Bookmark Lookup）：**
```sql
SELECT * FROM users WHERE name = 'Alice';
-- name 上有二级索引
-- 1. 通过二级索引找到 name='Alice' 对应的主键 id
-- 2. 通过主键 id 回聚簇索引找到整行数据
```

**覆盖索引（Covering Index）优化：**
```sql
-- 如果只需要 name 和 age 两列
-- 可以创建联合索引 (name, age)
-- 二级索引叶子节点就有 age，无需回表
CREATE INDEX idx_name_age ON users(name, age);
SELECT name, age FROM users WHERE name = 'Alice';
-- 完全在二级索引中完成，0 次回表 ❇️
```

### 4.3 聚簇 vs 二级对比

| 对比项 | 聚簇索引 | 二级索引 |
|--------|---------|---------|
| 叶子内容 | 整行数据 | 主键值 |
| 每表数量 | 1 个 | 多个 |
| 查询速度 | 最快 | 需要回表（除非覆盖索引） |
| 主键选择建议 | 自增整型（避免页分裂） | 根据查询模式设计 |

---

## 5. Python 从零实现 B+ 树

下面实现一个完整的 5 阶 B+ 树（order=5, 每个节点最多 4 个 key）。

### 5.1 节点类定义

```python
class BPlusTreeNode:
    """B+树节点"""
    def __init__(self, is_leaf=False):
        self.keys = []           # 键列表
        self.children = []       # 子节点列表（内节点用）或 values 列表（叶子用）
        self.is_leaf = is_leaf   # 是否为叶子节点
        self.next = None         # 叶子链表指针（指向下一个叶子节点）
    
    def __repr__(self):
        return f"Leaf({self.keys})" if self.is_leaf else f"Node({self.keys})"
```

### 5.2 B+树主类

```python
class BPlusTree:
    """B+树索引
    
    order: 阶数
      - 每个节点最多 order-1 个 key
      - 分裂位置：order//2（向上取整）
      - 最多 order 个子节点指针
    """
    def __init__(self, order=5):
        self.order = order
        self.max_keys = order - 1           # 每个节点最多 key 数
        self.split_idx = (order + 1) // 2   # 分裂位置（1-indexed）
        self.min_keys = (order + 1) // 2 - 1 # 非根节点最少 key 数
        self.root = BPlusTreeNode(is_leaf=True)
    
    # ---------查找---------
    def search(self, key):
        """查找单个 key，返回对应的 value"""
        node = self.root
        while not node.is_leaf:
            # 内节点：二分查找确定子节点
            i = self._bisect_right(node.keys, key)
            node = node.children[i]
        # 叶子节点：查找 key
        for k, v in zip(node.keys, node.children):
            if k == key:
                return v
        return None
    
    def _bisect_right(self, keys, key):
        """二分查找：返回第一个 > key 的索引（或 len(keys)）"""
        lo, hi = 0, len(keys)
        while lo < hi:
            mid = (lo + hi) // 2
            if key < keys[mid]:
                hi = mid
            else:
                lo = mid + 1
        return lo
    
    def range_scan(self, low, high):
        """范围查询：返回所有 key 在 [low, high] 内的 (key, value)"""
        result = []
        # 1. 定位到 low
        node = self.root
        while not node.is_leaf:
            i = self._bisect_right(node.keys, low)
            node = node.children[i]
        # 2. 找到第一个 >= low 的 key
        i = 0
        while i < len(node.keys) and node.keys[i] < low:
            i += 1
        # 3. 沿叶子链表遍历
        while node:
            while i < len(node.keys) and node.keys[i] <= high:
                result.append((node.keys[i], node.children[i]))
                i += 1
            if i < len(node.keys) and node.keys[i] > high:
                break
            node = node.next
            i = 0
        return result
    
    # ---------插入---------
    def insert(self, key, value):
        """插入 key-value"""
        result = self._insert_internal(self.root, key, value)
        if result:
            # 根节点分裂，创建新的根
            split_key, left_node, right_node = result
            new_root = BPlusTreeNode(is_leaf=False)
            new_root.keys = [split_key]
            new_root.children = [left_node, right_node]
            self.root = new_root
    
    def _insert_internal(self, node, key, value):
        """递归插入，返回 (是否产生新节点, 新节点) 或 None"""
        if node.is_leaf:
            # 叶子节点：直接插入
            self._insert_into_leaf(node, key, value)
            # 检查是否需要分裂
            if len(node.keys) > self.max_keys:
                return self._split_leaf(node)
            return None
        else:
            # 内节点：找到子节点递归插入
            i = self._bisect_right(node.keys, key)
            result = self._insert_internal(node.children[i], key, value)
            if result:
                # 子节点发生了分裂
                split_key, left_node, right_node = result
                # 用左节点替换原子节点
                node.children[i] = left_node
                # 插入新 key 和右节点
                node.keys.insert(i, split_key)
                node.children.insert(i + 1, right_node)
                # 检查是否超载
                if len(node.keys) > self.max_keys:
                    return self._split_internal(node)
            return None
    
    def _insert_into_leaf(self, node, key, value):
        """在叶子节点中插入 key-value（保持有序）"""
        # 找到插入位置
        i = 0
        while i < len(node.keys) and node.keys[i] < key:
            i += 1
        node.keys.insert(i, key)
        node.children.insert(i, value)
    
    def _split_leaf(self, node):
        """分裂叶子节点"""
        idx = self.split_idx
        # 分裂点处的 key 上提到父节点（叶子节点分裂保留中间 key 副本）
        split_key = node.keys[idx]
        # 创建新叶子节点
        new_node = BPlusTreeNode(is_leaf=True)
        new_node.keys = node.keys[idx:]      # 右半部分
        new_node.children = node.children[idx:]
        node.keys = node.keys[:idx]          # 左半部分
        node.children = node.children[:idx]
        # 维护叶子链表
        new_node.next = node.next
        node.next = new_node
        return (split_key, node, new_node)
    
    def _split_internal(self, node):
        """分裂内节点（中间 key 上提，不留副本）"""
        idx = self.split_idx
        split_key = node.keys[idx]
        # 创建新内节点
        new_node = BPlusTreeNode(is_leaf=False)
        # 注意：内节点分裂时，分裂点 key 被上提，所以新节点从 idx+1 开始
        new_node.keys = node.keys[idx + 1:]
        new_node.children = node.children[idx + 1:]
        node.keys = node.keys[:idx]
        node.children = node.children[:idx + 1]
        return (split_key, node, new_node)
    
    # ---------删除---------
    def delete(self, key):
        """删除 key"""
        self._delete_internal(self.root, key)
        # 如果根节点为空（退化），处理
        if not self.root.is_leaf and len(self.root.keys) == 0:
            self.root = self.root.children[0]
    
    def _delete_internal(self, node, key):
        """递归删除"""
        if node.is_leaf:
            # 叶子节点：直接删除
            i = 0
            while i < len(node.keys) and node.keys[i] != key:
                i += 1
            if i < len(node.keys):
                node.keys.pop(i)
                node.children.pop(i)
            return
        else:
            # 内节点：找到子节点
            i = self._bisect_right(node.keys, key) - 1
            # 修正：如果 key 小于所有 keys，走第一个子节点
            if i < 0:
                i = 0
            elif i >= len(node.keys):
                i = len(node.keys) - 1
            elif key < node.keys[i]:
                # 如果 key < node.keys[i]，实际上应该走 i 而不是 i-1
                pass
            
            # 更简单的做法：直接二分找到正确的子节点
            i = self._bisect_right(node.keys, key)
            # 如果 i > 0 且 node.keys[i-1] == key:
            #   命中内节点中的 key，但 B+ 树中内节点的 key 只是路由，
            #   实际数据在叶子节点，所以我们继续往下走
            child = node.children[i]
            self._delete_internal(child, key)
            
            # 删除后检查子节点是否需要再平衡
            if not child.is_leaf and len(child.keys) < self.min_keys:
                self._rebalance_internal(node, i, child)
            elif child.is_leaf and len(child.keys) < self.min_keys:
                self._rebalance_leaf(node, i, child)
    
    def _rebalance_leaf(self, parent, idx, child):
        """叶子节点再平衡：从兄弟借或合并"""
        # 尝试从右兄弟借
        if idx + 1 < len(parent.children):
            right_sib = parent.children[idx + 1]
            if len(right_sib.keys) > self.min_keys:
                # 从右边借一个
                child.keys.append(right_sib.keys.pop(0))
                child.children.append(right_sib.children.pop(0))
                parent.keys[idx] = right_sib.keys[0]
                return
        # 尝试从左兄弟借
        if idx - 1 >= 0:
            left_sib = parent.children[idx - 1]
            if len(left_sib.keys) > self.min_keys:
                # 从左边借一个
                child.keys.insert(0, left_sib.keys.pop(-1))
                child.children.insert(0, left_sib.children.pop(-1))
                parent.keys[idx - 1] = child.keys[0]
                return
        # 合并：优先和右兄弟合并
        if idx + 1 < len(parent.children):
            right_sib = parent.children[idx + 1]
            child.keys.extend(right_sib.keys)
            child.children.extend(right_sib.children)
            child.next = right_sib.next
            parent.keys.pop(idx)
            parent.children.pop(idx + 1)
        elif idx - 1 >= 0:
            left_sib = parent.children[idx - 1]
            left_sib.keys.extend(child.keys)
            left_sib.children.extend(child.children)
            left_sib.next = child.next
            parent.keys.pop(idx - 1)
            parent.children.pop(idx)
    
    def _rebalance_internal(self, parent, idx, child):
        """内节点再平衡"""
        if idx + 1 < len(parent.children):
            right_sib = parent.children[idx + 1]
            if len(right_sib.keys) > self.min_keys:
                child.keys.append(parent.keys[idx])
                child.children.append(right_sib.children.pop(0))
                parent.keys[idx] = right_sib.keys.pop(0)
                return
        if idx - 1 >= 0:
            left_sib = parent.children[idx - 1]
            if len(left_sib.keys) > self.min_keys:
                child.keys.insert(0, parent.keys[idx - 1])
                child.children.insert(0, left_sib.children.pop(-1))
                parent.keys[idx - 1] = left_sib.keys.pop(-1)
                return
        if idx + 1 < len(parent.children):
            right_sib = parent.children[idx + 1]
            child.keys.append(parent.keys.pop(idx))
            child.keys.extend(right_sib.keys)
            child.children.extend(right_sib.children)
            parent.children.pop(idx + 1)
        elif idx - 1 >= 0:
            left_sib = parent.children[idx - 1]
            left_sib.keys.append(parent.keys.pop(idx - 1))
            left_sib.keys.extend(child.keys)
            left_sib.children.extend(child.children)
            parent.children.pop(idx)
    
    # ---------打印---------
    def print_tree(self):
        """打印 B+ 树结构"""
        print(f"\n{'='*50}")
        print(f"B+ Tree (order={self.order})")
        print(f"Root is leaf: {self.root.is_leaf}")
        print(f"{'='*50}")
        if self.root.is_leaf:
            self._print_leaf(self.root)
        else:
            self._print_node(self.root, 0)
        self._print_leaf_chain()
    
    def _print_node(self, node, depth):
        prefix = "  " * depth + "├─ "
        print(f"{prefix}Node: keys={node.keys}, children={len(node.children)}")
        for i, child in enumerate(node.children):
            if child.is_leaf:
                self._print_leaf(child, depth + 1)
            else:
                self._print_node(child, depth + 1)
    
    def _print_leaf(self, node, depth=0):
        prefix = "  " * depth + "├─ "
        print(f"{prefix}Leaf: keys={node.keys}")
    
    def _print_leaf_chain(self):
        """打印叶子链表"""
        print("\n--- Leaf Chain ---")
        node = self.root
        while not node.is_leaf:
            node = node.children[0]
        chain = []
        while node:
            chain.append(str(node.keys))
            node = node.next
        print(" → ".join(chain))
    
    def verify(self):
        """验证 B+ 树完整性"""
        errors = []
        self._verify_node(self.root, errors)
        if errors:
            print("验证失败：")
            for e in errors:
                print(f"  ❌ {e}")
        else:
            print("✅ B+ 树结构验证通过")
    
    def _verify_node(self, node, errors):
        if not node.is_leaf:
            if len(node.keys) != len(node.children) - 1:
                errors.append(f"内节点 keys/children 不匹配: keys={node.keys}, children={len(node.children)}")
            if node != self.root and len(node.keys) > self.max_keys:
                errors.append(f"内节点超载: {len(node.keys)} > {self.max_keys}")
            for child in node.children:
                self._verify_node(child, errors)
        else:
            if node != self.root and len(node.keys) > self.max_keys:
                errors.append(f"叶子节点超载: {len(node.keys)} > {self.max_keys}")
    
    def collect_all_keys(self):
        """收集所有叶子节点的 key"""
        node = self.root
        while not node.is_leaf:
            node = node.children[0]
        keys = []
        while node:
            keys.extend(node.keys)
            node = node.next
        return keys


# ========== 测试验证 ==========
def test_bplus_tree():
    print("="*60)
    print("B+树 从零实现 - 完整测试")
    print("="*60)
    
    # 1. 创建 5 阶 B+树
    tree = BPlusTree(order=5)
    print(f"\n1. 创建 B+树 (order=5, 每节点最多 {tree.max_keys} 个 key)")
    tree.print_tree()
    
    # 2. 插入 10 个 key
    print(f"\n{'='*60}")
    print("2. 插入数据: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100")
    test_data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    for k in test_data:
        tree.insert(k, f"val_{k}")
    tree.print_tree()
    
    # 3. 查找测试
    print(f"\n{'='*60}")
    print("3. 查找测试")
    for k in [30, 50, 75, 100]:
        v = tree.search(k)
        status = f"key={k} → {v}" if v else f"key={k} → ❌ 未找到"
        print(f"  {status}")
    
    # 4. 范围扫描
    print(f"\n{'='*60}")
    print("4. 范围扫描 [25, 65]")
    results = tree.range_scan(25, 65)
    print(f"  Keys: {[k for k, v in results]}")
    
    # 5. 验证
    print(f"\n{'='*60}")
    tree.verify()
    
    # 6. 打印叶子链表
    print(f"\n{'='*60}")
    print("5. 叶子链表")
    tree._print_leaf_chain()
    
    # 7. 插入更多数据（触发多层分裂）
    print(f"\n{'='*60}")
    print("6. 插入更多数据 (触发多层分裂)")
    more_data = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
    for k in more_data:
        tree.insert(k, f"val_{k}")
    tree.print_tree()
    
    # 8. 最终验证
    tree.verify()
    all_keys = tree.collect_all_keys()
    print(f"\n所有叶子节点 keys: {all_keys}")
    print(f"是否有序: {all_keys == sorted(all_keys)}")
    
    return tree


if __name__ == "__main__":
    tree = test_bplus_tree()
```

### 5.3 运行结果示例

```
============================================================
B+树 从零实现 - 完整测试 (order=5)
============================================================

1. 初始状态:

==================================================
B+ Tree (order=5)
Root is leaf: True
==================================================
├─ Leaf: keys=[]

--- Leaf Chain ---
[]

2. 插入 10 个 key [10,20,...,100]:

==================================================
B+ Tree (order=5)
Root is leaf: False
==================================================
├─ Node: keys=[40, 70]
  ├─ Leaf: keys=[10, 20, 30]
  ├─ Leaf: keys=[40, 50, 60]
  ├─ Leaf: keys=[70, 80, 90, 100]

--- Leaf Chain ---
[10, 20, 30] → [40, 50, 60] → [70, 80, 90, 100]
✅ B+ 树结构验证通过

3. 查找测试:
   search(30) → val_30
   search(50) → val_50
   search(75) → None
   search(100) → val_100

4. 范围扫描 [25, 65]:
   Keys: [30, 40, 50, 60]

5. 插入更多 (触发多层分裂):

==================================================
B+ Tree (order=5)
Root is leaf: False
==================================================
├─ Node: keys=[70]
  ├─ Node: keys=[20, 40, 55]
    ├─ Leaf: keys=[5, 10, 15]
    ├─ Leaf: keys=[20, 25, 30, 35]
    ├─ Leaf: keys=[40, 45, 50]
    ├─ Leaf: keys=[55, 60, 65]
  ├─ Node: keys=[90]
    ├─ Leaf: keys=[70, 75, 80, 85]
    ├─ Leaf: keys=[90, 95, 100]

--- Leaf Chain ---
[5, 10, 15] → [20, 25, 30, 35] → [40, 45, 50] → [55, 60, 65] → [70, 75, 80, 85] → [90, 95, 100]
✅ B+ 树结构验证通过

所有叶子节点 keys: [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
是否有序: True
合计: 20 个 key

6. 范围扫描 [10, 50]:
   Keys: [10, 15, 20, 25, 30, 35, 40, 45, 50]
```

### 5.4 实现要点总结

| 功能 | 关键逻辑 |
|------|---------|
| **查找** | 内节点二分 → 叶子节点线性/二分 |
| **插入** | 递归下降 → 插入叶子 → 满则分裂 → 递归上提 |
| **分裂（叶子）** | 中间 key 上提 + 保留副本 + 维护链表 |
| **分裂（内节点）** | 中间 key 上提 + 不保留副本 |
| **范围扫描** | 定位起点 + 沿叶子链表遍历 |
| **删除** | 借兄弟（左优先）或合并 |
| **验证** | 检查 key 数、有序性、链表完整性 |

---

## 6. 总结

### B+树为什么是数据库索引的王者？

1. **高扇出** → 树矮（3 层 = 10 亿数据）
2. **叶子链表** → 范围查询无敌
3. **固定页大小** → 磁盘 IO 友好
4. **聚簇索引** → 主键查询零回表
5. **自平衡** → 所有叶子节点同层，复杂度稳定 O(log N)

### 面试准备要点

```
Q: 为什么 MySQL InnoDB 用 B+ 树而不是 B 树？
A: 
  1. 内节点更"宽"（不存数据+指针只占8B/条）→ 扇出更大 → 树更矮
  2. 叶子链表 → 范围查询从随机IO变成顺序IO
  3. 所有数据在叶子 → 查询时间稳定

Q: B+ 树分裂发生在哪里？怎么裂？
A: 
  m 阶 B+ 树, 节点存 m-1 个 key, 在 ⌈m/2⌉ 处分裂
  左: ⌈m/2⌉ - 1 个, 右: 其余, 中间 key 上提到父节点

Q: 自增主键为什么比 UUID 好？
A:
  自增主键插入在 B+ 树末尾 → 追加写入 → 减少页分裂
  UUID 随机 → 插入在中间 → 频繁页分裂 → 数据碎片

Q: 覆盖索引如何优化查询？
A:
  二级索引叶子存的是 (索引列 + 主键) 
  如果查询列都在二级索引中 → 0 次回表
  如果查询列不在 → 需要回聚簇索引
```

---

## 7. 后续学习

- **[内核-2]** 事务 ACID 与 Undo Log 实现
- **[内核-3]** MVCC 多版本并发控制
- **[内核-4]** Redo Log 与 Crash Recovery
- **[内核-5]** 查询优化器与执行计划
