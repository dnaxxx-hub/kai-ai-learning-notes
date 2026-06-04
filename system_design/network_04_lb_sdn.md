# 计算机网络第4课：负载均衡与SDN

## 一、负载均衡（Load Balancing）

### 1.1 L4 vs L7 负载均衡

| 维度 | L4（传输层） | L7（应用层） |
|------|-------------|-------------|
| 工作层次 | TCP/UDP 四元组（源IP:Port → 目的IP:Port） | HTTP 协议内容（URL、Header、Cookie） |
| 转发粒度 | TCP 连接级 | HTTP 请求级（同一个 TCP 连接可路由到不同后端） |
| 性能 | 高（不解析应用层，纯转发） | 中（需解析 HTTP，有一定开销） |
| 灵活性 | 低 | 高（可按域名、路径、用户路由） |
| 典型代表 | LVS、HAProxy L4 mode、F5 | Nginx、HAProxy L7 mode、Envoy |

**L4 模式（通用）**：
```
Client:Port → LB:VIP → Backend[1..N]:Port
LB 直接修改目的IP+端口，TCP 流量透传
```

**L7 模式（协议感知）**：
```
Client → LB (HTTP 终结) → Backend (新 HTTP 连接)
LB 解析 Host/Path/Cookie，按应用规则分配
```

### 1.2 负载均衡算法

#### 轮询（Round Robin）
- 顺序循环分配，简单公平
- 存在问题：不感知后端负载差异

```python
# 轮询算法示意
class RoundRobin:
    def __init__(self, servers):
        self.servers = servers
        self.idx = 0

    def select(self):
        s = self.servers[self.idx]
        self.idx = (self.idx + 1) % len(self.servers)
        return s
```

#### 最少连接（Least Connections）
- 选择当前活跃连接数最少的后端
- 适合长连接场景（WebSocket、数据库连接池）

```python
class LeastConnections:
    def select(self, servers):
        # 选活跃连接最少的
        return min(servers, key=lambda s: s.active_conns)
```

#### 一致性哈希（Consistent Hashing）
- 将请求的 Key（如 Client IP、Session ID）哈希到 2^32 环上
- 后端节点映射到环上多个虚拟节点
- 增删节点时：**仅影响相邻节点的流量**，而不是全部

```python
import hashlib

class ConsistentHash:
    def __init__(self, nodes, vnodes=150):
        self.vnodes = vnodes
        self.ring = []
        for node in nodes:
            for i in range(vnodes):
                h = self._hash(f"{node}-{i}")
                self.ring.append((h, node))
        self.ring.sort()

    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def select(self, key):
        h = self._hash(key)
        for ring_hash, node in self.ring:
            if h <= ring_hash:
                return node
        return self.ring[0][1]  # wrap around
```

#### 健康检查（Health Check）
- **主动检查**：LB 定时发 TCP 连接 / HTTP GET / ICMP ping
- **被动检查**：LB 根据连续错误次数摘除节点
- 摘除后流量切换到其他健康节点

### 1.3 L4 TCP 代理模拟

```python
import socket
import threading

BACKENDS = [("127.0.0.1", 8081), ("127.0.0.1", 8082)]
rr_idx = 0
rr_lock = threading.Lock()

def handle_client(client_sock):
    global rr_idx
    with rr_lock:
        backend = BACKENDS[rr_idx]
        rr_idx = (rr_idx + 1) % len(BACKENDS)

    backend_sock = socket.socket()
    backend_sock.connect(backend)

    # 双向转发（两个方向各一个线程）
    def forward(src, dst):
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)

    t1 = threading.Thread(target=forward, args=(client_sock, backend_sock))
    t2 = threading.Thread(target=forward, args=(backend_sock, client_sock))
    t1.start(); t2.start()
    t1.join(); t2.join()
    client_sock.close()
    backend_sock.close()
```

### 1.4 L7 HTTP 路由模拟

