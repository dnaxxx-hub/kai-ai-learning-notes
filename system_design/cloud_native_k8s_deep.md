# Kubernetes 深度学习笔记

## 一、Kubernetes 整体架构

### 1.1 控制平面（Control Plane）

控制平面是 K8s 集群的"大脑"，负责全局决策和集群状态管理。

| 组件 | 职责 | 关键要点 |
|------|------|----------|
| **API Server** | 所有组件交互的入口 | RESTful API；etcd 的唯一访问者；认证/授权/准入控制；watch 机制 |
| **Scheduler** | Pod 调度决策 | 过滤（Predicates）→ 打分（Priorities）→ 绑定（Bind）|
| **Controller Manager** | 集群状态调节 | 多个控制器循环：Node、Replication、Endpoint、ServiceAccount 等 |
| **etcd** | 集群状态存储 | 分布式键值存储；Raft 一致性协议；所有数据的来源 |

**API Server 工作流**：
```
用户/客户端 → 认证 → 授权(RBAC/ABAC) → 准入控制(Mutating/Validating) → 验证 → etcd 存储
```

### 1.2 工作节点（Worker Node）

| 组件 | 职责 |
|------|------|
| **kubelet** | 节点代理，管理 Pod 生命周期（CRI 接口） |
| **kube-proxy** | 网络代理，维护节点 iptables/IPVS 规则，实现 Service 负载均衡 |
| **容器运行时** | 实际运行容器（containerd / CRI-O / Docker） |

**Pod 创建流程**：
```
kubectl apply → API Server → etcd → Scheduler 调度 → 
API Server 更新 → kubelet 感知 → CRI 创建容器 → 
CNI 分配网络 → CSI 挂载存储
```

---

## 二、Pod 调度策略

### 2.1 核心调度流程

```
Scheduler 循环:
1. 从队列中取出待调度 Pod
2. 过滤阶段 (Predicates): 筛选可用节点
3. 打分阶段 (Priorities): 对候选节点排序
4. 选择最优节点
5. 绑定 (Bind): 写入调度决策到 API Server
```

### 2.2 过滤策略（Predicates）

- **资源足够**: Pod 请求 ≤ 节点可用资源
- **端口不冲突**: HostPort 未占用
- **污点容忍**: Pod 容忍节点的所有 Taints
- **节点选择器**: Pod 的 nodeSelector 匹配节点标签
- **亲和性**: 满足 nodeAffinity 规则
- **Volume 冲突**: 节点满足 PV 挂载要求

### 2.3 打分策略（Priorities）

- **资源均衡**: 所有资源维度最均衡的节点得分高
- **亲和性偏好**: 接近 preferredDuringScheduling 的目标
- **污点容忍度**: 容忍越多节点得分越高
- **Inter-pod 反亲和**: 分散同类型 Pod

### 2.4 污点与容忍（Taints & Tolerations）

```
NoSchedule: 不调度新的 Pod
PreferNoSchedule: 尽量避免调度
NoExecute: 立即驱逐已有 Pod（除非容忍）
```

### 2.5 亲和与反亲和

```
nodeAffinity: Pod 倾向/必须部署到特定节点
podAffinity: Pod 倾向/必须和同类 Pod 在一起
podAntiAffinity: Pod 倾向/必须和同类 Pod 分开
```

---

## 三、工作负载（Workloads）

### 3.1 Deployment — 无状态应用

| 特性 | 说明 |
|------|------|
| 副本管理 | ReplicaSet 管理 Pod 数量 |
| 滚动更新 | maxSurge + maxUnavailable 控制更新速率 |
| 回滚 | Revision 历史，kubectl rollout undo |
| 暂停/恢复 | 金丝雀发布 |

**滚动更新策略**:
```
maxSurge: 超出期望副本数的最大值（百分比或绝对数）
maxUnavailable: 更新期间不可用的最大 Pod 数（百分比或绝对数）

算法: 先启动新 Pod，等 Ready 后逐步删除旧 Pod
```

### 3.2 StatefulSet — 有状态应用

- 稳定的网络标识（Pod Name + Headless Service）
- 稳定的持久化存储（PVC 模板）
- 有序部署/删除（0 → N-1）
- 有序滚动更新

**使用场景**: 数据库、消息队列、ZooKeeper、Etcd

### 3.3 DaemonSet — 每个节点一个实例

