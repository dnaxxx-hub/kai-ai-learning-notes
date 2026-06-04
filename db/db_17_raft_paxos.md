# 共识算法：Paxos → Raft → Multi-Raft → 工程实践

## Paxos 简述

- **Basic Paxos**: Proposer → Acceptor → Learner 三角色；Prepare/Promise → Accept/Accepted 两阶段
- **Multi-Paxos**: 引入 Leader 避免活锁；选主后跳过 Prepare 阶段直接 Accept
- **痛点**: 难理解、难实现；Lamport 原论文偏理论，工程落地差异大

## Raft 核心机制

### Leader 选举
- 节点状态: Leader / Follower / Candidate
- 超时机制: Election Timeout (150-300ms 随机)；Leader 心跳保活
- 选票分裂: 同一 Term 每个节点只投一票，获得多数票即当选

### 日志复制
- 客户端请求 → Leader 追加日志 → 并行发送 AppendEntries → 多数确认后提交 → 应用到状态机
- 日志匹配特性: 如果两个节点某 index+term 相同，则之前所有日志一致

### 安全性
- **选举限制**: Candidate 的日志必须至少和多数节点一样新(比较 lastTerm → lastIndex)
- **提交限制**: 当前 Term 的日志才通过"多数确认"直接提交；老 Term 日志通过当前 Term 日志提交间接提交

### Snapshot
- 状态机快照 + 元数据(lastIncludedIndex/Term)；压缩日志释放空间
- InstallSnapshot RPC 处理落后节点追赶

## Multi-Raft

- 多个 Raft Group 并行(如 TiKV 每个 Region 一个 Raft Group)
- 优势: 分片并发、故障域隔离、Leader 分布均衡
- 挑战: 集群成员变更分发、跨 Group 事务需要协调

## 工程源码架构对比

| 特性 | etcd (Go) | Consul (Go) |
|------|-----------|-------------|
| Raft 库 | etcd/raft (自研) | hashicorp/raft |
| 存储 | BoltDB (B-tree) → 现支持 bboltdb | 内存 + 可选 BoltDB |
| 网络层 | gRPC Stream 多路复用 | 自定义 TCP + TLS |
| Snapshot | 定期 + etcdctl 手动触发 | 定时 + follower 自动同步 |
| 集群变更 | Add/Remove Member + Learner 过渡 | Add/Remove + 拆离重连 |
| 线性一致读 | ReadIndex / LeaseRead | ReadIndex |

**etcd 特点**: raft 库可独立使用；PreVote 避免网络分区后 disrupt；Learner 机制平滑扩容

**Consul 特点**: 基于 Serf 做 gossip 组管理；Raft 用于强一致状态(服务注册)，gossip 用于健康探测