```python
from http.server import HTTPServer, BaseHTTPRequestHandler

ROUTES = {
    "/api/*":   "127.0.0.1:9001",
    "/web/*":   "127.0.0.1:9002",
    "/static/*": "127.0.0.1:9003",
}

class HTTPProxy(BaseHTTPRequestHandler):
    def do_GET(self):
        backend = None
        for prefix, target in ROUTES.items():
            pattern = prefix.replace("*", "")
            if self.path.startswith(pattern):
                backend = target
                break
        if backend:
            self.send_response(200)
            self.send_header("X-Backend", backend)
            self.end_headers()
            self.wfile.write(f"Routed to {backend}".encode())
        else:
            self.send_error(404, "No route")
```

---

## 二、SDN（软件定义网络）

### 2.1 核心思想：控制面与数据面分离

```
传统网络：
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 交换机 A  │    │ 交换机 B  │    │ 交换机 C  │
  │ (控制+数据)│◄──►│ (控制+数据)│◄──►│ (控制+数据)│
  └──────────┘    └──────────┘    └──────────┘
  每台设备独立运行路由协议，分布式决策

SDN 网络：
  ┌──────────────────────────────────┐
  │        SDN Controller            │   ← 集中控制面
  │  (OpenDaylight / ONOS / Ryu)     │   下发流表
  └────────┬───────────┬─────────────┘
           │ OpenFlow  │ OpenFlow
  ┌────────▼──┐  ┌────▼──────────┐
  │ 交换机 A   │  │ 交换机 B       │   ← 纯数据面
  │ 只做转发   │  │ 只做转发       │      流表匹配+动作
  └───────────┘  └───────────────┘
```

### 2.2 OpenFlow 流表

**流表项结构**：

| 匹配域（Match Fields） | 优先级 | 计数器 | 指令/动作 | 超时 |
|:---|:---|:---|:---|:---|
| ingress_port + eth_dst + ip_src + ... | 65535 | packets/bytes | Output:port | idle_timeout |

**匹配字段**（可自定义组合）：
- 入端口、源/目的 MAC、以太网类型
- 源/目的 IP、IP 协议（TCP=6, UDP=17）
- TCP/UDP 源/目的端口
- VLAN ID、MPLS 标签等

**动作**：
| 动作 | 含义 |
|------|------|
| Output(port) | 从指定端口转发 |
| Drop | 丢弃 |
| Set-Field(ip_dst=...) | 修改包头字段（NAT） |
| Set-Queue(qid) | 设置 QoS 队列 |
| Group(gid) | 转发到组表（多播/ECMP） |
| Controller | 封装成 Packet-In 发给控制器 |

**流表匹配流程**：
```
Packet In → 查流表（按优先级从高到低）
    ├─ 命中 → 执行动作（转发/修改/丢弃）
    └─ 未命中 → 发 Packet-In 给 Controller
                 Controller 决策后下发新流表项
```

### 2.3 Python 模拟：简单 SDN 转发器

```python
class OFSwitch:
    def __init__(self, dp_id):
        self.dp_id = dp_id
        self.flow_table = []

    def add_flow(self, match, actions, priority=0):
        self.flow_table.append({
            "match": match,
            "actions": actions,
            "priority": priority,
            "packets": 0,
        })
        # 按优先级降序排列
        self.flow_table.sort(key=lambda f: f["priority"], reverse=True)

    def process_packet(self, packet):
        for flow in self.flow_table:
            if self._match(flow["match"], packet):
                flow["packets"] += 1
                return flow["actions"]
        # 未命中 → 通知控制器
        return self._packet_in(packet)

    def _match(self, match, packet):
        # 简化的匹配逻辑
        for key, val in match.items():
            if packet.get(key) != val:
                return False
        return True

    def _packet_in(self, packet):
        print(f"[Packet-In] dp_id={self.dp_id} packet={packet}")
        return ["CONTROLLER"]


# 模拟：弹性流量路径切换
sw = OFSwitch(dp_id=1)
sw.add_flow({"eth_dst": "00:11"}, [("OUTPUT", 2)], priority=100)
sw.add_flow({"eth_dst": "00:22"}, [("OUTPUT", 3)], priority=100)
sw.add_flow({}, [("OUTPUT", "CONTROLLER")], priority=0)  # 默认转发到控制器

# 控制器收到 Packet-In 后，可下发新流表（动态编程）
```

