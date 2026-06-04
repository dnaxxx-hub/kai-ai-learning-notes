# 云原生第4课：Helm 包管理 & Operator 模式

> 学习日期：2026-05-10
> 课程定位：Kubernetes 上层扩展生态

---

## 一、Helm 包管理

### 1.1 什么是 Helm

Helm 是 Kubernetes 的包管理器，类比：
- **apt**（Debian） / **yum**（RHEL） / **homebrew**（macOS）
- 核心价值：将复杂的 K8s YAML 清单打包、版本化、可复用

### 1.2 Helm 架构（v3）

```
┌─────────────────────────────────────────┐
│                 Helm CLI                 │
│  (纯客户端, 无 Tiller)                    │
├─────────────────────────────────────────┤
│  1. 加载 Chart（.tgz 或目录）              │
│  2. 合并 values.yaml + --set 覆盖         │
│  3. 模板引擎渲染 → 生成最终 YAML            │
│  4. kubectl apply 到集群                  │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│         Kubernetes API Server            │
│  (通过 kubeconfig 直接交互)                │
└─────────────────────────────────────────┘
```

**Helm v3 关键变化**：
- ❌ 移除了 Tiller（服务端组件）—— 安全风险消除
- ✅ 纯客户端架构，直接使用用户 kubeconfig 的 RBAC 权限
- ✅ 引入 Release 概念，Chart 实例独立命名
- ✅ 引入 OCI 注册表支持（Chart 可存储于容器镜像仓库）

### 1.3 Chart 目录结构

```
mychart/
├── Chart.yaml          # 元数据：名称、版本、API 版本
├── values.yaml         # 默认配置值
├── values.schema.json  # values JSON Schema 校验（可选）
├── charts/             # 子依赖 Chart（subcharts）
│   └── redis/          # 依赖的 subchart
├── templates/          # Go 模板文件（核心）
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── _helpers.tpl    # 可复用的模板片段
│   ├── hpa.yaml
│   └── NOTES.txt       # helm install 后显示的使用说明
├── crds/               # CRD 定义（优先于 templates 安装）
└── .helmignore         # 打包时忽略的文件
```

**核心文件详解**：

#### Chart.yaml
```yaml
apiVersion: v2          # Helm v2 为 v1, v3 使用 v2
name: myapp
version: 0.1.0          # Chart 版本
appVersion: "1.16.0"    # 应用版本
description: A Helm chart for Kubernetes
type: application       # application 或 library
dependencies:           # 依赖声明
  - name: redis
    version: ">=10.0.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled
```

#### values.yaml
```yaml
replicaCount: 3
image:
  repository: nginx
  tag: latest
  pullPolicy: IfNotPresent
service:
  type: ClusterIP
  port: 80
ingress:
  enabled: false
  host: myapp.example.com
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi
redis:
  enabled: true
  replicaCount: 1
```

### 1.4 模板语法

Go 模板引擎是 Helm 的核心，支持以下语法：

| 语法 | 说明 | 示例 |
|------|------|------|
| `{{ .Values.xxx }}` | 引用 values 中的值 | `{{ .Values.replicaCount }}` |
| `{{ .Release.Name }}` | Release 名称 | `myapp-release` |
| `{{ .Release.Namespace }}` | 命名空间 | `default` |
| `{{ .Chart.Name }}` | Chart 名称 | `myapp` |
| `{{ .Chart.Version }}` | Chart 版本 | `0.1.0` |
| `{{ .Files.Get "config.json" }}` | 读取文件 | 内嵌配置文件 |
| `{{ if .Values.ingress.enabled }}` | 条件判断 | 包含/排除 Ingress |
| `{{ range .Values.ports }}` | 循环迭代 | 遍历端口列表 |
| `{{ default "default" .Value }}` | 默认值 | 未定义时的回退 |
| `{{ include "mychart.labels" . }}` | 模板函数 | 复用 _helpers.tpl |
| `{{ .Values.config | indent 4 }}` | 管道 | 缩进/格式化 |
| `{{ quote .Values.name }}` | 内置函数 | 加引号 |

**模板渲染流程**：
```
values.yaml  +  --set key=val   →  完整 values 对象
        ↓
Chart 模板中的 {{.Values.xxx}}  →  Go 模板引擎  →  最终 YAML
        ↓
helm template --debug   →  预览渲染结果
```

#### Deployment 模板示例 (templates/deployment.yaml)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "mychart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "mychart.selectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: {{ .Values.service.port }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

