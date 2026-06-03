# 第2课：分布式存储

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 存储系统分层

```
应用层
    ↓
文件系统层（POSIX/NFS）
    ↓
块存储层（本地盘/云盘/iSCSI）
    ↓
物理层（HDD/SSD/NVMe）
```

分布式存储的关键问题：
- **分片**：数据分散到多台机器
- **复制**：多副本保证可靠性
- **一致性**：副本间数据一致

## 2. GFS（Google File System）

### 架构
```
Client ←→ Master（元数据服务器）
    ↓
Chunk Server 1 — Chunk Server 2 — ... — Chunk Server N
```

- **Master**：存储元数据（文件名→chunk映射、chunk位置），管理租约
- **Chunk Server**：存实际数据，每个chunk 64MB，默认3副本
- **Client**：先从Master拿元数据，直接和Chunk Server交互

### 关键设计
- **大chunk（64MB）**：减少元数据量，降低Master负载
- **写一次读多次**：追加写为主，不做随机写
- **租约机制**：Master将写入权委托给主副本，减少Master瓶颈
- **快照+日志**：Master元数据持久化

### 读流程
1. Client请求Master：文件名+chunk索引
2. Master返回chunk handle + 副本位置
3. Client缓存元数据，直接和最近的Chunk Server通信
4. Chunk Server返回数据

### 写流程
1. Client从Master获取主副本位置
2. 数据沿副本链推送（流水线）
3. 主副本确认，所有副本写入
4. 主副本返回Client

## 3. HDFS（Hadoop Distributed File System）

GFS的开源实现，核心组件：

- **NameNode**（对应GFS Master）
- **DataNode**（对应GFS Chunk Server）
- **Secondary NameNode**：合并FsImage+EditLog（不是热备）

### HDFS vs GFS
| 特性 | GFS | HDFS |
|------|-----|------|
| Chunk大小 | 64MB | 默认128MB |
| 副本数 | 3（可配置） | 3（可配置） |
| 默认写入模型 | 追加写 | 追加写 |
| 一致性模型 | 宽松 | 宽松 |
| 元数据 | 内存+日志 | 内存+FsImage + EditLog |

## 4. Ceph

统一分布式存储系统，支持块/文件/对象三种接口。

### RADOS（Reliable Autonomic Distributed Object Store）
Ceph底层核心：去中心化的对象存储。

- **CRUSH算法**：无中心化元数据查询，直接计算数据位置
- **PG（Placement Group）**：对象的逻辑分组
- **OSD（Object Storage Daemon）**：每块硬盘一个OSD

### CRUSH vs 中心化元数据
```
GFS/HDFS: Client → Master(NameNode) → "文件在哪？" → 返回位置
Ceph:     Client → CRUSH(文件ID, 集群拓扑) → "计算位置" → 直接访问
```

**CRUSH优势**：无单点瓶颈，扩容时数据自动重分布

### Ceph三接口
- **RADOS GW**（对象存储）：S3/Swift兼容
- **RBD**（块存储）：给虚拟机用
- **CephFS**（文件系统）：POSIX兼容

## 5. 对象存储 vs 块存储 vs 文件存储

| 类型 | 接口 | 典型场景 | 代表产品 |
|------|------|---------|---------|
| 块存储 | iSCSI/FC | 数据库、虚拟机盘 | AWS EBS、Ceph RBD |
| 文件存储 | NFS/SMB | 共享目录、HPC | AWS EFS、CephFS |
| 对象存储 | S3/HTTP | 媒体文件、备份/归档 | AWS S3、Ceph RGW、MinIO |

### 对象存储特点
- Key-Value：bucket + object key
- 扁平命名空间（无目录树）
- HTTP API访问
- 高可扩展（EB级别）
- 最终一致性

## 6. 核心原理

### 数据分片策略
| 策略 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| 范围分片 | 按Key范围分 | 范围查询快 | 热点倾斜 |
| 哈希分片 | Key哈希取模 | 数据均匀 | 范围查询差 |
| 一致性哈希 | 虚拟节点环 | 增减节点影响小 | 实现复杂 |

### 复制策略
- **同步复制**：全部确认才返回（强一致，延迟高）
- **异步复制**：本地确认就返回（最终一致，延迟低）
- **Quorum**：R + W > N（可调一致性和可用性）

### CAP在存储中的应用
- **HDFS NameNode**: CP（NameNode挂则系统不可用）
- **DynamoDB/Cassandra**: AP（允许读旧数据）
- **Google Spanner**: CP（TrueTime时钟实现强一致）
