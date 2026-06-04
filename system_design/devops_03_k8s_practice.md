# DevOps #3：Kubernetes 实操

> 2026-05-17
> 前置：Docker #2

## 1. 什么时候需要 K8s

```
Docker Compose 够用的情况（< 5 个服务）：
  微服务数量很少
  全部在一台机器上
  不需要自动伸缩
  不需要滚动更新

需要 K8s 的情况：
  多台机器（集群）
  服务需要自动伸缩
  零停机更新/回滚
  跨机器的服务发现
  配置/密钥统一管理

量化系统的实际评估：
  当前：单个 5070Ti → Docker Compose 完全够用
  未来：多台机器做分布式参数搜索 → K8s
  最需要 K8s 的功能：批量跑回测 Job
```

## 2. K8s 核心概念

```
Cluster（集群）
  ├── Control Plane（控制面）
  │   ├── API Server（入口，REST）
  │   ├── Scheduler（调度到哪个节点）
  │   ├── Controller Manager（维持期望状态）
  │   └── etcd（分布式 KV 存储，存集群状态）
  │
  └── Nodes（工作节点）
      ├── kubelet（与 API Server 通信）
      ├── kube-proxy（网络规则）
      └── Container Runtime（containerd/docker）

Pod = 最小部署单元（1+N 个容器）
Service = 稳定的网络端点
Deployment = 声明式 Pod 管理
ConfigMap / Secret = 配置和密钥
```

## 3. 量化系统的 K8s 资源

### 3.1 Pod

```yaml
# pod-quant-monitor.yaml
apiVersion: v1
kind: Pod
metadata:
  name: quant-monitor
  labels:
    app: quant
    component: monitor
spec:
  containers:
  - name: monitor
    image: quant-engine:latest
    command: ["python", "src/monitor.py"]
    resources:
      requests:
        memory: "512Mi"
        cpu: "0.5"
      limits:
        memory: "2Gi"
        cpu: "2"
    env:
    - name: LOG_LEVEL
      value: "INFO"
    - name: FEISHU_WEBHOOK
      valueFrom:
        secretKeyRef:
          name: quant-secrets
          key: feishu_webhook
    volumeMounts:
    - name: config
      mountPath: /app/config
      readOnly: true
    - name: data
      mountPath: /app/data
  volumes:
  - name: config
    configMap:
      name: quant-config
  - name: data
    persistentVolumeClaim:
      claimName: quant-data-pvc
```

### 3.2 Deployment（推荐替代裸 Pod）

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quant-monitor
spec:
  replicas: 1  # 监控服务只需要 1 个副本（避免重复信号）
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0   # 更新时至少 1 个 Pod 在运行
      maxSurge: 1          # 允许额外 1 个临时 Pod
  selector:
    matchLabels:
      app: quant
      component: monitor
  template:
    metadata:
      labels:
        app: quant
        component: monitor
    spec:
      containers:
      - name: monitor
        image: quant-engine:v2.0.0-20260517
        ports:
        - containerPort: 8000
          name: http
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

**滚动更新**：`kubectl set image deployment/quant-monitor quant-engine=quant-engine:v2.0.1`

### 3.3 Service（服务发现）

```yaml
apiVersion: v1
kind: Service
metadata:
  name: quant-monitor-svc
spec:
  selector:
    app: quant
    component: monitor
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP  # 集群内部访问
```

其他服务通过 `http://quant-monitor-svc:80` 访问 monitor。

### 3.4 ConfigMap & Secret

```yaml
# ConfigMap（非敏感配置）
apiVersion: v1
kind: ConfigMap
metadata:
  name: quant-config
data:
  strategy_config.yaml: |
    windows: [5, 10, 14, 20, 50]
    thresholds: [1.5, 2.0, 2.5]
    max_positions: 5
  log_level: "INFO"
  
---
# Secret（敏感信息，Base64 编码）
apiVersion: v1
kind: Secret
metadata:
  name: quant-secrets
type: Opaque
data:
  feishu_webhook: aHR0cHM6Ly9vcGVuLmZlaXNodS5j...  # 实际用 base64
  db_password: cGFzc3dvcmQxMjM=
```

## 4. 回测作业（Job）

一次性任务（回测、参数搜索）：

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: backtest-20260517
spec:
  completions: 1       # 完成 1 次即成功
  parallelism: 1        # 不并行
  backoffLimit: 3       # 失败重试 3 次
  ttlSecondsAfterFinished: 86400  # 完成后 1 天自动清理
  template:
    spec:
      containers:
      - name: backtest
        image: quant-engine:latest
        command:
        - python
        - scripts/full_backtest.py
        - --period=10y
        - --output=/app/results/backtest_20260517.json
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
      restartPolicy: Never
```

### 4.1 参数搜索（并行 Job）

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: param-search
spec:
  completions: 30         # 共 30 个任务
  parallelism: 5          # 同时运行 5 个
  template:
    spec:
      containers:
      - name: search
        image: quant-engine:latest
        command: ["python", "scripts/param_search.py"]
        env:
        - name: JOB_INDEX
          valueFrom:
            fieldRef:
              fieldPath: metadata.labels['batch.kubernetes.io/job-completion-index']
      restartPolicy: Never
```

每个 Pod 通过 `JOB_INDEX` 知道自己在哪组参数，只计算自己的部分。30 个组合，5 个并行，6 轮跑完——比串行快 5 倍。

## 5. 核心命令速查

```bash
# 基础
kubectl get pods -n quant-system        # 看 Pod
kubectl get deployments -n quant-system   
kubectl get svc -n quant-system
kubectl logs -f deployment/quant-monitor  # 日志

# 部署
kubectl apply -f deployment.yaml       # 创建/更新
kubectl rollout status deployment/quant-monitor  # 滚动更新状态
kubectl rollout undo deployment/quant-monitor    # 回滚

# Job
kubectl create job --from=cronjob/backtest-nightly manual-backtest

# 清理
kubectl delete pod quant-monitor-xxx  # Deployment 自动重建
kubectl delete job backtest-20260517

# 调试
kubectl exec -it quant-monitor-xxx -- /bin/sh  # 进入容器
kubectl port-forward svc/quant-monitor-svc 8000:80  # 本地访问
```

## 6. 本地 K8s（minikube）

在 Windows 5070Ti 上跑本地 K8s：

```powershell
# 1. 先启用 WSL 2
wsl --install -d Ubuntu

# 2. 安装 minikube
winget install minikube

# 3. 启动集群
minikube start --cpus=4 --memory=8g

# 4. 启用 Dashboard
minikube addons enable dashboard
minikube dashboard

# 5. 部署量化系统
kubectl create namespace quant-system
kubectl apply -f k8s/ -n quant-system

# 6. 访问
minikube service quant-monitor-svc -n quant-system
```

## 总结

```
K8s 的核心价值不在当前（单机够用），而在未来：
  分布式参数搜索（并行 Job）
  零停机滚动更新（策略不停）
  跨机器服务发现

量化资源模板：
  Deployment（监控服务、策略引擎）
  Job（回测、参数搜索）
  ConfigMap（策略配置）
  Secret（Webhook/DB 密码）

本地：minikube + WSL 2
生产：云托管 K8s（EKS/GKE/AKS）
```
