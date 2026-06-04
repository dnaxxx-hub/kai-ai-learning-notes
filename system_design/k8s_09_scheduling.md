# K8s 第9课：调度深度解析 —— 把Pod放到最合适的Node上

> 日期：2026-05-25 | 来源：K8s学习路线图（补充课）

## 核心概念

K8s调度器（kube-scheduler）的核心任务只有一个：**为新创建的Pod选择最合适的Node**。但"最合适"的背后，是一整套可配置的过滤（Filtering）和打分（Scoring）机制。

### 调度流程

```
Pod创建（未调度）
    │
    ▼
调度队列（Scheduling Queue）
    │ 按优先级排序
    ▼
过滤阶段（Filtering/Predicates）
    │ 排除不满足硬性条件的Node
    ▼
打分阶段（Scoring/Priorities）
    │ 对剩余Node打分排名
    ▼
绑定（Binding）
    │ 将Pod绑定到最高分Node
    ▼
kubelet感知 → 启动容器
```

整个流程是**异步的**。Scheduler watch到未调度的Pod（`spec.nodeName`为空），执行调度算法后更新Pod的`nodeName`。

### 调度框架（Scheduling Framework）

K8s从v1.19引入了可扩展的调度框架，允许通过插件自定义调度行为：

```
Scheduling Cycle          Binding Cycle
┌──────────────────┐    ┌──────────────────┐
│ QueueSort        │    │ WaitOnPermit     │
│ PreFilter        │    │ PreBind          │
│ Filter           │    │ Bind             │
│ PostFilter       │    │ PostBind         │
│ PreScore         │    └──────────────────┘
│ Score            │
│ NormalizeScore   │
│ Reserve          │
│ Permit           │
└──────────────────┘
```

默认调度器内置了20+个插件，涵盖QueueSort、Filter、Score等各个扩展点。

## 架构要点

### 1. nodeSelector —— 最简单的节点选择

nodeSelector是调度约束的"入门级"工具，通过label键值对做**硬性匹配**：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ssd-pod
spec:
  nodeSelector:
    disk-type: ssd        # 只调度到有该label的Node
  containers:
  - name: app
    image: nginx
```

```bash
# 给Node打label
kubectl label nodes node1 disk-type=ssd

# 移除label
kubectl label nodes node1 disk-type-

# 查看节点label
kubectl get nodes --show-labels
```

**局限性**：只支持等值匹配（In），不支持：
- 值不在集合中（NotIn）
- 存在性判断（Exists）
- 软性偏好（尽量但不强制）
- 跨Pod的亲和性调度

因此nodeSelector适用于简单场景，复杂场景要用Affinity。

### 2. Node Affinity —— 节点亲和性

Node Affinity是对nodeSelector的全面升级，分为**硬性**和**软性**两种：

#### requiredDuringSchedulingIgnoredDuringExecution（硬性）

Pod必须调度到满足条件的Node，否则Pending：

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: topology.kubernetes.io/zone
            operator: In
            values:
            - us-east-1a
            - us-east-1b
          - key: gpu-type
            operator: Exists    # 只要存在该key即可，不在乎值
```

**nodeSelectorTerms间的逻辑关系**：
- 多个`nodeSelectorTerms`：**或（OR）** —— 满足任一term即可
- 单个term内多个`matchExpressions`：**与（AND）** —— 必须全部满足

#### preferredDuringSchedulingIgnoredDuringExecution（软性）

调度器**优先选择**满足条件的Node，但不强制：

```yaml
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        preference:
          matchExpressions:
          - key: spot-instance
            operator: In
            values:
            - "true"
      - weight: 20
        preference:
          matchExpressions:
          - key: disk-type
            operator: In
            values:
            - ssd
```

**weight的作用**：调度器对满足偏好的Node加分，weight越大优先级越高。多个偏好的weight会累加。最终得分会归一化到0-100之间。

#### IgnoredDuringExecution的含义

名字的后半段"IgnoredDuringExecution"意味着**运行时不会生效**——如果Pod已经运行后Node的label变了，K8s不会主动重新调度Pod。这需要用户手动处理（比如用descheduler项目）。

### 3. Pod Affinity / Anti-Affinity —— Pod间的亲和与排斥

