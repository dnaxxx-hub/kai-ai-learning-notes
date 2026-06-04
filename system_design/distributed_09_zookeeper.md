# 第9课：ZooKeeper 深入与分布式协调服务

> **学习日期**: 2026-02-26  
> **核心脉络**: 分布式系统中，多个节点需要协调——谁做主？状态如何同步？节点挂了怎么办？ZooKeeper 就是为了解决这些问题而生的分布式协调服务。

---

## 一、ZooKeeper 概述

ZooKeeper 是一个**分布式协调服务**，为分布式应用提供：
- 配置管理（Configuration Management）
- 命名服务（Naming Service）
- 分布式锁（Distributed Locking）
- 集群选主（Leader Election）
- 服务发现（Service Discovery）

### 为什么需要 ZK？

| 问题 | ZK 的解决方案 |
|------|--------------|
| 配置动态变更 | Watcher 监听配置 ZNode |
| 服务上下线通知 | 临时节点 + Watcher |
| 分布式锁冲突 | 顺序节点 + Watch 前一个节点 |
| Leader 挂了 | ZAB 崩溃恢复协议 |
| 数据不一致 | ZAB 原子广播 + 多数派 |

### ZK 保证

- **顺序一致性**（Sequential Consistency）：客户端的更新按发送顺序应用
- **原子性**（Atomicity）：更新要么全成功要么全失败
- **单一系统镜像**（Single System Image）：客户端无论连到哪个 Server 都看到同一视图
- **可靠性**（Reliability）：更新一旦被多数派接受就会持久化
- **及时性**（Timeliness）：系统的滞后性有界，避免了"脑裂"

---

## 二、ZNode 数据结构

### 2.1 数据模型——树形命名空间

```
/ (root)
├── /services
│   ├── /services/api-gateway    (ephemeral, 0000000001)
│   ├── /services/user-service   (ephemeral, 0000000002)
│   └── /services/order-service  (ephemeral, 0000000003)
├── /config
│   ├── /config/database         (persistent, "url=jdbc:...")
│   └── /config/redis            (persistent, "host=10.0.1.1:6379")
├── /lock
│   ├── /lock/resource-1         (persistent)
│   │   └── /lock/resource-1/seq-0000000001
│   │   └── /lock/resource-1/seq-0000000002
│   └── /lock/resource-2         (persistent)
├── /leader                      (ephemeral, node-id=server-3)
└── /election
    └── /election/nodes
        └── /election/nodes/candidate-0000000001
        └── /election/nodes/candidate-0000000002
```

### 2.2 ZNode 类型

| 类型 | 持久性 | 顺序编号 | 场景 |
|------|--------|----------|------|
| **PERSISTENT**（持久） | 创建后持久存在，除非主动删除 | 无 | 配置存储、元数据 |
| **EPHEMERAL**（临时） | 创建客户端会话断开后自动删除 | 无 | 服务注册、Leader 选主 |
| **PERSISTENT_SEQUENTIAL**（持久顺序） | 持久，ZK 自动追加顺序号 | 全局单调递增 | 分布式队列 |
| **EPHEMERAL_SEQUENTIAL**（临时顺序） | 临时，ZK 自动追加顺序号 | 全局单调递增 | 分布式锁、选主 |

### 2.3 ZNode 结构

每个 ZNode 包含：
```
path:    /services/user-service
data:    "192.168.1.100:8080"
stat:    {                    # ZNode 状态信息
  czxid:  0x100000001,        # 创建时的事务 ID
  mzxid:  0x100000002,        # 最后修改时的事务 ID
  ctime:  1700000000,         # 创建时间戳
  mtime:  1700000001,         # 修改时间戳
  version:    2,              # 数据版本号（乐观锁）
  cversion:   0,              # 子节点版本号
  aversion:   0,              # ACL 版本号
  ephemeralOwner: 0x300000001,# 临时节点所属 Session ID
  dataLength:  22,            # 数据长度
  numChildren: 0,             # 子节点数量
  pzxid:  0x100000001         # 子节点列表修改时的事务 ID
}
```

> **关键点**: ZNode 的 `version` 字段用于**乐观锁**——更新时如果版本号不匹配（其他客户端已修改），操作会失败，从而实现 CAS（Compare-And-Swap）。

---

## 三、Watcher 机制

### 3.1 核心设计

Watcher 是 ZK 实现**发布-订阅**模式的核心机制。