#### _helpers.tpl 示例
```yaml
{{- define "mychart.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mychart.labels" -}}
helm.sh/chart: {{ include "mychart.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: Helm
{{- end -}}
```

### 1.5 依赖管理（Subcharts）

**声明方式**（Chart.yaml）：
```yaml
dependencies:
  - name: redis
    version: ">=10.0.0"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled     # 可通过 redis.enabled=true/false 控制
    tags: ["cache"]              # 按标签组控制
    alias: cache                 # 重命名
    import-values:               # 导入子 Chart 的 values
      - child: defaults
        parent: redis_defaults
```

**常用命令**：
```bash
helm dependency update    # 更新 charts/ 目录
helm dependency build     # 重新下载依赖
helm dependency list      # 查看依赖状态
```

**Subchart 注意事项**：
- 子 Chart 的 values 通过 `父Chart名称.子Chart名称.key` 访问
- `--set` 覆盖：`--set redis.replicaCount=3`
- 子 Chart 可被全局值覆盖（`global.*`）

### 1.6 生命周期钩子

Helm 支持在 Release 的关键节点挂载钩子 Job：

| 钩子 | 触发时机 | 典型用途 |
|------|----------|----------|
| `pre-install` | 安装前 | DB 初始化、ConfigMap 创建 |
| `post-install` | 安装后 | 数据初始化、通知发送 |
| `pre-upgrade` | 升级前 | 备份、DB 迁移准备 |
| `post-upgrade` | 升级后 | 通知、缓存预热 |
| `pre-delete` | 删除前 | 安全清理、日志导出 |
| `post-delete` | 删除后 | 清理外部资源 |
| `pre-rollback` | 回滚前 | 快照当前状态 |
| `post-rollback` | 回滚后 | 验证恢复到正确状态 |

**钩子 Job 声明方式**（模板中）：
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: "{{ .Release.Name }}-db-migrate"
  annotations:
    "helm.sh/hook": pre-upgrade,post-install
    "helm.sh/hook-weight": "5"       # 执行顺序（权重小的先执行）
    "helm.sh/hook-delete-policy": hook-succeeded  # 执行成功自动删除
```

### 1.7 常用 Helm 命令

```bash
helm create mychart           # 创建 Chart 脚手架
helm package mychart/         # 打包为 .tgz
helm install myrel mychart/   # 安装
helm upgrade myrel mychart2/  # 升级
helm rollback myrel 1         # 回滚到版本1
helm uninstall myrel          # 卸载
helm list                     # 列出已安装的 Release
helm get all myrel            # 获取 Release 全部信息
helm template mychart/        # 本地渲染预览（不安装）
helm lint mychart/            # 语法检查
helm repo add bitnami https://charts.bitnami.com/bitnami  # 添加仓库
```

---

## 二、Operator 模式

### 2.1 什么是 Operator

**定义**：Operator 是将人类运维知识编码为软件的 Kubernetes 扩展模式。

**本质**：`Operator = 自定义控制器 + CRD（Custom Resource Definition）`

**为什么需要 Operator**：
- Kubernetes 原生资源（Pod、Deployment、Service）对有状态应用不够
- 数据库、消息队列、缓存等需要专业的生命周期管理（备份、恢复、扩缩容）
- 重复的运维操作 → 自动化 → Operator

### 2.2 CRD（Custom Resource Definition）

CRD 允许你扩展 Kubernetes API，定义自己的资源类型。

**示例：定义一个 EtcdCluster CRD**
```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: etcdclusters.etcd.database.coreos.com
spec:
  group: etcd.database.coreos.com
  names:
    kind: EtcdCluster
    plural: etcdclusters
    singular: etcdcluster
    shortNames:
      - etcd
  scope: Namespaced
  versions:
    - name: v1beta2
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                size:
                  type: integer
                  minimum: 1
                  maximum: 9
                version:
                  type: string
                pod:
                  type: object
                  properties:
                    resources:
                      type: object
```

**创建 CRD 后**：
```bash
# 用户可以用 kubectl 自定义资源
kubectl apply -f - <<EOF
apiVersion: etcd.database.coreos.com/v1beta2
kind: EtcdCluster
metadata:
  name: my-etcd
spec:
  size: 3
  version: "3.5.0"
EOF

