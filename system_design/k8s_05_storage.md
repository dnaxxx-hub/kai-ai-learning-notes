# K8s/云原生 #5：存储、ConfigMap 与 Secret

> 2026-05-17
> 前置：Service 与网络 #4

## 1. 存储体系概览

K8s 存储从三个维度抽象：

```
存储供给 → Volume（Pod 级）
            ↓
存储声明 → PersistentVolumeClaim（用户声明）
            ↓  
存储资源 → PersistentVolume（管理员定义）
            ↓
实际提供 → CSI 驱动 / 内建插件
```

## 2. Volume 类型

### 2.1 临时存储

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log/app
  volumes:
  - name: shared-logs
    emptyDir: {}           # 随 Pod 生命周期的空目录
```

**emptyDir** — Pod 删除时数据丢失，同 Pod 容器间共享。

```yaml
  - name: cache-volume
    emptyDir:
      medium: Memory       # 基于 tmpfs（RAM），更快但受限
      sizeLimit: 1Gi       # 限制大小
```

### 2.2 节点本地存储

**hostPath** — 挂载节点文件系统（危险！）：

```yaml
  - name: docker-socket
    hostPath:
      path: /var/run/docker.sock
      type: Socket
```

**仅用于**：DaemonSet（日志/监控/CSI Driver）和需要直接访问节点资源的场景。
**不建议用于**：普通应用存储（Pod 调度到不同节点的行为不可控）。

### 2.3 网络存储

| 类型 | 说明 | 常用场景 |
|------|------|---------|
| NFS | 传统网络文件系统 | 低成本共享存储 |
| iSCSI | 块存储 | 数据库 |
| Ceph RBD | Ceph 块设备 | 高性能 |
| GlusterFS | 分布式文件系统 | 大文件 |
| 云盘 | EBS / GCE PD / Azure Disk | 云环境 |

## 3. PersistentVolume / PersistentVolumeClaim

### 3.1 PV（集群资源）

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-manual
spec:
  capacity:
    storage: 10Gi
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain   # 保留
  storageClassName: manual
  hostPath:
    path: /data/pv01
```

### 3.2 PVC（用户声明）

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: manual
```

### 3.3 PV → PVC 绑定

```
PVC: 需要 5Gi RWO
       ↓
PV 匹配：足够容量 + 兼容 accessMode + 相同 storageClass
       ↓
绑定（一对一），多余的 PV 无法绑定
```

### 3.4 StorageClass（动态供给）

无需手动创建 PV，SC 自动从云盘创建：

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  fsType: ext4
  iopsPerGB: "10"
```

PVC 引用 SC：

```yaml
spec:
  storageClassName: fast    # 自动创建 PV
```

### 3.5 AccessMode

| 模式 | 含义 |
|------|------|
| ReadWriteOnce (RWO) | 单节点读写（云盘/块存储） |
| ReadOnlyMany (ROX) | 多节点只读 |
| ReadWriteMany (RWX) | 多节点读写（NFS/CephFS） |

### 3.6 ReclaimPolicy

| 策略 | 含义 |
|------|------|
| Retain | PVC 删除后 PV 保留（手动清理） |
| Delete | PVC 删除后 PV 自动删除（动态供给默认） |
| Recycle | 已弃用，用动态供给替代 |

## 4. ConfigMap

将配置从 Pod 定义中分离：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  app.properties: |
    app.name=myapp
    app.mode=production
    db.host=db-service
  config.json: |
    {"key": "value"}
```

### 4.1 挂载方式

```yaml
spec:
  containers:
  - name: app
    env:
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: app.properties
    envFrom:
    - configMapRef:
        name: app-config
    volumeMounts:
    - name: config
      mountPath: /etc/config
  volumes:
  - name: config
    configMap:
      name: app-config
```

### 4.2 热更新

通过 Volume 挂载的 ConfigMap **自动热更新**（最长 60-90s 同步延迟）。
通过环境变量的不会更新（Pod 启动后不变）。

监听 ConfigMap 变化的常见模式：
```python
import time, os

# Sidecar 模式：监控文件变化
config_mtime = os.path.getmtime('/etc/config/app.properties')
while True:
    new_mtime = os.path.getmtime('/etc/config/app.properties')
    if new_mtime != config_mtime:
        reload_config()  # 重新加载配置
        config_mtime = new_mtime
    time.sleep(10)
```

## 5. Secret

与 ConfigMap 类似，但 Base64 编码 + 更严格的安全控制：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque                    # 通用类型
data:
  password: cGFzc3dvcmQxMjM=   # Base64 编码（echo -n "password123" | base64）
stringData:                     # 明文写入，自动编码
  username: admin
```

### 5.1 使用方式

```yaml
spec:
  containers:
  - name: app
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
    volumeMounts:
    - name: creds
      mountPath: /etc/creds
      readOnly: true
  volumes:
  - name: creds
    secret:
      secretName: db-secret
```

### 5.2 Secret 的安全风险

```
⚠️ Secret 仅 Base64 编码，不是加密！
    etcd 中的 Secret 如果未加密 → 有 etcd 访问权限就拿到所有 Secret
    Pod 环境的 env 命令可查看 → env | grep PASSWORD
    Volume 挂载的文件可读 → mount | grep secret
```

最佳实践：
- **etcd 加密**：`encryption-provider-config` 使用 AES-CBC / KMS
- **外部密钥管理**：使用 HashiCorp Vault / AWS Secrets Manager / External Secrets Operator
- **最小权限**：RBAC 限制 Secret 的读权限
- **避免 env**：优先用 Volume 挂载（安全审计可见）
- **禁止泄露**：日志不能打印 Secret 值

### 5.3 External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: vault-example
spec:
  refreshInterval: "1h"
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: generated-secret
  data:
  - secretKey: db-password
    remoteRef:
      key: /secrets/db
      property: password
```

自动同步外部密钥管理器到 K8s Secret，最小化存储在 etcd 中的明文。

## 6. CSI（容器存储接口）

插件化存储框架，K8s 1.13 GA：

```yaml
# CSI Driver 结构
CSI Driver (DaemonSet on each node)
  ↓
gRPC 接口与 kubelet 通信
  ↓
调用云厂商/存储厂商的 API 创建挂载卷
```

常见 CSI Driver：
- AWS EBS / EFS
- GCE PD / Filestore
- Azure Disk / File
- Ceph RBD / CephFS
- NFS CSI Driver

## 总结

```
Volume = Pod 级存储（临时/本地/网络）
PV/PVC = 存储抽象层（管理员供给/用户声明）
StorageClass = 动态自动创建
ConfigMap = 配置分离（环境变量/Volume 挂载/热更新）
Secret = 敏感信息（Base64 + 外部密钥管理）
CSI = 插件化存储框架
```
