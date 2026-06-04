# K8s/云原生 #7：Helm、Operator 与 CRD

> 2026-05-17
> 前置：RBAC 与多租户 #6

## 1. Helm：K8s 包管理器

### 1.1 为什么需要 Helm

原始 YAML 的问题：
- 100+ 个 YAML 文件管理混乱
- 环境差异（开发/测试/生产）手动改
- 没有版本管理和回滚

Helm 的核心抽象：**Chart** = 模板化的 K8s 资源描述 + 可配置参数。

### 1.2 架构

```
Helm (Client CLI) → K8s API Server
                      ↓
Tiller (旧版，Helm2) — 已弃用，Helm3 无服务端
```

Helm 3 移除 Tiller，直接与 API Server 交互，不需要 ClusterRole。

### 1.3 Chart 结构

```
mychart/
├── Chart.yaml           # 元数据：名称、版本、依赖
├── values.yaml          # 默认配置值
├── values.schema.json   # values 的 JSON Schema 验证
├── charts/              # 子 Chart（依赖）
├── templates/           # Go 模板 + Sprig
│   ├── deployment.yaml
│   ├── service.yaml
│   └── _helpers.tpl     # 模板辅助函数
└── README.md
```

### 1.4 模板语法

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}  # 调用 helper
  labels:
    app: {{ .Values.appName }}
spec:
  replicas: {{ .Values.replicaCount | default 3 }}
  selector:
    matchLabels:
      app: {{ .Values.appName }}
  template:
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        resources:
          {{- toYaml .Values.resources | nindent 10 }}  # 直接嵌入 YAML
```

```yaml
# values.yaml
appName: myapp
replicaCount: 3
image:
  repository: nginx
  tag: 1.25
resources:
  requests:
    cpu: 100m
    memory: 128Mi
```

### 1.5 常用命令

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm search repo nginx

helm install my-nginx bitnami/nginx --values my-values.yaml
helm list                        # 查看已安装的 release
helm upgrade my-nginx bitnami/nginx --set replicaCount=5
helm rollback my-nginx 1         # 回滚到版本 1
helm uninstall my-nginx

helm create mychart               # 创建新 Chart
helm lint ./mychart               # 验证 Chart 语法
helm template ./mychart           # 渲染模板看结果
```

### 1.6 依赖管理

```yaml
# Chart.yaml
dependencies:
- name: redis
  version: "~18.0.0"
  repository: "https://charts.bitnami.com/bitnami"
  condition: redis.enabled
- name: postgresql
  version: "~14.0.0"
  repository: "https://charts.bitnami.com/bitnami"
  condition: postgresql.enabled
```

```bash
helm dependency update ./myapp    # 拉取依赖到 charts/
```

## 2. CRD（自定义资源定义）

### 2.1 什么是 CRD

让 K8s 认识新的资源类型——就像 k8s 原生支持 Pod/Deployment/Service 一样。

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databases.example.com
spec:
  group: example.com
  names:
    kind: Database
    plural: databases
    singular: database
    shortNames: ["db"]
  scope: Namespaced
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              engine:
                type: string
                enum: ["postgres", "mysql"]
              version:
                type: string
              storage:
                type: string
```

创建 CRD 后，就可以像原生资源一样操作：

```yaml
apiVersion: example.com/v1
kind: Database
metadata:
  name: my-db
spec:
  engine: postgres
  version: "16"
  storage: 100Gi
```

```bash
kubectl get databases
kubectl describe database my-db
```

### 2.2 CRD 的生命周期

```
CRD 创建 → API Server 自动注册新 REST 路径
         → 可以 create/get/update/delete 自定义资源
         → 但这只是数据的 存储（etcd），没有 逻辑（不创建 Pod）

需要有 Operator 来监听自定义资源的变化，执行相应的逻辑
```

## 3. Operator

### 3.1 Operator 模式

Operator = CRD + Controller（Watch + Reconcile）

```
CRD 定义：什么资源（Database CRD）
Operator：谁负责处理（db-operator Deployment）
     ↓
Watch Loop → 监听 Database 资源的变更
                  ↓
          Reconcile（调谐循环）：对比期望状态 vs 实际状态
                  ↓
          创建/更新/删除 实际 K8s 资源
```

### 3.2 简单 Operator 逻辑

```go
// 伪代码示意（等价逻辑）
func (r *DatabaseReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 获取 Custom Resource
    var db examplev1.Database
    if err := r.Get(ctx, req.NamespacedName, &db); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    // 2. 检查期望状态 vs 实际状态
    //    是否需要创建 StatefulSet？
    var sts appsv1.StatefulSet
    if err := r.Get(ctx, types.NamespacedName{Name: db.Name}, &sts); err != nil {
        // 不存在 → 创建
        desired := buildStatefulSet(db)
        r.Create(ctx, &desired)
        return ctrl.Result{RequeueAfter: 5 * time.Second}, nil
    }

    // 3. 是否需要更新？
    if needsUpdate(sts, db) {
        sts.Spec.Replicas = db.Spec.Replicas
        r.Update(ctx, &sts)
    }

    // 4. 检查 Secret / Service / PVC 等关联资源

    return ctrl.Result{}, nil
}
```

### 3.3 Operator SDK 框架

| 框架 | 语言 | 特点 |
|------|------|------|
| kubebuilder | Go | 官方推荐，最成熟 |
| Operator SDK | Go | Red Hat，基于 kubebuilder |
| Kopf | Python | 快速原型 |
| Operator Framework (.NET) | C# | .NET 生态 |

### 3.4 常见 Operator

```
数据库：    MySQL Operator, PostgreSQL Operator, MongoDB Operator
消息队列：  Kafka Operator (Strimzi), RabbitMQ Operator
监控：     Prometheus Operator, Grafana Operator
中间件：   Redis Operator, Elasticsearch Operator
安全：     Vault Operator, Cert-Manager
基础设施： AWS/ GCP / Azure Service Operator
```

### 3.5 什么时候需要写 Operator

```
需要自动编排：
  ✅ 有状态应用部署（数据库/消息队列）
  ✅ 备份恢复（定期备份 + 灾难恢复）
  ✅ 自动扩缩容（基于自定义指标）
  ✅ 升级策略（滚动/金丝雀/蓝绿）
  ✅ 异常自愈（检测主节点故障自动切换）

不需要：
  ❌ 部署简单 CRUD 服务 → Helm Chart 就够了
  ❌ 少量 Pod → Deployment YAML
```

## 4. Helm vs Operator

| | Helm | Operator |
|---|------|---------|
| 时机 | 安装时 | 运行时持续 |
| 自动化 | 一次性部署 | 持续调谐（自愈）|
| CRD 管理 | 安装 & 卸载 | 持续管理 |
| 适用 | 无状态/简单有状态 | 复杂有状态/需要运维逻辑 |

**典型组合**：Helm 安装 Operator，Operator 管理后续生命周期。

## 总结

```
Helm = K8s 包管理（模板化 YAML + 版本管理）
  ↓ 快速部署
CRD = 自定义资源定义（教 K8s 认识新资源）
  ↓ 数据结构
Operator = 自动化运维逻辑（Watch + Reconcile 循环）
  ↓ 持续管理
稳定运行
```
