# Serverless 无服务器架构

## 1. 什么是 Serverless

### 核心理念
- **无服务器 ≠ 没有服务器** → 开发者不关心服务器
- 自动扩缩容（从 0 到无穷）
- 按实际使用计费（无请求=免费）
- 运维由云厂商负责

### Serverless 的两种形态
1. **FaaS (Function as a Service)**: 函数级
2. **BaaS (Backend as a Service)**: 托管后端服务

---

## 2. 主流 FaaS 产品

### AWS Lambda
| 特性 | 值 |
|------|-----|
| 运行时 | Python, Node.js, Java, Go, .NET, Ruby, Rust |
| 内存 | 128MB - 10GB |
| 超时 | 最多 15 分钟 |
| 临时磁盘 | /tmp 512MB - 10GB |
| 并发 | 每区域 1000 (可提额) |
| 冷启动 | ~200ms (Node/Python), ~1-5s (VPC/Java) |
| 计费 | 请求 ($0.20/百万) + 执行时间 ($0.0000166667/GB-s) |
| 免费套餐 | 100万请求/月 |

### GCP Cloud Functions
| 特性 | 值 |
|------|-----|
| 运行时 | Node.js, Python, Go, Java, .NET, Ruby, PHP |
| 内存 | 128MB - 32GB |
| 超时 | 9分钟 (Gen1) / 60分钟 (Gen2) |
| 并发 | 1/实例 → Gen2 支持多并发 |
| 免费套餐 | 200万请求/月 |

### Azure Functions
| 特性 | 值 |
|------|-----|
| 运行时 | C#, JavaScript, Python, Java, PowerShell |
| 计划 | Consumption / Premium / Dedicated |
| 超时 | 10分钟 (Consumption) / 无限 (Premium/Dedicated) |
| 免费套餐 | 100万请求/月 |

### 阿里云 FC (函数计算)
| 特性 | 值 |
|------|-----|
| 运行时 | Node.js, Python, Java, Go, .NET, PHP |
| 内存 | 128MB - 3GB |
| 超时 | 10分钟 (最大) |
| 弹性 | 按需实例 + 预留实例 |
| 免费套餐 | 100万次调用/月 |

---

## 3. 无服务器容器

### AWS Fargate
- ECS/EKS 的无服务器计算引擎
- 不需要管理节点/集群
- 按任务定义 CPU/内存（0.25 vCPU - 16 vCPU）
- 按秒计费，最少 1 分钟
- **与 Lambda 区别**:
  - Fargate = 长时间运行的容器
  - Lambda = 短时间运行的函数

### GCP Cloud Run
- 无服务器容器平台
- 从 Docker 镜像直接部署
- 自动 HTTPS + 域名
- 按请求 + CPU/内存计费
- **冷启动时间**: Go/Node <100ms, Java/Python ~200-500ms

### 对比 Fargate vs Cloud Run

| 特性 | Fargate | Cloud Run |
|------|---------|-----------|
| 复杂程度 | 需要 ECS/EKS 配置 | 极简，一键部署 |
| 启动速度 | 秒级 | 更快 |
| 请求驱动 | 否（一直运行） | 是（空闲缩到 0） |
| 最长运行 | 无限制 | 60分钟 |
| 并发 | 单任务单请求 | 单容器多并发 |
| 计费 | 按运行时间 | 按请求+CPU时间 |

---

## 4. 架构对比

### Lambda (事件驱动)

```
API Gateway → Lambda → DynamoDB
     ↓
S3 Bucket → Lambda → SNS → Email
     ↓
SQS → Lambda → RDS
```

### Cloud Run (请求驱动)

```
Cloud LB → Cloud Run (容器) → Cloud SQL
     ↓
Pub/Sub → Cloud Run (处理) → BigQuery
```

---

## 5. 冷启动问题

### 冷启动原因
- 新实例分配资源
- 下载代码/镜像
- 初始化运行时
- VPC ENI 附加 (最慢)

### 缓解方案

| 方案 | 效果 | 成本 |
|------|------|------|
| **预热 (Provisioned Concurrency)** | 最有效 | 付费（始终运行） |
| **最小化部署包** | 减少 50-200ms | 无 |
| **GraalVM (Java)** | 大幅减少 Java 冷启动 | 开发成本 |
| **SnapStart (Lambda+Java)** | 冷启动 <200ms | 无 |
| **Cloud Run min-instances** | 保留 N 个热实例 | 按闲置付费 |
| **函数代码优化** | 延迟加载依赖 | 无 |

---

## 6. 选型指南

### 什么时候用 Lambda/Cloud Functions？

✅ **适合**
- 事件响应（文件上传、消息处理）
- API 端点（轻量 CRUD）
- ETL / 数据转换
- Webhook 处理
- 定时任务 (Cron)
- 异步处理 / 消息消费

❌ **不适合**
- 长时间运行的任务 (>15/10分钟)
- 高并发 VPC 数据库连接
- WebSocket 长连接
- 状态保持（有状态服务）
- GPU 训练任务

### 什么时候用 Cloud Run/Fargate？

✅ **适合**
- Web 应用 / REST API
- 迁移现有容器应用
- 需要自定义运行时的场景
- 需要 gRPC / WebSocket
- 需要 GPU / 特殊硬件

### 决策树

```
需要运行代码？
├── 代码逻辑简单、事件触发 → FaaS (Lambda/CF/Azure功能)
├── 需要长时间运行 → 容器
│   ├── 需要 K8s 生态 → Fargate (EKS)
│   └── 简单部署 → Cloud Run
└── 需要自定义运行时/端口 → Cloud Run / Fargate
```

---

## 7. Serverless 最佳实践

### 架构模式
- **事件驱动**: Lambda 作为事件处理中枢
- **Fan-out**: 一个事件触发多个下游
- **Pipe**: 数据通过多个函数链式处理
- **Valve**: 用 SQS/SNS 做缓冲和背压

### 安全
- 最小权限 IAM 角色
- 加密环境变量
- VPC 私有部署 + NAT
- 输入验证 (防止注入)

### 可观测性
- 结构化日志 (JSON)
- 分布式追踪 (X-Ray / Cloud Trace)
- 自定义指标 (冷启动计数、延迟分位)
- 报警：错误率 > 1%, P99 延迟 > 3s

---

## 8. 三大平台函数对比速查

```python
# Lambda
def lambda_handler(event, context):
    return {"statusCode": 200, "body": "Hello"}

# Cloud Functions (Python)
def hello_http(request):
    return "Hello"

# Azure Functions
# def main(req: func.HttpRequest) -> func.HttpResponse:
#     return func.HttpResponse("Hello")
```

### 部署对比

| 步骤 | Lambda | Cloud Functions | Azure Functions |
|------|--------|----------------|----------------|
| 打包 | zip | zip | zip/csproj |
| CLI | aws lambda update-function-code | gcloud functions deploy | func azure functionapp publish |
| IaC | SAM/Serverless/CDK | Deployment Manager | ARM/Bicep |
| 本地调试 | SAM CLI | Functions Framework | func start |
| 日志 | CloudWatch | Cloud Logging | App Insights |