```
┌──────────┐  setData()     ┌───────────┐
│  Client A │ ─────────────> │  ZK Server │
└──────────┘                 └─────┬─────┘
                                   │ 数据变化
                                   │ 触发 Watcher
┌──────────┐                       ▼
│  Client B │ <─────────────────── 通知
└──────────┘  (一次性通知)
```

### 3.2 Watcher 特性

| 特性 | 说明 |
|------|------|
| **一次性触发**（One-time trigger） | 通知一次后立即失效，需要重新注册 |
| **异步通知**（Async notification） | ZK 保证先发送通知，后更新数据 |
| **轻量级**（Lightweight） | 通知只包含「发生了什么」，不包含「是什么」|
| **有序性**（Ordering） | 同一个客户端的通知按事件发生顺序到达 |

### 3.3 Watcher 事件类型

| 事件 | 触发条件 | 可监听的 API |
|------|----------|-------------|
| `None` | 客户端连接状态变化 | — |
| `NodeCreated` | ZNode 被创建 | `exists()` |
| `NodeDeleted` | ZNode 被删除 | `exists()`, `getData()`, `getChildren()` |
| `NodeDataChanged` | ZNode 数据被修改 | `exists()`, `getData()` |
| `NodeChildrenChanged` | ZNode 子节点列表变化 | `getChildren()` |
| `Node` | ZNode 相关事件 | — |
| `DataWatchRemoved` | 数据 Watcher 被移除 | — |
| `ChildWatchRemoved` | 子节点 Watcher 被移除 | — |

### 3.4 Watcher 注册 API

```java
// 注册 Watcher 的三种方式
zk.exists(path, watcher);               // 监听节点的创建、删除、数据变化
zk.getData(path, watcher, stat);         // 监听节点的删除、数据变化
zk.getChildren(path, watcher);           // 监听子节点列表的变化
```

### 3.5 Watcher 使用模式

```
【典型模式】Watch + 重新注册
─────────────────────────────────────────
步骤 1: Client 调用 getData("/config", watcher)
步骤 2: Server 返回数据，注册 watcher
步骤 3: 数据变化 → Server 触发 watcher → Client 收到通知
步骤 4: Client 处理完通知 → 再次 getData("/config", watcher)
         （重新注册，因为 watcher 是一次性的）
步骤 5: 回到步骤 3（循环）
─────────────────────────────────────────
```

---

## 四、会话（Session）管理

### 4.1 Session 生命周期

```
        ┌─────────────────────────────────────┐
        │              DISCONNECTED           │
        │                │                    │
        │           connect()                 │
        │                ▼                    │
        │          CONNECTING                 │
        │                │                    │
        │     连接建立 + Session 创建          │
        │                ▼                    │
        │      ┌─── CONNECTED ───┐            │
        │      │                 │            │
        │  心跳保持连接            会话超时      │
        │      │                 ▼            │
        │      │           EXPIRED            │
        │      └─────────────────┘            │
        └─────────────────────────────────────┘
```

### 4.2 会话关键参数

```
SessionID:  0x300000001      # 全局唯一 Session ID
TimeOut:    10000ms          # 会话超时时间
TickTime:   2000ms           # ZK 服务器时间单位
Expiration: currentTime + TimeOut  # 会话过期时间
```

### 4.3 会话超时处理

```
【超时检测机制】
ZK Server 每 TickTime 检查一次会话是否过期。
如果当前时间 > 会话过期时间，则关闭该会话。

【自动重连】
客户端断开后会自动重连到其他 ZK 节点。
重连期间：临时节点依然存在（只要没超时）。
超时后：临时节点被删除，watcher 被触发。
```

### 4.4 会话相关行为

| 事件 | 影响 |
|------|------|
| 心跳成功 | Session 续期，重置过期时间 |
| 客户端断开 | 进入 CONNECTING 状态，自动重连 |
| 会话超时 | 临时节点被删除，Watcher 被触发 |
| 会话转移 | 重连到新节点，Session 状态保持不变 |

---

## 五、读写分离架构

### 5.1 架构角色

