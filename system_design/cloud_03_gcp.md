# GCP 核心服务

## 1. 计算 — Compute Engine

### Compute Engine
- GCP 的虚拟机服务
- **机器类型**:
  - `e2` 系列：经济型 (E2-micro 免费)
  - `n2/n2d` 系列：通用 (N2 Standard/Highmem/Highcpu)
  - `c2/c2d/c3` 系列：计算优化
  - `m1/m2/m3` 系列：内存优化
  - `a2/g2` 系列：GPU/加速器

### 关键特性
- **自定义机器类型**：按需调整 vCPU 和内存（1:1 到 1:8）
- **Live Migration**：平台维护时自动迁移 VM（不重启）
- **Sole-tenant Nodes**：专用物理服务器
- **Preemptible VM**：类似 AWS Spot，24小时最大，最高 80% 折扣
- **OS Login**：SSH 密钥管理
- **Instance Template + Managed Instance Group**: 自动扩缩容

### 与 AWS EC2 对比
| 维度 | EC2 | Compute Engine |
|------|-----|---------------|
| 机器类型 | 预定义族 | 预定义+自定义 |
| 磁盘 | EBS (独立卷) | Persistent Disk (独立) / Local SSD |
| 网络 | ENA (100Gbps) | gVNIC (100Gbps) |
| 免费层级 | 750h t2.micro | 744h f1-micro |

---

## 2. 存储 — Cloud Storage

### Cloud Storage
- 对象存储，与 S3 对等服务
- **存储类别**:

| 类别 | 用途 | 最小存储 | 检索费 |
|------|------|---------|--------|
| Standard | 热数据，频繁访问 | 无 | 无 |
| Nearline | 30天以上访问一次 | 30天 | 有 |
| Coldline | 90天以上访问一次 | 90天 | 有 |
| Archive | 365天以上 | 365天 | 最高 |
| Autoclass | 自动按访问切换 | - | - |

### 关键能力
- **统一命名空间**: 全局唯一 Bucket 名
- **对象版本控制**: 同 S3 Versioning
- **对象生命周期管理**: 自动迁移到冷存储
- **Object Change Notification**: 通过 Pub/Sub 通知变更
- **Signed URL**: 临时访问
- **gcloud CLI**: 强大的命令行工具
- **gsutil**: 类似 aws cli

### 与 S3 区别
| 特性 | S3 | Cloud Storage |
|------|----|--------------|
| 一致性 | 强一致 (新) | 强一致 |
| 全局视图 | 所有 Bucket | 项目级 |
| IAM 集成 | 资源级+策略 | 组织/项目级 |
| 传输加速 | S3 Transfer Acceleration | gcloud storage |

---

## 3. 数据库 — Cloud SQL

### Cloud SQL
- 托管关系数据库：MySQL, PostgreSQL, SQL Server
- **核心功能**:
  - 自动备份与时间点恢复 (PITR)
  - 高可用（跨区故障切换）
  - 读副本（同区域/跨区域）
  - 自动存储扩容
  - Cloud SQL Auth Proxy（安全连接）

### Cloud Spanner
- 全球分布的关系数据库
- 强一致 + 水平扩展（突破传统 RDBMS 瓶颈）
- 适合全球化业务（如 游戏、金融、SaaS）

### Bigtable
- 宽列 NoSQL 数据库
- 适合：时序数据、IoT、广告技术
- 托管 HBase 兼容

### Firestore
- 文档型 NoSQL（类似 MongoDB）
- 移动端、实时应用
- 自动扩缩容

### 选择指南

| 场景 | 推荐 |
|------|------|
| 传统 Web | Cloud SQL (MySQL/PG) |
| 全球强一致 | Cloud Spanner |
| 移动/实时 | Firestore |
| 时序/大规模 | Bigtable |
| 数据仓库/分析 | BigQuery |

---

## 4. 无服务器 — Cloud Run

### Cloud Run
- 托管容器运行时（完全无服务器）
- **核心特点**:
  - 任意容器镜像（支持任何语言）
  - 自动从 0 到 N 伸缩
  - 按请求计费（无请求不收费）
  - 自带 HTTPS + 自定义域名
  - 支持 GPU
  - 最慢 60 分钟超时

### Cloud Functions
- 与 Lambda 对标，函数即服务
- **v1 (Gen1)**: 基于 GCE，较慢冷启动
- **v2 (Gen2)**: 基于 Cloud Run，改进冷启动
- 支持：HTTP, Pub/Sub, Storage, Firestore 触发

### App Engine
- PaaS 先行者
- **Standard Environment**: 沙盒运行，快速伸缩
- **Flexible Environment**: 容器运行，更灵活

### Cloud Run vs Lambda
| 维度 | Lambda | Cloud Run |
|------|--------|-----------|
| 运行形态 | 函数 | 容器 |
| 冷启动 | 3-500ms (VPC更慢) | 快 (Go/Node) |
| 端口 | 无 | HTTP 端口 |
| 部署 | zip 上传 | 任何容器镜像 |
| 超时 | 15分钟 | 60分钟 |
| 请求并发 | 可配并发 | 单容器可并发 |

---

## 5. VPC 网络

### GCP VPC 特性
- **全局 VPC**: GCP VPC 是全局资源，子网可以跨区域（而 AWS VPC 是区域级）
- **子网模式**:
  - 自动模式：每个区域自动创建子网
  - 自定义模式：手动控制
- **Cloud NAT**: 私有实例访问互联网
- **Cloud Router**: 动态路由（BGP）用于 VPN/互连
- **Cloud Load Balancing**:
  - 全球 HTTP(S) LB: 单 Anycast IP 全球分发
  - 区域内部/外部 LB

### 与 AWS VPC 区别

| 特性 | AWS VPC | GCP VPC |
|------|---------|---------|
| 范围 | 区域级 | 全局级 |
| 子网 | 区域+AZ绑定 | 区域级，跨AZ |
| 默认网络 | 无 | 有（auto mode） |
| 防火墙 | 安全组+NACL | 防火墙规则（分布式） |
| 负载均衡 | 区域 | 全球+区域 |

---

## 6. GKE (Google Kubernetes Engine)

### GKE 优势
- K8s 的诞生地，K8s 原生体验最好
- **Autopilot 模式**: 全托管，只需部署 Pod
- **Standard 模式**: 管理节点池
- 自动升级、自动修复
- 整合 Cloud Logging + Cloud Monitoring
- **Workload Identity**: K8s SA ↔ GCP IAM
- **GKE Dataplane V2**: eBPF 网络

---

## 7. 选型速查

| 需求 | AWS | GCP |
|------|-----|-----|
| 虚拟机 | EC2 | Compute Engine |
| K8s | EKS | GKE (更优) |
| 对象存储 | S3 | Cloud Storage |
| 云函数 | Lambda | Cloud Functions/Cloud Run |
| 数据库 | RDS | Cloud SQL |
| 数据仓库 | Redshift | BigQuery (更优) |
| 消息队列 | SQS | Pub/Sub (更优) |
| CDN | CloudFront | Cloud CDN |
| AI/ML | SageMaker | Vertex AI (更优) |

> 📌 **一句话**: AWS 服务最全，GCP 在 K8s、数据、AI 领域突出。选择 GCP 的核心理由是：BigQuery + GKE + Cloud Run + Vertex AI。
