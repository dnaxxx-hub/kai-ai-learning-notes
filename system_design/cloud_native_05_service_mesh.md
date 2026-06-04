# 云原生第5课：Service Mesh 与服务网格（Istio）

> 学习日期：2026-05-10
> 课程定位：Kubernetes 微服务通信层

---

## 一、Service Mesh 概念

### 1.1 什么是 Service Mesh

**定义**：Service Mesh 是用于处理服务间通信的基础设施层，负责在微服务拓扑中可靠地传递请求。

**核心洞察**：随着微服务数量增长，服务间通信的复杂度（重试、超时、熔断、安全、可观测性）已超越业务逻辑本身。Service Mesh 将这些"服务通信共性问题"从应用代码中剥离，下沉到基础设施层。

### 1.2 Sidecar Proxy 架构

```
┌─────────────────────────────────────────────────┐
│                  Kubernetes Pod                   │
│                                                    │
│  ┌──────────────┐     ┌──────────────────┐       │
│  │  Application  │ ──→ │  Sidecar Proxy   │       │
│  │  Container    │ ←── │  (Envoy)         │       │
│  │  (业务代码)    │     │  127.0.0.1:15000 │       │
│  └──────────────┘     └────────┬─────────┘       │
│                                │                  │
│                     iptables 规则劫持所有流量       │
│                     inbound → 15006               │
│                     outbound → 15001              │
└─────────────────────────────────────────────────┘
           │
           ▼
  ┌──────────────────┐
  │   Sidecar Proxy  │ ←── 对端 Pod 的 Sidecar
  │    (Envoy)       │ ──→ 自动 mTLS 加密通信
  └──────────────────┘
```

**关键要点**：
- 每个 Pod 自动注入一个 Envoy 代理容器（Sidecar 模式）
- **对应用完全透明** — 应用无需感知 Sidecar 存在
- 应用只看见 localhost 上的服务端口
- 所有进出 Pod 的流量被 iptables 规则劫持到 Envoy

### 1.3 数据面（Data Plane）vs 控制面（Control Plane）

```
┌────────────────────────────────────────────────────┐
│                   Control Plane                    │
│                                                     │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐      │
│  │  Pilot  │  │  Mixer  │  │   Citadel    │      │
│  │ (配置下发)│  │(策略控制)│  │ (证书管理)    │      │
│  └────┬────┘  └────┬────┘  └──────┬───────┘      │
│       │            │              │               │
│       └────────────┴──────────────┘               │
│                     │ xDS 协议                     │
└─────────────────────┼──────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
    ┌────▼────┐              ┌────▼────┐
    │ Envoy   │  ← mTLS →   │ Envoy   │  ... Data Plane
    │ (Sidecar)│             │ (Sidecar)│
    └─────────┘              └─────────┘
       Service A                Service B
```

| 维度 | 数据面（Data Plane） | 控制面（Control Plane） |
|------|---------------------|----------------------|
| 组成 | 所有 Sidecar Envoy 代理 | Pilot / Mixer / Citadel（Istio 旧版） |
| 职责 | 拦截并处理所有进出流量 | 下发配置、策略、证书 |
| 通信 | L4+L7 数据转发 | xDS 协议（动态配置分发） |
| 行为 | 处理实际请求 | 声明式配置管理 |
| 变更 | 流量不经过控制面 | 只下发配置，不处理数据 |

> **⚠️ Istio 1.5+ 架构简化**：Mixer 被移除，功能合并到 Envoy 中；Citadel 合并到 istiod。新架构只有一个组件 **istiod** 包含 Pilot + Citadel + Galley。

```
Istio 1.5+ 架构：
┌────────────────────────────────────────────┐
│                istiod                       │
│  ┌──────┐  ┌────────┐  ┌────────┐        │
│  │Pilot │  │Citadel │  │Galley  │        │
│  └──┬───┘  └───┬────┘  └───┬────┘        │
│     │          │           │              │
│     └──────────┴───────────┘              │
│              │ xDS                         │
└──────────────┼─────────────────────────────┘
               │
         ┌─────┴─────┐
         │   Envoy   │ Sidecar Proxy
         └───────────┘
```

**各组件职责**：

| 组件 | 职责 | 协议 |
|------|------|------|
| **Pilot** | 服务发现 + 流量管理配置下发 | xDS（LDS/RDS/CDS/EDS） |
| **Citadel** | 证书签发 + mTLS 密钥管理 | SPIFFE 身份体系 |
| **Galley** | 配置验证 + 转换 + 分发 | Kubernetes CRD → 内部格式 |
| **Mixer**（旧版） | 访问控制 + 遥测收集（已移除，功能并入 Envoy） | —— |

