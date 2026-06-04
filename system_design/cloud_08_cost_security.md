# 云计算成本与安全

## 1. 成本优化 (FinOps)

### FinOps 模型

```
阶段1: 可见 (Inform)
  → 成本可视化、标签、预算

阶段2: 优化 (Optimize)
  → 选择合适的购买模式和资源

阶段3: 运营 (Operate)
  → 持续治理、自动化、文化
```

### 计算成本优化

#### 预留/承诺使用
| 云 | 产品 | 折扣 | 期限 | 说明 |
|---|------|------|------|------|
| AWS | Reserved Instances | 30-60% | 1/3年 | 指定实例族/区域 |
| AWS | Savings Plans | 30-60% | 1/3年 | 灵活的 $/时承诺 |
| GCP | Committed Use Discounts | 30-57% | 1/3年 | vCPU+内存，灵活 |
| GCP | Sustained Use Discounts | 20-30% | 自动 | 月度使用自动 |
| Azure | Reserved VM Instances | 30-60% | 1/3年 | 实例大小灵活 |
| 阿里云 | 包年包月 | 50-70% | 1/3/5年 | 预付越多折扣越大 |

#### 竞价/抢占/Spot 实例

| 特性 | AWS Spot | GCP Preemptible | Azure Spot | 阿里云抢占式 |
|------|----------|----------------|------------|-------------|
| 折扣 | 60-90% | 60-80% | 60-80% | 50-80% |
| 中断通知 | 2分钟 | 30秒 | 30秒 | 5分钟 |
| 最长运行 | 无 | 24小时 | 无 | 无 |
| 适合 | 批处理/无状态/容错 | 批处理/容器 | 批处理/Dev | 批处理/Dev |

#### 自动伸缩 (Auto Scaling)
```yaml
# 不要过度配置 → 用 HPA/VPA
# 使用 Spot 实例作为工作节点
# 设置 min/max 边界防止失控
```

### 存储成本优化

| 策略 | 效果 |
|------|------|
| 生命周期管理 | 冷数据自动迁移到低成本层级 |
| 删除未使用 EBS/云盘 | 避免空盘持续计费 |
| S3 Intelligent-Tiering | 自动匹配最优层级 |
| CDN (CloudFront) | 减少源站请求 |
| 压缩/去重 | 减少存储量 |

### 网络成本优化
- **跨 AZ 流量收费**: 尽量将同一应用的组件放在同一 AZ
- **NAT Gateway 收费高**: 考虑使用 VPC Endpoint 或公网 IP
- **数据传输收费**: 入口免费，出口收费，用 CDN 降低
- **AWS Data Transfer**: $0.09/GB 出口 → 选择指定区域低成本

### 避免浪费的 Checklist
- [ ] 删除未关联的 EBS 卷 / IP 地址 / Load Balancer
- [ ] 停止非生产环境的实例下班后关闭
- [ ] 使用 Instance Scheduler 自动启停
- [ ] 设置 Budget 告警
- [ ] 使用标签 (Tag) 进行成本归因
- [ ] 清理未使用的快照和镜像
- [ ] 监控闲置实例（CPU < 5% 持续一周）
- [ ] 使用 Rightsizing 推荐调整实例规格

---

## 2. IAM 策略

### 最小权限原则

> **一个实体只拥有完成其任务所需的最少权限**

### AWS IAM

#### 核心概念
- **User**: 个人身份
- **Group**: 用户集合，统一分配权限
- **Role**: 临时权限，供服务/用户扮演
- **Policy**: JSON 权限文档
- **Principal**: 策略应用的主体

#### 策略示例

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::myapp-bucket",
                "arn:aws:s3:::myapp-bucket/*"
            ]
        }
    ]
}
```

#### 安全最佳实践
- ✅ 根用户启用 MFA，不用
- ✅ 使用 IAM Role 而不是长期密钥
- ✅ 为每个应用创建独立 Service Account
- ✅ 使用权限边界 (Permissions Boundary)
- ✅ 定期轮换 Access Key（90天）
- ❌ 不要在代码中硬编码 Access Key
- ❌ 不要在 S3 Bucket Policy 中使用通配符 Principal

### GCP IAM

#### 核心概念
- **Policy**: 绑定 Role 到 Member
- **Role**: 权限集合（Primitive/Predefined/Custom）
- **Member**: user/group/serviceAccount/domain
- **Organization/Project/Resource 层级**

```yaml
# GCP IAM Policy 示例
members:
  - user:alice@example.com
  - serviceAccount:my-sa@project.iam.gserviceaccount.com
