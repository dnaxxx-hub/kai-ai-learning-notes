# K8s/云原生运维 #1：容器编排基础与Kubernetes架构

> **课程定位**：云原生运维系列第1课，从零构建K8s认知体系。
> **目标读者**：有Linux/Shell基础，了解Docker但没系统学过K8s的运维开发者。
> **阅读时长**：约60分钟 | **篇幅**：10-15KB

---

## 引言：为什么要学K8s？

把Kubernetes放在运维技能树的C位，不是因为它是"流行词"，而是因为它事实上已成为**分布式系统的通用控制平面**。

过去十年，我们对服务器的操作方式经历了三个阶段：

| 阶段 | 模式 | 典型工具 | 痛点 |
|------|------|----------|------|
| 物理机时代 | 直接操作硬件 | Shell脚本、Ansible | 资源利用率低、部署慢 |
| 虚拟化时代 | 管理虚拟机 | VMware、OpenStack | VM太重、启动分钟级 |
| **容器化+K8s** | **声明式API调度** | **Kubernetes** | 学习曲线陡、排障难 |

今天的K8s已经不只是"容器编排工具"——它是一个**操作系统级别的资源抽象层**。你在上面跑的不只是Web服务，还有消息队列、数据库、数据管道、ML训练任务。云原生意味着**任何能在Linux上跑的东西，都应该能用K8s管起来**。

本系列直接从实操视角切入。这一课的目标很简单：**搞懂K8s是什么、怎么工作的、以及怎么用它部署一个真正的应用**。

---

## 第一章：容器化基础回顾

在进入K8s之前，先把容器的地基夯实。这不是浪费时间——**K8s排障中70%的问题根源在容器层面**。

### 1.1 Docker vs containerd vs CRI-O

容器运行时是K8s栈的最底层。如果你沿着K8s调用链往下走，大概是这样：

```
kubectl → kube-apiserver → kubelet → CRI(gRPC) → Container Runtime → runc(内核)
```

这里的`Container Runtime`就是负责真正启动/管理容器的组件。历史上Docker一枝独秀，现在则被更轻量的选择替代。

| 运行时 | 关系 | 特点 |
|--------|------|------|
| **Docker** | 完整工具链（CLI+daemon+runtime） | 最完善的工具体验，但架构重。K8s 1.24+已弃用dockershim |
| **containerd** | Docker拆出的核心runtime，CNCF毕业项目 | 更轻、更稳定，当前K8s默认选项 |
| **CRI-O** | 专为K8s CRI接口设计的runtime | 极简、安全，Red Hat/OpenShift主打 |

在K8s中你用`ctr`（containerd CLI）或`crictl`（CRI通用CLI）排查容器问题，而不是`docker`命令。

```bash
# 排查节点上的容器（K8s节点上更推荐用这个）
crictl ps
crictl logs <container-id>
crictl inspect <container-id>

# 查看当前节点的运行时
kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.containerRuntimeVersion}'
```

> **常见问题**：为什么我的kubectl可以执行，但docker ps看不到任何K8s容器？
> **答**：因为你用的是containerd运行时。用 `crictl ps` 或 `nerdctl ps` 代替docker命令。

### 1.2 Namespace与CGroup：容器的"两把锁"

容器的本质不是虚拟化，而是 **"受限的进程"**。Linux内核通过两个机制实现隔离和限制：

#### Namespace：让进程"看"不到别人

Namespace决定了**你能看到什么**。每个容器有自己的Namespace视图，感知不到宿主机和其他容器的存在。

| Namespace类型 | 隔离内容 | K8s中的应用 |
|:---:|:---|:---|
| PID | 进程号 | 容器内PID从1开始，看不到宿主机进程 |
| NET | 网络栈 | 每个Pod有自己的IP、端口、路由表 |
| MNT | 挂载点 | 容器有自己的文件系统视图 |
| UTS | 主机名 | 容器有自己的hostname |
| USER | 用户UID | 容器内root ≠ 宿主机root |
| IPC | 进程间通信 | 共享内存、信号量隔离 |
| CGROUP | cgroup层次 | 容器只能看到自己的cgroup |

> **说人话**：Namespace就是给进程戴了个"VR眼镜"——它以为自己是整个系统的主人，其实只是在沙盒里。

#### CGroup：让进程没能耐"吃太多"

CGroup决定了**你能用多少**。它限制CPU、内存、磁盘IO的上限。

```
/sys/fs/cgroup/
├── cpu/          # CPU使用上限、权重
├── memory/       # 内存上限、OOM优先级
├── blkio/        # 块设备IO限制
├── pids/         # 进程数限制
└── net_prio/     # 网络优先级
```

**K8s中的requests/limits最终映射到这里：**

```bash
# 查看某个Pod的cgroup限制（在Pod所在Node上执行）
cat /sys/fs/cgroup/memory/kubepods/burstable/pod<uid>/memory.limit_in_bytes
```

> **常见问题**：容器内存用满了会怎样？
> **答**：由CGroup的`memory.oom_control`决定。如果容器内存超过limit → OOM Kill。如果Node内存不足 → kubelet开始逐出Pod（Eviction），优先级按QoS类。

### 1.3 容器镜像分层与OCI标准

一个Docker镜像不是"一大坨文件"，而是一堆**只读层的堆叠**：

```
┌──────────────┐  ← 可写容器层（容器删除后丢失）
├──────────────┤
│   apt-get    │  ← 镜像层3（你RUN的指令）
├──────────────┤
│   base pkgs  │  ← 镜像层2（操作系统基础包）
├──────────────┤
│   ubuntu:22  │  ← 镜像层1（基础镜像，只读）
└──────────────┘
```

