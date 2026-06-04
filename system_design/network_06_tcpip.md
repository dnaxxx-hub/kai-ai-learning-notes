# 计算机网络 #6：TCP/IP 协议栈深度剖析

> 四层模型到各协议深度，含首部格式、拥塞控制、优化实战

---

## 一、TCP/IP 协议栈一览

```
应用层     HTTP/1.1 HTTP/2 HTTP/3(QUIC) DNS TLS/SSL DHCP FTP SMTP
传输层     TCP · UDP · SCTP · DCCP (端到端通信、可靠、流控、多路复用)
网络层     IP(IPv4/IPv6) · ICMP · ARP (寻址、路由、分片)
链路层     Ethernet · WiFi(802.11) · PPP (帧封装、MAC)
```

**数据封装**：应用→传输(TCP头)→网络(IP头)→链路(Eth头+CRC)，各层剥离自己头

**SAP映射**：传输→网络用Protocol(TCP=6,UDP=17)；应用→传输用端口；网络→链路用EtherType(IPv4=0x0800,ARP=0x0806)

---

## 二、IP 协议深度

### IPv4 首部 (20~60B)

| 字段 | 大小 | 说明 |
|------|------|------|
| Version | 4bit | 4 |
| IHL | 4bit | 首部长度×4, min=5(20B) |
| DSCP/ECN | 8bit | 差分服务+显式拥塞通知 |
| Total Length | 16bit | 总长, max=65535 |
| Identification | 16bit | 分片标识 |
| Flags | 3bit | DF(不分片), MF(更多片) |
| Fragment Offset | 13bit | 偏移×8 |
| TTL | 8bit | 每跳减1, 超时丢弃 |
| Protocol | 8bit | 上层协议(TCP=6, UDP=17) |
| Header Checksum | 16bit | 仅首部校验 |
| Source/Dest | 32bit×2 | IP地址 |

### IP分片示例（MTU=1500, 数据4000B）
- 分片1: ID=12345, Len=1500, MF=1, Offset=0 (1480B数据)
- 分片2: ID=12345, Len=1500, MF=1, Offset=185 (1480B数据)
- 分片3: ID=12345, Len=1060, MF=0, Offset=370 (1040B数据)

**问题**：一片丢失→整包丢弃；IPv6完全取消中间分片，由发送方做Path MTU Discovery

### IPv6 vs IPv4

| 特性 | IPv4 | IPv6 |
|------|------|------|
| 地址 | 32bit | 128bit |
| 首部 | 20~60B | 40B固定 |
| Checksum | 有 | 无 |
| 分片 | 路由器可做 | 仅发送方 |
| Options | 首部内可变 | 扩展首部链(Next Header) |
| 广播 | 有 | 无(多播替代) |

IPv6优势：固定首部HW转发快；无checksum省一跳；扩展首部链灵活

---

## 三、TCP 协议深度（核心）

### TCP 首部 (20~60B)

| 字段 | 大小 | 说明 |
|------|------|------|
| Source/Dest Port | 16bit×2 | 端口 |
| Sequence Number | 32bit | 本段首个字节序号 |
| Ack Number | 32bit | 期望的下一个字节 |
| Data Offset | 4bit | 首部长×4 |
| Flags | 9bit | SYN/ACK/FIN/RST/PSH/URG/ECE/CWR/NS |
| Window Size | 16bit | 接收窗口(×缩放因子) |
| Checksum | 16bit | 校验伪首部+TCP+数据 |
| Urgent Pointer | 16bit | URG标志时有效 |

**关键Options**：MSS(最大段大小)、Window Scale(缩放因子0~14)、SACK(选择性确认)、Timestamp(RTTM+PAWS)

### 三次握手
```
Client                        Server
  │──── SYN(seq=x) ──────────>│  SYN_SENT → SYN_RCVD
  │<── SYN-ACK(seq=y,ack=x+1)│
  │──── ACK(ack=y+1) ───────>│  ESTABLISHED
```

**SYN Flood**：伪造源IP发SYN填满半连接队列 → SYN Cookie防御（连接信息编码到seq中）

### 四次挥手
```
主动方                  被动方
FIN_WAIT_1 ──FIN──>    CLOSE_WAIT
FIN_WAIT_2 <──ACK──    (半关闭)
TIME_WAIT  <──FIN──    LAST_ACK
2MSL后CLOSE ──ACK──>   CLOSED
```

**TIME_WAIT必要性**：①确保最后ACK到达 ②防止旧连接数据干扰。2MSL≈4分钟。
优化：SO_REUSEADDR, tcp_tw_reuse（客户端安全）

### 可靠传输

**RTO计算**（RFC 6298）：
- SRTT = 7/8×SRTT + 1/8×RTT
- RTTVAR = 3/4×RTTVAR + 1/4×|SRTT - RTT|
- RTO = SRTT + 4×RTTVAR（下限1秒）
- 超时退避：RTO翻倍直到收到ACK

