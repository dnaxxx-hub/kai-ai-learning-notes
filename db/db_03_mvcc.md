# 并发控制：锁与MVCC

> 日期：2026-05-07 19:30 | 课程：DB路线 Phase 2-1
> 目标：理解"多个事务同时读写，怎么不出错"

## 核心问题

```
事务A: 读余额100 → 扣50 → 写回50
事务B: 读余额100 → 扣30 → 写回70

如果A和B同时执行: 
A先读了100 → B也读了100 → A写了50 → B写了70
结果: 应该有50+70=120 → 实际只剩70
```

**并发问题 → 数据不一致。**

## 并发读写的三种问题

| 问题 | 现象 | 结果 |
|------|------|------|
| 脏读 | 事务B读到事务A**未提交**的数据 | A回滚 → B读到的数据是"假的" |
| 不可重复读 | 事务A两次读同一行，结果不同 | B在中间修改并提交了该行 |
| 幻读 | 事务A两次查询，行数不同 | B在中间插入/删除了行 |

## 四种隔离级别

| 级别 | 脏读 | 不可重复读 | 幻读 | 实现方式 |
|------|------|-----------|------|---------|
| READ UNCOMMITTED | ❌可能 | ❌可能 | ❌可能 | 不隔离 |
| READ COMMITTED | ✅防 | ❌可能 | ❌可能 | 每次读最新版本 |
| REPEATABLE READ | ✅防 | ✅防 | ❌可能 | 快照读(MVCC) |
| SERIALIZABLE | ✅防 | ✅防 | ✅防 | 加锁 |

**MySQL InnoDB默认: REPEATABLE READ**

## MVCC（多版本并发控制）

### 思想
> **读不阻塞写，写不阻塞读**

```
不用锁来实现隔离，而是让每个事务看到不同的版本
```

### 原理

```python
# 每行数据有多个"版本"
# 每个版本记录: 创建时间戳 + 删除时间戳

# 事务启动时得到一个"快照"
# 只看到快照之前已提交的版本
# 快照之后的版本视而不见

# INSERT → 创建版本 (create_tx = 当前事务)
# DELETE → 标记删除 (delete_tx = 当前事务)
# UPDATE → 标记旧版本删除 + 创建新版本

# 读取时: 只看到 create_tx ≤ 我的快照 && delete_tx > 我的快照 的版本
```

### MVCC的好处

```sql
-- 事务A（长事务）
SELECT * FROM users WHERE id=1;  -- 读快照，0ms
-- 事务B（更新）
UPDATE users SET balance=0 WHERE id=1;

-- 事务A再读:
SELECT * FROM users WHERE id=1;  
-- REPEATABLE READ: 还是旧值（快照读）
-- READ COMMITTED:  新值（每次读最新已提交版本）
```

## 乐观锁 vs 悲观锁

| 特性 | 悲观锁 | 乐观锁 |
|------|--------|--------|
| 思想 | "肯定有人改" | "大概率没人改" |
| 实现 | SELECT ... FOR UPDATE | 版本号/CAS |
| 适用 | 写多读少 | 读多写少 |
| 性能 | 差（锁等待） | 好（无锁） |
| 死锁风险 | 高 | 无 |

```sql
-- 乐观锁（CAS）：UPDATE时检查版本号
UPDATE products 
SET stock = stock - 1, version = version + 1
WHERE id = 1 AND version = 5;
-- 如果version被改了 → 影响行数=0 → 重试

-- 悲观锁：直接锁住
SELECT * FROM products WHERE id = 1 FOR UPDATE;
```

## 今日收获
- 并发 = 脏读/不可重复读/幻读 三种问题
- READ COMMITTED vs REPEATABLE READ 是最常用的两种隔离级别
- **MVCC = 多版本 + 快照读**，读不锁不阻塞
- 乐观锁 = CAS重试，悲观锁 = FOR UPDATE
- MySQL的RC和RR都用MVCC，区别是RR做了**间隙锁**防止幻读
