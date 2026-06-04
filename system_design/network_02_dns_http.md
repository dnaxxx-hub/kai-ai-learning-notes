# 计算机网络第2课：DNS 系统与 HTTP 协议演进

> 学习日期：2026-05-10
> 核心主题：从 DNS 解析到 HTTP/1.1 → HTTP/2 → HTTP/3 的完整演进路径

---

## 1. DNS 系统（Domain Name System）

### 1.1 层次结构

DNS 是一个分布式、层次化的命名系统，将人类可读的域名（如 `www.example.com`）转换为机器可读的 IP 地址。

```
         ┌─────────────────────────────────┐
         │        根域名服务器 (Root)        │  ← 13 组逻辑根服务器（A-M）
         │    a.root-servers.net (198.41.0.4)   │
         └────────────┬────────────────────┘
                      │
         ┌────────────▼────────────────────┐
         │    顶级域名服务器 (TLD)          │  ← .com, .cn, .org, .net ...
         │    a.gtld-servers.net           │
         └────────────┬────────────────────┘
                      │
         ┌────────────▼────────────────────┐
         │    权威域名服务器 (Authoritative) │  ← 域名注册商/自建
         │    ns1.example.com → A: 93.184.216.34 │
         └─────────────────────────────────┘
```

**13 个逻辑根服务器（字母 A–M）**：实际部署数百台物理服务器（任播 Anycast），全球分布。标记为：
- A: Verisign（美国）, B: USC-ISI, C: Cogent, D: UMaryland, E: NASA, F: ISC, G: DoD, H: ARL, I: Netnod, J: Verisign, K: RIPE, L: ICANN, M: WIDE

### 1.2 递归查询 vs 迭代查询

```
【递归查询】客户端向本地 DNS 服务器发起，服务器负责完成整个解析链
  客户端 → 本地DNS（递归地查询直到拿到结果，然后返回给客户端）

【迭代查询】客户端/本地DNS 依次向各级服务器查询，每级服务器返回"下一级在哪"
  客户端 → 本地DNS → 根DNS（告诉你TLD在哪）→ TLD DNS（告诉权威在哪）→ 权威DNS（告诉IP）
  每一步服务器都说"我不认识，但那边有人认识"
```

**典型递归解析流程（详细）**：

```
客户端输入 www.example.com
  ↓ (1) 检查浏览器缓存
  ↓ (2) 检查 OS 缓存（hosts 文件 + 系统 DNS 缓存）
  ↓ (3) 查询本地 DNS 服务器（LDNS，如 8.8.8.8 或 192.168.1.1）

LDNS 开始递归解析：
  ↓ (4) 查询根服务器：www.example.com? → 回答：去 .com TLD 服务器，地址是 a.gtld-servers.net
  ↓ (5) 查询 TLD 服务器：www.example.com? → 回答：去 ns1.example.com（权威），地址是 93.184.216.34
  ↓ (6) 查询权威服务器：www.example.com? → 回答：A 记录 → 93.184.216.34

LDNS 将结果缓存后返回给客户端
客户端拿到 IP 后发起 HTTP 连接
```

### 1.3 DNS 缓存链

```
      浏览器缓存 ─→ OS 缓存 ─→ ISP/本地 DNS 缓存 ─→ 权威服务器
        ⌛短        ⌛中         ⌛长              ⌛原始
      (几十秒)    (几分钟)      (TTL)             (TTL=时效)
```

- **浏览器 DNS 缓存**：Chrome 约 1 分钟，可通过 `chrome://net-internals/#dns` 查看
- **操作系统 DNS 缓存**：Windows `ipconfig /displaydns`，缓存时间由 TTL 决定
- **ISP/本地 DNS 缓存**：运营商的递归解析器缓存，通常遵循 TTL 但可能覆盖（有些 ISP 忽略 TTL）
- **TTL（Time To Live）**：DNS 记录上的生存时间，A 记录通常 300~3600 秒，CNAME 有时更长

### 1.4 DNS 记录类型

