# 计算机网络 #11：MPLS

## MPLS 核心概念
- 多协议标签交换：在 IP 包头前加标签头
- 标签交换比 IP 路由查找更快（一次查表）
- 但现代 ASIC 已经让 IP 路由足够快，MPLS 的价值转向 VPN/TE

## 基本架构
```
IP包 → 入站LER(压入标签) → LSR(标签交换) → ... → 出站LER(弹出标签)
```
- **LER**（Label Edge Router）：边缘标签路由器，压入/弹出标签
- **LSR**（Label Switch Router）：核心标签路由器，只交换标签
- **FEC**（Forwarding Equivalence Class）：相同转发处理的包集合
- **LFIB**（Label Forwarding Information Base）：标签转发表

## MPLS VPN
- RFC 4364：提供商 MPLS VPN
- 每个 VPN 有独立 VRF（虚拟路由转发）
- 标签栈：外层 = MPLS 隧道 / 内层 = VPN 标识
- 支持 IPv4、IPv6、L2 传输

## MPLS TE（流量工程）
- 显式路径带宽预留
- RSVP-TE 信令建立 LSP（标签交换路径）
- FRR（快速重路由）：50ms 故障切换

## 演进：SR-MPLS
- Segment Routing MPLS：去掉 RSVP 信令
- 源路由：入口列出中间节点列表
- 简化运维，去掉了 LDP/RSVP 协议

## 应用对比
| 场景 | 传统方案 | MPLS 方案 |
|------|----------|-----------|
| VPN | IPSec/GRE | MPLS L3VPN |
| 带宽保证 | 无 | MPLS TE |
| 快速切换 | 无 | MPLS FRR |