---

## 三、VxLAN 与 VPC

### 3.1 为什么需要 VxLAN？

传统 VLAN（802.1Q）只有 12-bit VLAN ID → 最多 4096 个网络。云环境下远远不够。

**VxLAN 解决**：将 L2 以太网帧封装在 UDP 中穿越 L3 网络。

```
┌─────────────────────────────────────────────────┐
│ Outer MAC  │ Outer IP │ Outer UDP │ VxLAN | 原始帧 |
│             （VTEP 间隧道）   │ VNI=24bit │
└─────────────────────────────────────────────────┘
                        VNI: 16,777,216 个网络
```

### 3.2 VTEP（VxLAN Tunnel Endpoint）

```
                    VTEP-1                     VTEP-2
  ┌──────┐     ┌──────────────┐     L3      ┌──────────────┐     ┌──────┐
  │ VM-A │◄───►│   VxLAN GW   │◄───IP网────►│   VxLAN GW   │◄───►│ VM-B │
  │ VPC1 │     │ 10.0.0.1:4789│  隧道       │10.0.0.2:4789 │     │ VPC1 │
  └──────┘     └──────────────┘              └──────────────┘     └──────┘
```

### 3.3 VPC 租户隔离

| 概念 | 说明 |
|------|------|
| VPC | 虚拟私有云，每个租户一个隔离网络 |
| 子网（Subnet） | VPC 内的 IP 段，跨可用区 |
| 路由表 | 控制 VPC 内部 + 对外通信 |
| 安全组 | 有状态防火墙，白名单规则 |
| VNI | VxLAN Network Identifier，标识 VPC |

**租户隔离原理**：不同 VPC 使用不同 VNI，VTEP 仅在相同 VNI 内广播/转发。

### 3.4 Python VPC 模拟

```python
class VxLAN_Tunnel:
    def __init__(self, vni):
        self.vni = vni

    def encapsulate(self, inner_frame, src_ip, dst_ip):
        """外层 UDP 封装"""
        return {
            "outer_ip_src": src_ip,
            "outer_ip_dst": dst_ip,
            "vni": self.vni,
            "payload": inner_frame,
        }

class VPC:
    def __init__(self, name, vni):
        self.name = name
        self.vni = vni
        self.vms = {}

    def add_vm(self, mac, ip):
        self.vms[mac] = {"ip": ip, "vni": self.vni}

    def forward(self, src_mac, dst_mac, frame):
        # VPC 内部转发，VNI 必须一致
        if dst_mac not in self.vms:
            return None  # ARP 失败/隔离
        return f"[VPC={self.name}, VNI={self.vni}] {src_mac}→{dst_mac}: {frame}"


# 两个隔离的 VPC
vpc_a = VPC("Tenant-A", 10001)
vpc_b = VPC("Tenant-B", 10002)

vpc_a.add_vm("AA:AA", "10.0.1.2")
vpc_b.add_vm("BB:BB", "10.0.2.2")

print(vpc_a.forward("AA:AA", "AA:AA", "ping"))   # ✅ 通
print(vpc_a.forward("AA:AA", "BB:BB", "ping"))   # ❌ 不通（不同 VPC）
```

---

## 四、总结

| 技术 | 核心思想 | 关键协议/组件 |
|------|---------|-------------|
| L4 LB | 四元组转发，性能高 | LVS、F5、HAProxy |
| L7 LB | HTTP 内容路由，灵活 | Nginx、Envoy、Traefik |
| 一致性哈希 | 最小化节点变动影响 | Ketama、Hash Ring |
| SDN | 控制面与数据面分离 | OpenFlow、OVS、Ryu |
| VxLAN | L2 over L3 隧道 | VTEP、VNI 24-bit |
| VPC | 多租户网络隔离 | VNI + 路由表 + 安全组 |

> 负载均衡解决了**流量分发**问题，SDN 解决了**网络编程化**问题，VxLAN+VPC 解决了**多租户隔离**问题。三者共同构成了现代数据中心和云网络的基石。