| 类型 | 名称 | 用途 | 示例值 |
|------|------|------|--------|
| **A** | Address Record | IPv4 地址 | `93.184.216.34` |
| **AAAA** | IPv6 Address | IPv6 地址 | `2606:2800:220:1:248:1893:25c8:1946` |
| **CNAME** | Canonical Name | 域名别名（指向另一个域名） | `www.example.com → example.com` |
| **MX** | Mail Exchange | 邮件服务器（含优先级） | `10 mail.example.com` |
| **NS** | Name Server | 域名服务器 | `ns1.example.com` |
| **TXT** | Text Record | 任意文本（SPF/DKIM/DMARC 验证） | `v=spf1 include:_spf.google.com ~all` |
| **SRV** | Service Record | 指定特定服务的服务器 | `_sip._tcp.example.com` |
| **SOA** | Start of Authority | 区域权威信息（主服务器、管理员邮箱、序列号） | 区域传输的关键 |

**CNAME 的限制**：CNAME 不能与其他记录类型共存（如不能同时有 CNAME 和 MX）。
**MX 优先级**：数字越小优先级越高（10 > 20）。

### 1.5 DNSSEC（DNS Security Extensions）

**问题**：常规 DNS 查询是明文 UDP，可被中间人篡改（DNS 劫持、DNS 投毒）。

**DNSSEC 原理**：

```
DNSSEC 通过数字签名验证 DNS 响应的真实性：
  权威服务器用私钥为 DNS 记录签名生成 RRSIG 记录
  解析器用公钥（DS 记录）验证签名
  形成信任链：根(KSK) → TLD(ZSK) → 二级域(KSK/ZSK)

核心记录类型：
  - RRSIG：资源记录的数字签名
  - DNSKEY：公钥（KSK = Key Signing Key, ZSK = Zone Signing Key）
  - DS：委托签名者（父区域对子区域公钥的哈希）
  - NSEC/NSEC3：证明某记录不存在（防止枚举攻击）
```

**验证流程**：
```
根区签名(.的DNSKEY)  → 已验证
   ↓ DS 记录（含.对.com的哈希）
.com 区签名         → 通过 DS 验证.com的DNSKEY
   ↓ DS 记录（含.com对example.com的哈希）
example.com 签名    → 通过 DS 验证
   ↓ RRSIG（对 A 记录签名）
A记录 93.184.216.34 → 验证签名匹配 → 可信
```

**DNSSEC 现状**：根区 2010 年已签名，.com/.org/.net 等主流 TLD 已签名，但二级域部署率仍不高。

---

## 2. HTTP/1.1

### 2.1 持久连接（Keep-Alive）

HTTP/1.0 默认：每次请求新建 TCP 连接 → 3 次握手开销。
HTTP/1.1 默认：**持久连接**（`Connection: keep-alive`）。

```
HTTP/1.0 模式（每个请求独立连接）：
  [TCP三次握手] → [请求1] → [响应1] → [四次挥手]
  [TCP三次握手] → [请求2] → [响应2] → [四次挥手]
  [TCP三次握手] → [请求3] → [响应3] → [四次挥手]

HTTP/1.1 Keep-Alive：
  [TCP三次握手] → [请求1] → [响应1] → [请求2] → [响应2] → [请求3] → [响应3] → ...
                                                               ↓ 所有请求复用同一 TCP 连接
```

**优势**：
- 减少 TCP 握手次数（降低延迟）
- 减少慢启动（TCP 拥塞窗口逐步增大）
- 减少 TIME_WAIT 状态连接数

### 2.2 管道化（Pipelining）与队头阻塞（HOL）

```
非管道化：请求必须按序——发送请求→等待响应→发送下一个请求
  Client:  [请求1]→··········[响应1]→[请求2]→··········[响应2]
  
管道化：理论上可并发发送多个请求，但响应必须按序返回
  Client:  [请求1]→[请求2]→[请求3]→··········[响应1]→[响应2]→[响应3]
                                            ↑ 问题：如果响应1很慢，会阻塞响应2和3
```

**队头阻塞（Head-of-Line Blocking）**：即使请求是并发的，服务器必须按请求顺序返回响应。如果第一个请求的响应耗时较长（如数据库查询），后续所有响应都被阻塞。

