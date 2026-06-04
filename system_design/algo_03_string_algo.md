# 第3课：字符串算法

> 日期: 2026-05-08
> 主题: KMP、Rabin-Karp、Z函数、后缀数组、AC自动机

---

## 1. KMP 算法 (Knuth-Morris-Pratt)

### 核心思想
利用模式串自身的重复结构，在匹配失败时跳过已匹配的相同前缀，避免回溯文本指针。

### 前缀函数 (Prefix Function) π[i]
定义：`π[i]` 是子串 `s[0..i]` 中「最长相等真前缀和真后缀」的长度。

```
例如 s = "aabaaab"
π[0] = 0
π[1] = 1   ("aa" 前缀"a"=后缀"a")
π[2] = 0   ("aab")
π[3] = 1   ("aaba" 前缀"a"=后缀"a")
π[4] = 2   ("aabaa" 前缀"aa"=后缀"aa")
π[5] = 2   ("aabaaa")
π[6] = 3   ("aabaaab" 前缀"aab"=后缀"aab")
```

#### 线性计算 π 数组（O(n)）
```python
def compute_pi(pattern):
    pi = [0] * len(pattern)
    for i in range(1, len(pattern)):
        j = pi[i-1]
        while j > 0 and pattern[i] != pattern[j]:
            j = pi[j-1]
        if pattern[i] == pattern[j]:
            j += 1
        pi[i] = j
    return pi
```

关键：当 `pattern[i] != pattern[j]` 时，跳转到 `pi[j-1]`，而不是从头开始。

### 匹配过程
用类似 π 数组计算的方式扫描文本，记录「当前匹配长度」j：
- 文本指针 i 永不回退
- 每次不匹配时 j = π[j-1]
- 当 j == m 时找到匹配

```python
def kmp_search(text, pattern):
    pi = compute_pi(pattern)
    j = 0
    matches = []
    for i in range(len(text)):
        while j > 0 and text[i] != pattern[j]:
            j = pi[j-1]
        if text[i] == pattern[j]:
            j += 1
        if j == len(pattern):
            matches.append(i - j + 1)
            j = pi[j-1]
    return matches
```

### 复杂度
- **时间**: O(n + m)，n=文本长度, m=模式串长度
- **空间**: O(m)（存 π 数组）

### 应用
- 字符串匹配
- 字符串周期（最小周期 = n - π[n-1]）
- 前缀统计（π 数组的迭代形成前缀之间的包含关系树状结构）

---

## 2. Rabin-Karp 算法

### 核心思想
使用滚动哈希（Rolling Hash）在 O(1) 时间内计算子串哈希值，比较哈希值而非字符。

### 滚动哈希
```
hash(s[0..n-1]) = (s[0]*b^(n-1) + s[1]*b^(n-2) + ... + s[n-1]) mod M

滚动更新（窗口右移一位）：
new_hash = ((old_hash - s[i]*b^(m-1)) * b + s[i+m]) mod M
```

其中：
- `b` = 基数（通常选 131, 137, 91138233 等质数）
- `M` = 模数（通常选大质数，如 10^9+7, 10^9+9）

### 双哈希避免碰撞
使用两个不同的模数同时计算哈希，两个哈希都相同时才认为匹配。碰撞概率降至极低。

```python
def rabin_karp(text, pattern, base=131, mod=10**9+7):
    n, m = len(text), len(pattern)
    if m > n: return []
    
    # 预计算 b^(m-1)
    pow_base = [1] * (m + 1)
    for i in range(1, m + 1):
        pow_base[i] = (pow_base[i-1] * base) % mod
    
    # 计算 pattern 哈希
    ph = 0
    for ch in pattern:
        ph = (ph * base + ord(ch)) % mod
    
    # 计算 text 第一个窗口哈希
    th = 0
    for i in range(m):
        th = (th * base + ord(text[i])) % mod
    
    matches = []
    for i in range(n - m + 1):
        if th == ph:
            # 验证（防止碰撞）
            if text[i:i+m] == pattern:
                matches.append(i)
        # 滚动
        if i + m < n:
            th = ((th - ord(text[i]) * pow_base[m-1]) * base + ord(text[i+m])) % mod
            if th < 0:
                th += mod
    
    return matches
```

