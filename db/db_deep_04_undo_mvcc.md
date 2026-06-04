# Undo Log与MVCC深度

> 日期：2026-05-07 22:29 | 课程：数据库深水区 Phase 2-2
> 目标：理解"回滚和MVCC的底层细节"

## Undo Log类型

```sql
-- 每种DML操作产生不同的Undo:

-- INSERT: 记录插入的行ID
-- → 回滚时: 直接删除该行
-- → 提交后: Undo可以立即清理

-- DELETE: 记录被删除行的完整内容
-- → 回滚时: 重新插入
-- → MVCC: 保留给还在运行的事务

-- UPDATE: 记录修改前的旧值
-- → 回滚时: 恢复旧值
-- → MVCC: 保留旧版本
```

## 回滚段（Rollback Segment）

```python
# Undo Log存储在"回滚段"中
# 每个回滚段包含1024个Undo Slot

# InnoDB默认128个回滚段
# → 最多128 × 1024 = 131072个并发事务

# Undo Slot内部: 记录变更前的旧值
# 和组织方式类似链表（可以追溯历史版本）
```

## MVCC的可见性判断

```python
# 每个事务启动时, 创建一个"视图"（ReadView）
# ReadView包含:

# m_low_limit_id: 当前活跃事务的最大ID+1
# m_up_limit_id:  当前活跃事务的最小ID
# m_ids:          当前活跃事务ID列表

# 判断一条数据应不应该被看到:
# 1. 创建这条数据的事务 < m_up_limit_id → 可见（已提交）
# 2. 创建这条数据的事务 >= m_low_limit_id → 不可见（还没开始）
# 3. 创建这条数据的事务在m_ids中 → 不可见（还在运行）
# 4. 创建这条数据的事务不在m_ids中 → 可见（已提交）

# 所以: RR级别下, 同一个ReadView用到底
# RC级别下, 每条SQL创建新的ReadView
```

## Purge（清理）

```python
# 问题: Undo Log不能无限保留
# 当"所有可能用到这个版本的事务都结束了"
# → 这个Undo Log就可以删了

# Purge线程做这件事:
# 1. 检查哪些Undo Log不再需要
# 2. 物理删除Undo Log记录
# 3. 如果DELETE标记的行没有事务需要 → 真正删除

# 大事务的问题:
# 一个长事务一直不结束
# → 它的ReadView保留所有"它开始时的活跃事务"的Undo
# → Undo Log越积越多 → 表空间膨胀
# → 甚至导致"历史版本过多" → 性能下降
```

## 锁的兼容性矩阵

```python
# InnoDB锁的类型:

# 行级锁:
# - S锁 (共享锁): SELECT ... LOCK IN SHARE MODE
# - X锁 (排他锁): UPDATE/DELETE/INSERT/SELECT ... FOR UPDATE

# 间隙锁 (Gap Lock): 锁区间, 防插入
# 临键锁 (Next-Key Lock): 行锁 + 间隙锁 = RR默认

# 意向锁 (表级):
# - IS锁: 事务准备加S锁
# - IX锁: 事务准备加X锁

# 兼容性:
#        S    X    IS   IX
#   S    ✅   ❌   ✅   ✅
#   X    ❌   ❌   ❌   ❌
#   IS   ✅   ❌   ✅   ✅
#   IX   ✅   ❌   ✅   ✅

# 核心: S和X不兼容（读和写冲突）
#        IX和IX兼容（两个写事务可以同时在不同的行）
```

## 今日收获
- INSERT/DELETE/UPDATE 产生不同的Undo
- 回滚段 = Undo存储容器（128×1024个Slot）
- ReadView = 事务启动时的"快照"（决定看到哪个版本）
- Purge = 清理不再需要的Undo
- 锁兼容性矩阵 = S/X/IS/IX四种锁的冲突关系