**实际困境**：由于代理服务器和中间件支持不完善，管道化在实践中几乎被废弃。多数浏览器选择：
- 对同一域名建立**6 个 TCP 连接**（Chrome 默认 ~6）
- 使用域名分片（Domain Sharding）：将资源分散到多个子域名

### 2.3 分块传输编码（Chunked Transfer Encoding）

**场景**：服务器无法预先知道响应体大小（如动态生成内容、流式数据）。

**原理**：不使用 `Content-Length` 头，而是使用 `Transfer-Encoding: chunked`。

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

[块大小(HEX)]\r\n
[块数据]\r\n
[块大小(HEX)]\r\n
[块数据]\r\n
...
0\r\n      ← 零长度块表示结束
\r\n

示例：
5\r\n
Hello\r\n
7\r\n
 World!\r\n
0\r\n
\r\n
```

**用途**：SSE（Server-Sent Events）、动态页面、大文件流式传输。

### 2.4 虚拟主机（Host 头）

HTTP/1.1 新增**必须**的 `Host` 头，让一个 IP 地址托管多个域名。

```
GET /index.html HTTP/1.1
Host: www.example.com           ← 服务器据此判断该服务哪个网站
User-Agent: Mozilla/5.0
```

**意义**：这是虚拟主机托管的基础。同一台服务器（同一 IP）、同一端口（80/443），根据 `Host` 头路由到不同虚拟主机配置。

---

## 3. HTTP/2

### 3.1 二进制分帧（Binary Framing）

HTTP/2 核心变化：从 HTTP/1.1 的文本协议改为**二进制协议**。

```
HTTP/1.1（文本）：
  GET /index.html HTTP/1.1\r\n
  Host: example.com\r\n
  \r\n

HTTP/2（二进制帧）：
  ┌───────────────┬─────────────┬─────────────┬──────────────┐
  │ Length (24bit) │ Type (8bit) │ Flags (8bit) │ Stream ID (31bit) │
  ├───────────────┴─────────────┴─────────────┴──────────────┤
  │                     Payload (可变长)                      │
  └─────────────────────────────────────────────────────────┘
```

**帧类型**：
- `DATA`：传输 HTTP 消息体
- `HEADERS`：传输 HTTP 头部
- `PRIORITY`：指定流优先级
- `RST_STREAM`：终止流
- `SETTINGS`：连接参数协商
- `PUSH_PROMISE`：服务端推送承诺
- `PING`：心跳检测
- `GOAWAY`：连接关闭通知
- `WINDOW_UPDATE`：流量控制
- `CONTINUATION`：续传头部

### 3.2 多路复用（Multiplexing）

```
HTTP/1.1 多连接：
  TCP连接1: [请求1]→[请求2]→[请求3]→...（排队）
  TCP连接2: [请求4]→[请求5]→[请求6]→...（排队）
  TCP连接3: [请求7]→[请求8]→[请求9]→...（排队）

HTTP/2 单连接多路复用：
  TCP连接: Stream1:[请求1]  Stream2:[请求4]  Stream3:[请求7]
              混在一起在同一个 TCP 连接上交错传输
           [帧S1][帧S2][帧S3][帧S1][帧S3][帧S2]...
           ↑ Stream ID 区分属于哪个请求，接收端根据 ID 重组
```

**核心**：一个 TCP 连接上可以**同时交错**传输多个请求/响应的数据帧，由 `Stream ID` 区分。彻底消除了 HTTP/1.1 的应用层队头阻塞。

### 3.3 头部压缩（HPACK）

**问题**：HTTP/1.1 头部是纯文本，重复传输大量冗余信息（Cookie、User-Agent 等）。

**HPACK 组成**：
1. **静态表**：预定义的常用头部（如 `:method: GET`, `:scheme: https`, `content-length` 等，共 61 项）
2. **动态表**：连接期间动态更新的头部
3. **Huffman 编码**：对头部值进行熵编码

```
例如 :method: GET 在静态表索引 2 → 只需传一个字节 0x82
以前 HTTP/1.1 中 "GET / HTTP/1.1\r\nHost: example.com\r\n" 几十个字节
HTTP/2 中可能只需几个字节表示索引
```

**压缩效果**：头部体积减少 **85%~90%**，尤其对大量小请求（如 API 调用）效果显著。

### 3.4 服务端推送（Server Push）

服务器在客户端请求之前主动推送资源。

```
客户端请求 index.html
服务器响应 index.html 的同时，主动推送 style.css 和 app.js