当你在容器内写文件时，用的是**写时复制（Copy-on-Write）**——修改不会改到下层镜像，而是在顶层创建一份副本。

**OCI标准做了什么？**

2015年Docker和CoreOS等公司定义了OCI（Open Container Initiative），统一了：
- **Image Spec**：镜像层的格式规范（layer tar + manifest.json）
- **Runtime Spec**：容器运行时规范（config.json定义Namespace/CGroup等）

这意味着：**用Dockerfile构建的镜像，用containerd/CRI-O都能跑**。OCI是K8s生态互操作的基石。

```dockerfile
# 一个标准的Dockerfile -> OCI镜像
FROM alpine:3.18          # 基础层
RUN apk add --no-cache nginx  # 新增层
COPY index.html /usr/share/nginx/html/  # 新增层
CMD ["nginx", "-g", "daemon off;"]  # 元数据（不占层）
```

> **常见问题**：镜像层数太多有什么问题？
> **答**：层数越多，拉取和构建时间越长。最佳实践：合并RUN命令（`RUN apt-get update && apt-get install -y pkg1 pkg2`），控制在15层以内。

### 1.4 Pod的本质：共享Namespace的容器组

Pod是K8s的**最小调度单位**——这是K8s和Docker原生的最大区别。Docker只管理单个容器，K8s管理一组共享资源的容器。

```
┌───────────────────────────────┐
│            Pod                │
│  ┌──────┐  ┌──────┐  ┌────┐  │
│  │nginx │  │sidecar│  │log │  │
│  │容器   │  │容器   │  │容器│  │
│  └──────┘  └──────┘  └────┘  │
│  共享：IP+端口空间+Volume     │
│  Network Namespace (Pause容器控制) │
└───────────────────────────────┘
```

Pod里有一个**Pause容器**（也叫infra容器），它负责持有Pod的Network Namespace。其他容器加入这个NS，共享IP和端口。

**为什么需要Pause容器？** 因为进程挂了会导致Namespace销毁。Pause永远活着（啥也不干），确保Namespace稳定。

**哪些场景需要同一个Pod里的多个容器？**
- **Sidecar模式**：主容器+日志采集（如Filebeat）+ 监控（如Istio Envoy）
- **Proxy模式**：主容器+反向代理（如Nginx）
- **Adapter模式**：主容器+格式转换器

**Pod设计核心原则**：

> **一个Pod里的容器应该"共同扩缩容、共同调度到同一台机器"**。如果你觉得两个组件的生命周期可以独立管理，它们就应该拆成两个Pod。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-container-pod
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
  - name: sidecar
    image: busybox
    command: ["sh", "-c", "tail -f /var/log/nginx/access.log"]
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx
  volumes:
  - name: logs
    emptyDir: {}
```

> **常见问题**：Pod里的容器如何通信？
> **答**：互相访问 `localhost` 即可，因为它们共享Network Namespace。端口不能冲突。

---

## 第二章：Kubernetes架构总览

### 2.1 Control Plane：集群的大脑

Control Plane（控制面）负责决策和状态管理。通常有3个或5个节点（高可用），从不让运行用户业务Pod。

```
                    ┌─────────────────────┐
                    │    Control Plane    │
                    │                     │
                    │  ┌───────────────┐  │
         kubectl ───┼─▶│ kube-apiserver │──┼──▶ etcd（键值存储）
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────▼───────┐  │
                    │  │  kube-scheduler│  │
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────▼───────┐  │
            cloud ──┼─▶│kube-controller-│  │
            LB      │  │   manager     │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
```

#### kube-apiserver — 一切的门面

APIServer是K8s的唯一入口。所有组件、CLI、UI都通过HTTPS与它交互。它负责：
- **认证**：你是谁？（TLS证书、Token、用户名密码）
- **授权**：你能干什么？（RBAC、ABAC）
- **准入控制**：请求合法吗？（Admission Webhook）
- **持久化**：存etcd

> **一句话**：没有APIServer，K8s就死了。设计上它应该是**无状态、可水平扩展**的。

#### etcd — 真相的来源

etcd是K8s的"数据库"——一个分布式的、强一致性的键值存储。**所有集群状态都存在etcd里**：

```
/registry/
├── pods/
│   ├── default/my-app-abc123
│   └── kube-system/coredns-xyz789
├── deployments/
├── services/
├── secrets/
└── ...
```

**关键特征**：
- 基于Raft共识算法，保证强一致性
- 需要做定期快照备份（否则集群挂了就没了）
- 磁盘IO性能至关重要（建议SSD + 定期碎片整理）

```bash
# 备份etcd（每隔一小时）
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-snapshot-$(date +%Y%m%d-%H%M).db
```

#### kube-scheduler — 把Pod放到哪里？

Scheduler负责为新创建的Pod挑选合适的Node。决策流程：

1. **Predicates（过滤）**：排除不满足条件的Node（资源不足、端口冲突、taint不匹配）
2. **Priorities（打分）**：对剩余Node打分（资源利用率、亲和性规则、污点容忍）
3. **Binding（绑定）**：选择最高分Node，写回etcd

```bash
# 查看当前调度策略
kubectl describe pods <pod-name> | grep -A5 Events

