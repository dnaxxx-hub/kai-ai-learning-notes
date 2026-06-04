# 容器 K8s 运维 — Pod 生命周期 / 资源管理 / 调度 / 集群自治 / 安全

## 一、Pod 生命周期 & 探针

### 生命周期阶段
```
Pending → ContainerCreating → Running → Succeeded/Failed
                ↓ Error/CrashLoopBackOff → BackOff → 重启
```

### 三种探针（Probe）

| 探针 | 作用 | 失败后果 | 使用场景 |
|------|------|----------|----------|
| **livenessProbe** | 是否存活 | `restartPolicy=Always` → 重启容器 | 死锁、内存泄漏 |
| **readinessProbe** | 是否就绪 | 从 Service Endpoints 移除 | 启动慢、依赖未就绪 |
| **startupProbe** | 是否启动成功 | 同 liveness | 启动时间长的应用 |

```yaml
startupProbe:          # 给慢启动应用保护，不限制重试
  httpGet: { path: /health, port: 8080 }
  initialDelaySeconds: 0
  periodSeconds: 10
  failureThreshold: 30  # 5分钟启动时间
livenessProbe:
  httpGet: { path: /health, port: 8080 }
  periodSeconds: 15
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /ready, port: 8080 }
  periodSeconds: 5
```

### Pod 状态排查
- **CrashLoopBackOff** → `kubectl logs` + `kubectl describe pod` 看 Events
- **ImagePullBackOff** → 镜像不存在/拉取凭证错误/网络不通
- **Pending** → `kubectl describe pod` 看 Events，通常是资源不足或 PVC 未绑定
- **Evicted** → 节点资源压力（disk-pressure/memory-pressure）

## 二、资源管理：requests/limits

### 工作原理
- **requests**：调度的依据（保证），CGroup 为该容器预留资源
- **limits**：上限（限制），CGroup 硬限制，超过可能 OOMKill 或 CPU 节流
- **QoS Class**：按 requests/limits 配置分为三类

| QoS 等级 | 条件 | 优先级 | 回收优先级 |
|----------|------|--------|-----------|
| Guaranteed | requests = limits | 最高 | 最后被驱逐 |
| Burstable | requests < limits 且至少一个容器设了 requests | 中 | 其次 |
| BestEffort | 全未设置 | 最低 | 最早被驱逐 |

### OOM 优先级（oom_score_adj）
- Guaranteed：-998（最低 OOM 概率）
- Burstable：2 ~ 999（按内存余量计算）
- BestEffort：1000（最高 OOM 概率）

### CGroup v2 资源控制
- `cpu.max`、`memory.max`、`io.max` 是由 limits 写入的 cgroup 参数
- 内存超限 → OOM Kill（根据 oom_score）
- CPU 超限 → 节流（Throttling），不 kill

## 三、调度策略

### nodeAffinity（节点亲和性）
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: "kubernetes.io/zone"
              operator: In
              values: ["us-east-1"]
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
            - key: "instance-type"
              operator: In
              values: ["c5.large"]
```

### podAffinity / podAntiAffinity（Pod 亲和/反亲和）
```yaml
podAntiAffinity:
  requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchExpressions:
          - key: "app"
            operator: In
            values: ["nginx"]
      topologyKey: "kubernetes.io/hostname"  # 同一节点最多一个
```

### Toleration（容忍度）
```yaml
tolerations:
  - key: "node.kubernetes.io/disk-pressure"
    operator: Exists
    effect: NoSchedule
  - key: "dedicated"
    operator: Equal
    value: "gpu"
    effect: NoSchedule
```

### topologySpreadConstraints（拓扑分布约束）
```yaml
topologySpreadConstraints:
  - topologyKey: "topology.kubernetes.io/zone"
    maxSkew: 1
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: nginx
```

## 四、集群自治：HPA / VPA / Cluster Autoscaler

### HPA（Horizontal Pod Autoscaler）
- 基于 CPU / 内存 / 自定义指标自动扩缩 Pod 数量
- `--horizontal-pod-autoscaler-sync-period`：默认 15s
- **自定义指标**：集成 Prometheus Adapter 自定义 metric

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: nginx-hpa }
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nginx
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```

### VPA（Vertical Pod Autoscaler）
- 自动调整容器的 requests/limits（适合有状态服务）
- **模式**：Auto（自动重启）/ Initial（仅创建时）/ Off（只给建议）

### Cluster Autoscaler
- 不可调度 Pod 出现时，触发扩容 Node
- Node 低利用率时，缩容 Node（需考虑 PDB、Pod 是否可以重新调度）

## 五、安全

### PodSecurityPolicy（→ Pod Security Admission）
- K8s 1.25+ PSP 被删除，改为 Pod Security Standards
- **Privileged**（最低限制）、**Baseline**（中等）、**Restricted**（最严格）

### 网络策略（NetworkPolicy）
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: { name: api-allow }
spec:
  podSelector:
    matchLabels: { app: "api" }
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels: { role: "frontend" }
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels: { app: "database" }
      ports:
        - port: 5432
```

### Seccomp（安全计算模式）
- **RuntimeDefault**：使用容器运行时默认 profile（推荐）
- **Localhost**：自定义 profile
- `securityContext.seccompProfile.type: RuntimeDefault`

### 其他安全实践
- **只读根文件系统**：`readOnlyRootFilesystem: true`
- **放弃 root 运行**：`runAsNonRoot: true`
- **Capabilities 裁剪**：`drop: ["ALL"]` 后按需添加
- **ServiceAccount 最小权限**：每个应用独立 SA，RBAC 最小权限