流程：
  1. 客户端发送 Stream1: GET index.html
  2. 服务器发送 Stream1: HEADERS (响应 index.html)
  3. 服务器发送 Stream2: PUSH_PROMISE (承诺将要推送 style.css)
  4. 服务器发送 Stream3: PUSH_PROMISE (承诺将要推送 app.js)
  5. 客户端收到 PUSH_PROMISE，如果已有缓存，发 RST_STREAM 拒绝
  6. 服务器发送 Stream2: DATA (style.css)
  7. 服务器发送 Stream3: DATA (app.js)
```

**问题**：服务器难以准确知道客户端缓存状态 → 可能导致推送已缓存的资源浪费带宽 → Chrome 已计划移除 Server Push 支持，转向 103 Early Hints。

### 3.5 HTTP/2 的队头阻塞残留

**这是 HTTP/2 最大的痛点**：

```
HTTP/2 解决了应用层的队头阻塞（多个流交错传输）
但 TCP 层的队头阻塞仍在：
  TCP 保证有序传输——一个 TCP 段丢失，后续所有段都要等待重传

    流1: [数据帧1] [数据帧2]
    流2: [数据帧A] [数据帧B]
    流3: [数据帧X] [数据帧Y]

    TCP 发送顺序（混合交错）：
    [帧1-1][帧2-A][帧3-X][帧1-2][帧2-B][帧3-Y]...

    如果帧2-A 丢失：
    TCP 会阻塞直到重传帧2-A 到达 → 流1、流2、流3 全部停顿
```

**对比**：
| 层次 | HTTP/1.1 | HTTP/2 |
|------|----------|--------|
| 应用层队头阻塞 | ❌ 有（管道化请求排队） | ✅ 无（多路复用） |
| 传输层队头阻塞 | ❌ 有（单连接内请求排队） | ❌ **仍有**（TCP 按序交付） |

---

## 4. HTTP/3 (QUIC)

### 4.1 基于 UDP，替代 TCP 传输层

```
协议栈对比：

HTTP/1.1 & HTTP/2:          HTTP/3:
┌────────────────┐          ┌────────────────┐
│    HTTP 应用层    │          │    HTTP 应用层    │
├────────────────┤          ├────────────────┤
│  TLS 安全层│          │ TLS 1.3 (内嵌)│
├────────────────┤          ├────────────────┤
│  TCP 传输层│          │   QUIC 传输层    │
├────────────────┤          ├────────────────┤
│  IP 网络层│          │     UDP 传输层      │
└────────────────┘          ├────────────────┤
                             │  IP 网络层│
                             └────────────────┘
```

QUIC（Quick UDP Internet Connections）在 UDP 之上实现了可靠的传输层：
- 内置 TLS 1.3 加密（连接建立时同时完成加密握手）
- 多路流（多路复用）
- 0-RTT 连接
- 连接迁移

### 4.2 彻底解决队头阻塞

```
HTTP/3 (QUIC)：
  UDP 不保证有序 → 每个流独立传输，互不影响

    流1: [数据帧1] ... 流1 正常接收 ✅
    流2: [数据帧A] ← 丢失，但只影响流2
    流3: [数据帧X] ... 流3 正常接收 ✅

    丢失的只有流2 需要等待重传，流1 和流3 继续工作
```

**关键**：QUIC 在单个 UDP 连接内实现了**多流多路复用**，每个流有独立的可靠传输和拥塞控制状态。一个流的丢包**不会**阻塞其他流。

### 4.3 0-RTT 快速连接

```
首次连接：
  Client:  Hello (Client Hello + QUIC 参数)
  Server:  Hello + Certificate + Config
  Client:  GET /index.html HTTP/3    ← 1-RTT 就可以发送数据

再次连接（缓存了 Server Config）：
  Client:  Hello + 缓存配置 + 已加密的 HTTP 请求
  Server:  Response                  ← 0-RTT！发送请求的同时就拿到响应

