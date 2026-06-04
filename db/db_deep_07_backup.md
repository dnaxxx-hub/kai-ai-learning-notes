# 备份与恢复

> 日期：2026-05-07 22:32 | 课程：数据库深水区 Phase 3-3
> 目标：理解"数据库挂了你还能找回多少数据"

## 核心问题

```python
# 数据库可能发生的事:
# - 磁盘坏了 → 数据全丢
# - 误操作 → DROP TABLE 删错表
# - 数据损坏 → 文件系统错误
# - 被攻击 → 勒索病毒加密数据

# 备份 = 最后的防线
```

## 备份类型

### 1. 全量备份

```python
# 备份整个数据库

# mysqldump: 逻辑备份（生成SQL语句）
mysqldump -u root -p mydb > mydb.sql
# 优点: 可读，可编辑，跨版本
# 缺点: 慢（要逐行读数据）, 大表很慢

# XtraBackup: 物理备份（复制数据文件）
xtrabackup --backup --target-dir=/backup/full
# 优点: 快（文件级复制）, 支持增量
# 缺点: 只能在同版本的MySQL恢复
```

### 2. 增量备份

```python
# 只备份"从上一次备份以来改过的数据"

# XtraBackup增量
xtrabackup --backup --target-dir=/backup/inc1 \
           --incremental-basedir=/backup/full

# 恢复时需要按顺序: 全量 → 增量1 → 增量2 → ...
```

### 3. binlog备份

```python
# 实时备份binlog（天级别的数据量）
# 配合全量备份 → 实现PITR（时间点恢复）

# 场景:
# 备份: 昨晚12点全量备份
# 灾难: 今天下午3点误删表
# 恢复: 
# 1. 恢复到昨晚12点的全量
# 2. 重放binlog: 12:00 → 15:00之前（跳过DROP语句）
```

## PITR（时间点恢复）

```sql
-- 基于binlog恢复到指定时刻

-- 1. 先恢复全量备份
mysql -u root -p mydb < full_backup.sql

-- 2. 从全量备份时间点 → 到灾难发生前一刻
mysqlbinlog --start-datetime="2026-05-06 00:00:00" \
            --stop-datetime="2026-05-07 14:59:59" \
            binlog.000001 binlog.000002 | mysql -u root -p

-- 跳过误执行的DROP语句
```

## 3-2-1 备份策略

```python
# 3份数据
# 2种存储介质（本地 + 异地）
# 1份异地存储

# 建议:
# 日常: 每天全量 + binlog实时
# 本地: 保留最近7~30天
# 异地: 每月或每周同步到云端（S3/OSS等）
```

## 恢复验证

```python
# 比备份更重要的事: 验证备份可用

# 常见悲剧:
# DBA每天做备份，但从不恢复测试
# 灾难来了 → 发现备份文件是坏的

# 建议:
# 每周至少恢复一次备份到测试环境
# 检查: 表结构完整 / 数据行数正确 / 业务能跑通
```

## 误操作补救（无备份时）

```sql
-- 如果误删了数据，而且没有备份:

-- 情况1: DROP TABLE
-- 试试从binlog找回
-- 或者看看有没有从库

-- 情况2: DELETE忘加WHERE
-- 立刻: SET GLOBAL innodb_flush_log_at_trx_commit=2;
-- 让InnoDB别急着刷盘
-- 然后: 数据可能还在Buffer Pool里
-- 但保活方案成功率不高

-- 最好的方案: 提前准备（备份 + 延迟从库 + 智能查询审计）
```

## 今日收获
- 备份三件套 = 全量 + 增量 + binlog
- XtraBackup = 物理备份（比mysqldump快）
- PITR = binlog重放到指定时间点
- 3-2-1 = 备份的最佳实践
- **比备份更重要的是定期恢复测试**
- 误操作补救很难 → 预防比补救重要100倍
