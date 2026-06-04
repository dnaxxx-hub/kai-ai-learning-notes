# 云原生架构

> 关联: 见 `cloud_native_04_helm_operator.md` (Helm/Operator) 和 `cloud_native_05_service_mesh.md` (服务网格)

## 1. 12-Factor App

### 背景
Heroku 提出的 12 条云原生应用开发原则，指导构建可弹性伸缩、可移植的 SaaS 应用。

### 12 条法则

| # | 法则 | 要点 | 实践 |
|---|------|------|------|
| 1 | **基准代码 (Codebase)** | 一份代码多环境部署 | Git → 开发/预发布/生产 |
| 2 | **依赖 (Dependencies)** | 显式声明依赖 | requirements.txt, go.mod, package.json |
| 3 | **配置 (Config)** | 配置从代码中分离 | 环境变量, K8s ConfigMap/Secret |
| 4 | **后端服务 (Backing Services)** | 视作附加资源 | 数据库/缓存/MQ 通过 URL 连接 |
| 5 | **构建/发布/运行 (Build/Release/Run)** | 严格分离三阶段 | CI/CD Pipeline, 不可变制品 |
| 6 | **进程 (Processes)** | 无状态进程 | 水平扩展，Session 存外部存储 |
| 7 | **端口绑定 (Port Binding)** | 应用自包含 HTTP 服务 | 不依赖外部 Web 服务器 |
| 8 | **并发 (Concurrency)** | 通过进程模型扩展 | K8s HPA, 多副本 |
| 9 | **易处置 (Disposability)** | 快速启动优雅关闭 | /health 就绪探针, SIGTERM 处理 |
| 10 | **开发/生产一致 (Dev/Prod Parity)** | 环境尽量相同 | 容器化, Docker Compose |
| 11 | **日志 (Logs)** | 事件流, 不写文件 | stdout, 日志采集 (Fluentd/Loki) |
| 12 | **管理进程 (Admin Processes)** | 一次性管理任务 | K8s Job, 数据库迁移 |

### 12-Factor 在 K8s 上的实践
```
1. Codebase   → Git 仓库 (每个应用一个)
3. Config     → ConfigMap + Secret (环境变量)
4. Backing    → Service 资源 (通过 DNS 发现)
6. Processes  → Deployment (无状态), StatefulSet (有状态)
9. Disposable → startupProbe + readinessProbe + preStop hook
11. Logs      → stdout → Fluent Bit → Loki/Elasticsearch
```

---

## 2. 微服务治理

### 核心关注点

| 领域 | 挑战 | 解决方案 |
|------|------|---------|
| **服务发现** | 实例动态变化 | DNS (CoreDNS), 服务注册中心 |
| **负载均衡** | 流量分发 | 客户端 (gRPC LB) / 服务端 (Service) |
| **熔断** | 防止雪崩 | 断路器 (Hystrix/Resilience4j) |
| **重试** | 临时故障 | 带指数退避的重试 |
| **超时** | 防止积压 | 请求超时 + 链路超时 |
| **限流** | 防止打爆 | 令牌桶/漏桶, 限流器 |
| **安全** | 服务间认证 | mTLS, JWT, OAuth2 |
| **容错** | 部分失败 | 舱壁隔离, 优雅降级 |

### Kubernetes 原生治理
```yaml
# Service (服务发现 + 负载均衡)
apiVersion: v1
kind: Service
spec:
  selector:
    app: myapp
  ports:
    - port: 80
      targetPort: 8080
  type: ClusterIP

# HorizontalPodAutoscaler (自动伸缩)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### 微服务框架

| 框架 | 语言 | 特点 |
|------|------|------|
| **Spring Cloud** | Java | 生态最成熟 |
| **Go Kit** | Go | 适合 Go 微服务 |
| **Kratos** | Go | 字节跳动出品 |
| **Dapr** | 多语言 | 基于 Sidecar 的微服务运行时 |
| **Temporal** | 多语言 | 工作流引擎 |

---

## 3. 服务网格

> 详细内容参见 `cloud_native_05_service_mesh.md`

### 核心概念
- **Sidecar Proxy**: 每个 Pod 旁路运行代理 (Envoy)
- **控制面**: 管理 Sidecar 配置 (Istiod/Linkerd-controller)
- **数据面**: 实际的流量代理

### 关键能力
- **mTLS**: 服务间加密通信
- **流量分割**: 金丝雀发布、蓝绿部署
- **超时/重试/熔断**: 微服务韧性
- **观测**: 分布式追踪、指标、日志
- **授权策略**: 服务级访问控制

### Istio vs Linkerd
| 特性 | Istio | Linkerd |
|------|-------|---------|
| 代理 | Envoy (C++) | Linkerd-proxy (Rust) |
| 架构复杂度 | 高 | 低 |
| 资源开销 | 较高 | 较低 |
| 功能丰富度 | 非常丰富 | 够用 |
| 性能 | 稍差 | 更好 |
| 学习曲线 | 陡峭 | 平缓 |
| 社区 | CNCF, Google/Lyft | CNCF, Buoyant |

### 何时引入服务网格
✅ 单语言微服务 → 不需要（用 SDK 更简单）
✅ 多语言异构 → 服务网格优势明显
✅ 已有 Spring Cloud → 保留现有方案
✅ 新项目 K8s 原生 → 可引入 Linkerd（轻量）
✅ 大型组织、合规要求 → Istio

---

## 4. 可观测性 (Observability)

### 三大支柱

```
可观测性 = 日志 (Logs) + 指标 (Metrics) + 追踪 (Traces)
```

### 日志 (Logging)
| 方案 | 特点 |
|------|------|
| **ELK** (Elasticsearch + Logstash + Kibana) | 经典方案，功能强大 |
| **Loki + Grafana** | 轻量，与 Prometheus 集成好 |
| **Fluent Bit / Fluentd** | 日志采集器（推荐 Fluent Bit） |

```yaml
# Fluent Bit DaemonSet 采集 Pod 日志 → Elasticsearch/Loki
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
spec:
  template:
    spec:
      containers:
        - name: fluent-bit
          image: fluent/fluent-bit:latest