对比例：TCP + TLS 1.3 至少 1-RTT（若要 0-RTT 也需缓存）
```

### 4.4 连接迁移

**场景**：手机从 WiFi 切换到 5G，普通 TCP 连接会断开 → 需要重新 TCP 三次握手 + TLS 握手。

**QUIC 解决方案**：
- 使用 Connection ID（而非 IP+端口）标识连接
- 网络切换时，IP 改变但 Connection ID 不变
- 连接保持，继续传输数据

```
WiFi (192.168.1.10:54321) → 连接ID: AABBCC
                             ↓ 切换到 5G
5G (10.0.0.5:43876)      → 连接ID: AABBCC (不变)

服务器收到新 IP 的包但 Connection ID 匹配 → 连接仍然有效
```

---

## 5. HTTP 协议演进总结

| 特性 | HTTP/0.9 | HTTP/1.0 | HTTP/1.1 | HTTP/2 | HTTP/3 |
|------|----------|----------|----------|--------|--------|
| 年代 | 1991 | 1996 | 1997 (1999 修订) | 2015 | 2022 (RFC 9114) |
| 协议格式 | ASCII文本 | ASCII文本 | ASCII文本 | 二进制分帧 | 二进制分帧 |
| 传输层 | TCP | TCP | TCP | TCP | **QUIC (UDP)** |
| 请求方法 | GET | GET,POST,HEAD | +PUT,DELETE等 | 同上 | 同上 |
| 持久连接 | ❌ | ✅(非默认) | ✅(默认 Keep-Alive) | ✅(单连接) | ✅(单连接) |
| 管道化/并发 | ❌ | ❌ | 管道化（有HOL） | 多路复用（无应用层HOL） | 多路复用（无HOL） |
| 头部压缩 | n/a | ❌ | ❌ | HPACK (85-90%) | QPACK |
| 服务器推送 | ❌ | ❌ | ❌ | ✅ | ✅ |
| 连接迁移 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 传输级HOL | ❌ | ❌ | ❌ | ❌ | ✅(已解决) |
| 安全性 | 明文 | 明文 | 明文/HTTPS | 通常HTTPS | 强制加密 |

---

## 6. Python 模拟代码

见 `memory/learning/code/dns_http_evolution.py`

- DNS 递归解析链模拟：根服务器 → TLD → 权威 → 返回 IP
- HTTP/1.1 vs HTTP/2 多路复用传输对比
- HTTP/2 队头阻塞（TCP 丢包阻塞所有流）
- HTTP/3 无队头阻塞（UDP 丢包只影响一个流）

---

## 关键概念复习

### DNS
- **任播（Anycast）**：13 个逻辑根通过 Anycast 部署到全球数百台服务器
- **迭代 vs 递归**：问"你知道在哪吗" vs "帮我查一下"
- **DNS 劫持**：中间人篡改 DNS 响应 → DNSSEC 的 RRSIG 签名可检测
- **反向 DNS**：`PTR` 记录，IP → 域名，用于邮件反垃圾（反向验证）

### 队头阻塞（三层次）
1. **HTTP/1.1 管道化 HOL**：响应必须按序返回（应用层）
2. **HTTP/2 多路复用 HOL**：虽然应用层解决了，但 TCP 丢包阻塞所有流（传输层）
3. **HTTP/3 QUIC 彻底解决**：UDP + 多流独立传输，丢包只影响单个流

### HTTP/2 帧结构
```
+-----------------------------------------------+ 
| Length (24 bits)         | Type (8) | Flags (8) |
+---------------+---------------+---------------+
|R| Stream Identifier (31 bits)                  |
+-----------------------------------------------+
| Frame Payload (Length bytes) ...               |
+-----------------------------------------------+
```

### 头部压缩演进
- HTTP/1.1：纯文本
- HTTP/2：HPACK（静态表 + 动态表 + Huffman）
- HTTP/3：QPACK（类似 HPACK，但适应流乱序——编码器和解码器状态需要更复杂的设计）

### QUIC 特性
- 基于 UDP
- 内置 TLS 1.3
- 0-RTT 握手
- 多流无头阻塞
- Connection ID 实现连接迁移
- 流级别的流量控制
