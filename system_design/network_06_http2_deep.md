# HTTP/2 深度解析

## 背景：从文本到二进制的范式转换

HTTP/1.x 基于**文本协议**（一行一行解析文本头部），HTTP/2 基于**二进制分帧**（最小的通信单位是帧）。

这不仅是格式变化，而是整个通信模型的**根本性重构**。

## 1. 二进制分帧层 (Binary Framing Layer)

```
HTTP/1.1 原始请求:
GET /index.html HTTP/1.1
Host: www.example.com

HTTP/2 对应的帧:
[HEADERS帧, StreamID=1] 包含 :method=GET, :path=/index.html, :authority=www.example.com
[DATA帧, StreamID=1]    包含请求体(如有)
```

### 帧结构详解

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
┌───────────────────────────────────────────────────────────────┐
│         Length (24 bit)          │   Type (8 bit)  │ Flags    │
├──────────────────────────────────┴─────────────────┴──────────┤
│ R │          Stream Identifier (31 bit)                       │
├───────────────────────────────────────────────────────────────┤
│                   Frame Payload (变长)                         │
└───────────────────────────────────────────────────────────────┘
```

- **Length**: 帧负载长度(不包括9字节头部), 最大 2^14 = 16384 (默认)
- **Type**: 帧类型(见下表)
- **Flags**: 帧的附加标志(如 END_STREAM, END_HEADERS)
- **Stream Identifier**: 流ID(客户端发=奇数, 服务器发=偶数, 0为连接级帧)

### 10种帧类型

| 类型 | 代码 | 用途 |
|------|------|------|
| DATA | 0x0 | 传输HTTP消息体 |
| HEADERS | 0x1 | 打开新的流/发送头部 |
| PRIORITY | 0x2 | 设置流的优先级 |
| RST_STREAM | 0x3 | 终止单个流(非致命错误/拒绝服务器推送) |
| SETTINGS | 0x4 | 连接级参数协商 |
| PUSH_PROMISE | 0x5 | 服务器通知客户端将推送资源 |
| PING | 0x6 | 心跳检测/RTT测量 |
| GOAWAY | 0x7 | 优雅关闭连接 |
| WINDOW_UPDATE | 0x8 | 流量控制更新 |
| CONTINUATION | 0x9 | 继续传输头部块 |

## 2. 多路复用 (Multiplexing)

**核心**：一个TCP连接上同时交错传输多个独立流。

```
时间→
TCP连接:
┌───Stream 1 HEADERS───┐
├───Stream 3 HEADERS───┤
├───Stream 1 DATA──────┤
├───Stream 2 HEADERS───┤
├───Stream 3 DATA──────┤
├───Stream 1 DATA──────┤
└──────────────────────┘

流1、流2、流3的帧在TCP连接上交错发送
接收端按Stream ID重组
```

**与HTTP/1.1的对比**：
- HTTP/1.1 管道化: 请求可并发发, 但响应必须按序返回
- HTTP/2 多路复用: 响应可以乱序返回, 先完成先返回

## 3. 流优先级 (Stream Priority)

**为什么需要**？多路复用中, 浏览器需要告诉服务器哪些资源**更重要**。

```
流依赖树示例:

           根 (虚拟)
          /    \
         /      \
     流1(图片)  流3(HTML)
       /     
      /       
  流5(CSS)   流7(JS)
  
优先级计算:
- 每个流有: StreamID + 依赖(哪个流) + 权重(1-256)
- 默认权重 = 16
- 高权重子流分得更多带宽
```

**权重分配算法**：
```
总和 = 所有同级子流的权重之和
每个子流分得带宽比例 = 该子流权重 / 总和

例:
流3(HTML)权重=32, 流1(图片)权重=16
流3分得 32/(32+16)=66%, 流1分得 16/48=33%
```

## 4. HPACK 头部压缩

### 为什么需要压缩？
- HTTP/1.1 头部通常 600-800 字节
- 请求间重复内容多: Cookie(常>1KB), User-Agent, Host等
- 多路复用下, 头部开销被放大

### 三张表

**静态表** (预定义, 共61项):

| 索引 | 名称 | 值 |
|------|------|-----|
| 1 | :authority | - |
| 2 | :method | GET |
| 3 | :method | POST |
| 4 | :path | / |
| 5 | :path | /index.html |
| 6 | :scheme | http |
| 7 | :scheme | https |
| ... | ... | ... |
| 61 | www-authenticate | - |

**动态表** (连接双方动态构建):

```
初始为空, 后续请求逐渐填充:
索引62: cookie: session=abc123
索引63: user-agent: Mozilla/5.0 ...

规则: 之前出现过的大小256字节以下的头部, 缓存在动态表
下次发送只需传输索引号(通常1字节)
```

**哈夫曼编码**: 对静态表和动态表都匹配不上的内容, 使用预定义的哈夫曼表压缩。

### 压缩效果

```
原始: 600+ 字节 → 压缩后 ~100 字节 (压缩比 ~85%)
多请求平均: 每次请求仅需 ~20-30 字节

HPACK 极限场景: 请求 `GET / HTTP/2` 仅需 9 字节帧头+索引
```

## 5. 服务器推送 (Server Push)

**流程**：
```
客户端: GET /index.html
服务器: 
  1. 返回 HTML 内容 (在 HEADERS 和 DATA 帧中)
  2. 同时发送 PUSH_PROMISE 帧: "我将推送 /style.css, /app.js"
  3. 在单独的流上发送 /style.css 和 /app.js

客户端:
  - 如果缓存中已有, 发送 RST_STREAM 拒绝推送
  - 否则正常接收
```

**实际效果有限**的原因：
- 浏览器缓存的资源服务器不知道 → 可能推已经缓存的内容
- 需要额外的逻辑决定推什么
- HTTP/2 的推送无法被Service Worker拦截
- **HTTP/3 已移除服务器推送**

## 与HTTP/1.1性能对比

| 特性 | HTTP/1.1 | HTTP/2 |
|------|----------|--------|
| 格式 | 文本(简单) | 二进制(高效) |
| 多路复用 | 无(需域名分片) | 有 |
| 队头阻塞 | 应用层 | TCP层(比应用层好) |
| 头部压缩 | 无 | HPACK |
| 服务器推送 | 无 | 有(现已废弃) |
| 连接数 | 6-8个/域名 | 1个 |
| 协议协商 | - | ALPN(TLS扩展) |
| 流量控制 | TCP级别 | TCP + 流级别 |

### 实操验证

```bash
# 查看HTTP/2连接
curl --http2 -v https://nghttp2.org
# 输出中 "Using HTTP/2" 表示使用HTTP/2

# h2load 压力测试
h2load -n1000 -c10 https://nghttp2.org/

# Wireshark 过滤
tcp.stream eq 0 and http2

# 查看帧类型
nghttp -v https://nghttp2.org

# 检查服务器ALPN支持
openssl s_client -connect google.com:443 -alpn h2
```
