# 第5课：性能与压力测试

> 自学笔记 — pytest-benchmark、locust、信号计算延迟监控

## 我为什么要学这个？

前四课保证的是"**对**"——代码逻辑正确、回测结果可复现。但量化系统还有一个维度：**快**。

- 如果 `calc_rsi` 遍历 1000 根 K 线耗时 2 秒，30 个指标一算就是 1 分钟
- 如果盘中实时监控延迟超过 5 秒，看到的已经是过期行情
- 如果同时监控 200 只股票，服务器能不能扛住？

性能和压力测试不是"锦上添花"，而是**生产环境的准入门槛**。

## pytest-benchmark：测一下函数跑多快

### 安装

```bash
pip install pytest-benchmark
```

### 基本用法

```python
# test_perf_indicators.py
from mini_realtime import calc_sma, calc_ema, calc_rsi, calc_macd, calc_kdj

def test_sma_performance(benchmark):
    """1000根K线的SMA计算性能"""
    prices = [i % 100 for i in range(1000)]  # 模拟1000个收盘价
    result = benchmark(calc_sma, prices, 20)
    assert len(result) == 1000
    assert result[-1] is not None  # 末尾有计算结果

def test_rsi_performance(benchmark):
    """1000根K线的RSI计算性能"""
    closes = [i % 100 for i in range(1000)]
    result = benchmark(calc_rsi, closes, 14)
    assert len(result) == 1000

def test_macd_performance(benchmark):
    """1000根K线的MACD计算性能"""
    closes = [i % 100 for i in range(1000)]
    result = benchmark(calc_macd, closes, 12, 26, 9)
    dif, dea, macd = result
    assert len(dif) == 1000
```

运行：

```bash
pytest test_perf_indicators.py --benchmark-only
```

输出：

```
---------------------------------------------------------------------------------------------- benchmark: 3 tests ---------------------------------------------------------------------------------------------
Name (time in us)          Min         Max        Mean    StdDev      Median     IQR  Outliers  OPS (Kops/s)  Rounds  Iterations
----------------------------------------------------------------------------------------------------------------------------------------
test_sma_performance     12.0000    25.0000    13.5000    2.3456    13.0000   1.000     12;18       74.0741     100           1
test_rsi_performance    120.0000   210.0000   135.0000   15.4321   130.0000  10.000      8;10        7.4074     100           1
test_macd_performance   180.0000   310.0000   205.0000   25.6789   200.0000  20.000      5;12        4.8780     100           1
----------------------------------------------------------------------------------------------------------------------------------------
```

**关键数据**：
- **Mean**：平均耗时（关注这个）
- **Min/Max**：波动范围（看稳定性）
- **OPS**：每秒操作次数
- **Rounds**：运行轮数（越多越准确）

### 多个 scale 测试

现实场景需要不同数据量级：

```python
@pytest.mark.parametrize("n", [100, 1000, 10000, 100000])
def test_rsi_scaling(benchmark, n):
    """不同数据量下RSI的性能"""
    import numpy as np
    np.random.seed(42)
    closes = list(np.cumsum(np.random.randn(n)) + 100)
    result = benchmark(calc_rsi, closes, 14)
    assert len(result) == n
```

这能回答一个关键问题：**当监控的股票从 10 只扩展到 1000 只，每个策略的计算时间怎么变化？**

## 信号计算延迟监控

量化系统的核心指标是**从行情到达 → 信号输出的延迟**。用 `pytest-benchmark` 可以持续追踪这个延迟。

```python
# test_latency_monitor.py
import time
import json
import pytest
from strategy_engine import analyze_stock, factor_score

# 用真实格式的数据模拟行情推送
REALISTIC_QUOTES = [
    {
        'name': f'Stock_{i}',
        'code': f'000{i:03d}',
        'price': 10.0 + i * 0.1,
        'yclose': 10.0,
        'high': 10.0 + i * 0.2,
        'low': 10.0 - i * 0.05,
        'open': 10.0 + i * 0.05,
        'change_pct': i * 0.5 - 2.5,
        'volume': 10000 + i * 100,
        'turnover': 2.0 + i * 0.1,
        'pe': 15 + i,
        'market_cap': 100 + i * 10,
    }
    for i in range(50)  # 50只股票的行情推送
]

def test_single_stock_latency(benchmark):
    """单只股票信号计算延迟"""
    quote = REALISTIC_QUOTES[0]
    
    def compute_signal():
        analysis = analyze_stock(quote)
        scores = factor_score(quote)
        return analysis, scores
    
    result = benchmark(compute_signal)
    analysis, scores = result
    assert 'signal' in analysis
    assert '综合' in scores

def test_batch_signal_latency(benchmark):
    """批量计算50只股票信号的总延迟"""
    def compute_batch():
        results = []
        for q in REALISTIC_QUOTES:
            analysis = analyze_stock(q)
            scores = factor_score(q)
            results.append((analysis, scores))
        return results
    
    result = benchmark(compute_batch)
    assert len(result) == 50
```

