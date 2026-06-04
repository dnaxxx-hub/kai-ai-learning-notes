# 图数据库实战：从零实现迷你图数据库引擎

## 概述

从零实现了一个纯 Python 迷你图数据库引擎，支持属性图模型、邻接表存储、标签索引、Cypher 子集查询、BFS/DFS 遍历、事务管理和 JSON 持久化。零外部依赖，100% 标准库。

## 项目结构

```
projects/graphdb/
├── __init__.py      # 包入口
├── node.py          # Node 类（属性图节点）
├── edge.py          # Edge 类（属性图边）
├── graph.py         # Graph 主类（邻接表存储、标签索引）
├── query.py         # Cypher 子集解析器（MATCH/WHERE/RETURN）
├── traversal.py     # BFS、DFS、最短路径
├── transaction.py   # 写时复制（CoW）快照事务
├── storage.py       # JSON 序列化/反序列化
└── test_all.py      # 完整测试套件（25+ 测试用例）
```

## 关键技术决策

### 1. 属性图模型

- **Node**: id（UUID）、labels（集合）、properties（字典）
- **Edge**: id（UUID）、type（字符串/标签）、src/tgt（节点ID）、properties（字典）
- 属性图是工业标准（Neo4j、TigerGraph 等），最适合表达复杂关联

### 2. 邻接表存储

每个 Node 维护两个列表：
- `out_edges`: 从该节点出发的边
- `in_edges`: 指向该节点的边

查询复杂度：O(deg(v))，适合图遍历型查询。

### 3. 标签索引

`Graph._label_index`: `{label: set(node_ids)}`

按标签查找节点从 O(n) 降到 O(1)。新增/删除节点时自动更新索引。

### 4. Cypher 子集解析器

设计了一个 MiniCypherParser，支持：

**MATCH 模式**：
- `MATCH (n:Person)` — 按标签匹配节点
- `MATCH (n:Person)-[:KNOWS]->(m:Person)` — 模式匹配遍历
- `MATCH (n)-[:FRIEND]-(m),(n)-[:FOLLOWS]->(p)` — 多模式（逗号分隔）

**WHERE 过滤**：
- 比较操作：`=`, `!=`, `>`, `<`, `>=`, `<=`
- 逻辑组合：`AND`, `OR`
- 字符串属性用引号包裹

**RETURN 投影**：
- `RETURN n` — 返回整个节点
- `RETURN n.name, m.age` — 返回特定属性
- `RETURN *` — 返回所有变量

**解析策略**：
- 纯字符串解析（无正则滥用），约 150 行
- 先解析 MATCH 提取变量、标签、方向
- 再解析 WHERE 构建过滤函数
- 最后解析 RETURN 构建投影

### 5. BFS/DFS 遍历

- **BFS**: 使用 deque 队列，O(V+E)，适合最短路径
- **DFS**: 使用 list 栈，O(V+E)，适合可达性分析
- **最短路径**: BFS 变体，记录前驱节点，回溯路径
- **多源/多目标**: BFS/DFS 支持多起始节点和多终止节点

### 6. 写时复制事务

**Transaction** 类：
- `begin()`: 对 Graph 状态做快照（copy.copy 引用复制）
- `commit()`: 将修改写到 Graph（无冲突检测的简单模型）
- `rollback()`: 从快照恢复 Graph

**写时复制（CoW）**：事务开始时复制引用，事务内修改不影响主状态，直到 commit。

缺点：不支持并发冲突检测。适合单用户场景或作为学习演示。

### 7. JSON 持久化

**序列化**：将图转换为可 JSON 序列化的字典结构
- 节点：{id, labels, properties}
- 边：{id, src_id, tgt_id, type, properties}
- 分开存储：{"nodes": [...], "edges": [...]}

**反序列化**：恢复 Node/Edge/Graph 对象
- 重建邻接表
- 重建标签索引

## 查询示例

```python
from graphdb import Graph

g = Graph()
alice = g.add_node("Person", name="Alice", age=30)
bob = g.add_node("Person", name="Bob", age=25)
g.add_edge(alice, bob, "KNOWS", since=2020)

# Cypher 查询：找所有 Person
result = g.query("MATCH (n:Person) RETURN n.name, n.age")
# [{"n.name": "Alice", "n.age": 30}, {"n.name": "Bob", "n.age": 25}]

# 模式匹配
result = g.query("MATCH (n)-[:KNOWS]->(m) RETURN n.name, m.name")
# [{"n.name": "Alice", "m.name": "Bob"}]

# 属性过滤
result = g.query("MATCH (n:Person) WHERE n.age > 25 RETURN n.name")
# [{"n.name": "Alice"}]

# BFS 最短路径
path = g.shortest_path(alice, bob)
# [alice, bob]

# 事务
tx = g.begin()
tx.add_node("City", name="Beijing")
tx.commit()
```

## 测试覆盖

25 个测试用例覆盖所有功能模块：

| 模块 | 测试数 | 覆盖内容 |
|------|--------|----------|
| 节点 CRUD | 3 | 创建、属性更新、删除 |
| 边 CRUD | 3 | 有向边创建、属性更新、删除 |
| 标签索引 | 2 | 按标签查询、索引一致性 |
| 属性过滤 | 2 | 数值/字符串比较 |
| 模式匹配 | 5 | 单节点/有向边/无向边/多模式/链式 |
| 图遍历 | 3 | BFS/DFS/最短路径 |
| 事务 | 4 | commit/rollback/隔离性/嵌套 |
| 持久化 | 3 | 序列化/反序列化/文件IO |

## 与专业图数据库的对比

| 特性 | 本引擎 | Neo4j | TigerGraph |
|------|-------|-------|------------|
| 存储模型 | 邻接表（内存） | 原生图存储（磁盘） | 邻接表 + 压缩 |
| 查询语言 | Cypher 子集 | Cypher 完整 + GDS | GSQL |
| 事务 | CoW 快照 | ACID（WAL） | ACID |
| 并发 | 无 | MVCC | 分区级锁 |
| 持久化 | JSON 文件 | 自定义格式 | 列式存储 |
| 规模 | 内存限制 | TB 级 | PB 级 |
| 部署 | 单进程 | 集群 | 分布式 |

## 学到的关键设计模式

1. **属性图**优于 RDF 三元组：可附加属性到节点和边，表达能力更强
2. **邻接表**优于邻接矩阵：稀疏图场景下空间效率高，图遍历友好
3. **标签索引**是图数据库性能关键：将 O(n) 扫描降到 O(1) 查找
4. **写时复制**是最简单的事务模型：源码量少（~80行），适合学习
5. **纯字符串解析**可以很小巧：对于 DSL 子集，正则 + 字符串操作足够

## 参考

- Neo4j Cypher Manual: https://neo4j.com/docs/cypher-manual/current/
- TigerGraph 架构: https://docs.tigergraph.com/
- Apache TinkerPop / Gremlin: https://tinkerpop.apache.org/
