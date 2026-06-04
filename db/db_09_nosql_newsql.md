# NoSQL & NewSQL：什么时候用关系型，什么时候不用

> 日期：2026-05-07 19:42 | 课程：DB路线 Phase 4-2
> 目标：理解"关系型数据库的局限和其他数据库的选择"

## 核心问题

```
2010年代: 互联网爆发 → 数据量爆炸
MySQL撑不住了 → 分库分表太复杂 → NoSQL兴起

2020年代: NoSQL的问题暴露 → NewSQL出现
```

## NoSQL的四种类型

### 1. 键值存储（Key-Value）

| 特点 | 例子 |
|------|------|
| 最简单，只用主键查 | Redis, Memcached |
| O(1) 读写 | DynamoDB |

```python
# 适用: 缓存, Session, 用户配置
# 不适用: 复杂查询, 多条件查询
```

### 2. 文档数据库（Document）

| 特点 | 例子 |
|------|------|
| 存JSON，表结构灵活 | MongoDB, Couchbase |
| 支持索引，但弱JOIN | Firestore |

```python
# 适用: 内容管理, 日志, 监控
# 不适用: 多表关联, 事务要求高
```

### 3. 列族存储（Wide-Column）

| 特点 | 例子 |
|------|------|
| 按列存，适合分析 | Cassandra, HBase |
| 高压缩比 | BigTable |

```python
# 适用: 时序数据, IoT, 大数据分析
# 不适用: OLTP事务
```

### 4. 图数据库（Graph）

| 特点 | 例子 |
|------|------|
| 关系是核心 | Neo4j, JanusGraph |
| 擅长社交/推荐 | Dgraph |

```python
# 适用: 社交网络, 推荐引擎, 知识图谱
# 不适用: 通用业务系统
```

## NoSQL vs SQL 核心差异

| 特性 | SQL (MySQL/PostgreSQL) | NoSQL (MongoDB/Redis) |
|------|----------------------|---------------------|
| Schema | 固定 | 灵活 |
| 事务 | ACID | BASE |
| 查询 | SQL强大 | 有限 |
| 扩展 | 垂直为主 | 水平原生 |
| 一致性 | 强 | 最终 |
| 学习曲线 | 高 | 低 |

## NewSQL：SQL + 水平扩展

```
TiDB / CockroachDB / OceanBase
 ↑          ↑           ↑
SQL协议    SQL协议     SQL协议
Raft共识    Raft共识     Paxos共识
自动分片    自动分片      自动分片
兼容MySQL  兼容PostgreSQL 兼容MySQL
```

### 为什么需要NewSQL？

```python
# 2010年代: MySQL不行了 → 用NoSQL
# 但NoSQL不兼容SQL，应用要重写 → 成本巨大

# NewSQL = SQL的舒服 + NoSQL的水平扩展
# 开发不用改代码 → 自动分片 → 分布式事务
```

### NewSQL的代表

| 产品 | 公司 | 特点 |
|------|------|------|
| TiDB | PingCAP | 兼容MySQL，HTAP |
| CockroachDB | Cockroach Labs | 兼容PostgreSQL |
| OceanBase | 蚂蚁集团 | 双11核心 |
| YugabyteDB | Yugabyte | 兼容PostgreSQL + Cassandra |

## 怎么选

```python
# 需要ACID事务？               → SQL/NewSQL
# 海量数据+水平扩展？          → NewSQL/NoSQL
# 简单缓存？                   → Redis
# 复杂关联查询？               → SQL
# Schema经常变？              → MongoDB
# 社交关系/推荐？             → 图数据库
# 时序数据？                   → 列存/时序数据库
# 需要分析+事务一体？（HTAP） → TiDB
```

## 今日收获
- NoSQL的四种类型：KV/文档/列存/图
- **NewSQL = SQL + 自动分片 + 分布式事务**
- TiDB是国产数据库的代表（PingCAP，兼容MySQL）
- 没有"最好的数据库"，只有最合适的
- 现代架构常是 **SQL + Redis + ES** 组合使用
