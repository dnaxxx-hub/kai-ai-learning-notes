# 第9课：云原生

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 什么是云原生

**定义**：充分利用云计算弹性、自动化、分布式的架构风格。

**五大特征**：
1. **容器化** — 应用+依赖打包
2. **微服务** — 单一职责、独立部署
3. **服务网格** — 通信层从应用层剥离
4. **声明式API** — 描述期望状态，系统搞定差异
5. **不可变基础设施** — 不修服务器，直接替换

## 2. 容器技术

### 容器 vs 虚拟机
| 对比 | 容器 | 虚拟机 |
|------|------|--------|
| 内核 | 共享宿主机 | 独立Guest OS |
| 启动 | ms级 | 秒级 |
| 大小 | MB级 | GB级 |
| 隔离 | Namespace+Cgroup | 硬件虚拟化 |
| 密度 | 极高 | 低 |

### 核心原理
```
容器 = Namespace（隔离） + Cgroup（限制） + 联合文件系统（镜像）

       ┌──────────────┐
       │  进程 (PID 1) │
       ├──────────────┤
       │  Namespace   │ ← PID/网络/挂载/UTS独立
       ├──────────────┤
       │  Cgroup      │ ← CPU/内存/IO限制
       ├──────────────┤
       │  OverlayFS   │ ← 分层镜像（只读层+可写层）
       └──────────────┘
```

### Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "server.py"]
```

## 3. Kubernetes核心

### 架构
```
┌──────────────────┐
│  Control Plane   │
│  ┌─────────────┐ │
│  │ API Server  │─│────── etcd (集群状态)
│  │ Scheduler   │ │
│  │ Controller  │ │
│  └─────────────┘ │
└────────┬─────────┘
         │
    ┌────┴────┐
    │  Node1  │    │  Node2  │    │  Node3  │
    │  kubelet│    │  kubelet│    │  kubelet│
    │  Pods   │    │  Pods   │    │  Pods   │
    └─────────┘    └─────────┘    └─────────┘
```

### 核心资源
- **Pod**：最小调度单元（一组容器+共享网络/存储）
- **Service**：Pod的稳定访问入口（ClusterIP/NodePort/LoadBalancer）
- **Deployment**：声明式Pod更新（Rolling Update/Rollback）
- **ConfigMap/Secret**：配置注入
- **PersistentVolume**：持久化存储

### 调度器流程
```
Pod → Filter → 排除不可用Node
   → Score → 给可用Node打分
   → Bind → 绑定到最优Node
   → kubelet → 拉镜像、启动容器
```

## 4. 服务网格（Service Mesh）

### 为什么需要
- 微服务多了，通信逻辑膨胀（重试、超时、熔断、追踪）
- 这些不该每个服务自己实现

### Istio架构
```
Pod A                    Pod B
┌────────────┐          ┌────────────┐
│ 业务容器   │          │ 业务容器   │
└─────┬──────┘          └─────┬──────┘
┌─────┴──────┐          ┌─────┴──────┐
│  Sidecar   │  ◄───►   │  Sidecar   │
│ (Envoy)    │  mTLS    │ (Envoy)    │
└────────────┘          └────────────┘
```

### 功能
- **流量管理**：蓝绿部署、金丝雀发布、流量镜像
- **安全**：mTLS双向认证、RBAC
- **可观测性**：Tracing、Metrics、Logging
- **弹性**：重试、超时、熔断、限流

### 边车（Sidecar）模式
> 给每个Pod注入一个代理容器，接管所有进出流量

## 5. 不可变基础设施

### 传统 vs 不可变
```
传统：
  1. 服务器崩了 → SSH上去修
  2. 修完 → 不知道改了什么
  3. 下次部署 → 手动重复，漏了步骤

不可变：
  1. 服务器崩了 → 直接销毁，从镜像重建
  2. 更新 → 新镜像，滚动替换
  3. 回滚 → 切回旧镜像
```

### 关键理念
- 绝不修改运行中的实例
- 每次变更 = 新版本镜像
- 实例 = 同质化、可替换的

## 6. 配置与密钥管理

### ConfigMap
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DB_HOST: "mysql-service"
  CACHE_TTL: "300"
```

### Secret（Base64编码 + etcd加密）
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
data:
  password: cGFzc3dvcmQxMjM=
```

## 7. 可观测性（Observability）

### Metrics：Prometheus
```
架构：
┌──────────┐   /metrics   ┌────────────┐
│ 业务服务  │ ──────────→ │ Prometheus  │
│ (暴露指标)│              │ Server      │
└──────────┘              └──────┬─────┘
                                 │ Pull
                                 ▼
                          ┌────────────┐
                          │  AlertManager │
                          │ (报警规则)   │
                          └────────────┘
```

**四种指标类型**：
- **Counter**：只增不减（请求总数、错误总数）
- **Gauge**：可增可减（当前连接数、内存使用）
- **Histogram**：分桶统计（请求延迟 P50/P90/P99）
- **Summary**：分位值计算（类似 Histogram 但客户端算）

```yaml
# Prometheus 采集配置
scrape_configs:
  - job_name: 'quant_strategies'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8501', 'localhost:8502']
```

### Logging：Loki + Grafana
```
日志流：
Pod stdout → Promtail → Loki → Grafana
                         │
                    LogQL 查询
                    {app="strategy-engine"} |= "error"
