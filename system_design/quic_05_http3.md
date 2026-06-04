# 第5课：HTTP/3（基于QUIC）

> 参考 RFC 9114（HTTP/3）、RFC 9204（QPACK）

---

## 5.1 QPACK：HTTP/2 HPACK的QUIC适配版

### HPACK 的问题

HTTP/2 使用 HPACK 进行头部压缩。HPACK 依赖**有序传输**——使用**静态表**+**动态表**+**Huffman 编码**进行压缩。

HPACK 的**动态表**需要在两端保持同步：
```
HPACK 动态表同步：
发送方动态表                  接收方动态表
┌──────────────┐            ┌──────────────┐
│ Index 1: ... │  必须完全   │ Index 1: ... │
│ Index 2: ... │ ←同步→     │ Index 2: ... │
│ Index 3: ... │            │ Index 3: ... │
└──────────────┘            └──────────────┘

问题：如果 Stream A 和 Stream B 的 HEADERS 帧
     到达顺序不同 → 动态表状态不同步 → 解压失败！
```

在 TCP 中这不是问题（TCP 保证有序交付）。但在 QUIC 中，**不同的流到达顺序可能乱序**，HPACK 的有序依赖会直接崩溃。

### QPACK 的设计

QPACK 将**编码器指令**和**解码器指令**放在**独立的单向流**上传输，与数据流分离：

```
QUIC 连接
├── Stream 0 (CRYPTO, 控制)
├── Stream N (请求/响应数据)
├── Stream M (请求/响应数据)
├── Unidirectional Stream (发送方 → 接收方) —— 编码器流
│    └── 动态表插入/删除指令
└── Unidirectional Stream (接收方 → 发送方) —— 解码器流
     └── 动态表确认、容量更新
```

#### 编码器流（Encoder Stream）

单向流，包含以下指令：

```
指令类型：
0x00 - Set Dynamic Table Capacity   设置动态表容量
      格式: 0x00 + VLI(容量)
      
0x01 - Duplicate                    复制表项到最新
      格式: 0x01 + VLI(索引)
      
0x02 - Insert With Name Ref         用已存在的名插入
      格式: 0x02 + Static(比特) + VLI(索引) + VLI(值长度) + 值
      
0x03 - Insert Without Name Ref      用新名插入
      格式: 0x03 + VLI(名长度) + 名 + VLI(值长度) + 值
      
0x04 - Insert With Name Ref(Dynamic) 用动态表名插入
0x05 - Insert Without Name Ref(Dynamic)
```

#### 解码器流（Decoder Stream）

单向流，包含确认和反馈：

```
指令类型：
0x06 - Header Ack                   确认 HEADERS 已处理
      格式: 0x06 + VLI(Stream ID)
      
0x07 - Stream Cancellation          流取消通知
      格式: 0x07 + VLI(Stream ID)
      
0x08 - Insert Count Increment       插入计数增量
      格式: 0x08 + VLI(增量值)
```

### QPACK 的字段编解码

```
参考索引（Reference Indexed）：
  - 标志位: '1'
  - 结构: S(1) + Index(6) + ...
  - S=0: 静态表, S=1: 动态表
  
字面量（Literal）：
  - 标志位: '0'
  - 结构: 0 + Name-Length + Name + Value-Length + Value
  - 可选引用: 用已有名引用减少冗余
```

### 静态表（与 HPACK 相同）

QPACK 的静态表与 HPACK 完全一致（前 61 项），常见的头部已预定义：

| Index | Name | Value |
|-------|------|-------|
| 0 | :authority | — |
| 1 | :path | / |
| 2 | :method | GET |
| 3 | :method | POST |
| ... | ... | ... |
| 16 | :scheme | https |
| ... | ... | ... |

### QPACK vs HPACK 对比

| 特性 | HPACK | QPACK |
|------|-------|-------|
| 动态表同步要求 | 有序 | 可乱序 |
| 控制流 | 与数据流共享 | 独立单向流 |
| 解码器反馈 | 隐式（有序保证） | 显式（Header Ack） |
| 复杂程度 | 较低 | 较高 |
| 流间独立 | 否 | 是 |
| 压缩效率 | 高 | 略低于 HPACK（额外开销） |

---

## 5.2 HTTP/3帧结构

### HTTP/3 帧的通用格式

