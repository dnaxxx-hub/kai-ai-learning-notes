# K8s 第10课：CNI网络与Service Mesh —— Pod间通信的底层与顶层

> 日期：2026-05-25 | 来源：K8s学习路线图（补充课）

## 核心概念

K8s的网络栈分为三个层次，从下到上依次是：

```
Service Mesh（服务网格）
    ↑ 七层：流量管理、mTLS、可观测性
─────────────────────────
K8s Service & Ingress（服务发现与入口）
    ↑ 四层/七层：负载均衡、DNS、Ingress路由
─────────────────────────
CNI 插件（容器网络）
    ↑ 三层/四层：Pod IP分配、跨节点通信、NetworkPolicy
─────────────────────────
Linux 网络栈（veth pair、iptables、路由表、overlay）
```

本课聚焦**最底层（CNI）**和**最顶层（Service Mesh）**，中间层已在第4课中覆盖。

## 一、CNI 插件深度解析

### 1.1 CNI 接口标准

CNI（Container Network Interface）是K8s与网络插件之间的**标准接口**，定义为一个gRPC协议和一组二进制调用：

```
kubelet → CRI (containerd) → CNI Plugin (二进制) → 配置网络
```

CNI插件需要实现四个操作：

| 操作 | 触发时机 | 行为 |
|------|---------|------|
| **ADD** | Pod创建时 | 分配IP、创建veth pair、配置路由 |
| **DEL** | Pod删除时 | 释放IP、清理网络资源 |
| **CHECK** | 周期性 | 验证Pod网络状态是否正常 |
| **VERSION** | 插件初始化 | 返回插件支持的CNI版本 |

**CNI配置文件**（在Node上）：

```json
// /etc/cni/net.d/10-calico.conflist
{
  "cniVersion": "0.3.1",
  "name": "k8s-pod-network",
  "plugins": [
    {
      "type": "calico",
      "datastore_type": "kubernetes",
      "mtu": 1500,
      "ipam": {
        "type": "calico-ipam",
        "assign_ipv4": "true"
      },
      "policy": {
        "type": "k8s"
      }
    },
    {
      "type": "portmap",
      "capabilities": {"portMappings": true},
      "snat": true
    }
  ]
}
```

### 1.2 三大CNI方案的架构对比

| 特性 | Flannel | Calico | Cilium |
|------|---------|--------|--------|
| **数据面技术** | VXLAN (UDP封装) | BGP + iptables | eBPF (BPF程序) |
| **网络模型** | Overlay | Pure Layer 3 | Overlay / Native |
| **性能损耗** | ~10-15% | ~5-10% (BGP) / ~10% (IPIP) | ~0-5% (eBPF) |
| **NetworkPolicy** | ❌ 不支持 | ✅ 原生支持 | ✅ 超集（支持DNS/L7规则） |
| **可观测性** | 基本无 | 中等（Felix策略日志） | 强（Hubble) |
| **部署复杂度** | 低 | 中（需要BGP配置或IPIP） | 中高（内核版本要求） |
| **大规模支持** | 一般（VXLAN性能瓶颈） | 好（BGP路由可直接交换） | 优秀（eBPF无锁效率高） |
| **内核要求** | 无特殊 | 无特殊 | Linux 5.10+ (eBPF) |

### 1.3 Flannel —— 最简单，最省心

#### VXLAN 模式原理

Flannel使用VXLAN（Virtual eXtensible LAN）技术，在现有三层网络上构建二层Overlay网络：

```
PodA (10.1.1.2) → 发送 → PodB (10.1.2.3)
    │
    ▼
NodeA 上的 Flannel（VTEP设备 flannel.1）
    │ 封装：内层IP=10.1.2.3, 外层IP=NodeB的IP
    │ VXLAN Header + UDP
    ▼
物理网络（跨Node传输）
    │
    ▼
NodeB 上的 flannel.1
    │ 解封装：剥掉VXLAN头，还原原始包
    ▼
PodB (10.1.2.3) 接收
```

**VXLAN的代价**：每个数据包增加50字节开销（VXLAN头8B + UDP头8B + 外层IP头20B + 外层MAC头14B）。MTU需要从1500调整为1450。

#### 配置示例

