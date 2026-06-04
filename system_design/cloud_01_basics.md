# 云计算基础

## 1. 云服务模型

### IaaS (Infrastructure as a Service)
- **提供**: 计算、网络、存储等基础资源
- **用户管理**: OS、中间件、应用、数据
- **云厂商管理**: 虚拟化、硬件、数据中心
- **代表产品**: AWS EC2, GCP Compute Engine, Azure VM
- **适用**: 需要完全控制基础设施，迁移传统应用

### PaaS (Platform as a Service)
- **提供**: 运行时环境、数据库、中间件
- **用户管理**: 应用代码、数据
- **云厂商管理**: OS、运行时、基础设施
- **代表产品**: AWS Elastic Beanstalk, GCP App Engine, Azure App Service
- **适用**: 专注于应用开发，不想管理底层

### SaaS (Software as a Service)
- **提供**: 完整软件应用
- **用户管理**: 配置、数据
- **云厂商管理**: 一切基础设施和软件
- **代表产品**: Gmail, Office 365, Salesforce
- **适用**: 开箱即用，零运维

### 服务模型对比

| 维度 | IaaS | PaaS | SaaS |
|------|------|------|------|
| 控制力 | 高 | 中 | 低 |
| 运维成本 | 高 | 中 | 低 |
| 灵活性 | 高 | 中 | 低 |
| 部署速度 | 慢 | 中 | 快 |

---

## 2. 虚拟化技术

### KVM (Kernel-based Virtual Machine)
- Linux 内核模块，将 Linux 转为 Type-1 hypervisor
- 基于硬件辅助虚拟化 (Intel VT-x / AMD-V)
- 每个 VM 是一个独立 Linux 进程
- **QEMU**: 提供设备模拟和 I/O 虚拟化

### 虚拟化类型
- **Type-1 (裸机)**: KVM, VMware ESXi, Xen — 直接跑在硬件上
- **Type-2 (托管)**: VirtualBox, VMware Workstation — 跑在 OS 上

### 容器 vs 虚拟机

| 特性 | VM | 容器 |
|------|----|------|
| 隔离级别 | 内核级 | 进程级 |
| 启动时间 | 分钟级 | 秒级 |
| 镜像大小 | GB | MB |
| 资源开销 | 高 (每个 VM 有独立 OS) | 低 (共享宿主机内核) |

---

## 3. VPC / 子网 / 网络基础

### VPC (Virtual Private Cloud)
- 云上的隔离虚拟网络
- 用户可以完全控制 IP 地址范围、路由、网关
- 支持跨可用区部署实现高可用

### 关键组件
- **子网 (Subnet)**: VPC 的 IP 地址范围划分，分公有/私有子网
- **路由表 (Route Table)**: 控制子网流量去向
- **IGW (Internet Gateway)**: 公有子网访问互联网
- **NAT Gateway**: 私有子网访问互联网但不可被外部访问
- **安全组 (Security Group)**: 实例级防火墙，有状态
- **NACL (Network ACL)**: 子网级防火墙，无状态
- **VPC Peering**: 两个 VPC 之间私网互通
- **VPN/专线**: 连接本地数据中心到云

### 经典架构
```
Internet → IGW → Public Subnet (Web/ALB)
                         ↓
              Private Subnet (App Server)
                         ↓
              Private Subnet (RDS Database)
```

---

## 4. 三大云厂商对比

### AWS vs GCP vs Azure

| 维度 | AWS | GCP | Azure |
|------|-----|-----|-------|
| 市场份额 (2024) | ~32% | ~11% | ~23% |
| 核心优势 | 服务最丰富，生态成熟 | 数据分析/AI，K8s原生 | 企业集成，Office 365 |
| 计算 | EC2 | Compute Engine | VM |
| 容器 | ECS/EKS | GKE | AKS |
| 无服务器 | Lambda | Cloud Functions | Azure Functions |
| 对象存储 | S3 | Cloud Storage | Blob Storage |
| 关系数据库 | RDS | Cloud SQL | SQL Database |
| 数据仓库 | Redshift | BigQuery | Synapse |
| AI/ML | SageMaker | Vertex AI | Azure AI |
| K8s | EKS ($0.10/时/集群) | GKE ($0.10/时/集群) | AKS (免费控制面) |
| 全球区域 | 30+ | 40+ | 60+ |
| 计费粒度 | 秒 (1分钟最低) | 秒 (1分钟最低) | 分钟 |

### 选型建议
- **AWS**: 通用首选，服务最全，社区最大
- **GCP**: 数据/AI 场景，K8s 体验最佳
- **Azure**: 微软生态 (.NET, Office 365, Active Directory)
- **阿里云**: 国内合规，中文支持好，性价比高

---

## 5. 部署模型

| 模型 | 描述 | 适用场景 |
|------|------|---------|
| 公有云 | 多租户共享基础设施 | 创业公司、弹性需求 |
| 私有云 | 专有基础设施 | 金融、政府、合规要求 |
| 混合云 | 公有云+私有云互通 | 弹性扩展+数据主权 |
| 多云 | 同时使用多个公有云 | 避免锁定、差异化服务 |

---

## 核心概念速记

| 概念 | 一句话 |
|------|--------|
| **弹性** | 按需扩容缩容，用多少付多少 |
| **可用区 (AZ)** | 物理隔离的数据中心，跨 AZ 部署实现高可用 |
| **区域 (Region)** | 地理区域，包含多个 AZ |
| **水平扩展** | 加机器 → 提升吞吐 |
| **垂直扩展** | 升级机器 → 提升单机性能 |
| **SLA** | 服务等级协议，AWS EC2 通常 99.99% |
| **CAPEX vs OPEX** | 一次性购买 vs 按需付费 |
