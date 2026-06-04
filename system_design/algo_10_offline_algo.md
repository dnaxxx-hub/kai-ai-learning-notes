# 第10课：离线算法 — CDQ分治、莫队算法、整体二分

> 2026-05-09 | Phase 4 波次1 | 算法与数据结构深度

## 离线算法思想

离线（Offline）指一次性读完所有查询，利用全局信息批量处理。
**核心优势**：将在线无法做的操作变成可做（如排序、分治、分块）。

三种经典离线范式：
| 算法 | 适用场景 | 复杂度 | 核心思想 |
|------|---------|--------|---------|
| **CDQ分治** | 三维偏序、动态问题转静态 | O(N log² N) | 按维分治，一维化归 |
| **莫队** | 区间查询（离线） | O((N+Q)√N) | 分块+暴力移动 |
| **整体二分** | 多查询的第K大/小 | O((N+Q) log V) | 二分答案+分治 |

---

## 1. 莫队算法（Mo's Algorithm）

### 原理
- 对查询按 `(block[l], r)` 排序
- 块大小 = N/√Q（经典）或 N/√(2/3)（优化）
- 左右指针暴力移动，移动时O(1)更新答案
- 总复杂度 O((N+Q)√N)

### 关键技巧
- 分块大小 = N/√Q（约300~1000）
- 奇偶排序：偶数块r升序，奇数块r降序（减少指针跳跃）
- 删除不好维护用**回滚莫队**

### 模板（统计区间不同元素个数）

```python
def mo_range_distinct(arr, queries):
    """
    arr: 数组
    queries: [(l, r, idx), ...]
    return: [ans, ...]
    """
    n = len(arr)
    q = len(queries)
    block_size = int(n / (q**0.5)) + 1
    
    queries.sort(key=lambda x: (x[0] // block_size, 
                                 x[1] if (x[0] // block_size) % 2 == 0 else -x[1]))
    
    freq = {}
    cur = 0
    l, r = 0, -1
    ans = [0] * q
    
    def add(pos):
        nonlocal cur
        v = arr[pos]
        freq[v] = freq.get(v, 0) + 1
        if freq[v] == 1:
            cur += 1
    
    def remove(pos):
        nonlocal cur
        v = arr[pos]
        freq[v] -= 1
        if freq[v] == 0:
            cur -= 1
    
    for ql, qr, qi in queries:
        while l > ql: l -= 1; add(l)
        while r < qr: r += 1; add(r)
        while l < ql: remove(l); l += 1
        while r > qr: remove(r); r -= 1
        ans[qi] = cur
    
    return ans
```

### 何时不能用莫队
- 操作含修改（用**带修莫队**，多一维时间）
- 更新无法O(1)维护
- 在线查询

---

## 2. CDQ分治（CDQ Divide & Conquer）

### 原理
解决**三维偏序**问题：给定三元组 `(a, b, c)`，统计满足 `a'≤a, b'≤b, c'≤c` 的个数。

**思路**：
1. 按a排序（消去第一维）
2. 分治：左右分别按b排序
3. 归并时，左边c值插入BIT，右边c值查询前缀和

### 模板（三维偏序计数）

```python
class BIT:
    def __init__(self, n):
        self.n = n
        self.bit = [0] * (n + 2)
    
    def add(self, i, v):
        i += 1
        while i <= self.n:
            self.bit[i] += v
            i += i & -i
    
    def sum(self, i):
        i += 1
        s = 0
        while i > 0:
            s += self.bit[i]
            i -= i & -i
        return s
    
    def clear(self, i):
        i += 1
        while i <= self.n:
            self.bit[i] = 0
            i += i & -i


def cdq_3d(points):
    """
    points: [(a, b, c), ...]
    return: 对每个点，统计三维都 ≤ 它的点数
    """
    # 按a排序
    points.sort(key=lambda x: (x[0], x[1], x[2]))
    n = len(points)
    ans = [0] * n
    bit = BIT(max(c for _, _, c in points) + 1)
    
    def cdq(l, r):
        if l >= r:
            return
        mid = (l + r) // 2
        cdq(l, mid)
        cdq(mid + 1, r)
        
        # 左右区间分别按b排序
        left = points[l:mid+1]
        right = points[mid+1:r+1]
        left.sort(key=lambda x: x[1])
        right.sort(key=lambda x: x[1])
        
        i, j = 0, 0
        while j < len(right):
            if i < len(left) and left[i][1] <= right[j][1]:
                bit.add(left[i][2], 1)
                i += 1
            else:
                # 找到右边点的原index
                idx = points.index(right[j])
                ans[idx] += bit.sum(right[j][2])
                j += 1
        
        # 清理BIT
        for k in range(i):
            bit.clear(left[k][2])
        
        # 合并排序（保持整体按b有序）
        points[l:r+1] = sorted(points[l:r+1], key=lambda x: x[1])
    
    cdq(0, n - 1)
    return ans
```