```bash
# 安装Flannel
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml

# 查看Flannel配置
kubectl get configmap -n kube-system kube-flannel-cfg -o yaml
```

```yaml
# Flannel配置（ConfigMap中的net-config.json）
{
  "Network": "10.244.0.0/16",
  "Backend": {
    "Type": "vxlan",
    "Port": 8472
  }
}
```

#### 适用场景
- 小规模集群（<50 Node）
- 不需要NetworkPolicy
- 追求极简部署

### 1.4 Calico —— 生产标准，功能全面

#### BGP模式原理

Calico使用BGP（Border Gateway Protocol）在Node之间直接交换路由，不封装数据包：

```
PodA (10.1.1.2) → PodB (10.1.2.3)

NodeA路由表：
10.1.2.0/24 → via NodeB的物理IP（raw IP，无封装）

NodeB路由表：
10.1.1.0/24 → via NodeA的物理IP

每个Node既是Pod的路由器，也是BGP speaker
```

**BGP的优势**：纯三层路由，无封装开销，性能接近原生网络。

**BGP的局限**：
- 需要物理网络支持BGP（或运行BGP在underlay网络上）
- 大规模集群（>100 Node）需要Route Reflector
- 公有云环境可能不支持BGP

#### IPIP模式（BGP不可用时的备选）

当物理网络不支持BGP时，Calico使用IPIP封装（IP over IP）：

```
PodA → PodB
原始包：src=10.1.1.2, dst=10.1.2.3
IPIP封装后：外层 src=NodeA_IP, dst=NodeB_IP
```

IPIP比VXLAN轻（只需20B额外头），但不如BGP直接。

#### Felix —— Calico的策略执行组件

Calico的核心是Felix，它在每个Node上运行，负责：

1. 维护iptables规则实现NetworkPolicy
2. 更新BGP路由
3. 保持与etcd的同步

```bash
# 查看Felix状态
calicoctl get workloadendpoints

# 查看当前生效的NetworkPolicy
calicoctl get networkpolicy -o wide

# 检查Node上的iptables规则
iptables-save | grep cali-
```

#### 部署示例

```bash
# 安装Calico（使用Operator）
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.26/manifests/tigera-operator.yaml

# 配置Calico（自定义资源）
cat <<EOF | kubectl apply -f -
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
    - blockSize: 26
      cidr: 10.244.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
---
apiVersion: operator.tigera.io/v1
kind: APIServer
metadata:
  name: default
spec: {}
EOF
```

> **VXLANCrossSubnet**：跨子网用VXLAN封装，同子网直接用BGP。这是生产中最推荐的Calico模式——同子网无开销，跨子网自动封装。

### 1.5 Cilium —— eBPF驱动的下一代CNI

#### eBPF的革命性

Cilium基于eBPF（extended Berkeley Packet Filter），允许在内核中运行沙箱化的用户定义程序：

```
传统模式（Calico/Flannel）：
数据包 → 内核协议栈 → iptables (线性遍历规则) → 用户空间转内核空间 → ...

eBPF模式（Cilium）：
数据包 → BPF程序 (在内核中直接决策, O(1)) → 处理完成
```

**eBPF的好处**：
- **性能**：iptables规则是O(n)遍历（规则越多越慢），BPF是O(1)
- **可编程性**：可以在内核中执行自定义逻辑（7层解析、负载均衡）
- **可观测性**：无需sidecar就能获取到每个连接的详细数据（Hubble）

#### Cilium架构

```
┌─────────────────────────────────────┐
│           Cilium Agent              │
│  (每个Node运行，管理BPF程序)         │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ BPF Map  │  │ Identity Store   │  │
│  │ (内核态)  │  │ (基于标签的身份)  │  │
│  └──────────┘  └──────────────────┘  │
└──────────┬──────────────────────────┘
           │
    ┌──────▼──────┐
    │  Hubble     │ ← 可观测性层（流量可视化）
    └─────────────┘
           │
    ┌──────▼──────┐
    │  Cilium     │ ← 完整的网络策略
    │ NetworkPolicy│   (支持L7规则、DNS规则)
    └─────────────┘
```

#### Cilium部署

