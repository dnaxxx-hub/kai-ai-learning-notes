# 第5课：线段树与树状数组

> 日期: 2025-05-09 | 路线图: Phase 4 波次1

---

## 一、线段树 (Segment Tree)

### 1.1 基本概念

线段树是一种**二叉树**，用于对一个数组的**区间**进行高效的查询和更新。每个节点代表数组的一个区间 `[L, R]`。

- 叶子节点：长度为 1 的区间
- 内部节点：将区间 `[L, R]` 均分为 `[L, M]` 和 `[M+1, R]`，其中 `M = (L+R)//2`
- 树高：`O(log N)`，N 为数组长度

### 1.2 建树 (Build)

**思路**：递归构建。如果 L == R，叶子节点直接赋值；否则递归建左右子树，然后上推合并。

**伪代码**：
```
build(node, L, R):
    if L == R:
        tree[node] = arr[L]
    else:
        M = (L+R)//2
        build(node*2, L, M)
        build(node*2+1, M+1, R)
        tree[node] = tree[node*2] + tree[node*2+1]
```

**数组表示**：根节点下标为 1，左子 = 2*node，右子 = 2*node+1。数组大小开 4N 保证安全。

**复杂度**：`O(N)` 时间，`O(N)` 空间。

### 1.3 单点更新 (Point Update)

**思路**：从根递归到叶子，更新叶子值，回溯时更新所有祖先。

```
update(node, L, R, pos, val):
    if L == R:
        tree[node] = val
    else:
        M = (L+R)//2
        if pos <= M: update(left, L, M, pos, val)
        else: update(right, M+1, R, pos, val)
        tree[node] = tree[left] + tree[right]
```

**复杂度**：`O(log N)`

### 1.4 区间查询 (Range Query)

**思路**：递归查询。如果当前节点区间完全在查询范围内，直接返回值；部分重叠则递归左右子树合并。

```
query(node, L, R, ql, qr):
    if ql <= L and R <= qr: return tree[node]
    M = (L+R)//2
    res = 0
    if ql <= M: res += query(left, L, M, ql, qr)
    if qr > M:  res += query(right, M+1, R, ql, qr)
    return res
```

**复杂度**：`O(log N)` — 因为每层最多访问 4 个节点。

### 1.5 区间更新 + 懒标记 (Lazy Propagation)

**核心思想**：对于区间更新操作（如区间每个元素加 val），不立即更新所有叶子，而是在节点上标记"待更新"的信息。查询/更新时若遇到标记，先下推给子节点再继续。

```
apply(node, L, R, val):
    tree[node] += val * (R - L + 1)
    lazy[node] += val

push(node, L, R):
    if lazy[node] != 0:
        M = (L+R)//2
        apply(node*2, L, M, lazy[node])
        apply(node*2+1, M+1, R, lazy[node])
        lazy[node] = 0

range_update(node, L, R, ql, qr, val):
    if ql <= L and R <= qr:
        apply(node, L, R, val)
        return
    push(node, L, R)
    M = (L+R)//2
    if ql <= M: range_update(left, L, M, ql, qr, val)
    if qr > M:  range_update(right, M+1, R, ql, qr, val)
    tree[node] = tree[left] + tree[right]
```

区间查询时也须先 push 再递归。

**复杂度**：区间更新 `O(log N)`，区间查询 `O(log N)`。

**为什么叫 Lazy**？因为更新信息被"懒"地留在高层节点，直到真的需要时才向下传播。这避免了 O(N) 的暴力更新。

---

## 二、树状数组 (Fenwick Tree / BIT)

### 2.1 基本原理

树状数组用 **O(log N)** 时间处理**单点更新 + 前缀和查询**，代码极短（~10行）。

核心思想：利用 lowbit 分解区间，每个下标 i 负责 `[i - lowbit(i) + 1, i]` 的和。

### 2.2 lowbit

```
lowbit(x) = x & (-x)   # 取最低位 1 的值
```

- `lowbit(6)=2` (二进制 110 → 10)
- `lowbit(8)=8` (二进制 1000 → 1000)
- `lowbit(7)=1` (二进制 111 → 1)

lowbit 将整数分解为若干个 2 的幂次之和，每个幂次对应 BIT 中的一个区间。

### 2.3 单点更新 + 前缀和查询

**更新**：在位置 i 加 val，则将所有覆盖 i 的区间更新：
```
while i <= n:
    bit[i] += val
    i += lowbit(i)
```

**前缀和**：求 sum[1..i]：
```
res = 0
while i > 0:
    res += bit[i]
    i -= lowbit(i)
return res
```

**区间查询** `[L, R]`：`sum(R) - sum(L-1)`

### 2.4 区间更新 + 区间查询（差分 BIT）

使用**两个 BIT** 实现：

设原始数组 a，维护差分数组 `d[i] = a[i] - a[i-1]`（定义 `a[0]=0`）。

- 区间加 `[L, R] += val`：`d[L] += val, d[R+1] -= val`
- 前缀和 `sum[1..k]` = `k * Σd[i] - Σ((i-1) * d[i])` (i=1..k)

所以用两个 BIT：
- `bit1` 维护 `d[i]`
- `bit2` 维护 `(i-1) * d[i]`

**区间加** `[L, R] += val`：
```
add(bit1, L, val);  add(bit1, R+1, -val)
add(bit2, L, (L-1)*val);  add(bit2, R+1, R*(-val))
```

**前缀和** `sum(k)`：
```
return k * query(bit1, k) - query(bit2, k)
```

**区间查询** `[L, R]`：`sum(R) - sum(L-1)`

**复杂度**：单次操作 O(log N)，代码简洁 ≈ 15 行。

