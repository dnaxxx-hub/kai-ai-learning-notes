# 计算机网络完整路线 — 汇总笔记

> 从零搭建的网络知识体系，覆盖 OSI→物理层→网络层→传输层→应用层→安全→实战

## 路线总览

```
┌─────────────────────────────────────────────────────┐
│                 计算机网络完整体系                      │
├──────────┬──────────┬──────────┬──────────┬──────────┤
│  基础    │  底层     │  核心     │  传输    │  应用+安全│
│          │          │          │          │          │
│  OSI模型 │  物理层   │  IP协议  │  TCP深度 │  DNS     │
│  TCP/IP  │  以太网   │  子网划分 │  三次握手│  HTTP演化 │
│  分层思想│  MAC/ARP │  OSPF/BGP│  流量控制│  HTTP/2  │
│          │  交换机   │  NAT     │  拥塞控制│  gRPC    │
│          │  VLAN     │  ICMP    │  QUIC   │  TLS 1.3 │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

## 课程清单

| # | 主题 | 文件 | 核心知识点 |
|---|------|------|-----------|
| 1 | 网络基础 | `network_01_network_basics.md` | OSI七层, TCP/IP四层, 封装/解封装, 对等通信 |
| 2 | 物理+链路层 | `network_02_physical_datalink.md` | 以太网帧, MAC地址, ARP, 交换机, VLAN, MTU |
| 3 | 网络层 | `network_03_network_layer.md` | IPv4/IPv6, 子网划分CIDR, OSPF/BGP, NAT, ICMP |
| 4 | 传输层(TCP/UDP) | `network_04_transport_layer_tcp_udp.md` | 三次握手, 四次挥手, 滑动窗口, 慢启动, 快速恢复 |
| 5 | DNS+HTTP | `network_05_dns_http.md` | DNS递归/迭代, HTTP/1.1, HTTP/2多路复用, HTTP/3 |
| 6 | HTTP/2 深度 | `network_06_http2_deep.md` | 二进制分帧, 10种帧类型, 流优先级, HPACK, 服务器推送 |
| 7 | gRPC | `network_07_grpc.md` | protobuf, 四种调用模式, 拦截器, vs REST对比 |
| 8 | QUIC | `network_08_quic.md` | 0-RTT, 无队头阻塞, 连接迁移, UDP传输层 |
| 9 | TLS | `network_09_tls.md` | TLS 1.3握手, 证书链, 加密套件, SNI, PFS |
| 10 | 网络实战 | `network_10_network_practice.md` | tcpdump抓包, iperf吞吐, 故障排查方法论 |

## 协议栈全景（数据从应用到网线）

```
用户输入 https://www.example.com
         │
    ┌────┴────┐
    │ 应用层  │  HTTP/2, gRPC, DNS
    ├─────────┤
    │ 安全层  │  TLS 1.3 (握手、加密、证书验证)
    ├─────────┤
    │ 传输层  │  TCP (可靠、有序) 或 QUIC (基于UDP)
    ├─────────┤
    │ 网络层  │  IP (路由、寻址、分片)
    ├─────────┤
    │ 链路层  │  以太网 (MAC、帧、VLAN)
    ├─────────┤
    │ 物理层  │  光纤/双绞线/无线
    └─────────┘
```

## 各层关键协议一览

| 层 | 核心协议/技术 | 关键概念 | 数据单元 |
|----|-------------|---------|----------|
| 应用层(7) | HTTP/1.1, HTTP/2, HTTP/3, DNS, gRPC | 域名, RESTful, RPC, 流式 | Data |
| 表示层(6) | TLS (握手、加密) | 证书链, AEAD, PFS, SNI | - |
| 传输层(4) | TCP, UDP, QUIC | 三次握手, 滑动窗口, 拥塞控制, 0-RTT | Segment |
| 网络层(3) | IP, ICMP, ARP, OSPF, BGP | 子网, CIDR, NAT, 路由表, TTL | Packet |
| 链路层(2) | 以太网, 802.11(WiFi) | MAC, 交换机, VLAN, ARP | Frame |
| 物理层(1) | 双绞线, 光纤, 无线 | 比特, 信号, 频段 | Bit |

## HTTP 协议演进路线

```
HTTP/1.0 (1996)
  └─ 短连接, 简单
     
HTTP/1.1 (1999)
  ├─ 持久连接(Keep-Alive)
  ├─ 管道化(部分解决)
  ├─ 虚拟主机(Host头)
  └─ ⚠️ 队头阻塞 + 头部冗余
     
HTTP/2 (2015)
  ├─ 二进制分帧 → 解析快
  ├─ 多路复用 → 一个连接处理所有请求
  ├─ HPACK → 头部压缩85%+
  ├─ 服务器推送(已废弃)
  └─ ⚠️ TCP层队头阻塞
     
HTTP/3 (2022)
  ├─ 基于QUIC(UDP) → 无队头阻塞
  ├─ 0-RTT 连接 → 超快建立
  ├─ 连接迁移 → 移动端无忧
  └─ 内置TLS 1.3 → 强制加密
```

## 核心公式速记

### 子网计算
```
网络地址 = IP & 子网掩码
可用主机数 = 2^(32-前缀) - 2
```

### TCP 拥塞控制
```
慢启动:   cwnd *= 2 (每RTT)
拥塞避免: cwnd += 1 (每RTT)
快速恢复: ssthresh = cwnd/2, cwnd = ssthresh + 3
```

### RTT (延迟)
```
网络RTT ≈ 处理延迟 + 排队延迟 + 传输延迟 + 传播延迟
公网RTT: 同城<10ms, 国内<50ms, 跨洋<200ms
```

## 故障排查黄金流程

```
1. 确认问题范围: 全站还是单站? 所有用户还是你?
2. 物理/链路层: ping 网关通吗? Link灯亮?
3. 网络层: ping 8.8.8.8? tracert在哪断?
4. 传输层: nc -zv 目标 端口 通吗?
5. 应用层: curl 返回什么?
6. 抓包确认: 用tcpdump/Wireshark看协议交互
```

## 推荐资源

- **书籍**: 《计算机网络: 自顶向下方法》 - 经典入门
- **书籍**: 《TCP/IP 详解 卷1》 - 深度参考
- **工具**: Wireshark (抓包), iperf3 (吞吐), mtr (路由), dig (DNS)
- **在线**: Cloudflare Learning Center, 各RFC文档
- **面试准备**: 重点刷三次握手、拥塞控制、HTTP/2→3演进、HTTPS握手