```
┌──────────────────────────────────────────────────────────┐
│                   ZooKeeper Ensemble                     │
│                                                          │
│     ┌──────────┐   ┌──────────┐   ┌──────────┐          │
│     │  LEADER  │   │ FOLLOWER │   │ FOLLOWER │  ...    │
│     │ (写 + 读) │<─>│  (读)    │<─>│  (读)    │          │
│     └────┬─────┘   └────┬─────┘   └────┬─────┘          │
│          │              │              │                 │
└──────────┼──────────────┼──────────────┼─────────────────┘
           │              │              │
      ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
      │ Client  │   │ Client  │   │ Client  │
      └─────────┘   └─────────┘   └─────────┘
```

### 5.2 读写模型

| 操作 | 处理节点 | 是否需要 Leader | 说明 |
|------|---------|----------------|------|
| **读**（getData / exists / getChildren）| 任意节点 | ❌ | 本地直接返回，不经过共识 |
| **写**（create / setData / delete）| Leader 节点 | ✅ | 经 ZAB 原子广播达成共识 |
| **Watch 注册** | 任意节点 | ❌ | 在连接的节点上注册 |

### 5.3 写请求流程

```
Client → Follower  →  Leader  →  Follower  →  Client
  │          │           │           │           │
  │ 写请求    │           │           │           │
  │ ────────> │           │           │           │
  │          │ 转发请求   │           │           │
  │          │ ────────> │           │           │
  │          │           │ 提案广播   │           │
  │          │           │ ────────> │           │
  │          │           │ <──────── │ ACK       │
  │          │           │ 提交      │           │
  │          │           │ ────────> │ 应用      │
  │          │           │           │ ────────> │
  │          │           │           │ 响应      │
  │          │ 响应      │           │           │
  │ <────────│           │           │           │
```

### 5.4 为什么读不需要共识？

- ZK 保证**单一系统镜像**：任意节点返回的数据不会比已经提交的更旧
- 实际上 Follower 可能落后于 Leader，ZK 的保证是**最终一致性** + 单调读
- 如果需要强一致读取，可以调用 `sync()` 方法先同步再读

---

## 六、ZAB 协议（ZooKeeper Atomic Broadcast）

ZAB 是 ZK 的核心共识协议，分为两个模式：
1. **崩溃恢复**（Recovery Mode）：Leader 挂了后的选举和数据同步
2. **消息广播**（Broadcast Mode）：正常运行时的事务提交

### 6.1 ZAB 的核心：zxid（事务 ID）

```
zxid = epoch (高32位) + counter (低32位)

例子:
zxid = 0x100000001
       │         │
       │         └── counter = 1（事务序号）
       └──────────── epoch = 268435456（Leader 任期）
```

| 组成部分 | 含义 | 变化时机 |
|---------|------|---------|
| **epoch** | Leader 的任期编号 | 每次新 Leader 选举 +1 |
| **counter** | 该 Leader 任期内的事务序号 | 每处理一个事务 +1 |

> **ZK 对比 Raft**: ZK 用 zxid 单一维度（epoch + counter）就能确定事务的全序关系；Raft 需要 term + log index 两个维度。

### 6.2 消息广播（二阶段提交的变体）

```
【正常事务提交流程】

Leader                            Follower
  │                                   │
  │  1. PROPOSAL (zxid, data)         │
  │ ───────────────────────────────>  │
  │                                   │
  │  2. ACK                           │
  │ <───────────────────────────────  │
  │                                   │
  │  3. COMMIT (zxid)                 │
  │ ───────────────────────────────>  │
  │                                   │
  │  4. 应用事务到内存                │
  │                                   │
  │                                   │
  【与 2PC 的区别】                    │
  ● ZK 没有 Prepare 阶段              │
  ● ZK 的 ACK 就是 Prepare + Commit   │
  ● 收到多数派 ACK 就 Commit          │
  ● 没有回滚（在 ZK 中写操作不会失败）  │
```

**消息广播的关键特性：**
1. Leader 为每个事务生成唯一的 zxid（严格递增）
2. Leader 向所有 Follower 发送 PROPOSAL 消息
3. Follower 将事务写入事务日志（磁盘），然后回复 ACK
4. Leader 收到多数派（quorum）的 ACK 后，发送 COMMIT
5. Follower 收到 COMMIT 后，将事务应用到内存数据库

### 6.3 崩溃恢复

当 Leader 崩溃或失去多数派连接时，ZAB 进入恢复模式：

```
【Leader Election 流程】

1. 每个节点进入 LOOKING 状态
2. 节点广播自己的选票 (myid, zxid)
3. 比较规则：
   a. 优先选 zxid 最大的节点（数据最新的）
   b. zxid 相同则选 myid 最大的
4. 获得多数派（> N/2）投票的节点成为 Leader
5. 新 Leader 开始数据同步
```

