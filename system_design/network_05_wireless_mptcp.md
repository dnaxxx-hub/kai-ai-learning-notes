# 计算机网络第5课：无线网络与多路径TCP

## 一、802.11 WiFi

### 1.1 介质访问控制：CSMA/CA

WiFi 使用 **CSMA/CA（载波侦听多路访问/冲突避免）**，与以太网的 CSMA/CD 不同。

**为什么不能检测冲突？**
- 无线收发器无法同时发送和接收
- 隐蔽站问题（Hidden Terminal Problem）

**CSMA/CA 流程（DCF 模式）**：

```
1. 站点监听信道（CCA - Clear Channel Assessment）
2. 若信道空闲持续 DIFS 时间 → 退避计数
3. 退避过程中，每检测到一个空闲时隙，计数器减1
4. 计数器到零 → 发送数据
5. 接收方收到后等待 SIFS → 回复 ACK
6. 发送方收到 ACK → 发送成功；未收到 → 重传（指数退避）
```

```
          DIFS                  SIFS
┌─────────┴──────────┐   ┌──────┴──────┐
│ 退避计数（随机）    │   │   数据帧    │
├────────────────────┤   ├─────────────┤
| 被其他站点冻结     │   │    ACK      │
└────────────────────┘   └─────────────┘
```

### 1.2 RTS/CTS 机制

解决**隐蔽站问题**：

```
     A          AP           B
     │          │            │
     ├── RTS ──►│            │   A 发 RTS（Request To Send）
     │          ├─ CTS ────►│   AP 广播 CTS（Clear To Send）
     │          │            │   B 听到 CTS → 静默 NAV 时间
     ├── DATA ─►│            │   A 发数据
     │          ├─ ACK ────►│   AP 回 ACK（B 恢复发送）
     │          │            │
```

**NAV（Network Allocation Vector）**：CTS 中包含持续时间字段，所有听到 CTS 的站点在此期间保持静默。

### 1.3 MIMO（多输入多输出）

```
802.11n (MIMO)    2-4 天线 → 最高 600 Mbps
802.11ac (MU-MIMO) 多用户同时波束赋形 → 最高 6.9 Gbps
802.11ax (WiFi 6)  OFDMA + 上行 MU-MIMO → 最高 9.6 Gbps
```

| 技术 | 说明 |
|------|------|
| **空间复用** | 多天线同时发送不同数据流（并行管道） |
| **空间分集** | 多天线发送相同数据（抗衰落） |
| **波束赋形** | 调整天线相位，信号集中到目标设备 |
| **OFDMA** | 子载波分配给不同用户（WiFi 6 上行） |

---

## 二、4G LTE

### 2.1 架构：E-UTRAN + EPC

```
UE ── eNB ──┐
UE ── eNB ──┼── MME ── HSS
UE ── eNB ──┤         │
            └── S-GW ── P-GW ── Internet
```

| 组件 | 全称 | 作用 |
|------|------|------|
| **UE** | User Equipment | 手机终端（SIM + 射频） |
| **eNB** | evolved Node B | 基站：无线资源管理、调度、加密 |
| **MME** | Mobility Management Entity | 信令面：鉴权、移动性管理、寻呼 |
| **S-GW** | Serving Gateway | 用户面：数据隧道、QoS 执行、漫游锚点 |
| **P-GW** | PDN Gateway | 连接互联网：IP 分配、计费、策略 |
| **HSS** | Home Subscriber Server | 用户数据库：签约信息、鉴权向量 |

### 2.2 OFDMA 与 SC-FDMA

| 方向 | 多址接入技术 | 原因 |
|------|-------------|------|
| 下行（eNB → UE） | OFDMA | 高峰均比可接受，调度灵活 |
| 上行（UE → eNB） | SC-FDMA | 峰均比低，省电（终端功率受限） |

---

## 三、5G NR

### 3.1 架构：gNB + 5GC

```
UE ── gNB-CU (集中单元) ── 5GC (AMF/SMF/UPF)
       ├── gNB-DU (分布式单元) ── RU (射频单元)
       └── gNB-DU ── RU
```

**功能拆分**：
- **CU（Central Unit）**：RRC、PDCP 层（控制面 + 用户面）
- **DU（Distributed Unit）**：RLC、MAC、部分 PHY
- **RU（Radio Unit）**：射频前端、FFT、波束赋形

**5GC 核心网组件**：

| 组件 | 代替 4G | 作用 |
|------|---------|------|
| AMF | MME | 接入与移动性管理（信令面） |
| SMF | S-GW 控制面 | 会话管理、IP 地址分配 |
| UPF | S/P-GW 用户面 | 用户面转发：灵活下沉到边缘 |
| PCF | PCRF | 策略控制、计费策略 |
| UDM | HSS | 用户数据管理 |

### 3.2 网络切片（Network Slicing）

