# 高级图算法学习笔记

## 目录
- [Tarjan 强连通分量（SCC）](#tarjan-强连通分量scc)
- [拓扑排序（Kahn算法 + DFS）](#拓扑排序kahn算法--dfs)
- [最大流最小割（Ford-Fulkerson / Dinic）](#最大流最小割ford-fulkerson--dinic)
- [二分图匹配（匈牙利算法）](#二分图匹配匈牙利算法)
- [总结与对比](#总结与对比)

---

## Tarjan 强连通分量（SCC）

### 原理

**强连通分量（Strongly Connected Component, SCC）** 是指有向图中的一个最大子图，其中任意两个顶点都可以互相到达。

Tarjan算法由Robert Tarjan于1972年提出，基于**深度优先搜索（DFS）**，利用两个核心数组：
- **`dfn[u]`**：节点 `u` 被访问的次序（dfs序）
- **`low[u]`**：节点 `u` 通过其子树和一条返祖边能访问到的最小 `dfn` 值

**核心思想**：
1. 对图进行DFS，每访问一个节点分配 `dfn` 值，将其压入栈中
2. 当处理完节点 `u` 的所有邻接点后，若 `dfn[u] == low[u]`，则从栈顶到 `u` 的所有节点构成一个SCC
3. 更新 `low[u]` 规则：
   - 邻接点未访问 → 递归处理，用 `low[v]` 更新 `low[u]`
   - 邻接点在栈中（返祖边）→ 用 `dfn[v]` 更新 `low[u]`

### 算法流程

```
Tarjan(u):
  dfn[u] = low[u] = ++timer
  push u onto stack
  mark u on stack

  for each v in adj[u]:
    if not visited[v]:
      Tarjan(v)
      low[u] = min(low[u], low[v])
    else if v on stack:
      low[u] = min(low[u], dfn[v])

  if dfn[u] == low[u]:
    pop from stack until u → this is one SCC
```

### 时间复杂度
- **O(V + E)**，每个节点和每条边恰好访问一次

### 应用场景
- 社交网络中的紧密社区检测
- 程序依赖分析（将循环依赖归类）
- 2-SAT问题求解
- 图缩点（DAG化）

### Python代码示例

```python
def tarjan_scc(graph):
    n = len(graph)
    dfn = [-1] * n
    low = [0] * n
    on_stack = [False] * n
    stack = []
    timer = 0
    sccs = []

    def dfs(u):
        nonlocal timer
        dfn[u] = low[u] = timer
        timer += 1
        stack.append(u)
        on_stack[u] = True

        for v in graph[u]:
            if dfn[v] == -1:
                dfs(v)
                low[u] = min(low[u], low[v])
            elif on_stack[v]:
                low[u] = min(low[u], dfn[v])

        if dfn[u] == low[u]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == u:
                    break
            sccs.append(scc)

    for i in range(n):
        if dfn[i] == -1:
            dfs(i)
    return sccs
```

---

## 拓扑排序（Kahn算法 + DFS）

### 原理

**拓扑排序**是有向无环图（DAG）的一种线性排序，使得对每条有向边 `u→v`，`u` 都排在 `v` 之前。

### Kahn算法（BFS思路）

**核心思想**：重复移除入度为0的节点

```
Kahn(G):
  in_degree = [0] * V
  for each edge u→v: in_degree[v]++

  queue = all nodes with in_degree == 0
  result = []

  while queue not empty:
    u = queue.pop()
    result.append(u)
    for each v in adj[u]:
      in_degree[v]--
      if in_degree[v] == 0:
        queue.push(v)

  if len(result) != V: → cycle detected
  return result
```

### DFS拓扑排序

**核心思想**：后序遍历 + 反向

1. 对图进行DFS
2. 节点处理完毕后将其加入结果栈
3. 最终结果栈的逆序即为拓扑序

```python
def topo_sort_dfs(graph):
    n = len(graph)
    visited = [False] * n
    result = []

    def dfs(u):
        visited[u] = True
        for v in graph[u]:
            if not visited[v]:
                dfs(v)
        result.append(u)  # 后序加入

    for i in range(n):
        if not visited[i]:
            dfs(i)
    return result[::-1]  # 反转即为拓扑序
```

### 时间复杂度
- **O(V + E)**

### 应用场景
- 任务调度/课程安排
- 编译器的依赖解析
- 包管理器依赖排序
- 数据库表外键依赖处理

---

## 最大流最小割（Ford-Fulkerson / Dinic）

### 原理

**最大流问题**：给定有向图（每条边有容量），找出从源点 `s` 到汇点 `t` 的最大流量。

**最小割定理**：最大流的值 = 最小割的容量。割是指将顶点集分成两个集合（含s和t各一个），割的容量是跨越两个集合的边容量之和。

### Ford-Fulkerson算法

**核心思想**：不断寻找增广路径，沿路径增加流量

1. 构建残余网络（包含正向剩余容量和反向容量）
2. 在残余网络中寻找从s到t的任意路径（增广路）
3. 沿路径增加流量（增加值为路径上的最小残余容量）
4. 更新残余网络（正向减，反向加）
5. 重复直到没有增广路

**局限**：可能陷入无限循环（当使用DFS且容量为无理数时）

### Dinic算法（优化的FF）

**核心思想**：分层图 + 多路增广

1. **BFS建分层图**：从s开始计算每个节点的层次
2. **DFS多路增广**：在分层图上一次DFS找到多条增广路
3. **当前弧优化**：记录每个节点已经处理到的边，避免重复

```python
class Dinic:
    def __init__(self, n):
        self.n = n
        self.adj = [[] for _ in range(n)]

    def add_edge(self, u, v, cap):
        self.adj[u].append([v, cap, len(self.adj[v])])
        self.adj[v].append([u, 0, len(self.adj[u]) - 1])

    def bfs(self, s, t):
        self.level = [-1] * self.n
        q = deque([s])
        self.level[s] = 0
        while q:
            u = q.popleft()
            for v, cap, rev in self.adj[u]:
                if cap > 0 and self.level[v] < 0:
                    self.level[v] = self.level[u] + 1
                    q.append(v)
        return self.level[t] >= 0

    def dfs(self, u, t, f):
        if u == t:
            return f
        for i in range(self.it[u], len(self.adj[u])):
            self.it[u] = i
            v, cap, rev = self.adj[u][i]
            if cap > 0 and self.level[u] < self.level[v]:
                ret = self.dfs(v, t, min(f, cap))
                if ret > 0:
                    self.adj[u][i][1] -= ret
                    self.adj[v][rev][1] += ret
                    return ret
        return 0

    def max_flow(self, s, t):
        flow = 0
        INF = 10**18
        while self.bfs(s, t):
            self.it = [0] * self.n
            while True:
                pushed = self.dfs(s, t, INF)
                if pushed == 0:
                    break
                flow += pushed
        return flow
```

### 时间复杂度
- **Dinic**: O(E·V²) 一般情况，O(E·√V) 在单位容量图上
- **实际表现**：Dinic在竞赛中通常能处理10⁵级别的图

### 应用场景
- 网络带宽分配
- 二分图最大匹配（转化为最大流）
- 任务分配/负载均衡
- 图像分割（Graph Cut）
- 管道/交通流量计算

---

## 二分图匹配（匈牙利算法）

### 原理

**二分图**：顶点可分成两个不相交集U和V，所有边连接U和V中的顶点。

**最大匹配**：找到边数最多的匹配（匹配中任意两条边没有公共顶点）。

### 匈牙利算法（Kuhn-Munkres）

**核心思想**：增广路定理——通过寻找**增广路**来扩大匹配

1. 从未匹配的左部节点出发
2. 尝试为它寻找匹配：遍历其所有邻接右部节点
3. 如果右部节点未匹配 → 直接匹配成功（增广路长度为1）
4. 如果右部节点已匹配 → 尝试"让"已匹配的左部节点重新匹配（递归）
5. 如果成功找到增广路 → 匹配数+1

```python
def hungarian(adj, n_left, n_right):
    # adj[u] = list of v in right side that u connects to
    match_right = [-1] * n_right  # 右部节点匹配的左部节点
    match_left = [-1] * n_left    # 左部节点匹配的右部节点

    def dfs(u, visited):
        for v in adj[u]:
            if not visited[v]:
                visited[v] = True
                if match_right[v] == -1 or dfs(match_right[v], visited):
                    match_right[v] = u
                    match_left[u] = v
                    return True
        return False

    result = 0
    for u in range(n_left):
        visited = [False] * n_right
        if dfs(u, visited):
            result += 1
    return result, match_left, match_right
```

### 时间复杂度
- **O(V·E)**

### 应用场景
- 任务分配（员工-任务）
- 相亲/配对问题
- 课程表排课
- 棋盘覆盖问题

---

## 总结与对比

| 算法 | 核心思想 | 时间复杂度 | 主要应用 |
|------|---------|-----------|---------|
| Tarjan SCC | DFS + low/dfn | O(V+E) | 图缩点、2-SAT |
| 拓扑排序Kahn | 入度归零+BFS | O(V+E) | 依赖排序 |
| 拓扑排序DFS | 后序反转 | O(V+E) | 依赖排序 |
| Ford-Fulkerson | 增广路径 | O(E·f) | 最大流 |
| Dinic | 分层图+多路增广 | O(E·V²) | 最大流（高效） |
| 匈牙利算法 | 增广路递归 | O(V·E) | 二分图匹配 |

### 算法间的联系

1. **缩点 + 拓扑排序**：先用Tarjan将图缩成DAG，再进行拓扑排序
2. **最大流 → 二分图匹配**：构造超级源点→左部→右部→超级汇点，跑Dinic
3. **最小割 → 图像分割**：最小割就是最小代价的分割方案

### 练习建议

1. 先用小图手算一遍Tarjan的low/dfn值
2. 理解Dinic的分层图概念，写代码后debug观察每轮BFS/DFS
3. 匈牙利算法的"让路"过程是递归精华，画图追踪每个递归调用
