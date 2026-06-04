# 数据库内核第4课：复制与高可用

> 学习日期：2026-05-10
> 关键主题：主从复制、binlog/WAL机制、故障转移、读写分离

---

## 1. 主从复制三种模式

### 1.1 异步复制（Asynchronous Replication）

```
主库: 写入 → 提交事务 → 返回客户端 ✅
                               ↓ (后台线程, 可能有延迟)
从库:                       接收binlog → 应用
```

- **流程**：主库提交事务后立即返回客户端，不等待从库确认
- **优势**：主库延迟最小，吞吐最高
- **风险**：主库宕机时未传送到从库的数据永久丢失
- **典型延迟**：毫秒级到秒级（取决于网络和从库负载）
- **适用场景**：对数据一致性要求不高、能容忍少量数据丢失的场景

### 1.2 半同步复制（Semi-Synchronous Replication）

```
主库: 写入 → 提交事务 → 等待至少1个从库ACK → 返回客户端
                               ↓
从库:                       接收并确认
```

- **流程**：主库等待至少一个从库确认收到 binlog 后再返回客户端
- **互斥参数**：
  - `rpl_semi_sync_master_enabled=1` — 主库启用
  - `rpl_semi_sync_slave_enabled=1` — 从库启用
  - `rpl_semi_sync_master_timeout` — 超时后降级为异步（默认10秒）
  - `rpl_semi_sync_master_wait_for_slave_count=N` — 等待N个从库确认
- **权衡**：数据安全与性能的中间地带
  - 至少一个从库有数据 → 主库宕机不会丢数据
  - 但写延迟增加（至少一个RTT）

### 1.3 同步复制（Synchronous Replication）

```
主库: 写入 → 等待所有从库确认 → 提交事务 → 返回客户端
```

- **流程**：所有从库都确认收到并应用后，主库才返回客户端
- **优势**：数据零丢失（强一致性）
- **代价**：
  - 写入延迟 = 最慢从库的延迟
  - 一个从库宕机 → 整个集群不可写
  - 吞吐大幅下降
- **实现**：PostgreSQL 的 `synchronous_commit = remote_apply`

### 三种模式对比

| 特性 | 异步 | 半同步 | 同步 |
|:----|:----:|:------:|:----:|
| 数据安全 | ❌ 可能丢 | ✅ 至少1副本 | ✅✅ 全部副本 |
| 写入延迟 | 0 RTT | 1+ RTT | N RTT |
| 吞吐 | 最高 | 中等 | 最低 |
| 从库宕机影响 | 无影响 | 超时降级 | 不可写 |
| 典型场景 | 日志/分析 | 通用生产 | 金融/强一致 |

---

## 2. MySQL 复制机制

### 2.1 binlog（二进制日志）

binlog 是 MySQL 复制的基础，记录所有修改数据的操作。

**三种记录格式：**

| 格式 | 内容 | 优点 | 缺点 |
|:----|:----|:----|:----|
| **STATEMENT** | SQL语句原文 | 紧凑、量小 | 非确定性函数问题（NOW(), UUID()） |
| **ROW** | 每行变更的前后镜像 | 精确、确定性强 | 量大（尤其批量UPDATE） |
| **MIXED** | 自动选择 | 兼顾两者 | 复杂场景可能有意外 |

**binlog 文件结构：**
```
+-------------------+-------------------+-------------------+
|  File Header      |  Event            |  Event            | ...
|  (magic number    |  (GTID event /    |  (Query /         |
|   + metadata)     |   Table map /     |   Xid event)      |
|                   |   Write rows)     |                   |
+-------------------+-------------------+-------------------+
```

- `mysql-bin.000001`, `mysql-bin.000002`, ... 滚动写入
- `binlog_index` 文件维护所有 binlog 的索引
- 通过 `PURGE BINARY LOGS` 清理过期日志

### 2.2 从库复制流程

