# 第8课：RPC与gRPC

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. RPC基础

### 什么是RPC
远程过程调用——像调用本地函数一样调用远程服务。

```
客户端                   服务端
  │                         │
  │── 序列化参数 (JSON/PB) ──→│
  │                         │── 反序列化
  │                         │── 执行函数
  │←── 序列化结果 ────────────│
```

### RPC vs REST
| 对比 | RPC | REST |
|------|-----|------|
| 抽象 | 调用方法 | 操作资源 |
| 协议 | TCP/HTTP2 | HTTP1.1 |
| 编码 | Protobuf/Thrift | JSON |
| 性能 | 高 | 中 |
| 可读性 | 低 | 高 |
| 适用 | 微服务内部 | 对外API |

## 2. gRPC核心机制

### Protocol Buffers
```protobuf
syntax = "proto3";

service Greeter {
  rpc SayHello (HelloRequest) returns (HelloReply);
  rpc StreamHello (HelloRequest) returns (stream HelloReply);
}

message HelloRequest {
  string name = 1;
  int32 age = 2;
}

message HelloReply {
  string message = 1;
}
```

### 4种调用模式
1. **Unary RPC**：客户端发1条，服务端回1条
2. **Server Streaming**：客户端发1条，服务端流式返回
3. **Client Streaming**：客户端流式发送，服务端回1条
4. **Bidirectional Streaming**：双向流

### gRPC通信栈
```
应用层：gRPC Stub (生成的客户端/服务端代码)
序列化层：Protocol Buffers (高效二进制编码)
传输层：HTTP/2 (多路复用、头部压缩、流控)
底层：TCP
```

## 3. 服务发现与负载均衡

### 服务注册
```
                Registry
              /    |    \
             /     |     \
         Provider1 Provider2 Provider3
              \     |     /
               \    |    /
              Consumer
```

### 常见方案
- **gRPC内置**：`dns:///service-name`
- **Consul**：健康检查 + KV存储
- **etcd**：watch机制推送变更
- **Kubernetes**：CoreDNS + Service

### 负载均衡策略
- Round-Robin（轮询）
- Least Connections（最小连接）
- Random（随机）
- Weighted（加权）
- Consistent Hashing（一致性哈希，状态ful服务）

## 4. 自定义序列化实现

### Protobuf核心思想
```
字段编号（不是名字）→ 节省空间
Varint编码 → 小整数占更少字节
T-L-V格式 → 类型Tag(3bit)+字段编号+长度+值
向后兼容 → 新增字段不影响旧代码
```

### Varint编码示例
```
数值 300 → 二进制: 100101100
分成7bit组: 010 1100  000 0011
反转并加高位: 10101100  00000011
→ 0xAC 0x03 (2字节 vs 原始2字节)
```

## 5. 自定义RPC框架设计

### 核心组件
```
Client Stub     Server Stub
   │                │
   ▼                ▼
Invoker           Handler
   │                │
   ▼                ▼
Serializer        Serializer
   │                │
   ▼                ▼
Transporter       Transporter
(TCP/HTTP)        (TCP/HTTP)
   │                │
   └──── network ───┘
```

### 一次RPC调用包含
1. 客户端Stub拦截调用
2. 序列化参数为字节流
3. 网络传输
4. 服务端反序列化
5. 调用实际处理函数
6. 序列化结果
7. 网络回传
8. 客户端反序列化得到结果

## 6. 服务注册发现机制深度

### etcd（我们最想要的方案）
etcd 的 Watch 机制天然适合服务发现——服务启动时注册临时 key（TTL），消费者 Watch 这个目录，任何变化实时推送。

```
服务注册流程：
┌──────────┐     PUT /services/strategy/A    ┌──────────┐
│ 策略引擎  │ ──────────────────────────────→ │  etcd    │
│ (Provider)│                                 │ 集群     │
└──────────┘     Lease 30s + Auto-Keepalive   └────┬─────┘
                                                    │ Watch
                                                    │ /services
                                                    ▼
                                              ┌──────────┐
                                              │ 交易引擎  │
                                              │ (Consumer)│
                                              └──────────┘
```

**etcd 服务发现关键点**：
- **Lease（租约）**：每个注册的服务有个 TTL，服务挂了租约到期自动清除
- **Watch（监听）**：消费者监听目录变化，新增/删除/更新实时通知
- **Revision（版本号）**：每次变更递增版本，支持历史查询和断线重连
- **TTL 设置**：建议 10-30s，心跳间隔 TTL/3

```
# 伪代码：服务注册
etcd.put("/services/strategy/ma-14-18", 
         value='{"host":"192.168.1.10","port":8501,"strategies":["ma_14_18","bollinger"]}',
         lease=30)
go routine: every 10s → etcd.keepalive(lease_id)

# 伪代码：服务发现（Watch）
etcd.watch("/services/strategy", callback=on_change)
def on_change(events):
    for e in events:
        if e.type == PUT:    add_service(e.key, e.value)
        if e.type == DELETE: remove_service(e.key)
```

### Consul
- **Gossip协议**：SWIM 改进版，节点间互相探测健康
- **DNS接口**：`strategy.service.consul` → 自动解析到可用节点
- **KV存储**：可存策略配置、全局开关
- **多数据中心**：跨机房服务发现

### 分布式协调选型对比