这是比Node Affinity更复杂的调度约束：**让Pod根据其他Pod的位置做调度决策**。

#### 工作原理

```
Pod Affinity（亲和）：
  "我想和标签为 app=cache 的Pod待在同一个拓扑域"

Pod Anti-Affinity（反亲和）：
  "我不想和标签为 app=web 的Pod待在同一个拓扑域"
```

**拓扑域（topologyKey）**：用Node的哪个label来定义"同一个域"？
- `kubernetes.io/hostname`：同一Node（最严格）
- `topology.kubernetes.io/zone`：同一可用区
- `topology.kubernetes.io/region`：同一地域

#### Pod Affinity —— 把相关Pod聚在一起

```yaml
spec:
  affinity:
    podAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - cache
        topologyKey: topology.kubernetes.io/zone
```

**含义**：该Pod必须调度到"存在app=cache的Pod"的同一可用区。

#### Pod Anti-Affinity —— 把冲突Pod分开

```yaml
spec:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
            - key: app
              operator: In
              values:
              - web
          topologyKey: kubernetes.io/hostname
```

**含义**：尽可能避免和app=web的Pod待在同一个Node上。

#### 典型场景：高可用部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - web
            topologyKey: kubernetes.io/hostname
      containers:
      - name: nginx
        image: nginx:1.25
```

**效果**：3个副本会分布在3个不同的Node上。任何一个Node宕机，最多影响1个副本，服务不中断。

#### Pod Affinity/Anti-Affinity vs nodeSelector

| 特性 | nodeSelector | Node Affinity | Pod Affinity |
|------|-------------|---------------|--------------|
| 选择依据 | Node标签 | Node标签 | 其他Pod的标签 |
| 表达能力 | 等值匹配 | In/NotIn/Exists/DoesNotExist/Gt/Lt | In/NotIn/Exists/DoesNotExist |
| 软性约束 | ❌ | ✅ (preferred) | ✅ (preferred) |
| 调度开销 | 无 | 低 | 高（需查询其他Pod） |

> **实战注意**：required Pod Anti-Affinity + topologyKey: hostname + 大量副本 = 集群没有足够Node时副本Pending。软性约束preferred更安全。

### 4. Taint（污点）与 Toleration（容忍）

Taint/Toleration是K8s调度中最灵活也最易混淆的机制。

#### 核心概念

```
Taint（污点）：Node说"我不喜欢某些Pod"
Toleration（容忍）：Pod说"我不介意这个污点"

匹配规则：
1. Node有 Taint → 默认拒绝所有Pod调度
2. Pod有 Toleration → 允许调度（但不保证一定调度到这个Node）
```

#### Node Taint 操作

```bash
# 添加污点
kubectl taint nodes node1 key=value:NoSchedule

# 移除污点
kubectl taint nodes node1 key=value:NoSchedule-

# 查看污点
kubectl describe nodes node1 | grep Taints
```

#### 三种污点效果（Effect）

| Effect | 行为 | 典型用途 |
|--------|------|---------|
| **NoSchedule** | 不调度新Pod（已有Pod不受影响） | 将某类Pod排除出Node |
| **PreferNoSchedule** | 尽量避免调度（软性NoSchedule） | 节点维护前标记 |
| **NoExecute** | 不调度 + 驱逐已有不匹配的Pod | 节点故障时驱逐Pod |

#### Pod Toleration 写法

```yaml
spec:
  tolerations:
  - key: "key1"
    operator: "Equal"
    value: "value1"
    effect: "NoSchedule"
  - key: "key2"
    operator: "Exists"
    effect: "NoSchedule"
  - key: "key3"
    operator: "Exists"       # 省略effect表示匹配所有effect
  - key: "key4"
    operator: "Equal"
    value: "value4"
    effect: "NoExecute"
    tolerationSeconds: 3600  # 容忍3600秒后被驱逐
