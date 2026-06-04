# 计算机网络纵深 — 6课汇总

| # | 课程 | 核心内容 |
|:-:|------|----------|
| 7 | **QUIC 协议** | 解决HTTP/2队头阻塞 → UDP+Connection ID+0-RTT+流隔离 → 连接迁移 → 拥塞控制 → HTTP/3映射 |
| 8 | **HTTP/3** | QPACK头部压缩 → 帧结构控制流/请求流 → 服务端推送弃用 → nginx/quiche/CDN迁移 → Alt-Svc回退 |
| 9 | **MPTCP** | 多路径架构(Subflow/Path Manager/Scheduler) → 调度器(minRTT/redundant) → 拥塞控制(OLIA/Balia) → Linux内核(mptcp.org) → 移动应用(5G+/WiFi+蜂窝) |
| 10 | **BGP** | AS路径 → 选路(Weight/LocalPref/AS Path/MED 7步) → iBGP/eBGP → COMMUNITY/MED属性 → RPKI/BGPsec → 前缀劫持 |
| 11 | **MPLS** | 标签交换(LER/LSR/LFIB) → MPLS VPN(VRF/双标签栈) → TE(RSVP-TE/LSP/FRR 50ms) → SR-MPLS去信令 |
| 12 | **DNS/任播** | EDNS/DNSSEC/DoH/DoT → 全球DNS架构(根/TLD/权威) → Anycast BGP路由 → CDN调度(DNS/GSLB/HTTP重定向) |