# 查看自定义资源
kubectl get etcdclusters
kubectl get etcd
```

### 2.3 Controller 与 Reconcile Loop

Operator 的核心是 Controller，它运行一个无限循环：

```
┌────────────────────────────────────────────────────────┐
│                 Reconcile Loop（调谐循环）                 │
│                                                         │
│  期望状态（Spec）             当前状态（Status）              │
│   ┌────────────┐           ┌─────────────┐              │
│   │ size: 3    │           │ Ready: 2/3  │              │
│   │ version:   │   ──→    │ Pods: [p1]  │              │
│   │ "3.5.0"    │           │ [p2] [p3↓]  │              │
│   └────────────┘           └─────────────┘              │
│         ↓                          ↑                    │
│   ┌────────────────────┐           │                    │
│   │   Reconcile()      │───────────┘                    │
│   │   调谐逻辑          │  (Watch/事件回调)               │
│   └────────────────────┘                                │
│         ↓                                               │
│   动作：创建/更新/删除 Pod、Service、ConfigMap ...         │
└────────────────────────────────────────────────────────┘
```

**伪代码**：
```python
def reconcile(cluster_resource):
    desired_state = parse_spec(cluster_resource.spec)
    current_state = get_current_state(cluster_resource)
    
    if desired_state == current_state:
        return  # 无需操作
    
    # 创建缺失的 Pod
    for i in range(desired_state.size):
        if not has_pod(cluster_resource, i):
            create_pod(cluster_resource, i)
    
    # 删除多余的 Pod
    for pod in current_state.pods:
        if pod.index >= desired_state.size:
            delete_pod(pod)
    
    # 更新状态
    update_status(cluster_resource, "Ready", 
                  f"{len(running_pods)}/{desired_state.size}")
```

### 2.4 Operator 三件套

一个完整的 Operator 包含三个组件：

```
┌──────────────────────────────────────────────────┐
│              Operator 三件套                        │
│                                                    │
│  1. CRD（自定义资源定义）                              │
│     定义用户可操作的 API 对象                          │
│                                                    │
│  2. Controller（控制器）                             │
│     监听 CRD 变化 → 调谐到期望状态                    │
│                                                    │
│  3. Webhook（准入控制）                              │
│     - MutatingWebhook: 修改请求（默认值注入）           │
│     - ValidatingWebhook: 校验请求（验证约束）           │
└──────────────────────────────────────────────────┘
```

**Webhook 的作用**：
```yaml
# 用户提交的 CR（可能不完整）
apiVersion: etcd.database.coreos.com/v1beta2
kind: EtcdCluster
metadata:
  name: my-etcd
spec:
  size: 3
# version 未指定 → MutatingWebhook 注入默认值 "3.5.0"
# size: 10 → ValidatingWebhook 拒绝（max=9）
```

### 2.5 Operator 成熟度模型（Capability Levels）

```
Level 5: 自动修复/自动扩缩
   ├── 自动进行故障转移
   ├── 根据负载自动扩缩容
   └── 自我修复（无需人工干预）
   
Level 4: 深度洞察
   ├── 集成监控指标
   ├── 日志和告警管理
   └── 自动备份和恢复验证
   
Level 3: 完整生命周期
   ├── 升级/回滚/迁移
   ├── 配置变更管理
   └── 存储卷管理
   
Level 2: 升级
   ├── 安全升级（滚动更新）
   └── 版本管理
   
Level 1: 基础安装
   └── 部署和配置
```

**常见 Operator 成熟度评估**：

| Operator | Level | 能力 |
|----------|-------|------|
| etcd-operator | L3-L4 | 自动备份/恢复，动态扩缩容 |
| Prometheus Operator | L4-L5 | ServiceMonitor 动态发现，告警管理 |
| Strimzi (Kafka) | L4 | Broker 重新均衡，Topic 自动管理 |
| TiDB Operator | L4-L5 | 自动扩缩，备份恢复，滚动升级 |
| Elasticsearch Operator | L3-L4 | 集群扩缩，安全升级 |
| Postgres Operator | L3-L4 | 流复制，自动故障转移 |

### 2.6 构建工具

| 工具 | 特点 | 适用场景 |
|------|------|----------|
| **Operator SDK** | Red Hat 出品，Go/Ansible/Helm 支持 | 企业级，功能最全面 |
| **KubeBuilder** | Google 出品，原生 Go 控制器框架 | Go 开发者，轻量灵活 |
| **Kopf** (Kubernetes Operator Pythonic Framework) | Python 实现 | Python 开发者快速原型 |
| **Java Operator SDK** | Java 实现 | Java 技术栈团队 |

**KubeBuilder 工作流**：
```bash
# 1. 初始化项目
kubebuilder init --domain mycompany.com --repo github.com/mycompany/my-operator

# 2. 创建 API（CRD + Controller）
kubebuilder create api --group myapp --version v1 --kind MyApp

