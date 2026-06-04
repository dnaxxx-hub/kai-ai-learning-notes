# SQL调优实战

> 日期：2026-05-07 22:31 | 课程：数据库深水区 Phase 3-2
> 目标：理解"一条慢SQL怎么找到原因并优化"

## 核心工具

```sql
-- EXPLAIN 是你的第一武器
EXPLAIN SELECT * FROM orders WHERE user_id = 123 AND amount > 1000;

-- 重点关注:
-- type: 访问类型（all=最差, range=还行, ref=好, eq_ref=很好, const=最好）
-- key: 实际使用的索引
-- rows: 估计扫描的行数
-- Extra: 额外信息（Using index=覆盖索引, Using filesort=需要优化）
```

## 常见问题与优化

### 1. 索引失效

```sql
-- ❌ 函数导致索引失效
WHERE YEAR(created_at) = 2025;
-- ✅ 改为范围查询
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01';

-- ❌ 隐式类型转换
WHERE phone = 13800138000;  -- phone是varchar
-- ✅ 字符串类型用字符串比较
WHERE phone = '13800138000';

-- ❌ 前模糊匹配
WHERE name LIKE '%张三%';
-- ✅ 可以用覆盖索引
-- ✅ 考虑全文索引（FULLTEXT INDEX）
```

### 2. 索引设计

```sql
-- 联合索引: 最左前缀原则
CREATE INDEX idx_user_date ON orders(user_id, created_at);

-- 能用上索引:
WHERE user_id = 123;
WHERE user_id = 123 AND created_at > '2025-01-01';

-- 用不上索引:
WHERE created_at > '2025-01-01';  -- 没用到user_id

-- 索引覆盖: 查询的列都在索引里
-- 如果只需要user_id和created_at → 不用回表
SELECT user_id, created_at FROM orders WHERE user_id = 123;
```

### 3. 索引下推（ICP）

```sql
-- MySQL 5.6+ 的特性

-- 没有ICP:
-- 用索引找到user_id=123的rows → 回表读整行 → 再过滤amount
-- 有ICP:
-- 在索引层面就过滤amount → 只回表满足条件的行

-- EXPLAIN中显示: Using index condition
-- 这说明ICP生效了
```

### 4. MRR（多范围读取）

```sql
-- 问题: 回表IO是随机的
-- 如果查到100条记录要回表 → 100次随机IO

-- MRR: 先排序主键 → 按主键顺序回表
-- → 随机IO变成顺序IO → 快很多

-- EXPLAIN显示: Using MRR
```

## 分页优化

```sql
-- ❌ 深度分页很慢
SELECT * FROM orders ORDER BY id LIMIT 100000, 20;
-- 需要扫描10万行再取20行 → 浪费

-- ✅ 游标分页（基于索引）
SELECT * FROM orders 
WHERE id > 100000 
ORDER BY id 
LIMIT 20;

-- ✅ 子查询延迟关联
SELECT * FROM orders 
WHERE id IN (
  SELECT id FROM orders 
  ORDER BY id 
  LIMIT 100000, 20
);
```

## 索引合并

```sql
-- MySQL会判断: 用多个索引分别查 → 合并结果

-- 索引A: idx_user_id
-- 索引B: idx_amount

SELECT * FROM orders 
WHERE user_id = 123 OR amount > 10000;

-- 如果两个条件都用索引更优 →
-- MySQL用索引合并: 分别查两个索引 → 取并集
-- 但通常不如建联合索引好
```

## 今日收获
- EXPLAIN = 分析SQL的第一工具
- 索引失效的常见原因：函数/隐式转换/前模糊匹配
- 联合索引 = 最左前缀原则
- ICP = 索引层面过滤，减少回表
- MRR = 回表前排序主键 → 顺序IO
- 深度分页不用OFFSET，用游标或延迟关联
