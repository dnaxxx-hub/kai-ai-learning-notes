# 数据库 #22：性能调优

## 慢查询分析
```sql
# 开启慢查询日志
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;   -- 超过1秒
SET GLOBAL log_queries_not_using_indexes = ON;

# 分析
mysqldumpslow -s t -t 10 slow.log    -- 最慢的10条
pt-query-digest slow.log              -- Percona Toolkit 分析
```

## InnoDB Buffer Pool 调优
```ini
innodb_buffer_pool_size = 70% 可用内存    -- 核心参数
innodb_buffer_pool_instances = 8          -- 减少锁竞争
```
- Pool 命中率 > 95% 正常，< 90% 需要增加内存
- `SHOW STATUS LIKE 'Innodb_buffer_pool_read_%'`

## Redo Log 优化
```ini
innodb_redo_log_capacity = 4G   -- 默认为2G，写密集型增大
innodb_log_write_ahead_size = 8192
```
- Redo log 太小 → 频繁切换 checkpoint → I/O 压力

## 磁盘 I/O 模式
- 顺序写（Redo Log/WAL）：SSD 的强项
- 随机读（数据页）：Buffer Pool 命中是关键
- 双写缓冲（Doublewrite Buffer）：SSD 上可考虑关闭

## 连接池参数（应用层）
```go
// GORM 示例
db.SetMaxOpenConns(25)              // 最大连接
db.SetMaxIdleConns(10)              // 最大空闲
db.SetConnMaxLifetime(5 * time.Minute) // 超时回收
```
- 最大连接数 > 数据库 max_connections 会报错
- 空闲太多浪费资源