```bash
# 安装Cilium CLI
curl -L --remote-name-all https://github.com/cilium/cilium-cli/releases/latest/download/cilium-linux-amd64.tar.gz

# 安装Cilium到集群
cilium install

# 验证状态
cilium status

# 启动可观测性
cilium hubble enable

# 查看流量
cilium hubble ui
```

#### eBPF vs iptables：性能对比

| 场景 | iptables | eBPF (Cilium) |
|------|----------|----------------|
| 100条规则 | ~5μs/包 | ~1μs/包 |
| 1000条规则 | ~50μs/包 | ~1μs/包 |
| 10000条规则 | ~500μs/包 | ~1μs/包 |
| 大规模Service | O(n)遍历 | O(1)哈希表 |
| 并发创建Service | 性能抖动 | 平滑 |

### 1.6 CNI选型决策树

```
需要NetworkPolicy吗？
├── 不需要 → Flannel（最简）
└── 需要 → 
    ├── 内核 ≥ 5.10，想要最新技术 → Cilium（强烈推荐）
    └── 内核较旧，追求稳定 → Calico BGP（生产首选）
```

## 二、NetworkPolicy 深度实战

### 2.1 默认拒绝策略

```yaml
# 拒绝Namespace内所有入站流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}        # 匹配该NS下所有Pod
  policyTypes:
  - Ingress
---
# 拒绝所有出站流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
spec:
  podSelector: {}
  policyTypes:
  - Egress
```

### 2.2 精细控制场景

```yaml
# 只允许frontend访问backend的API端口
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-policy
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
    - namespaceSelector:
        matchLabels:
          env: staging
    ports:
    - protocol: TCP
      port: 8080

---
# 允许monitoring NS的Prometheus访问metrics端点
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-monitoring
spec:
  podSelector:
    matchLabels:
      app: backend
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
      podSelector:
        matchLabels:
          app: prometheus
    ports:
    - protocol: TCP
      port: 9090
```

**关键的Combination逻辑**：
- 同一个`from`块内的`podSelector`和`namespaceSelector`：**与（AND）**
- 多个`from`块之间：**或（OR）**

### 2.3 NetworkPolicy与Calico/Cilium的增强策略

#### Calico的GlobalNetworkPolicy

```yaml
apiVersion: projectcalico.org/v3
kind: GlobalNetworkPolicy
metadata:
  name: deny-all-external
spec:
  selector: all()
  types:
  - Egress
  egress:
  - action: Allow
    destination:
      selector: has(projectcalico.org/namespace)
  - action: Deny
    destination:
      nets:
      - 0.0.0.0/0
```

#### Cilium的L7 NetworkPolicy

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: l7-policy
spec:
  endpointSelector:
    matchLabels:
      app: backend
  ingress:
  - fromEndpoints:
    - matchLabels:
        app: frontend
    toPorts:
    - ports:
      - port: "8080"
        protocol: TCP
      rules:
        http:
        - method: "GET"
          path: "/api/v1/.*"
        - method: "POST"
          path: "/api/v1/orders"
```

**效果**：不仅控制TCP:8080，还在七层控制HTTP方法和路径。这是原生K8s NetworkPolicy做不到的。

## 三、Service Mesh 概念与架构

### 3.1 为什么需要Service Mesh？

当K8s集群发展到一定规模（50+微服务），以下问题会越来越突出：

```
传统K8s（无Service Mesh）：

服务A ──HTTP──▶ 服务B ──HTTP──▶ 服务C
  │                │                │
  ├ 重试逻辑在代码里  ├ 熔断在代码里  ├ 追踪在代码里
  ├ TLS在代码里      ├ 限流在代码里  ├ ...
  └ 各路SDK各自为战  └ 集成困难     └ 每个语言写一次
```

**问题**：服务治理（重试、熔断、限流、追踪、安全）散落在每个微服务的代码里，每个服务/每种语言都要重复实现一遍。

**Service Mesh的答案**：

```
服务A ──HTTP──▶ Sidecar(Envoy) ──mTLS──▶ Sidecar(Envoy) ──HTTP──▶ 服务B
                  │                            │
                  └────── Control Plane ────────┘
                         (Istiod / Linkerd控制面)