```
HTTP/3 帧格式（在 QUIC STREAM 帧中传输）：
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Type (Variable Length Integer)                         ...
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Length (Variable Length Integer)                       ...
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Frame Payload                                          ...
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

所有 HTTP/3 帧都使用 **Variable Length Integer (VLI)** 编码：
- 前 2 位表示长度：`00`=1字节, `01`=2字节, `10`=4字节, `11`=8字节
- 大端编码

### HTTP/3 帧类型

| 类型值 | 帧名 | 用途 | 传输流 |
|--------|------|------|--------|
| 0x00 | DATA | HTTP 响应体 | 请求/响应双向流 |
| 0x01 | HEADERS | HTTP 头部（QPACK 编码） | 请求/响应双向流 |
| 0x02~0x03 | PRIORITY (废弃) | 流的优先级 (HTTP/3 弃用了, 用 Extensible Priorities) | 请求/响应双向流 |
| 0x04 | CANCEL_PUSH | 取消服务器推送 | 请求/响应双向流 |
| 0x05 | SETTINGS | 设置参数 | 控制流 |
| 0x07 | GOAWAY | 优雅关闭连接 | 控制流 |
| 0x0d | MAX_PUSH_ID | 限制推送 ID | 控制流 |

### 控制流（Control Streams）

HTTP/3 使用两对单向流传输控制数据：

```
客户端 → 服务器：
  Stream 2 (客户端控制流):
    ┌─ SETTINGS 帧 ──────────────────────┐
    │  设置: QPACK_BLOCKER_STREAMS = 100 │
    │  设置: MAX_FIELD_SECTION_SIZE = 64K│
    └────────────────────────────────────┘
    ┌─ GOAWAY 帧 ─────────────────────────┐
    │  Stream ID = 100 (不再接受新请求)   │
    └────────────────────────────────────┘
    
  Stream 6 (客户端 QPACK 编码器流): QPACK 编码器指令
  
  Stream 10 (客户端 QPACK 解码器流): QPACK 解码器指令

服务器 → 客户端：
  Stream 3 (服务器控制流): SETTINGS, GOAWAY, MAX_PUSH_ID
  
  Stream 7 (服务器 QPACK 编码器流)
  
  Stream 11 (服务器 QPACK 解码器流)
```

### 请求-响应过程

```
请求（客户端 → 服务器）：
  Stream N: 
    ┌─ HEADERS 帧 ───────────────────────┐
    │  :method = GET                     │
    │  :path = /index.html               │
    │  :scheme = https                   │
    │  :authority = example.com          │
    │  accept-encoding = gzip, br        │
    └────────────────────────────────────┘
    
响应（服务器 → 客户端）：
  Stream N (相同 Stream ID, 双向):
    ┌─ HEADERS 帧 ───────────────────────┐
    │  :status = 200                     │
    │  content-type = text/html          │
    │  content-encoding = br             │
    └────────────────────────────────────┘
    ┌─ DATA 帧 ──────────────────────────┐
    │  <压缩后的 HTML 内容>              │
    └────────────────────────────────────┘
    ┌─ DATA 帧 ──────────────────────────┐
    │  <更多内容...>                     │
    └────────────────────────────────────┘
    │  (流结束: Stream FIN)
```

---

## 5.3 服务器推送（Server Push）

### 基本流程

服务器预测客户端可能需要的资源（如 HTML 中引用的 CSS/JS），主动推送：

```
客户端                         服务器
  │                              │
  │──── Stream 4: GET /index.html→│
  │                              │
  │    (服务器检测到 index.html  │
  │     引用了 style.css)        │
  │                              │
  │←─ Stream 6 (单向): PUSH_PROMISE─│
  │   (Push ID=1, :path=/style.css)  │
  │                              │
  │←─ Stream 4: 200 OK + body───│
  │                              │
  │←─ Stream 8 (单向): HEADERS──│ ← 推送响应头
  │←─ Stream 8 (单向): DATA─────│ ← 推送响应体 (style.css)
```

### PUSH_PROMISE 帧

PUSH_PROMISE 帧在**原始请求流**上发送，告诉客户端"稍后会推送资源"：

```
PUSH_PROMISE 帧格式:
┌─────────────────────────────────────────────┐
│ Type = 0x05                                 │
│ Length = ...                                │
│ Push ID (VLI)                               │
│ Encoded Field Block (QPACK 编码的请求头)    │
└─────────────────────────────────────────────┘
```

### 客户端控制

```
MAX_PUSH_ID 帧：客户端告诉服务器最大允许的 Push ID
  ┌─ MAX_PUSH_ID=10 ─→ 服务器最多推送 10 个资源
  
