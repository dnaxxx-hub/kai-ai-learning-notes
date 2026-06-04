# 云计算实战 — 学习笔记

## 1. 云服务基础模型

### IaaS (Infrastructure as a Service)
- **定义**：提供虚拟化的计算资源（服务器、网络、存储），用户自行管理 OS、中间件、应用
- **类比**：租用整台物理服务器的虚拟版本
- **代表产品**：阿里云 ECS、AWS EC2、GCP Compute Engine
- **用户负责**：操作系统、运行时、应用、数据、网络配置
- **云厂商负责**：物理硬件、虚拟化层、网络基础设施

### PaaS (Platform as a Service)
- **定义**：提供运行时平台（数据库、中间件、开发框架），用户专注代码
- **类比**：租用带预装环境的服务器
- **代表产品**：阿里云 RDS、AWS RDS、Heroku
- **用户负责**：应用代码、数据
- **云厂商负责**：OS、运行时、中间件、硬件

### SaaS (Software as a Service)
- **定义**：开箱即用的完整软件服务
- **类比**：订阅使用软件，无需任何部署
- **代表产品**：阿里邮箱、Salesforce、Google Workspace
- **用户负责**：配置、数据输入
- **云厂商负责**：一切技术层面

## 2. 阿里云核心产品

### ECS (Elastic Compute Service) — 云服务器
- 按需弹性伸缩的虚拟服务器
- 支持多种规格族：通用型 g7/g8、计算型 c7/c8、内存型 r7/r8
- 计费方式：按量付费、包年包月、抢占式实例
- 镜像市场：公共镜像、自定义镜像、共享镜像

### RDS (Relational Database Service) — 关系型数据库
- 支持 MySQL、PostgreSQL、SQL Server、MariaDB
- 自动备份、日志管理、只读实例、灾备
- 规格：按内存/CPU 分级（s2.large, s4.large ...）

### OSS (Object Storage Service) — 对象存储
- 海量、安全、低成本存储
- 存储桶 (Bucket) + 对象 (Object) 模型
- 支持 CDN 加速、跨区域复制、生命周期管理

### SLB (Server Load Balancer) — 负载均衡
- 将流量分发到多台 ECS 实例
- 支持四层（TCP/UDP）和七层（HTTP/HTTPS）负载均衡
- 健康检查、会话保持、SSL 卸载

## 3. AWS 核心产品

### EC2 (Elastic Compute Cloud) — 云服务器
- 等价于阿里云 ECS，功能高度一致
- 实例类型：t（通用突发型）、m（通用型）、c（计算型）、r（内存型）
- AMI（Amazon Machine Image）→ 阿里云镜像

### RDS (Relational Database Service) — 关系型数据库
- 功能与阿里云 RDS 一致
- 额外特性：Multi-AZ 部署、Read Replica

### S3 (Simple Storage Service) — 对象存储
- 等价于阿里云 OSS
- Bucket → Bucket，Object → Object
- 差异化：S3 Glacier（归档存储）、S3 Intelligent-Tiering

### ELB (Elastic Load Balancing) — 负载均衡
- 等价于阿里云 SLB
- 类型：ALB（应用型）、NLB（网络型）、CLB（经典型）

## 4. 安全组和网络配置

### VPC / 专有网络
- 逻辑隔离的私有网络环境
- 关键概念：
  - **CIDR 块** — IP 地址范围（如 10.0.0.0/16）
  - **子网 (Subnet)** — VPC 内的 IP 段划分
  - **路由表** — 控制子网流量
  - **NAT 网关** — 允许私有子网访问公网
  - **Internet 网关** — 公网入口

### 安全组 (Security Group)
- 实例级别的虚拟防火墙
- 规则：方向（入/出）+ 协议（TCP/UDP/ICMP）+ 端口范围 + 源/目标 IP
- **阿里云安全组**：支持 5 元组规则，最多 200 条/组
- **AWS 安全组**：有状态（出站自动允许），最多 60 组/个实例
- 最佳实践：最小权限（仅开放必要端口）

## 5. SSH 密钥管理

### 密钥对机制
- 公钥存放在云服务器的 `~/.ssh/authorized_keys`
- 私钥由用户保管（权限必须为 600）
- 阿里云 / AWS 都支持创建密钥对

### 管理实践
- 每个环境使用独立密钥对
- 定期轮换（推荐每 90 天）
- 私钥加密存储（如 1Password、KMS）
- 禁用密码登录，仅密钥认证

```
ssh-keygen -t ed25519 -C "your_email@example.com"
# 或
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

## 6. 基础设施即代码 (IaC)

### 核心概念
- 用代码定义和管理基础设施（声明式或命令式）
- 版本控制、可审计、可复现
- 消除"雪花服务器"（手动配置漂移）

### IaC 工作流
1. 编写配置文件（YAML / JSON / HCL）
2. 代码评审 + 版本控制
3. 自动化部署（plan → apply）
4. 状态管理（state tracking）
5. 销毁清理（destroy）

## 7. Terraform vs CloudFormation vs ROS

| 特性 | Terraform | AWS CloudFormation | ROS (阿里云) |
|------|-----------|-------------------|-------------|
| 厂商 | HashiCorp | AWS | 阿里云 |
| 多云 | ✅ 支持 | ❌ 仅 AWS | ❌ 仅阿里云 |
| DSL | HCL | YAML/JSON | YAML/JSON |
| 状态管理 | 本地/远程 state | 自动管理 | 自动管理 |
| 开源 | ✅ MPL | ❌ 专有 | ❌ 专有 |
| 模块化 | ✅ Registry | ✅ 嵌套栈 | ✅ 模板复用 |

## 8. CI/CD + 云部署最佳实践

### 云部署流水线
```
代码提交 → 测试 → 构建 → 部署到预发布 → 验收 → 滚动部署到生产
```

### 部署策略
- **蓝绿部署**：维护两套完整环境，切换流量
- **滚动更新**：逐台替换实例
- **金丝雀部署**：先给少量用户，逐步放量

### CI/CD 流水线原则
- 构建产物不可变（为每次构建生成唯一版本号）
- 环境间配置分离（开发/预发布/生产）
- 数据库变更与代码变更分离
- 部署失败自动回滚

## 9. 成本管理

### 计费模式对比

| 模式 | 适用场景 | 节省比例 |
|------|---------|---------|
| 按量付费 | 短周期、突发、测试 | 0%（基准价） |
| 包年包月 | 稳定长期负载 | 15%~50% |
| 预留实例 | 可预测负载 | 最高 72% |
| 抢占式实例 | 容错性好的批处理 | 最高 90% |

### 成本优化策略
- 使用 Auto Scaling 弹性伸缩
- 闲置资源回收不用的实例/EIP/快照
- 存储分层：热数据 → SSD，冷数据 → HDD/归档
- 预留实例 + 按量混用

## 10. 安全最佳实践

### 最小权限原则 (Principle of Least Privilege)
- RAM (阿里云) / IAM (AWS) 角色权限按需分配
- 避免使用 root 账号做日常操作
- 服务间调用使用 RAM 角色而非 AccessKey

### 密钥轮换
- AccessKey 定期轮换（推荐 90 天）
- 同时维护两套密钥（旧 + 新）实现无间断切换
- SSH 密钥对定期更新

### 其他安全措施
- 启用日志审计（ActionTrail / CloudTrail）
- 网络安全：WAF、DDoS 防护
- 数据加密：传输层 TLS、存储层 SSE/KMS
- 定期安全扫描和漏洞修复

---

*学习日期：2026-05-28*
*笔记完成 - 涵盖了跨云部署所需的核心概念*