```

### 指标 (Metrics)
| 方案 | 特点 |
|------|------|
| **Prometheus** | 云原生事实标准，Pull 模式 |
| **VictoriaMetrics** | Prometheus 兼容，更高性能 |
| **Thanos** | 长期存储 + 全局视图 |
| **Grafana** | 可视化仪表盘 (必配) |

```yaml
# Prometheus Operator ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp
spec:
  selector:
    matchLabels:
      app: myapp
  endpoints:
    - port: metrics
      interval: 30s
```

### 追踪 (Tracing)
| 方案 | 特点 |
|------|------|
| **Jaeger** | CNCF 毕业项目，OpenTelemetry 集成 |
| **Zipkin** | Twitter 开源，较成熟 |
| **Tempo (Grafana)** | 与 Loki/Prometheus 深度集成 |
| **OpenTelemetry** | CNCF 标准，统一 API/SDK |

```go
// OpenTelemetry 集成示例 (Go)
import "go.opentelemetry.io/otel"

tracer := otel.Tracer("my-service")
ctx, span := tracer.Start(ctx, "handle-request")
defer span.End()

// 自动把追踪上下文通过 HTTP header 传播
span.SetAttributes(attribute.String("http.method", r.Method))
```

### 可观测性架构推荐
```
应用日志 → stdout → Fluent Bit → Loki → Grafana
应用指标 → /metrics → Prometheus → Grafana
Tracing → OTel SDK → Jaeger/Tempo → Grafana
告警 → Prometheus AlertManager → PagerDuty/飞书
```

### Golden Signals (四大黄金信号)

| 信号 | 说明 | 典型告警规则 |
|------|------|-------------|
| **延迟 (Latency)** | 请求处理时间 | P99 > 500ms |
| **流量 (Traffic)** | 请求量 | QPS 异常波动 |
| **错误 (Errors)** | 错误率 | HTTP 5xx > 1% |
| **饱和度 (Saturation)** | 资源使用率 | CPU > 80%, 内存 > 85% |

---

## 5. 云原生架构模式

### 常用模式

| 模式 | 描述 | 场景 |
|------|------|------|
| **Sidecar** | 主容器 + 辅助容器 | 日志采集、代理、TLS 终止 |
| **Ambassador** | 代理模式 | 流量管理、认证卸载 |
| **Adapter** | 标准适配器 | 将应用适配到统一接口 |
| **Circuit Breaker** | 断路器 | 防止级联故障 |
| **Bulkhead** | 舱壁隔离 | 限制故障影响范围 |
| **CQRS** | 读写分离 | 读写负载不同场景 |
| **Event Sourcing** | 事件溯源 | 审计、重建状态 |
| **Saga** | 分布式事务 | 跨服务事务一致性 |
| **Strangler Fig** | 绞杀者模式 | 渐进式重构老系统 |

### 云原生成熟度模型

```
Level 1: 上云 (Lift & Shift)
    → 直接把 VM 搬上云，不改变架构

Level 2: 容器化 (Containerization)
    → 应用打包为 Docker，K8s 编排
    → 使用 ConfigMap/Secret 管理配置

Level 3: 微服务化 (Microservices)
    → 单体拆分为微服务
    → 服务发现 + API 网关 + 无状态

Level 4: 平台化 (Platform)
    → 服务网格 + 可观测性
    → GitOps + 自助化部署

Level 5: 自适应 (Autonomous)
    → AI 驱动自动伸缩
    → 混沌工程 + 自愈
    → FinOps 成本优化
```

---

## 6. GitOps 与 CI/CD 流水线

### GitOps 原则
- **声明式**: 期望状态声明在 Git 中
- **不可变性**: 每次部署创建新版本
- **自动同步**: Operator 持续将集群对齐 Git
- **自愈**: 手动修改会被自动回滚

### 工具链
```yaml
Git (声明式配置)
  → Webhook / Polling
    ↓
GitOps Operator (ArgoCD / Flux)
  → Diff 当前状态 vs Git 状态
    ↓
Apply 到 K8s 集群
```

| 工具 | 特点 |
|------|------|
| **ArgoCD** | 最流行，Web UI 好，多集群 |
| **Flux** | 轻量，Weaveworks 出品 |
| **GitLab CI/CD** | 一体化解决方案 |
| **Jenkins X** | Jenkins 的 K8s 原生版本 |

### 推荐工具链
```
代码 → GitHub/GitLab
CICD → GitHub Actions / GitLab CI
镜像仓库 → Docker Hub / ECR / Harbor
GitOps → ArgoCD
部署 → K8s (EKS/GKE/AKS)
监控 → Prometheus + Grafana + Loki/Tempo
```
