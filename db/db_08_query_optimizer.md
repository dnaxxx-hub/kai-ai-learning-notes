# 查询优化器：数据库怎么选最快的执行路径

> 日期：2026-05-07 19:40 | 课程：DB路线 Phase 4-1
> 目标：理解"同样的SQL为什么有时快有时慢"

## 核心问题

```sql
SELECT * FROM orders WHERE user_id=123 AND amount>1000;

-- 数据库有多个索引可供选择:
-- 方案A: 先用user_id索引找到用户订单 → 过滤amount
-- 方案B: 先用amount索引找到大额订单 → 过滤user_id
-- 方案C: 两个表都走全表扫描

-- 哪个最快？——查询优化器来决策
```

## 优化器的决策过程

```
SQL → 解析器 → 逻辑计划 → 优化器 → 物理计划 → 执行器
                                         ↓
                                   成本估算 + 统计信息
```

### 1. 统计信息

```sql
-- 优化器需要知道：
-- 表有多少行？
-- 索引的区分度（cardinality）？
-- 数据分布（是否倾斜）？

-- MySQL: 
SHOW INDEX FROM users;
-- 可以看到 cardinality（唯一值数量）
-- cardinality 越接近行数 → 索引区分度越好

-- 统计信息过时 → 优化器选错索引 → SQL变慢
-- ANALYZE TABLE 可以更新统计信息
```

### 2. 成本模型

```
优化器给每个执行计划算"成本"：

成本 = IO成本 + CPU成本

IO成本:  从磁盘读数据页
CPU成本: 内存中处理数据

全表扫描成本 = 总页数 × 每页IO成本
索引查询成本 = 索引高度×IO + 回表行数×IO + ...
```

### 3. 常见的执行计划

| 方式 | 场景 | 代价估算 |
|------|------|---------|
| 全表扫描 | 小表/无索引 | 行数少时便宜 |
| 索引扫描 | 精确匹配 | 区分度高时 |
| 范围扫描 | BETWEEN/>/< | 取决于范围有多大 |
| 索引覆盖 | 查询的列都在索引里 | 不用回表，最快 |
| JOIN (NLJ) | 驱动表小 | 小表驱动大表 |
| JOIN (HJ) | 大表无索引 | 内存够的情况下更快 |

## 常见优化案例

```sql
-- ❌ 慢SQL
SELECT * FROM orders WHERE YEAR(created_at) = 2025;
-- 函数导致索引失效 → 全表扫描

-- ✅ 快SQL
SELECT * FROM orders 
WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01';
-- 范围查询 → 用上索引

-- ❌ 慢SQL
SELECT * FROM users WHERE name LIKE '%张三%';
-- 前模糊匹配 → 索引失效

-- ✅ 快SQL
SELECT * FROM users WHERE name LIKE '张三%';
-- 后模糊匹配 → 能用索引

-- 索引下推 (Index Condition Pushdown)
-- MySQL 5.6+ 可以在索引层面过滤
-- 减少回表次数
```

## 今日收获
- 优化器 = 基于统计信息的成本估算
- 索引失效的常见原因：函数/隐式转换/前模糊匹配
- **EXPLAIN**  = 看执行计划 = 调优的第一步
- 统计信息过期 → 优化器选错索引
- 索引覆盖 = 不回表 = 最快