# 手动设置节点调度
kubectl taint nodes node1 key=value:NoSchedule  # 不允许调度
kubectl taint nodes node1 key=value:NoExecute    # 驱逐已有Pod
```

#### kube-controller-manager — 确保"想要"等于"实际"

Controller Manager包含几十个控制器（Controller），每个关注一种资源，不断从"当前状态"趋近"期望状态"：

| 控制器 | 作用 |
|:---|:---|
| Node Controller | 检测节点健康，标记NotReady |
| ReplicaSet Controller | 确保Pod副本数匹配 |
| Deployment Controller | 管理Deployment的滚动更新 |
| Endpoint Controller | 更新Service的后端Pod列表 |
| Namespace Controller | 删除Namespace时清理所有资源 |
| ServiceAccount Controller | 自动创建默认ServiceAccount |
| ... | 还有几十个 |

每个控制器的逻辑都是一个**控制循环**（Reconciliation Loop）：

```
Observe(当前状态) → Diff(比较期望状态) → Act(执行变更)
```

> **排障技巧**：Deployment更新了但Pod没变？检查Deployment Controller和ReplicaSet Controller的日志：
> `kubectl logs -n kube-system kube-controller-manager-<node> --tail=50`

### 2.2 Worker Node：真正干活的地方

```
┌─────────────────────────────────────────┐
│           Worker Node (Node1)           │
│                                         │
│  ┌──────────┐  ┌───Pod──┐  ┌───Pod──┐  │
│  │  kubelet  │  │  nginx │  │  app   │  │
│  │  (agent)  │  └────────┘  └────────┘  │
│  └──────────┘                           │
│  ┌──────────┐  ┌─────────────────────┐  │
│  │ kube-proxy│  │  Container Runtime │  │
│  │ (网络规则) │  │  (containerd)      │  │
│  └──────────┘  └─────────────────────┘  │
└─────────────────────────────────────────┘
```

#### kubelet — 节点上的"监工"

kubelet是Node上最重要的组件。它做的事情：
1. **注册节点**：告诉APIServer"我来了"
2. **监听Pod分配**：Watch APIServer，看到分配给自己的新Pod
3. **启动容器**：调用CRI（containerd）拉镜像、创建容器
4. **健康检查**：定期执行liveness/readiness/startup probe
5. **上报状态**：持续更新Node/Pod状态到APIServer
6. **资源回收**：清理死亡的容器和未使用的镜像

```bash
# 查看kubelet日志
journalctl -u kubelet -f

# kubelet的配置文件
cat /var/lib/kubelet/config.yaml
```

**kubelet和APIServer的交互**：

```
kubelet ────Watch(/pods)────▶ APIServer
   ▲                              │
   │  发现分配给自己的Pod          │
   │                              ▼
   └───────────启动容器────────── containerd
         (通过CRI gRPC调用)
```

> **经典故障**：Pod一直Pending？可能scheduler没找到合适Node。Pod一直ContainerCreating？查kubelet和containerd日志。

#### kube-proxy — 网络规则守护者

kube-proxy实现了Service的**虚拟IP**路由。它有三种模式：

| 模式 | 原理 | 特点 |
|:---|:---|:---|
| **iptables** | 在每个Node创建iptables规则 | 简单稳定，但大规模效率低（O(n)） |
| **IPVS** | 使用内核IPVS模块 | 性能好（O(1)），支持更多调度算法 |
| **userspace** | 用户空间代理（已弃用） | 不推荐，仅历史原因保留 |

```bash
# 查看Node上的iptables规则（kube-proxy创建的）
iptables-save | grep KUBE-SVC

# 查看当前kube-proxy模式
kubectl get configmap -n kube-system kube-proxy -o yaml | grep mode
```

### 2.3 核心资源对象

K8s的API对象分为三类层次：

```
资源类型 → 资源实例（YAML） → 存储在etcd
```

先认识四个最核心的资源：

| 资源 | 作用 | 一句话 |
|:---|:---|:---|
| **Pod** | 最小的部署单元 | 一群共享资源的容器 |
| **Service** | 稳定的网络入口 | Pod的网络负载均衡 |
| **Deployment** | 声明式Pod管理 | 你告诉它"要几个"，它自动维持 |
| **Namespace** | 资源隔离边界 | 类似"项目"或"环境"的隔离 |

#### Namespace：逻辑上的"租户"

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
---
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  namespace: production  # 指定命名空间
```

**常见命令**：
```bash
# 创建Namespace
kubectl create namespace dev

# 在指定Namespace操作
kubectl get pods -n production

# 所有Namespace
kubectl get pods --all-namespaces
```

> **注意**：Namespace不能嵌套。跨Namespace访问需要通过Service的`<service>.<namespace>.svc.cluster.local`域名。

### 2.4 声明式API vs 指令式

这是K8s最核心的设计哲学，也是刚接触时最容易搞混的概念。

| 方式 | 命令示例 | 原理 |
|:---|:---|:---|
| **指令式** | `kubectl run nginx --image=nginx` | 一步直达目标 |
| **声明式** | `kubectl apply -f deployment.yaml` | 告诉系统期望状态，系统自行达到 |

**指令式的问题**：
```bash
# 你手动改了副本数
kubectl scale deployment nginx --replicas=5

# 别人重新apply了原文件
kubectl apply -f deployment.yaml  # 副本数变回3

# 为什么？因为apply用的是declarative——以文件中的期望状态为准
```

#### kubectl apply 到底发生了什么？

```
1. 你执行: kubectl apply -f deployment.yaml
          │
2. kubectl 读取deployment.yaml，转为JSON
          │
3. HTTPS POST → kube-apiserver
          │
4. apiserver: 认证 → 授权 → 准入(MutatingWebhook→验证)
          │
5. 写入etcd (如果已有该资源，做Merge Patch)
          │
6. kube-controller-manager里的Deployment Controller Watch到变更
          │
7. ReplicaSet Controller 开始创建Pod
          │
8. kube-scheduler 为新Pod分配Node
          │
9. Node上的kubelet Watch到Pod被分配给自己
          │
10. kubelet调用CRI → 拉镜像 → 启动容器
```

