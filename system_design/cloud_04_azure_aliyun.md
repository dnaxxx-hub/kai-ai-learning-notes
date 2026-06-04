# Azure / Aliyun — 对比篇

## 1. Azure 核心服务

### Azure VM
- 虚拟机服务，与 AWS EC2 对标
- **尺寸系列**:
  - `B` 系列：爆发型 (Burstable)
  - `D` 系列：通用 (Dsv3/Dv4)
  - `E` 系列：内存优化
  - `F` 系列：计算优化
  - `NC/ND` 系列：GPU 加速
- **可用性集**: 多个故障域+更新域
- **VMSS (VM Scale Set)**: 自动扩缩容
- **Azure Hybrid Benefit**: 自带 Windows Server/SQL 许可

### Blob Storage
- 对象存储，对标 AWS S3
- **层级**: Hot → Cool → Cold → Archive
- **存储类型**:
  - Block Blob：非结构化数据（默认）
  - Append Blob：日志追加
  - Page Blob：VHD 磁盘
- **ADLS Gen2**: Data Lake 存储，兼容 Hadoop

### AKS (Azure Kubernetes Service)
- 托管 K8s
- **特点**: 免费控制面（仅付节点费用）
- Azure Active Directory 集成
- **Virtual Node**: 基于 ACI 的弹性扩缩
- **Azure Policy**: K8s 合规策略

### 其他关键服务
| 服务 | 说明 |
|------|------|
| **Azure Functions** | 无服务器函数 |
| **App Service** | PaaS Web 应用托管 |
| **Cosmos DB** | 全球分布式 NoSQL |
| **Azure SQL Database** | SQL Server 托管 |
| **Logic Apps** | 工作流编排 |
| **Service Bus** | 企业消息队列 |
| **Azure DevOps** | CI/CD + Boards + Repos |

---

## 2. 阿里云核心服务

### ECS (Elastic Compute Service)
- 虚拟机，对标 AWS EC2
- **实例族**:
  - `ecs.g7`：通用型 (第7代)
  - `ecs.c7`：计算型
  - `ecs.r7`：内存型
  - `ecs.i3`：本地 SSD 型
  - `ecs.gpu`：GPU 实例
- **付费方式**: 按量、包年包月、抢占式实例
- **自动快照**: 磁盘快照策略

### OSS (Object Storage Service)
- 对象存储，对标 AWS S3
- **存储层级**: 标准 → 低频 → 归档 → 冷归档
- **特点**:
  - 99.9999999999% 持久性 (12个9)
  - 全球 CDN (CDN 加速)
  - 图片处理（缩略图、水印）
  - 跨区域复制
- **内网免流量**: 同区域 ECS 访问 OSS 免费

### RDS (Relational Database Service)
- **引擎**: MySQL, PostgreSQL, SQL Server, MariaDB, Oracle
- **PolarDB**: 阿里云自研（类似 AWS Aurora）
  - 计算存储分离
  - 最大 100TB
  - 一写多读

### 其他关键服务
| 服务 | 对标 AWS | 说明 |
|------|---------|------|
| **ACK (容器服务)** | EKS | 托管 K8s |
| **SAE (Serverless AE)** | - | 应用托管（免运维） |
| **FC (函数计算)** | Lambda | 无服务器函数 |
| **SLB (负载均衡)** | ELB | L4/L7 负载均衡 |
| **ALB** | ALB | 应用负载均衡 |
| **SLS (日志服务)** | CloudWatch Logs | 日志+查询 |
| **MaxCompute** | Redshift | 大数据计算 |
| **DataWorks** | - | 数据开发平台 |

---

## 3. 三大+阿里云对比总表

### 计算

| 功能 | AWS | GCP | Azure | 阿里云 |
|------|-----|-----|-------|-------|
| 虚拟机 | EC2 | Compute Engine | VM | ECS |
| 无服务器函数 | Lambda | Cloud Functions | Azure Functions | FC |
| 容器服务 | ECS/EKS | GKE | AKS | ACK |
| 无服务器容器 | Fargate | Cloud Run | Container Instances | ECI |
| 自动伸缩 | ASG | MIG | VMSS | ESS |

### 存储

