# 第6课：并查集与平衡树

> DSU (Disjoint Set Union) / Treap / Splay
> 日期: 2026-05-13

## 一、并查集 (Disjoint Set Union)

### 1.1 基础回顾

并查集用于维护不相交集合的合并与查询操作：
- `find(x)`：查找 x 所在集合的代表元
- `union(x, y)`：合并 x 和 y 所在的集合

### 1.2 路径压缩 + 按秩合并

两者结合可以达到**近乎O(1)**的均摊时间复杂度。

**路径压缩（Path Compression）：**
```python
def find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])  # 递归，将路径上的所有节点直接指向根
    return parent[x]
```
树高被压缩为几乎常数。

**按秩合并（Union by Rank/Size）：**
```python
def union(x, y):
    rx, ry = find(x), find(y)
    if rx == ry:
        return
    if rank[rx] < rank[ry]:
        parent[rx] = ry
    elif rank[rx] > rank[ry]:
        parent[ry] = rx
    else:
        parent[ry] = rx
        rank[rx] += 1  # 只有相同秩合并才增加秩
```
- **按大小合并**（size）：将较小的树挂到较大的树下
- **按秩合并**（rank/高度近似）：将高度较低的树挂到较高的树下

**结论：** 路径压缩 + 按秩合并 → 时间复杂度为 **O(α(n))**，α为反阿克曼函数，几乎为常数。

### 1.3 带权并查集 (Weighted DSU)

在常规并查集的基础上，维护每个节点**到根的距离/权值**，用于处理偏移量关系问题。

**核心思想：**
- `parent[x]` 存储父节点
- `weight[x]` 存储 x **到 parent[x] 的权值**（不是到根的距离）

**find 时的权值更新：**
```python
def find(x):
    if parent[x] != x:
        orig_parent = parent[x]
        parent[x] = find(parent[x])     # 先递归
        weight[x] += weight[orig_parent] # 累加权值（到新根的距离）
    return parent[x]
```

**union 时的权值计算：**
```python
def union(x, y, w):
    # 合并后需满足: weight[x] + w_rel == weight[y] (某种关系)
    rx, ry = find(x), find(y)
    if rx != ry:
        # 计算 rx 应该接到 ry 时的权值
        parent[rx] = ry
        weight[rx] = weight[y] - weight[x] + w  # 或关系而定
```

**典型应用：**
1. **维护集合大小** — 在 union 时更新 size，query 时返回 size[root]
2. **维护到根的偏移量** — 如食物链（POJ 1182）、星球大战之类的关系问题
3. **维护区间和** — 通过带权并查集处理多个已知区间和关系

**经典问题：**
- **POJ 1182 食物链**：三类动物 A→B→C→A 循环捕食，维护每个节点到根的模3关系
- **HDU 3038**：给定多个区间和，判断矛盾数

### 1.4 可持久化并查集

> 需要维护历史版本，支持在某个历史版本上查询/合并。

**核心思路：**
- 使用**可持久化线段树（主席树）** 来存储 `parent` 和 `rank`（或 size）数组
- 每次 `union` 只修改少数节点（路径上），产生新版本
- 为了支持 `find`，需要：
  - 在 old 版本上读取 parent
  - 由于路径压缩在可持久化中代价高（需要写回），通常**放弃路径压缩**，只使用**按秩合并**
  - find 递归查根（仅读取，不修改）

**复杂度：**
- 时间复杂度：`find O(log^2 n)`（线段树查询 O(log n)，最多 log n 次递归），`union O(log^2 n)`
- 空间复杂度：每次 merge 产生 O(log n) 个新节点

**代码结构：**
```
可持久化数组（主席树） → parent[] 和 rank[]
find(x, version) → 从 version 读取 parent，递归找根
union(x, y, version) → 返回新版本
```

**应用场景：**
- 在线处理"在第 i 次操作后"的条件查询
- 图连通性的时间回溯问题

---

## 二、Treap（树堆）

### 2.1 基本性质

Treap = **Tree + Heap**（二叉搜索树 + 二叉堆）

每个节点包含：
- `key`：满足 BST 性质（左 < 根 < 右）
- `priority`：满足堆性质（通常用随机数，大根堆或小根堆）
  - **随机优先级**保证了树的平衡性：期望高度 O(log n)

**为什么随机化有效？**
随机优先级使树在插入顺序任意时依然接近均匀分布，复杂度为期望 O(log n)。

### 2.2 旋转操作 (Rotation)

传统 Treap 通过**左旋 / 右旋**维护堆性质：

```
右旋:
    P               L
   / \             / \
  L   C    →      A   P
 / \                 / \
A   B               B   C

左旋:
    P               R
   / \             / \
  A   R    →      P   C
     / \         / \
    B   C       A   B
```

旋转维持 BST 性质，同时调整父子关系以修复优先级的堆性质。

### 2.3 Split + Merge 法（无旋转 Treap）

更现代的写法，在竞赛中更常用，避免处理旋转细节。

**Split(root, key)：** 将树分成两棵：
- 左树：所有 key < `key` 的节点
- 右树：所有 key >= `key` 的节点

```python
def split(root, key):
    if root is None:
        return (None, None)
    if key <= root.key:         # 当前节点进入右树
        left, root.left = split(root.left, key)
        return (left, root)
    else:                       # 当前节点进入左树
        root.right, right = split(root.right, key)
        return (root, right)
```