### 复杂度
- **平均**: O(n + m)
- **最坏**: O(nm)（大量哈希碰撞时，但双哈希 + 字符验证把这种可能降到极低）

### 应用
- 多模式匹配（预处理多个模式的哈希，一次扫描文本）
- 最长重复子串（配合二分搜索）
- 字符串指纹

---

## 3. Z 函数 (Z-Algorithm)

### 定义
Z 数组 `z[i]` 表示从位置 i 开始的最长子串长度，该子串同时也是字符串的前缀。

```
例如 s = "aaabaaab"
z[0] = 0  (习惯定义为 0)
z[1] = 2  ("aa" = 前缀"aa")
z[2] = 1  ("a" = 前缀"a")
z[3] = 0  ("b" ≠ "a")
z[4] = 3  ("aaa" = 前缀"aaa"? 不, "aab" vs "aaa", 所以是3)
z[5] = 2
z[6] = 1
z[7] = 0
```

### 线性计算

使用「Z-box」区间 [l, r] 表示最右的匹配前缀的子串：
```
for i in [1, n-1]:
    if i <= r:
        z[i] = min(r - i + 1, z[i - l])
    while i + z[i] < n and s[z[i]] == s[i + z[i]]:
        z[i] += 1
    if i + z[i] - 1 > r:
        l, r = i, i + z[i] - 1
```

### 字符串匹配
构造 `S = pattern + '$' + text`，计算 Z 数组。当 `z[i] == len(pattern)` 时匹配（在 text 部分）。

### 复杂度
- **时间**: O(n)
- **空间**: O(n)

### 应用
- 字符串匹配（替代 KMP）
- 字符串压缩（最小周期 = n / z[1] 如果 z[1] 能整除 n）
- 不同子串数统计（配合后缀数组）

---

## 4. 后缀数组 (Suffix Array)

### 定义
字符串的所有后缀按字典序排序后，后缀起始位置组成的数组 SA。

例如 `s = "banana"`:
```
后缀:
0: banana
1: anana
2: nana
3: ana
4: na
5: a

排序后:
5: a          → SA[0] = 5
3: ana        → SA[1] = 3
1: anana      → SA[2] = 1
0: banana     → SA[3] = 0
4: na         → SA[4] = 4
2: nana       → SA[5] = 2
```

### 倍增法（O(n log n)）

1. 初始化 rank = 每个字符的排名（ASCII 码）
2. 用 k = 1, 2, 4, ... 倍增排序：
   - 每个后缀用一个二元组 (rank[i], rank[i+k]) 表示
   - 基数排序或 Python 的 sort（key 函数）
3. 重复直到 k >= n

```python
def build_sa(s):
    n = len(s)
    k = 1
    sa = list(range(n))
    rank = [ord(c) for c in s]
    tmp = [0] * n
    
    while True:
        sa.sort(key=lambda x: (rank[x], rank[x + k] if x + k < n else -1))
        tmp[sa[0]] = 0
        for i in range(1, n):
            prev, cur = sa[i-1], sa[i]
            prev_key = (rank[prev], rank[prev + k] if prev + k < n else -1)
            cur_key = (rank[cur], rank[cur + k] if cur + k < n else -1)
            tmp[cur] = tmp[prev] + (prev_key != cur_key)
        rank = tmp[:]
        if rank[sa[-1]] == n - 1:
            break
        k <<= 1
    
    return sa
```

### LCP 数组 (Longest Common Prefix)

`lcp[i] = LCP(SA[i], SA[i-1])`，即排名相邻的后缀的最长公共前缀。

Kasai 算法（O(n)）：
```python
def build_lcp(s, sa):
    n = len(s)
    rank = [0] * n
    for i, pos in enumerate(sa):
        rank[pos] = i
    lcp = [0] * n
    k = 0
    for i in range(n):
        if rank[i] == 0:
            k = 0
            continue
        j = sa[rank[i] - 1]
        while i + k < n and j + k < n and s[i + k] == s[j + k]:
            k += 1
        lcp[rank[i]] = k
        if k:
            k -= 1
    return lcp
```

### 应用

#### 最长重复子串
重复子串 = 两个后缀的公共前缀。取 LCP 数组的最大值。

#### 不同子串的数量
所有子串数 = n*(n+1)/2
减去重复计数 = Σ lcp[i]
**不同子串数 = n*(n+1)/2 - Σ_{i=1}^{n-1} lcp[i]**

