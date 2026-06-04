# DevOps #4：监控与告警

> 2026-05-17
> 前置：K8s 实操 #3

## 1. 监控体系

量化系统需要监控的四个层面：

```
1. 基础设施（CPU/内存/磁盘/网络）
2. 应用（行情延迟、信号计算时间、回测状态）
3. 业务（持仓盈亏、信号频率、策略表现）
4. 告警（阈值触发、状态变化、异常检测）
```

### 1.1 Prometheus + Grafana

```
Prometheus（监控数据采集 + 存储）
  └─ 拉模式：定期从目标抓取 metrics
  └─ 时序数据库：存储所有指标
  └─ Alertmanager：告警路由

Grafana（可视化面板）
  └─ 连接 Prometheus 数据源
  └─ 自定义仪表盘
  └─ 告警通知
```

### 1.2 Python Metrics 接入

```python
# prometheus_client 库
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import time

# 指标定义
signals_generated = Counter(
    'quant_signals_total', 
    'Total trading signals generated',
    ['strategy']  # label: 按策略区分
)

portfolio_value = Gauge(
    'quant_portfolio_value',
    'Current portfolio value'
)

signal_latency = Histogram(
    'quant_signal_latency_seconds',
    'Signal computation latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

# 在 Monitor 中上报
class QuantMonitor:
    def __init__(self):
        start_http_server(8000)  # Prometheus 抓取 endpoint
        
    def on_signal(self, strategy: str):
        signals_generated.labels(strategy=strategy).inc()
        
    def update_portfolio(self, value: float):
        portfolio_value.set(value)

    def compute_signal(self, prices: np.ndarray):
        with signal_latency.time():  # 自动记录耗时
            signal = self._calc(prices)
        return signal
```

## 2. 量化系统监控面板

### 2.1 思路

```
实时面板（Grafana）：
  ┌───────────────┬────────────────┬───────────────┐
  │ 持仓盈亏       │ 今日信号次数    │ 最新行情      │
  │ 曲线 + 数字    │ 按策略分解      │ 买一/卖一     │
  ├───────────────┼────────────────┼───────────────┤
  │ 策略信号延迟    │ 布林带状态      │ 系统资源      │
  │ 直方图         │ K 线图+信号点   │ CPU/内存/网络 │
  ├───────────────┴────────────────┴───────────────┤
  │ 最近交易列表（时间、策略、方向、价格、盈亏）      │
  └───────────────────────────────────────────────┘
```

### 2.2 PromQL 查询示例

```promql
# 夏普比率计算（最近 30 天）
quant_portfolio_value / 
  delta(quant_portfolio_value[30d])

# 信号频率（每分钟）
rate(quant_signals_total[1m])

# 信号延迟 P99
histogram_quantile(0.99, 
  rate(quant_signal_latency_seconds_bucket[5m])
)

# 策略比较（按标签聚合）
sum by(strategy) (quant_signals_total)

# 异常检测：信号数量突然改变
abs(
  rate(quant_signals_total[5m]) - 
  avg_over_time(rate(quant_signals_total[5m])[1h:])
) > threshold
```

## 3. 告警

### 3.1 Alertmanager 规则

```yaml
# prometheus-rules.yaml
groups:
- name: quant-alerts
  rules:
  - alert: HighSignalLatency
    expr: |
      histogram_quantile(0.95, 
        rate(quant_signal_latency_seconds_bucket[5m])
      ) > 0.1
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "信号计算延迟过高"
      description: "P95 延迟 {{ $value | humanizeDuration }}，超过 100ms"

  - alert: NoSignals
    expr: |
      rate(quant_signals_total[10m]) == 0
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "信号停止生成"
      description: "过去 10 分钟无新信号"

  - alert: BacktestFailed
    expr: |
      quant_backtest_status{result="failure"} > 0
    labels:
      severity: critical
    annotations:
      summary: "回测失败"
      description: "策略 {{ $labels.strategy }} 最新回测失败"

  - alert: PortfolioDrop
    expr: |
      quant_portfolio_value < 90000
    labels:
      severity: critical
    annotations:
      summary: "组合资产跌到 9 万以下"
      description: "当前 {{ $value | humanize }} 元"
```