```
主库 binlog ──→ I/O线程 ──→ relay log ──→ SQL线程 ──→ 从库数据
                        ↓                              ↓
                  接收并写入               重放SQL/ROW变更
                  到 relay log             (类似重做)
```

**三步流程：**
1. **I/O 线程**：从主库读取 binlog 写入本地 relay log
2. **SQL 线程**：从 relay log 读取事件并执行
3. **协调**：两个线程异步工作，I/O 线程可能超前 SQL 线程

**relay log 文件结构：**
```
relay-log.000001 → relay-log-index → relay-log-info
    (事件序列)       (文件索引)       (断点位置记录)
```

### 2.3 GTID（全局事务ID）

**格式：** `GTID = server_uuid:transaction_id`
- 例：`3E11FA47-71CA-11E1-9E33-C80AA9429562:23`
- 全局唯一，每个事务一个 GTID

**优势：**
- **自动定位断点**：从库无需指定 binlog 文件名 + 位置（`MASTER_LOG_FILE`/`MASTER_LOG_POS`）
- **全局一致**：主从切换后新主库自动知道从哪个位置继续
- **状态追踪**：`gtid_executed`（已执行集合）和 `gtid_purged`（已清理集合）

**GTID 模式复制自动定位：**
```sql
CHANGE MASTER TO
    MASTER_HOST='新主库IP',
    MASTER_USER='repl',
    MASTER_PASSWORD='xxx',
    MASTER_AUTO_POSITION=1;  -- 不用指定FILE和POS
```

**GTID 生命周期：**
```
主库提交事务 → 分配GTID → 写入binlog → 传送到从库
                                    ↓
从库skip或重做 ← 检查gtid_executed ← 接收GTID事件
```

### 2.4 半同步复制插件

MySQL 通过插件机制实现半同步复制，需安装 `semisync_master.so` 和 `semisync_slave.so`：

```sql
-- 主库
INSTALL PLUGIN rpl_semi_sync_master SONAME 'semisync_master.so';
SET GLOBAL rpl_semi_sync_master_enabled = 1;
SET GLOBAL rpl_semi_sync_master_timeout = 10000; -- 10秒超时

-- 从库
INSTALL PLUGIN rpl_semi_sync_slave SONAME 'semisync_slave.so';
SET GLOBAL rpl_semi_sync_slave_enabled = 1;

-- 重启复制
STOP SLAVE IO_THREAD;
START SLAVE IO_THREAD;
```

**状态变量：**
- `Rpl_semi_sync_master_status` — 是否运行中
- `Rpl_semi_sync_master_clients` — 半同步从库数量
- `Rpl_semi_sync_master_yes_tx` — 成功半同步事务数
- `Rpl_semi_sync_master_no_tx` — 降级为异步的事务数（超时导致）

---

## 3. PostgreSQL 复制机制

### 3.1 WAL 流复制（Streaming Replication）

PostgreSQL 通过 WAL（Write-Ahead Log）实现复制：

```
主库 WAL ──→ WAL Sender进程 ──→ WAL Receiver进程 ──→ WAL日志 ──→ Startup进程
                                    ↓                       ↓
                              网络传输到从库           重放WAL到数据文件
```

**核心进程：**
- **WAL Sender**（主库）：读取 WAL 日志并发送到从库
- **WAL Receiver**（从库）：接收 WAL 日志写入本地
- **Startup**（从库）：重放 WAL 日志恢复数据

**配置方式（postgresql.conf）：**
```ini
# 主库
wal_level = replica                 # 或 logical
max_wal_senders = 10                # WAL发送进程上限
wal_keep_segments = 64              # 保留WAL段数

# 从库
primary_conninfo = 'host=主库IP port=5432 user=repl'
hot_standby = on                    # 从库可读
```

**创建从库（pg_basebackup）：**
```bash
pg_basebackup -h 主库IP -D /var/lib/postgresql/data -U repl -P --wal-method=stream
```

### 3.2 同步提交配置

```ini
# postgresql.conf
synchronous_commit = on             # off/local/remote_write/remote_apply/on
synchronous_standby_names = '2 (*)' # 等2个从库确认
```

