# 可观测性三大支柱 — Metrics / Logging / Tracing

## 概述

可观测性（Observability）是 SRE 判断系统内部状态的黄金三角。三大支柱相互独立又协同工作：**Metrics 告诉你哪里有问题，Tracing 告诉你哪个请求出了问题，Logging 告诉你具体是什么问题。**

## 一、Metrics（指标）

### Prometheus
- **拉模型架构**：Prometheus Server 定期从 Exporter 拉取指标，避免推模型中的目标注册压力
- **多维数据模型**：时间序列通过 `metric_name{label="value"}` 唯一标识
- **Exporter 生态**：node_exporter（系统）、blackbox_exporter（探活）、process_exporter、自定义 exporter
- **Pushgateway**：适合短生命周期任务（批处理、CronJob），但不要滥用（单点故障、无法过期）

### OpenMetrics
- CNCF 孵化标准，Prometheus exposition format 的超集
- 支持 **metadata 元信息、单位（unit）、类型提示（_total/_created）**
- 由 IETF HTTP API 标准化工作组推进，Prometheus 2.x 原生支持

### Grafana
- **面板类型**：Time Series（时序）、Stat（统计）、Table（表）、Heatmap（热力图/直方图）
- **多数据源**：Prometheus、Loki、Elasticsearch、CloudWatch、Graphite 等
- **告警规则**：Grafana Alerting 可作为 Alertmanager 的替代或补充
- **Annotations**：在图上标记部署、故障时间点，关联事件

### 关键指标类型
| 指标 | 说明 | 适用场景 |
|------|------|----------|
| Counter | 只增不减 | 请求总数、错误计数 |
| Gauge | 可增可减 | 内存使用、在线连接数 |
| Histogram | 分桶统计 | 延迟分布（适合计算 p99） |
| Summary | 分位数预估 | 延迟分位数（客户端计算） |

## 二、Logging（日志）

### ELK Stack
- **Filebeat → Logstash → Elasticsearch → Kibana**：经典管道
- **结构化日志**：JSON 格式优于文本日志，便于字段提取
- **Logstash 管道**：input（beats/syslog/tcp）→ filter（grok/geoip/mutate）→ output（es/kafka）
- **Elasticsearch 索引**：按时间滚动的 `logstash-YYYY.MM.DD` 索引

### Loki
- **Grafana Loki**：受 Prometheus 启发的日志系统
- **标签索引**：仅索引日志流的标签（如 service、pod），不索引日志内容
- **LogQL**：类似 PromQL 的查询语法，可结合 metrics 做 label 关联
- **agent**：promtail / Alloy，自动从容器、文件、journald 采集

### 结构化日志最佳实践
```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "ERROR",
  "service": "payment-api",
  "trace_id": "abc123",
  "user_id": "u_456",
  "message": "payment failed",
  "error": "insufficient_balance",
  "latency_ms": 150
}
```

## 三、Tracing（分布式追踪）

### OpenTelemetry
- **合并 OpenTracing + OpenCensus**，CNCF 孵化项目
- **三个核心组件**：API/SDK、Collector、Exporters
- **跨语言支持**：Java/Go/Python/Node.js/Ruby/C++/.NET
- **自动埋点**：通过 ByteBuddy（Java）或 Monkey Patching（Python）自动注入

### Jaeger vs Zipkin
| 特性 | Jaeger | Zipkin |
|------|--------|--------|
| 后端存储 | Elasticsearch/Cassandra/Badger | Elasticsearch/Cassandra/MySQL |
| UI 丰富度 | 高（DAG、火焰图、服务依赖） | 基础 |
| 采样策略 | 概率/速率限制/自适应 | 概率/速率限制 |
| 部署方式 | All-in-one / Production (Collector+Query) | 单体/微服务 |
| 社区 | CNCF 毕业项目 | 较成熟但更新慢 |

### 核心概念
- **Trace**：一个请求的完整调用链
- **Span**：调用链中的单个操作（含 SpanContext、ParentSpanID、Timing）
- **SpanContext**：携带 TraceID、SpanID、Baggage（跨服务传播元数据）
- **Baggage**：跨服务传播的键值对（不滥用，避免性能开销）

## 四、三大支柱关系

```
┌─────────────────────────────────────────────┐
│                   用户反馈                    │
└─────────────┬───────────────────────────────┘
              │
    ┌─────────▼─────────┐
    │   Metrics 告警     │ ← 第一时间知道"有问题"
    │  (高延迟/错误率)    │
    └─────────┬─────────┘
              │
    ┌─────────▼─────────┐
    │   Tracing 定位     │ ← 找出是哪类请求/哪个服务
    │  (TraceID/延迟分布) │
    └─────────┬─────────┘
              │
    ┌─────────▼─────────┐
    │   Logging 排查     │ ← 确认具体错误堆栈/原因
    │  (trace_id 关联)   │
    └─────────┬─────────┘
              │
    ┌─────────▼─────────┐
    │   Root Cause      │
    └───────────────────┘
```

**实战决策链路**：
1. **Metrics** 告警 → 看 Grafana Dashboard 确认异常范围（时间、服务、区域）
2. **Tracing** → 找到该时间窗口的高延迟 Trace，定位瓶颈服务/数据库
3. **Logging** → 通过 trace_id 在日志中搜索该请求，查看具体错误堆栈

## 关键思维

- **可观测性不是工具堆砌，而是数据关联能力**：能用一个 TraceID 串起 Metrics、Logs、Traces
- **成本控制**：指标降采样（Recording Rules），日志采样（tail-based），Tracing 头采样
- **三大支柱缺一不可**：只有 Metrics 没有 Trace 只能定位到"哪个服务"；只有 Trace 没有 Log 只能知道"哪里慢"不知道"为什么"；只有 Log 没有 Metrics 无法主动发现问题