```

**operator区别**：
- `Equal`：key + value + effect 必须完全匹配
- `Exists`：key + effect 匹配即可（不在乎value）
- 若不指定operator，默认为`Equal`

#### 内置污点

K8s会自动给Node添加一些系统级污点：

```bash
# 常见的Node级别的Condition → Taint映射
node.kubernetes.io/not-ready       # Node未就绪 → NoExecute
node.kubernetes.io/unreachable     # Node不可达 → NoExecute
node.kubernetes.io/out-of-disk     # 磁盘满 → NoSchedule
node.kubernetes.io/memory-pressure # 内存压力 → NoSchedule（软性）
node.kubernetes.io/disk-pressure   # 磁盘压力 → NoSchedule（软性）
node.kubernetes.io/network-unavailable # 网络不可用 → NoSchedule
```

K8s系统组件（如kube-proxy、CoreDNS）的Toleration就是匹配这些内置污点，确保即使Node有问题它们也能留在Node上干活。

#### Taint + Toleration + Node Affinity 组合：专用Node池

```yaml
# 1. 给GPU节点打污点
# kubectl taint nodes gpu-node-1 gpu=true:NoSchedule

# 2. GPU Pod声明容忍+Node Affinity
apiVersion: v1
kind: Pod
metadata:
  name: gpu-job
spec:
  tolerations:
  - key: "gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  nodeSelector:
    gpu: "true"            # 可选，进一步确保
  containers:
  - name: cuda
    image: nvidia/cuda:12.0
    resources:
      limits:
        nvidia.com/gpu: 1
```

**效果**：普通Pod不会调度到GPU节点，只有明确声明Toleration的Pod才能使用GPU资源。这比依赖NodeSelector更安全——如果有人忘记打Label会导致调度错误，而Taint是"默认拒绝，显式允许"。

#### 实战：节点维护组合拳

```bash
# 1. 标记：不可调度 + 驱逐已有Pod
kubectl cordon node-1
kubectl drain node-1 --ignore-daemonsets --delete-emptydir-data

# 2. 或者：直接加NoExecute污点驱逐
kubectl taint nodes node-1 maintenance=true:NoExecute

# 3. 维护完成后
kubectl taint nodes node-1 maintenance=true:NoExecute-
kubectl uncordon node-1
```

### 5. 自定义调度器

K8s允许运行多个调度器实例。默认调度器是`default-scheduler`，可以部署自己的调度器来处理特殊需求。

#### 声明使用特定调度器

```yaml
spec:
  schedulerName: my-custom-scheduler    # 使用自定义调度器
  containers:
  - name: app
    image: nginx
```

#### 调度器扩展机制

| 机制 | 原理 | 复杂度 |
|------|------|--------|
| **Scheduler Extender** | HTTP回调，在Filter/Score阶段调用外部服务 | 中等 |
| **调度框架插件** | 编译到调度器中的Go插件 | 高 |
| **独立调度器** | 完整的独立调度器二进制 | 最高 |
| **Descheduler** | 事后重新调度已运行的Pod（不参与初始调度） | 低 |

#### Descheduler —— 让运行时调度更合理

Scheduler只在Pod创建时调度一次。运行时集群拓扑变化（如新节点加入）不会触发重新调度。Descheduler负责检测并驱逐"调度不合理"的Pod，让Scheduler重新调度：

```bash
# 安装Descheduler（使用Helm）
helm repo add descheduler https://kubernetes-sigs.github.io/descheduler/
helm install descheduler descheduler/descheduler \
  --namespace kube-system \
  --set strategies={
    "RemoveDuplicates",
    "LowNodeUtilization",
    "RemovePodsViolatingInterPodAntiAffinity",
    "RemovePodsViolatingNodeAffinity",
    "RemovePodsViolatingTopologySpreadConstraint"
  }
```

### 6. Pod Topology Spread Constraints —— 拓扑分布约束

K8s v1.19引入，让Pod在集群中更均匀地分布：

```yaml
spec:
  topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app: web