| 功能 | AWS | GCP | Azure | 阿里云 |
|------|-----|-----|-------|-------|
| 对象存储 | S3 | Cloud Storage | Blob Storage | OSS |
| 块存储 | EBS | Persistent Disk | Managed Disk | 云盘 |
| 文件存储 | EFS | Filestore | Azure Files | NAS |
| CDN | CloudFront | Cloud CDN | Azure CDN | CDN |

### 数据库

| 功能 | AWS | GCP | Azure | 阿里云 |
|------|-----|-----|-------|-------|
| 托管 MySQL/PG | RDS | Cloud SQL | Azure DB | RDS |
| 自研兼容 | Aurora | Spanner | Cosmos DB | PolarDB |
| NoSQL | DynamoDB | Firestore | Cosmos DB | TableStore |
| 缓存 | ElastiCache | Memorystore | Redis Cache | Redis(云) |
| 数据仓库 | Redshift | BigQuery | Synapse | MaxCompute |
| 搜索引擎 | OpenSearch | - | - | Elasticsearch |

### 网络

| 功能 | AWS | GCP | Azure | 阿里云 |
|------|-----|-----|-------|-------|
| VPC | VPC | VPC | VNet | VPC |
| 负载均衡 | ALB/NLB | Cloud LB | Azure LB | SLB/ALB |
| DNS | Route53 | Cloud DNS | Azure DNS | DNS |
| VPN | VPN Gateway | Cloud VPN | VPN Gateway | VPN Gateway |
| 专线 | Direct Connect | Interconnect | ExpressRoute | 高速通道 |

### 安全/IAM

| 功能 | AWS | GCP | Azure | 阿里云 |
|------|-----|-----|-------|-------|
| IAM | IAM (User/Role) | IAM (Service Account) | Azure AD | RAM |
| KMS | KMS | Cloud KMS | Key Vault | KMS |
| WAF | WAF | Cloud Armor | WAF | WAF |
| DDoS | Shield | Cloud Armor | DDoS Protection | Anti-DDoS |

---

## 4. 选型建议

### 阿里巴巴/阿里云
- ✅ **国内场景首选**: 合规、数安法、ICP 备案
- ✅ **性价比**: 中国市场竞争激烈，价格低
- ✅ **中文生态**: 文档、社区、技术支持
- ✅ **企业级**: 钉钉、企业应用集成
- ❌ 海外节点较少，国际体验不如前三

### Azure
- ✅ **企业客户**: 与 Active Directory、Office 365 深度集成
- ✅ **混合云**: Azure Arc, Azure Stack
- ✅ **.NET/C# 生态**: 原生支持最好
- ✅ **合规认证**: 最多合规证书
- ❌ 服务命名混乱，管理界面复杂

### 选型速查

| 你的场景 | 推荐云 |
|----------|--------|
| 国内公司，国内用户 | **阿里云** |
| 国内外企，.NET 栈 | **Azure** |
| 全球 SaaS，新项目 | **AWS** |
| 数据分析/AI/ML | **GCP** |
| K8s 深度使用 | **GCP GKE** |
| 创业公司（成本敏感） | **AWS (免费套餐) → 阿里云(国内)** |
| 多云战略 | **AWS + GCP** 或 **Azure + 阿里云** |

---

## 5. 云服务等价表 (速查)

```
AWS EC2     = GCP Compute Engine = Azure VM      = 阿里云 ECS
AWS S3      = GCP Cloud Storage  = Azure Blob     = 阿里云 OSS
AWS Lambda  = GCP Cloud Functions = Azure Functions = 阿里云 FC
AWS RDS     = GCP Cloud SQL      = Azure DB       = 阿里云 RDS
AWS EKS     = GCP GKE            = Azure AKS      = 阿里云 ACK
AWS SQS     = GCP Pub/Sub        = Azure Queue    = 阿里云 MNS
AWS ELB     = GCP Cloud LB       = Azure LB       = 阿里云 SLB
AWS Route53 = GCP Cloud DNS      = Azure DNS      = 阿里云 DNS
AWS IAM     = GCP IAM            = Azure AD       = 阿里云 RAM
AWS KMS     = GCP Cloud KMS      = Azure Key Vault = 阿里云 KMS
```