- 每个符合条件的节点运行一个 Pod
- 节点加入集群时自动创建
- 滚动更新策略：onDelete / RollingUpdate

**使用场景**: 日志采集（Fluentd）、监控代理（Prometheus Node Exporter）、CNI 插件

### 3.4 Job / CronJob — 批处理

```
Job:
  - 执行一次性任务
  - completions: 完成的 Pod 数量
  - parallelism: 并行度
  - backoffLimit: 重试次数

CronJob:
  - 定时调度 Job
  - 标准 Cron 表达式
  - concurrencyPolicy: Allow/Forbid/Replace
```

---

## 四、Service & 网络

### 4.1 Service 类型

| 类型 | 访问方式 | 典型场景 |
|------|----------|----------|
| **ClusterIP** | 集群内虚拟 IP | 内部微服务通信 |
| **NodePort** | 节点 IP + 端口 | 外部简单访问、测试 |
| **LoadBalancer** | 云厂商 LB | 对外提供公有云服务 |
| **ExternalName** | CNAME 到外部 DNS | 访问外部服务 |

**Service 工作流**:
```
用户 → Service(ClusterIP:Port) → Endpoints/Pod IP → Pod
    ↑                      ↑
  kube-proxy           Endpoint Controller
  (iptables/IPVS)      (维护 Endpoint 列表)
```

### 4.2 Ingress — 七层路由

- 基于 Host 和 Path 路由
- TLS 终止
- 限流、白名单等高级策略（依赖 Ingress Controller 实现）

**常用 Ingress Controller**:
- NGINX Ingress Controller（最广泛）
- Traefik
- HAProxy
- Istio Gateway

### 4.3 CNI 网络模型

**核心要求**:
1. 每个 Pod 有唯一的 IP 地址
2. Pod 之间可以直接通信（无需 NAT）
3. Node 之间可以直接通信

| CNI 插件 | 特点 |
|----------|------|
| **Flannel** | 简单 Overlay（VXLAN），性能一般 |
| **Calico** | BGP 路由 + iptables 网络策略，性能好 |
| **Cilium** | eBPF 技术，性能最佳，功能最丰富 |

### 4.4 Service Mesh（边车模式）

```
Pod
┌─────────────────────┐
│  App Container      │
│  Service Mesh Proxy │ ← 边车 (sidecar)
└─────────────────────┘
```

**核心能力**:
- 流量管理：灰度发布、流量分割
- 可观测性：调用链追踪、指标、日志
- 安全：mTLS 加密通信、RBAC
- 故障注入、超时重试

| 方案 | 特点 |
|------|------|
| **Istio** | 功能最全面，Envoy 代理 |
| **Linkerd** | 轻量级，Rust 实现 |
| **Consul Connect** | HashiCorp 生态 |

---

## 五、存储

### 5.1 PV / PVC 模型

```
动态供给流程:
StorageClass(provisioner) → PVC 请求 → 自动创建 PV → PV 绑定 PVC → Pod 使用
```

**PV 访问模式**:
- ReadWriteOnce (RWO) — 单节点读写
- ReadOnlyMany (ROX) — 多节点只读
- ReadWriteMany (RWX) — 多节点读写

### 5.2 StorageClass 动态供给

```yaml
# 存储类定义
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  fsType: ext4
reclaimPolicy: Retain  # 或 Delete
allowVolumeExpansion: true
```

---

## 六、配置管理

### 6.1 ConfigMap & Secret

| 对比 | ConfigMap | Secret |
|------|-----------|--------|
| 存储内容 | 非敏感配置 | 敏感信息（密码、Token） |
| 编码 | 明文 | Base64（但建议用外部 KMS 加密）|
| 注入方式 | 环境变量 / 挂载卷 | 环境变量 / 挂载卷 |

**最佳实践**:
- 使用 `envFrom` 注入大量配置
- Secret 使用外部系统管理（Vault / Sealed Secrets / SOPS）

---

## 七、Helm — Kubernetes 包管理

**核心概念**:
```
Chart: 应用包（模板 + values.yaml 配置）
Repository: Chart 仓库
Release: Chart 部署后的实例
```

**常用操作**:
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm search repo nginx
helm install my-nginx bitnami/nginx -f values.yaml
helm upgrade my-nginx bitnami/nginx --set replicaCount=3
helm rollback my-nginx 1
```

---

## 八、监控体系

### 8.1 Prometheus + Grafana

```
Pod → Metrics API → Prometheus → AlertManager → 告警通知
                      ↓
                   Grafana (可视化仪表盘)
