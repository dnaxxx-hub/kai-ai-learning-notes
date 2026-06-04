# 第8课：生产部署与工具

> 参考各部署工具官方文档

---

## 8.1 浏览器QUIC支持状态

### 主流浏览器支持

| 浏览器 | 支持版本 | 启用方式 | 状态 |
|--------|----------|----------|------|
| Google Chrome | 91+ (2021) | 默认启用 | ✅ 全量 |
| Microsoft Edge | 91+ (2021) | 默认启用 (Chromium 内核) | ✅ 全量 |
| Mozilla Firefox | 113+ (2023) | 默认启用 (早期需 flag) | ✅ 全量 |
| Safari | 16+ (2022) | macOS/iOS 默认启用 | ✅ 全量 |
| Opera | 70+ | Chromium 内核，默认启用 | ✅ 全量 |

### 检查 QUIC 是否启用

在 Chrome/Edge 中访问：`chrome://flags/#enable-quic`

```
在 chrome://net-internals/#quic 可以查看：
- 活跃的 QUIC 连接列表
- 每个连接的详细信息（RTT、丢包率、拥塞算法等）
- 会话信息（握手时间、0-RTT 命中率）

状态示例：
  QUIC Enabled: true
  Connections:
    [142.250.80.4]:443 (www.google.com)
      Protocol: QUICv1
      Version: 0x00000001
      ALPN: h3
      State: ESTABLISHED
      RTT: 15ms
      CWND: 15360 bytes
```

### 浏览器的 QUIC 回退逻辑

```
浏览器优先级：
1. 优先尝试 h3 (QUIC)
2. 如果 UDP 被阻塞 → 回退到 h2 (HTTP/2 over TLS)
3. 如果 TLS 失败 → 回退到 h1.1 (HTTP/1.1)

检测方式：
- Alt-Svc 响应头
- DNS HTTPS 记录
- 之前的成功连接记录

回退阈值：
- 连接尝试超时: 约 300ms ~ 2s（各浏览器不同）
- 连续失败次数: 通常是 3 次后降级
```

---

## 8.2 服务端部署

### Caddy（最易上手）

Caddy 从 v2.6+ 默认启用 QUIC/HTTP/3：

```caddyfile
# Caddyfile — 最小配置
# Caddy 会自动启用 HTTP/3 (h3)

example.com {
    # Caddy 自动：
    # 1. 申请 Let's Encrypt 证书
    # 2. 配置 TLS 1.3
    # 3. 启用 HTTP/3 over QUIC
    # 4. 发送 Alt-Svc 头
    
    root * /var/www/html
    file_server
}
```

**验证 QUIC 是否生效：**

```bash
# 1. 检查 Alt-Svc 头（QUIC 发现机制）
curl -I --http2 https://example.com | grep -i alt-svc
# 输出: alt-svc: h3=":443"; ma=2592000

# 2. 使用 curl 测试 HTTP/3（需要支持 h3 的 curl）
curl --http3 -I https://example.com

# 3. Caddy 访问日志中查看协议
curl https://example.com
# Caddy 日志: "Request: /, proto: HTTP/3.0"
```

### Nginx + QUIC

Nginx 从 1.25.x 开始内置 QUIC/HTTP/3 支持（使用 Cloudflare 的 quiche 或 Nginx 自己的实现）：

```nginx
# nginx.conf — QUIC + HTTP/3 配置

server {
    # 同时监听 TCP（HTTP/1.1 + HTTP/2）和 QUIC（HTTP/3）
    listen 443 ssl;          # HTTP/1.1 + HTTP/2 (TCP)
    listen 443 quic;         # HTTP/3 (QUIC over UDP)
    
    # 或者使用 reuseport (推荐，多核性能更好)
    # listen 443 quic reuseport;
    
    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    # 必须启用 HTTP/2（QUIC 回退支持）
    http2 on;
    
    # 启用 HTTP/3
    http3 on;
    
    # 配置 ALPN（应用层协议协商）
    ssl_protocols TLSv1.3;
    ssl_early_data on;  # 启用 0-RTT
    
    # Alt-Svc 通知客户端支持 HTTP/3
    add_header Alt-Svc 'h3=":443"; ma=86400';
    
    location / {
        root /var/www/html;
    }
}
```

