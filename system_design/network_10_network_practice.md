# 网络实战 — 抓包、测试、故障排查

## 1. tcpdump 抓包分析

### 基础用法

```bash
# 抓取所有流量 (需要root权限)
tcpdump -i any

# 抓取特定网卡
tcpdump -i eth0

# 不解析DNS, 显示数字IP
tcpdump -nn

# 抓取80端口的HTTP流量
tcpdump -i any port 80

# 抓取指定主机
tcpdump host 192.168.1.1
tcpdump src host 192.168.1.1
tcpdump dst host 8.8.8.8

# 组合过滤 (and / or / not)
tcpdump -nn 'host 192.168.1.1 and port 443'

# 保存到文件, 供Wireshark分析
tcpdump -i any -w capture.pcap
tcpdump -r capture.pcap              # 读取pcap文件

# 显示数据包内容
tcpdump -A                           # ASCII格式(HTTP请求体)
tcpdump -X                           # Hex + ASCII
tcpdump -XX                          # 链路层头部 + Hex + ASCII
```

### 实操场景

**抓TCP三次握手**:
```bash
tcpdump -i any -nn 'host example.com and tcp port 443'
# 输出示例:
# 12:00:00.123456 IP 192.168.1.2.54321 > 93.184.216.34.443: Flags [S], seq 1000
# 12:00:00.123789 IP 93.184.216.34.443 > 192.168.1.2.54321: Flags [S.], seq 2000, ack 1001
# 12:00:00.124012 IP 192.168.1.2.54321 > 93.184.216.34.443: Flags [.], ack 2001
# 三次握手完成!
```

**抓HTTP请求**:
```bash
tcpdump -i any -A port 80 | grep -A5 "GET\|Host"
```

**抓DNS查询**:
```bash
tcpdump -i any -nn port 53
```

**抓TCP重传**:
```bash
tcpdump -i any 'tcp[tcpflags] & (tcp-syn|tcp-ack) != 0 and not host localhost'
```

### tcpdump 标志位速查

| Flags | 字符 | 含义 |
|-------|------|------|
| [S] | SYN | 握手请求 |
| [.] | ACK | 确认 |
| [F] | FIN | 关闭连接 |
| [R] | RST | 重置连接 |
| [P] | PSH | 推送数据 |
| [S.] | SYN-ACK | 握手响应 |
| [R.] | RST-ACK | 带确认的复位 |

## 2. Wireshark 使用技巧

### 常用过滤表达式

```
# 基础过滤
tcp.port == 443                     # HTTPS端口
ip.addr == 192.168.1.1              # 特定IP
http || dns                         # HTTP或DNS
tcp.flags.syn == 1                  # SYN包
tcp.analysis.retransmission         # 重传包
tcp.analysis.fast_retransmission    # 快速重传
tcp.analysis.lost_segment           # 丢包
tcp.stream eq 0                     # 单个TCP流

# 组合过滤
(ip.src == 192.168.1.1 || ip.dst == 192.168.1.1) && tcp.port == 80
http.request && http.host contains "example"

# 延迟分析
tcp.analysis.ack_rtt > 0.1          # ACK RTT > 100ms
```

### Wireshark 分析流程

```
1. 统计 → 协议分级(Protocol Hierarchy)
   看哪种协议占流量最多

2. 统计 → 对话(Conversations)
   看哪些IP通信最频繁

3. 统计 → 端点(Endpoints)
   看单个IP的流量统计

4. 用 TCP 流(Follow TCP Stream)
   右键 → Follow → TCP Stream
   重建整个HTTP对话内容

5. 专家信息(Expert Info)
    分析 → 专家信息
    自动标记错误/警告/注意
```

## 3. iperf 吞吐测试

```bash
# 服务端
iperf3 -s                      # 默认端口5201
iperf3 -s -p 8888             # 指定端口

# 客户端 (测试30秒)
iperf3 -c server_ip
iperf3 -c server_ip -t 30 -i 1   # 30秒, 每秒输出

# 反向测试 (服务器→客户端)
iperf3 -c server_ip -R

# 并行流 (测试多连接性能)
iperf3 -c server_ip -P 4

# UDP测试 (测试抖动/丢包)
iperf3 -c server_ip -u -b 100M  # 100Mbps UDP
iperf3 -c server_ip -u -b 0     # 最大速率UDP

# 双向同时测试
iperf3 -c server_ip --bidir

# 测试结果解读
[ ID] Interval       Transfer      Bitrate         Jitter    Lost/Total
[  5] 0.00-30.00 sec 356 MBytes   99.5 Mbits/sec  0.052ms   0/262601 (0%)
# Bitrate = 实际吞吐量
# Jitter = 延迟抖动 (UDP)
# Lost = 丢包率 (UDP)
```

