# K8s 运维实战

## 1. kubeadm 搭建 K8s 集群

### 环境准备
```bash
# 所有节点：关闭 swap
sudo swapoff -a
# /etc/fstab 注释 swap 行

# 所有节点：安装容器运行时 (containerd)
cat <<EOF | sudo tee /etc/modules-load.d/containerd.conf
overlay
br_netfilter
EOF
sudo modprobe overlay && sudo modprobe br_netfilter

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system

# 安装 containerd
sudo apt-get update && sudo apt-get install -y containerd
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
# 配置 SystemdCgroup = true
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
```

### 安装 kubeadm / kubelet / kubectl
```bash
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gpg
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update && sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

### 初始化控制面
```bash
# 控制面节点
sudo kubeadm init --pod-network-cidr=10.244.0.0/16

# 配置 kubectl
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# 安装网络插件 (Calico)
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27/manifests/calico.yaml

# 节点加入 (worker 节点执行)
sudo kubeadm join <控制面IP>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

### 高可用方案
- **堆叠式 etcd**: 控制面节点同时运行 etcd
- **外部 etcd**: etcd 集群独立部署
- 推荐使用 **kubeadm + keepalived + haproxy** 做负载均衡

---

## 2. etcd 备份与恢复

### 备份 etcd
```bash
# 方法1：etcdctl 快照
ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  snapshot save /backup/etcd-snapshot-$(date +%Y%m%d).db

# 方法2：定时备份 (cron)
0 2 * * * /usr/local/bin/etcd-backup.sh
```

### 恢复 etcd
```bash
# 停止 API server
systemctl stop kube-apiserver

# 恢复快照
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-snapshot-20250101.db \
  --data-dir=/var/lib/etcd-restored

# 替换数据目录
mv /var/lib/etcd /var/lib/etcd.old
mv /var/lib/etcd-restored /var/lib/etcd

# 重启 etcd
systemctl restart etcd
systemctl start kube-apiserver
```

### 关键注意事项
- ⚠️ **Raft 核心**: etcd 需要多数节点 (quorum) 才能写，3 节点容忍 1 失败
- ⚠️ **备份频率**: 推荐每小时快照 + 每日归档
- ⚠️ **定期测试恢复**: 在生产环境之前务必演练

---

## 3. Pod / 节点故障排查

### Pod 状态速查

| 状态 | 含义 | 排查方向 |
|------|------|---------|
| `Pending` | 未调度 | 资源不足、PVC 不可用、污点 |
| `ContainerCreating` | 镜像拉取/启动中 | 镜像名错误、拉取凭据、CNI |
| `CrashLoopBackOff` | 持续重启 | 应用错误、OOM、健康检查失败 |
| `ImagePullBackOff` | 镜像拉取失败 | 镜像不存在、仓库认证 |
| `Running` | 运行中（正常） | 检查日志和就绪探针 |
| `Terminating` | 正在终止 | 挂载卷、finalizer |
| `OOMKilled` | 内存超限 | 增加 limit 或优化内存 |
| `Evicted` | 被驱逐 | 节点资源压力 |
| `Unknown` | 节点失联 | 网络/节点问题 |

### 排查三板斧
```bash
# 1. 查看 Pod 详情
kubectl describe pod <pod-name> -n <ns>

# 2. 查看日志
kubectl logs <pod-name> -n <ns> --tail=100
kubectl logs <pod-name> -n <ns> -c <container>  # 多容器

# 3. 进入 Pod 调试
kubectl exec -it <pod-name> -n <ns> -- sh

# 辅助：查看事件
kubectl get events -n <ns> --sort-by='.lastTimestamp'
```

### 节点故障排查
```bash
# 查看节点状态
kubectl get nodes
kubectl describe node <node-name>

# 常见节点问题
# - NotReady: kubelet 挂了或网络问题
# - DiskPressure: 磁盘空间不足
# - MemoryPressure: 内存不足
# - PIDPressure: PID 耗尽

# 排查命令（SSH 到节点）
systemctl status kubelet
journalctl -xeu kubelet -f
crictl ps  # 查看容器运行时
crictl logs <container-id>  # 容器运行时日志
df -h      # 磁盘
top / free -m  # 内存
```

### 网络策略问题
```bash
# 检查 CNI 插件
kubectl get pods -n kube-system | grep calico  # 或 cni/flannel

# 检查 Service 和 Endpoint
kubectl get svc
kubectl get endpoints <svc-name>
kubectl run tmp --image=busybox -it --rm -- wget -O- http://<svc>.<ns>

# 测试 DNS
kubectl run tmp --image=busybox -it --rm -- nslookup kubernetes.default
```

---

## 4. 网络策略

### NetworkPolicy (K8s 原生)
- 需要 CNI 支持（Calico, Cilium, Weave 等）
- 默认允许所有流量 → 一旦创建策略则白名单

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-ingress
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              env: prod
      ports:
        - port: 80
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: backend
      ports:
        - port: 8080
```

### 常见模式

| 模式 | 效果 |
|------|------|
| 默认拒绝所有入站 | 限制外部访问 |
| 仅允许同命名空间 | 隔离环境 |
| 允许来自特定命名空间 | 跨命名空间通信 |
| 允许出口到特定 CIDR | 访问外部数据库 |
| 拒绝到特定 CIDR | 安全合规需求 |

### Calico 网络策略（更强大）
```yaml
# 全局策略
apiVersion: projectcalico.org/v3
kind: GlobalNetworkPolicy
metadata:
  name: deny-all-external
spec:
  selector: all()
  egress:
    - action: Deny
      destination:
        notNamespace: kube-system
```

---

## 5. 运维 Checklist

### 日常运维
- [ ] 定期备份 etcd（每小时快照）
- [ ] 监控集群（Prometheus + Grafana）
- [ ] 升级 K8s 版本（小版本逐个升级）
- [ ] 审计日志（kube-apiserver audit）
- [ ] Pod 资源限制（防止 OOM 和 CPU 抢占）
- [ ] 节点自动修复（节点健康检查）
- [ ] 镜像安全扫描（Trivy/Clair）

### 故障场景速查

| 症状 | 可能原因 | 快速修复 |
|------|---------|---------|
| Pod 一直 Pending | 资源不足/污点 | `kubectl describe pod` 查看事件 |
| Pod CrashLoopBackOff | 应用错误/OOM | `kubectl logs` 查看错误 |
| 节点 NotReady | Kubelet 挂了 | SSH 登录检查 kubelet 服务 |
| DNS 解析失败 | CoreDNS 挂了 | `kubectl -n kube-system rollout restart deploy/coredns` |
| Service 不通 | Endpoint 为空 | 检查 Pod 标签匹配 |
| CNI 问题 | 网络不通 | 检查 calico-node Pod 状态 |
| 证书过期 | kube-apiserver 报错 | `kubeadm certs renew all` |
| etcd 性能慢 | 磁盘 IO 高 | 使用 SSD，调整 --quota-backend-bytes |
