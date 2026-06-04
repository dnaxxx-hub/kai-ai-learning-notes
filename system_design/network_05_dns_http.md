# DNS + HTTP — 从域名到应用层协议演进

## DNS（Domain Name System）

**作用**：将人类可读的域名(example.com) 转换为机器可读的 IP 地址。

### DNS 分层结构

```
根域名服务器 (.)        13组根服务器 (a.root-servers.net 等)
      │
顶级域 (TLD)           .com, .org, .net, .cn, .io ...
      │
二级域名               example.com, google.com
      │
子域名                 www.example.com, api.google.com
```

### 域名解析流程

```
递归查询 (Recursive) + 迭代查询 (Iterative):

1. 浏览器: "www.example.com 的IP是什么?"
   → 本地DNS缓存 (有则返回, 无则下一步)
   
2. 本地DNS解析器 (通常 ISP 或 8.8.8.8):
   → 向根服务器查询 "www.example.com"
   ─── 根服务器: "我不知道, 去问 .com TLD服务器"
   
3. → 向 .com TLD服务器查询
   ─── TLD服务器: "我不知道, 去问 example.com 的权威服务器 ns1.example.com"
   
4. → 向 authoritative DNS (ns1.example.com) 查询
   ─── 权威服务器: "www.example.com = 93.184.216.34"

5. 返回结果 → 本地缓存 → 浏览器发起HTTP请求
```

### DNS记录类型

| 类型 | 含义 | 示例 |
|------|------|------|
| A | IPv4地址 | `example.com. IN A 93.184.216.34` |
| AAAA | IPv6地址 | `example.com. IN AAAA 2606:2800:220::1` |
| CNAME | 别名(域名→域名) | `www.example.com. IN CNAME example.com.` |
| MX | 邮件服务器 | `example.com. IN MX 10 mail.example.com.` |
| NS | 权威DNS服务器 | `example.com. IN NS ns1.example.com.` |
| TXT | 文本信息(SPF验证等) | `example.com. IN TXT "v=spf1 include:_spf.google.com"` |
| SOA | 区域权威信息(起始授权) | 包含主NS, 管理员邮箱, 刷新间隔等 |

### DNS 使用工具

```bash
# 基本DNS查询
nslookup example.com
dig example.com

# 指定DNS服务器
dig @8.8.8.8 example.com

# 查询特定类型
dig example.com MX
dig example.com CNAME
dig example.com ANY

# 反向查询 (IP → 域名)
dig -x 93.184.216.34

# 查看DNS解析过程
dig +trace example.com

# 清空DNS缓存
ipconfig /flushdns           # Windows
sudo dscacheutil -flushcache # macOS
sudo systemd-resolve --flush-caches  # Linux (systemd-resolved)
```

### DNS 优化技术

- **DNS缓存**: 浏览器 → 操作系统 → 本地DNS服务器 → ISP DNS
- **TTL**: 缓存有效期，短TTL更新快但查询多
- **CDN DNS**: 根据用户地理位置返回最近的节点IP (GSLB)
- **DNS over HTTPS (DoH)**: 加密DNS查询, 防劫持

---

## HTTP 协议演进

### HTTP/1.0 (1996)
- 短连接: 每次请求建立新TCP连接
- 简陋的功能集
- 几乎已淘汰

### HTTP/1.1 (1999)

**核心改进**：
1. **持久连接** (Keep-Alive): 复用TCP连接
2. **管道化** (Pipelining): 请求无需等待响应即可发送下一个(但响应必须按序返回)
3. **分块传输编码** (Chunked Transfer): 动态生成内容
4. **Host头部** (必选): 同一IP上托管多个域名
5. **缓存控制**: Cache-Control, Etag, Last-Modified

```
HTTP Request 格式:
GET /index.html HTTP/1.1
Host: www.example.com
User-Agent: Mozilla/5.0
Accept: text/html
Connection: keep-alive

HTTP Response 格式:
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 1234
Cache-Control: max-age=3600
```

**HTTP/1.1 问题**：
- 队头阻塞: 一个请求慢 → 后面所有排队(即使是管道化也受限于FIFO响应)
- 头部冗余: 每次请求重复发送相同头部(cookie, user-agent等)
- 并发限制: 浏览器限制单个域名6-8个并发连接(通过域名分片解决)

### HTTP/2 (2015, RFC 7540)

**核心改进**：

1. **二进制分帧** (Binary Framing)
   - 文本 → 二进制, 解析更快, 更紧凑
   - 帧(Frame): HTTP/2最小通信单位(HEADERS帧, DATA帧等)
   - 流(Stream): 帧的序列, 每个请求一个流ID

2. **多路复用** (Multiplexing)
   - 在单一TCP连接上交错发送多个流
   - 一个流阻塞不影响其他流
   - **解决了HTTP/1.1的队头阻塞**

3. **头部压缩** (HPACK)
   - 静态表: 预定义的61个常见头部
   - 动态表: 双方维护上下文, 重复头部只传索引
   - 哈夫曼编码: 进一步压缩
   - 头部压缩比可达 85-90%

4. **服务器推送** (Server Push)
   - 服务器主动推送资源(如CSS, JS, 图片)
   - 客户端可以拒绝(RST_STREAM)
   - 实践中使用不多(浏览器缓存冲突)

5. **流优先级** (Stream Priority)
   - 客户端可设置流的依赖和权重
   - 服务器按优先级分配资源

```
二进制帧格式:
┌─────────────────────────────────────────────────────┐
│ Length (24bit)           │ Type (8bit) │ Flags(8bit)│
├─────────────────────────┴──────────────┴────────────┤
│ Reserved(1bit) │ Stream Identifier (31bit)          │
├──────────────────────────────────────────────────────┤
│ Frame Payload (变长)                                  │
└──────────────────────────────────────────────────────┘

帧类型: HEADERS, DATA, PRIORITY, SETTINGS, PUSH_PROMISE,
        GOAWAY, RST_STREAM, WINDOW_UPDATE, CONTINUATION
```

**HTTP/2 问题**：
- 底层仍是TCP → **TCP层队头阻塞**
- 一个TCP包丢失 → 整个连接所有流都等待

### HTTP/3 (2022, RFC 9114)

**核心改进**：将传输层从TCP替换为QUIC（基于UDP）

```
HTTP/1.1: HTTP over TCP
HTTP/2:   HTTP over TCP (二进制分帧)
HTTP/3:   HTTP over QUIC (基于UDP)
```

**关键优势**：
1. 0-RTT 连接建立（之前连接过的情况下）
2. 无队头阻塞: 一个流丢包不影响其他流
3. 连接迁移: 切换网络WiFi→蜂窝不断连
4. 内置TLS 1.3

详见第8课 QUIC 详解。

### 实操抓HTTP包

```bash
# 查看HTTP/1.1 vs HTTP/2
curl -v http://example.com           # 默认HTTP/1.1
curl --http2 https://nghttp2.org     # HTTP/2 (需要--http2)
curl --http3 -V https://www.google.com  # HTTP/3 (需要curl支持QUIC)

# 查看HTTP头部
curl -I https://example.com

# 抓包分析HTTP
tcpdump -i any port 80 -A           # HTTP明文数据
tcpdump -i any port 443             # HTTPS加密数据

# nghttp2 专用调试
echo -e "GET / HTTP/1.1\r\nHost: example.com\r\n\r\n" | nc example.com 80

# 查看服务器支持的HTTP版本
curl -v -s https://www.google.com/ 2>&1 | grep -i "http"
```
