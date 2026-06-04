# K8s/云原生 #6：RBAC、命名空间与多租户

> 2026-05-17
> 前置：存储与 ConfigMap #5

## 1. 多集群 vs 多命名空间

```
单集群多 Namespace：K8s 推荐的方式
多集群：按环境/团队/合规划分
```

| | 单集群多 Namespace | 多集群 |
|---|-------------------|--------|
| 资源利用率 | ✅ 共享 | ❌ 各集群空闲浪费 |
| 管理开销 | ✅ 统一控制面 | ❌ 每个集群独立管理 |
| 隔离性 | ❌ RBAC+NetworkPolicy 逻辑隔离 | ✅ 物理隔离 |
| 合规性 | ❌ 可能跨边界 | ✅ 独立合规域 |
| 灾难恢复 | ❌ 共享 etcd | ✅ 各自故障域 |

**典型组织方案**（按环境隔离）：

```
集群: prod（生产）
├── Namespace: api
├── Namespace: web
├── Namespace: data
└── Namespace: monitoring

集群: staging（预发布）
├── Namespace: api
└── Namespace: web

集群: dev（开发，可共享）
└── Namespace: team-a, team-b, team-c
```

## 2. Namespace 隔离机制

### 2.1 可见性

```bash
kubectl get pods                        # 当前 Namespace（default）
kubectl get pods -n kube-system         # 指定 Namespace
kubectl get pods --all-namespaces       # 所有 Namespace
```

- Pod/Service/ConfigMap/Secret → **Namespace 范围**
- Node/PV/StorageClass → **集群范围**
- ClusterRole → **集群范围**
- Role → **Namespace 范围**

### 2.2 资源配额（ResourceQuota）

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "4"
    requests.memory: "8Gi"
    limits.cpu: "8"
    limits.memory: "16Gi"
    pods: "10"
    services: "5"
    persistentvolumeclaims: "3"
    configmaps: "10"
```

超出配额时拒绝创建（不会驱逐已有资源）。

### 2.3 LimitRange（默认资源限制）

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: team-a
spec:
  limits:
  - max:                                 # Pod 最大限制
      cpu: "2"
      memory: "2Gi"
    min:                                 # Pod 最小需求
      cpu: "50m"
      memory: "64Mi"
    default:                             # 未设 limits 时默认
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:                      # 未设 requests 时默认
      cpu: "100m"
      memory: "128Mi"
    type: Container
```

## 3. RBAC

### 3.1 核心概念

```
Subject（谁）→ Role/ClusterRole（能做什么）→ RoleBinding/ClusterRoleBinding（绑定）
```

| 资源 | 范围 | 说明 |
|------|------|------|
| ServiceAccount（SA） | Namespace | Pod 运行身份 |
| Role | Namespace | 资源的权限规则 |
| ClusterRole | 集群 | 跨 Namespace / 集群级别的权限 |
| RoleBinding | Namespace | 绑定 Subject 到 Role/ClusterRole |
| ClusterRoleBinding | 集群 | 绑定 Subject 到 ClusterRole |

### 3.2 ServiceAccount

Pod 默认使用 `default` 的 SA（权限极低）。

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api-sa
  namespace: api
---
apiVersion: v1
kind: Pod
metadata:
  name: api-pod
spec:
  serviceAccountName: api-sa     # 指定 SA
  containers:
  - name: app
    image: my-api
```

SA 对应的 Secret Token 自动挂载到容器的 `/var/run/secrets/kubernetes.io/serviceaccount/`。

### 3.3 Role 定义

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: api
  name: pod-reader
rules:
- apiGroups: [""]          # 空=核心 API
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "delete"]
```

### 3.4 ClusterRole

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cluster-admin-readonly
rules:
- apiGroups: [""]
  resources: ["nodes", "nodes/proxy", "persistentvolumes"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["get", "list"]
```

### 3.5 RoleBinding

```yaml
# 绑定 SA 到 Namespace 范围的 Role
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-sa-pod-reader
  namespace: api
subjects:
- kind: ServiceAccount
  name: api-sa
  namespace: api
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
---
# 绑定 SA 到集群范围的 ClusterRole（跨 Namespace 读）
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-sa-nodes-reader
  namespace: api
subjects:
- kind: ServiceAccount
  name: api-sa
  namespace: api
roleRef:
  kind: ClusterRole
  name: cluster-admin-readonly
  apiGroup: rbac.authorization.k8s.io
```

### 3.6 ClusterRoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cluster-admin-binding
subjects:
- kind: User
  name: admin@example.com
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
```

### 3.7 最小权限原则

| 角色 | 权限 | 适用场景 |
|------|------|---------|
| view | pods/services/endpoints GET | 只读监控 |
| edit | CRUD 大多数资源（不含 RBAC） | 开发者 |
| admin | edit + 管理 RoleBinding + RBAC | 项目管理员 |
| cluster-admin | 集群所有权限 | 集群管理员 |

```
✅ 只给 SA 需要的权限
✅ 优先用 Role（Namespace 范围），少用 ClusterRole
✅ 生产环境禁止 cluster-admin SA
✅ Kubernetes Dashboard / Lens 只给 view
```

## 4. Pod Security Standards

K8s 内建的 Pod 安全策略（Pod Security Admission，取代 PSP）：

```yaml
apiVersion: pod-security.kubernetes.io/v1beta1
kind: PodSecurityConfiguration
metadata:
  name: pod-security
spec:
  # 三个安全级别
  enforce: "restricted"     # 拒绝越界 Pod
  audit: "baseline"         # 记录越界但不拒绝
  warn: "baseline"          # 提示越界
```

| 级别 | 说明 | 典型策略 |
|------|------|---------|
| **privileged** | 无限制 | 特批 |
| **baseline** | 最小限制 | 不允许 privileged 容器、hostPID、hostNetwork |
| **restricted** | 严格限制 | baseline + 只读 rootfs、禁止 seccomp=unconfined |

## 5. 实战：多租户架构设计

```
集群 → 多个 Namespace

  Team-A namespace:
    RBAC: team-admin RoleBinding + team-view RoleBinding
    Quota: 4CPU / 8Gi RAM / 10 Pods
    NetworkPolicy: 允许内部通信，禁止跨 Namespace

  Team-B namespace:
    RBAC: 同上结构
    Quota: 8CPU / 16Gi RAM / 20 Pods

  Shared namespace:
    Ingress Controller, Monitoring, Logging
    Cluster Admin 维护
```

## 总结

```
Namespace = 逻辑租户单元（不是安全边界，但够用）
ResourceQuota = 隔离资源
RBAC = 最小权限控制主体
ServiceAccount = Pod 运行身份
Pod Security = 容器安全基线
```