### 1.4 流量劫持原理（iptables）

Istio 通过 Init Container（初始化容器）在 Pod 启动时注入 iptables 规则：

```
# 入站流量劫持（Inbound）
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 15006

# 出站流量劫持（Outbound）
iptables -t nat -A OUTPUT -p tcp ! -d 127.0.0.1/32 -j REDIRECT --to-port 15001

# 注意：Envoy 本身使用的端口（15000/15001/15006）会绕过劫持
iptables -t nat -A OUTPUT -p tcp --dport 15000 -j RETURN
```

**流量流转路径**：
```
外 → Pod：  外部请求 → NodePort / Ingress → Pod IP:port
              ↓ iptables PREROUTING
            Envoy Inbound (15006) → 处理 → 应用容器 localhost:port

Pod → 外：  Pod 发出请求 → 目标 IP
              ↓ iptables OUTPUT (非 127.0.0.1)
            Envoy Outbound (15001) → 发现目标 Service
              ↓ 负载均衡 → 选择实例
            Envoy → 目标 Pod（mTLS 加密）
```

---

## 二、Istio 核心功能

### 2.1 流量管理

Istio 的流量管理基于两个核心 CRD：

#### VirtualService（虚拟服务 — 路由规则）

定义请求到达后如何路由到实际服务。

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
    - reviews                    # 匹配的目标服务名
  http:
    - match:
        - headers:
            end-user:
              exact: jason       # Header 匹配 → A/B 测试
      route:
        - destination:
            host: reviews
            subset: v2           # 路由到 v2 版本
    - match:
        - uri:
            prefix: /api/v1      # URI 前缀匹配
      rewrite:
        uri: /api/v2             # 重写路径
      route:
        - destination:
            host: reviews
            port:
              number: 9080
    - route:                     # 默认路由（权重切分）
        - destination:
            host: reviews
            subset: v1
          weight: 90
        - destination:
            host: reviews
            subset: v2
          weight: 10
```

#### DestinationRule（目标规则 — 负载均衡 + 熔断）

定义目标服务的负载均衡策略、连接池、熔断规则。

```yaml
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: reviews
spec:
  host: reviews
  trafficPolicy:
    loadBalancer:
      simple: LEAST_CONN          # 负载均衡算法
    connectionPool:
      tcp:
        maxConnections: 100       # 最大连接数
        connectTimeout: 30ms      # 连接超时
      http:
        http1MaxPendingRequests: 10
        http2MaxRequests: 1000
        maxRequestsPerConnection: 10
    outlierDetection:             # 熔断检测
      consecutive5xxErrors: 5     # 连续5次错误触发
      interval: 30s               # 检测间隔
      baseEjectionTime: 30s       # 熔断持续时间
      maxEjectionPercent: 100
  subsets:
    - name: v1
      labels:
        version: v1
    - name: v2
      labels:
        version: v2
    - name: v3
      labels:
        version: v3
```

**路由规则匹配优先级**：

```
VirtualService 匹配规则
     │
     ├── 1. 请求 Header 匹配（精确/前缀/正则）
     ├── 2. URI 路径匹配
     ├── 3. 方法匹配（GET/POST）
     ├── 4. 来源服务（from）
     └── 5. 默认路由（无匹配条件）
```

### 2.2 灰度发布

#### Header-based（A/B 测试）

```
用户请求 with header "end-user: jason"
    │
    ▼
VirtualService 匹配 header
    │
    ├── end-user=jason → reviews v2（新版本）
    │
    └── 其他用户 → reviews v1（稳定版）
```

**典型场景**：内部 QA 团队、VIP 用户体验新功能。

#### Weight-based（金丝雀发布）

```
金丝雀发布流程（v1 → v2）：

阶段 1：10% 流量到 v2
  ┌─────────┐  90%    ┌────────────┐
  │ reviews │ ──────→ │ v1 (stable)│
  │ Service │         └────────────┘
  │         │  10%    ┌────────────┐
  │         │ ──────→ │ v2 (canary)│
  └─────────┘         └────────────┘

阶段 2：50%
  │ reviews │  50% v1 / 50% v2

阶段 3：90%
  │ reviews │  10% v1 / 90% v2

