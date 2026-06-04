# 第3课：一致性协议（ZAB / Gossip / Paxos 概述）

> 系统设计 — 分布式系统核心 | 日期：2026-05-10
> 学习目标：理解三大一致性协议的核心机制与适用场景

---

## 目录

1. [ZAB — ZooKeeper Atomic Broadcast](#1-zab--zookeeper-atomic-broadcast)
2. [Gossip 协议 — 反熵传播](#2-gossip-协议--反熵传播)
3. [Paxos 简介 — 分布式一致性理论基础](#3-paxos-简介--分布式一致性理论基础)
4. [Raft vs Paxos vs ZAB 对比](#4-raft-vs-paxos-vs-zab-对比)
5. [Python 代码实现](#5-python-代码实现)

---

## 1. ZAB — ZooKeeper Atomic Broadcast

**ZAB** 是 ZooKeeper 使用的崩溃恢复原子广播协议，保证 ZooKeeper 集群在进程崩溃或网络分区时仍然能够对外提供一致性服务。

### 1.1 ZAB 的两个核心阶段

```
┌─────────────────────────────────────────────────────┐
│                    ZAB 协议                           │
├──────────────────────┬──────────────────────────────┤
│  崩溃恢复阶段          │  原子广播阶段                 │
│  (Leader Election +   │  (Message Broadcast)         │
│   Recovery)           │                              │
│  ① 选出一个 Leader    │  ① Leader 接收写请求          │
│  ② 同步未提交事务      │  ② 广播 Proposal             │
│  ③ 与过半 Follower    │  ③ 收集 Quorum 确认          │
│     建立同步关系       │  ④ 提交（Commit）             │
└──────────────────────┴──────────────────────────────┘
```

### 1.2 Fast Leader Election（快速选举）

ZooKeeper 使用 **Fast Leader Election（FLE）** 算法来选出新的 Leader。

**选举规则（ZooKeeper 3.4+）：**

```
每个服务器启动时发出投票 (myid, zxid)：
  - myid：服务器唯一 ID
  - zxid：最大事务 ID（越新越大）
  
投票规则（按优先级）：
  1. zxid 最大的服务器优先
  2. zxid 相同时，myid 最大的优先
  3. 获得过半票数 → 成为 Leader
```

**选举过程：**

```
图解：5 节点集群（myid=1,2,3,4,5）

1. Follower 检测到 Leader 失联（心跳超时）
2. Follower 切换为 LOOKING 状态
3. 每个 LOOKING 节点投给 (zxid 最大, myid 最大) 的节点
4. 节点收到过半相同投票 → 确认新 Leader

示例流程：
  节点1: (zxid=100, myid=1) → 投给节点5
  节点2: (zxid=95,  myid=2) → 投给节点5  
  节点3: (zxid=100, myid=3) → 投给节点5
  节点4: (zxid=98,  myid=4) → 投给节点5
  节点5: (zxid=100, myid=5) → 投给自己
  → 节点5 获 5/5 票 → 成为 Leader
```

### 1.3 原子广播（Atomic Broadcast）

ZAB 的原子广播类似于 2PC（两阶段提交）的变体，但做了崩溃容忍优化。

```
Leader                          Follower
  │                                 │
  │  1. PROPOSAL(txid, data)        │
  │ ──────────────────────────────> │
  │                                 │
  │  2. ACK(txid)                   │
  │ <────────────────────────────── │
  │                                 │
  │  3. 收到过半 ACK → 提交         │
  │                                 │
  │  4. COMMIT(txid)                │
  │ ──────────────────────────────> │
  │                                 │
  │  5. 本机提交并响应客户端         │
```

**关键特性：**
- **FIFO 顺序**：事务按 zxid 递增顺序处理
- **全局有序**：所有服务器看到的事务顺序一致
- **至少一次**：保证事务最终被执行（幂等处理）

### 1.4 崩溃恢复（Crash Recovery）

当新 Leader 选出后，需要完成状态同步：

```
新 Leader 处理步骤：
1. 从 Follower 收集各自的最新 zxid
2. 找出「已提交但未同步」的事务
3. 向所有 Follower 发送缺失的 COMMIT 消息
4. 通知所有 Follower 开始接受新 Proposal
```

**关键规则：**
- **Leader 必须拥有所有已提交的事务**（zxid 最大）
- **未提交的事务被丢弃**（client 会重试）
- **同步完成前，集群不接受新写入**

---

## 2. Gossip 协议 — 反熵传播

**Gossip（流言协议）** 是一种去中心化的最终一致性协议，灵感来自流行病传播模型。广泛用于：Cassandra、Redis Cluster、DynamoDB、Consul。

### 2.1 核心思想

```
每个节点随机选择几个其他节点交换信息
→ 信息像病毒一样扩散
→ 最终所有节点数据一致
```

### 2.2 三种传播模式

```
┌─────────────────────────────────────────────┐
│               Gossip 模式                     │
├──────────────┬──────────────┬────────────────┤
│  Push（推）   │ Pull（拉）    │ Push-Pull      │
├──────────────┼──────────────┼────────────────┤
│ A 把自己的     │ A 向 B        │ A 推给 B       │
│ 数据发给 B     │ 拉取 B 的数据  │ 同时从 B 拉取   │
│              │              │                │
│ A →→→→→→ B   │ A ←←←←←← B   │ A ↕↕↕↕↕↕↕ B   │
│ 开销：小      │ 开销：中      │ 开销：大        │
│ 适用：更新多   │ 适用：更新少   │ 适用：对称      │
└──────────────┴──────────────┴────────────────┘
```

**收敛速度：**
```
设集群有 N 个节点，每个周期选择 f 个节点传播：
- 时间复杂度：O(log(N))
- 经过 O(log(N)) 轮后，信息扩散到全网

举例 N=1000, f=2:
  轮次 0:  1  节点知晓
  轮次 1:  3  节点知晓  (1 + 1*2)
  轮次 2:  9  节点知晓  (3 + 3*2)
  轮次 3:  27 节点知晓
  轮次 4:  81 节点知晓
  轮次 5:  243 节点知晓
  轮次 6:  729 节点知晓
  轮次 7:  1000+ (全网覆盖)
```

### 2.3 去中心化与容错

```
Gossip 容忍：
  ✓ 节点随时加入/离开（membership 自动收敛）
  ✓ 消息丢失（下轮继续传播）
  ✓ 网络分区（恢复后自动同步）
  ✓ 节点故障（其他节点替代传播）
```

### 2.4 SWIM — 成员关系维护

**SWIM（Scalable Weakly-consistent Infection-style Process Group Membership）** 是 Gossip 协议的一个变体，专门用于成员管理。

```
SWIM 的两层机制：

1. 故障检测（Failure Detection）
   每个节点周期性地 ping 一个随机节点
   → 如果无响应，发 indirect ping（让其他节点代为 ping）
   → 仍无响应 → 标记为可疑（Suspected）
   → 多轮确认后 → 宣告死亡（Dead）

2. 成员更新传播（Gossip Dissemination）
   一旦检测到成员变化，通过 Gossip 扩散到全集群

SWIM vs 传统心跳：
  - 传统心跳：每个节点向所有人发 → O(N²) 消息
  - SWIM：随机采样 → O(N log N) 消息
```

**SWIM 的 Suspect 机制（避免误判）：**
```
Time ──────────────────────────────────────────>
   │         │          │             │
   A ping B  │  无响应   │  indirect   │  宣告死亡
   ─────→    │  ───→    │  ping 确认  │  ──────→
             │          │  ──────→   │
```

---

## 3. Paxos 简介 — 分布式一致性理论基础

**Paxos** 是 Leslie Lamport 提出的共识算法，被公认为分布式一致性理论的基础。虽然实践中很少直接使用（因为复杂），但它是理解 Raft、ZAB 的基础。

### 3.1 Basic Paxos

**三个角色：**
```
Proposer（提案者） → 提出值
Acceptor（接受者） → 投票决策
Learner（学习者） → 学习最终决定
```

**两阶段提交：**

```
Phase 1: Prepare/Promise
  Proposer              Acceptor
    │                       │
    │  1. Prepare(N)        │  N = 提案编号（全局递增）
    │ ──────────────────>  │
    │                       │  如果 N > 之前看到的编号:
    │                       │  → Promise(N, 上次接受的值)
    │  2. Promise(N, v)     │  → 不再接受 < N 的 Prepare
    │ <──────────────────  │
    │                       │

Phase 2: Accept/Accepted
  Proposer              Acceptor
    │                       │
    │  3. Accept(N, v)      │  v = 上一个 Promise 中编号最大的值
    │ ──────────────────>  │  或如果没有，用自己提的值
    │                       │  如果 N >= 已 Promise 的编号:
    │                       │  → 接受该值
    │  4. Accepted(N)       │
    │ <──────────────────  │
    │                       │
```

**核心约束（Paxos 正确性）：**
```
P1: Acceptor 必须接受它收到的第一个提案
P2: 如果值为 v 的提案被选中，
    所有更高编号的提案也必须选中 v
P2c: 对于任意提案 (N, v)：
     存在一个过半集 S，使得 S 中：
     • 要么 S 中没有 Acceptor 接受过 < N 的提案
     • 要么 v 是 S 中所有 < N 的提案中编号最大的值
```

### 3.2 活锁问题

```
两个 Proposer 轮流干扰：
  P1: Prepare(1) → Promise → Accept(1) → 被 P2 的 Prepare(2) 拒绝
  P2: Prepare(2) → Promise → Accept(2) → 被 P1 的 Prepare(3) 拒绝
  P1: Prepare(3) → Promise → Accept(3) → 被 P2 的 Prepare(4) 拒绝
  ... 无限循环

解法：
  • 选举 Distinguished Proposer（唯一 Leader）
  • 随机退避（Random Backoff）
```

### 3.3 Multi-Paxos（选主优化）

Multi-Paxos 通过选举一个稳定的 Leader 来避免每轮都跑 Prepare 阶段。

```
流程对比：

Basic Paxos（每轮 2 RTT）:
  Client → Proposer   1 RTT
  Prepare/Promise     1 RTT
  Accept/Accepted     1 RTT
  → 写延迟 = 2 RTT

Multi-Paxos（选主后 1 RTT）:
  Phase 1: 选举 Leader（1 轮 Prepare/Promise）
  Phase 2: Leader 直接 Accept（跳过 Prepare）
           → 写延迟 = 1 RTT
           → 除非 Leader 变更，才重新 Phase 1
```

---

## 4. Raft vs Paxos vs ZAB 对比

### 4.1 协议对比表

| 特性 | Basic Paxos | Multi-Paxos | Raft | ZAB |
|------|------------|-------------|------|-----|
| **提出者** | Lamport（1998） | 学术优化 | Ongaro（2013） | 雅虎（ZooKeeper） |
| **核心角色** | Proposer/Acceptor/Learner | 同左 + Leader | Leader/Follower/Candidate | Leader/Follower/Observer |
| **选举机制** | 无固定选主 | Distinguished Proposer | 随机超时 + 投票 | Fast Leader Election |
| **写延迟** | 2 RTT | 1 RTT（稳定后） | 1 RTT | 1 RTT |
| **日志顺序** | 无序 | 有序（Leader保证） | 严格有序 | 严格有序（zxid） |
| **实现复杂度** | 极高（难懂） | 高 | 中（教科书级） | 中高 |
| **安全证明** | 数学完备 | 数学完备 | 操作性描述 | 操作+形式化 |
| **生产使用** | 几乎不用 | Google Chubby | etcd/Consul/TiKV | ZooKeeper |
| **学习门槛** | 🔴 极高 | 🔴 高 | 🟡 中等 | 🟡 中等 |

### 4.2 角色对照

```
共识协议的角色映射：

                Basic Paxos    Raft        ZAB
                ──────────    ─────       ─────
写请求入口        Proposer →   Leader →   Leader
日志存储者        Acceptor →   Follower →  Follower
日志学习者        Learner →   Follower →  Observer
选举时的角色      -           Candidate → LOOKING
```

### 4.3 关键差异

| 维度 | Raft | ZAB | 为什么不同 |
|------|------|-----|-----------|
| Leader 产生 | 随机超时选举 | 比较 (zxid, myid) 最大 | Raft 更随机，ZAB 总是选数据最新的 |
| 日志提交 | Leader 提交后通知 | 过半 ACK 后 Leader 提交 | 语义等价 |
| 成员变更 | Joint Consensus | 滚动重启 | Raft 支持动态成员变更 |
| 读优化 | Read Index/Lease read | Follower 可能读到旧数据 | Raft 有更多优化 |
| 最简实现 | 教学友好 | 面向 ZooKeeper 特殊优化 | 目标不同 |

### 4.4 选型建议

```
┌─────────────────────────────────────────────────────┐
│  场景                   推荐协议        示例产品       │
├─────────────────────────────────────────────────────┤
│  配置中心/服务发现       Raft          etcd/Consul    │
│  分布式协调服务           ZAB          ZooKeeper      │
│  最终一致成员管理         Gossip        Cassandra      │
│  全局锁/元数据管理        Multi-Paxos   Chubby         │
│  强一致 KV 存储          Raft          TiKV            │
│  P2P 消息传播           Gossip        DynamoDB        │
└─────────────────────────────────────────────────────┘
```

---

## 5. Python 代码实现

以下提供三个可运行的 Python 示例代码：

1. [Gossip Gossip 协议模拟](./consensus_demo.py) - 完整的 Push-Pull 模拟
2. [Basic Paxos 核心逻辑](./consensus_demo.py) - Prepare/Promise/Accept/Accepted
3. [Multi-Paxos Leader 优化](./consensus_demo.py) - 选主后的 1RTT 写入

> ⚡ 运行方式：`python memory/learning/consensus_demo.py`