**Merge(left, right)：** 合并两棵树（保证 left 中所有 key < right 中所有 key）
- 根据优先级决定谁做根

```python
def merge(left, right):
    if left is None: return right
    if right is None: return left
    if left.prio > right.prio:    # 大根堆：left 做根
        left.right = merge(left.right, right)
        return left
    else:
        right.left = merge(left, right.left)
        return right
```

### 2.4 基本操作

**插入 insert(key)：**
1. `split(root, key)` → `(left, right)`
2. 创建新节点 `node`
3. `root = merge(merge(left, node), right)`

**删除 erase(key)：**
1. `split(root, key)` → `(left, mid1)`  (mid1 中 key >= val)
2. `split(mid1, key + 1)` → `(mid, right)`  (mid 中 key == val)
3. 丢弃 mid（可选：如果 mid 是单节点，释放；允许重复则弹出一次）
4. `root = merge(left, right)`

**第 k 小 kth(k)：**
```python
def kth(root, k):
    left_size = size_of(root.left)
    if k <= left_size:
        return kth(root.left, k)
    elif k == left_size + 1:
        return root.key
    else:
        return kth(root.right, k - left_size - 1)
```
需要维护 `size` 属性，每次 split/merge 后更新。

**排名 rank(key)：** 严格小于 key 的节点数 + 1
1. `split(root, key)` → `(left, right)`
2. rank = size(left) + 1
3. `root = merge(left, right)`
4. 返回 rank

**前驱 predecessor(key)：** 小于 key 的最大值
- `split(root, key)` → `(left, right)`
- 如果 left 不为空，pre = left 中最右下的节点
- `root = merge(left, right)`

**后继 successor(key)：** 大于等于 key 的最小值
- `split(root, key)` → `(left, right)`
- 如果 right 不为空，suc = right 中最左下的节点
- `root = merge(left, right)`

**lower_bound(key)：** 第一个 >= key 的值
- 同后继而无需 split，直接递归找

### 2.5 复杂度总结

| 操作 | 复杂度 | 说明 |
|------|--------|------|
| insert | O(log n) 期望 | split + merge |
| erase | O(log n) 期望 | 两次 split |
| kth | O(log n) 期望 | 递归 |
| rank | O(log n) 期望 | split + size |
| pre/succ | O(log n) 期望 | split 或递归 |

---

## 三、Splay（简要）

### 3.1 核心思想

Splay 树通过 **splay 操作** 将刚访问的节点旋转到根：

- 每次 find / insert / delete 后都将目标节点 splay 到根
- 无显式的平衡条件，依靠 splay 操作维持均摊复杂度
- **均摊 O(log n)**

### 3.2 Splay 操作（三种情况）

设 x 为目标节点，p = parent(x)，g = parent(p)：

1. **Zig（单旋）：** p 为根 → 将 x 绕 p 旋起
2. **Zig-Zig（双旋同向）：** x 和 p 都是左/右子 → 先旋 p 再旋 x
3. **Zig-Zag（双旋反向）：** x 在 p 和 g 中间 → 旋两次 x

```
Zig-Zig (LL):
    g              x
   / \            / \
  p   D    →     A   p
 / \                / \
x   C              B   g
/ \                  / \
A B                 C   D
```

### 3.3 优势

1. **区间翻转（区间操作）：** Splay 通过"提取区间"可以很方便地处理区间反转、区间加减等操作
   - `splay(l-1)` 和 `splay(r+1)` 将区间 [l, r] 提取到一棵子树
   - 打 lazy tag 实现区间操作
2. **LCT（Link-Cut Tree）的基础：** 动态树（LCT）的核心数据结构就是 Splay
3. **不需要 priority 随机化**

### 3.4 Treap vs Splay 对比

| 特性 | Treap | Splay |
|------|-------|-------|
| 平衡方式 | 随机优先级 + 旋转/split-merge | 均摊 splay 到根 |
| 复杂度 | O(log n) 期望 | O(log n) 均摊 |
| 区间操作 | 较复杂，需隐式Treap | 天然支持（区间翻转等） |
| 代码量 | 较小（split+merge法） | 中等 |
| 最坏情况 | 概率极低的坏情况 | 单次可能 O(n) |
| 实现难度 | ⭐⭐ | ⭐⭐⭐ |
| 典型应用 | 普通平衡树、优先队列 | 区间操作、LCT |

### 3.5 隐式 Treap（区间操作替代方案）

Splay 不是区间操作的唯一选择。**隐式 Treap**（也称 Treap with implicit keys）也可以做区间反转：
- 用**子树大小**作为键（隐含的下标）
- 通过 split(root, k) 按大小拆分 → 提取区间
- 打 lazy tag

---

## 四、总结与思考

1. **并查集看似简单，但带权并查集解决了很多看似毫不相干的复杂问题**（关系推理、区间和一致性）
2. **可持久化并查集是"数据结构嵌套"的典型范例**：用可持久化线段树来实现数组版本化
3. **Treap 的 split+merge 比旋转实现更优雅**，是竞赛中最常用的平衡树写法
4. **Splay 虽然代码更长，但在区间操作和 LCT 领域无可替代**
5. **学习路线：** 普通 DSU → 带权 DSU → Treap (split+merge) → Splay → 隐式 Treap → LCT