```

### Tracing：OpenTelemetry
```
请求链路：
┌──────────┐     ┌──────────┐     ┌──────────┐
│  客户端   │ ──→ │ 策略引擎  │ ──→ │ 行情服务  │
│ TraceID   │     │ SpanID   │     │ SpanID   │
│ =abc123   │     │ =def456  │     │ =ghi789  │
└──────────┘     └──────────┘     └──────────┘
```

**三大支柱的关系**：
```
一个请求的完整观察：
  1. TraceID = abc123（Tracing）
  2. 该请求耗时 245ms（Metrics，Histogram +1）
  3. 请求日志中包含 abc123（Logging）
→ 从延迟高→找到慢Span→查相关日志→定位根因
```

## 8. GitOps 与持续交付

### GitOps 工作流
```
开发流程：
  1. 修改策略参数 → push 到 git
  2. ArgoCD 检测到 git 变更
  3. 自动同步到 K8s
  4. K8s 滚动更新策略 Pod
  5. 回滚 → revert git → ArgoCD 自动回滚

对比传统：
  传统：ssh到服务器，改文件，重启
  GitOps：改git，系统自动搞定差异
```

### ArgoCD 核心
- **Application**：定义从哪个 git repo 部署到哪个 namespace
- **Sync Policy**：手动/自动同步
- **Sync Phases**：PreSync（数据库迁移）→ Sync（部署）→ PostSync（测试）
- **Rollback**：一键回到任意历史版本

### Helm Chart
```yaml
# quant-strategy/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.strategy.name }}
spec:
  replicas: {{ .Values.strategy.replicas }}
  template:
    spec:
      containers:
      - name: strategy
        image: {{ .Values.image.repository }}:{{ .Values.image.tag }}
        env:
        - name: MA_PERIOD
          value: "{{ .Values.strategy.ma_period }}"
```

```yaml
# values.yaml
strategy:
  name: ma-14-18
  replicas: 2
  ma_period: 14
image:
  repository: registry.quant/strategy-engine
  tag: v1.2.3
```

## 9. 与量化系统的结合（重点）
 
### 现状 vs 云原生目标

| 维度 | 当前系统 (system_bridge.py) | 云原生目标 (K8s) |
|------|----------------------------|-------------------|
| 部署 | Python直接运行在 Windows 上 | Docker镜像 + K8s Pod |
| 扩容 | 手动跑多进程 | HPA自动伸缩 |
| 配置 | 硬编码/本地文件 | ConfigMap热更新 |
| 监控 | 无集中监控 | Prometheus + Grafana |
| 日志 | print到控制台 | Loki集中收集 |
| 容错 | 挂了手动重启 | Deployment自愈 |
| 更新 | 改代码重启 | 滚动更新零停机 |
| 弹性 | 无 | 资源超卖+QoS分级 |

### 容器化量化系统的 Dockerfile

```dockerfile
# 多阶段构建
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /root/.local /root/.local
COPY strategy_v4.py monitor_v3.py backtest_v3.py ./
COPY config/ ./config/
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
EXPOSE 8501
CMD ["python", "strategy_v4.py"]
```

### K8s 部署量化系统

```yaml
# Deployment: 策略引擎
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ma-strategy
  labels:
    app: strategy
    version: v4
spec:
  replicas: 2          # 双副本高可用
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0   # 保证不中断
      maxSurge: 1
  selector:
    matchLabels:
      app: strategy
  template:
    metadata:
      labels:
        app: strategy
    spec:
      containers:
      - name: strategy
        image: quant/strategy:v4
        ports:
        - containerPort: 8501
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:     # 存活检查
          httpGet:
            path: /health
            port: 8501
          initialDelaySeconds: 30
        envFrom:
        - configMapRef:
            name: strategy-config
---
# 自动伸缩 (HPA)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ma-strategy-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ma-strategy
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: strategy_signal_latency_ms
      target:
        type: AverageValue
        averageValue: 100
```

### ConfigMap 热更新策略参数

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: strategy-config
data:
  STRATEGY_CONFIG: |
    {
      "ma_14_18": {
        "fast_ma": 14,
        "slow_ma": 18,
        "position_size": 0.3
      },
      "bollinger_v2": {
        "period": 20,
        "std_dev": 2.0,
        "exit_strategy": "stop_loss"
      }
    }
```

ConfigMap 更新后 K8s 自动挂载新配置（可通过 restartPolicy 自动滚动重启），或者策略进程内监听文件变化实现热加载。

### 架构差距分析

我们当前 system_orchestrator_v2.py + system_bridge.py 的架构在单机上运行得很好，但：

1. **无容器化** — 所有模块在同一进程/环境，依赖冲突无法隔离
2. **无自动扩缩** — 策略增多时只能手动加进程
3. **无健康检查** — 某个模块挂了不影响其他模块，但没人知道它挂了
4. **无声明式配置** — 配置修改后需要重启整个主进程

**云原生化的最小可行步骤**：
1. 先把行情抓取模块（mini_realtime.py）容器化，独立部署
2. 用 ConfigMap 管理策略参数（替代当前 config/active_strategies.json）
3. Prometheus 接入 system_bridge 的指标暴露点
4. 最终全部迁到 K3s（轻量 K8s，适合单机部署）

这正是我们从"好用的量化工具"走向"生产级量化平台"的路线图。
