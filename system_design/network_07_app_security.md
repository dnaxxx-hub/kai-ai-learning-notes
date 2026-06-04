# 计算机网络 #7：应用层与安全协议实战

> 前置：TCP/IP协议栈深度(#6)，CDN/边缘计算(#1~#5)
> 定位：从协议规范到 Wireshark 抓包落地，聚焦生产排障能力

---

## 1. HTTP/2 深度

### 1.1 二进制分帧层（Binary Framing）

HTTP/2 摒弃了 HTTP/1.x 的文本协议，引入二进制分帧：

```
Frame 结构 (9B 固定头 + payload):
  +-----------------------------------------------+
  | Length (24b)     | Type (8b) | Flags (8b)     |
  +------------------+-----------+----------------+
  | R (1b) | Stream Identifier (31b)              |
  +-----------------------------------------------+
  | Frame Payload (variable)                      |
  +-----------------------------------------------+
```

- **Stream ID**：奇数=客户端发起，偶数=服务端推送
- **Type**：DATA(0x0), HEADERS(0x1), PRIORITY(0x2), RST_STREAM(0x3), SETTINGS(0x4), PUSH_PROMISE(0x5), PING(0x6), GOAWAY(0x7), WINDOW_UPDATE(0x8), CONTINUATION(0x9)
- **Flags**：END_STREAM(0x1), END_HEADERS(0x4), PADDED(0x8), PRIORITY(0x20)

### 1.2 HPACK 压缩

| 表类型 | 内容 | 大小 |
|--------|------|------|
| 静态表 | 61 个预定义头部（:method: GET, :status: 200 等） | 固定 |
| 动态表 | 双方动态维护，LRU 淘汰 | 默认 4096 字节 |

**索引引用方式**：
- 索引值 ≤ 61 → 静态表
- 索引值 > 61 → 动态表 (index - 61)
- 字面量插入 → Huffman 编码后添加到动态表

```
HPACK 编码示例：
  :method: GET    → 索引 2（静态表，仅1字节）
  :scheme: https  → 索引 7（静态表）
  x-my-header     → 字面量（Huffman编码）+ 值
```

### 1.3 服务器推送

- 客户端发送请求 → 服务端推测资源（如 HTML 关联的 CSS/JS）
- 服务端 **先**发 `PUSH_PROMISE` frame（告知客户端即将推送），**后**发 `HEADERS` + `DATA`
- 客户端可以 `RST_STREAM` 拒绝推送（流 ID 推给服务端）
- **时机**：`PUSH_PROMISE` 必须在响应 HEADERS 之前发送

### 1.4 TCP HOL 阻塞

```
HTTP/2 多路复用逻辑视图：
  Stream 1 ████████████████           ← 大文件下载
  Stream 2 ████░░░░                    ← 小请求（被阻塞）
  
物理上共用一个 TCP 连接：
  [S1 packet] [S1 packet] [S1 packet ←丢包]
  [S2 packet] S2 在队列中等待 S1 重传完成
```

**本质**：TCP 保证有序交付 → 一个丢包阻塞所有 Stream。这是 HTTP/3 要解决的核心问题。

---

## 2. HTTP/3 与 QUIC 实战

### 2.1 QUIC Packet 类型

| Packet Type | 用途 | 加密 |
|-------------|------|------|
| Initial | 首次连接，包含 TLS ClientHello | 部分加密 |
| Handshake | 密钥交换阶段 | 握手密钥 |
| 1-RTT | 正常数据传输 | 完整加密 |
| 0-RTT | 复用之前会话，立即发送数据 | 前向密钥 |

### 2.2 Stream 独立可靠传输

```
QUIC Connection (UDP)
├── Stream 1 (独立滑动窗口，独立ACK)
├── Stream 2 (独立滑动窗口，独立ACK)
├── Stream 3 (独立滑动窗口，独立ACK)
└── ...

TCP:      [S1-S2-S3] ← 一个丢包全部block
QUIC:     [S1█] [S2█] [S3█] ← 独立ACK，互不影响
```

**Stream Frame 结构**：
- Stream ID (variable-length)
- Offset (数据偏移，支持乱序到达)
- Length
- Data

### 2.3 0-RTT 重放攻击防范

```
攻击者捕获 0-RTT 数据包 → 重放给服务端

防御策略：
1. 服务端仅接受幂等操作（GET/HEAD/OPTIONS）
2. 0-RTT 中的非幂等请求 MUST be rejected
3. 服务端维护 0-RTT 重放窗口，检测重复
4. 使用 "Anti-Replay" 机制（Ticket Age */
```

### 2.4 连接迁移

- TCP 使用 `(src_ip, src_port, dst_ip, dst_port)` 四元组标识连接
- QUIC 使用 **Connection ID**（64-bit），独立于 IP:Port
- 切换 WiFi→5G 时，发送新包带上相同 Connection ID
- 服务端识别 → 继续通信，无需重新握手

### QUIC vs TCP 对比

| 特性 | TCP + TLS | QUIC |
|------|-----------|------|
| 传输层 | 内核 | 用户态（可快速迭代） |
| 握手 | 1 RTT(TCP) + 1 RTT(TLS) = 2 RTT | 0-RTT / 1-RTT |
| 流隔离 | 无（单TCP通道） | 独立 Stream，独立 ACK |
| 连接迁移 | 不支持（IP:Port 绑定） | Connection ID 支持 |
| 队头阻塞 | TCP HOL | 无（Stream 级独立） |
| 头部加密 | 无（TCP header 可见） | 全加密 |
| 实现复杂度 | 内核协议栈成熟 | 依赖用户态库（quiche/msquic） |

**抓包命令**：
```bash
# QUIC 抓包（需要解密key）
tcpdump -i any -s0 -w quic.pcap port 443
# Wireshark 过滤器：
# quic
# quic.packet_type == 0  (Initial)
# quic.stream_id == 4
```

---

## 3. WebSocket 实战

### 3.1 握手过程

**客户端请求**：
```
GET /chat HTTP/1.1
Host: server.example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

**服务端响应**：
```
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

**Accept 计算**：
```
accept = Base64(SHA1(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
```

### 3.2 帧格式

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - -+-------------------------------+
|                               |Masking-key, if MASK set to 1  |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
```

**opcode**：
| 值 | 类型 | 说明 |
|----|------|------|
| 0x1 | Text | UTF-8 文本 |
| 0x2 | Binary | 二进制数据 |
| 0x8 | Close | 关闭连接 |
| 0x9 | Ping | 心跳探测 |
| 0xA | Pong | 心跳回复 |

### 3.3 掩码（Masking）

- **客户端 → 服务端**：MASK=1, 32-bit masking-key 必填
- **服务端 → 客户端**：MASK=0
- **目的**：防止缓存污染攻击（攻击者利用 HTTP 缓存投毒）
- **原理**：掩码让 payload 不可预测，避免攻击者控制 on-the-wire 数据

### 3.4 心跳保活

- 客户端或服务端发送 Ping Frame（opcode=0x9）
- 接收方必须在**收到 Ping 后尽快**回复 Pong（opcode=0xA）
- Pong 中的 application data 应与对应的 Ping 相同
- 超时未收到 Pong → 判定断连，触发重连

**抓包命令**：
```bash
# WebSocket 抓包（先抓HTTP Upgrade，再追踪WebSocket）
tcpdump -i any -s0 -w websocket.pcap port 8080
# Wireshark 过滤器：
# websocket
# websocket.opcode == 1  (text frame)
# websocket.opcode == 8  (close frame)
# tcp.port == 8080 and websocket
```

---

## 4. gRPC 核心

### 4.1 HTTP/2 作为传输层

gRPC 直接构建在 HTTP/2 之上：

- 每个 gRPC 调用 = 一个 HTTP/2 Stream
- 请求 → HTTP/2 HEADERS frame（`:method: POST`）+ DATA frame（Protobuf payload）
- 响应 → HTTP/2 HEADERS frame（`:status: 200`）+ DATA frame
- 元数据 → HTTP/2 HEADERS 末尾的 `grpc-*` 头

```
gRPC over HTTP/2:
  Stream 1: HEADERS → DATA → HEADERS → DATA (unary)
  Stream 2: HEADERS → DATA → DATA → ... (server streaming)
  Stream 3: HEADERS → DATA → DATA → HEADERS → DATA (bidirectional)
```

### 4.2 Protocol Buffers 编码

**Varint 编码**：
```
数字 300 的 varint 编码：
  300 = 1010 1100  0000 0010
  Step1: 拆分7bit组 + MSB标志
    [010 1100][000 0010]
    [1 010 1100][0 000 0010]  ← MSB=1表示后续还有, MSB=0表示结束
  Step2: 小端顺序写入
    1010 1100  0000 0010  →  0xAC 0x02
```

**Zigzag 编码**（sint32/sint64）：
```
n         → zigzag(n)
0         → 0
-1        → 1
1         → 2
-2        → 3
2         → 4
公式: zigzag(n) = (n << 1) ^ (n >> 31)
```

**Wire Type**：
| Type | 意义 | 用于 |
|------|------|------|
| 0 | Varint | int32/uint64/bool/enum |
| 1 | 64-bit | fixed64/sfixed64/double |
| 2 | Length-delimited | string/bytes/embedded message |
| 5 | 32-bit | fixed32/sfixed32/float |

**抓包**：
```bash
# gRPC（依赖HTTP/2）
tcpdump -i any -s0 -w grpc.pcap port 50051
# Wireshark 过滤器：
# grpc
# http2.streamid == 1
# grpc.status_code == 0
```

### 4.3 四种 RPC 模式

| 模式 | 客户端 | 服务端 | 使用场景 |
|------|--------|--------|----------|
| Unary | 1 req | 1 resp | 传统请求-响应 |
| Server Streaming | 1 req | N resp | 日志推送、订阅推送 |
| Client Streaming | N req | 1 resp | 文件上传、批量写入 |
| Bidirectional | N req | N resp | 实时聊天、AI 流式推理 |

### 4.4 负载均衡

| 方式 | 原理 | 问题 |
|------|------|------|
| **Lookaside**（K8s Service） | 客户端 DNS 解析 → L4 LB → 后端 Pods | 连接结束前无法切换，**最终一致** |
| **Client-side**（gRPC LB Policy） | 客户端维护后端列表，**精确** round_robin | 需要服务发现（etcd/consul） |

**推荐做法**：gRPC 的 long-lived HTTP/2 连接不兼容传统 L4 LB。使用 **Client-side LB** + 服务发现，或 **Proxy LB**（如 Envoy/Linkerd）。

---

## 5. TLS 1.3 深度

### 5.1 完整握手

```
Client                                      Server
  |                                         |
  |----- ClientHello ---------------------->|  (key_share, supported_versions, sig_algs)
  |                                         |
  |<---- ServerHello -----------------------|  (key_share, version=1.3)
  |<---- EncryptedExtensions ---------------|  (ALPN, server_name)
  |<---- Certificate -----------------------|  (公钥证书链)
  |<---- CertificateVerify -----------------|  (签名验证)
  |<---- Finished --------------------------|  (HMAC of handshake)
  |                                         |
  |----- Finished ------------------------->|
  |                                         |
  |<=========== Application Data ==========>|  1-RTT 数据
```

### 5.2 0-RTT 与 PSK

```
Client                                      Server
  |                                         |
  |----- ClientHello (pre_shared_key) ----->|  + 0-RTT Data (Early Data)
  |<---- ServerHello -----------------------|
  |<---- EncryptedExtensions ---------------|
  |<---- Finished ------------------------->|
  |<======== Application Data =============>|
```

- **PSK**：Pre-Shared Key，通过第一次完整握手的 Session Ticket 建立
- **Session Ticket**：服务端加密发给客户端，下次连接时使用
- **0-RTT 风险**：数据包可被重放 → 服务端必须限制幂等操作
- **限制**：0-RTT 不支持 forward secrecy（前向安全）

### 5.3 密钥派生

```
PSK (Pre-Shared Key)
    │
    ▼
HKDF-Extract(salt=0, PSK) → Early Secret
    │
    ├── HKDF-Expand-Label("traffic", "c e traffic")  → Client Early Traffic Secret
    │
    ▼
HKDF-Extract(salt=Early Secret, (EC)DHE) → Handshake Secret
    │
    ├── HKDF-Expand-Label("traffic", "c hs traffic") → Client Handshake Traffic Secret
    ├── HKDF-Expand-Label("traffic", "s hs traffic") → Server Handshake Traffic Secret
    │
    ▼
HKDF-Extract(salt=Handshake Secret, 0) → Master Secret
    │
    ├── HKDF-Expand-Label("traffic", "c ap traffic") → Client Application Traffic Secret
    ├── HKDF-Expand-Label("traffic", "s ap traffic") → Server Application Traffic Secret
    ├── HKDF-Expand-Label("exporter", "exporter")    → Exporter Secret
    ├── HKDF-Expand-Label("res master", "res master")→ Resumption Master Secret
```

**总共 6 个 Secret**：Early → 2 Handshake → 2 Application + Exporter + Resumption

**抓包命令**：
```bash
# TLS 1.3 抓包（需要获取 keylog）
export SSLKEYLOGFILE=/tmp/tls.keylog
curl https://example.com
tcpdump -i any -s0 -w tls.pcap port 443

# Wireshark 配置：
# Edit → Preferences → TLS → (Pre)-Master-Secret log filename
# 选中 /tmp/tls.keylog

# Wireshark 过滤器：
# tls.handshake.type == 1      (ClientHello)
# tls.handshake.type == 11     (Certificate)
# tls.handshake.type == 15     (CertificateVerify)
# tls.handshake.type == 20     (Finished)
# tls.handshake.extensions_supported_version == "0x0304" (TLS 1.3)
```

---

## 6. 网络排障实战

### 6.1 抓包工作流

```
生产问题 → tcpdump 抓包 → 拖入 Wireshark → 分析定位
```

**tcpdump 常用**：
```bash
# 抓指定端口，保存文件
tcpdump -i eth0 -s0 -w capture.pcap port 443

# 指定协议+主机
tcpdump -i eth0 tcp and host 10.0.0.1 and port 443

# 有限循环抓包（避免撑满磁盘）
tcpdump -i eth0 -C 100 -W 5 -w capture.pcap port 443
# -C 100: 每个文件100MB
# -W 5: 最多5个文件，滚动覆盖

# 不保存，实时看包内容（-X: hex+ascii）
tcpdump -i any -X port 80
```

**Wireshark 过滤器速查**：

| 过滤表达式 | 说明 |
|-----------|------|
| `tcp.stream eq 0` | 追踪特定 TCP 连接 |
| `http2` | 所有 HTTP/2 帧 |
| `quic` | QUIC 流量 |
| `tls.handshake.type == 1` | 查看 ClientHello |
| `tcp.analysis.flags` | TCP 异常（重传、零窗口等） |
| `http2.streamid == 1 and http2.type == 0` | Stream 1 的 DATA 帧 |
| `websocket` | WebSocket 帧 |
| `grpc` | gRPC 调用 |
| `tcp.analysis.retransmission` | TCP 重传 |
| `tcp.window_size == 0` | 零窗口通知 |
| `tls.handshake.extensions_server_name` | SNI 信息 |

### 6.2 常见问题排查

#### SYN 重传（RTT 太高）
```
Wireshark: tcp.analysis.retransmission
现象：连续多个 [SYN] 重传，无 [SYN, ACK]
原因：RTT 过高 / 防火墙阻断 / 服务端端口未监听
排查：
  1. ping 测 RTT
  2. 确认服务端端口是否 open: nc -zv server 443
  3. 检查 iptables/安全组规则
```

#### 零窗口（接收端负荷）
```
Wireshark: tcp.window_size == 0 或 tcp.analysis.zero_window
现象：接收端宣告窗口为 0，发送端停止发送
原因：接收端应用程序来不及读取缓冲区
排查：
  1. 检查应用进程是否卡死/线程池耗尽
  2. 确认是否出现慢 SQL 或后端调用超时
  3. 查看 receive buffer 是否过小（net.ipv4.tcp_rmem）
```

#### TLS 握手失败
```
Wireshark: tls.handshake.type == 21 (Alert)
现象：
  - [Fatal] Alert (Level: Fatal, Description: Handshake Failure)
  - [Fatal] Alert (Description: Certificate Unknown)
原因：
  1. Cipher mismatch：客户端和服务端没有共同支持的加密套件
  2. 证书过期或 CN/SAN 不匹配
  3. 协议版本不支持（客户端要求 1.3，服务端只支持 1.2）
排查：
  1. 查看 ClientHello 中 cipher_suites 列表
  2. 查看 ServerHello 选择的 cipher
  3. 确认服务端支持的 TLS 版本：nmap --script ssl-enum-ciphers -p 443 target
```

#### HTTP/2 GOAWAY（优雅关闭）
```
Wireshark: http2.type == 7
原因：服务端要重启/更新，通知客户端不要再发新请求
排查：
  - 查看 goaway 中的 last_stream_id，确认已经处理完的流
  - 检查服务端是否频繁重启（持续集成部署）
```

### 6.3 延迟分析

```
一次 HTTPS 请求延迟拆解：

等待DNS     0~20ms      (域名解析缓存？dns缓存命中则0ms)
    ↓
TCP握手     RTT         (一般为10~50ms，跨洲200ms+)
    ↓
TLS握手     1 RTT       (TLS 1.3完整握手，0-RTT复用则0)
    ↓
数据传输    payload/RTT  (取决于带宽和往返次数)
```

**实测命令**：
```bash
# 查看各阶段耗时
curl -w "\n
  time_namelookup: %{time_namelookup}s\n
  time_connect: %{time_connect}s\n
  time_appconnect: %{time_appconnect}s\n
  time_total: %{time_total}s\n
" -o /dev/null -s https://example.com

# 更详细的时间分解
curl -w "@curl-format.txt" -o /dev/null -s https://example.com
```

**快速定位瓶颈**：
```
如果 time_connect 很大   → 问题出在网络层（RTT高/丢包）
如果 time_appconnect 大  → TLS 协商慢（证书链太长/密码学操作）
如果 time_namelookup 大  → DNS 解析慢（换公共 DNS / 加缓存）
```

---

## 总结：从 OSI 视角看全链路

```
┌─────────────────────────────────────────────┐
│ 应用层    HTTP/2, HTTP/3, WebSocket, gRPC    │
├─────────────────────────────────────────────┤
│ 表示层    HPACK, Protobuf, TLS 1.3           │
├─────────────────────────────────────────────┤
│ 会话层    QUIC Connection, HTTP/2 Stream     │
├─────────────────────────────────────────────┤
│ 传输层    TCP / QUIC (over UDP)              │
├─────────────────────────────────────────────┤
│ 网络层    IP (Connection ID for QUIC)        │
└─────────────────────────────────────────────┘

抓包三板斧：
1. tcpdump -i any -s0 -w capture.pcap port 443
2. Wireshark 过滤器：tcp.analysis.flags 或对应协议过滤器
3. 定位问题：延迟拆解 → 重传/窗口 → 握手/证书
```