```

服务治理逻辑从业务代码中**剥离**到Sidecar代理中，业务代码只关注业务逻辑。

### 3.2 Service Mesh 架构组件

| 组件 | 角色 | 实现（以Istio为例） |
|------|------|-------------------|
| **数据面（Data Plane）** | 代理所有进出流量 | Envoy Proxy |
| **控制面（Control Plane）** | 下发配置给数据面 | Istiod |
| **Sidecar注入器** | 自动注入Sidecar到Pod | istio-sidecar-injector |

#### 数据面 —— Envoy Proxy

Envoy是每个Pod旁边的Sidecar代理，拦截所有进出流量：

```
Pod: my-service-abc123
┌─────────────────────────────────┐
│  Container: my-app (port 8080)  │
│         ▲  localhost:8080  │     │
│         │                   │     │
│  Container: istio-proxy      │     │
│  (Envoy, 监听 15001/15006)   │     │
│  入站 ← 15006 | 出站 → 15001      │
└─────────┬───────────────────────┘
          │ iptables规则透明拦截
          ▼
         网络
```

**Envoy为什么被选为数据面？**
- 高性能C++实现
- 丰富的L4/L7协议支持（HTTP/gRPC/TCP/MongoDB/Redis...）
- 热重载配置（无需重启）
- 成熟的过滤器链架构

#### 控制面 —— Istiod

Istiod是Istio的控制面核心，负责：

1. **配置下发**：将VirtualService、DestinationRule等CRD转化为Envoy配置
2. **证书管理**：自动签发mTLS证书（基于SPIFFE身份）
3. **服务发现**：从K8s API获取Service/Pod信息

```
Istiod
  │
  ├── Pilot (配置下发) ──▶ gRPC/xDS ──▶ Envoy(Sidecar)
  ├── Citadel (证书管理) ──▶ 自动mTLS
  └── Galley (配置验证) ──▶ 接入控制Webhook
```

### 3.3 Service Mesh 的核心能力

#### 1. 流量管理

```yaml
# 金丝雀发布：5%流量到新版本
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
  - reviews
  http:
  - match:
    - headers:
        end-user:
          exact: jason          # 基于Header路由
    route:
    - destination:
        host: reviews
        subset: v2
  - route:
    - destination:
        host: reviews
        subset: v1
      weight: 95
    - destination:
        host: reviews
        subset: v2
      weight: 5
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100     # 连接池限制
      http:
        http1MaxPendingRequests: 10
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutive5xxErrors: 5   # 熔断：连续5个5xx
      interval: 30s
      baseEjectionTime: 60s
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
```

#### 2. 安全（自动化mTLS）

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT    # 整个网格强制mTLS
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: httpbin-policy
spec:
  selector:
    matchLabels:
      app: httpbin
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/sleep"]
    to:
    - operation:
        methods: ["GET"]
        paths: ["/status/*"]
```

**效果**：所有服务间通信自动加密，无需在代码中配置TLS。每个服务用SPIFFE身份标识，基于身份做授权。

#### 3. 可观测性

Service Mesh提供"免费"的可观测性（无需修改代码）：

| 能力 | 说明 | 工具 |
|------|------|------|
| **Golden Signals** | 延迟、流量、错误率、饱和度 | Prometheus + Grafana |
| **分布式追踪** | 端到端请求链路 | Jaeger / Zipkin |
| **服务拓扑** | 服务间调用关系图 | Kiali |
| **访问日志** | 完整的请求/响应日志 | Envoy Access Log |

```bash
# 安装Kiali查看服务拓扑
istioctl dashboard kiali

# 查看Jaeger分布式追踪
istioctl dashboard jaeger
```

### 3.4 Istio vs Linkerd

| 特性 | Istio | Linkerd |
|------|-------|---------|
| **数据面** | Envoy (C++) | 自研Rust代理 |
| **控制面语言** | Go | Go |
| **资源开销** | 较高（每个Sidecar ~50MB） | 较低（每个Sidecar ~10MB） |
| **功能丰富度** | 极丰富 | 够用（少但精） |
| **配置复杂度** | 陡峭 | 较低 |
| **mTLS** | STRICT/PERMISSIVE | 自动 |
| **TCP支持** | 完整 | 有限 |
| **社区** | CNCF毕业项目，Google主导 | CNCF毕业项目，Buoyant主导 |

**选型建议**：
- **Istio**：大型企业、功能需求多、有人力维护
- **Linkerd**：中小团队、追求轻量、不想太复杂