```
同一个物理 5G 网络 → 多个逻辑切片

┌─────────────────────────────────────┐
│       共享基础设施（RAN + 传输）      │
├──────────┬──────────┬────────────────┤
│ eMBB 切片 │ URLLC 切片 │ mMTC 切片    │
│ 大带宽    │ 低延迟    │ 海量连接      │
│ 视频/AR   │ 自动驾驶  │ IoT/智能家居  │
│ 100 Mbps  │ 1ms 延迟  │ 100万/km²    │
└──────────┴──────────┴────────────────┘
```

- 每个切片有独立的 AMF/SMF/UPF 实例
- RAN 侧通过 QoS Flow + 差异化调度实现
- NSSF（Network Slice Selection Function）选择合适的切片

### 3.3 MEC（多接入边缘计算）

```
         核心网（集中式） ← 传统架构
         │
    ┌────┴────┐
    │  UPF    │    ← UPF 下沉到基站附近
    │ + MEC   │      应用在边缘处理
    └────┬────┘
         │
    gNB ─┘    → UE
```

**价值**：
- 延迟从 50ms 降至 5-10ms
- 流量本地卸载，不经过核心网
- 典型应用：车联网 V2X、工业控制、AR/VR

---

## 四、MPTCP（多路径 TCP）

### 4.1 背景与目标

**问题**：设备有多个网络接口（WiFi + 4G, 双 WiFi），但传统 TCP 只能用一个。

**MPTCP**：在传输层将多条路径聚合成一条 TCP 连接。

```
            ┌──────────────────┐
            │    Application   │
            │    socket API    │
            ├──────────────────┤
            │    MPTCP 层       │ ← 调度器将数据分配到多条子流
            ├────┬──────┬──────┤
            │子流1│ 子流2│ 子流3│ ← 每条子流是一个标准 TCP
            ├────┴──────┴──────┤
            │    Network       │
            │  WiFi  4G  LAN  │
            └──────────────────┘
```

### 4.2 多路径子流（Subflow）

**MPTCP 连接建立**：

```
Client (WiFi+4G)                   Server
      │                               │
      ├── SYN + MP_CAPABLE ──────────►│   主连接（MPTCP 握手）
      │◄── SYN/ACK + MP_CAPABLE ─────┤
      │── ACK ──────────────────────►│
      │                               │
      ├── SYN + MP_JOIN(addr2) ─────►│   附加子流（通过第二接口）
      │◄── SYN/ACK + MP_JOIN ────────┤
      │── ACK ──────────────────────►│
      │                               │
      │◄═══ 数据双向传输（可同时在多条子流上）═══►│
```

**TCP Option 类型**：
| Option | 含义 |
|--------|------|
| MP_CAPABLE | MPTCP 主连接协商 |
| MP_JOIN | 添加新子流到已有连接 |
| DSS（Data Sequence Signal） | 数据序列号映射（子流 SEQ ↔ 全局 SEQ） |
| ADD_ADDR/REMOVE_ADDR | 通知对端新/被移除的 IP 地址 |

### 4.3 调度策略（Scheduler）

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| **Default** | 优先使用最低 RTT 子流 | 低延迟优先 |
| **Round Robin** | 轮询所有子流 | 带宽聚合 |
| **Redundant** | 所有子流发相同数据 | 高可靠性 |
| **Backup** | 仅主路径活动，备路径空闲 | 故障切换 |
| **Netlink Based** | 由用户态策略动态调度 | 灵活控制 |

### 4.4 耦合拥塞控制（CCAs）

多路径最棘手的问题：**不要比单路径更激进**。

**LIA（Linked Increases Algorithm）**（RFC 6356 标准）：
- 总吞吐量不差于最优子流
- 不劣于将所有流量放在单路径
- 兼顾**公平性**与**效率**

```
带宽小的路径上，拥塞窗口增长更慢（AIMD 耦合）
LIA 算法核心：
  - 所有子流的总和增速 ≤ 最差子流的单路径 TCP
  - 移走动量：从窗口最小的子流上丢包后，其他子流窗口也相应调整
```

**其他 CCA**：
| CCA | 特点 |
|-----|------|
| OLIA（Opportunistic LIA） | 改进型，对非瓶颈路径利用率更高 |
| wVegas | 基于延迟的拥塞控制 |
| BBR for MPTCP | 基于模型（不依赖丢包），聚合吞吐量更优 |

### 4.5 Python 模拟：MPTCP 多路径传输对比