**快速重传**：收到3个dup ACK → 不等超时立即重传

**SACK**：接收方告知精确丢失信息，只重传丢失段，避免Go-Back-N浪费

### 流量控制

滑动窗口：发送方视角「已确认|已发送未确认|可发送|不可发送」
实际发送窗口 = min(cwnd, rwnd)

窗口缩放因子：Window Size只有16bit(max=65535)，缩放因子S(0~14)使实际窗口可达1GB

### 拥塞控制

| 概念 | cwnd(拥塞窗口) | rwnd(接收窗口) |
|------|-----------------|----------------|
| 控制方 | 发送方 | 接收方通告 |
| 目的 | 避免网络过载 | 避免接收方过载 |
| 依据 | 丢包/延迟 | 接收缓冲区 |

**慢启动**：cwnd初始=10MSS，每ACK+1MSS（每RTT翻倍），直到ssthresh

**拥塞避免**：cwnd>=ssthresh后，每RTT+1MSS（线性增长）

**快速恢复(NewReno)**：3 dup ACK → ssthresh=飞行中/2, cwnd=ssthresh+3

**CUBIC**（Linux默认）：三次函数 cwnd=C(t-K)³+Wmax
- 距离Wmax远→快速增长，接近→缓慢，超过→再快
- RTT公平性好

### CUBIC vs BBR

| 维度 | CUBIC | BBR |
|------|-------|-----|
| 驱动信号 | 丢包 | 带宽+RTT建模 |
| 丢包响应 | cwnd×0.3 | 不把丢包当拥塞信号 |
| 适用 | 有线网络 | 高延迟/高丢包/无线 |
| 阈值 | 需要缓冲区 | BtlBW×RTprop |
| Linux | 默认 | 4.9+可选 |

BBR核心：测量BtlBW和RTprop，发送速率=BtlBW×BDP，pacing控制

---

## 四、TCP 优化实战

### 应用层参数
- **TCP_NODELAY**：禁用Nagle，交互/游戏必须开
- **TCP_CORK**：攒够MSS再发，大文件传输用
- **SO_KEEPALIVE**：默认2h，建议调短

### 内核调优
```
net.core.rmem_max = 16777216    # 16MB
net.ipv4.tcp_rmem = 4096 131072 16777216
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_congestion_control = bbr
net.core.default_qdisc = fq
```

**TCP Fast Open**：SYN携带TFO Cookie和数据，后续连接0-RTT数据发送

---

## 五、UDP vs TCP 选型

| 维度 | TCP | UDP |
|------|-----|-----|
| 首部 | 20~60B | 8B |
| 可靠 | 可靠有序 | 不可靠无序 |
| 连接 | 面向连接 | 无连接 |
| 拥控 | 有 | 无(QUIC在UDP上实现) |

UDP场景：实时音视频(WebRTC)、在线游戏、DNS、IoT

### QUIC (HTTP/3)

**核心特性**：
- 基于UDP，用户空间可靠传输（绕过内核TCP栈）
- 0-RTT握手（首次1-RTT，后续0-RTT）
- 多路复用无HoL阻塞（一个stream丢包不影响其他stream）
- 连接迁移（IP/端口变化保持连接）
- 内置TLS 1.3加密
- 拥塞控制可定制

```
HTTP/2 over TCP: Stream1丢包 → 全部等重传 (TCP HoL)
HTTP/3 over QUIC: Stream1丢包 → 只影响Stream1
```

---

## 六、DNS 与 HTTP 演进

### DNS 解析
客户端→本地DNS(递归) → 根域→.com NS→example.com NS→A记录→返回IP
CDN负载均衡：GeoDNS根据源IP返回最近节点；Anycast多节点共享IP

### HTTP 版本对比

| 版本 | 核心 | 延迟 | 复用 |
|------|------|------|------|
| 1.1 | 持久连接 | 中等(HOL) | 无 |
| 2 | 二进制分帧+HPACK+多路复用 | 低(TCP HoL) | 流级别 |
| 3 | QUIC+0-RTT+无HOL | 最低 | 流+连接 |

### TLS 1.3 握手 (1-RTT)
ClientHello(密码套件+KeyShare) ↔ ServerHello+KeyShare+证书+Finished → 加密传输

---

## 总结

| 层 | 核心理念 | 关键权衡 |
|------|----------|----------|
| 链路层 | 物理寻址 | 冲突检测 vs 避免 |
| 网络层 | 尽力而为 | 分片 vs MTUD；IPv4灵活 vs IPv6简洁 |
| 传输层 | 端到端 | TCP可靠高开销 vs UDP不可靠低延迟 |
| 应用层 | 语义丰富 | HTTP/1.1简单 vs HTTP/3复杂高效 |

> "End-to-end principle: 将功能推至通信的端点，保持网络核心简单。"