**数据同步策略：**

| 同步类型 | 条件 | 行为 |
|---------|------|------|
| **DIFF**（差异化同步）| Follower 只落后部分事务 | 发送差异事务并提交 |
| **TRUNC**（截断同步）| Follower 有 Leader 没有的事务 | 回滚多余事务，再同步 |
| **SNAP**（全量同步）| Follower 落后太多或没有事务日志 | 发送完整快照 |
| **TRUNC+DIFF** | 截断 + 差异结合 | 先截断后补差异 |

```
【新 Leader 数据同步过程】

Leader（zxid=0x200000005）          Follower（zxid=0x200000003）
  │                                        │
  │  NEWLEADER (epoch)                      │
  │ ─────────────────────────────────────>  │
  │                                        │
  │  检测到 Follower 落后 2 个事务          │
  │  zxid 0x200000004 和 0x200000005       │
  │                                        │
  │  PROPOSAL (0x200000004) + COMMIT        │
  │ ─────────────────────────────────────>  │
  │  PROPOSAL (0x200000005) + COMMIT        │
  │ ─────────────────────────────────────>  │
  │                                        │
  │  UPTODATE                              │
  │ <─────────────────────────────────────  │
```

### 6.4 ZAB vs Raft 对比

| 维度 | ZAB | Raft |
|------|-----|------|
| **核心标识** | zxid（epoch + counter） | term + log index |
| **Leader Election** | 先到先得 + 比较 zxid | 随机超时 + 请求投票 |
| **日志复制** | 二阶段提交变体 | 日志条目追加 |
| **数据同步** | DIFF / TRUNC / SNAP | 日志复制（AppendEntries） |
| **脑裂保护** | 法定人数（多数派） | 法定人数（多数派） |
| **角色** | Leader / Follower / Observer | Leader / Candidate / Follower |
| **写性能** | Leader 单点写 | Leader 单点写 |
| **读性能** | 任意节点可读 | 仅 Leader（新版本支持 ReadIndex） |
| **心跳机制** | PING 消息 | AppendEntries（空条目心跳） |
| **日志一致性** | zxid 单调递增保证 | Term 和 Log Index 对比 |

---

## 七、典型应用场景

### 7.1 服务发现（Service Discovery）

```
【服务注册 + 发现机制】

┌────────────┐  create(/services/user/192.168.1.1:8080, EPHEMERAL)
│ User-Svc-1 │ ────────────────────────────────────────────────>  ZooKeeper
│ 启动       │                                                         │
└────────────┘                                                  ┌─────┴──────┐
                                                                 │ /services  │
┌────────────┐  create(/services/user/192.168.1.2:8080, EPHEMERAL)│ ├ user/     │
│ User-Svc-2 │ ────────────────────────────────────────────────>  │ │ ├ 192.168│
│ 启动       │                                                    │ │ └ 192.168│
└────────────┘                                                    │ ├ order/   │
                                                                  │ └ api-gw/  │
┌────────────┐  getChildren(/services/user, watcher)              └────────────┘
│ API-Gateway│ <────────────────────────────────────────────────           │
│ (消费者)   │                                                    User-Svc-1 挂了
│            │  NodeChildrenChanged (通知)  <───────────────── Session 超时
│            │  getChildren(/services/user) → 获得新的地址列表
└────────────┘
```

### 7.2 分布式锁

使用临时顺序节点实现分布式锁——**"最小节点优先"** 算法。

```
【加锁流程】

锁路径: /lock/resource-1

步骤 1: 创建临时顺序节点 /lock/resource-1/lock-0000000003
步骤 2: 获取 /lock/resource-1 的所有子节点
步骤 3: 判断自己是不是最小的那个节点
步骤 4a: 是 → 获得锁
步骤 4b: 否 → 监听前一个节点的删除事件
         └── 等前一个节点删除后回到步骤 2

示意图：
/lock/resource-1/
    ├── lock-0000000001  ← Client-C 持有锁
    ├── lock-0000000002  ← Client-B 等待（监听 lock-0000000001）
    └── lock-0000000003  ← Client-A 等待（监听 lock-0000000002）
```