这个过程全部是**异步的**。这就是为什么你apply后Pod不会立刻Running——中间有几步异步操作。

**如何追踪整个过程？**
```bash
# 查看事件（按时间序）
kubectl get events -w

# 查看特定Pod的详细事件
kubectl describe pod my-app-7d4f8b9c6-abcde

# 实时Watch变化
kubectl get pods -w
```

> **实战经验**：排障时永远先 `kubectl describe` 看Events，绝大多数问题的线索都在Events里。

---

## 第三章：Pod与工作负载

Pod是K8s里最小的"可以干活"的单位，但你通常不会直接创建Pod——而是通过**工作负载（Workload）资源**来管理Pod。

```
工作负载（Deployment/StatefulSet/DaemonSet/Job）
   └── 管理
       ReplicaSet（确保Pod副本数）
          └── 创建/删除
              Pod（运行实际容器）
```

### 3.1 Pod生命周期

Pod从创建到结束经历以下状态：

```
                  ┌─── Succeeded（正常退出）
                  │
Pending → Running ─── CrashLoopBackOff（反复崩溃）
                  │
                  └─── Failed（非零退出码）
                      Unknown（与Kubelet失联）
```

| 状态 | 含义 | 排查方向 |
|:---|:---|:---|
| **Pending** | Pod已创建，但还没调度或镜像没拉完 | `kubectl describe pod` → Events，检查资源是否足够、调度策略 |
| **ContainerCreating** | 容器正在创建（拉镜像、配置存储） | 查kubelet日志、检查镜像仓库是否可访问 |
| **Running** | 至少一个容器已运行 | 正常状态 |
| **CrashLoopBackOff** | 容器反复崩溃，kubelet在退避重启 | `kubectl logs <pod> --previous` 看上次日志 |
| **Succeeded** | 所有容器正常退出（Job场景） | 正常 |
| **Failed** | 容器非零退出码 | `kubectl logs <pod>` 查退出原因 |
| **Unknown** | Kubelet失联，apiserver不确定Pod状态 | 检查Node是否宕机、网络是否断裂 |

#### 探针（Probe）—— K8s的"心跳"检测

kubelet在Pod运行期持续检查容器健康：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: health-check-demo
spec:
  containers:
  - name: app
    image: nginx
    # 存活检查：挂了就重启容器
    livenessProbe:
      httpGet:
        path: /healthz
        port: 80
      initialDelaySeconds: 5  # 启动后等5秒再检查
      periodSeconds: 10        # 每10秒检查一次
    # 就绪检查：不通过则Service不转发流量
    readinessProbe:
      httpGet:
        path: /ready
        port: 80
      initialDelaySeconds: 3
      periodSeconds: 5
    # 启动检查：慢启动应用的绿灯（v1.18+）
    startupProbe:
      httpGet:
        path: /startup
        port: 80
      failureThreshold: 30     # 允许30次失败（共60秒慢启动）
      periodSeconds: 2
```

> **实战坑**：livenessProbe设置得太激进（比如1秒就检查），启动慢的应用会反复重启。**readiness和liveness要分开考虑**——readiness是"能用不能用"，liveness是"死了没有"。

```bash
# 查看Pod的探测日志
kubectl describe pod <pod-name> | grep -A10 "Liveness"

# 手动进入Pod测试探针接口
kubectl exec -it <pod-name> -- curl localhost:8080/healthz
```

### 3.2 Init Containers与Sidecar模式

#### Init Containers：按顺序执行的前置任务

Init容器在主容器启动前按顺序执行，必须全部成功才能启动主容器。

**适用场景**：
- 等待外部依赖（等数据库就绪）
- 数据库迁移（schema migrate）
- 初始化文件权限/配置

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-container-demo
spec:
  initContainers:
  - name: wait-for-db
    image: busybox:1.28
    command: ['sh', '-c', 'until nc -z db-service 3306; do echo waiting for db; sleep 2; done']
  - name: run-migration
    image: migrate/migrate
    command: ['migrate', '-path', '/migrations', '-database', 'mysql://...', 'up']
    volumeMounts:
    - name: migrations
      mountPath: /migrations
  containers:
  - name: app
    image: myapp:latest
    ports:
    - containerPort: 8080
  volumes:
  - name: migrations
    configMap:
      name: db-migrations
```

> **注意**：Init容器如果失败，整个Pod重启（取决于restartPolicy）。Init容器不支持readiness/liveness探针。

#### Sidecar模式：给主容器"加料"

Sidecar是在同一个Pod里、与主容器并行运行的辅助容器。

| Sidecar类型 | 典型例子 | 作用 |
|:---|:---|:---|
| 日志采集 | Filebeat、Fluentd | 把日志推到ES/Loki |
| 网络代理 | Istio Envoy、Nginx | 服务网格数据面 |
| 监控采集 | Prometheus Exporter | 暴露自定义指标 |
| 配置同步 | configmap-reload | 配置变更自动热加载 |

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-with-sidecar
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: myapp:latest
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: logs
          mountPath: /var/log/app
      - name: filebeat
        image: docker.elastic.co/beats/filebeat:8.11.0
        volumeMounts:
        - name: logs
          mountPath: /var/log/app
          readOnly: true
        - name: filebeat-config
          mountPath: /usr/share/filebeat/filebeat.yml
          subPath: filebeat.yml
      volumes:
      - name: logs
        emptyDir: {}
      - name: filebeat-config
        configMap:
          name: filebeat-config
