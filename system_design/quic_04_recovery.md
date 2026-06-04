# 第4课：QUIC恢复与拥塞控制

> 参考 RFC 9002（QUIC Loss Detection and Congestion Control）

---

## 4.1 不像TCP那样用序列号——使用包编号（Packet Number）空间

### TCP 的问题：一个序列号空间

TCP 的序列号（Sequence Number）同时承担两个角色：
1. **数据排序** — 告诉接收方字节顺序
2. **丢失检测** — 通过序列号间隙判断丢包

```
TCP:
SEQ=1 ─→│SEQ=2 ─→│SEQ=3 ─→│SEQ=4 ─→│SEQ=5 ─→│
         ↑ 丢失       ↑ 已到，但必须等 SEQ=3
```

问题是 TCP 无法区分"这是对原始包的 ACK"还是"这是对重传包的 ACK"（**重传歧义**）。

### QUIC 的三个独立包编号空间

QUIC 为不同阶段使用独立的包编号空间：

```
包编号空间 1: Initial
  PN=0 (Initial) ─→ PN=1 (Initial) ─→ PN=2 (Initial)

包编号空间 2: Handshake
  PN=0 (Handshake) ─→ PN=1 (Handshake)

包编号空间 3: 1-RTT (Application Data)
  PN=0 ─→ PN=1 ─→ PN=2 ─→ PN=3 ─→ PN=4...
```

每个空间独立计数，**互不干扰**。

---

## 4.2 显式单调包编号（解决TCP重传歧义）

### 核心设计

QUIC 的包编号是**严格单调递增**的，**重传不重用包编号**：

```
QUIC 发送:
原始:   PN=10 (STREAM "Hello")
重传:   PN=20 (STREAM "Hello")  ← 使用新的包编号！

TCP 发送:
原始:   SEQ=100 (数据 "Hello", 长度5)
重传:   SEQ=100 (数据 "Hello", 长度5)  ← 重用相同序列号！
```

### 重传歧义问题的解决

**TCP 的歧义**：
```
TCP 发送:
  发送 SEQ=100 ───→│ (丢失)
  发送 SEQ=100 ───→│ (重传)
  
收到 ACK=105:
  → 这是对原始传输的 ACK 还是对重传的 ACK？
  → 无法区分！RTT 测量不准确
  → 可能导致 spurious retransmission（虚假重传）
```

**QUIC 的明确性**：
```
QUIC 发送:
  发送 PN=10 ───→│ (丢失)
  发送 PN=20 ───→│ (重传)
  
  收到 PN=10 的 ACK:
  → 明确知道是对原始传输的确认
  → 可以精确计算 RTT
  → 不会产生歧义
```

### 包编号的编码

包编号不是全 62 位传输，而是使用**可变长度编码**（节省带宽）：

```
包编号值    | 编码长度 | 编码方式
1-63       | 1 字节   | 6-bit 包编号
64-16383   | 2 字节   | 14-bit 包编号
16384-4194303 | 4 字节 | 30-bit 包编号
>= 4194304 | 8 字节   | 62-bit 包编号
```

接收方通过包编号的**最高位前缀**来判断实际长度。例如收到 `0x50`（二进制 `01 010000`），高 2 位 `01` 表示 14-bit 编码，剩余 `010000` + 下一个字节组成实际值。

---

## 4.3 RTT测量、ACK处理

### RTT 测量

QUIC 使用三种 RTT 度量：

| 度量 | 公式 | 说明 |
|------|------|------|
| **smoothed_rtt** | 指数加权移动平均 | 长期平滑值，类似 TCP SRTT |
| **rttvar** | RTT 偏差 | 反映 RTT 波动程度 |
| **min_rtt** | 观测到的最小 RTT | 路径延迟的下界（用于 RACK 算法） |

计算过程（RFC 9002 §6）：
```
1. 当收到一个确认包 PN=x 的 ACK 时：
   latest_rtt = 当前时间 - PN=x 的发送时间
   
2. 首次 RTT 样：
   smoothed_rtt = latest_rtt
   rttvar = latest_rtt / 2
   min_rtt = latest_rtt

3. 后续更新（指数加权）：
   rttvar = (3/4) * rttvar + (1/4) * |smoothed_rtt - latest_rtt|
   smoothed_rtt = (7/8) * smoothed_rtt + (1/8) * latest_rtt
   min_rtt = min(min_rtt, latest_rtt)
```

### ACK 处理（与 TCP 的不同）

TCP 使用累积 ACK（cumulative ACK）：
```
收到 ACK=105: 确认已收到 105 之前的所有数据
```

QUIC ACK 帧支持**非连续确认**（类似 SACK）：
```
ACK {
  Largest Acknowledged: 100    ← 最大已确认包编号
  ACK Delay: 5ms              ← 接收方延迟
  ACK Range Count: 2          ← 非连续区间数量
  First ACK Range: 20         ← [81, 100] 已确认
  ───────── 间隙 ──────────
  Gap: 10                     ← [70, 80] 未确认（丢失？延迟？）
  ACK Range: 30              ← [40, 69] 已确认
  ───────── 间隙 ──────────
  Gap: 5                      ← [34, 39] 未确认
  ACK Range: 33              ← [1, 33] 已确认
}
```