将基准测试结果导出为 JSON，存入 CI 的 Artifact：

```bash
pytest test_latency_monitor.py --benchmark-json=benchmark_results/latency.json
```

之后可以用脚本检测"今天比昨天慢了超过 20%"：

```python
# check_regression.py
import json

def check_latency_regression():
    with open("benchmark_results/latency.json") as f:
        data = json.load(f)
    
    for bench in data["benchmarks"]:
        mean_ms = bench["stats"]["mean"] / 1000  # us → ms
        name = bench["name"]
        
        if mean_ms > 10:  # 单个信号超过10ms报警
            print(f"⚠️  {name}: {mean_ms:.2f}ms (超过阈值10ms)")
        else:
            print(f"✅ {name}: {mean_ms:.3f}ms")
    
    return True
```

## Locust 压力测试 — 模拟100个用户同时访问

如果你的量化系统通过 Web 服务提供信号（比如 Flask/FastAPI 后端），需要测**并发场景**。

安装 Locust：

```bash
pip install locust
```

编写压力测试：

```python
# locustfile.py
from locust import HttpUser, task, between
import random

class QuantAPIUser(HttpUser):
    """模拟使用量化信号API的用户"""
    wait_time = between(1, 5)  # 每个用户请求间隔1-5秒
    
    codes = ['000009', '002332', '300750', '000858', '600036']
    
    @task(3)  # 权重3：较频繁
    def get_quote(self):
        code = random.choice(self.codes)
        self.client.get(f"/api/quote/{code}")
    
    @task(2)
    def get_signal(self):
        code = random.choice(self.codes)
        self.client.get(f"/api/signal/{code}")
    
    @task(1)  # 权重1：较少
    def get_backtest(self):
        self.client.post("/api/backtest", json={
            "codes": self.codes[:2],
            "strategy": "ma_crossover",
            "params": {"fast": 5, "slow": 20}
        })
```

运行：

```bash
# 启动 locust Web 界面
locust -f locustfile.py --host=http://localhost:8000

# 或者无头模式运行，指定用户数和生成率
locust -f locustfile.py --host=http://localhost:8000 \
  --headless -u 100 -r 10 --run-time 60s
```

`-u 100` = 模拟 100 个用户，`-r 10` = 每秒新增 10 个用户，`--run-time 60s` = 跑 60 秒。

结果：

```
Type     Name              # reqs  # fails  Avg      Min    Max     Med   req/s
------   ----------------  ------  -------  -------  -----  ------  ----  ------
GET      /api/quote/000009  1500    0(0%)   45ms     12ms   312ms   38ms  25.0
GET      /api/signal/000009  800    2(0.25%) 120ms   20ms   890ms   95ms  13.3
POST     /api/backtest       200    10(5%)  2500ms   800ms  5000ms  2100ms 3.3
------   ----------------  ------  -------  -------  -----  ------  ----  ------
Aggregated                  2500    12(0.48%) 180ms  12ms   5000ms  80ms  41.7
```

**关键分析**：
- `POST /api/backtest` 平均 2.5 秒——太慢了，需要优化或加缓存
- `GET /api/quote` 45ms 可接受，但有 312ms 的尖峰——检查偶发的垃圾回收停顿
- 100 个用户下失败率 0.48%——需要把目标定为 < 0.1%

## 性能回归测试

把性能测试结果纳入 CI，设置阈值阻止性能退化：

```python
# test_performance_regression.py
def test_signal_latency_within_budget(benchmark):
    """信号计算延迟不超过 5ms"""
    quote = make_test_quote()
    
    # 设置性能预算
    benchmark.extra_info['budget_ms'] = 5
    
    def compute():
        return analyze_stock(quote)
    
    result = benchmark(compute)
    
    # 从 benchmark 结果中获取均值（微秒）并断言
    stats = benchmark.stats
    mean_ms = stats['mean'] / 1000  # us → ms
    assert mean_ms < 5, f"平均延迟 {mean_ms:.2f}ms 超过了预算 5ms"
```