```

| 参数 | 说明 |
|------|------|
| `maxSkew` | 最大不均衡度。1表示任意两个拓扑域间Pod数差不超过1 |
| `topologyKey` | 拓扑域的Node label |
| `whenUnsatisfiable` | DoNotSchedule（硬性）或ScheduleAnyway（软性） |
| `labelSelector` | 匹配哪些Pod参与计数 |

**使用场景**：当Pod Anti-Affinity不够灵活时。Anti-Affinity只在"有/没有"之间选择，Topology Spread Constraints控制"分布均匀度"。

## 代码/配置示例

### 生产级高可用部署（调度全貌）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: production-web
spec:
  replicas: 5
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      # 1. 软性Node偏好：优先SSD节点
      affinity:
        nodeAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 50
            preference:
              matchExpressions:
              - key: disk-type
                operator: In
                values:
                - ssd
        # 2. Pod反亲和：相同副本分布在不同Node
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - web
              topologyKey: kubernetes.io/hostname
      # 3. 拓扑分布：节点间均匀分布
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: kubernetes.io/hostname
        whenUnsatisfiable: ScheduleAnyway
        labelSelector:
          matchLabels:
            app: web
      # 4. 容忍系统级污点
      tolerations:
      - key: "node.kubernetes.io/not-ready"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 60
      - key: "node.kubernetes.io/unreachable"
        operator: "Exists"
        effect: "NoExecute"
        tolerationSeconds: 60
      containers:
      - name: web
        image: nginx:1.25
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
```

### 节点池隔离：GPU vs CPU混部

```yaml
# GPU节点池
apiVersion: v1
kind: Pod
metadata:
  name: gpu-training
spec:
  tolerations:
  - key: "nvidia.com/gpu"
    operator: "Exists"
    effect: "NoSchedule"
  nodeSelector:
    node-type: gpu
  containers:
  - name: trainer
    image: tensorflow/tensorflow:latest-gpu
    resources:
      limits:
        nvidia.com/gpu: 1
---
# 普通CPU节点Pod（无需特别配置）
apiVersion: v1
kind: Pod
metadata:
  name: web-service
spec:
  nodeSelector:
    node-type: cpu
  containers:
  - name: web
    image: nginx:1.25
```

```bash
# 创建节点池隔离
kubectl label nodes gpu-node-1 node-type=gpu
kubectl label nodes cpu-node-1 node-type=cpu
kubectl taint nodes gpu-node-1 nvidia.com/gpu=true:NoSchedule
```

## 与已有知识的关联

- **k8s_01_arch_basics.md**（第1课）：复习了Scheduler组件在整个架构中的位置
- **k8s_02_pod_deep.md**（第2课）：Pod的nodeSelector和资源限制部分与本课深度关联
- **k8s_03_workloads.md**（第3课）：工作负载的调度策略是本课的实际应用场景
- **分布式系统笔记**：调度算法和一致性哈希等分布式调度思想在K8s中体现

## 思考

### 调度的本质

K8s调度不是"最优匹配"问题，而是"足够好"问题。原因有三：
1. **集群状态动态变化**：调度时的"最优"节点可能在Pod启动前就资源紧张了
2. **打分策略依赖业务场景**：同一个Pod在不同团队眼中的"最优Node"不同
3. **计算代价**：全局最优解是NP难问题，K8s用Filter+Score的贪心策略

所以调度的核心设计哲学是：**快速给出一个"足够好"的解，让控制循环在运行时不断修正**。

### Taint/Toleration的逆向思维

Taint/Toleration的设计体现了安全领域的**白名单思维**：
- NodeSelector/Affinity是黑名单："不让我的Pod去那些节点"
- Taint/Toleration是白名单："不让别的Pod来我的节点，除非你特别声明"

**最佳实践**：核心组件用Taint保护（如控制面节点），普通应用用Node Affinity做优化。

### 多调度策略叠加规则

同时使用多种调度策略时，遵循以下规则：

```
1. 所有硬性约束必须满足（AND逻辑）
2. 所有软性约束加权求和
3. Taint/Toleration是独立于Affinity的否决机制
4. 最终只有"通过硬性过滤 + 容忍所有Taint"的Node参与打分
```

### 排障速查

| 现象 | 可能原因 | 排查命令 |
|------|---------|---------|
| Pod一直Pending | 没有Node满足调度条件 | `kubectl describe pod` → Events |
| Pod调度到不需要的Node | Taint忘加或Toleration不匹配 | `kubectl describe node` → Taints |
| 副本都跑在同一Node | 没配Pod Anti-Affinity | `kubectl get pods -o wide` |
| 新节点利用率低 | 调度策略没考虑新节点 | 检查Descheduler是否运行 |
| 更新Deployment后Pod调度异常 | Affinity selector没更新 | `kubectl get pods --show-labels` |
