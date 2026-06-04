# K8s/云原生 #8：监控、日志与可观测性

> 2026-05-17
> 前置：Helm、Operator #7

## 1. 可观测性的三个支柱

```
Metrics（指标）     — K8s 暴露什么数据
Logs（日志）        — 应用在做什么
Traces（追踪）      — 请求经过哪些服务
```

K8s 本身提供指标（kube-state-metrics），不提供日志和追踪——需要外部工具。

## 2. Metrics：Prometheus 生态

### 2.1 架构

```
应用 Pod          K8s 组件           系统
  ┌──────┐      ┌──────────┐      ┌──────────┐
  │ App  │      │kube-state│      │ node-    │
  │/metrics ├──┼─│-metrics  ├──┼──│ exporter ├──
  └──────┘      └──────────┘      └──────────┘
        │              │                │
        └──────────────┴────────────────┘
                     │
              ┌──────▼──────┐
              │ Prometheus  │ (拉模式)
              │   Server    │
              └──────┬──────┘
                     │ Alertmanager → Slack/Email/PagerDuty
                     │
              ┌──────▼──────┐
              │  Grafana    │
              │  Dashboard  │
              └─────────────┘
```

### 2.2 核心指标

**K8s 组件指标**（kube-state-metrics）：

```promql
# 不可用 Pod 数量
kube_deployment_status_replicas_unavailable{namespace="production"}

# 节点 CPU/内存使用率
1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes

# Pod CPU/内存
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (pod)
sum(container_memory_working_set_bytes{container!=""}) by (pod)
```

**应用指标**（Prometheus 客户端库）：

```go
// Go 示例
var httpRequests = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total HTTP requests",
    },
    []string{"method", "path", "status"},
)

// Rust 示例 (metrics crate)
use metrics::{counter, histogram};

counter!("http_requests_total", "method" => "GET", "path" => "/api");
histogram!("request_duration_seconds", 0.125, "method" => "GET");
```

### 2.3 告警规则

```yaml
# prometheus-alert-rules.yaml
groups:
- name: k8s-critical
  rules:
  - alert: PodCrashLooping
    expr: rate(kube_pod_container_status_restarts_total[5m]) > 1
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Pod {{ $labels.pod }} 频繁重启"
  - alert: NodeNotReady
    expr: kube_node_status_condition{condition="Ready",status="true"} == 0
    for: 5m
    labels:
      severity: critical
  - alert: DiskSpaceLow
    expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} < 0.1
    for: 5m
    labels:
      severity: warning
```

### 2.4 自定义指标 HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: custom-metrics-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: my-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: 1000
```

## 3. Logs：日志收集方案

### 3.1 标准模式

```
Pod                    Node                    Cluster
┌──────────┐          ┌──────────┐          ┌──────────┐
│ App 容器  │ → stdout │ fluentd  │          │          │
│          │          │ (Daemon- │ → Kafka → │ Elastic- │
│ Sidecar  │ → 文件    │  Set)    │          │  search   │
└──────────┘          └──────────┘          └──────────┘
                                               ↓
                                            Kibana
```

### 3.2 日志方案对比

| 方案 | 存组件 | 优点 | 缺点 |
|------|--------|------|------|
| **EFK** | Elasticsearch + Fluentd + Kibana | 成熟/搜索强 | 资源消耗大 |
| **Loki** | Loki + Promtail + Grafana | 轻量/K8s 原生 | 搜索不如 ES |
| **PLG** | Promtail + Loki + Grafana | 同 Loki | 同 Loki |
| **DataDog** | 商业 + Agent | 开箱即用 | 贵 |

**Loki 的优势**：标签索引（不全文索引日志内容），存储成本低，与 Prometheus 同一个 Grafana。

### 3.3 结构化日志最佳实践

```go
// ❌ 不好
log.Printf("User %s logged in from %s", user, ip)

// ✅ 好（JSON 结构化，k8s 标签友好）
log.WithFields(log.Fields{
    "user": user,
    "ip":   ip,
    "action": "login",
}).Info("user_login")
```

结构化日志的好处：
- 在 Loki/Grafana 中直接用标签过滤
- 方便自动关联 Trace ID
- 自动序列化后容易做分析

## 4. Pod 排障工具

### 4.1 kubectl 调试命令

```bash
# 基础
kubectl describe pod <name>         # 查看事件和条件
kubectl logs <pod> [-c container]   # 查看容器日志
kubectl logs --previous             # 查看上次崩溃的日志

# 进阶
kubectl exec -it <pod> -- /bin/sh   # 进入容器
kubectl top pod                     # 实时资源使用
kubectl top node                    # 节点资源

# 端口转发（本地调试）
kubectl port-forward pod/my-pod 8080:80

# 临时调试 Pod
kubectl debug my-pod -it --image=busybox --target=my-container
```

### 4.2 Pod 状态排障流程

```
Pending
  ├── 资源不足（CPU/Memory/GPU）
  ├── PVC 未绑定
  ├── nodeSelector / affinity 不匹配
  └── ImagePullBackOff

CrashLoopBackOff
  ├── 应用启动配置错误
  ├── 探针配置太严格（initialDelaySeconds 不够）
  └── Secret/ConfigMap 缺少

ImagePullBackOff
  ├── 镜像名/标签不存在
  ├── 私有仓库认证失败（imagePullSecrets）
  └── 镜像拉取超时

OOMKilled
  └── 内存限制过小

RunContainerError
  └── 存储卷挂载失败 / 端口冲突
```

### 4.3 k9s（终端 UI 排障）

```bash
k9s                            # 启动 TUI
:pod                           # 查看 Pod
:namespace prod                # 切换到 prod 命名空间
/error                         # 搜索 error
ctrl+d                         # 查看选中资源详情
ctrl+l                         # 查看日志
```

k9s 是 K8s 排障效率最高的 CLI 工具——比 kubectl describe 快 10x。

## 5. 可观测性工具对比

| 工具 | 类型 | 特点 |
|------|------|------|
| kube-state-metrics | 监控 | K8s 原生指标 |
| node-exporter | 监控 | 节点指标（CPU/Mem/Disk/Net）|
| cAdvisor | 监控 | 容器资源（内建在 kubelet）|
| metrics-server | 监控 | 实时资源（HPA 需要）|
| Prometheus | 监控+告警 | 拉模式 TSDB |
| Grafana | 可视化 | 仪表盘 + Loki + Alert |
| Loki | 日志 | 轻量标签索引 |
| Jaeger / Tempo | 追踪 | 分布式追踪 |
| OpenTelemetry | 规范 | 统一的 Metrics + Logs + Traces API |

## 6. HPA（自动扩缩容）

### 6.1 基于 CPU/Memory

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nginx-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx
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

### 6.2 VPA（垂直扩缩容）

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: nginx-vpa
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind: Deployment
    name: nginx
  updatePolicy:
    updateMode: "Auto"    # Auto / Initial / Off
  resourcePolicy:
    containerPolicies:
    - containerName: '*'
      minAllowed:
        cpu: 100m
        memory: 128Mi
      maxAllowed:
        cpu: "2"
        memory: 4Gi
```

## 总结

```
可观测性三角：
  指标（Prometheus）— 发生了什么
  日志（Loki/EFK）  — 为什么发生
  追踪（Jaeger）    — 请求走了哪

自动扩缩容：
  HPA — 水平扩容（加 Pod，适合无状态）
  VPA — 垂直扩容（加资源，适合有状态）
  CA  — 集群扩缩（加节点）
```