**编译 Nginx 支持 QUIC 的注意事项：**

```bash
# 从源码编译（Nginx 1.25+ 默认包含 QUIC 支持）
# 或使用当前主流 Linux 发行版已 build-in 的包：

# Ubuntu 22.04+ / Debian 12+
apt install nginx-extras

# 添加 QUIC 模块到已有的 Nginx：
./configure \
    --with-http_ssl_module \
    --with-http_v3_module \
    --with-http_v2_module
```

### Cloudflare

Cloudflare 是全球最大的 QUIC 部署者之一，自动为所有用户启用 QUIC：

```
在 Cloudflare Dashboard 中：
- Speed → Optimization → HTTP/3 (with QUIC)
- 默认开启："
- 自动回退：如果 QUIC 连接失败，自动降级到 HTTP/2
```

### 各方案对比

| 方案 | 配置难度 | QUIC 版本 | HTTP/3 | 性能 |
|------|---------|-----------|--------|------|
| Caddy | ⭐ 极简 | v1 | ✅ | ⭐⭐⭐⭐ |
| Nginx (1.25+) | ⭐⭐ | v1 + v2 | ✅ | ⭐⭐⭐⭐⭐ |
| Cloudflare | 无需配置 | v1 | ✅ | ⭐⭐⭐⭐⭐ |
| LiteSpeed | ⭐⭐ | v1 + v2 | ✅ | ⭐⭐⭐⭐⭐ |
| HAProxy (3.0+) | ⭐⭐⭐ | v1 | ✅ | ⭐⭐⭐⭐ |
| Envoy | ⭐⭐⭐ | v1 | ✅ | ⭐⭐⭐⭐ |

---

## 8.3 调试工具

### qvis — QUIC 可视化工具

**qvis** 是 QUIC WG 推荐的可视化调试工具，可以将 QUIC 抓包文件转换为交互式可视化视图。

```bash
# 安装 qvis（基于 Python）
pip install qvis

# 使用方法
# 1. 使用 tshark 或 Wireshark 抓包
tshark -i eth0 -f "udp port 443" -w quic_capture.pcap

# 2. 用 qvis 将 pcap 转换为 qlog（JSON 格式的 QUIC 事件日志）
qvis convert quic_capture.pcap

# 3. 启动 qvis web UI
qvis serve
# 浏览器访问 http://localhost:3000/

# 4. 加载 qlog 文件，可以看到：
#    - 时间线视图：包发送/接收时间轴
#    - 带宽图：拥塞窗口变化
#    - RTT 图：RTT 随时间变化
#    - 丢包分布
```

**qvis 的可视化面板：**

```
┌─────────────────────────────────────────────────────────────┐
│  qvis 可视化面板                                           │
├──────────────────┬──────────────────────────────────────────┤
│ Packets Timeline │   ●    ●  ●     ●     ●    ●    ●       │
│ (逐包时间线)     │     ●      ●  ●    ●  ●   ●             │
│                  │  ───── Time ─────────────────→            │
├──────────────────┼──────────────────────────────────────────┤
│ CWND / Bytes     │  ████████                                │
│ (拥塞窗口变化)   │  ████████████████                        │
│                  │  ████████████████████████                 │
├──────────────────┼──────────────────────────────────────────┤
│ RTT / ms         │     ● ●   ●                             │
│ (延迟变化)       │  ● ●   ●   ●  ●  ●  ●                   │
├──────────────────┴──────────────────────────────────────────┤
│ Event Log (事件日志)                                        │
│ [0.000] Initial 发送                                        │
│ [0.047] Handshake完成                                       │
│ [0.052] 1-RTT 数据开始发送                                 │
│ [1.200] 丢包检测: PN=47 已确认PN=50但PN=47未确认           │
│ [1.201] 拥塞窗口: 15360 → 7680                             │
└─────────────────────────────────────────────────────────────┘
```