**代码伪代码：**
```java
// 加锁
String myNode = zk.create("/lock/resource-1/lock-", 
                          data, CreateMode.EPHEMERAL_SEQUENTIAL);
while (true) {
    List<String> children = zk.getChildren("/lock/resource-1", false);
    Collections.sort(children);
    if (myNode.equals(children.get(0))) {
        return; // 获得锁
    }
    String prevNode = children.get(children.indexOf(myNode) - 1);
    // 监听前一个节点
    Stat stat = zk.exists("/lock/resource-1/" + prevNode, watcher);
    if (stat != null) {
        watcher.wait(); // 阻塞等待前一个节点被删除
    }
}

// 解锁
zk.delete("/lock/resource-1/" + myNode, -1);
```

### 7.3 集群选主（Leader Election）

```
【选主流程】

所有候选节点在 /election 下创建临时顺序节点。
创建后获取所有子节点，最小的那个就是 Leader。

    候选节点: C-1, C-2, C-3, C-4, C-5

    /election/candidate-0000000001  ← Leader（C-1）
    /election/candidate-0000000002  ← Standby（监听 candidate-0000000001）
    /election/candidate-0000000003  ← 监听 candidate-0000000002
    /election/candidate-0000000004  ← 监听 candidate-0000000003
    /election/candidate-0000000005  ← 监听 candidate-0000000004

    当 Leader（C-1）挂了：
    1. Session 超时 → candidate-0000000001 被删除
    2. C-2 收到 NodeDeleted 通知
    3. C-2 检查自己是当前最小的节点 → 成为新 Leader

【优势】
- 每个节点只监听前一个节点（避免惊群效应）
- Leader 挂了只有一个节点收到通知并接替
```

### 7.4 配置管理（Configuration Management）

```
【动态配置中心】

┌──────────────┐
│  Admin Console│  setData("/config/database", "url=new-url...")
│  (运维人员)   │ ──────────────────────────────────────────────>  ZooKeeper
└──────────────┘                                                   ┌─ /config/database ─┐
                                                                    │ "url=old-url..."   │
                                                                    └────────────────────┘
应用服务器启动：
    getData("/config/database", watcher)
    → 获取初始配置并注册 watcher
    
配置变更：
    1. Admin 更新 /config/database 数据
    2. ZK 触发 Client A、B、C 的 Watcher
    3. Client 收到 NodeDataChanged 通知
    4. Client 获取新配置并应用
    5. Client 重新注册 watcher（循环）
```

---

## 八、etcd 对比分析

### 8.1 etcd 概述

etcd 是 CoreOS 开发的分布式键值存储，与 ZK 功能类似但设计更现代化。

```
etcd 技术栈:
┌──────────────────────────┐
│      gRPC API            │  ← 基于 HTTP/2，双向流
├──────────────────────────┤
│      MVCC（多版本并发控制） │  ← 保留历史版本
├──────────────────────────┤
│      Raft 共识协议        │  ← 更简洁、可理解
├──────────────────────────┤
│      BoltDB / bbolt      │  ← 底层 KV 存储引擎
└──────────────────────────┘
```

### 8.2 核心概念对比

| 维度 | ZooKeeper | etcd |
|------|-----------|------|
| **API 风格** | 自定义协议（Jute） | gRPC（Protobuf） |
| **通信协议** | TCP 长连接 + 自定义序列化 | HTTP/2 + Protobuf |
| **数据模型** | 树形 ZNode（有目录结构） | 扁平 KV（按 key 前缀组织） |
| **存储** | 内存树 + 事务日志 + 快照 | BoltDB 持久化 KV + MVCC |
| **共识协议** | ZAB（自研） | Raft（业界标准） |
| **版本控制** | 单一版本 + version 乐观锁 | 多版本（MVCC，保留历史） |
| **Watcher** | 一次性触发，单向 | Watch 流式（保持连接持续推送） |
| **租约机制** | Session 绑定 | Lease 独立于 Session |
| **语言绑定** | Java 原生，其他语言通过 C 绑定 | 原生 gRPC，多语言一流支持 |
| **事务** | 无（单节点操作） | 支持事务（TXN，条件 + 操作） |
| **读一致性** | 单调读（sync() 可强一致） | 可配置（Serializable / Linearizable）|
| **运维工具** | zkCli.sh | etcdctl |
| **健康检查** | 临时节点 | Lease + KeepAlive |
| **社区** | Apache 基金会 | CNCF（云原生基金会）|

### 8.3 Watch 机制对比