## 4. 常见网络故障排查

### 排查方法论 (自上而下)

```
1. 应用层     → 浏览器报错? 服务跑着没? curl能否访问?
2. 传输层     → 端口通不通? TCP握手成功了?
3. 网络层     → ping通吗? 路由表对吗? TTL超时了吗?
4. 链路层     → ARP解析OK吗? 网卡Link灯亮吗?
5. 物理层     → 网线插好了吗? WiFi连上了吗?
```

### 经典故障场景

#### 场景1: 网页打不开

```bash
# 1. 本地网络检查
ping 192.168.1.1             # 网关通不通?
ping 8.8.8.8                 # 外网通不通?
ping baidu.com               # DNS解析正常吗?

# 2. DNS检查
nslookup example.com
dig example.com

# 3. 端口检查
nc -zv example.com 80        # telnet/nc测试端口
curl -v http://example.com   # HTTP详细输出

# 4. 路由追踪
traceroute example.com       # 在哪一跳断了?
```

#### 场景2: 网速慢

```bash
# 1. 瓶颈在哪段?
iperf3 -c 网关IP             # 局域网内吞吐
iperf3 -c 8.8.8.8            # 外网吞吐

# 2. 丢包检查
ping -c 100 -i 0.1 网关IP    # 大量ping看丢包率
mtr 8.8.8.8                  # 每一跳的丢包和延迟

# 3. TCP参数检查
sysctl net.ipv4.tcp_congestion_control  # 拥塞控制算法
ss -i                         # TCP窗口大小

# 4. 带宽占用
nethogs                       # 按进程看带宽
iftop                         # 按连接看带宽
```

#### 场景3: DNS解析失败

```bash
# 排障步骤
nslookup example.com 8.8.8.8     # 用Google DNS试试
nslookup example.com 114.114.114.114  # 用国内DNS

dig +trace example.com            # 完整解析链路

# DNS缓存问题
ipconfig /flushdns                # Windows
sudo systemd-resolve --flush-caches  # Linux

# 检查/etc/resolv.conf
cat /etc/resolv.conf              # Linux DNS配置
```

#### 场景4: TCP连接重置(RST)

```bash
# 抓RST包
tcpdump -i any 'tcp[tcpflags] & tcp-rst != 0'

# 可能原因:
# 1. 防火墙拦截
# 2. 服务没运行 / 端口未监听
# 3. 半连接超时
# 4. 内核参数 tcp_tw_reuse/tcp_tw_recycle (Linux)

# 检查监听端口
ss -tlnp | grep 8080
netstat -antp | grep 8080
```

## 5. 实用网络工具一览

| 工具 | 用途 | 示例 |
|------|------|------|
| ping | 连通性 + RTT | `ping -c 5 8.8.8.8` |
| traceroute | 路由追踪 | `traceroute google.com` |
| mtr | 综合路由+丢包 | `mtr 8.8.8.8` |
| nslookup/dig | DNS查询 | `dig example.com` |
| nc (netcat) | 端口扫描/原始连接 | `nc -zv host 22` |
| curl | HTTP调试 | `curl -v https://api.example.com` |
| tcpdump | 抓包 | `tcpdump -i any port 80` |
| iperf3 | 吞吐测试 | `iperf3 -c server -t 30` |
| ss | socket统计 | `ss -tanp` |
| iftop | 带宽监控 | `iftop` |
| nethogs | 进程带宽 | `nethogs eth0` |
| sslyze | TLS扫描 | `sslyze --regular example.com:443` |
| nmap | 端口扫描 | `nmap -sT -p 1-1000 192.168.1.1` |

## 6. 排查速查表

```
问题: "连不上网站"
  ├─ ping 不通   → 网络不通 / DNS / 路由问题
  ├─ ping 通     → 端口问题 / 防火墙 / 服务挂了
  │   ├─ nc -zv port 连不上 → 防火墙或服务没开
  │   └─ nc -zv port 连上  → 应用层问题(证书/HTTP错误)
  └─ 用curl测试:
      - curl -v http://...   → 看HTTP响应
      - curl -k https://...  → 跳过证书验证

问题: "很慢"
  ├─ ping 看 RTT: 正常<10ms(局域网), <100ms(跨海)
  ├─ mtr 看每跳延迟和丢包
  ├─ iperf3 测吞吐: 局域网应有线, 无线可能有干扰
  └─ tcpdump 抓包看TCP重传

问题: "间歇性断连"
  ├─ 检查WiFi信号强度
  ├─ 检查ARP表有没有冲突
  ├─ 检查DHCP租期和路由表
  └─ 大量ping看连续丢包模式
```
