# DevOps #5：日志聚合与分析

> 2026-05-17
> 前置：监控与告警 #4

## 1. 日志体系设计

### 1.1 日志层次

```
DEBUG     → 开发调试（本地环境）
INFO      → 正常运行状态（可追踪业务路径）
WARNING   → 不影响运行但需要注意（延迟偏高、参数异常）
ERROR     → 功能受损（信号计算失败、网络超时）
CRITICAL  → 系统不可用（内存溢出、进程崩溃）

量化系统的日志分层：
  INFO:
    "信号生成: 布林带, 买入, 价格 10.45, 延迟 12ms"
    "回测开始: 策略 5组, 数据 10年, 参数 30个"
  
  WARNING:
    "行情延迟偏高: 当前 850ms (阈值 500ms)"
    "信号频率异常: 过去 5分钟 0条 (平滑模式 3条/分钟)"
  
  ERROR:
    "数据源连接失败: qt.gtimg.cn, 重试 3 次后放弃"
    "策略引擎崩溃: signal_compute, OOM"
  
  CRITICAL:
    "实盘连接断开: 交易所 WebSocket 断开 > 60秒"
```

### 1.2 日志文件轮转

```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'logs/quant.log',
    maxBytes=10*1024*1024,     # 10MB
    backupCount=5,              # 保留 5 个备份
    encoding='utf-8'
)

# 按天轮转（更适合量化日志）
from logging.handlers import TimedRotatingFileHandler

daily_handler = TimedRotatingFileHandler(
    'logs/quant.log',
    when='midnight',            # 每天午夜轮转
    interval=1,
    backupCount=30,             # 保留 30 天
    encoding='utf-8'
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        daily_handler,
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
```

### 1.3 JSON 结构化日志（可搜索）

```python
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 如果有额外字段（extra）
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
        return json.dumps(log_entry)

# 使用
logger = logging.getLogger('quant.monitor')
logger.info("signal_computed", extra={
    "extra": {
        "strategy": "bollinger",
        "direction": "buy",
        "latency_ms": 12
    }
})
```

## 2. ELK Stack

Elasticsearch + Logstash + Kibana——业界标准的日志方案：

```
量化系统 → Logstash（解析+过滤） → Elasticsearch（存储+索引） → Kibana（搜索+可视化）
```

### 2.1 Filebeat（轻量日志采集器）

```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  paths:
    - /app/logs/*.log
  multiline:
    pattern: '^\d{4}-\d{2}-\d{2}'
    negate: true
    match: after

output.elasticsearch:
  hosts: ["localhost:9200"]
  index: "quant-logs-%{+yyyy.MM.dd}"

# 资源占用很小（~20MB 内存），适合和量化引擎共存在同一台机器
```

### 2.2 Elasticsearch 索引

```json
// 日志存储后，可以按字段搜索
GET /quant-logs-2026.05.17/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "strategy": "bollinger" } },
        { "range": { "latency_ms": { "gt": 50 } } }
      ]
    }
  },
  "sort": [{ "@timestamp": "desc" }]
}
```

### 2.3 日志查询的有效模式

```
Kibana 快速诊断：

问题 "今天信号延迟为什么变高了？"
  1. latency_ms > 100, 时间 = today
  2. 看到全都是下午 3:00-3:30 的布林带信号
  3. 再查这段时间的 CPU 使用率 → 冲突合并占用大量资源
  4. 结论：布林带合并日程和信号计算撞上了

问题 "策略引擎崩溃过吗？"
  搜索 level: ERROR OR level: CRITICAL, 时间 = last 7d
```

## 3. Loki（轻量级替代 ELK）

Grafana Loki 是 ELK 的轻量替代——只索引 metadata，不索引 log body。

```yaml
services:
  loki:
    image: grafana/loki:3.0
    command: -config.file=/etc/loki/config.yaml
    volumes:
      - ./loki-config.yaml:/etc/loki/config.yaml
      - loki-data:/loki
    ports:
      - "3100:3100"

  promtail:
    image: grafana/promtail:3.0
    volumes:
      - ./logs:/var/log/quant
      - ./promtail.yaml:/etc/promtail/promtail.yaml
    command: -config.file=/etc/promtail/promtail.yaml

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_PATHS_PROVISIONING=/etc/grafana/provisioning
    ports:
      - "3000:3000"
```

优势：资源占用远小于 ELK，适合量化引擎的单机或小集群部署。

## 4. 量化日志的最佳实践

### 4.1 关键事件日志

```python
# 每次交易都记录（可追溯）
def execute_trade(order: Order):
    logger.info("trade_executed", extra={
        "trade_id": order.id,
        "strategy": order.strategy,
        "symbol": order.symbol,
        "direction": order.direction,
        "price": order.price,
        "volume": order.volume,
        "total": order.price * order.volume,
        "timestamp": datetime.now().isoformat()
    })
```

### 4.2 异常追踪

```python
def compute_signal(prices: np.ndarray):
    try:
        result = strategy.bollinger(prices)
        if result is None:
            logger.error("bollinger_compute_failed", extra={
                "prices_len": len(prices),
                "strategy_state": strategy.dump_state()
            })
        return result
    except Exception as e:
        logger.exception("signal_compute_crash", extra={
            "strategy": strategy.name,
            "prices_len": len(prices)
        })
        raise
```

## 5. D 盘日志仓库

当前系统已经自动同步日志到 `D:\kai_knowledge\library\`：

```python
# 自动归档日志到 D 盘
class DailyLogSync:
    def __init__(self):
        self.src = "memory/daily/"
        self.dst = "D:\\kai_knowledge\\library\\"
    
    def sync(self):
        today = datetime.now().strftime("%Y-%m-%d")
        src_file = f"{self.src}{today}.md"
        if os.path.exists(src_file):
            shutil.copy2(src_file, self.dst)
            logger.info(f"日志已归档: {today}.md → D 盘")
```

## 总结

```
日志 = 可追溯的系统记录，不是噪声

分层管理：
  DEBUG → 开发环境
  INFO  → 业务追踪（信号、交易、回测）
  WARNING → 潜在问题
  ERROR → 功能受损
  CRITICAL → 不可用

工具选择：
  轻量（当前）：结构化 JSON + D 盘日志仓库 + 飞书告警
  中等（推荐）：Loki + Grafana
  重量（团队）：ELK Stack

关键日志点：
  每次信号生成（可回溯策略行为）
  每次交易执行（可审计）
  每次异常（可快速定位）
  每分钟心跳（确认系统存活）
```
