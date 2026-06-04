# Redo Log深度：InnoDB崩溃恢复的基石

> 日期：2026-05-07 22:28 | 课程：数据库深水区 Phase 2-1
> 目标：理解"InnoDB怎么保证提交的数据不会丢"

## 核心问题

```
你执行:
UPDATE users SET balance=0 WHERE id=1;

这条语句在你看来已经"执行完了"
但数据页可能还在Buffer Pool，没刷到磁盘
如果此时机器断电 → 数据没丢  → 靠Redo Log

如果数据页已经刷到磁盘，但Redo Log没写
机器断电重启 → 数据库问: "这条更新做了没？"
→ 不知道！ → 靠"Write-Ahead Logging"
```

## WAL（Write-Ahead Logging）

```python
# 铁律: 写Redo Log在前，写数据页在后

# 流程:
# 1. 修改Buffer Pool中的数据页
# 2. 写Redo Log（记录"这个页的这个偏移量改了啥"）
# 3. 事务提交（Redo Log必须刷盘）
# 4. 后台择机刷脏页到磁盘

# 如果重启:
# 检查Redo Log最后一个"检查点"
# 重放检查点之后的Redo Log → 恢复数据

# 关键: Redo Log是顺序写，数据页是随机写
# 顺序写比随机写快100倍
```

## Mini-Transaction（MTR）

```python
# 一个MTR = InnoDB内部的一次"原子操作"

# 比如:
# UPDATE一行 → 可能涉及:
# - 数据页修改 (MTR 1)
# - 索引页分裂 (MTR 2)
# - Deleted标记位修改 (MTR 3)

# 每个MTR会生成一组Redo Log记录
# 同一MTR的Redo Log要么全部执行，要么全不执行
```

## 组提交（Group Commit）

```python
# 问题: 每个事务提交都要刷Redo Log到磁盘
# 刷磁盘耗时 ~10ms (fsync)
# 如果有100个并发事务 → 每个都要等10ms → 太慢了

# Group Commit:
# 多个事务的提交一起刷盘
# 100个事务 → 全部等第1个事务的fsync → 一次刷盘
# 总耗时: 10ms 而不是 1000ms

# 步骤:
# 1. Flush Stage: 多个事务的日志写入Log Buffer
# 2. Sync Stage: 一次fsync刷到磁盘
# 3. Commit Stage: 所有事务标记为已提交

# Binlog也有组提交 → 和Redo Log组提交配合
```

## 双写（Doublewrite Buffer）

```python
# 问题: InnoDB数据页是16KB
# 但操作系统写入磁盘的最小单位是4KB（页）
# 如果写16KB时只写了4KB就断电了：
# → 数据页"半写" → 既不是旧值也不是新值

# 解决方案: Doublewrite Buffer

# 写入数据页前:
# 1. 先写到Doublewrite Buffer（内存、128页）
# 2. 再写到共享表空间的Doublewrite磁盘区域（连续2MB）
# 3. 最后写回真实的数据页位置

# 如果步骤3崩溃:
# 重启时 → 从Doublewrite区域恢复原始页
# 重新写入 → 数据完整

# 代价: 额外写（数据要写两次）
# 收益: 不会出现"半写"导致的页损坏
```

## 检查点（Checkpoint）

```python
# 问题: Redo Log会越写越大 → 不能无限增长

# 检查点: 标记"这个点之前的数据都已经刷到磁盘了"
# 检查点之前的Redo Log → 可以删除/重用

# 类型:
# 模糊检查点: 只记录检查点的LSN位置
# 页被后台线程持续刷盘 → 不阻塞用户
# 实际数据库重启时从最后一个检查点开始恢复
```

## 今日收获
- WAL = 先写Redo Log再刷数据页（顺序写快于随机写）
- MTR = InnoDB内部的原子操作
- 组提交 = 多个事务一起刷盘 → 吞吐量提升10倍
- 双写 = 防"半写页损坏"（额外的安全保障）
- 检查点 = 标记已刷盘的位置 → 控制Redo Log增长