CANCEL_PUSH 帧：客户端取消推送
  ┌─ CANCEL_PUSH, Push ID=3 → 取消 #3
  
也可以直接 RESET_STREAM: 拒绝已推送的流
```

### HTTP/3 推送 vs HTTP/2 推送

| 特性 | HTTP/2 推送 | HTTP/3 推送 |
|------|-------------|-------------|
| 推送流类型 | 双向流（被客户端引用） | 单向流 |
| PUSH_PROMISE | 在请求流的 HEADERS 前 | 同左 |
| 推送取消 | RST_STREAM 或拒绝 | CANCEL_PUSH 或 RESET_STREAM |
| 使用情况 | 很少用 | 很少用（同为浏览器的 cache 策略问题） |

---

## 5.4 与HTTP/2的迁移注意事项

### 兼容性注意事项

1. **流标识变化**：HTTP/2 的流 ID 是 31 位，HTTP/3 的 Stream ID 是 62 位
2. **协议升级**：HTTP/2 通过 HTTP/1.1 Upgrade 头或 ALPN (h2)，HTTP/3 通过 DNS SVCB/HTTPS RR 中的 ALPN (h3)
3. **端口**：HTTP/3 默认端口也是 **443**（UDP），通过 Alt-Svc 头发现

### SETTINGS 参数差异

| HTTP/2 SETTINGS | HTTP/3 等价 | 变化说明 |
|-----------------|-------------|----------|
| SETTINGS_HEADER_TABLE_SIZE | QPACK 编码器容量（SETTINGS_QPACK_MAX_TABLE_CAPACITY） | 名称变更 |
| SETTINGS_ENABLE_PUSH | 继续存在 | 功能相同 |
| SETTINGS_MAX_CONCURRENT_STREAMS | 由 QUIC 传输参数的 `initial_max_streams_*` 管理 | 移到 QUIC 层 |
| SETTINGS_INITIAL_WINDOW_SIZE | 由 QUIC 流控控制 | 不再需要 |
| SETTINGS_MAX_FRAME_SIZE | QUIC 最大数据包大小 | 不再需要 |
| SETTINGS_MAX_HEADER_LIST_SIZE | 继续存在为 SETTINGS_MAX_FIELD_SECTION_SIZE | 名称变更 |
| — (新增) | SETTINGS_QPACK_BLOCKER_STREAMS | QPACK 需要 |

### 头部字段映射

HTTP/2 使用的伪头字段在 HTTP/3 中保持一致：

```
请求伪头：
  :method      → 必需
  :scheme      → 必需
  :authority   → 可选（Host 头替代）
  :path        → 必需

响应伪头：
  :status      → 必需
```

### 优先级变化

HTTP/2 的依赖树优先级（带权重）已被**可扩展优先级（Extensible Priorities）** 替代（RFC 9218）：
- 使用 `Priority` 头字段：`Priority: u=1, i`
- `u` = urgency（紧迫度，0~7，0 最高）
- `i` = incremental（可否增量式响应）

### DNS 发现

HTTP/3 需要客户端知道服务器支持 h3。通过 DNS HTTPS RR（SVCB）记录：

```
example.com.  IN HTTPS  1 . alpn="h3,h2"
```

或者在 HTTP 响应头中：
```
Alt-Svc: h3=":443"; ma=86400
```

### 迁移路径建议

```
从 HTTP/2 迁移到 HTTP/3 的建议步骤：

1. 确认基础设施支持 UDP（防火墙、LB、CDN）
2. 服务端启用 QUIC 和 HTTP/3（Caddy/Nginx/Cloudflare 等）
3. 配置 Alt-Svc 头以通知客户端
4. 配置 DNS HTTPS 记录
5. 客户端库全面支持（浏览器已支持，后端库可选择）
6. 监控 UDP 丢包率和 QUIC 性能
7. 逐步增加 QUIC 连接比例
```

---

## 一句话总结

HTTP/3 通过 QPACK 头部压缩（用独立单向流解决乱序问题）、在 QUIC 流上传输 HTTP 帧，解决了 HTTP/2 在 TCP 上的队头阻塞问题，迁移时需注意 DNS 发现、Alt-Svc 声明和优先级模型的变更。