### quic-trace（Google 开发的 QUIC 调试工具）

```bash
# 安装 quic-trace（需要 Go 环境）
go install github.com/google/quic-trace/...

# 使用 Chromium 的 QUIC 抓包
# 在 Chrome 中设置环境变量：
export QUIC_TRACE_DIR=/tmp/quic_traces

# 启动浏览器，访问页面
# 退出后查看轨迹文件
cd /tmp/quic_traces
# 每个 QUIC 连接生成一个 .qtr 文件

# 使用 quic-trace 查看
quic-trace --port=3000 /tmp/quic_traces/*.qtr
# 浏览器访问 http://localhost:3000/
```

### 其他实用工具

```bash
# 1. curl 测试 HTTP/3
# 需要编译支持 quiche 或 ngtcp2 的 curl
curl --http3 https://www.example.com/
curl --http3 -I https://www.google.com/

# 如果 curl 不支持 --http3，可以使用：
curl --alt-svc altsvc.txt https://www.example.com/
# 或检查 Alt-Svc 头：
curl -sI https://www.google.com/ | grep -i alt-svc

# 2. ngtcp2 自带的 client 工具
# 编译 ngtcp2 后：
nghttp3 --h3 -v https://www.example.com/

# 3. qlog 格式查看
# QUIC 连接事件日志（结构化 JSON）
cat connection.qlog | jq '.'

# 4. 端口扫描 QUIC 支持
# 使用 nmap 扫描：
nmap -sU -p 443 --script quic-support example.com

# 5. 在线测试
# https://http3check.net/ — 检查域名是否支持 HTTP/3
# https://quic.xyz/ — QUIC 连接测试
```

### Wireshark + QUIC 高级分析

```bash
# Wireshark QUIC 分析技巧

# 1. 解密 QUIC 流量（需要 SSLKEYLOGFILE）
# 设置 Chrome/Edge 的 SSLKEYLOGFILE 环境变量：
export SSLKEYLOGFILE=/tmp/ssl_keys.log
# Wireshark: Edit → Preferences → Protocols → TLS → 
# (Pre)-Master-Secret log filename → 选择 /tmp/ssl_keys.log

# 2. 展示 QUIC 统计
# Statistics → QUIC → Connection Overview
# Statistics → QUIC → Resets

# 3. Wireshark 显示过滤器
quic                        # 显示所有 QUIC 包
quic.long_packet_type == 0  # 初始包
quic.long_packet_type == 2  # 握手包
quic.frame_type == 0x16     # STREAM 帧
quic.frame_type == 0x06     # CRYPTO 帧

# 4. 合并多个 UDP 包（连接合并分析）
# 在同一 UDP 包中可能包含 Initial + Handshake
# Wireshark 会显示为多个 QUIC 包
```

---

## 8.4 性能调优参数

### 服务端调优

#### Caddy 调优

```caddyfile
# Caddyfile — 性能调优
{
    # 全局设置
    servers {
        # UDP 读缓冲区（越大越好，高并发场景）
        read_buffer 4M
        
        # 加速 QUIC 握手
        protocols h1 h2 h3
        
        # Maximum concurrent streams
        max_concurrent_streams 1000
    }
}

example.com {
    # 启用 0-RTT（加速重连）
    tls {
        # 必须！0-RTT 依赖于 session ticket
        session_tickets on
    }
    
    # 开启 early_data（0-RTT 数据）
    @early-data {
        header early_data 1
    }
    
    root * /var/www/html
    file_server
}
```

#### Nginx 调优

```nginx
# nginx.conf — QUIC 性能调优

# 全局 QUIC 设置
quic_retry on;           # 防放大攻击（但在高负载下可关闭）
quic_gso on;             # Generic Segmentation Offload（需要内核支持）

# SSL 优化
ssl_early_data on;       # 0-RTT
ssl_session_cache shared:SSL:10m;
ssl_session_tickets on;

# 拥塞控制调优
# QUIC 使用内核的拥塞控制状态，所以需要设置内核参数
# sysctl -w net.core.default_qdisc=fq
# sysctl -w net.ipv4.tcp_congestion_control=bbr

# 流控调优
http3_max_concurrent_streams 256;
http3_max_header_size 64k;

# 缓冲区调优
# UDP 缓冲区大小（影响 QUIC 吞吐）
# sysctl -w net.core.rmem_max=26214400
# sysctl -w net.core.wmem_max=26214400
```