```

### 3.3 Deployment — 无状态应用的"自动驾驶"

Deployment是K8s里用得最多的工作负载资源。它做的事情：

1. **声明副本数** → ReplicaSet维持该数量
2. **滚动更新** → 逐步替换Pod，不中断服务
3. **回滚** → 出问题一键回退到旧版本
4. **自愈** → 节点挂了自动在其他Node重建Pod

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  labels:
    app: nginx
spec:
  replicas: 3                    # 期望3个副本
  selector:
    matchLabels:
      app: nginx
  strategy:
    type: RollingUpdate          # 滚动更新
    rollingUpdate:
      maxSurge: 1                # 允许多出1个Pod
      maxUnavailable: 0          # 不允许有Pod不可用（零停机）
  revisionHistoryLimit: 5        # 保留最近5个版本用于回滚
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.25.3
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "200m"
            memory: "256Mi"
```

#### ReplicaSet机制

Deployment不直接管理Pod，而是通过**ReplicaSet**来管理：

```
Deployment
  └── ReplicaSet-v1 (当前版本，副本数=3)
  │     └── Pod 1
  │     └── Pod 2
  │     └── Pod 3
  └── ReplicaSet-v2 (新版本，滚动中→最终副本数=3)
        └── Pod 4
        └── Pod 5
        └── Pod 6
```

```bash
# 查看Deployment下的ReplicaSet
kubectl get replicasets -l app=nginx

# 手动扩缩容（声明式！）
kubectl scale deployment nginx-deployment --replicas=5
```

#### 滚动更新与回滚

```bash
# 更新镜像版本（触发滚动更新）
kubectl set image deployment/nginx-deployment nginx=nginx:1.26.0

# 查看更新状态
kubectl rollout status deployment/nginx-deployment

# 暂停/继续更新
kubectl rollout pause deployment/nginx-deployment
kubectl rollout resume deployment/nginx-deployment

# 回滚到上一个版本
kubectl rollout undo deployment/nginx-deployment

# 回滚到指定版本
kubectl rollout undo deployment/nginx-deployment --to-revision=2

# 查看历史版本
kubectl rollout history deployment/nginx-deployment
```

**滚动更新的关键参数**：
- `maxSurge`：允许超出期望数的最大Pod数（可以是个数或百分比）。设为1意味着滚动中最多4个Pod（3+1）
- `maxUnavailable`：更新中允许不可用的最大Pod数。设为0意味着逐个更新，零停机

> **实战坑**：如果你设了 `maxUnavailable: 25%` + `replicas: 4`，滚动更新时可能有1个Pod不可用。对高可用服务，建议 `maxUnavailable: 0` 配合Pod的preStop钩子优雅关机。

### 3.4 StatefulSet — 有状态服务的"身份证"

Deployment假设所有Pod是"可互换的"——谁先死都无所谓。但数据库、缓存这类有状态服务不一样——每个实例有**唯一身份**。

```
StatefulSet
  └── my-app-0 (Pod名称固定，重启后不变)
  └── my-app-1
  └── my-app-2
```

**StatefulSet的三大特征：**

| 特征 | 说明 | 对比Deployment |
|:---|:---|:---|
| **稳定的网络标识** | Pod名称固定，重启后DNS不变 | Deployment的Pod名随机生成 |
| **稳定的持久化存储** | 每个实例绑定独立PV | Deployment共享或不绑定存储 |
| **有序的部署/伸缩** | 按序号从0到N-1逐步启动 | Deployment并发启动 |

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: "nginx"        # 必须关联一个Headless Service
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
        ports:
        - containerPort: 80
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html
  volumeClaimTemplates:       # 自动创建PVC
  - metadata:
      name: www
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

**DNS格式**：`<statefulset-name>-<ordinal>.<service-name>.<namespace>.svc.cluster.local`

```
web-0.nginx.default.svc.cluster.local
web-1.nginx.default.svc.cluster.local
web-2.nginx.default.svc.cluster.local
```

> **常见问题**：StatefulSet的Pod挂了一个，重建后数据还在吗？
> **答**：在！因为重建的是Pod，PV还在。StatefulSet的PVC不会随Pod删除，必须手动清理。

### 3.5 DaemonSet — 每个节点一个Pod

DaemonSet确保集群中**每个符合条件的Node**都运行一个Pod副本。新节点加入时自动创建，节点删除时自动回收。

**适用场景**：
- 日志采集（Fluentd/Filebeat）
- 节点监控（Node Exporter）
- 网络插件（Calico/Flannel代理）
- 存储插件（CSI驱动）

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd-elasticsearch
  namespace: kube-system
spec:
  selector:
    matchLabels:
      name: fluentd-es
  template:
    metadata:
      labels:
        name: fluentd-es
    spec:
      tolerations:
      - key: node-role.kubernetes.io/master
        effect: NoSchedule
      containers:
      - name: fluentd-es
        image: quay.io/fluentd_elasticsearch/fluentd:v4.6.0
        resources:
          limits:
            memory: 500Mi
          requests:
            cpu: 100m
            memory: 200Mi
        volumeMounts:
        - name: varlog
          mountPath: /var/log
        - name: dockercontainers
          mountPath: /var/lib/docker/containers
          readOnly: true
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
      - name: dockercontainers
        hostPath:
          path: /var/lib/docker/containers
```

```bash
# 查看DaemonSet部署情况
kubectl get daemonsets -n kube-system
kubectl get pods -n kube-system -o wide | grep fluentd
```

### 3.6 Job/CronJob — 跑一次就走的任务

#### Job：一次性批处理

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: pi-calc
spec:
  completions: 3       # 共需要成功3次
  parallelism: 2       # 最多同时跑2个
  backoffLimit: 4      # 重试上限4次
  template:
    spec:
      containers:
      - name: pi
        image: perl:5.34
        command: ["perl", "-Mbignum=bpi", "-wle", "print bpi(2000)"]
      restartPolicy: Never  # Job的restartPolicy不能是Always
```