阶段 4：100% → v2（v1 下线）
```

**实际 K8s 配置对比**：

| 维度 | K8s Deployment（原生） | Istio VirtualService |
|------|----------------------|---------------------|
| 流量切分 | 调整 Replica 比例 | 调整 weight 比例 |
| 粒度 | Pod 数比例 | 请求数比例 |
| 精确度 | 粗粒度（依赖 Pod 数量） | 精确百分比 |
| 跨服务 | 无法控制 | 可逐跳控制 |
| 回滚 | 回退 Deployment | 修改路由权重 |

### 2.3 可观测性

Istio 天然提供三大可观测性支柱，无需修改应用代码：

```
                     ┌──────────────────┐
  Envoy Sidecar ───→ │     Istio        │
  (Telemetry v2)     │   Telemetry      │
                     │ (Envoy 内嵌)     │
                     └────────┬─────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
     ┌──────────┐      ┌───────────┐      ┌────────┐
     │ Tracing  │      │  Metrics  │      │ Logging│
     │ Jaeger   │      │ Prometheus│      │  Loki  │
     │ Zipkin   │      │           │      │        │
     └──────────┘      └───────────┘      └────────┘
```

| 可观测性 | 数据来源 | 典型工具 | 展示内容 |
|----------|---------|---------|---------|
| **Tracing** | Envoy 自动注入 trace headers | Jaeger / Zipkin | 请求完整调用链，每跳延迟 |
| **Metrics** | Envoy 导出标准指标 | Prometheus + Grafana | QPS、延迟（P50/P95/P99）、错误率 |
| **Logging** | Envoy Access Log | Loki + Grafana | 请求日志（来源、目标、状态码、延迟） |

**Envoy 自动生成的指标**：

```
# HTTP 请求指标
istio_requests_total{
  source_workload="frontend",
  destination_workload="reviews",
  destination_service="reviews.default.svc.cluster.local",
  response_code="200",
  reporter="destination"
}

# TCP 指标
istio_tcp_sent_bytes_total{
  source_workload="reviews",
  destination_workload="ratings",
  ...
}

# 延迟
istio_request_duration_milliseconds_bucket{
  destination_workload="reviews",
  le="100",
  ...
}
```

### 2.4 安全：mTLS（双向 TLS）

**自动 mTLS**：Istio 自动为服务间通信启用双向 TLS 加密：

```
Service A                Service B
  Pod                      Pod
┌─────────┐             ┌─────────┐
│  App    │             │  App    │
└───┬─────┘             └───┬─────┘
    │                       │
┌───▼─────┐    mTLS     ┌───▼─────┐
│ Envoy   │ ═══════════ │ Envoy   │
│  SAN:    │ 握手+加密   │  SAN:    │
│ spiffe://│             │ spiffe://│
│ cluster/ │             │ cluster/ │
│ ns/      │             │ ns/      │
│ sa/      │             │ sa/      │
│ reviews  │             │ ratings  │
└─────────┘             └─────────┘
```

**mTLS 握手流程**：
```
1. Client Envoy → Server Envoy: Client Hello（支持 TLS 1.3）
2. Server Envoy → Client Envoy: Server Hello + 证书（SPIFFE X.509）
3. Client Envoy: 验证服务器证书（CA 签发，SAN 匹配）
4. Client Envoy → Server Envoy: Client 证书
5. Server Envoy: 验证客户端证书
6. 双向握手完成 → 加密隧道建立
7. 后续所有通信经过加密隧道
```

**SPIFFE 身份格式**：
```
spiffe://<trust-domain>/ns/<namespace>/sa/<service-account>
                                   │              │
                              命名空间        K8s ServiceAccount
```

**mTLS 配置**：

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: istio-system
spec:
  mtls:
    mode: STRICT          # STRICT: 仅接受 mTLS
                          # PERMISSIVE: 接受 mTLS 或明文（迁移期）
                          # DISABLE: 禁用 mTLS
```

**mTLS 模式对比**：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `STRICT` | 只接受 mTLS 加密连接 | 生产环境 |
| `PERMISSIVE` | 同时接受 mTLS 和明文 | 渐进式迁移，兼容旧服务 |
| `DISABLE` | 禁用 mTLS | 调试或非敏感链路 |

### 2.5 授权策略（AuthorizationPolicy）

基于来源 + 操作 + 条件的精细访问控制：

```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: reviews-policy
  namespace: default
spec:
  selector:
    matchLabels:
      app: reviews           # 策略作用于 reviews Pod
  action: ALLOW              # ALLOW / DENY / AUDIT
  rules:
    - from:                  # 来源（source）
        - source:
            principals: ["cluster.local/ns/default/sa/frontend"]
            namespaces: ["default"]
            ipBlocks: ["10.0.0.0/8"]
      to:                    # 操作（operation）
        - operation:
            methods: ["GET"]
            paths: ["/ratings/*"]
            ports: ["9080"]
      when:                  # 条件（condition）
        - key: request.headers[X-Risk-Token]
          values: ["trusted"]
```