**对比线段树**：
- BIT：代码极短，常数极小，但功能有限（只能处理可逆/可差分的操作）
- 线段树：代码较长，功能更强（区间最值、复杂合并）

---

## 三、离散化 (Discretization)

### 3.1 为什么要离散化

当数据范围极大（如坐标范围 1e9），但实际数据点很少时（如 N=1e5），直接按值域开数组不可行（空间爆炸）。

**离散化将原始值映射到连续的整数下标**，从而可以在紧凑空间上使用线段树/BIT等。

典型场景：
- 矩形面积并中的坐标
- 值域很大的统计问题
- 动态开点不好用的场景

### 3.2 实现方法

```python
def discretize(arr):
    """对arr去重排序，返回(原值→rank的映射, 原值排序列表)"""
    sorted_uniq = sorted(set(arr))
    mapping = {v: i for i, v in enumerate(sorted_uniq)}  # 0-based
    return mapping, sorted_uniq

def get_rank(value, mapping):
    return mapping[value]  # O(1)
```

**注意事项**：
- 如果涉及区间操作（如线段树覆盖），离散化后相邻两点之间可能有"空隙"
- 扫描线处理缝隙：将 x 坐标离散化后，线段树维护的是"段"而非"点"

---

## 四、扫描线 (Sweep Line) — 矩形面积并

### 4.1 问题描述

给定 N 个矩形，求它们覆盖的总面积（重叠部分只算一次）。

### 4.2 核心思路

1. **水平扫描**：沿 y 轴从下往上扫描
2. **事件**：每次遇到矩形的下边（加入）或上边（离开），更新当前覆盖长度
3. **面积计算**：`当前覆盖总长度 × (当前y - 上次y)`

### 4.3 线段树维护的内容

线段树维护 x 轴方向被覆盖的"段"的总长度。每个节点需要两个值：
- `cnt`：该区间被完全覆盖的次数（不 push 下传，因为不需要叶子精确值）
- `len`：该区间内被覆盖的总长度（如果 cnt > 0 则是全区间长，否则从子节点合并）

这是经典的**不 push 的线段树**——因为只需要根节点的 len。

### 4.4 代码框架

```python
# 1. 读取所有矩形，提取上下边事件
events = []  # (y, x1, x2, type)  type=1 下边(进入)，type=-1 上边(离开)

# 2. 离散化 x 坐标
xs = sorted(set of all x1, x2)
rank = {v:i for i,v in enumerate(xs)}

# 3. 线段树维护 "段"长度（xs 相邻两点之间为一段）
#    节点覆盖 [l, r) 区间（左闭右开）

# 4. 排序 events 按 y
# 5. 遍历 events，更新线段树，累计面积
```

**线段树维护段**：
- 区间 `[l, r)` 代表 `xs[l]` 到 `xs[r]` 之间的总长度
- `cnt[node] > 0` 表示整段被完全覆盖：`len[node] = xs[r] - xs[l]`
- 否则：`len[node] = len[left] + len[right]`（叶子则 = 0）

**复杂度**：`O(N log N)`，N 为矩形数。

### 4.5 代码示例（核心）

```python
class SegTree:
    def __init__(self, xs):
        self.xs = xs
        n = len(xs) - 1
        self.cnt = [0] * (4 * n)
        self.len = [0] * (4 * n)
    
    def update(self, node, l, r, ql, qr, val):
        if ql <= l and r <= qr:
            self.cnt[node] += val
        else:
            mid = (l + r) // 2
            if ql < mid: self.update(node*2, l, mid, ql, qr, val)
            if qr > mid: self.update(node*2+1, mid, r, ql, qr, val)
        self._pull(node, l, r)
    
    def _pull(self, node, l, r):
        if self.cnt[node] > 0:
            self.len[node] = self.xs[r] - self.xs[l]
        elif r - l == 1:  # 叶子
            self.len[node] = 0
        else:
            self.len[node] = self.len[node*2] + self.len[node*2+1]
```

---

## 五、复杂度对比总结

| 数据结构 | 建树 | 单点更新 | 区间查询 | 区间更新 | 代码长度 |
|---------|------|---------|---------|---------|---------|
| 暴力数组 | O(1) | O(1) | O(N) | O(N) | 极短 |
| 前缀和 | O(N) | O(N) | O(1) | O(N) | 短 |
| 线段树(懒标记) | O(N) | O(log N) | O(log N) | O(log N) | 长(~60行) |
| 树状数组(BIT) | O(N) | O(log N) | O(log N) | O(log N) | 极短(~15行) |
| 差分BIT(两个) | O(N) | - | O(log N) | O(log N) | 短(~25行) |

**选型建议**：
- 只求前缀和+单点更新 → BIT
- 区间求和+区间加 → 差分BIT（如果可以差分化）或 线段树
- 区间最值/非可逆操作 → 线段树
- 扫描线等复杂区间 → 线段树

---

## 六、LeetCode 练习题推荐

| 题号 | 题目 | 数据结构 | 难度 |
|-----|------|---------|------|
| 307 | Range Sum Query - Mutable | BIT/线段树 | 🟡 |
| 303 | Range Sum Query - Immutable | 前缀和 | 🟢 |
| 370 | Range Addition | 差分 | 🟡 |
| 304 | Range Sum Query 2D | 2D前缀和 | 🟡 |
| 315 | Count of Smaller Numbers After Self | BIT+离散化 | 🔴 |
| 493 | Reverse Pairs | BIT+离散化 | 🔴 |
| 850 | Rectangle Area II | 扫描线+线段树 | 🔴 |
| 218 | The Skyline Problem | 扫描线 | 🔴 |
| 391 | Perfect Rectangle | 扫描线 | 🔴 |
| 327 | Count of Range Sum | BIT/归并 | 🔴 |
