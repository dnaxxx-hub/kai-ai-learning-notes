# QUIC 协议深度解析

## 什么是 QUIC？

**QUIC** (Quick UDP Internet Connections) = Google 设计的基于 UDP 的传输协议。

- 最初由 Google 在 2012 年设计并部署
- 2016 年提交 IETF 标准化 (RFC 8999, 9000, 9001, 9002)
- HTTP/3 的底层传输协议

## 为什么需要 QUIC？TCP 的三大问题

| TCP 问题 | 具体表现 | QUIC 如何解决 |
|----------|---------|---------------|
| 连接建立慢 | TCP握手(1RTT) + TLS握手(1-2RTT) = 2-3RTT | 0-RTT 或 1-RTT |
| 队头阻塞 | TCP按序交付, 丢包阻塞后续所有流 | 独立流, 一个流丢包不影响其他 |
| 连接迁移 | 切换WiFi→蜂窝, TCP连接断开 | 连接ID不变, 无缝迁移 |
| 内核升级难 | TCP在操作系统内核中, 更新慢 | 用户态UDP, 可快速迭代 |

## 1. 连接建立 (0-RTT)

### 首次连接 (1-RTT)

```
Client                              Server
  |                                   |
  | ---- Initial (1-RTT) --------->  |  Step 1: 客户端Hello
  |                                   |  (包含TLS 1.3 ClientHello)
  | <--- Handshake (1-RTT) ---------  |  Step 2: 服务端Hello + 证书
  |                                   |
  | ---- Handshake (1-RTT) -------->|  Step 3: 客户端完成
  |                                   |
  | ==== 连接建立, 可以发送数据 ======== |
  |                                   |
  | ---- 1-RTT (加密数据) ---------->|  立刻发送应用数据
```

### 再次连接 (0-RTT)

```
Client (之前连接过, 缓存了服务端参数)
  |                                   |
  | ---- 0-RTT (加密数据) ---------->|  首次包就包含应用数据!
  | + Initial                         |
  |                                   |
  | <--- Handshake (1-RTT) ---------  |  服务端回复握手完成
  |                                   |
  | ======== 0RTT 数据直接可用 ======== |
```

**0-RTT 限制**：
- 只能发送幂等的请求(GET, 非POST)
- 存在重放攻击风险(需应用层处理)

## 2. 多路复用 — 无队头阻塞

### TCP 的队头阻塞

```
TCP 连接 (只有一个流):
[Packet 1 OK] [Packet 2 OK] [Packet 3 LOST] [Packet 4 OK] [Packet 5 OK]
                                                 ↑ 必须等Packet 3重传!
                                                 所有请求都阻塞

即使只有一个流丢包, 所有流(HTTP/2)都卡住
```

### QUIC 的独立流

```
QUIC 连接 (多个独立流):
流1: [P1 OK] [P2 OK] ------> [P3(重传后到达)] [P4 OK]
流2: [P1 OK] [P2 OK] [P3 OK] [P4 OK] [P5 OK]  ← 完全不受流1丢包影响
流3: [P1 OK] [P2 OK] [P3 OK] [P4 OK]          ← 也不受影响
```

**关键**：每个流独立有序, 一个流丢包只影响该流内部, 其他流照常处理。

### 流 ID 和类型

| 类型 | 流ID特征 | 方向 |
|------|---------|------|
| 客户端发起双向流 | 奇数 | 双向 |
| 服务端发起双向流 | 偶数 | 双向 |
| 客户端发起单向流 | 奇数 | 单向 |
| 服务端发起单向流 | 偶数 | 单向 |

## 3. 连接迁移 (Connection Migration)

**场景**: 用户从 Wi-Fi 走到户外, 手机自动切到蜂窝网络。

```
TCP: IP:端口 → IP:端口 (四元组)
     Wi-Fi IP改变 → TCP连接断开 → 重建连接

QUIC: 使用 Connection ID (64位随机值)
     Wi-Fi:  ConnID=ABC,  IP=192.168.1.2
     切换:   ConnID=ABC,  IP=10.0.0.5 (蜂窝)
     结果:   对方根据ConnID识别是同一连接, 继续通信
```

**优势**：
- 连接迁移**无缝**, 应用层无感知
- 不需要重新握手
- 移动端体验极大提升

## 4. QUIC 与 TCP+TLS 对比

| 特性 | TCP + TLS 1.3 | QUIC |
|------|--------------|------|
| 传输层 | TCP (内核) | UDP (用户态) |
| 加密 | TLS on top | 内置TLS 1.3 |
| 连接建立 | 1-RTT (TLS 1.3) | 0-RTT / 1-RTT |
| 队头阻塞 | 有(TCP层) | 无(独立流) |
| 连接迁移 | 不支持 | 原生支持 |
| 拥塞控制 | 内核实现(更新慢) | 用户态(更新快) |
| 流量控制 | 连接级 | 连接级 + 流级 |
| 丢包重传 | 按包序号 | 按流+包序号 |
| 前向纠错(FEC) | 无 | 支持 |
| 实现复杂度 | 简单(协议成熟) | 较复杂 |

## 5. QUIC 的加密特性

QUIC **强制加密** (不像TCP可选择TLS或不加密):
- 除Initial包外, 所有包加密
- Initial 包也做了部分保护
- 基于TLS 1.3, 使用AEAD加密
- 密钥更新: 握手完成后可更新密钥(PFS)

### 包保护层次

```
QUIC Packet:
┌─────────────────────────────────────┐
│ Public Header (可见但受限)           │
│  - Connection ID (可加密)            │
│  - Packet Number (加密)             │
├─────────────────────────────────────┤
│ Protected Payload (完全加密)         │
│  - 流数据                           │
│  - 流帧头部                         │
│  - 控制帧                           │
└─────────────────────────────────────┘
```

## 6. QUIC 的拥塞控制

QUIC 不绑定特定拥塞控制算法, 实现了**可插拔**的拥塞控制:
- TCP NewReno (默认兼容)
- CUBIC
- BBR (推荐, 适合QUIC特性)
- 自定义算法

**关键区别**: QUIC 的RTT和丢包检测更精确
- 单调递增的Packet Number (TCP可能被重传混淆)
- 更精确的RTT采样

## 7. 当前部署

| 平台 | QUIC 支持 | 备注 |
|------|-----------|------|
| Chrome | 全量启用 | 所有Google服务 |
| Edge | 启用 | Chromium内核 |
| Safari | 启用 | 从iOS 14+ / macOS 11+ |
| Firefox | 启用 | 默认开启 |
| YouTube | 全量QUIC | 视频流体验提升明显 |
| Google Search | 全量QUIC | 0-RTT显著加速 |
| Cloudflare | 支持 | 可开启HTTP/3 |

### 如何验证 QUIC？

```bash
# 检查浏览器是否使用QUIC
chrome://net-export/   → 抓取网络日志
chrome://net-internals/#quic  → QUIC会话信息

# curl 测试 HTTP/3
curl --http3 -I https://www.google.com

# 抓包分析 QUIC
tcpdump -i any -n udp port 443
# 查看UDP 443端口的流量

# QUIC 丢包模拟
tc qdisc add dev eth0 root netem loss 5%

# 检查 QUIC 连接
ss -unap | grep 443    # 查看UDP 443连接
```