**synchronous_commit 级别（从快到安全）：**

| 级别 | 含义 | 数据安全 |
|:----|:----|:--------:|
| `off` | 不等待WAL刷盘 | ❌ OS崩溃丢0.5秒数据 |
| `local` | 等待本地WAL刷盘 | ✅ 主库不丢 |
| `remote_write` | 等待从库收到WAL（未刷盘） | ⚠️ 从库OS崩溃可能丢 |
| `on` | 等待从库刷盘 | ✅✅ 主从都不丢 |
| `remote_apply` | 等待从库应用（可读） | ✅✅✅ 严格同步 |

**synchronous_standby_names 语法：**
```ini
-- 列表含义
synchronous_standby_names = '1 (node1, node2)'  -- 等最快那1个
synchronous_standby_names = '2 (*)'              -- 等任意2个
synchronous_standby_names = 'FIRST 2 (a, b, c)' -- 前2个优先级
synchronous_standby_names = 'ANY 1 (a, b)'       -- 任意1个
```

### 3.3 级联复制（Cascading Replication）

```
主库 ──→ 从库1 ──→ 从库1.1
                  ──→ 从库1.2
      ──→ 从库2
```

- **减少主库负载**：WAL Sender 只连一级，从库更多时由下游从库承担
- **地理分布友好**：从库1在北京，从库1.1在上海，减少跨区域带宽
- **配置**：从库的 `primary_conninfo` 指向另一台从库即可

**注意事项：**
- 级联复制延迟 = 各级延迟之和
- 数据安全性取决于最近的上游
- 常用于跨数据中心部署

---

## 4. 高可用架构

### 4.1 主从切换（Failover）

**手动切换流程：**
```
原主库 → 设置readonly / kill连接
       → 等待从库追赶完relay log
       → 将从库设为主库
       → 修改客户端连接指向新主库
       → 原主库恢复后作为从库加入
```

**自动切换核心问题：**
- **脑裂（Split-Brain）**：两个节点都认为自己是主库
- **仲裁机制**：需要第三方（etcd/zk/Consul）或多数派投票
- **数据一致性**：确保未复制的数据不丢失或能被保留

### 4.2 MySQL 高可用工具

| 工具 | 原理 | 特点 |
|:----|:----|:----|
| **MHA** | Manager节点监控 → SSH切换 | 成熟，但架构比较重 |
| **Orchestrator** | Raft+MySQL管理 | 自动故障检测+恢复，Web UI |
| **Patroni** | etcd/zk + 配置管理 | PG为主，也支持MySQL，HA全自动 |

**MHA 工作流程：**
```
1. Manager 监控 Master 健康
2. Master 宕机 → 识别最新的 Slave
3. SSH连接到该 Slave → 应用差异 binlog
4. 将该 Slave 提升为 Master
5. 其他 Slave 指向新 Master
```

**Orchestrator 核心：**
- 基于 Raft 的 Orchestrator 集群（3或5节点）
- 自动检测 MySQL 主库故障
- 通过 GTID 自动定位断点
- 提供回滚功能（最近切换可撤销）
- Web UI 展示集群拓扑

**Patroni 架构：**
```
        +-----------------------+
        |     etcd / ZooKeeper  |   ← 分布式配置存储
        +----------+------------+
                   |
       +-----------+-----------+
       |                       |
   Patroni(M1)           Patroni(M2)
       |                       |
    PostgreSQL主库          PostgreSQL从库
```

### 4.3 MySQL InnoDB Cluster + Group Replication

**Group Replication 原理：**
- **Paxos 风格**：多数派提交，事务广播到所有节点
- **单主模式**：只有一个节点可写，其他只读（类似主从）
- **多主模式**：所有节点可写，冲突检测解决

**InnoDB Cluster 组件：**
```
MySQL Shell → 配置管理（dba.createCluster()）
       ↓
Group Replication → 数据复制 + 组内共识
       ↓
MySQL Router → 客户端路由（读写分离自动）
```

