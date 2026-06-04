# ELK 日志体系 — Logstash / Elasticsearch / Kibana

## 一、Logstash 管道

Logstash 数据处理三阶段：**Input → Filter → Output**，支持丰富的插件生态。

### Input 插件
```ruby
input {
  beats { port => 5044 }                              # Filebeat 推送
  syslog { port => 514  type => "syslog" }            # Syslog 收集
  kafka { topics => ["app-logs"] bootstrap_servers => "kafka:9092" }
  tcp { port => 5000  codec => "json" }               # TCP 直推
}
```

### Filter 插件（核心价值）

**Grok** — 非结构化日志 → 结构化字段
```ruby
filter {
  grok {
    match => { "message" => "%{COMBINEDAPACHELOG}" }
    # 预置模式 120+：%{IP} %{USER} %{TIMESTAMP_ISO8601} ...
    # 自定义模式：%{DATA:custom_field}
    break_on_match => true  # 匹配成功后停止，提高性能
  }
  mutate {
    convert => { "[bytes]" => "integer" }     # 类型转换
    rename  => { "host" => "server_host" }    # 字段重命名
    remove_field => ["message", "path"]       # 删除无意义字段
  }
  geoip {
    source => "clientip"                       # IP → 地理信息
    target => "geo"
    fields => ["city_name", "country_code2", "location"]
  }
  date {
    match => ["timestamp", "ISO8601"]         # 时间格式标准化
    target => "@timestamp"
  }
}
```

### Output 插件
```ruby
output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "logs-%{+YYYY.MM.dd}"
    flush_size => 1000      # 批量写入提高吞吐
    idle_flush_time => 5    # 5 秒强制刷新
  }
  # 或投递到 Kafka 做缓冲
  kafka { topic_id => "log-output" bootstrap_servers => "kafka:9092" }
}
```

## 二、Elasticsearch 索引优化

### 分片（Shards）
- **主分片**：索引数据切分，数量在创建索引时固定（默认 1，推荐 ≤ 20/节点）
- **副本分片**：高可用 + 读性能（默认 1，可动态调整）
- **分片大小**：10GB-50GB 为黄金区间，过小→碎片过多，过大→恢复慢

### 路由（Routing）
```json
{
  "settings": { "number_of_shards": 5, "number_of_replicas": 1 },
  "mappings": {
    "_routing": { "required": true },
    "properties": {
      "service": { "type": "keyword" },
      "@timestamp": { "type": "date" },
      "message": { "type": "text" },
      "latency_ms": { "type": "integer" }
    }
  }
}
```
- **自定义路由**：按 `service` 或 `tenant_id` 路由，保证同一服务数据在相同 shard
- **调优**：`index.routing.allocation.total_shards_per_node` 控制每节点 shard 数

### ILM（Index Lifecycle Management）
```
Hot (SSD, 写入) → Warm (HDD, 只读) → Cold (cost-effective) → Delete (过期)
```
```json
PUT _ilm/policy/logs_policy
{
  "policy": {
    "phases": {
      "hot":  { "min_age": "0ms", "actions": { "rollover": { "max_size": "50GB", "max_age": "1d" }}},
      "warm": { "min_age": "7d",  "actions": { "allocate": { "require": { "data": "warm" }}}},
      "cold": { "min_age": "30d", "actions": { "freeze": {} }},
      "delete": { "min_age": "90d", "actions": { "delete": {} }}
    }
  }
}
```

## 三、Kibana 可视化

### Dashboard
- **TSVB**（Time Series Visual Builder）：灵活的时间序列可视化
- **Vega/Vega-Lite**：自定义图形语法（适合复杂可视化）
- **Lens**：拖拽式可视化，推荐首选
- **Alerting**：基于查询的告警（阈值/异常检测）

### Canvas
- 像素级控制，适合制作运维大屏
- 支持实时数据 + 静态元素组合
- 适用于：SOC 大屏、运营报表墙

### Maps
- **坐标地图**：geoip 字段的地理可视化
- **区域聚合**：按国家/城市聚合错误分布
- **追踪分析**：结合 IP 地理信息观察流量来源

## 四、替代方案：Loki + Promtail + Grafana

### Loki 架构
| 特性 | ELK | Loki |
|------|-----|------|
| 索引策略 | 全文本索引（昂贵） | 标签索引（廉价） |
| 存储成本 | 高（倒排索引占 50%+） | 低（仅标签索引） |
| 查询语法 | Lucene/Query DSL | LogQL（类似 PromQL） |
| 与 Metrics 关联 | 弱 | 强（共用 label，同一个 Grafana） |
| 实时性 | 秒级 | 秒级 |
| 推荐场景 | 复杂搜索/分析 | K8s 日志/与 Prometheus 联动 |

### LogQL 示例
```logql
{service="payment-api", namespace="prod"} |= "ERROR" 
| json 
| latency_ms > 200 
| rate [5m]
```

### 选择建议
- **ELK 更适合**：需要全文搜索、复杂过滤、数据 Pipeline 丰富的场景
- **Loki 更适合**：K8s 原生环境、与 Prometheus 深度整合、控制日志成本的场景

## 五、日志成本控制

### 采样策略
- **头采样（Head-based）**：请求入站时决定采集（简单，可能漏掉慢请求）
- **尾采样（Tail-based）**：完成后再决定采样（精准，延迟高）
- **动态采样**：异常日志全采，正常日志按比例采

### 热温冷架构（ELK）
| 层 | 存储 | 保留时间 | 副本数 | 建议 |
|----|------|----------|--------|------|
| Hot | SSD | 1-3 天 | 1 | 可写入、实时查询 |
| Warm | HDD | 7-30 天 | 0-1 | 只读、可查询 |
| Cold | Object Storage | 30天-1年 | 0 | 很少查询 |

### 其他成本优化
- **结构化日志**：减少无用字段、避免超大 message
- **日志级别过滤**：生产环境 WARN+，DEBUG 仅在排查时开启
- **日志压缩**：GZIP 压缩比可达 10:1，ES 索引时设置 `best_compression`
- **Rollover + Shrink**：旧索引缩小 shard 数
- **保留策略自动清理**：ILM 或 Curator 定时任务