### CDQ的变形
- **CDQ化动态为静态**：把时间t当作第一维，修改和查询按t分治
- **嵌套CDQ**：四维(k=4) → 两重CDQ
- **CDQ代替树套树**：空间O(N) vs O(N log N)

---

## 3. 整体二分（Parallel Binary Search）

### 原理
对所有查询同时二分答案，适用于：
- 区间第K大（主席树的替代）
- 带修改的第K大
- 满足单调性的多查询问题

**思路**：
1. 二分答案区间 [lo, hi]
2. 将所有查询按mid划分到左右子问题
3. 分治递归

### 模板（静态数组区间第K小）

```python
def kth_smallest(arr, queries):
    """
    queries: [(l, r, k, idx), ...]
    """
    n = len(arr)
    q = len(queries)
    ans = [0] * q
    
    # 压缩值域
    vals = sorted(set(arr))
    
    def solve(lo, hi, q_indices):
        """值域 [lo, hi], 处理 q_indices 中的查询"""
        if lo == hi:
            for qi in q_indices:
                ans[qi] = vals[lo]
            return
        if not q_indices:
            return
        
        mid = (lo + hi) // 2
        mid_val = vals[mid]
        
        # BIT标记 <= mid_val 的位置
        bit = BIT(n)
        for i, v in enumerate(arr):
            if v <= mid_val:
                bit.add(i, 1)
        
        # 划分查询
        left_q, right_q = [], []
        for qi in q_indices:
            l, r, k, _ = queries[qi]
            cnt = bit.sum(r) - bit.sum(l - 1)
            if cnt >= k:
                left_q.append(qi)
            else:
                # 减去前半部分的贡献
                new_query = list(queries[qi])
                new_query[2] = k - cnt
                queries[qi] = tuple(new_query)
                right_q.append(qi)
        
        solve(lo, mid, left_q)
        solve(mid + 1, hi, right_q)
    
    q_indices = list(range(q))
    solve(0, len(vals) - 1, q_indices)
    return ans
```

### 整体二分 vs 主席树
| 方面 | 整体二分 | 主席树 |
|------|---------|--------|
| 实现复杂度 | 低 | 中 |
| 空间 | O(N) | O(N log N) |
| 时间 | O((N+Q) log² V) | O((N+Q) log N) |
| 离线 | 必须 | 可在线 |
| 修改 | 支持 | 难 |

---

## 量化管道的离线算法应用

### 场景1：滑动窗口统计（莫队）
- 计算任意区间内的**动量统计量**（如某阈值内K线数量）
- 适用：财报季密集查询、特殊时间段对比

### 场景2：三维偏序选股（CDQ）
- `(市盈率, 市净率, 净利润增速)` 三维排序选股
- 或 `(时间, 价格, 成交量)` 找出"量价齐升"窗口

### 场景3：多阈值回测（整体二分）
- 同时查询100个不同止损阈值的回测结果
- 用整体二分一次算完，比逐个回测快1~2个数量级

---

## 总结

| 算法 | 记忆点 | 一句话 |
|------|-------|--------|
| 莫队 | 分块+排序+暴力移动 | "离线区间查询的瑞士军刀" |
| CDQ分治 | 按维分治+BIT统计 | "三维偏序的最优解" |
| 整体二分 | 分治答案+BIT划分 | "一次二分解决所有查询" |

时间复杂度：O(N log² N) 级别，空间O(N)。
应用场景：大数据离线分析、回测参数搜索、选股因子排序。
