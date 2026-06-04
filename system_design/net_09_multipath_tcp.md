# 计算机网络 #9：多路径 TCP（MPTCP）

## 为什么需要 MPTCP
- 移动设备有 WiFi + 蜂窝双连接
- 传统 TCP 只能用一个路径
- 切换时连接中断（TCP 5 元组绑定）
- MPTCP 在一条 TCP 连接中用多个 subflow

## MPTCP 架构
```
应用层：单一 TCP socket
MPTCP 层：
  ├── Subflow 1 (WiFi, 192.168.1.1:54321 → 203.0.113.1:80)
  ├── Subflow 2 (LTE, 10.0.0.1:54322 → 203.0.113.1:80)
  └── ...
网络层：普通 IP 包
```
- **Path Manager**：管理 subflow 创建/删除
- **Scheduler**：选择哪个 subflow 发数据
- **Congestion Control**：协调多路径拥塞

## 调度器类型
| 调度器 | 策略 | 适用场景 |
|--------|------|----------|
| minRTT | 选最小 RTT 的路径 | 主路径优先，备用 |
| redundant | 所有路径都发 | 高可靠，低延迟 |
| balanced | 按拥塞窗口比例分配 | 带宽聚合 |
| default | minRTT + backup | 通用 |

## 拥塞控制
- **LIA（Linked Increases Algorithm）**：MPTCP 初始算法，总吞吐接近单路径
- **OLIA（Opportunistic LIA）**：改进版，更好利用备路径
- **Balia**：平衡公平性和性能

## Linux 支持 (mptcp.org)
- Linux 5.6+ 内核内置 MPTCP
- `sysctl net.mptcp.enabled=1`
- ss 命令查看：`ss -tMi`
- iproute2：`ip mptcp endpoint add 10.0.0.1 dev wlan0 id 1`

## MPTCP vs MPQUIC
| 特性 | MPTCP | MPQUIC |
|------|-------|--------|
| 标准化 | RFC 8684 | IETF 草案 |
| 加密 | 可选 | 强制 |
| 部署 | 内核（难升级） | 用户态（易升级） |
| 移动场景 | 好 | 更好 |