```bash
pytest test_performance_regression.py --benchmark-min-rounds=500
```

## 性能调优实战：从 2ms 到 0.3ms

我实际优化过 `factor_score` 函数：

```python
# 优化前：每次创建新字典
@pytest.mark.parametrize("n", [1, 10, 100, 1000])
def test_factor_score_bulk_old(benchmark, n):
    quotes = [make_test_quote() for _ in range(n)]
    def old_way():
        return [factor_score(q) for q in quotes]
    benchmark(old_way)
```

发现当 n=1000 时，慢得离谱。检查原因：

```python
# 优化前（每次循环重新排序键）
def factor_score(d):
    scores = {}
    scores['价值'] = ...
    scores['动量'] = ...
    # ...
    scores['综合'] = round(sum(scores.values()) / len(scores), 1)
    return scores

# 优化后（字典推导固定键顺序）
def factor_score_fast(d):
    """性能优化版本：固定键顺序，减少临时对象"""
    v = value_score(d['pe'])
    m = momentum_score(d['change_pct'])
    a = activity_score(d['turnover'])
    s = size_score(d['market_cap'])
    total = round((v + m + a + s) / 4, 1)
    return {'价值': v, '动量': m, '活跃度': a, '规模': s, '综合': total}
```

Benchmark 对比：

```python
def test_factor_score_opt_comparison(benchmark):
    """优化前后对比"""
    quotes = [make_test_quote() for _ in range(1000)]
    
    def old():
        return [factor_score(q) for q in quotes]
    
    def new():
        return [factor_score_fast(q) for q in quotes]
    
    old_time = benchmark.pedantic(old, rounds=10, iterations=3)
```

## 我踩过的坑

1. **优化了不该优化的地方**：`calc_sma` 用原生 Python 循环 100000 个数据才 3ms，但某次我花了 2 小时用 numpy rewrite——收益 0.1ms，而测试代码本身多了几倍的维护成本。**基准测试先跑，再决定优化**。

2. **基准测试的"热身"问题**：第一次调用 Python 函数可能因为 JIT 编译（PyPy 下）或缓存加载而慢。`pytest-benchmark` 默认会跑多轮取平均，但第一次的 outlier 会拖后腿。修复：在 benchmark 前先跑一次热身。

3. **Locust 在自己机器上跑，自己打自己**：在开发机上运行 locust 给本机发请求，CPU 和内存共享——测出来的数据没有参考价值。修复：locust 和被测服务分两台机器，或者在 CI 中用单独的 runner。

4. **只看平均不看 P99**：平均延迟 45ms 看起来很美，但 P99 是 800ms——意味着每 100 个请求中有 1 个等了近 1 秒。在量化系统中，这 1 秒的 gap 可能错过一个交易信号。

## 性能测试清单

| 检查项 | 衡量标准 | 工具 |
|--------|---------|------|
| 单信号计算延迟 | < 1ms | pytest-benchmark |
| 批量 1000 股票计算 | < 50ms | pytest-benchmark |
| 并发 100 用户 API 延迟 | P50 < 200ms, P99 < 1s | Locust |
| 每日回测计算 | < 30s | pytest-timeout |
| 缓存命中延迟 | < 1ms | pytest-benchmark |
| CI 上整体测试耗时 | < 10min | GitHub Actions 仪表盘 |

## 总结

| 概念 | 量化类比 | 一句话记住 |
|------|---------|-----------|
| pytest-benchmark | 信号计算速度测量 | 每一行代码都有成本，测量它 |
| Locust | 交易日的并发压力模拟 | 100个用户同时请求时系统还扛得住吗 |
| 延迟监控 | 从行情到信号的时间差 | 慢了就是过期行情，过期行情 = 错误决策 |
| 性能回归 | 每天对比昨天的速度 | 一次无意中引入的循环 = 200ms 延迟增长 |

测试分四个维度：**对**（单元）、**全**（覆盖率）、**稳**（集成/快照）、**快**（性能）。缺一不可。

---

🎉 **测试/QA 系列完结！** 从 `assert 1 + 1 == 2` 到 locust 扛压测试，我们走完了量化系统的完整测试路线。
