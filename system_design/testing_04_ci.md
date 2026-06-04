# 第4课：CI 集成测试

> 自学笔记 — 多组件测试、行情模拟、快照测试

## 我为什么要学这个？

前三课都在讲「怎么测试」。但有一个问题：**谁来保证每次代码合并前都跑了一次测试？**

人肉记忆是世界上最不靠谱的东西。写了测试不跑 = 没写测试。CI（持续集成）就是那个"自动帮你跑测试的机器人门卫"：每次 git push，它自动拉代码、装依赖、跑所有测试，挂了就拦住。

## CI 的基本流程（以 GitHub Actions 为例）

```yaml
# .github/workflows/quant_tests.yml
name: Quant Trading Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov pytest-benchmark
          pip install -r requirements.txt
          # 量化系统特有依赖
          pip install pandas numpy

      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ \
            --cov=finance \
            --cov-report=term-missing \
            --cov-fail-under=80 \
            -v

      - name: Run backtest regression tests
        run: |
          pytest tests/regression/ -v --tb=short

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report-${{ matrix.python-version }}
          path: htmlcov/
```

把这个文件放到 `.github/workflows/` 下，每次 git push 就会自动触发。

## 多组件测试 — 量化系统的组件依赖

量化系统通常由几个组件构成：

```
行情获取 (TencentStockAPI) 
    → 技术指标计算 (calc_sma, calc_rsi, calc_macd)
        → 信号生成 (analyze_stock, factor_score)
            → 策略执行 (AStockStrategies.ma_crossover_strategy)
                → 回测引擎 (AStockStrategies.backtest)
                    → 报告生成 (morning_report, closing_report)
```

集成测试不是测单个组件，而是测**组件间的连接**：

```python
# test_integration.py
"""集成测试：从行情到信号的完整链路"""
import pytest
from unittest.mock import patch
from strategy_engine import StockAPI, analyze_stock, factor_score

# mock 的行情数据 — 模拟腾讯 API 返回格式
MOCK_QUOTE = {
    '中国宝安': {
        'name': '中国宝安', 'code': '000009',
        'price': 10.5, 'yclose': 10.0, 'open': 10.2,
        'high': 10.8, 'low': 9.9, 'change_pct': 5.0,
        'volume': 80000, 'turnover': 3.2, 
        'pe': 18.5, 'market_cap': 150,
    }
}

def test_full_pipeline():
    """
    完整流水线测试：
    StockAPI.batch → analyze_stock → factor_score 的数据一致性
    """
    # 模拟 API 调用
    with patch.object(StockAPI, 'batch', return_value=MOCK_QUOTE):
        api = StockAPI()
        quote = api.batch(['sz000009'])
        
        stock_data = quote['中国宝安']
        assert stock_data['change_pct'] == 5.0  # API 数据正确解析
        
        # 信号分析
        analysis = analyze_stock(stock_data)
        assert analysis['signal'] == '📈 大涨'         # 5% ≥ 3%
        assert analysis['pos'] == '中位'                # (10.5-9.9)/(10.8-9.9)*100 ≈ 67，不到70
        
        # 多因子评分
        scores = factor_score(stock_data)
        assert scores['综合'] > 50                     # 正常股票综合分应>50
        assert scores['价值'] > 80                     # PE=18.5，在0-20区间
        assert scores['动量'] > 70                     # 5%涨幅
```

## 行情模拟 — 别让网络决定测试成败

集成测试最大的敌人是**外部依赖**。腾讯行情 API 有频率限制、有停机维护、有返回格式变化。这些都不应该让测试失败。

策略：**分层 Mock**。

### 第一层：在单元测试中完全 mock

```python
# 测试 analyze_stock 自身逻辑，完全不依赖 API
def test_analyze_with_fake_data():
    d = make_fake_quote(price=10.0, change_pct=2.0)
    assert analyze_stock(d)['signal'] == '🟢 上涨'
```

### 第二层：在集成测试中用 fixture 缓存的真实数据

```python
@pytest.fixture(scope="session")
def real_cached_data():
    """用真实数据但只抓一次，后续用缓存"""
    import json, os
    cache_file = ".test_cache/000009_quote.json"
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)
    # 第一次跑时抓取
    from mini_realtime import TencentStockAPI
    api = TencentStockAPI()
    data = api.get_quote('000009')
    os.makedirs(".test_cache", exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(data, f)
    return data

def test_real_data_processing(real_cached_data):
    """用缓存过的真实数据测试处理链路"""
    result = analyze_stock(real_cached_data)
    assert 'signal' in result
    assert 'pos' in result
```

### 第三层：E2E 测试标记为手动运行

```python
@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("RUN_E2E"), 
                    reason="需要设置 RUN_E2E=1 才运行")
def test_e2e_live_api():
    """端到端：真的去拉腾讯API"""
    from mini_realtime import TencentStockAPI
    api = TencentStockAPI()
    quotes = api.batch_quote(['000009', '002332'])
    assert len(quotes) == 2
    assert all(q['price'] > 0 for q in quotes.values())
```

## 快照测试（Snapshot Testing）— 把报告"拍下来"

量化系统的输出往往是文本报告（`morning_report`、`closing_report`）。内容复杂、格式化字符串多，手写断言验证每个细节太累。

快照测试的思路：第一次运行时把输出存为文件（"快照"），后续运行和快照比对。如果变化是有意的，手动更新快照。

