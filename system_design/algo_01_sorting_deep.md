# 高级排序与选择 — 算法深度第1课

## 1. 快速排序变体

### 三路快排（Dutch National Flag）
处理大量重复元素时从O(n²)→O(n log n)。

```python
def quicksort_3way(arr, lo, hi):
    """三路快排：<pivot, =pivot, >pivot 三区"""
    if lo >= hi:
        return
    lt, gt = lo, hi  # lt: <区右边界, gt: >区左边界
    i = lo
    pivot = arr[lo]
    while i <= gt:
        if arr[i] < pivot:
            arr[lt], arr[i] = arr[i], arr[lt]
            lt += 1
            i += 1
        elif arr[i] > pivot:
            arr[i], arr[gt] = arr[gt], arr[i]
            gt -= 1
        else:
            i += 1
    quicksort_3way(arr, lo, lt - 1)
    quicksort_3way(arr, gt + 1, hi)
```

### 随机化快排与BFPRT
BFPRT（Median of Medians）保证O(n)选pivot，消除最差情况。

```python
def bfprt_select(arr, k):
    """BFPRT: O(n) 找出第k小的元素"""
    if len(arr) <= 5:
        return sorted(arr)[k]
    
    # 1. 分5组，每组排序取中位数
    medians = []
    for i in range(0, len(arr), 5):
        group = sorted(arr[i:i+5])
        medians.append(group[len(group)//2])
    
    # 2. 递归找中位数的中位数
    pivot = bfprt_select(medians, len(medians)//2)
    
    # 3. 分区
    left  = [x for x in arr if x < pivot]
    mid   = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    
    # 4. 递归定位
    if k < len(left):
        return bfprt_select(left, k)
    elif k < len(left) + len(mid):
        return pivot
    else:
        return bfprt_select(right, k - len(left) - len(mid))
```

## 2. 堆排序深化

### 二叉堆构建的O(n)证明
叶子节点占一半，越往下节点越多但下沉步数越少。
```
第h层: n/2^(h+1)个节点 × h步 → 总和趋于n
```

### d叉堆（d-ary Heap）
缓存友好，减少树高。d=4时实际CPU缓存性能最优。

## 3. 桶排序与基数排序
当数据范围已知时突破O(n log n)下界。

```python
def bucket_sort(arr, bucket_size=10):
    if not arr: return arr
    min_val, max_val = min(arr), max(arr)
    bucket_count = (max_val - min_val) // bucket_size + 1
    buckets = [[] for _ in range(bucket_count)]
    
    for x in arr:
        idx = (x - min_val) // bucket_size
        buckets[idx].append(x)
    
    result = []
    for bucket in buckets:
        result.extend(sorted(bucket))  # 桶内用插入排序
    return result
```

## 4. 后缀数组排序（Suffix Array）
字符串处理核心——在O(n log n)内对所有后缀排序。

```python
def suffix_array(s):
    """倍增法构建后缀数组 O(n log n)"""
    n = len(s)
    sa = list(range(n))
    rank = [ord(c) for c in s]
    k = 1
    tmp = [0] * n
    
    while True:
        sa.sort(key=lambda x: (rank[x], rank[x + k] if x + k < n else -1))
        tmp[sa[0]] = 0
        for i in range(1, n):
            prev, cur = sa[i-1], sa[i]
            prev_key = (rank[prev], rank[prev+k] if prev+k < n else -1)
            cur_key  = (rank[cur],  rank[cur+k]  if cur+k  < n else -1)
            tmp[cur] = tmp[prev] + (prev_key != cur_key)
        rank = tmp[:]
        if rank[sa[-1]] == n - 1:
            break
        k <<= 1
    return sa
```

## 要点
- 三路快排解决重复元素退化
- BFPRT O(n)选pivot（常数大，实战不如随机化）
- 桶排序前提：数据均匀分布
- 后缀数组是一种"对排序的排序"

---

*后续：第2课 — 高级图算法（Tarjan SCC、最大流）*
