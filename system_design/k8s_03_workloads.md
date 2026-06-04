# K8s/云原生 #3：Deployment、StatefulSet 与 DaemonSet

> 2026-05-17
> 前置：Pod 深度解析 #2

## 1. Workload 控制器对比

K8s 提供 4 种核心 Workload 控制器：

| 控制器 | 适用场景 | Pod 特性 |
|--------|---------|----------|
| **Deployment** | 无状态服务（Web API、微服务） | 任意替换，不关心身份 |
| **StatefulSet** | 有状态服务（DB、消息队列） | 稳定网络标识 + 持久存储 |
| **DaemonSet** | 节点级服务（日志/监控/网络） | 每个节点一个 Pod |
| **Job/CronJob** | 批处理（ETL、ML训练、数据迁移） | 运行到完成 |

## 2. Deployment

### 2.1 核心设计

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deploy
spec:
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
```

三个关键组件：
- **ReplicaSet** — 保持指定数量的 Pod 运行
- **Pod Template** — Pod 的模板定义
- **滚动更新机制** — 控制版本切换策略

### 2.2 更新策略

```yaml
spec:
  strategy:
    type: RollingUpdate      # 默认：滚动更新
    rollingUpdate:
      maxSurge: 1            # 更新中最多超量 1 个 Pod
      maxUnavailable: 0      # 更新时必须可用 Pod 不少于 3 个
```

**maxSurge** — 更新中允许多于期望数量的 Pod 数（可以是绝对数或百分比）
**maxUnavailable** — 更新中允许不可用 Pod 数

### 2.3 回滚

```bash
kubectl rollout undo deployment/nginx-deploy          # 回滚到上一版本
kubectl rollout undo deployment/nginx-deploy --to-revision=2  # 回滚到指定版本
kubectl rollout history deployment/nginx-deploy        # 查看版本历史
```

Deployment 会保留 .spec.revisionHistoryLimit 个版本的 ReplicaSet。

### 2.4 暂停与恢复

```bash
kubectl rollout pause deployment/nginx-deploy    # 暂停更新（可做金丝雀）
kubectl set image deployment/nginx-deploy nginx=nginx:1.26  # 先改一部分？
kubectl rollout resume deployment/nginx-deploy   # 恢复更新
```

## 3. StatefulSet

### 3.1 与 Deployment 的核心区别

| | Deployment | StatefulSet |
|---|-----------|-------------|
| Pod 名 | 随机后缀（nginx-7d8b...） | 序号名（web-0, web-1, web-2）|
| 网络标识 | 换 IP | 稳定 DNS（web-0.nginx.default.svc）|
| 存储 | 共享或临时 | 每 Pod 独立 PVC |
| 启停顺序 | 随机 | 有序（0→N 启动，N→0 停止）|
| 扩容收缩 | 任意 | 顺序推进+等待 |

### 3.2 定义

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: web
spec:
  serviceName: "nginx"
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
        image: nginx
        volumeMounts:
        - name: www
          mountPath: /usr/share/nginx/html
  volumeClaimTemplates:      # 🔑 自动生成 PVC
  - metadata:
      name: www
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

**volumeClaimTemplates** — 每个 Pod 自动获得独立的 PVC（web-0 的 pvc-xxx，web-1 的 pvc-yyy）。

### 3.3 有状态服务最佳实践

```
StatefulSet 适合：
  ✅ 数据库（MySQL/PostgreSQL 主从）
  ✅ 消息队列（Kafka/ZooKeeper）
  ✅ 分布式协调（etcd/Consul）
  ✅ 需要固定网络标识的服务

不适合：
  ❌ 无状态应用（用 Deployment）
  ❌ 每个节点都需要一个的（用 DaemonSet）
```

常见 Operator（自动管理复杂有状态应用）：
- **Prometheus Operator** — 监控
- **Kafka Operator**（Strimzi）
- **MySQL Operator**（Kubedb / Presslabs）
- **etcd Operator**

## 4. DaemonSet

### 4.1 定义与场景

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
spec:
  selector:
    matchLabels:
      name: fluentd
  template:
    metadata:
      labels:
        name: fluentd
    spec:
      tolerations:        # 容忍所有污点，确保覆盖所有节点
      - operator: Exists
      containers:
      - name: fluentd
        image: fluent/fluentd
```

典型场景：
- **日志收集**：每个节点跑 fluentd/filebeat 收集容器日志
- **监控采集**：每个节点跑 node-exporter 暴露指标
- **网络代理**：每个节点跑 kube-proxy / Cilium agent / Istio 的 envoy
- **存储插件**：每个节点跑 CSI 驱动

### 4.2 滚动更新

```yaml
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1      # 一次只更新 1 个节点
```

默认用 maxUnavailable=1 的 RollingUpdate，避免全部节点同时重启。

## 5. Job / CronJob

### 5.1 Job（一次性任务）

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: pi
spec:
  completions: 4              # 需要 4 个 Pod 成功才算完成
  parallelism: 2              # 最多同时运行 2 个 Pod
  backoffLimit: 3             # 失败重试次数
  template:
    spec:
      containers:
      - name: pi
        image: perl
        command: ["perl", "-Mbignum=bpi", "-wle", "print bpi(2000)"]
      restartPolicy: Never
```

| 参数 | 作用 |
|------|------|
| completions | 需要的成功 Pod 数（默认 1） |
| parallelism | 并行度（默认 1） |
| backoffLimit | 失败重试（默认 6） |
| activeDeadlineSeconds | 任务整体超时 |
| ttlSecondsAfterFinished | 完成后自动清理 |

### 5.2 CronJob（定时任务）

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: report
spec:
  schedule: "0 9 * * 1"         # 每周一 9:00
  startingDeadlineSeconds: 60   # 最长启动延迟
  concurrencyPolicy: Forbid     # 禁止并发执行
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: report
            image: my-report
            command: ["python", "gen_report.py"]
          restartPolicy: OnFailure
```

## 6. 实战选择决策树

```
需要固定网络标识 + 持久存储？
  → StatefulSet

每个节点都需要一个？
  → DaemonSet

运行到结束（批处理）？
  → Job / CronJob

其余全部 → Deployment
```

## 总结

```
Deployment  = 无状态工作的瑞士军刀
StatefulSet = 有状态服务的保险箱
DaemonSet   = 节点级工作的影子
Job         = 批处理的沙漏
```