# 3. 实现 Reconcile 逻辑
# 编辑 controllers/myapp_controller.go

# 4. 生成 CRD YAML
make generate
make manifests

# 5. 部署
make deploy
```

---

## 三、常用 Operator 案例分析

### 3.1 etcd-operator

**功能**：
- 自动创建和管理 etcd 集群
- 自动备份到 S3/OSS
- 从备份自动恢复
- 动态扩缩容
- 滚动升级

**核心 CRD**：
```yaml
# EtcdCluster — 集群定义
apiVersion: etcd.database.coreos.com/v1beta2
kind: EtcdCluster
spec:
  size: 3
  version: "3.5.0"
  backup:
    backupIntervalInSecond: 1800
    maxBackups: 5
    storageType: "S3"
    s3:
      path: "/etcd-backups"
      awsSecret: "aws-secret"
  pod:
    resources:
      requests:
        cpu: 200m
        memory: 256Mi
```

**Reconcile 流程**：
```
收到 EtcdCluster CR → 检查当前集群状态
├── Pod 数不匹配 → 创建/删除 etcd Pod
├── 版本不匹配 → 滚动更新
├── 备份到期 → 触发备份
└── 成员故障 → 替换故障成员
```

### 3.2 Prometheus Operator

**核心能力**：
- `Prometheus` CRD：定义 Prometheus 实例配置
- `ServiceMonitor` CRD：动态发现监控目标
- `PrometheusRule` CRD：定义告警规则
- `Alertmanager` CRD：管理告警路由

**ServiceMonitor 动态发现**：
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: myapp-monitor
spec:
  selector:                     # 匹配 Service 标签
    matchLabels:
      app: myapp
  endpoints:
    - port: http                # Service 端口名
      interval: 15s
      path: /metrics
```

**工作流**：
```
部署新 Service（带 app=myapp 标签）
    ↓
Prometheus Operator 监听到 ServiceMonitor 变化
    ↓
自动更新 Prometheus 的 scrape config
    ↓
Prometheus 开始拉取 /metrics
    ↓
匹配告警规则 → 触发 Alertmanager 通知
```

### 3.3 Strimzi (Kafka Operator)

**核心能力**：
- `Kafka` CRD：管理 Kafka 集群
- `KafkaTopic` CRD：自动创建 Topic
- `KafkaUser` CRD：管理用户认证
- `KafkaRebalance` CRD：触发 Broker 均衡

**自动 Broker 均衡流程**：
```
用户创建 KafkaRebalance CR
    ↓
Strimzi 的 Cruise Control 组件分析负载
    ↓
生成重新均衡提案
    ↓
自动或手动触发执行
    ↓
Broker 间 Topic 分区自动迁移
    ↓
集群负载均衡完成
```

---

## 四、Python 模拟实现

参见同目录下的 `code/helm_sim.py`，包含：

1. **最小 Helm 模板引擎**：
   - 解析 `{{ .Values.xxx }}` / `{{ .Release.Name }}` 语法
   - 支持 `if/else` 条件判断
   - 支持 `range` 循环
   - Chart 目录解析

2. **Operator Reconcile 模拟**：
   - CRD 注册模拟
   - Reconcile 循环：期望状态 → 当前状态 → 调谐
   - 状态匹配和修正逻辑
   - 事件驱动的 Watch 机制

3. **运行示例**：
```bash
python memory/learning/code/helm_sim.py
```

---

## 五、关键总结

### Helm
```
Chart（模板 + values） → 渲染 → YAML → kubectl apply → Release
                                          ↑
                               （Helm v3 纯客户端）
```

### Operator
```
CRD（定义 API） + Controller（Reconcile 循环） + Webhook（校验）
                               ↓
                  将运维知识编码为自动化软件
```

### 最佳实践
1. **Chart 设计**：保持模板简单，尽量在 values.yaml 中表达配置差异
2. **Operator 开发**：从 Level 1 开始，逐步增加能力
3. **CRD 设计**：考虑向后兼容，使用版本化（v1alpha1 → v1beta1 → v1）
4. **Reconcile 幂等性**：Reconcile 函数必须幂等，重复调用结果一致
5. **状态记录**：Operator 需要记录 Status，供用户和下次 Reconcile 使用

---

## 六、参考资源

- [Helm 官方文档](https://helm.sh/docs/)
- [Operator 模式 - Kubernetes 官方](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [Operator SDK](https://sdk.operatorframework.io/)
- [KubeBuilder](https://kubebuilder.io/)
- [OperatorHub.io](https://operatorhub.io/) — 社区 Operator 市场
