# K8s/云原生 #4：Service、Ingress 与网络模型

> 2026-05-17
> 前置：Workload 控制器 #3

## 1. K8s 网络模型的核心约束

K8s 网络模型有 3 条不可违反的约束：

1. **所有 Pod 都能与所有其他 Pod 直接通信**（无 NAT）
2. **所有 Node 都能与所有 Pod 直接通信**（无 NAT）
3. **Pod 看到的自身 IP 就是其他 Pod 看到的它的 IP**（地址透明）

这意着 K8s 网络必须是 **扁平 Overlay 网络**——通过 CNI 插件实现。

| CNI 插件 | 模式 | 特点 |
|---------|------|------|
| **Flannel** | VXLAN | 简单、性能略低 |
| **Calico** | BGP / IPIP | 高性能、支持 NetworkPolicy |
| **Cilium** | eBPF | 极高性能、安全可观测性 |
| **Weave** | 自建 UDP | 简单、自动组网 |

## 2. Service

### 2.1 为什么需要 Service

Pod 的生命周期是短暂的——IP 随时变化。Service 提供一个**稳定的虚拟 IP**，负载均衡到一组 Pod。

### 2.2 Service 类型

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
spec:
  selector:
    app: nginx           # 匹配 Pod 的 label
  ports:
  - protocol: TCP
    port: 80             # Service 端口
    targetPort: 8080     # Pod 端口（不填默认等于 port）
```

四种 Service 类型：

| 类型 | 访问方式 | 适用场景 |
|------|---------|---------|
| **ClusterIP** | 集群内虚拟 IP（默认） | 内部服务间调用 |
| **NodePort** | 节点 IP + 随机端口 (30000-32767) | 开发调试、外部流量直连 |
| **LoadBalancer** | 云厂商 LB + 自动创建外部 IP | 对外暴露服务给公网 |
| **ExternalName** | DNS CNAME | 引入集群外服务 |

### 2.3 kube-proxy 与负载均衡

kube-proxy 支持 3 种模式：

| 模式 | 实现 | 性能 | 功能 |
|------|------|------|------|
| userspace | 用户态代理 | ❌ 慢 | 基本 |
| iptables | 内核态 NAT 规则 | ✅ 快 | 基本 |
| IPVS | 内核态 LVS | ✅✅ 很快 | 丰富（轮询/最小连接/随机）|

当 Service 返回的 Pod IP 列表变化时：
- iptables 模式：更新所有 iptables 规则（集群规模增大时 O(n) 性能下降）
- IPVS 模式：只更新内核哈希表（O(1) 更新）

**集群 > 1000 个 Service 时建议切 IPVS**。

### 2.4 无头 Service（Headless Service）

```yaml
spec:
  clusterIP: None          # 不分配 ClusterIP
  selector:
    app: stateful-app
```

DNS 直接返回所有匹配 Pod 的 IP 列表。用于 StatefulSet 的稳定网络标识（Pod 名.服务名.namespace.svc.cluster.local）。

## 3. Ingress

### 3.1 为什么需要 Ingress

NodePort 每个 Service 一个端口，LoadBalancer 每个 Service 一个 LB——资源浪费。

Ingress 提供**7 层负载均衡**（HTTP/HTTPS），一个入口点路由到多个 Service。

```
                               ┌──────────┐
       /api  → api-svc:80      │          │
用户 → Ingress (80/443) ──────┼─ Ingress ├── /web  → web-svc:80
       /ws   → ws-svc:8080    │ Controller│
                               └──────────┘
```

### 3.2 Ingress 定义

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - example.com
    secretName: tls-secret
  rules:
  - host: example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
      - path: /web
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

**pathType**：
- `Prefix` — 前缀匹配（/api 匹配 /api/v1、/api/health）
- `Exact` — 精确匹配（必须完全一致）
- `ImplementationSpecific` — 由 Ingress Controller 定义

### 3.3 Ingress Controller

Ingress 资源本身不做实际的路由——需要 Ingress Controller 来 "解释" Ingress 规则并配置代理。

主流 Ingress Controller：

| Controller | 底层 | 特点 |
|-----------|------|------|
| **nginx-ingress** | Nginx | 最成熟、社区最大 |
| **HAProxy** | HAProxy | 高性能，配置复杂 |
| **Traefik** | Go | 自动发现、动态配置 |
| **Istio Gateway** | Envoy | Service Mesh 集成 |
| **AWS LB Controller** | AWS ALB/NLB | 云原生 |
| **Kong** | OpenResty | API Gateway 能力 |

## 4. 南北向 vs 东西向

K8s 的流量分为两类：

```
南北向（North-South）：外部 → 集群内
  入口：Ingress / LoadBalancer / NodePort / Gateway API

东西向（East-West）：集群内服务间调用
  通信：Service / DNS (CoreDNS) / mTLS / 服务网格
```

## 5. Gateway API（Ingress 的下一代）

K8s Gateway API 是 Ingress 的演进：

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
spec:
  gatewayClassName: istio
  listeners:
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      certificateRef:
        name: my-cert
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
spec:
  parentRefs:
  - name: my-gateway
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api
    backendRefs:
    - name: api-svc
      port: 80
```

**Ingress vs Gateway API**：

| | Ingress | Gateway API |
|---|---------|-------------|
| 基础设施角色 | 开发者定义 | 分离基础设施（Gateway）和路由（Route） |
| 协议支持 | HTTP/HTTPS | HTTP/HTTPS + TCP + UDP + TLS |
| 后端流量拆分 | 有限 | 原生支持（金丝雀/A/B）|
| 可扩展性 | 注解 | 标准 CRD |

## 6. NetworkPolicy（网络安全）

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-allow
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  - Egress
  ingress:                # 允许哪些流量进入
  - from:
    - podSelector:
        matchLabels:
          app: web
    ports:
    - port: 8080
  egress:                 # 允许哪些流量出去
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 10.0.0.0/8
    ports:
    - port: 443
```

**默认行为**：没有 NetworkPolicy 时，允许所有流量。
**一旦定义**：未显式允许的流量被阻止（白名单模型）。

NetworkPolicy 依赖 CNI 支持（Calico / Cilium / Weave，Flannel 不支持）。

## 总结

```
Service → 虚拟 IP + 负载均衡（4层 L4）
Ingress → 路由规则 + TLS 终止（7层 L7）
Gateway API → Ingress 的下一代（跨协议/角色分离）
NetworkPolicy → 网络安全白名单

kube-proxy 选择：
  小集群 → iptables（够用）
  大集群 → IPVS（性能好）
  eBPF   → Cilium（最高性能+可观测）
```