| 方案 | 一致性 | 性能 | 适用场景 | 我们现状 |
|------|--------|------|----------|----------|
| **etcd** | Raft强一致 | 高(万级QPS) | 服务发现/配置中心 | ✅ 最适合，API简洁 |
| **Consul** | Raft+SWIM | 中 | 服务发现+DNS | 健康检查强于etcd |
| **Nacos** | 自研(AP/CP) | 高 | 微服务全套 | 重，比etcd复杂 |
| **ZooKeeper** | ZAB强一致 | 中 | 分布式协调 | 太重，不建议 |
| **Eureka** | AP最终一致 | 高 | 纯服务发现 | 已过时(Netflix弃用) |

## 7. 负载均衡高级策略

### gRPC 内置 LB
```go
// gRPC 客户端负载均衡
conn, _ := grpc.Dial(
    "dns:///strategy-cluster:8501",
    grpc.WithDefaultServiceConfig(`{
        "loadBalancingConfig": [{"round_robin": {}}]
    }`),
)
```

### 一致性哈希
```
传统取模的问题：
  服务器从N台变N-1台 → 大部分key被重新映射
一致性哈希：
  服务器+key都哈希到环上 → 增减服务器只影响相邻节点
  虚拟节点 → 解决分布不均
```

### 动态加权
```
实时采集每个节点的：
  - CPU 使用率
  - 请求延迟 P50/P95
  - 错误率
动态调整权重：
  weight = base_weight × (1 - error_rate) × (1 - cpu_usage × 0.5)
```

## 8. 与量化系统的结合（重点）

### 现状问题
我们现有的 system_orchestrator_v2.py + system_bridge.py 是一个单体调度+总线架构：

```
当前架构（单体总线）：
  monitor_v3.py ─→ system_bridge.py (消息总线) ─→ strategy_v4.py
  backtest_v3.py ─→ system_bridge.py ─→ live_signal.py
  curiosity_engine.py ─→ system_bridge.py ─→ distill_engine.py
```

问题：
- 所有模块通过同一个Python进程中的消息总线通信 → 单点故障
- 不能跨机器部署（策略模块和数据模块都在一台机器上）
- 模块重启需要手动干预
- 扩容困难

### 目标架构（微服务+RPC）

```
目标架构（gRPC + etcd 服务发现）：

                    ┌─────────────┐
                    │    etcd     │ ← 服务注册中心
                    │  集群(3节点)│
                    └──────┬──────┘
                           │ Watch / Register
         ┌─────────────────┼────────────────────┐
         ▼                 ▼                     ▼
  ┌────────────┐   ┌──────────────┐   ┌────────────────┐
  │ 行情服务    │   │ 策略引擎      │   │ 交易执行服务    │
  │ gRPC Server │   │ gRPC Server  │   │ gRPC Server     │
  │ 推送实时行情 │   │ 计算信号      │   │ 对接券商API     │
  ├────────────┤   ├──────────────┤   ├────────────────┤
  │ Stream K线  │   │ Unary 信号   │   │ Unary 下单      │
  │ Stream Tick │   │ Stream 反馈  │   │ Stream 成交回报 │
  └────────────┘   └──────────────┘   └────────────────┘
         │                 │                    │
         └─────────────────┼────────────────────┘
                           ▼
                    ┌──────────────┐
                    │  风控服务     │
                    │ gRPC Server  │
                    │ 拦截非法订单  │
                    │ 检查仓位限制  │
                    │ 检查资金额度  │
                    └──────────────┘
```

### 各模块的 proto 定义

```protobuf
// 行情服务
service MarketData {
  // 单次查询
  rpc GetKLine(KLineRequest) returns (KLineResponse);
  // 实时推送（Server Streaming）
  rpc SubscribeTick(TickRequest) returns (stream TickData);
  // 历史+实时混合
  rpc GetBackfillThenStream(BackfillRequest) returns (stream BarData);
}

message KLineRequest {
  string symbol = 1;       // "000009"
  string exchange = 2;     // "SZ"
  int32 period = 3;        // 60(1min), 300(5min), 3600(...)
  int64 start_ts = 4;
  int64 end_ts = 5;
}

message BarData {
  string symbol = 1;
  int64 timestamp = 2;
  double open = 3;
  double high = 4;
  double low = 5;
  double close = 6;
  int64 volume = 7;
}

// 策略引擎
service Strategy {
  rpc GetSignal(SignalRequest) returns (SignalResponse);
  rpc StreamSignal(SignalRequest) returns (stream SignalResponse);
}
```

### 迁移路线图

| 阶段 | 内容 | 收益 |
|------|------|------|
| **Phase 1** | system_bridge 加 gRPC 接口模块 | 预留未来拆分接口 |
| **Phase 2** | 行情模块独立为 gRPC 服务 | 策略和行情解耦 |
| **Phase 3** | etcd 做服务注册+配置中心 | 热更新策略参数 |
| **Phase 4** | 策略引擎水平扩展 | 支持多策略并行 |
| **Phase 5** | 全微服务+容器化 | 交付运维一体化 |

### 热更新方案（etcd Watch）

```
当前系统：改策略参数需要改代码后重启
etcd 方案：
  1. 策略参数存 etcd /config/strategy/ma_14_18
  2. 策略运行 Watch /config/strategy
  3. 参数变化 → 策略动态重算信号 → 无感知切换
```

这就解决了我们目前改策略参数需要改代码重启的问题——利用 etcd 的 Watch 机制实现真正的热更新。我们现有的 system_orchestrator_v2.py 也内置类似逻辑就更完美了。  