### 3.5 部署Service Mesh的代价

Service Mesh不是银弹，引入时需要评估以下代价：

| 代价维度 | 说明 |
|---------|------|
| **资源开销** | 每个Pod多一个Sidecar容器（~50-100MB内存 + 0.5-1vCPU） |
| **延迟增加** | 每次请求增加~1-5ms（Envoy L7处理） |
| **启动延迟** | Pod需要等待Sidecar就绪才能接收流量 |
| **排障复杂度** | 多了一层代理，需要理解Envoy / iptables 行为 |
| **运维成本** | 控制面组件需要维护、升级、监控 |

```bash
# 查看Sidecar资源占用（Istio）
kubectl top pod -n istio-system
kubectl top pod -n default | grep istio-proxy
```

**典型资源评估**：100个服务的集群，引入Istio大概需要额外5-10个vCPU和10-20GB内存。

## 代码/配置示例

### 完整的多层网络策略

```yaml
# 1. 默认拒绝所有
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
# 2. 允许DNS出站（CoreDNS在kube-system）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
spec:
  podSelector: {}
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - port: 53
      protocol: UDP
    - port: 53
      protocol: TCP
  policyTypes:
  - Egress
---
# 3. 允许API Server出口（令牌认证需要）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-apiserver-egress
spec:
  podSelector: {}
  egress:
  - to:
    - ipBlock:
        cidr: 10.0.0.0/24    # API Server所在网段
    ports:
    - port: 443
      protocol: TCP
  policyTypes:
  - Egress
```

### Cilium+Hubble流量可视化

```bash
# 安装Cilium
cilium install

# 启用Hubble
cilium hubble enable

# 安装Hubble UI
cilium hubble ui

# 查看集群内实时流量
cilium hubble observe

# 查看特定服务的流量
cilium hubble observe --from-service frontend --to-service backend
```

## 与已有知识的关联

- **k8s_04_networking.md**（第4课）：前面讲了Service/Ingress/DNS，本课延伸到CNI底层和Service Mesh顶层
- **k8s_02_pod_deep.md**（第2课）：Sidecar模式在Service Mesh中达到顶峰——Envoy是所有Pod的标准Sidecar
- **分布式系统笔记**：eBPF的O(1) vs iptables的O(n)体现了算法复杂度在系统设计中的关键作用
- **云计算笔记**：BGP路由协议在云网络中的应用

## 思考

### 网络的"抽象层次"思维

K8s网络栈的设计遵循了经典的分层抽象原则：

```
应用层     ↔ Service Mesh (七层路由/策略)
服务发现层 ↔ Service/DNS (四层负载均衡)
容器网络层 ↔ CNI Plugin (三层网络连通)
物理网络层 ↔ Underlay (物理设备路由)
```

每层解决不同的问题，层间解耦。这意味着：
- **CNI换了不影响Service**（因为Service是iptables/IPVS规则，不依赖CNI实现）
- **Service Mesh换了不影响CNI**（因为Sidecar代理通过Pod网络接口出入）
- **Service Mesh和CNI可以协同**（如Cilium的eBPF可以和Envoy Sidecar配合）

### 为什么Service Mesh是"顶层的网络"？

传统网络工程师看网络是"硬件+路由协议"；K8s时代的网络是"声明式策略+代理+可观测性"。Service Mesh本质上是在应用层实现了**软件定义网络（SDN）**——通过控制面下发策略，数据面在用户态执行。

### CNI选型建议

- **开发/测试环境**：Flannel（5分钟装好，不纠结）
- **生产小集群（<50 Node）**：Calico BGP（性能好，功能全）
- **生产大集群（>100 Node）**：Cilium eBPF（性能随规模扩展线性保持，iptables做不到）
- **安全敏感场景**：Cilium（L7策略，Hubble审计日志）

### Service Mesh采纳路径

```
第1步：不用Mesh
  → 基础K8s + Service + Ingress

第2步：选择性Mesh
  → 选择关键链路（如支付服务）接入Mesh
  → 其他服务不受影响

第3步：全面Mesh
  → 全集群Sidecar注入
  → mTLS严格模式
  
第4步：Mesh增强
  → 自定义Envoy Filter
  → 渐进式交付（金丝雀/暗部署）
```