#### 内核调优

```bash
# /etc/sysctl.conf — 内核级 QUIC 性能调优

# UDP 缓冲区（直接影响 QUIC 吞吐量）
net.core.rmem_default = 262144
net.core.rmem_max = 134217728      # 128MB (提升高延迟链路性能)
net.core.wmem_default = 262144
net.core.wmem_max = 134217728

# BBR 拥塞控制（推荐用于 QUIC）
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# GRO/GSO 优化（Generic Receive/Segmentation Offload）
# 减少 CPU 中断次数
net.core.gro_default = 1

# 应用：
# sysctl -p /etc/sysctl.conf
```

### 客户端调优

```python
"""
QUIC 客户端可配置参数（以 aioquic 为例）
"""

from aioquic.quic.configuration import QuicConfiguration

config = QuicConfiguration(
    alpn_protocols=["h3"],
    is_client=True,
    
    # ===== 性能调优参数 =====
    
    # 初始拥塞窗口（默认 10，对于高带宽链路可以增大）
    initial_congestion_window=20,           # 包的数量
    
    # 初始 RTT 估计（默认 333ms，如果知道延迟可以优化）
    initial_rtt=50.0,                       # 毫秒
    
    # 空闲超时（连接保持时间，默认 30s）
    idle_timeout=60.0,                      # 秒
    
    # 连接级别初始流控窗口（默认 1MB）
    max_data=5242880,                       # 5MB
    
    # 每个流初始流控窗口（默认 256KB）
    max_stream_data=1048576,                # 1MB
    
    # 最大并发流数
    max_streams_bidi=100,
    
    # 支持 0-RTT 快速重连
    session_ticket_callback=save_ticket,    # 保存会话票据
)

# 0-RTT 测量指标
# 如果 0-RTT 命中率 > 50%，说明配置良好
# 否则检查 session ticket 保存/加载是否正确
```

### 调优关键指标

| 指标 | 参考值 | 说明 |
|------|--------|------|
| 0-RTT 命中率 | > 50% | 会话缓存有效 |
| 初始 1-RTT 握手时间 | < 50ms | 较好的网络条件 |
| QUIC 成功率 | > 95% | 不与 TCP 差距过大 |
| 连接迁移成功率 | > 80% | 移动端体验关键 |
| UDP 丢包率 | < 1% | 超过时考虑 TCP 回退 |
| CWND 峰值 | 视带宽而定 | 高带宽链路应达到 BDP |

### 常见问题排查

```
Q: QUIC 总是回退到 HTTP/2
   → 检查防火墙是否放行 UDP 443
   → 检查是否是 NAT 设备重置 UDP 包
   → 尝试增大 initial RTT

Q: QUIC 性能比 TCP 差
   → 检查 UDP 缓冲区大小
   → 检查丢包率（QUIC 对丢包更敏感）
   → 调整拥塞控制算法

Q: 0-RTT 不生效
   → 检查 session ticket 保存是否正确
   → 检查服务器是否支持 early_data
   → 检查是否改了 IP（0-RTT 在 IP 变化时失效）

Q: QUIC 导致 CPU 使用率升高
   → 用户空间处理 vs 内核 offload
   → 考虑 GSO/GRO 启用
   → 检查 TLS 加密开销（AES-GCM vs ChaCha20-Poly1305）
```

---

## 一句话总结

QUIC/HTTP/3 的浏览器支持已全面覆盖，生产部署可通过 Caddy（最简）或 Nginx（最灵活）快速启用，调试工具 qvis 提供可视化分析，性能调优需关注 UDP 缓冲区大小、0-RTT 命中率和拥塞控制算法的选择。