Python 中用 `syrupy` 实现：

```bash
pip install syrupy
```

```python
# test_report_snapshot.py
def test_morning_report_snapshot(mock_stock_api, snapshot):
    """早报快照测试"""
    from strategy_engine import morning_report
    
    report = morning_report(mock_stock_api)
    
    # syrupy 会自动创建/比对快照
    assert report == snapshot
```

第一次运行，`syrupy` 在 `__snapshots__/` 目录下生成快照文件。第二次运行如果输出变了：

```
这是一个新的输出，与快照不同…
─────────────────
@@ -2,6 +2,6 @@
 🕐 2026-05-17 09:30

 📈 大盘
-🟢 上证: 3350.21 (+0.15%)
+🟢 上证: 3350.50 (+0.18%)
```

看到变化后，如果这是预期的（因为 mock 数据变了？），更新快照：

```bash
pytest --snapshot-update
```

**快照测试像什么？** 就像每天收盘时的截图——你不需要检查每个像素，但一眼就能看出今天和昨天不一样的地方。

## 模拟行情变化 — 盘中突发场景测试

行情是动态的。集成测试也要覆盖盘中变化：

```python
# test_market_scenarios.py
import pytest

SCENARIOS = {
    "正常开盘": {
        "price": 10.0, "yclose": 10.0, "high": 10.2, "low": 9.9,
        "change_pct": 0.2, "volume": 50000,
    },
    "盘中拉涨": {
        "price": 10.6, "yclose": 10.0, "high": 10.8, "low": 9.8,
        "change_pct": 6.0, "volume": 200000,
    },
    "尾盘跳水": {
        "price": 9.5, "yclose": 10.0, "high": 10.1, "low": 9.3,
        "change_pct": -5.0, "volume": 180000,
    },
    "无量跌停": {
        "price": 9.0, "yclose": 10.0, "high": 9.0, "low": 9.0,
        "change_pct": -10.0, "volume": 1000,
    },
    "停牌归来": {
        "price": 11.0, "yclose": 9.0, "high": 12.0, "low": 10.5,
        "change_pct": 22.22, "volume": 50000,
    },
}

@pytest.mark.parametrize("scenario_name,data", SCENARIOS.items())
def test_market_scenarios(scenario_name, data):
    """各种行情场景下的信号表现"""
    from strategy_engine import analyze_stock
    
    result = analyze_stock(data)
    assert 'signal' in result, f"{scenario_name}: 缺少signal"
    assert 'pos' in result, f"{scenario_name}: 缺少position"
    assert 'support' in result, f"{scenario_name}: 缺少support"
    
    # 跌停时 position 应该是低位
    if data['change_pct'] <= -10:
        assert result['pos'] == '低位', f"{scenario_name}: 跌停应在低位"
    
    # 大幅跳空时应该有缺口标记
    if abs(data['change_pct']) > 20:
        assert result['gap_up'] or result['gap_down'], f"{scenario_name}: 大幅跳空应有缺口"
```

## CI 中的超时与资源控制

集成测试比单元测试慢。慢的后果是开发体验变差、CI 排队时间变长。

```python
@pytest.mark.timeout(30)  # 超过30秒就失败
def test_large_backtest():
    """大数据量回测，但30秒内必须完成"""
    df = pd.read_parquet("tests/fixtures/1000_days.parquet")
    result = AStockStrategies.backtest(df, AStockStrategies.ma_crossover_strategy)
    assert result["trade_count"] > 0
```

在 CI 中把测试分层：

```yaml
# CI Step 1: 单元测试（快速）
- run: pytest tests/unit/ --timeout=10 -v

# CI Step 2: 集成测试（中等）
- run: pytest tests/integration/ --timeout=60 -v

# CI Step 3: 慢速测试（可选）
- run: pytest tests/slow/ --timeout=300 -v --run-slow
  if: github.ref == 'refs/heads/main'
```

## 我踩过的坑

1. **CI 和本地环境不一致**：本地 Windows 跑绿了，CI 的 Ubuntu 上挂了——原因是路径分隔符 `\` vs `/`。修复：用 `os.path.join` 或 `pathlib.Path`。

2. **快照太频繁**：`syrupy` 默认对每个测试函数的字符串输出做快照。`morning_report` 里带时间戳，每次 CI 跑都触发快照变更。修复：把时间戳抽出去，只快照数据部分。

3. **E2E 测试在 CI 上永远挂**：腾讯 API 在 CI 环境（海外服务器）可能被墙。修复：加 `@pytest.mark.skipif` 条件，只在有网络标记的环境运行。

## 总结

| 概念 | 量化类比 | 一句话记住 |
|------|---------|-----------|
| CI Pipeline | 自动化的开盘前检查 | 每次 git push 自动跑全套测试 |
| 行情模拟 | 不依赖真实行情的测试数据 | 三层 mock：单元 mock → 集成缓存 → E2E 标记 |
| 快照测试 | 每天收盘后的固定截图 | 把报告"拍下来"，只关注变化 |
| 场景测试 | 各种市场环境下的策略表现 | 暴涨/暴跌/停牌/无量，每个场景一个测试用例 |

集成测试的价值不是「所有测试都绿了」那一瞬间，而是「昨晚同事改了行情解析代码，今早 CI 告诉我 `analyze_stock` 还能正常工作」的那份安心。

下一步：测试跑得对很好，但**跑得快**也很重要。看第5课。
