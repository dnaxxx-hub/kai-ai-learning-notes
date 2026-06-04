# Prometheus 深度 — 指标 / PromQL / 告警 / 高可用 / 存储

## 一、指标类型详解

### Counter（计数器）
- 只增不减，重启时归零
- 典型场景：请求总数、错误总数、CPU 时间
- **关键操作**：必须结合 `rate()` / `increase()` 使用，原始值无意义
- **命名约定**：以 `_total` 结尾，如 `http_requests_total`

### Gauge（仪表盘）
- 可增可减，反映当前值
- 典型场景：内存使用率、连接数、温度
- **关键操作**：`avg_over_time()` / `max_over_time()` 获取时间范围内的聚合值

### Histogram（直方图）
- 将观测值放入可配置的桶（bucket）中计数
- 典型场景：请求延迟、响应大小
- **关键指标**：`<metric>_bucket{le="<upper>"}` 累积计数
- **自动生成**：`_count`（总数）、`_sum`（总和）、`_bucket{le="+Inf"}`
- **计算分位数**：`histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[1m]))`

### Summary（摘要）
- 在客户端计算分位数，直接暴露分位数结果
- **不可聚合**：不同实例的 Summary 分位数不可相加
- **适用场景**：已知需要 p99/p50 且不需要跨实例聚合时
- 自动生成：`<metric>{quantile="0.99"}`、`_count`、`_sum`

| 特性 | Histogram | Summary |
|------|-----------|---------|
| 是否需要聚合 | 服务端计算分位数 | 客户端预计算 |
| 分位点可聚合 | ✅ 可跨实例聚合 | ❌ 不可聚合 |
| 分位点精确度 | 受桶数量限制 | 由客户端算法决定 |
| 额外开销 | 需要上报所有 bucket | 仅上报计算后的分位数 |

## 二、PromQL 必知必会

### 基础函数
```promql
rate(metric[5m])                        # 每秒增长率（Counter）
increase(metric[1h])                    # 一段时间内的增量（Counter）
avg_over_time(metric[5m])              # 时间窗口内平均值（Gauge）
max_over_time(metric[5m])              # 时间窗口内最大值
min_over_time(metric[5m])              # 时间窗口内最小值
```

### 聚合操作符
```promql
sum(rate(http_requests_total[5m])) by (service)           # 按服务聚合
avg(rate(http_requests_total[5m])) by (status_code)      # 按状态码平均
topk(5, rate(http_requests_total[5m])) by (endpoint)     # 前5个端点
count(rate(http_requests_total[5m]) > 0) by (service)    # 有流量的服务数
```

### 分位数计算
```promql
# p99 延迟（需要在 Histogram bucket 上做）
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)

# p50 延迟
histogram_quantile(0.50,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)
```

### 高级查询模式
```promql
# 错误率计算
sum(rate(http_requests_total{status=~"5.."}[5m])) 
  / sum(rate(http_requests_total[5m])) * 100

# 前值与当前对比（一周同比）
rate(http_requests_total[1h]) 
  / rate(http_requests_total[1h] offset 1w)

# 空数据补0（or 操作符）
rate(http_requests_total[5m]) or vector(0)
```

## 三、告警规则与 Alertmanager

### Prometheus 告警规则
```yaml
groups:
  - name: node_alerts
    rules:
      - alert: InstanceDown
        expr: up == 0
        for: 1m              # 持续1分钟才告警（防抖动）
        labels:
          severity: critical
        annotations:
          summary: "Instance {{ $labels.instance }} down"
          description: "{{ $labels.instance }} has been down for > 1 minute"
```

### Alertmanager 核心能力
- **分组（Grouping）**：相同告警合并为一条通知，如 `group_by: ['severity', 'cluster']`
- **抑制（Inhibition）**：已有关联高等级告警时抑制低等级告警（如：节点 Down 则抑制该节点上的所有告警）
- **静默（Silence）**：运维窗口期手动静音匹配的告警（维护期间避免骚扰）
- **路由树**：按标签匹配分发到不同接收器（Email、Slack、PagerDuty、Webhook）

```yaml
route:
  group_by: ['alertname', 'cluster']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: default
  routes:
    - match:
        severity: critical
      receiver: pagerduty
```

## 四、服务发现（Service Discovery）

- **kubernetes_sd_configs**：自动发现 Pod、Service、Endpoint、Node
- **file_sd_configs**：静态文件维护目标列表（适合 CMDB 集成）
- **consul_sd_configs**、**dns_sd_configs**、**ec2_sd_configs**
- **relabel_config**：标签重写、过滤（keep/drop/replace/hashmod）

## 五、高可用方案

### Thanos
- **Sidecar**：每个 Prometheus 挂一个 Sidecar，将数据上传到对象存储
- **Store Gateway**：从对象存储读取历史数据，实现无限保留
- **Querier**：统一查询入口，合并多个 Prometheus 的数据
- **Compactor**：降采样、去重、压缩对象存储数据
- **Ruler**：在 Thanos 层面运行告警规则

### Cortex
- **水平分片**：按时间范围拆分（Ingester + Distributor + Querier）
- **多租户**：原生支持，适合大型 SaaS 场景
- 相比 Thanos 更重，功能更全（支持 Ruler、Alertmanager 托管）

### 对比
| 方案 | 复杂度 | 存储 | 适用规模 |
|------|--------|------|----------|
| 单机 Prometheus | 低 | 本地 TSDB | 小规模(<100w series) |
| Prometheus HA | 中 | 本地 + 重复采集 | 中等 |
| Thanos | 中高 | 对象存储 | 大规模 |
| Cortex | 高 | 对象存储 + 分片 | 超大/SaaS |

## 六、存储优化

### TSDB 压缩
- **2小时 block**：Prometheus 每 2h 生成一个 block，不可变
- **压缩后**：block 内对同一 series 的数据做 delta/delta-of-delta 编码
- **压缩比**：原始数据:TSDB ≈ 10:1 ~ 20:1（取决于值的变化率）

### Retention（保留期）
- `--storage.tsdb.retention.time`：默认 15 天
- `--storage.tsdb.retention.size`：按大小限制保留（适合 SSD 有限场景）

### WAL（Write-Ahead Log）
- 数据先写 WAL 再写内存，崩溃时可回放恢复
- WAL 文件每 2h 在 block 压缩后清理
- **监控指标**：`prometheus_tsdb_wal_corruptions_total`、`prometheus_tsdb_head_series`

### 最佳实践
- **Recording Rules**：预聚合高频查询，减少实时计算压力
- **relabel 精简**：只保留需要的 label，避免高基数（cardinality）爆炸
- **对象存储归档**：热数据 Prometheus（3-7天）+ 冷数据 Thanos/Cortex（S3/GCS）
