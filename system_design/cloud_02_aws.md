# AWS 核心服务

## 1. 计算 — EC2

### EC2 (Elastic Compute Cloud)
- 核心：虚拟服务器，按需创建
- **实例类型族**:
  - `t` 系列：burstable (t2/t3/t4g) — 适合开发/低负载
  - `m` 系列：通用 (m5/m6g/m7g)
  - `c` 系列：计算优化 (c5/c6g) — 批处理/游戏
  - `r/x` 系列：内存优化 (r5/x2) — 数据库/缓存
  - `i/d` 系列：存储优化 (i3/d3) — 日志/数仓

### 购买模式
| 模式 | 折扣 | 特点 |
|------|------|------|
| **按需 (On-Demand)** | 0% | 灵活，无承诺 |
| **预留 (Reserved 1-3年)** | 30-60% | 稳定负载，预付 |
| **竞价 (Spot)** | 70-90% | 可中断应用，批处理 |
| **Savings Plans** | 30-60% | 灵活预留($/时承诺) |
| **专用主机** | - | 合规/BYOL |

### AMI (Amazon Machine Image)
- 预配置模板：OS + 软件
- 支持自建 / AWS Marketplace / 社区
- 跨区域复制需要先共享再复制

### 关键特性
- **User Data**: 启动时运行脚本
- **EBS 卷**: 持久化块存储，支持快照
- **ENI (弹性网卡)**: 附加多个网卡/IP
- **安全组**: 实例级防火墙
- **Instance Metadata**: 169.254.169.254

---

## 2. 存储 — S3

### S3 (Simple Storage Service)
- 对象存储，无限容量，99.999999999% 持久性 (11个9)
- **存储层级** (从热到冷):

| 层级 | 成本 | 检索 | 最小存储 |
|------|------|------|---------|
| Standard | 高 | 即时 | 无 |
| Infrequent Access (IA) | 中 | 即时 | 30天 |
| One Zone-IA | 中低 | 即时 | 30天 |
| Glacier Instant Retrieval | 较低 | 毫秒 | 90天 |
| Glacier Flexible Retrieval | 低 | 1-5分钟-12小时 | 90天 |
| Glacier Deep Archive | 最低 | 12-48小时 | 180天 |
| Intelligent-Tiering | 自动 | 按访问自动调整 | 30天 |

### S3 关键概念
- **Bucket**: 全局唯一命名，存储容器
- **Object**: 文件（最大 5TB）
- **Key**: 对象标识符（路径）
- **Versioning**: 多版本保留
- **Replication**: CRR（跨区域）/ SRR（同区域）
- **Presigned URL**: 临时访问链接
- **Static Website Hosting**: 托管静态网站
- **S3 Select**: SQL 过滤对象内数据

### 安全
- **ACL**: 对象/Bucket 级别权限
- **Bucket Policy**: JSON 策略
- **IAM Policy**: 用户/角色策略
- **Block Public Access**: 全局禁止公开访问
- **默认加密 (SSE-S3/KMS/C)**
- **MFA Delete**: 删除需要 MFA

---

## 3. 数据库 — RDS

### RDS (Relational Database Service)
- **引擎**: MySQL, PostgreSQL, MariaDB, Oracle, SQL Server, Aurora
- **核心功能**:
  - 自动备份（7-35天保留）
  - Multi-AZ（同步备库，故障自动切换）
  - Read Replica（异步只读副本，跨区域）
  - 自动扩缩容（Storage Auto Scaling）
  - 自动补丁与维护窗口

### Aurora — AWS 自研数据库
- 兼容 MySQL/PostgreSQL
- 存储自动扩展到 128TB
- 6副本跨 3个 AZ
- 写性能 3倍 MySQL，读性能 6倍
- **Serverless v2**: 自动伸缩，按 ACU 计费

### 对比