#### CronJob：定时执行

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-db
spec:
  schedule: "0 2 * * *"      # 每天凌晨2点执行（Cron表达式）
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: mysql:8.0
            command: ["mysqldump", "--all-databases", "-u", "root", "-p$MYSQL_ROOT_PASSWORD"]
            env:
            - name: MYSQL_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: password
          restartPolicy: OnFailure
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
```

```bash
# Job操作
kubectl get jobs
kubectl logs job/pi-calc
kubectl delete job pi-calc

# CronJob操作
kubectl get cronjobs
kubectl describe cronjob backup-db
kubectl create job --from=cronjob/backup-db manual-backup-001  # 手动触发一次
```

### 3.7 Pod资源管理：requests/limits → QoS类

K8s通过两个参数控制Pod的资源使用：

| 参数 | 含义 | 调度时 | 运行时 |
|:---|:---|:---|:---|
| **requests** | 保证的最小资源 | Scheduler以此计算Node容量 | CPU保证调度权，内存保证可用 |
| **limits** | 上限值 | 不影响调度 | CPU可超限（throttle），内存超限则OOM |

CPU是可压缩资源（超限了被throttle，但进程不挂）；内存是不可压缩资源（超限就OOM）。

#### QoS类：三种优先级

K8s根据requests/limits的匹配程度，给Pod打上QoS类。Node内存不足时**按QoS优先级逐出Pod**。

| QoS类 | 条件 | 逐出优先级 | 典型用途 |
|:---|:---|:---:|:---|
| **Guaranteed** | requests = limits（所有容器） | 最低（最安全） | 数据库、核心服务 |
| **Burstable** | 至少一个容器requests < limits | 中等 | 一般Web服务 |
| **BestEffort** | 不设requests和limits | 最高（最先被Kill） | 批处理、临时任务 |

```yaml
# Guaranteed — 最稳
resources:
  requests:
    cpu: "1"
    memory: "512Mi"
  limits:
    cpu: "1"
    memory: "512Mi"

# Burstable — 一般服务
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
  limits:
    cpu: "1"
    memory: "512Mi"

# BestEffort — 有啥用啥（不设资源限制）
# 不写resources字段，或者只写limits不写requests也变成BestEffort
```

```bash
# 查看Pod的QoS等级
kubectl describe pod <pod-name> | grep QoS

# Node资源压力时的驱逐排序
# BestEffort → Burstable → Guaranteed
# 同QoS内按资源使用比例排序
```

> **实战建议**：生产环境的核心服务务必设为Guaranteed，Web服务用Burstable，CI任务用BestEffort。**不要在生产用BestEffort**，Node一紧张它们的Pod先死。

---

## 第四章：网络与存储

### 4.1 CNI模型：Pod间如何通信？

K8s对网络有两个硬性要求：
1. **所有Pod可以直接通信**（不需要NAT）
2. **所有Node可以直接与Pod通信**（一对一）

这就需要一个扁平网络——**CNI（Container Network Interface）** 就是实现这个的插件规范。

#### CNI的工作流程

```
1. kubelet → CRI → containerd → CNI plugin (二进制定时)
2. 给Pod分配IP（从CNI管理的IP池）
3. 创建veth pair（一头连Pod，一头连主机的cni网桥）
4. 配置路由/封装（取决于CNI实现）
```

#### Flannel vs Calico

| 特性 | Flannel | Calico |
|:---|:---|:---|
| **数据面** | VXLAN（UDP封装）| BGP+iptables/eBPF |
| **网络模型** | Overlay Network | 纯三层网络 |
| **性能** | 有封装开销（~10-15%）| 接近原生网络 |
| **安全策略** | ❌ 不支持NetworkPolicy | ✅ 原生支持 |
| **部署复杂度** | 简单 | 中等 |
| **典型场景** | 小集群、需求简单 | 生产、需要网络隔离 |

```bash
# 查看集群使用什么CNI
kubectl get pods -n kube-system | grep -E 'calico|flannel|weave|cilium'