**ACK 与丢包检测的逻辑**：
```
规则 1: 包编号 < Largest Acknowledged 且不在 ACK Range 中 = 丢失
规则 2: 某包已发送足够久（基于超时）且未确认 = 疑似丢失
```

### 丢包检测阈值（RFC 9002）

```
丢包检测时间 = max(1.125 * smoothed_rtt, kGranularity)
              + max(4 * rttvar, kGranularity)
              + ack_delay

其中：kGranularity = 1ms（时钟粒度）
```

更精确的检测：**包阈值法（Packet Threshold）**
```
如果 PN=50 已发送但未确认，而 PN=60 已确认：
  → 检测到 PN=50 丢失（阈值通常为 3 个包差距）
```

### 伪丢包（Spurious Loss）避免

QUIC 使用**ACK 频率控制**（类似 TCP 的 delayed ACK）：
- 每个收到包不一定立即回复 ACK
- 批量确认降低带宽消耗
- 但每收到 2 个包至少发 1 个 ACK（或 25ms 内）

---

## 4.4 拥塞控制适配

QUIC 的拥塞控制框架与传输解耦，允许**插入不同的拥塞控制算法**。

### 拥塞控制架构

```
QUIC 传输层
     │
     ├── 丢包检测器 (Loss Detection)
     │    └── 检测到丢包 → 通知拥塞控制器
     │
     └── 拥塞控制器 (Congestion Controller)
          │
          ├── 初始窗口 (默认 10 个包 ≈ 12KB 或更大)
          ├── 慢启动 (SS)
          ├── 拥塞避免 (CA)
          └── 恢复 (Recovery)
               └── 重置拥塞窗口
```

### 内置算法：NewReno（RFC 9002 默认）

QUIC 标准要求至少实现 NewReno-like 行为：

```
变量：
  congestion_window (cwnd): 当前拥塞窗口（字节）
  slow_start_threshold (ssthresh): 慢启动阈值（字节）
  bytes_in_flight: 已发送但未确认的字节数

发送新数据条件：
  if (bytes_in_flight < congestion_window):
      可以发送新数据

慢启动阶段（cwnd < ssthresh）：
  每个 ACK 确认 n 字节 → cwnd += n
  窗口指数增长

拥塞避免阶段（cwnd >= ssthresh）：
  每个 ACK 确认 cwnd 字节 → cwnd += max_datagram_size / cwnd
  窗口线性增长

丢包处理（NewReno）：
  进入恢复阶段
  ssthresh = max(cwnd / 2, 2 * max_datagram_size)
  cwnd = ssthresh
  退出恢复后继续拥塞避免

超时（Persistent Congestion）：
  如果连续多个 RTT 没收到任何 ACK
  cwnd = 2 * max_datagram_size （最小窗口）
```

### CUBIC 在 QUIC 中的适配

CUBIC 是目前互联网最广泛使用的 TCP 拥塞控制算法，QUIC 实现可以直接移植：

```
CUBIC 窗口增长函数：
  W(t) = C * (t - K)^3 + W_max
  
  其中：
  - W_max = 丢包时的窗口大小
  - K = (W_max * beta / C)^(1/3)
  - C = 0.4 (CUBIC 常数)
  - beta = 0.7 (乘法减小因子)
  
特点：窗口增长与 RTT 无关 → 高带宽链路优势明显
```

### BBR 的适配

BBR（Bottleneck Bandwidth and Round-trip propagation time）在 QUIC 中的优势：

```
BBR 基本原理（非丢包驱动）：
  1. 测量：BtlBw（瓶颈带宽）和 RTprop（最小 RTT）
  2.  pacing_rate = BtlBw * pacing_gain
  3.  发送窗口 = BtlBw * RTprop
  
  在 QUIC 中的好处：
  - QUIC 的精确 RTT 测量 → 更好的 RTprop 估计
  - 用户空间 → BBR 状态机更容易实现和维护
  - 多流复用 → 更好的带宽利用
```

### QUIC 拥塞控制的独特优势

| 特性 | TCP | QUIC |
|------|-----|------|
| 丢包检测 | 依赖序列号间隙 | 依赖包编号 + ACK 范围 |
| 重传歧义 | 有 | 无（单调包编号） |
| 算法切换 | 需内核修改 | 用户空间直接替换 |
| 多流独立拥塞 | 不支持 | 支持（可选） |
| 迁移后拥塞状态 | 重置 | 可选择重置或复用 |

### 多路 QUIC 实现支持的算法

| 实现 | 支持的拥塞控制 |
|------|---------------|
| Chromium QUIC | CUBIC, BBR, PCC |
| lsquic | NewReno, CUBIC, BBR |
| ngtcp2 | NewReno, CUBIC |
| msquic | CUBIC, BBR |
| quiche (Cloudflare) | CUBIC, NewReno |
| aioquic | NewReno |

---

## 一句话总结

QUIC 通过三个独立的包编号空间和单调递增包编号解决了 TCP 的重传歧义问题，其拥塞控制框架支持 NewReno/CUBIC/BBR 等多种算法并且可以在用户空间灵活切换。
