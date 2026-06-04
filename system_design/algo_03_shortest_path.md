# 第3课：最短路径算法

> Phase 2.2 | 图算法（下）
> 日期: 2026-05-09

## 概述

本课深入实现三种经典最短路径算法：Dijkstra（单源非负权）、Bellman-Ford（支持负权+负环检测）、Floyd-Warshall（全源）。同时覆盖路径重建（predecessor/successor 数组）和负环检测机制。

## 学习内容

### 1. Dijkstra 算法
- **适用条件**：非负权有向图/无向图
- **时间复杂度**：O((V+E)logV) — 最小堆优化
- **核心思想**：贪心策略，每次选当前最短路径的未处理节点
- **正确性依赖**：权值非负，确保已处理的节点距离不会再被更新
- **实现细节**：
  - 使用 `heapq` 最小堆始终取最小距离节点
  - `dist[v]` 记录源点到 v 的当前最短距离
  - `pred[v]` 记录前驱节点，用于路径重建
  - `visited` 标记已确定最短路径的节点

### 2. Bellman-Ford 算法
- **适用条件**：任意有向图（可处理负权边）
- **时间复杂度**：O(VE)
- **核心思想**：动态规划，逐轮松弛所有边
  - 第 1 轮：找到最多 1 条边的最短路径
  - 第 2 轮：找到最多 2 条边的最短路径
  - ...
  - 第 V-1 轮：找到最多 V-1 条边的最短路径（即最终结果）
- **负环检测**：第 V 轮松弛如果还能更新，则存在负环

### 3. Floyd-Warshall 算法
- **适用条件**：任意有向图（全源）
- **时间复杂度**：O(V³)
- **核心思想**：三维 DP 压缩为二维
  - `dist[i][j]` = 经过前 k 个中间节点时 i 到 j 的最短距离
  - 外层循环 `k` 表示允许使用节点 0..k 作为中间节点
- **路径重建**：记录 `next[i][j]` = 从 i 到 j 最短路径上的第一个后继节点

### 4. 路径重建
- **predecessor 数组**（Dijkstra, Bellman-Ford）：记录每个节点的前驱，从目标节点反向回溯
- **next 矩阵**（Floyd-Warshall）：记录后继，从源节点正向追踪
- **处理不可达**：pred[dst] == -1 或 dist == INF 时表示不可达

### 5. 负环检测
- Bellman-Ford 第 V 次松弛检测
- Floyd-Warshall 检测 `dist[i][i] < 0`
- 存在负环时最短路径无意义（可以无限次绕环减小距离）

## 算法对比

| 特性 | Dijkstra | Bellman-Ford | Floyd-Warshall |
|------|----------|-------------|----------------|
| 适用场景 | 单源正权 | 单源含负权 | 全源 |
| 时间复杂度 | O((V+E)logV) | O(VE) | O(V³) |
| 空间复杂度 | O(V) | O(V) | O(V²) |
| 负权支持 | ❌ | ✅ | ✅ |
| 负环检测 | ❌ | ✅ | ✅ |
| 路径重建 | pred 数组 | pred 数组 | next 矩阵 |
| 实现难度 | 简单 | 简单 | 中等 |

## 运行结果

```
=== 1. Dijkstra (正权图) ===
  0->0: dist=0, path=0
  0->1: dist=3, path=0->2->1
  0->2: dist=2, path=0->2
  0->3: dist=5, path=0->2->1->3
  0->4: dist=6, path=0->2->1->4
  ✓ Dijkstra 正确找到最短路径 (0->2->1->4 比直接 0->1->4 更短)

=== 2. Bellman-Ford (含负权边) ===
  0->4: dist=-2, path=0->3->2->1->4
  ✓ 正确处理含负权边 (-4的边带来了更优路径)
  
=== 3. Bellman-Ford (含负环) ===
  含负环: True (负环节点位置: 2)
  ✓ 成功检测负环! 0→1→2→0 环总和=1+(-3)+(-2)=-4<0

=== 4. Floyd-Warshall (全源最短路径) ===
  0->4最短: -2
  1->0最短: -2
  3->2最短: -3
  ✓ 全源最短路径与 Dijkstra/BF 一致

=== 5. 不连通图 ===
  0->3: path=None (预期不可达)
  ✓ INF正确表示不可达节点

=== 6. 正确性验证 (V=5,10,20) ===
  V=5: Dijkstra == Bellman-Ford: True
  V=10: Dijkstra == Bellman-Ford: True
  V=20: Dijkstra == Bellman-Ford: True
  ✓ 三种算法在无负环时结果完全一致
```

## 可视化

可视化图保存在 `figures/` 目录下：
- `shortest_path_dijkstra.png`
- `shortest_path_bf_positive.png`
- `shortest_path_bf_neg_edge.png`
- `shortest_path_bf_neg_cycle.png`
- `shortest_path_floyd.png`

## 总结

（待补充）