### 3.2 通知渠道

```yaml
# alertmanager.yaml
route:
  receiver: 'feishu-default'
  routes:
  - match:
      severity: critical
    receiver: 'feishu-urgent'
    repeat_interval: 30m  # 严重告警每 30 分钟重发

receivers:
- name: 'feishu-default'
  webhook_configs:
  - url: 'https://open.feishu.cn/open-apis/bot/v2/hook/xxx'
    send_resolved: true

- name: 'feishu-urgent'
  webhook_configs:
  - url: 'https://open.feishu.cn/open-apis/bot/v2/hook/xxx-urgent'
    send_resolved: true
```

### 3.3 Python 内置告警（轻量方案）

在不引入 Prometheus 的情况下，可以用 Python 自建简单监控：

```python
class SimpleMonitor:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.metrics = {
            'signal_count': 0,
            'last_signal_time': 0,
            'portfolio_value': 100000,
        }
        
    def check(self):
        now = time.time()
        alerts = []
        
        # 信号停止检查
        if now - self.metrics['last_signal_time'] > 600:  # 10 分钟
            alerts.append('CRITICAL: 停止接收行情信号超过 10 分钟')
            
        # 组合下跌检查
        if self.metrics['portfolio_value'] < 90000:
            alerts.append('CRITICAL: 组合跌破 9 万')
            
        # 延迟检查（传入 timeout 函数）
        latency = self.measure_latency()
        if latency > 100:  # ms
            alerts.append(f'WARNING: 信号延迟 {latency}ms')
            
        # 发送告警
        for alert in alerts:
            self.send_feishu(alert)
```

## 4. 日志聚合

### 4.1 Loki（轻量日志系统）

```
类似 Prometheus 的日志聚合：
  Prometheus 负责指标（数字）
  Loki 负责日志（文本）

Grafana 统一展示指标 + 日志
```

```yaml
# docker-compose 中的 Loki
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"
  
  promtail:  # 日志收集器
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log
      - ./promtail.yaml:/etc/promtail/promtail.yaml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
```

### 4.2 结构化日志（JSON 格式）

```python
import structlog

# 配置结构化的 JSON 日志
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()

# 使用
logger.info("signal_computed", 
    strategy="bollinger",
    direction="buy",
    latency_ms=12,
    price=10.45
)

logger.warning("position_alert",
    position_id=5,
    pnl=-850,
    reason="stop_loss_approaching"
)
```

日志输出示例：

```json
{"timestamp": "2026-05-17T19:35:00Z", "level": "info", 
 "event": "signal_computed", "strategy": "bollinger", 
 "direction": "buy", "latency_ms": 12, "price": 10.45}
```

## 5. Windows 上的监控方案

对当前 Windows 5070Ti 环境：

```
轻量方案（当前适用）：
  日志 → 结构化 JSON → D:\kai_knowledge\library\ 作为日志仓库
  监控 → heartbeat_isolated 每 30 分钟检测
  告警 → 飞书 webhook

进阶方案（需要时可上）：
  Windows Exporter → Prometheus（WSL 中）→ Grafana
  Loki + Promtail → 日志搜索
```

## 总结

```
监控四层：
  infra → app → business → alert

工具链：
  Prometheus（指标）+ Grafana（展示）+ Loki（日志）
  prometheus_client（Python SDK）
  Alertmanager（告警路由）

量化核心指标：
  ✅ 信号延迟（Histogram - P95/P99）
  ✅ 信号频率（Counter - rate/5m）
  ✅ 持仓盈亏（Gauge）
  ✅ 回测状态（Gauge - 成功/失败）

当前最佳：
  轻量级告警（Python + 飞书 webhook）
  待需要时升级 Prometheus + Grafana
```
