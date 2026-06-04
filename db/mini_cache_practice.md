# MiniCache - 纯Python Redis-like 内存缓存系统

## 概述

使用纯Python实现一个类Redis的内存缓存系统，零外部依赖。实现日期：2026-02-27。

## 核心功能

### 1. 数据结构存储
- **String**: `set`/`get`/`incr`/`decr` — 支持 NX 选项（仅当key不存在时设置）
- **List**: `lpush`/`rpush`/`lpop`/`rpop`/`lrange`/`llen` — 双端操作
- **Set**: `sadd`/`srem`/`smembers`/`sismember`/`sinter`/`sunion` — 集合运算
- **Hash**: `hset`/`hget`/`hgetall`/`hincrby`/`hdel` — 字段级操作
- **SortedSet (Zset)**: `zadd`/`zscore`/`zrange`/`zrank`/`zrem`/`zincrby` — 按分数排序

### 2. TTL 管理
- `expire(key, seconds)` — 设置过期时间
- `ttl(key)` — 查询剩余时间（-2=不存在, -1=无过期）
- `persist(key)` — 移除过期
- 惰性删除（读取时检查） + 定期扫描（每操作概率触发）

### 3. 淘汰策略
- `maxmemory` 限制总内存（字节）
- 支持策略: `noeviction` / `allkeys-lru` / `volatile-lru` / `allkeys-random` / `volatile-random` / `volatile-ttl`
- LRU 近似实现：使用 `OrderedDict` 记录访问顺序，采样5个key淘汰最少使用的

### 4. 持久化
- **RDB (快照)**: pickle 序列化整个数据集到文件。`save()` / `load()`
- **AOF (日志)**: 每个写操作追加到日志文件，启动时重放重建状态

### 5. 命令接口
- `execute(command_str)` — 解析并执行类Redis文本协议命令
- 支持: `SET GET DEL EXISTS INCR DECR KEYS TYPE RANDOMKEY RENAME`
- 支持: `LPUSH RPUSH LPOP RPOP LRANGE LLEN`
- 支持: `SADD SREM SMEMBERS SISMEMBER SINTER SUNION`
- 支持: `HSET HGET HGETALL HINCRBY HDEL`
- 支持: `ZADD ZSCORE ZRANGE ZRANK ZREM ZINCRBY`
- 支持: `EXPIRE TTL PERSIST SAVE LOAD FLUSHDB FLUSHALL DBSIZE INFO CONFIG`
- 错误处理: `WRONGTYPE`, `ERR`

### 6. 统计
- `info()` — 返回统计数据（dbsize, used_memory, maxmemory, policy, keys_evicted, hits, misses, hit_rate）

## 实现细节

### LPUSH 语义
Redis LPUSH 逐个元素从左侧插入。例如 `LPUSH lst x y`：
1. LPUSH lst x → [x]
2. LPUSH lst y → [y, x]
结果: [y, x]

实现时需要按传入顺序逐个 insert(0, value)，**不要**使用 reversed()。

### AOF 日志与重放
AOF 文件记录每个写操作的命令文本。启动时逐行执行以恢复状态。关闭时必须 `close()` 释放文件句柄，否则后续进程无法打开（Windows 文件锁）。

### LRU 淘汰
使用 Python 的 `OrderedDict` 维护访问顺序：
- 访问 key 时调用 `move_to_end(key)` 将其移到末尾
- 淘汰时取首部 key（最久未使用）
- 采样策略：只从所有 key（或 volatile key）中取前5个

## 测试覆盖
18 个测试用例覆盖全部功能：
- String CRUD、incr/decr
- List push/pop/range
- Set 交集/并集
- Hash 字段操作
- Zset 排序正确性
- TTL 惰性过期
- LRU/Random/Noeviction 三种淘汰策略
- EXISTS/DEL/TYPE/KEYS/RENAME
- RDB 快照持久化
- AOF 日志重放
- 混合持久化
- WRONGTYPE 类型检查
- Info 统计信息