**单主模式角色选举：**
- 协调者发生故障 → 自动重选主库
- 新主库必须拥有最新的数据
- 失败节点恢复后自动加入组

### 4.4 Paxos/Raft 为基础的 HA

**Percona XtraDB Cluster（Galera Cluster）：**
- **同步复制**：所有节点同时写，基于 Galera 库
- **认证机制**：写集（writeset）+ 全局排序 + 认证回滚
- **节点宕机**：无数据丢失，剩余节点继续服务
- **网络分区**：发生 split-brain 时，分区中的少数派停止服务

**CockroachDB：**
- **Raft 共识**：数据分片（Range），每个 Range 维护一个 Raft 组
- **强一致性**：线性一致性读写
- **自动容错**：副本失效自动重新均衡
- **跨区域**：支持跨数据中心的自动故障转移

**总结对比：**

| 架构 | 复制方式 | 一致性 | 容错能力 | 复杂度 |
|:----|:--------:|:------:|:--------:|:-----:|
| MHA | 异步/半同步 | 最终一致 | 1主挂 | 中 |
| Orchestrator | 异步/半同步 | 最终一致 | 1主挂 | 中 |
| Patroni | 流复制 | 可配置 | 1主挂 | 高 |
| InnoDB Cluster | 组复制 | 强一致 | N-1挂 | 高 |
| Galera Cluster | 同步 | 强一致 | ⌊N/2⌋挂 | 高 |
| CockroachDB | Raft | 线性一致 | ⌊N/2⌋挂 | 很高 |

---

## 5. 读写分离

### 5.1 中间件方式

**ProxySQL：**
```
客户端 ──→ ProxySQL ──→ 主库(写)
                    ──→ 从库1(读)
                    ──→ 从库2(读)
```

- **规则路由**：基于查询类型（SELECT→从库，INSERT/UPDATE/DELETE→主库）
- **连接池**：复用后端连接，减少连接开销
- **健康检查**：定期检测后端的可用性和延迟
- **查询重写**：可修改 SQL 语句（如加注释、改语法）

**ProxySQL 配置示例：**
```ini
# 分两个组：写组和读组
mysql_replication_hostgroups = (
    { writer_hostgroup=10, reader_hostgroup=20, comment="cluster" }
)

# 查询规则：SELECT 走读组，其余走写组
mysql_query_rules = (
    { rule_id=1, active=1, match_pattern="^SELECT", destination_hostgroup=20 },
    { rule_id=2, active=1, match_pattern=".*", destination_hostgroup=10 }
)
```

**MaxScale（MariaDB）：**
- 类似 ProxySQL，但专为 MariaDB 设计
- 支持自动故障检测和读写分离
- **Monitors** 监控后端状态

**HAProxy：**
- TCP/HTTP 层负载均衡
- 本身不感知 SQL 协议，需配合脚本判断主从
- 通常作为前置 LB + 后端 Keepalived 做 VIP

### 5.2 客户端方式

应用层直接集成负载均衡和路由逻辑：

```python
class DatabaseRouter:
    def __init__(self, masters, slaves):
        self.masters = masters  # 主库列表
        self.slaves = slaves    # 从库列表
    
    def get_connection(self, readonly=False):
        if readonly:
            return random.choice(self.slaves)  # 读：轮询从库
        return self.masters[0]                  # 写：固定主库
    
    def execute(self, sql, readonly=False):
        conn = self.get_connection(readonly)
        return conn.execute(sql)
```

**连接池 + 读写分离路由：**
- HikariCP（Java）/ PgBouncer（PG）
- 业务代码标记：`read_only=True` 控制路由
- 事务内自动保持同一连接

### 5.3 延迟敏感处理策略

某些场景下，写入后立即读取需要读到最新数据（刚写完就查）：

**强制读主策略：**

