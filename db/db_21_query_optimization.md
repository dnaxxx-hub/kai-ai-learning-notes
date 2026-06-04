# 数据库 #21：查询优化实战

## 执行计划解读

### 连接类型
| 类型 | 说明 | 适用场景 |
|------|------|----------|
| Nested Loop Join | 外表逐行匹配内表 | 小表 join 大表（有索引） |
| Hash Join | 建哈希表后探测 | 大表 join（无索引） |
| Merge Join | 排序后归并 | 两个有序输入（排序代价高） |

### 索引访问
| 类型 | 说明 | 建议 |
|------|------|------|
| Index Scan | 全索引遍历 | 大范围查询 |
| Index Seek | 索引定位 | 精确查找（首选） |
| Key Lookup | 索引回表 | 覆盖索引可避免 |
| Index Only Scan | 覆盖索引（不回表） | 性能最好 |

## 索引设计原则

### 联合索引（最左前缀）
```sql
CREATE INDEX idx_a_b_c ON t(a, b, c);
-- 可用：a, a+b, a+b+c
-- 不可用：b, c, b+c（跳过第一列）
```

### 覆盖索引
- 查询只用到索引中的列，不回表
- MySQL 5.6+：Index Condition Pushdown（ICP）

### Index Condition Pushdown
- WHERE 条件中索引列的判断下推到存储引擎
- 减少回表次数

### MRR（Multi-Range Read）
- 排序 rowid → 按物理顺序回表
- 把随机I/O变成顺序I/O

## SQL 改写技巧
- `EXISTS` vs `IN`：IN 可以走 semijoin，EXISTS 不一定
- `SELECT *` → 只选需要的列
- `ORDER BY` 走索引避免 filesort
- `LIMIT` 优化：游标分页替代 offset
- `IN + 子查询` → 改 JOIN + DISTINCT