**授权策略匹配逻辑**：
```
DENY 规则 → 优先匹配（拒绝优先于允许）
    │
    ▼ 无匹配
ALLOW 规则 → 匹配则放行
    │
    ▼ 无匹配
默认拒绝
```

---

## 三、Envoy 架构

### 3.1 xDS 协议

xDS 是 Envoy 动态配置的协议族，控制面通过 xDS 向 Envoy 下发配置：

```
       Control Plane (istiod)
              │
              │ xDS gRPC Stream
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐
│Envoy │ │Envoy │ │Envoy │
│ Pod1 │ │ Pod2 │ │ Pod3 │
└──────┘ └──────┘ └──────┘
```

**xDS 资源类型**：

| 协议 | 全称 | 配置内容 | 作用 |
|------|------|---------|------|
| **LDS** | Listener Discovery Service | 监听器定义 | 监听端口、绑定过滤器链 |
| **RDS** | Route Discovery Service | 路由规则 | URL → Cluster 映射 |
| **CDS** | Cluster Discovery Service | 集群定义 | 上游服务配置 |
| **EDS** | Endpoint Discovery Service | 端点列表 | 后端实例 IP:Port |
| **SDS** | Secret Discovery Service | 证书密钥 | TLS 证书动态更新 |

**配置下发流程**：
```
Envoy 启动
    │
    ├── 1. LDS: 获取 Listener 配置（监听 :15001/:15006）
    │         ↓
    ├── 2. RDS: 获取 Route 配置（URL → Cluster）
    │         ↓
    ├── 3. CDS: 获取 Cluster 配置（连接池、超时、熔断）
    │         ↓
    └── 4. EDS: 获取 Endpoint 列表（Pod IP 实时更新）
```

### 3.2 过滤器链（Filter Chain）

Envoy 的过滤架构使其同时支持 L4 和 L7 流量处理：

```
入站请求
    │
    ▼
Listener (0.0.0.0:15006)
    │
    ├── Filter Chain ────────────────────────────┐
    │                                            │
    │  ┌──────────────────────────────────────┐  │
    │  │ Network Filters (L4 网络过滤器)        │  │
    │  │  - TCP Proxy Filter                  │  │
    │  │  - Rate Limit Filter                 │  │
    │  │  - RBAC Filter (源 IP 白名单)         │  │
    │  └──────────────┬───────────────────────┘  │
    │                  │                          │
    │  ┌──────────────▼───────────────────────┐  │
    │  │ HTTP Connection Manager (HCM)         │  │
    │  │ ┌─────────────────────────────────┐   │  │
    │  │ │ HTTP Filters (L7 HTTP 过滤器)    │   │  │
    │  │ │  - Router Filter (路由)          │   │  │
    │  │ │  - CORS Filter                   │   │  │
    │  │ │  - Fault Injection Filter        │   │  │
    │  │ │  - gRPC-Web Filter              │   │  │
    │  │ └─────────────────────────────────┘   │  │
    │  └───────────────────────────────────────┘  │
    └──────────────────────────────────────────────┘
```

**过滤器类型**：

| 类型 | 层次 | 示例 | 功能 |
|------|------|------|------|
| **Network Filter** | L4 网络层 | TCP Proxy | 原始 TCP 流量转发 |
| | | Rate Limit | 连接速率限制 |
| | | RBAC | 基于 IP 的访问控制 |
| **HTTP Filter** | L7 应用层 | Router | 路由到 Cluster |
| | | Fault Injection | 故障注入测试 |
| | | CORS | 跨域请求处理 |
| | | gRPC-Web | gRPC-Web 协议转换 |
| **Listener Filter** | 监听器层 | Original Dst | 原始目标地址恢复 |
| | | TLS Inspector | TLS 协议检测 |

**Envoy 与 iptables 的网络流**：
```
外部流量 → Pod IP:80
    ↓ iptables PREROUTING → REDIRECT 15006
    ↓ Envoy Inbound Listener
    ↓ Filter Chain → 匹配过滤器
    ↓ HTTP Router → Cluster
    ↓ mTLS 加密 → 后端实例
```

---

## 四、与 K8s 原生对比

### 4.1 K8s Service（L4） vs Istio（L7）