```python
class ReadWriteRouter:
    def __init__(self):
        self._write_recently = {}  # session_id → timestamp
    
    def execute_write(self, session_id, sql):
        master.execute(sql)
        self._write_recently[session_id] = time.time()
    
    def execute_read(self, session_id, sql):
        last_write = self._write_recently.get(session_id, 0)
        if time.time() - last_write < 0.5:  # 0.5秒内刚写过
            return master.execute(sql)       # 强制读主
        return slave.execute(sql)            # 正常读从
```

**其他方案：**
- **Session 级别绑定**：会话写过后，该会话后续都走主库
- **时间戳对比**：从库追赶到最新LSN前走主库
- **等待策略**：写操作返回从库 LSN 位置，读操作等待从库追上

---

## 6. Python 模拟：复制与故障转移

配套代码：`memory/learning/code/replication_ha_demo.py`

### 6.1 设计思路

```python
"""
模拟组件：
- Binlog: 事务日志序列
- Master: 接收写入，记录binlog，推送binlog到从库
- Slave: 接收binlog，应用日志到本地数据
- Failover: 主库挂 → 选从库升主 → 加新从库
- ReplicationDelay: 模拟网络延迟
"""
```

### 6.2 核心类设计

**Binlog 模拟：**
```python
class BinlogEntry:
    """事务日志条目"""
    def __init__(self, lsn, tx_id, operation, key, value=None):
        self.lsn = lsn           # 日志序列号
        self.tx_id = tx_id       # 事务ID
        self.operation = operation  # SET/DELETE
        self.key = key
        self.value = value
        self.gtid = None         # GTID: server_uuid:seq
```

**主库模拟：**
```python
class Master:
    def __init__(self, server_id, replication_mode='async'):
        self.server_id = server_id
        self.data = {}            # KV 存储
        self.binlog = []          # binlog 序列
        self.slaves = []          # 从库列表
        self.replication_mode = replication_mode  # async/semi_sync/sync
        self.lsn = 0
        self.tx_counter = 0
        self.alive = True
    
    def write(self, key, value):
        """写入数据：binlog → 本地数据 → 推送到从库"""
        with self.lock:
            lsn = self._allocate_lsn()
            entry = BinlogEntry(lsn, self.tx_counter, 'SET', key, value)
            entry.gtid = f"{self.server_id}:{self.tx_counter}"
            
            # 1. 写 binlog
            self.binlog.append(entry)
            
            # 2. 应用本地数据
            self.data[key] = value
            
            # 3. 推送 binlog 到从库
            if self.replication_mode == 'async':
                self._push_to_slaves_async(entry)
            elif self.replication_mode == 'semi_sync':
                self._push_to_slaves_semi_sync(entry)
            elif self.replication_mode == 'sync':
                self._push_to_slaves_sync(entry)
            
            return entry  # 返回 binlog 条目
```

**从库及故障转移模拟：**
```python
class Slave:
    def __init__(self, server_id, master, delay_ms=0):
        self.server_id = server_id
        self.data = {}
        self.relay_log = []
        self.applied_lsn = -1
        self.delay_ms = delay_ms    # 模拟复制延迟
        self.is_master = False      # 是否已升为主库
        self.alive = True
    
    def apply_entry(self, entry):
        """应用 binlog 到本地"""
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)  # 模拟延迟
        
        if entry.operation == 'SET':
            self.data[entry.key] = entry.value
        elif entry.operation == 'DELETE':
            self.data.pop(entry.key, None)
        
        self.applied_lsn = entry.lsn
        # 记录 relay log
    
    def promote_to_master(self):
        """提升为主库"""
        self.is_master = True
        return Master(self.server_id, replication_mode='async')
```

### 6.3 故障转移模拟

