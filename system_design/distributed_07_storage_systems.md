# 分布式系统 第7课：分布式存储系统（Google 三驾马车）

> **学习日期**: 2026-05-10
> **前置知识**: 分布式共识(Raft/Paxos)、一致性哈希、分布式事务
> **本课覆盖**: GFS / Bigtable / Spanner / 极简分布式KV实现

---

## 大纲

1. [Google File System (GFS)](#1-google-file-system-gfs)
2. [Google Bigtable](#2-google-bigtable)
3. [Google Spanner](#3-google-spanner)
4. [极简分布式 KV 存储实现](#4-极简分布式-kv-存储实现)

---

## 1. Google File System (GFS)

### 1.1 核心设计思路

GFS 是为 Google 内部大规模数据处理（如 PageRank 爬取、索引构建）设计的分布式文件系统。设计前提：

| 前提 | 含义 |
|------|------|
| **硬件故障是常态** | 大量廉价机器，任一时刻都有故障 |
| **文件巨大** | 多 GB 级文件很常见，小文件不优化 |
| **追加为主，覆盖极少** | 数据流式写入，写一次读多次 |
| **高吞吐量优先** | 延迟不是首要目标 |

### 1.2 系统架构

```
┌──────────┐     Heartbeat / 元数据操作
│  Master  │◄──────────────────────────┐
│ (主)      │                          │
│ G名空间树 │  Shadow Master(备)       │
│ 文件→Chunk │   日志 + Checkpoint      │
│ Chunk位置 │                          │
│ 租约管理  │                          │
└────┬─────┘                          │
     │ 控制流                          │
     │ (租约授予/Chunk位置)             │
     ▼                                 │
┌──────────┐    数据流(不经过Master)     │
│  Client  │────────────────────────► ChunkServer
│          │  读: IP + ChunkHandle     │  (若干台,存64MB
│ 缓存:    │  追加: 控制流到Primary     │   Chunk副本)
│ Chunk位置 │  数据流到所有副本(链式)     │
└──────────┘                          │
                                      │
    ChunkServer  ◄──── Heartbeat ────┘
    (存数据块 + 校验和)
```

**三个主要组件**：

- **Master**：元数据服务器，管理文件系统命名空间、Chunk → 位置映射、租约管理
- **ChunkServer**：数据存储节点，每个 Chunk 默认 3 副本，存 Linux 文件
- **Client**：与 Master 交互获取元数据（缓存），直接与 ChunkServer 传输数据

### 1.3 Chunk 设计（64MB）

为什么是 **64MB** 这种大块？

```
Chunk大小对比：

传统 FS 4KB:    ████░░░░░░░░░░░░░░░░  (元数据多)
GFS 64MB:       ████████████████████  (元数据少，大IO优势)

好处：
1. 减少元数据量 → Master 内存可容纳所有元数据
2. 客户端一次获取 Chunk 位置 → 多次读写重用缓存
3. 大块顺序读取 → HDD 磁盘吞吐率最大化
4. 减少 Master 交互次数
```

- **延迟初始化**：只在写入时创建新 Chunk
- **副本数**：默认 3，可通过配置调整
- **校验和**：每个 Chunk 分为 64KB 块，每块 32-bit 校验和

### 1.4 单 Master + Shadow Master

**单 Master 是瓶颈也是简化点**：

```
读路径:
  Client → Master(元数据) → ChunkServer(数据)
  │                   │
  ▼                   ▼
  缓存元数据         直接数据流
  (可重复使用)       (不经过Master)

写路径(追加):
  Client → Master(查询Primary) → Primary ChunkServer
      ↓
  数据推送到所有副本(链式管道)
      ↓
  所有副本ACK → Primary回复Client
```

**Shadow Master**（备 Master）：
- 只读，提供读放大降低（实际很少用，Master 本身够快）
- 实时从 Master 复制操作日志 + Checkpoint
- 如果 Shadow Master 的 Chunk 位置信息过期 → 回退到 ChunkServer 查询

**故障恢复**：
- Master 崩溃 → 从操作日志 + Checkpoint 恢复
- Shadow Master 提升需要人工干预（Google 经验：频率非常低）

### 1.5 租约（Lease）机制

**问题**：多个 ChunkServer 写同一 Chunk，谁决定写入顺序？

**解决方案**：租约（Lease）

```
租约生命周期:

  Master                          Primary ChunkServer
    │                                    │
    ├── 授予租约(60s) ──────────────────►│
    │                                    ├── 写序列化 (所有写入排队)
    │                                    ├── 心跳续约
    │◄─────────── Heartbeat + 续约 ─────┤
    │                                    │
    │  (Master 暂停写 → 等到期或回收)      │
    │                                    │
    └── Primary故障 → 等待租约到期(60s) ──┘
                    → 授予新Primary
```

**为什么用租约不用分布式锁**：
- 租约不依赖外部协调服务（GFS 无 ZooKeeper）
- Master 崩溃时租约自动到期，无需清理
- 时间租约天然支持故障检测

### 1.6 追加写入（Record Append）

GFS **不支持覆盖写入**，核心操作为 **追加**。

```
传统写入（GFS 不支持）:
  [原有数据] ← 新数据覆盖 → [新数据]

GFS 追加:
  [原有数据 | 新追加数据 | 新追加数据...]

并发追加语义（At-least-once Append）:
  Client1: "aaaa"
  Client2: "bbbb"
  
  可能的磁盘布局（交错可能导致空洞但原子追加）:
  ┌────────────┬────────────┬────────────┐
  │ Primary    │ Secondary1 │ Secondary2 │
  ├────────────┼────────────┼────────────┤
  │ aaaa│bbbb  │ aaaa│bbbb  │ aaaa│bbbb  │
  └────────────┴────────────┴────────────┘

追加的原子性保障:
  1. Client 发送数据到所有副本（链式管道）
  2. Primary 分配 offset，所有副本在相同 offset 写入
  3. 任一副本失败 → Client 重试（可能导致重复记录）
  4. 应用层通过 record ID 去重
```

**为什么只追加**：
- 简化并发控制（不需要锁、不需要复杂的写冲突解决）
- MapReduce/PageRank 等应用天然适合追加写
- HDD 顺序写性能远优于随机写

### 1.7 关键设计决策

| 决策 | 原因 |
|------|------|
| 单 Master | 简单，瓶颈可控（元数据全内存，操作快） |
| Chunk 64MB | 减少元数据、大IO优化、减少Master交互 |
| 租约 | 避免分布式锁的复杂度，自动过期 |
| 追加写入 | 简化并发，匹配应用模式 |
| 3副本 | 权衡可靠性和成本 |
| 校验和 | 检测静默数据损坏（bit rot） |
| Shadow Master | 读扩展（虽然Google很少用到） |

---

## 2. Google Bigtable

### 2.1 数据模型

Bigtable 本质上是一个 **稀疏、分布式、多维排序映射表**。

```
数据模型： (row:string, column:string, time:int64) → string

                   列族(Column Family)
                   ┌──────┐   ┌──────┐
                   │ cf1  │   │ cf2  │
                   ├──┬───┤   ├──┬───┤
                   │q1│ q2│   │q1│ q2│  ← 列限定符(Qualifier)
                   │  │   │   │  │   │
   "com.example" ──┤  │   │   │  │   │
                   │  │t3 │   │  │t3 │  ← 时间戳 (t3 > t2 > t1)
                   │  │t2 │   │  │t2 │
                   │  │t1 │   │  │t1 │
```

**实际示例**（网页存储）：

```
Row Key          | Column "anchor:"   | Column "contents:"
─────────────────┼────────────────────┼─────────────────────
"com.cnn.www"    | anchor:cnnsi="CNN" | contents:"<html>..."
(t3=19:30)       |   "CNN"            |   "网页HTML内容"
                 | (t3=19:30)         | (t3=19:30)
```

**核心特性**：
- **Row Key**：任意字符串，按字典序排序 → 范围扫描友好
- **Column Family**：权限控制单元，相同列族通常存同类数据
- **Timestamp**：64位整数（微秒），自动版本GC可配置

### 2.2 底层存储：GFS

```
       Bigtable
    ┌─────────────┐
    │  Tablet 0   │
    │  (行范围a-c)  │
    ├─────────────┤
    │  Tablet 1   │   ← Bigtable逻辑视角，Tablet是行范围分区
    │  (行范围d-f)  │
    └─────────────┘
           │
    SSTable 文件 (不可变，按key排序)
    ┌────────────────┐
    │ SSTable        │
    │ ┌──┬──┬──┬──┐  │  ← 数据块 + 索引 + Bloom Filter
    │ │  │  │  │  │  │
    │ └──┴──┴──┴──┘  │
    └────────────────┘
           │
           ▼
    GFS (底层存储)
    ┌──────────────┐
    │ ChunkServer  │  ← 最终存储平台
    │ (3副本)       │
    └──────────────┘
```

### 2.3 Tablet 分裂机制

Bigtable 的粒度控制单元是 **Tablet**（类似 HBase 的 Region）。

```
Tablet的层次结构:

  ┌────────────────────────────────────────┐
  │           META0 Tablet                  │ ← 根Tablet，固定位置
  │  记录所有META1 Tablet的位置               │  (从不分裂)
  └────────────────┬───────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
  ┌──────┐      ┌──────┐      ┌──────┐
  │META1 │      │META1 │ ...  │META1 │  ← META1 Tablet
  │t1-t3 │      │t4-t7 │      │t100..│  记录用户Tablet位置
  └──────┘      └──────┘      └──────┘
    │
    ▼
  ┌──────────┐   ┌──────────┐
  │ UserTab  │   │ UserTab  │    ← 用户表 Tablet
  │ row a-d  │   │ row e-h  │
  └──────────┘   └──────────┘
```

**三层次寻址**：
```
寻址流程:
  Client → 1. 查询 META0 (根)
         → 2. 查询 META1 (用户表位置)
         → 3. 直接访问 Chubby(锁服务)
```

**分裂流程**（一条 URL 表为例）：

```
(1) Tablet满 (~200MB)
    ┌──────────────────────────────────┐
    │ Tablet: "com.cnn.www"~"com.mit"  │  ← 太大，需要分裂
    └──────────────────────────────────┘

(2) Master选择分裂点(中间Row Key)
    ┌────────────────┬─────────────────┐
    │ "com.cnn.www"~ │ "com.google"~   │
    │ "com.google"   │ "com.mit"       │
    └────────────────┴─────────────────┘

(3) 生成两个新SSTable
    Tablet-1.sstable → Tablet-2.sstable

(4) Master在META表中更新记录
    删除旧条目，添加两个新条目
```

### 2.4 SSTable + MemTable

Bigtable 使用 LSM-Tree 风格的读写路径：

```
写入路径:
  Client write("com.cnn.www", <data>)
                │
                ▼
            ┌──────────┐
            │ MemorTable │  ← 内存中的有序缓冲区 (写缓存)
            │ (Red-Black │    写入先到这里，累积一定量再刷盘
            │  Tree)     │
            └─────┬─────┘
                  │ 满了 → 冻结当前MemTable
                  ▼
            ┌──────────┐
            │ SSTable   │  ← 写入GFS，不可变文件
            │ (文件0)    │    写时立即创建新MemTable
            └──────────┘

读取路径:
  Client read("com.cnn.www")
                │
                ▼
      检查所有层次，从新到旧:
    ┌────────────────┐
    │ 1. MemTable    │  ← 先查内存 (最新数据)
    ├────────────────┤
    │ 2. SSTable 1   │  ← 然后查最近的SSTable
    ├────────────────┤
    │ 3. SSTable 0   │  ← 再查更早的SSTable
    ├────────────────┤
    │ ...            │
    └────────────────┘
    
    (使用 Bloom Filter 快速跳过不包含key的SSTable)

合并(Compaction):
  小SSTable合并成大SSTable
  删除重复记录(保留最新版本)
  删除已删除的记录
```

**SSTable 内部结构**：

```
┌──────────────────────────────────────┐
│  Data Block 0: (key1→val1, key2...)  │
│  Data Block 1: (...)                  │
│  ...                                  │
│  Data Block N: (...)                  │
├──────────────────────────────────────┤
│  Index: [Block0:key1, Block1:keyX..] │  ← 二分查找定位数据块
├──────────────────────────────────────┤
│  Bloom Filter: (判断key是否存在)      │  ← 快速跳过不包含key的块
├──────────────────────────────────────┤
│  Footer: [Index位置, Bloom位置]       │
└──────────────────────────────────────┘
```

### 2.5 Master 与 Tablet Server

```
Bigtable集群组件:

  Chubby (分布式锁 + 选主):
  ┌──────────────────────────┐
  │  ● Master (锁)           │
  │  ● Tablet Server (锁)    │  
  │  ● 访问控制ACL           │
  │  ● META0位置             │
  └──────────────────────────┘

  Master:
  ┌──────────────────────────┐
  │ ● 分配Tablet给TabletServer│
  │ ● 监控TabletServer健康   │
  │ ● Tablet分裂/合并调度    │
  │ ● GFS垃圾清理            │
  │ (不参与读写路径)          │
  └──────────────────────────┘

  Tablet Server（若干台）:
  ┌──────────────────────────┐
  │ ● 处理读写请求            │
  │ ● 管理SSTable(读)        │
  │ ● 管理MemTable(写)       │
  │ ● Tablet分裂执行          │
  └──────────────────────────┘
```

### 2.6 关键设计决策

| 决策 | 原因 |
|------|------|
| Row Key 排序 | 范围扫描高效，支持前缀扫描 |
| LSM-Tree | 写优化，顺序写GFS，不可变SSTable适合读多写少 |
| SSTable不可变 | 简化并发控制，适合GFS追加写模式 |
| MemTable | 批量写入减少GFS操作次数 |
| Bloom Filter | 减少不必要的SSTable扫描 |
| 三层次寻址 | 缓存友好，META不会成为瓶颈 |

---

## 3. Google Spanner

### 3.1 全球级分布式数据库

Spanner 是 Google 的 **全球级（Global-scale）分布式数据库**，特点：

```
F1 (Google AdWords)
    │
    ▼
  Spanner ← 全球数据，外部一致性
    │
    ├── GPS + 原子钟 → TrueTime
    ├── Paxos → 跨数据中心共识
    └── 2PC → 跨分片事务
```

数据组织：

```
数据模型 → 分层关系型表 (SQL-like)
  目录(Directory)：数据放置单元
  区域(Zone)：一个Paxos组（Leader + Followers）
  分片：自动分裂
```

### 3.2 TrueTime API

**这是 Spanner 最重要的创新** —— 用物理时钟实现一致性而不牺牲性能。

```
TrueTime 接口：

  TT.now() → [earliest, latest]
              ↑           ↑
            最早可能时间  最晚可能时间
            (保证真实时间在这区间内)

  TT.after(t)  → true if t < earliest
  TT.before(t) → true if latest < t

时钟误差（误差区间）：
  ──────┬──────earliest──────┬──────latest──────→ 时间轴
        │                    │
        │   真实时间(未知)     │
        │   ∈ [e, l]         │
        └────────────────────┘

  常规服务器          GPS + 原子钟
  ±几百ms误差        ±1~7ms（95% < 4ms）
```

**GPS 误差来源**：
- 卫星信号接收（天线部署、电磁干扰）
- 大气层延迟校正
- GPS 接收器时钟漂移

**原子钟**：短期精度高，弥补 GPS 故障时的空白期。

### 3.3 外部一致性（External Consistency）

**定义**：数据库行为等同于在单台机器上串行执行，且事务顺序遵循墙钟（wall-clock）顺序。

```
非一致性场景（普通数据库）:

  Client A:  Write(X=1) @ 10:00:00.100
  Client B:  Read(X)    @ 10:00:00.200
  
  Client B 可能读到 X=0（看不到 A 的写入）
  （因为 A 的写可能还没到达 B 所在的副本）

外部一致性场景 (Spanner):

  Client A:  Write(X=1) @ 10:00:00.100
  Client B:  Read(X)    @ 10:00:00.200
  
  Client B 一定读到 X=1
  （Spanner 保证写的时间戳 < 读的时间戳时，读能看到写）
```

**实现机制**：

```
写事务步骤（用 TrueTime 保证）：

  1. 给 Paxos leader 发送写请求
  2. Leader 分配时间戳 s = TT.now().latest（保证所有副本一致）
  3. 等待 TT.after(s) —— 直到 earliest > s
     (等待钟差过去，确保所有服务器时间已越过 s)
  4. Paxos 提交 s
  5. 回复 Client

读事务步骤：

  1. 分配读时间戳 s_read ≥ TT.now().latest
  2. 等待 TT.after(s_read)
  3. 在最新的副本上执行读（保证看到所有 ≤ s_read 的写）

为什么等待叫做"Commit Wait"：
  ──────s──────e───────→ 时间
        ↑       ↑
    写时间戳  当前时间  等待直到 earliest > s
                      → 保证所有时钟已超过 s
                      → 保证 s 是"过去"的
```

### 3.4 2PC + Paxos 混合

**Paxos 用于组内复制，2PC 用于跨组协调**。

```
单一 Paxos 组内复制：

  ┌─ Zone 1 (Data Center A) ─┐
  │  Leader ── Leader ────── │  ← 服务读写
  │  │     Paxos              │
  │  ├── Follower (DC B)      │
  │  └── Follower (DC C)      │
  └───────────────────────────┘

  Paxos 角色：
  - Leader：序列化写入，分配时间戳
  - Follower：接受复制，参与选举
  - 读：Leader 本地可读（不需要多数派）

跨组 2PC 事务（表跨多个目录/分片）:

  ┌────────────────────────────────────┐
  │          Coordinator (协调者)        │
  │  (任选一个组的Leader担任)            │
  └──┬──────────┬──────────┬──────────┘
     │          │          │
     ▼          ▼          ▼
  ┌──────┐  ┌──────┐  ┌──────┐
  │Group1│  │Group2│  │Group3│  ← 每个Group内部Paxos复制
  │Paxos │  │Paxos │  │Paxos │
  └──────┘  └──────┘  └──────┘

2PC 流程:

  Prepare阶段:
  Coordinator → 所有 Participant
                Prepare(t)
  Participant → Ack(就绪) 或 No(放弃)

  Commit阶段:
  Coordinator → 所有 Participant
                Commit(t) 或 Abort

  参与者故障 → 日志恢复可以重新询问Coordinator
```

**为什么 2PC + Paxos**：

```
仅用2PC：协调者单点故障 → 整个事务挂起
仅用Paxos：不支持跨组事务（Paxos只解决副本一致性）

Spanner方案：
  - 组内：Paxos 提供高可用 + 强一致复制
  - 组间：2PC 提供跨组原子提交
  - Paxos 日志 -> 协调者故障时可选举新协调者（恢复2PC状态）
```

### 3.5 与 Bigtable 的关系

```
              Spanner vs Bigtable
┌────────────────────┬────────────────────┐
│     Spanner        │     Bigtable       │
├────────────────────┼────────────────────┤
│ SQL + 事务         │ Key-Value + 单行事务 │
│ 外部一致性         │ 最终/弱一致性        │
│ 全球部署           │ 单数据中心           │
│ 2PC + Paxos       │ 无跨行事务           │
│ TrueTime          │ 无                  │
│ 读写分离（读副本）  │ 单一角色             │
└────────────────────┴────────────────────┘

Spanner → 适合 AdWords、Gmail 等需要强一致性 + SQL
Bigtable → 适合 Web索引、爬取等 高吞吐 + 模式灵活
```

### 3.6 Spanner 关键设计决策

| 决策 | 原因 |
|------|------|
| TrueTime(GPS+原子钟) | 用物理时钟实现外部一致性，避免时钟不同步陷阱 |
| Paxos 投票 | 跨数据中心强一致复制、自动故障转移 |
| 2PC 协调 | 跨分片事务的原子提交保障 |
| Commit Wait | 等时钟误差窗口过去，保证时间戳安全 |
| 分层关系型表 | 支持SQL + schema evolution + 目录放置控制 |

---

## 4. 极简分布式 KV 存储实现

> **文件名**: `memory/learning/code/distributed_kv.py`
> **模拟方式**: 线程 + queue.PriorityQueue 模拟管道通信
> **功能**: 分片哈希 + 主备复制 + 强一致读

### 4.1 架构设计

```
        ┌───────────────────────────────────────┐
        │               Client                   │
        │    hash(key) → shard_id                 │
        │    路由到指定分片节点                     │
        └──┬────────────┬────────────┬──────────┘
           │            │            │
           ▼            ▼            ▼
      ┌─────────┐  ┌─────────┐  ┌─────────┐
      │ Shard 0 │  │ Shard 1 │  │ Shard 2 │  ← 分片节点
      │ 主/备   │  │ 主/备   │  │ 主/备   │
      └─────────┘  └─────────┘  └─────────┘

  每个分片:
  ┌─────────────────────────┐
  │ Shard Server            │
  │ ┌─────────────────────┐ │
  │ │ 主(Master)          │ │
  │ │  ← 处理读写         │ │
  │ ├─────────────────────┤ │
  │ │ 备(Backup)          │ │
  │ │  ← 复制写入 + 可读  │ │
  │ └─────────────────────┘ │
  └─────────────────────────┘
```

### 4.2 代码文件位置

完整代码见: `memory/learning/code/distributed_kv.py`

核心组件：
- `KVNode`：单个KV节点（主或备）
- `ShardGroup`：一个分片组（主+备）
- `DistributedKV`：分布式KV整体（分片路由 + 协调）

### 4.3 验证结果

运行三个分片，每个分片 1 主 1 备：
```
分片0: 主+备 (键hash到0)
分片1: 主+备
分片2: 主+备

写入 "key_a" → hash=0 → Shard0主写入 → 复制到备
读取 "key_a" → hash=0 → 主读 (强一致)
主故障 → 读切换到备 (故障转移)
备恢复写 → 新写入自动复制
```

---

## 三驾马车体系总览

```
          Google 数据基础设施栈

  ┌─────────────────────────────────────┐
  │            Spanner                   │
  │  全球分布式关系型数据库(外部一致)     │
  │  SQL, 事务, TrueTime, 2PC+Paxos      │
  ├─────────────────────────────────────┤
  │           Bigtable                   │
  │  稀疏分布式多维排序表(高吞吐KV)       │
  │  LSM-Tree, SSTable, Tablet分裂       │
  ├─────────────────────────────────────┤
  │             GFS                      │
  │  分布式文件系统(底层基石)              │
  │  64MB Chunk, 追加写, 主+Shadow       │
  ├─────────────────────────────────────┤
  │      硬件：廉价服务器 + 磁盘          │
  └─────────────────────────────────────┘

  三者关系:
  GFS 提供存储 → Bigtable 提供结构化数据接口
  GFS 提供存储 → Spanner 提供事务性数据库
  Bigtable 不依赖 Spanner, Spanner 不依赖 Bigtable
  它们共享一些基础设施(Chubby锁/集群管理)
```

---

## 核心考点速记

| 系统 | 一句话概括 | 核心创新 |
|------|-----------|---------|
| GFS | 大文件追加写分布式文件系统 | 64MB Chunk、租约机制 |
| Bigtable | 稀疏分布式排序多维表 | LSM-Tree、Tablet分裂 |
| Spanner | 全球级事务数据库 | TrueTime、外部一致性 |

**面试常问**：
1. **GFS 为什么用 64MB Chunk？** 减少元数据、大IO、减少Master交互
2. **租约和分布式锁的区别？** 租约自动过期，不依赖外部锁服务
3. **GFS 追加和普通写入区别？** 追加是 at-least-once，应用层去重
4. **SSTable vs B+Tree？** SSTable 顺序写不可变，适合 LSM-Tree；B+Tree 原地更新随机写
5. **TrueTime 误差怎么办？** commit wait 等钟差过去
6. **Spanner 为什么不用 TSO？** TSO 有单点故障 + 全球延迟高

---

*本笔记为分布式系统第7课，覆盖 Google 三驾马车的核心原理和实现细节。配套代码见 `code/distributed_kv.py`。*