| 能力 | K8s Service | Istio（Envoy Sidecar） |
|------|------------|----------------------|
| **负载均衡** | L4（TCP/UDP，轮询） | L7（HTTP Header/Cookie/WRR） |
| **路由粒度** | 按 Service 名称 | 按 Header/URI/Method/权重 |
| **灰度发布** | 手动调整 Replica 比例 | VirtualService weight 切分 |
| **熔断保护** | ❌ 不支持 | ✅ ConnectionPool + OutlierDetection |
| **安全加密** | ❌ 需自行实现 | ✅ 自动 mTLS |
| **可观测性** | ❌ 无 | ✅ Tracing + Metrics + Logging |
| **故障注入** | ❌ 不支持 | ✅ Fault Injection Filter |
| **重试/超时** | ❌ 不支持 | ✅ VirtualService 配置 |
| **性能开销** | 内核空间（零额外） | 用户空间代理（~5-15ms 延迟） |
| **协议支持** | TCP/UDP | HTTP/1.1, HTTP/2, gRPC, TCP |

### 4.2 对比示例

**K8s 原生 — 金丝雀发布**：
```yaml
# 需要创建两个 Deployment + 调整副本数
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reviews-v1
spec:
  replicas: 9              # 90% 流量（粗粒度）
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reviews-v2
spec:
  replicas: 1              # 10% 流量
```

**Istio — 金丝雀发布**：
```yaml
# 一个 Service + 两个 Deployment + VirtualService 权重
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: reviews
spec:
  hosts:
    - reviews
  http:
    - route:
        - destination:
            host: reviews
            subset: v1
          weight: 90        # 精确百分比
        - destination:
            host: reviews
            subset: v2
          weight: 10
```

### 4.3 何时需要 Istio

**推荐使用 Istio 的场景**：
- 微服务数量 > 10，服务间调用链路复杂
- 需要精细的流量控制和灰度发布策略
- 安全合规要求所有服务间通信加密（mTLS）
- 需要统一的可观测性（无侵入的 Tracing/Metrics）
- 异地多活、故障注入测试、混沌工程

**不推荐使用 Istio 的场景**：
- 微服务数量很少（< 5），链路简单
- 对延迟极度敏感（每跳额外 ~5ms）
- 团队没有 K8s 经验
- 开发和运维资源有限

---

## 五、Python 简化模拟

参见同目录下的 `code/service_mesh_sim.py`，包含：

1. **Sidecar 代理模拟**：
   - Envoy 风格的代理拦截入/出流量
   - 应用无感知的请求转发
   - iptables 劫持逻辑简化

2. **VirtualService 路由规则匹配**：
   - Header 匹配（A/B 测试）
   - Weight 路由（金丝雀发布）
   - 多规则优先级

3. **金丝雀发布模拟**：
   - 10% / 50% / 90% 流量切分
   - 统计数据验证

4. **mTLS 握手模拟**：
   - 证书交换
   - 身份验证
   - 加密通信隧道

### 运行方式

```bash
python memory/learning/code/service_mesh_sim.py
```

---

## 六、关键总结

### Service Mesh 架构
```
应用 → Sidecar Proxy → 对端 Sidecar → 对端应用
        ↕ 透明劫持      ↕ mTLS 加密
        ↕ xDS 配置      ↕ 动态负载均衡

控制面（istiod）: Pilot + Citadel + Galley
```

### Istio 三大价值
1. **流量管理** — L7 精细化路由 + 灰度发布
2. **安全** — 自动 mTLS + 细粒度授权策略
3. **可观测性** — 无侵入 Tracing / Metrics / Logging

### Envoy 配置下发
```
LDS → RDS → CDS → EDS
(监听器) (路由) (集群) (端点)
```

### 与 K8s 原生对比
```
K8s Service: L4 负载均衡，零开销
Istio:      L7 精细控制，~5ms 额外延迟
```

### 最佳实践
1. **渐进式迁移**：先用 PERMISSIVE 模式启用 mTLS，再切到 STRICT
2. **金丝雀先小后大**：1% → 10% → 50% → 100%
3. **监控先行**：先部署 Prometheus + Grafana 再启灰度
4. **AuthorizationPolicy 最小权限**：默认拒绝，仅放行必要调用
5. **性能评估**：每个 Sidecar 约占用 0.5-1 vCPU + 50-100MB 内存

---

## 七、参考资源

- [Istio 官方文档](https://istio.io/latest/docs/)
- [Envoy 架构文档](https://www.envoyproxy.io/docs/envoy/latest/)
- [SPIFFE 标准](https://spiffe.io/)
- [xDS 协议规范](https://www.envoyproxy.io/docs/envoy/latest/api-docs/xds_protocol)