```

**关键指标**:
- 资源使用率: CPU / 内存 / 磁盘 / 网络
- Kubernetes 指标: Pod 状态、Node 健康、API 延迟
- 应用指标: HPA 指标、QPS、错误率

**ServiceMonitor** (Prometheus Operator):
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: app-monitor
spec:
  selector:
    matchLabels:
      app: my-app
  endpoints:
  - port: metrics
    interval: 15s
```

### 8.2 告警规则示例
```yaml
- alert: PodCrashLooping
  expr: rate(kube_pod_container_status_restarts_total[5m]) > 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Pod {{ $labels.pod }} 持续重启"
```

---

## 九、日志体系

### 9.1 EFK (Elasticsearch + Fluentd + Kibana)

```
Pod (stdout/stderr) → Fluentd DaemonSet → Elasticsearch → Kibana
                                              ↑
                                       structured JSON logs
```

### 9.2 Loki (Grafana 生态)
```
Pod → Promtail DaemonSet → Loki → Grafana (Explore)
```

**Loki 优势**: 不索引日志内容，只索引标签，存储成本低。

---

## 十、云原生 CI/CD

### 10.1 GitOps (ArgoCD)

**核心思想**: Git 仓库是状态的唯一真实来源。

```
Git Repo (期望状态)
  ↓ Auto/Poll Sync
ArgoCD
  ↓ Diff + Apply
Kubernetes Cluster (实际状态)
  ↓ Auto-Heal (如果偏差)
回写到 Git Repo (仅 Drift Detection)
```

**关键概念**:
- Application: 一个 Git Repo → K8s 集群的映射
- Sync Policy: Manual / Automated
- Sync Status: Synced / OutOfSync
- Health Status: Healthy / Degraded / Progressing

### 10.2 Tekton — 云原生 CI

- Task: 执行单元（一系列 Step）
- Pipeline: Task 的有向无环图
- PipelineRun: Pipeline 的实际执行
- TaskRun: Task 的实际执行

---

## 十一、成本优化

### 11.1 资源预留策略

| 服务质量 | CPU/内存 | 特性 |
|----------|----------|------|
| **Guaranteed** | Limits == Requests | 最高优先级，永不驱逐 |
| **Burstable** | Requests < Limits | 可超卖，低优先级 |
| **BestEffort** | 无 Requests/Limits | 最低优先级，最先驱逐 |

### 11.2 HPA (Horizontal Pod Autoscaler)

```yaml
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
        averageUtilization: 80
```

### 11.3 Spot 实例

- 成本降低 60-90%
- 使用 `PodDisruptionBudget` 保障稳定性
- 使用 `Cluster Autoscaler` 自动替换

---

## 十二、生产运维

### 12.1 证书管理 (Cert Manager)

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
spec:
  secretName: tls-secret
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - myapp.example.com
```

### 12.2 备份恢复 (Velero)

```bash
# 备份
velero backup create daily-backup --include-namespaces production

# 恢复
velero restore create --from-backup daily-backup

# 调度
velero schedule create daily --schedule="0 1 * * *" \
  --include-namespaces production --ttl 24h
```

### 12.3 升级策略

| 策略 | 说明 |
|------|------|
| **Rolling Update** | 逐节点驱逐 + 新版本加入 |
| **Blue-Green** | 完整新集群 + 切换流量 |
| **Canary** | 小比例流量到新版本 |

**升级检查清单**:
1. etcd 备份
2. 节点镜像预拉取
3. PodDisruptionBudget 配置
4. 监控告警确认正常
5. 分批次升级（control plane → worker nodes）

---

## 十三、总结：云原生运维心法

1. **声明式优先**: 所有状态 Git 管理，拒绝手工操作
2. **可观测性**: 监控 + 日志 + 追踪三件套缺一不可
3. **容错设计**: 预期故障，使用 PDB、AntiAffinity、多副本
4. **渐进式变更**: 滚动更新、金丝雀、灰度发布
5. **自动化一切**: HPA、Cluster Autoscaler、GitOps 自动同步
6. **安全默认**: NetworkPolicy、PodSecurity、加密通信
7. **成本意识**: 资源 Request/Limit 设置、Spot 实例利用