```python
def simulate_failover(master, slaves):
    """主库挂了 → 选最新从库升主 → 加新从库同步"""
    
    # 1. 主库宕机
    master.alive = False
    print(f"⛔ Master {master.server_id} crashed!")
    print(f"   Last binlog LSN: {master.lsn}")
    print(f"   Last GTID: {master.tx_counter}")
    
    # 2. 选择最新的从库（已应用 LSN 最大 + relay log 最新）
    best_slave = max(slaves, key=lambda s: (s.applied_lsn, len(s.relay_log)))
    print(f"🏆 Promoting Slave {best_slave.server_id} (applied_lsn={best_slave.applied_lsn})")
    
    # 3. 升级为新的主库
    new_master = best_slave.promote_to_master()
    print(f"✅ New Master: {new_master.server_id}")
    
    # 4. 其他从库指向新主库
    remaining_slaves = [s for s in slaves if s.server_id != best_slave.server_id]
    old_slave = slaves[0] if slaves else None
    
    # 5. 新从库加入（从新主库全量同步）
    if old_slave:
        new_slave = Slave("slave-3", new_master, delay_ms=0)
        catch_up_sync(new_slave, new_master)
        new_master.slaves.append(new_slave)
        remaining_slaves.append(new_slave)
        print(f"🆕 New slave joined and caught up!")
    
    return new_master, remaining_slaves
```

### 6.4 完整模拟场景

运行 `replication_ha_demo.py` 验证以下场景：

```
=== 场景1: 异步复制 ===
主库写入10条 (key0~key9), 从库延迟100ms
主库返回: 10/10 立即返回 ✅
从库同步: 10/10 已应用 ✅
 
=== 场景2: 半同步复制 ===
主库写入5条, 从库确认后返回
等待从库 ACK...
主库返回: 5/5 已在从库确认 ✅
 
=== 场景3: 主库故障转移 ===
主库写入中 → 宕机
轮询从库状态...
选择最新从库: slave-1 (已应用9条)
提升slave-1为新主库
其他从库指向新主库 ✅
 
=== 场景4: 新从库加入追赶 ===
新从库 slave-3 加入
全量同步: 从新主库复制所有数据
增量追赶: 从断点开始接收新 binlog
追赶完成: slave-3 已同步 ✅
 
=== 场景5: 同步复制 ===
主库写入3条, 等待所有从库确认
所有从库已确认, 返回客户端 ✅
```

---

## 7. 总结与思考

### 7.1 核心权衡

```
数据安全 ←→ 性能
  一致性 ←→ 可用性
  复杂度 ←→ 可靠性
```

- **异步复制** → 最快的写入，但有数据丢失风险
- **同步复制** → 最安全，但延迟和可用性是代价
- **半同步** → 实用折中，生产环境首选

### 7.2 MySQL vs PostgreSQL 复制差异

| 方面 | MySQL | PostgreSQL |
|:----|:------|:----------|
| 日志格式 | binlog (STATEMENT/ROW/MIXED) | WAL (物理日志) |
| 从库读取 | I/O 线程+SQL 线程 | WAL Receiver+Startup |
| 复制方式 | binlog 推拉 | WAL Sender 推送 |
| 级联 | 支持 | 原生支持 |
| 同步模式 | 插件 (semisync) | 内核内置 |
| GTID | MySQL 5.6+ | LSN (日志序列号) |
| 从库可读 | 默认不可读需设置 | hot_standby=on |

### 7.3 高可用设计要点

1. **故障检测**：心跳超时 + 多次重试，避免误判
2. **选主策略**：最新数据优先，避免选丢数据的从库
3. **数据补偿**：旧主恢复后作为从库加入，自动追赶
4. **防脑裂**：仲裁节点 / STONITH（Shoot The Other Node In The Head）
5. **优雅降级**：半同步超时降级异步，不阻塞写入

### 7.4 架构演进路径

```
单库 → 异步主从 → 半同步 → 组复制/PAXOS → 全球多活
  ↓        ↓          ↓          ↓            ↓
单点    读扩展    安全写入   自动故障   地理容灾
```

---

## 参考资料

- MySQL 官方文档：Replication
- PostgreSQL 官方文档：High Availability, Load Balancing, and Replication
- Percona XtraDB Cluster 文档
- Raft 论文：In Search of an Understandable Consensus Algorithm