# 查看CNI配置文件
cat /etc/cni/net.d/*.conf

# Calico查看IP池
calicoctl get ippool
```

> **常见问题**：Pod能访问同Node的其他Pod，但跨Node不行？大概率是CNI的路由规则没配好，检查Node之间的VXLAN或BGP配置。

### 4.2 Service类型

Pod的IP是临时的——重启就变。Service提供了**稳定的访问入口**。

#### ClusterIP（默认）— 集群内部可访问

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: ClusterIP
  selector:
    app: nginx          # 关联哪些Pod
  ports:
  - port: 80            # Service端口
    targetPort: 8080    # Pod端口
    protocol: TCP
```

#### NodePort — 节点端口对外暴露

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: NodePort
  selector:
    app: nginx
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080
```

集群外访问：`http://<任意NodeIP>:30080`

#### LoadBalancer — 云厂商LB集成

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  type: LoadBalancer
  selector:
    app: nginx
  ports:
  - port: 80
    targetPort: 8080
```

#### ExternalName — DNS级别的别名

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-db
spec:
  type: ExternalName
  externalName: mydb.example.com
```

#### Headless Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: headless-svc
spec:
  clusterIP: None
  selector:
    app: stateful-app
```

```bash
# 测试Service DNS解析
kubectl run -it --rm dnsutils --image=gcr.io/kubernetes-e2e-test-images/dnsutils:1.3 -- nslookup my-service

# 查看Service的后端端点
kubectl get endpoints my-service
```

### 4.3 Ingress与Gateway API

Service是四层（TCP/UDP）负载均衡。Ingress是七层（HTTP/HTTPS）的路由器。

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
  tls:
  - hosts:
    - app.example.com
    secretName: example-tls
```

**Gateway API**是K8s v1.28+引入的新一代入口标准，比Ingress更强大、更灵活（支持TCP/UDP/gRPC、跨Namespace路由等）。

### 4.4 DNS解析：CoreDNS

K8s集群内的DNS由**CoreDNS**提供。

**Pod的DNS解析规则**：`<service>.<namespace>.svc.cluster.local`

```bash
# 查看CoreDNS配置
kubectl get configmap -n kube-system coredns -o yaml

# 测试DNS
kubectl run test-pod --rm -it --image=busybox:1.28 -- nslookup kubernetes.default
```

### 4.5 存储卷

Docker容器的文件系统是临时的（容器删除数据就没了）。K8s通过**卷（Volume）**提供持久化存储。

#### emptyDir — 同Pod内容器共享

```yaml
volumes:
- name: cache-volume
  emptyDir:
    sizeLimit: 500Mi
```

#### hostPath — 挂载Node目录

```yaml
volumes:
- name: host-log
  hostPath:
    path: /var/log/app
    type: DirectoryOrCreate
```

#### PV/PVC/StorageClass — 真正的持久化

K8s的存储抽象分三层：

| 组件 | 谁定义 | 作用 |
|:---|:---|:---|
| **PV** (PersistentVolume) | 管理员 | 物理存储（NFS、Ceph、云盘） |
| **PVC** (PersistentVolumeClaim) | 用户 | 申请存储（多少空间、什么访问模式） |
| **StorageClass** | 管理员 | 自动创建PV的模板（动态供应） |

```yaml
# StorageClass（动态供应）
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  fsType: ext4
---
# PVC（用户申请）
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  storageClassName: fast-ssd
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
# Pod使用
apiVersion: v1
kind: Pod
metadata:
  name: app-with-pvc
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data-pvc
```

**访问模式**：ReadWriteOnce (RWO)、ReadOnlyMany (ROX)、ReadWriteMany (RWX)

```bash
kubectl get pv
kubectl get pvc
kubectl get storageclass
kubectl describe pvc data-pvc
```

> **常见问题**：Pod启动后显示FailedMount？大概率是CSI驱动没部署或存储后端没配好。查kubectl describe pod看Mount Events。

---

## 第五章：配置与安全

### 5.1 ConfigMap与Secret管理

K8s的设计原则之一是**把配置从应用镜像中剥离**。ConfigMap和Secret就是做这个的。

#### ConfigMap — 非敏感配置

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_ENV: production
  APP_DEBUG: "false"
  nginx.conf: |
    server {
      listen 80;
      server_name example.com;
      location / {
        proxy_pass http://backend:8080;
      }
    }
```

**三种挂载方式：**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: configmap-demo
spec:
  containers:
  - name: app
    image: nginx
    env:
    - name: APP_ENV
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: APP_ENV
    envFrom:
    - configMapRef:
        name: app-config
    volumeMounts:
    - name: config
      mountPath: /etc/nginx/conf.d
  volumes:
  - name: config
    configMap:
      name: app-config
```

#### Secret — 敏感配置

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
data:
  username: YWRtaW4=            # echo -n "admin" | base64
  password: cGFzc3dvcmQxMjM=
---
apiVersion: v1
kind: Pod
metadata:
  name: secret-demo
spec:
  containers:
  - name: app
    image: nginx
    env:
    - name: DB_USER
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: username
    - name: DB_PASS
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
```

```bash
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=password123

kubectl get secret db-secret -o yaml
echo "YWRtaW4=" | base64 -d
```

> **安全要点**：Base64不是加密！只是编码。生产环境建议使用外部Secrets管理方案（如Vault、Sealed Secrets、External Secrets Operator）。

### 5.2 ServiceAccount：JWT令牌与RBAC

ServiceAccount是Pod在K8s中的"身份"。每个Pod被创建时，会自动挂载一个ServiceAccount的Token。

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "watch", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-sa-pod-reader
subjects:
- kind: ServiceAccount
  name: app-sa
  namespace: default
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

**RBAC的三个要素**：
- **Subject**：谁？（User、Group、ServiceAccount）
- **Resource**：对什么？（pods、services、deployments）
- **Verb**：做什么？（get、list、create、update、delete、watch）

```bash
# 验证Pod中的Token
kubectl exec <pod> -- cat /var/run/secrets/kubernetes.io/serviceaccount/token

# 用Token调用API
kubectl exec <pod> -- curl -k \
  -H "Authorization: Bearer $(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" \
  https://kubernetes.default.svc/api/v1/namespaces/default/pods
```

**RBAC最佳实践**：
```
❌ 不要用cluster-admin
❌ 不要创建不必要的ServiceAccount
✅ 最小权限原则：只给需要的操作
✅ 每个应用使用专用ServiceAccount，不共享
```

### 5.3 Pod Security Standard

K8s v1.25+使用**Pod Security Admission**来定义Pod的安全等级。

| 等级 | 说明 | 典型禁止 |
|:---|:---|:---|
| **Privileged** | 无限制 | 基本没有禁止 |
| **Baseline** | 最低限制（推荐） | 特权容器、hostPID |
| **Restricted** | 严格限制 | 添加capabilities、非只读rootfs |

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: secure-ns
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: baseline
```

```yaml
# Restricted级别的Pod声明
apiVersion: v1
kind: Pod
metadata:
  name: restricted-pod
  namespace: secure-ns
spec:
  securityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: nginx
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
      readOnlyRootFilesystem: true
```

### 5.4 NetworkPolicy控制流量

默认情况下，K8s允许所有Pod互相通信。NetworkPolicy用来**限制Pod间的网络流量**。

> **注意**：NetworkPolicy需要CNI支持（Calico支持，Flannel默认不支持）。

```yaml
# 拒绝所有入站流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
spec:
  podSelector: {}
  policyTypes:
  - Ingress
---
# 只允许frontend访问backend的3306端口
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-fe-to-be
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 3306
```

> **实战建议**：生产环境使用"默认拒绝所有"的策略，然后显式开放需要的通信。

---

## 第六章：日常运维命令

### 6.1 kubectl debug：临时调试容器

K8s v1.18+引入了 `kubectl debug`，可以在运行中的Pod旁启动一个临时调试容器。

```bash
# 在现有Pod旁启动一个调试容器（共享Network）
kubectl debug my-pod -it --image=nicolaka/netshoot

# 创建临时Pod复制并执行命令
kubectl debug my-pod -it --copy-to=debug-pod --image=ubuntu -- bash

# 在Node上调试（共享主机的PID Namespace）
kubectl debug node/node1 -it --image=ubuntu -- bash
```

**netshoot排障神器**，内置了：curl, wget, dig, nslookup, nmap, tcpdump, iperf, ss, traceroute, mtr, ping, telnet, nc, jq, grpcurl

```bash
# 手动启动netshoot Pod
kubectl run netshoot --image=nicolaka/netshoot --rm -it -- /bin/bash
```

### 6.2 kubectl exec/logs/describe/top

```bash
# 进入Pod
kubectl exec -it <pod-name> -- /bin/sh

# 进入多容器Pod的特定容器
kubectl exec -it <pod-name> -c <container-name> -- bash

# 实时跟随日志
kubectl logs -f <pod-name>

# 查看上次运行的日志（CrashLoopBackOff时特别有用）
kubectl logs <pod-name> --previous

# 多容器Pod指定容器
kubectl logs -f <pod-name> -c sidecar

# 查看详情（Events段信息量最大）
kubectl describe pod <pod-name>
kubectl describe node <node-name>

# Pod的实时CPU/Memory
kubectl top pod
kubectl top node
kubectl top pod --sort-by=cpu
kubectl top pod --sort-by=memory
```

### 6.3 Pod日志轮转与持久化

**kubelet配置日志轮转**（在Node的kubelet配置中）：

```json
{
  "containerLogMaxSize": "10Mi",
  "containerLogMaxFiles": 5
}
```

```bash
# 查看哪些Pod日志大
du -sh /var/log/pods/*/ | sort -rh | head -10