| 场景 | 推荐 |
|------|------|
| Web 应用 | RDS MySQL/PostgreSQL |
| 企业 SQL Server | RDS SQL Server |
| 高吞吐 OLTP | Aurora |
| NoSQL 缓存 | ElastiCache (Redis/Memcached) |
| NoSQL 文档 | DynamoDB |
| 数据仓库 | Redshift |

---

## 4. 无服务器 — Lambda

### AWS Lambda
- 运行代码无需管理服务器
- **触发器**: S3, API Gateway, SQS, DynamoDB Streams, EventBridge...
- **限制**: 15分钟超时, 10GB 内存, 50MB 部署包(/tmp 512MB)
- **支持语言**: Python, Node.js, Java, Go, .NET, Ruby, Rust
- **计费**: 请求数(每百万$0.20) + 执行时间(GB-秒)
- **冷启动**: VPC 内启用 ENI 附加造成延迟 (~1-5s)

### 最佳实践
- 最小化部署包大小
- 使用环境变量（非代码硬编码）
- 开启 Reserved Concurrency 防止打爆
- 使用 Powertools 增强可观测性
- VPC Lambda 需要 NAT 才能访问互联网

---

## 5. 负载均衡 — ELB

### ELB (Elastic Load Balancing)

| 类型 | 层级 | 特点 |
|------|------|------|
| **ALB (Application)** | L7 | HTTP/HTTPS/gRPC，基于路径/主机路由，WAF集成 |
| **NLB (Network)** | L4 | TCP/UDP/TLS，极低延迟，静态IP |
| **CLB (Classic)** | L4/L7 | 旧版，不推荐新使用 |

### ALB 核心特性
- **目标组 (Target Group)**: EC2, Lambda, IP, ECS
- **监听器规则**: 按路径(/api/*)、主机头(api.example.com)、查询参数
- **加权路由**: 蓝绿部署、金丝雀发布
- **粘性会话**: 基于 Cookie
- **Connection Draining**: 优雅关闭

---

## 6. DNS — Route53

### Route 53
- **托管 DNS**: 域名解析服务
- **路由策略**:

| 策略 | 用途 |
|------|------|
| 简单 (Simple) | 单记录，随机返回 IP |
| 加权 (Weighted) | 按权重分配流量 |
| 延迟 (Latency) | 路由到延迟最低的区域 |
| 故障转移 (Failover) | 主备切换，配合健康检查 |
| 地理位置 (Geolocation) | 按用户位置路由 |
| 地理接近 (Geoproximity) | 按位置+偏置路由 |
| 多值 (Multivalue) | 随机返回多个健康记录 |

- **健康检查**: 关联 ALB/IP/Endpoint
- **Alias 记录**: 路由到 AWS 资源（免费）
- **DNSSEC**: 域名安全扩展

---

## 7. 架构选型速查

| 场景 | 推荐架构 |
|------|---------|
| **Web应用** | Route53 → CloudFront → ALB → ECS/Fargate → RDS → ElastiCache |
| **无服务器API** | Route53 → CloudFront → API Gateway → Lambda → DynamoDB |
| **静态网站** | Route53 → CloudFront → S3 |
| **微服务** | Route53 → ALB (多个Target Group) → ECS/EKS → RDS Aurora |
| **批处理** | S3 → SQS → Lambda/EC2 Spot |
| **视频处理** | S3 → MediaConvert → S3 + CloudFront |
| **CI/CD** | CodeCommit → CodeBuild → CodeDeploy → CodePipeline |

---

## 关键术语

| 术语 | 说明 |
|------|------|
| **ARN** | Amazon Resource Name，资源唯一标识 |
| **CloudFormation** | IaC (基础设施即代码) |
| **CloudWatch** | 监控、日志、告警 |
| **IAM** | 身份与访问管理 |
| **KMS** | 密钥管理服务 |
| **VPC Endpoint** | 私网访问 AWS 服务 |
| **Terraform + AWS** | 实际最常用的 IaC 组合 |
