# K8s/云原生 #2：Pod 深度解析与容器生命周期

> 2026-05-17
> 前置：K8s 架构基础 #1

## 1. Pod 的本质

Pod 是 K8s 最小的调度和执行单元，不是一个容器，而是一个或多个容器的**共享沙箱**。

### 1.1 共享资源

同一个 Pod 内的容器共享：

```
Linux 网络命名空间 → localhost 通信（端口需协调）
IPC 命名空间       → 共享内存 / 信号量
UTS 命名空间       → 共享 hostname
存储卷（Volumes）   → 共享文件系统目录

彼此隔离的：
PID 命名空间       → 默认隔离（可开启 shareProcessNamespace）
挂载命名空间       → 各自文件系统
```

这意着同一 Pod 中的容器通过 `localhost:port` 通信。

### 1.2 设计原则

```
单 Pod ≠ 单容器
         = 单进程（一个主容器运行一个进程）
         = 多个辅助容器（Sidecar），扩展主容器的能力

最佳实践：
  ✅ 一个 Pod 一个主容器 + 辅助 Sidecar
  ✅ 强耦合服务放同 Pod（Proxy + App, Log Collector + App）
  ❌ 微服务放同 Pod（应该独立 Pod+Service）
  ❌ 不同生命周期管理的东西放同 Pod
```

### 1.3 Sidecar 模式

常见 Sidecar 场景：
- **日志收集** — 主容器写日志到共享 Volume，Sidecar 读取并发送到 ELK
- **网络代理** — Istio Envoy 作为 Sidecar 代理所有进出流量
- **配置热更新** — Sidecar 监控 ConfigMap 变化，动态 reload 主容器
- **健康检测代理** — 针对不原生支持健康检查的应用做适配

## 2. 容器生命周期管理

### 2.1 健康检查（Probe）

K8s 提供三种探测：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: health-check-demo
spec:
  containers:
  - name: app
    image: nginx
    livenessProbe:      # 🟢 存活探测：容器是否活着
      httpGet:
        path: /healthz
        port: 80
      initialDelaySeconds: 3   # 启动后等 3 秒再检查
      periodSeconds: 10        # 每 10 秒检查一次
      timeoutSeconds: 1        # 超时 1 秒算失败
      failureThreshold: 3      # 连续 3 次失败 → 重启
    readinessProbe:     # 🔵 就绪探测：容器能否接受流量
      tcpSocket:
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
    startupProbe:       # 🟠 启动探测：慢启动应用专用
      httpGet:
        path: /startup
        port: 3000
      failureThreshold: 30     # 允许 30 次失败（30×10=300s 等待启动）
      periodSeconds: 10
```

| 探测 | 失败后果 | 典型应用 |
|------|---------|---------|
| livenessProbe | 重启容器 | 检测死锁/内存泄漏 |
| readinessProbe | 从 Service 端点移除 | 检测热点/慢启动 |
| startupProbe | 延迟其他探测 | 需要 60s+ 启动的应用 |

### 2.2 钩子（Lifecycle Hooks）

```yaml
spec:
  containers:
  - name: app
    lifecycle:
      postStart:    # 容器创建后立即执行
        exec:
          command: ["/bin/sh", "-c", "echo Container started > /tmp/status"]
      preStop:      # 容器停止前执行（优雅关闭）
        httpGet:
          path: /shutdown
          port: 8080
```

**postStart 注意**：和容器的 ENTRYPOINT 是**异步并行**执行的，不要用它来做初始化完毕的信号。

**preStop 关键**：K8s 发给 Pod SIGTERM，等 terminationGracePeriodSeconds（默认 30s），超时强行 SIGKILL。

## 3. Pod 的调度与资源

### 3.1 资源限制

```yaml
spec:
  containers:
  - name: app
    resources:
      requests:          # 🟢 调度保障（最小需求）
        cpu: "0.5"       # 500m（500 milli CPU）
        memory: "256Mi"
      limits:            # 🔴 上限（CGroup 限制）
        cpu: "1"         # 1000m（1 核）
        memory: "512Mi"
```

| 资源 | requests | limits |
|------|----------|--------|
| CPU | 调度决定权（确保拿到） | CFS 配额（超限节流不发 OOM） |
| 内存 | 调度决定权（确保拿到） | OOM Killer（超限直接被杀） |

**不设 limits 的风险**：Pod 可能耗尽节点资源，导致同节点其他 Pod OOM。

### 3.2 QoS 等级

资源定义决定 Pod 的服务质量等级：

| QoS | 条件 | OOM 优先级 | 驱逐优先级 |
|-----|------|-----------|-----------|
| **Guaranteed** | requests=limits（所有容器） | 最低 | 最低 |
| **Burstable** | 至少一个容器有 requests≠limits | 中 | 中 |
| **BestEffort** | 无 requests 和 limits | 最高 | 最高（最先被杀） |

### 3.3 节点选择

```yaml
spec:
  nodeSelector:          # 🔵 硬性约束：必须匹配 label
    disk: ssd
  
  affinity:              # 🟢 软性约束：优先但不强制
    nodeAffinity:
      preferredDuringScheduling:
      - weight: 100
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values: ["us-east-1"]

  tolerations:           # 🟡 容忍污点
  - key: "special"
    operator: "Exists"
    effect: "NoSchedule"
```

## 4. Init 容器

Init 容器在 Pod 主容器启动前**串行执行**，全部成功后才启动主容器：

```yaml
spec:
  initContainers:
  - name: init-db
    image: busybox
    command: ['sh', '-c', 'until nc -z db-service 5432; do echo waiting for db; sleep 2; done']
  - name: init-config
    image: busybox
    command: ['sh', '-c', 'cp /config/* /app-config/']
    volumeMounts:
    - name: config
      mountPath: /app-config
  containers:
  - name: app
    image: my-app
```

用例：等待依赖服务就绪、预热缓存、拉取配置、数据库迁移。

## 5. 静态 Pod 与裸 Pod

### 5.1 静态 Pod

由 **kubelet 直接管理**的 Pod，不经过 API Server：

```
配置文件路径：/etc/kubernetes/manifests/
              （由 kubelet --pod-manifest-path 指定）
适用：控制面组件（etcd、apiserver、controller-manager、scheduler）
```

kubelet 自动检测 manifest 目录的变化（创建/删除/修改），无需 API Server 参与。

### 5.2 裸 Pod（Controller 管理）

```yaml
# ❌ 不要直接创建 Pod
apiVersion: v1
kind: Pod
# ...

# ✅ 通过 Controller 管理
apiVersion: apps/v1
kind: Deployment
# ...
```

裸 Pod 不会在节点故障时自动恢复 —— 一定要通过 Deployment/DaemonSet/StatefulSet 等 Controller 创建。

## 6. 排毒经验

1. **CrashLoopBackOff** → 看 `kubectl logs <pod> --previous`，通常是启动配置错
2. **ImagePullBackOff** → 镜像名错 / 私有仓库凭据过期 / 网络不通
3. **Pending** → `kubectl describe pod <pod>`，找 Events，通常是资源不足
4. **OOMKilled** → 调大 limits 或优化内存使用
5. **RunContainerError** → 存储卷挂载失败常见的

## 总结

```
Pod = 共享沙箱，最小调度单元
健康检查 = liveness(活) + readiness(就绪) + startup(慢启动)
生命周期 = postStart(创) + preStop(停) + terminationGracePeriod(宽限)
资源 = requests(调度) + limits(上限) ⇒ QoS 等级
Init 容器 = 串行前置任务
静 Pod = kubelet 直接管理
```