# 直接清理日志
truncate -s 0 /var/log/pods/<namespace>_<pod>/<container>/0.log
```

### 6.4 节点维护：cordon/drain/uncordon

```bash
# 1. 标记节点为不可调度
kubectl cordon node-1

# 2. 驱逐节点上的Pod
kubectl drain node-1 --ignore-daemonsets --delete-emptydir-data

# 3. 做维护操作（重启、升级内核、换硬盘...）

# 4. 恢复节点
kubectl uncordon node-1
```

**节点维护标准流程**：`cordon → drain → 维护操作 → uncordon`

> **实战经验**：节点维护前先 `kubectl top node` 确认集群资源充裕。如果集群资源紧张，drain后Pod可能Pending。

---

## 总结与下一课预告

### 本课核心地图

```
用户视角（kubectl）
  │
  ▼
kube-apiserver（唯一入口）
  │
  ├── etcd（集群状态存储）
  ├── kube-scheduler（Pod→Node）
  ├── kube-controller-manager（各种Controller）
  │
  ▼
kubelet（Worker Node守护进程）
  │
  ├── containerd（容器运行时）
  ├── CNI插件（Pod网络）
  ├── CSI插件（持久化存储）
  └── kube-proxy（Service路由）
```

### 关键思维模型

1. **声明式API思维**："告诉系统你想要什么状态，不要告诉它怎么做"
2. **控制循环**：Observe → Diff → Act，所有Controller都遵循这个模式
3. **Pod是最小单位**：共享Namespace的容器组，而不是单个容器
4. **抽象分层**：K8s通过Service、Ingress、PV/PVC层层抽象

### 技能清单

| ✅ | 技能 |
|:---:|:---|
| ✅ | 理解容器运行时（Docker/containerd/CRI-O）的区别 |
| ✅ | 知道Namespace和CGroup的原理 |
| ✅ | 理解Pod的本质 |
| ✅ | 能画出K8s Control Plane和Worker Node的架构图 |
| ✅ | 知道kubectl apply的完整流程 |
| ✅ | 会写基本的Deployment、Service YAML |
| ✅ | 理解Pod生命周期和探针 |
| ✅ | 区分Deployment、StatefulSet、DaemonSet、Job的用途 |
| ✅ | 理解requests/limits和QoS |
| ✅ | 知道CNI、Service、Ingress的基本原理 |
| ✅ | 会使用ConfigMap和Secret |
| ✅ | 理解ServiceAccount和RBAC |
| ✅ | 会用kubectl exec/logs/describe/top |
| ✅ | 知道如何安全地维护节点 |

### 下一课预告

**K8s/云原生运维 #2：集群部署与生产化配置**

我们将亲手搭建一个三节点的生产级K8s集群，内容包括：
- 使用kubeadm部署集群（从零到集群搭建完成）
- containerd运行时配置与镜像仓库镜像
- CNI插件安装（Calico BGP模式）
- 集群证书管理与轮换
- Ingress Controller（Nginx Ingress）部署
- metrics-server与集群监控
- 集群备份与恢复（etcd快照）
- 生产环境的最优配置清单

---

*本系列文章由Kai编写，遵循CC BY-NC 4.0协议。欢迎学习交流，但请勿商用。*