#### 最长公共子串（两个字符串）
拼接 s1 + '$' + s2 + '#', 找 SA 中跨两个字符串的最大 LCP。

### 复杂度
- 构建 SA: O(n log n)
- 构建 LCP: O(n)

---

## 5. AC 自动机 (Aho-Corasick)

### 核心思想
多模式匹配算法。在 Trie 上构建 fail 指针（类似 KMP 的 π 函数），一次扫描文本即可匹配所有模式串。

### 三步构建

#### 第一步：构建 Trie
将每个模式串插入 Trie 树。每个节点记录：
- `children`: 子节点字典/数组
- `fail`: fail 指针
- `output`: 该节点匹配的模式串列表

#### 第二步：构建 fail 指针（BFS）
```
根节点的子节点 fail = 根
对于其他节点 u：
  对每个字符 c:
    v = u.children[c]
    if v 存在:
      v.fail = u.fail.children[c] 或回溯
    else:
      u.children[c] = u.fail.children[c]  (路径压缩/字典图)
```

#### 第三步：匹配
```
指针 cur = root
对文本每个字符 c:
  cur = cur.children[c]
  沿 fail 链收集 output
```

### 字典图优化（Trie Graph）
当 children[c] 不存在时，直接指向 fail 指针的对应子节点。这样匹配时无需 while 循环回溯，变成 O(1) 转移。

```python
class AhoCorasick:
    def __init__(self):
        self.trie = [{}]    # 每个节点: {char: next_index}
        self.fail = [0]
        self.output = [[]]  # 节点对应的匹配模式串
    
    def insert(self, word):
        cur = 0
        for ch in word:
            if ch not in self.trie[cur]:
                self.trie[cur][ch] = len(self.trie)
                self.trie.append({})
                self.fail.append(0)
                self.output.append([])
            cur = self.trie[cur][ch]
        self.output[cur].append(word)
    
    def build(self):
        from collections import deque
        q = deque()
        # 第一层 fail 指向根
        for ch, nxt in self.trie[0].items():
            self.fail[nxt] = 0
            q.append(nxt)
        # BFS
        while q:
            u = q.popleft()
            for ch, v in self.trie[u].items():
                # 计算 v 的 fail
                f = self.fail[u]
                while f and ch not in self.trie[f]:
                    f = self.fail[f]
                if ch in self.trie[f]:
                    self.fail[v] = self.trie[f][ch]
                else:
                    self.fail[v] = 0
                # 合并 output
                self.output[v].extend(self.output[self.fail[v]])
                q.append(v)
    
    def search(self, text):
        cur = 0
        matches = {}
        for i, ch in enumerate(text):
            while cur and ch not in self.trie[cur]:
                cur = self.fail[cur]
            if ch in self.trie[cur]:
                cur = self.trie[cur][ch]
            else:
                cur = 0
            for word in self.output[cur]:
                start = i - len(word) + 1
                matches.setdefault(word, []).append(start)
        return matches
```

### 复杂度
- **构建**: O(Σ|pattern|) 总模式串长度
- **匹配**: O(n + 总匹配数)
- **空间**: O(总字符数 × alphabet_size)

### 应用
- 敏感词过滤
- 多关键词搜索
- DNA 序列多模式匹配
- 入侵检测系统

---

## 总结对比

| 算法 | 场景 | 时间复杂度 | 空间复杂度 |
|------|------|-----------|-----------|
| KMP | 单模式串匹配 | O(n+m) | O(m) |
| Rabin-Karp | 单/多模式串匹配 | O(n+m) 平均 | O(1) |
| Z函数 | 单模式串匹配 | O(n) | O(n) |
| 后缀数组 | 子串/重复/统计 | O(n log n) | O(n) |
| AC自动机 | 多模式串匹配 | O(n + Σ\|p\|) | O(Σ\|p\|) |

### 选择指南
- **单模式匹配**: KMP（稳定）或 Rabin-Karp（适合多模式哈希）
- **多模式匹配**: AC自动机（高效）或 Rabin-Karp（模式少时）
- **子串统计**: 后缀数组 + LCP（不同子串数、最长重复子串）
- **模式串固定 + 文本变化**: 预处理模式串（π数组/Z/AC）
- **文本固定 + 模式变化**: 后缀数组（预处理文本）