role: roles/storage.objectViewer
```

#### GCP IAM 最佳实践
- 使用 Service Account 而非用户密钥
- 使用 Workload Identity 将 K8s SA 映射到 GCP SA
- 组织级策略限制项目创建者

### Azure RBAC

- **Role Definition**: 权限列表（内置/自定义）
- **Scope**: Management Group → Subscription → Resource Group → Resource
- **Built-in Roles**: Owner, Contributor, Reader, User Access Administrator

### 阿里云 RAM

- **User**: 子账号
- **Role**: 跨账号/服务授权
- **Policy**: 系统策略 + 自定义策略
- **默认**: Root 账号不用于日常操作

---

## 3. 安全组 / WAF / 网络安全

### 安全组 (Security Group)

| 特性 | 说明 |
|------|------|
| 作用 | 实例级有状态防火墙 |
| 状态 | **有状态**（返回流量自动允许） |
| 规则 | 仅允许规则（Deny All 隐式） |
| 关联 | 附加到 ENI / 实例 |

#### 最佳实践
```yaml
# 最小化开放端口
HTTP:  0.0.0.0/0 → 80
HTTPS: 0.0.0.0/0 → 443
SSH:   <办公IP> → 22
DB:    <App-SG> → 3306 (MySQL)
```

### NACL (Network ACL)
| 特性 | 说明 |
|------|------|
| 作用 | 子网级无状态防火墙 |
| 状态 | **无状态**（需同时配置入站和出站规则） |
| 规则 | 允许 + 拒绝（按编号顺序评估） |
| 适用 | 子网级别额外保护层 |

### WAF (Web Application Firewall)

| 云 | 产品 | 特点 |
|---|------|------|
| AWS | WAF | 关联 ALB/CloudFront/API Gateway |
| GCP | Cloud Armor | 关联 Cloud LB |
| Azure | WAF | 关联 Application Gateway/Front Door |
| 阿里云 | WAF | 支持云原生+CNAME接入 |

#### WAF 防护能力
- **SQL 注入** & **XSS**: 默认规则
- **IP 黑/白名单**: 来源 IP 过滤
- **地理限制**: 按国家/区域控制
- **速率限制**: 防 DDoS / CC 攻击
- **自定义规则**: 匹配 URI/Header/Body
- **OWASP Top 10**: 可启用托管规则集
- **机器人管理**: 识别爬虫/Bot

### DDoS 防护

| 云 | 免费防护 | 付费增强 |
|---|---------|---------|
| AWS | AWS Shield Standard | Shield Advanced ($3000/月) |
| GCP | Cloud Armor 基础 | Cloud Armor Managed Protection |
| Azure | Azure DDoS 基础 | DDoS Protection Standard |
| 阿里云 | Anti-DDoS Basic | Anti-DDoS Pro |

---

## 4. 云安全最佳实践

### 身份与访问管理

| 实践 | 说明 |
|------|------|
| ✅ 启用 MFA | 所有管理员和 Root 用户 |
| ✅ 最小权限 | IAM 策略仅授予必需权限 |
| ✅ 定期审计 | IAM 凭证报告、CloudTrail 审计 |
| ❌ 共享密钥 | 每个服务/人独立密钥 |
| ✅ 临时凭证 | 使用 STS/Role 而非长期 AK |
| ✅ 权限边界 | 防止权限提升 |

### 数据加密

```
静态加密 (At Rest)
  └── EBS/S3/RDS → SSE-S3/KMS/C
  └── 使用 KMS 管理密钥

传输加密 (In Transit)
  └── HTTPS/TLS 1.2+
  └── 内部通信 mTLS (服务网格)
```

### 基础设施安全

```yaml
网络层:
  - VPC 隔离: 公/私有子网分离
  - 安全组: 最小端口开放
  - NACL: 子网级额外保护
  - VPC Flow Logs: 流量审计
  - PrivateLink/VPC Endpoint: 私网访问

主机层:
  - AMI 安全基线: CIS Benchmark
  - 定期安全补丁
  - 主机入侵检测 (CrowdStrike/Wazuh)
  - 最小化安装包

容器层:
  - 镜像扫描 (Trivy/Clair)
  - 不可变镜像: 不在运行中修补
  - 只读文件系统
  - Pod Security Standards (Restricted)
  - Seccomp/AppArmor 限制系统调用
```

### 监控与合规

| 工具 | AWS | GCP | Azure | 阿里云 |
|------|-----|-----|-------|-------|
| 审计日志 | CloudTrail | Cloud Audit Logs | Azure Monitor | ActionTrail |
| 合规扫描 | Config / Security Hub | Security Command Center | Defender for Cloud | 安全中心 |
| 密钥管理 | KMS | Cloud KMS | Key Vault | KMS |
| 机密管理 | Secrets Manager | Secret Manager | Key Vault | KMS(凭据) |

### 事件响应

```yaml
1. 识别 (Identify)
   ├── CloudTrail 异常检测
   └── GuardDuty / Security Hub 告警

2. 评估 (Assess)
   ├── 确定影响范围和类型
   └── 确认是否有数据泄露

3. 遏制 (Contain)
   ├── 隔离受影响的 EC2/容器
   └── 撤销泄露的密钥

4. 清除 (Eradicate)
   ├── 重建资源（不可变）
   └── 轮换所有相关密钥

5. 恢复 (Recover)
   ├── 从备份恢复
   └── 验证修复

6. 复盘 (Post-mortem)
   ├── Root Cause Analysis
   └── 更新安全策略
```

---

## 5. 合规框架

| 框架 | 区域 | 适用 |
|------|------|------|
| **SOC 2** | 全球 | SaaS / 数据处理 |
| **ISO 27001** | 全球 | 信息安全管理系统 |
| **PCI DSS** | 全球 | 支付/信用卡 |
| **HIPAA** | 美国 | 医疗健康 |
| **GDPR** | 欧盟 | 数据隐私 |
| **等保 2.0** | 中国 | 网络安全等级保护 |
| **GDPR** | 欧盟 | 个人数据保护 |

### 云厂商合规工具
- **AWS**: Artifact (合规报告), Audit Manager
- **GCP**: Assured Workloads
- **Azure**: Azure Policy, Compliance Manager
- **阿里云**: 合规中心

---

## 6. 成本 + 安全 = 架构平衡

### 不要过度优化
```
过度省钱 → 单点故障 → 业务中断 → 损失 > 节省
过度安全 → 复杂度高 → 开发效率低 → 交付慢
```

### 生产环境最低配置
- ✅ 跨 AZ 部署（至少 2 个）
- ✅ 数据库 Multi-AZ
- ✅ 备份策略（RPO < 1小时）
- ✅ 安全组最小开放
- ✅ 日志审计
- ✅ 成本预算告警（$XXX/月上限）
