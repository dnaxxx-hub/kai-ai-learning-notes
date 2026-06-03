# 第7课：数据库内核（深度）

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 查询计划优化

### SQL执行流程
```
SQL → 解析器 → 查询重写器 → 优化器 → 执行器 → 存储引擎
         ↓           ↓            ↓         ↓          ↓
      AST/CST    逻辑优化    代价估算    算子执行   数据访问
```

### 逻辑优化（Rule-based）
- **谓词下推**：WHERE条件尽早过滤
- **投影下推**：只取需要的列
- **子查询优化**：EXISTS转JOIN
- **视图展开**：视图定义并入主查询
- **常量折叠**：`WHERE 1=1` 消除

```sql
-- 优化前
SELECT * FROM (
    SELECT * FROM orders WHERE amount > 100
) o JOIN users u ON o.user_id = u.id
WHERE u.city = '北京'

-- 优化后（谓词下推）
SELECT * FROM orders o
JOIN users u ON o.user_id = u.id
WHERE o.amount > 100 AND u.city = '北京'
```

### 物理优化（Cost-based）
- 枚举各种执行路径
- 估算每个路径的IO+CPU代价
- 选代价最小的

**统计信息**：行数、列基数(NDV)、数据分布直方图、索引深度

**访问方式选择**：
```sql
-- 全表扫描：无索引，表小，或要查大部分数据
-- 索引扫描：有索引且选择性高
-- 聚簇索引：索引即数据，不需要回表
-- 覆盖索引：索引包含所需所有列
-- 位图索引：基数低的列
```

**JOIN算法选择**：
| 算法 | 场景 | 复杂度 |
|------|------|--------|
| Nested Loop Join | 小表驱动大表 | O(N₁×N₂) |
| Hash Join | 无索引，大表等值连接 | O(N₁+N₂) |
| Sort Merge Join | 已排序，范围连接 | O(N logN) |

## 2. 索引选择

### 索引类型
- **B+Tree**：范围查询、排序、模糊匹配（最常用）
- **Hash**：等值查询极度快，不支持范围
- **GiST**：地理空间、全文搜索
- **GIN**：倒排索引、数组、JSON

### 联合索引（Composite Index）
```sql
CREATE INDEX idx_user ON users(city, age, name);

-- 走索引：最左前缀
WHERE city = '北京'               -- ✅
WHERE city = '北京' AND age > 20  -- ✅
WHERE city = '北京' AND age > 20 AND name LIKE '张%' -- ✅

-- 不走索引：跳过最左列
WHERE age > 20              -- ❌
WHERE name = '张三'          -- ❌
```

### 索引下推（Index Condition Pushdown, ICP）
MySQL 5.6+：存储引擎在索引遍历时直接过滤，减少回表

## 3. 事务调度与锁管理器

### 锁类型

| 锁 | 作用 |
|----|------|
| 共享锁(S) | 读锁，可并发读 |
| 排他锁(X) | 写锁，互斥 |
| 意向锁(IS/IX) | 表级锁，表示某行有锁 |
| 间隙锁(Gap Lock) | 封锁范围，防止幻读 |
| Next-Key Lock | 行锁+间隙锁的组合 |

### 两阶段锁（2PL）
```
Phase 1: 获取锁（加锁阶段）
Phase 2: 释放锁（解锁阶段，一旦开始不能加新锁）
```
- **严格2PL**：解锁在事务提交时（避免级联回滚）
- MySQL InnoDB 使用严格2PL

### 死锁检测
- 等待图检测：有环则死锁
- 超时检测：超过innodb_lock_wait_timeout

**死锁处理**：挑一个事务回滚（选代价最小的）

## 4. 极小SQL解析器

### 解析步骤
```
SQL字符串
  → 词法分析（Tokenizer）：把SQL拆成token
  → 语法分析（Parser）：根据文法构建AST
  → 语义分析（Analyzer）：检查表和列是否存在
  → 优化（Optimizer）：生成执行计划
  → 执行（Executor）：执行算子
```

### 简单SQL的文法
```sql
SELECT [columns] FROM table [WHERE conditions] [ORDER BY col]
```

### Token类型
```python
Token Type: SELECT, FROM, WHERE, ORDER, BY,
            IDENTIFIER, NUMBER, STRING,
            COMPARISON(=,>,<,>=,<=,!=),
            AND, OR, COMMA, DOT, SEMICOLON
```

### AST节点
```python
class SelectStatement:
    columns: List[str]
    table: str
    where: Optional[Expression]
    order_by: Optional[OrderBy]
```