```python
import random
import time

class Subflow:
    """模拟一条子流"""
    def __init__(self, name, rtt_ms, bw_mbps, loss_rate):
        self.name = name
        self.rtt = rtt_ms / 1000.0           # 秒
        self.bw = bw_mbps * 1_000_000 / 8     # B/s
        self.loss = loss_rate
        self.cwnd = 10                        # 初始窗口 (MSS)
        self.sent = 0
        self.lost = 0

    def transmit(self, bytes_to_send, mss=1460):
        """模拟一次传输"""
        available = self.cwnd * mss
        actual = min(bytes_to_send, available)

        # 模拟丢包
        lost_bytes = 0
        for _ in range(actual // mss):
            if random.random() < self.loss:
                lost_bytes += mss

        delivered = actual - lost_bytes
        self.sent += actual
        self.lost += lost_bytes

        # 简化 AIMD
        if lost_bytes > 0:
            self.cwnd = max(2, self.cwnd // 2)   # 丢包 → 窗口减半
        else:
            self.cwnd += 1 / self.cwnd            # 无损 → 线性增长

        # 传输时间 = 数据量 / 带宽 + RTT
        tx_time = actual / self.bw + self.rtt
        return delivered, tx_time, lost_bytes


class MPTCP:
    """多路径 TCP 连接"""
    def __init__(self, subflows):
        self.subflows = subflows
        self.total_sent = 0
        self.total_delivered = 0

    def transmit(self, total_bytes, strategy="default"):
        """按策略调度传输"""
        if strategy == "default":
            # 始终选 RTT 最小的
            ordered = sorted(self.subflows, key=lambda sf: sf.rtt)
        elif strategy == "rr":
            # 轮询
            ordered = self.subflows[:]
            random.shuffle(ordered)
        elif strategy == "redundant":
            # 冗余：每个子流都发全部数据
            results = []
            for sf in self.subflows:
                d, t, l = sf.transmit(total_bytes)
                results.append((sf.name, d, t, l))
            return results
        elif strategy == "lia":
            # 耦合拥塞控制模拟
            total_bw = sum(sf.bw for sf in self.subflows)
            results = []
            for sf in self.subflows:
                # 按带宽比例分配
                share = int(total_bytes * sf.bw / total_bw)
                d, t, l = sf.transmit(share)
                results.append((sf.name, d, t, l))
            return results

        # 默认：选最优路径发全部
        best = ordered[0]
        d, t, l = best.transmit(total_bytes)
        return [(best.name, d, t, l)]


# === 模拟对比 ===

# 创建两个子流：WiFi（低延迟）和 4G（高带宽高延迟）
wifi = Subflow("WiFi",  rtt_ms=10,  bw_mbps=50,  loss_rate=0.01)
lte  = Subflow("4G/LTE", rtt_ms=50, bw_mbps=100, loss_rate=0.03)

mptcp = MPTCP([wifi, lte])
data = 10 * 1024 * 1024  # 10MB

print("=" * 60)
print(f"传输数据: {data/1024/1024:.1f} MB")
print("=" * 60)

for strategy in ["default", "rr", "redundant", "lia"]:
    # 重置子流状态
    wifi.cwnd = 10
    lte.cwnd = 10
    wifi.sent = wifi.lost = 0
    lte.sent = lte.lost = 0

    start = time.time()
    remaining = data
    while remaining > 0:
        results = mptcp.transmit(remaining, strategy)
        for name, delivered, tx_time, lost in results:
            remaining -= delivered
            if delivered == 0:
                break
        if all(r[1] == 0 for r in results):
            break
        time.sleep(0.001)  # 模拟时间推进

    elapsed = time.time() - start
    total_delivered = data - remaining
    throughput = total_delivered / elapsed if elapsed > 0 else 0

    print(f"\n策略: {strategy.upper():12s} | 耗时: {elapsed:.3f}s | 吞吐: {throughput/1e6:.2f} MB/s")
    print(f"  WiFi: sent={wifi.sent/1024/1024:.1f}MB, lost={wifi.lost/1024/1024:.1f}MB, cwnd={wifi.cwnd:.0f}")
    print(f"  4G:   sent={lte.sent/1024/1024:.1f}MB, lost={lte.lost/1024/1024:.1f}MB, cwnd={lte.cwnd:.0f}")
```

---

## 五、总结

| 技术 | 关键要点 |
|------|---------|
| **WiFi 802.11** | CSMA/CA 避免冲突、RTS/CTS 解决隐蔽站、MIMO + OFDMA 提速率 |
| **4G LTE** | E-UTRAN（eNB）+ EPC（MME/S-GW/P-GW），OFDMA 下行 + SC-FDMA 上行 |
| **5G NR** | gNB（CU+DU+RU）、5GC 服务化架构、网络切片按场景隔离、MEC 边缘计算 |
| **MPTCP** | 多子流聚合、MP_CAPABLE/MP_JOIN 握手、调度器选径、耦合拥塞控制保公平 |

> 无线网络的核心挑战在于**不可靠的信道**和**稀缺的空口资源**。从 4G 到 5G 的演进，实质是从"连接人人"到"连接万物"的跃迁。MPTCP 则在传输层弥补了移动设备多接口的潜力，是"带宽聚合"与"无缝切换"的关键技术。
