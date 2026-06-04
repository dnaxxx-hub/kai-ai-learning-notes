# 计算机网络 #7：QUIC 协议深度

## 背景：HTTP/2 的队头阻塞
- HTTP/2 多路复用同一 TCP 连接
- TCP 丢包时，所有 stream 都阻塞（TCP 队头阻塞）
- 一个 HTTP 流丢包，其他流也得等重传
- QUIC 用 UDP 解决这个问题

## QUIC 核心设计（RFC 9000）

### 连接与流
- 连接 = 一个 UDP 5元组 + Connection ID
- ID 随机生成，不绑定 IP → 连接迁移（切换网络不断连）
- 流（Stream）= 独立字节序列，类似 HTTP/2 的 stream
- 流之间隔离：一个流丢包不影响其他流

### 0-RTT 握手
1. 首次连接：1-RTT 完成 TLS 1.3 握手
2. 后续连接：0-RTT 直接发数据（缓存会话凭据）
3. 比 TCP+TLS 的 2-3 RTT 快得多

### 流量控制
- 连接级 + 流级 双层流控
- 允许接收方控制每个流的窗口
- 窗口更新通过帧传递，不阻塞

### 拥塞控制
- 可插拔，默认类似 NewReno / Cubic
- 在应用层实现（不是内核），可以快速迭代
- Google BBR 算法常用于 QUIC

## 相比 TCP 的优势
| 特性 | TCP | QUIC |
|------|-----|------|
| 传输层 | 内核态 | 用户态 |
| 握手延迟 | 1-3 RTT | 0-1 RTT |
| 队头阻塞 | 有（所有流共享） | 无（流隔离） |
| 连接迁移 | 不支持（5元组绑定） | 支持（Connection ID） |
| 加密 | 可选（+TLS） | 强制（内建 TLS 1.3） |
| 更新方式 | 内核更新 | 程序更新 |

## HTTP/3 映射
- HTTP/3 = HTTP over QUIC
- RFC 9114
- 浏览器和 CDN 已在大量使用（Google/Cloudflare/Facebook）