```
ZK Watcher（一次性）:
Client ──注册──> ZK Server
                  │ 数据变化
                  │ 触发事件
Client <──通知─── Server
Client ──重新注册─> Server  ← 必须重新注册才能继续监听

etcd Watch（流式）:
Client ──Watch──> etcd Server
                  │ 数据变化 1
Client <──通知──── Server
                  │ 数据变化 2
Client <──通知──── Server  ← 长连接保持，不需要重新注册
                  │ 数据变化 3
Client <──通知──── Server
```

### 8.4 事务支持

**etcd 事务（TXN）示例：**
```go
// etcd 事务：如果 key1 的值是 "v1"，则更新 key2，否则删除 key3
txn := client.Txn(ctx).
    If(compare.Value("key1", "=", "v1")).
    Then(client.OpPut("key2", "v2")).
    Else(client.OpDelete("key3"))
txnResp, err := txn.Commit()
```

**ZK 不支持事务**——每个操作都是原子的，但不能组合成事务。

### 8.5 选型建议

| 场景 | 推荐 | 理由 |
|------|------|------|
| Hadoop/HBase 生态 | **ZK** | 天然集成，Kafka/HBase 依赖 ZK |
| 微服务注册发现 | **etcd** 或 ZK | 两者都可，etcd 更现代化 |
| Kubernetes | **etcd** | K8s 的核心存储，必须用 etcd |
| 配置中心 | **etcd** | Watch 流式 + 多版本支持 |
| 分布式锁 | **ZK** | 临时顺序节点天然适合 |
| 云原生应用 | **etcd** | gRPC 原生支持，CNCF 生态 |
| 高性能要求 | **etcd** | BoltDB 持久化性能更好 |

---

## 九、ZooKeeper 局限与注意事项

### 9.1 已知局限

1. **写性能瓶颈**：所有写操作必须经过 Leader，无法水平扩展写能力
2. **Watch 一次性**：需要反复注册，编程模型复杂
3. **数据量限制**：所有 ZNode 存储在内存中，不适合大容量数据存储
4. **重连风暴**：大规模节点同时重连可能导致 ZK 集群压力激增
5. **Leader 选举期间不可用**：选举期间整个集群无法处理写请求

### 9.2 最佳实践

```
【连接管理】
- 复用 ZooKeeper 客户端实例（重量级，维护 Session）
- 设置合理的 Session Timeout（通常 10-30s）
- 实现 Watcher 自动重新注册

【数据设计】
- ZNode 数据大小限制在 1MB 以内，最好 < 1KB
- 避免大量临时节点快速创建删除（会导致 Leader 压力大）
- 合理设计命名空间深度（一般不超过 5 层）

【性能调优】
- 使用 Observer 节点扩展读能力（不参与投票）
- 合理设置 tickTime（默认 2000ms）
- 使用 sync() 确保强一致读
```

---

## 十、总结与思维导图

```
                          ┌─────────────────┐
                          │  ZooKeeper      │
                          │  分布式协调服务   │
                          └────────┬────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
       ┌────┴────┐           ┌────┴────┐           ┌────┴────┐
       │  数据模型 │           │  一致性   │           │  应用    │
       ├─────────┤           ├─────────┤           ├─────────┤
       │ ZNode   │           │ ZAB协议  │           │ 服务发现  │
       │ ├持久    │           │ ├广播    │           │ 分布式锁  │
       │ ├临时    │           │ ├恢复    │           │ 集群选主  │
       │ └顺序    │           │ └zxid   │           │ 配置管理  │
       │ Watcher  │           │ vs Raft  │           │          │
       │ Session  │           │         │           │          │
       └─────────┘           └─────────┘           └──────────┘
```

### 关键理解

1. **ZK 本质是一个协调服务，不是数据库**——数据量小，但要求高可靠
2. **ZAB = ZK 自研的共识协议**——与 Raft 思路相似但独立进化
3. **ZNode + Watcher = 分布式的观察者模式**——变化的主动通知而非轮询
4. **zxid 是 ZAB 的核心**——一个数字同时编码了任期和序号
5. **ZAB 的同步策略比 Raft 复杂**——DIFF/TRUNC/SNAP 三种模式应对不同场景
6. **etcd 正在取代 ZK**——云原生生态中 etcd 更受欢迎，但 ZK 在 Hadoop 生态中不可替代

---

**下一课预告**: 分布式系统第10课——分布式共识算法 Raft 彻底理解
