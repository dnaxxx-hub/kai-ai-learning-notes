# 第3课：回测验证测试

> 自学笔记 — 给定输入 → 期望输出，数据驱动测试，回归基线比对

## 我为什么要学这个？

单元测试验证了单个函数（如 `analyze_stock`）的正确性。但量化系统真正的核心是**回测引擎**：给定一段历史行情，策略应该产生什么样的交易信号？买入点和卖出点对不对？收益率对不对？

我之前遇到过：回测跑了 3 年，年化 25%，很开心。结果发现代码里有个 bug——信号当天买入变成了信号后一天买入，所有收益都是"未来数据"作弊来的。**回测测试就是抓这种 bug 的。**

## 数据驱动测试（DDT）— 把测试当数据表写

回测测试天然适合数据驱动：输入是一段行情数据，输出是期望的信号序列。把这些写成表格，pytest 自动生成用例。

```python
# test_backtest.py
import pytest
import pandas as pd
import numpy as np

# ---------- 数据驱动 ------------------
BACKTEST_CASES = [
    {
        "name": "MA金叉买入信号",
        "klines": [
            # date, open, close, high, low, volume
            ("2026-01-06", 10.0, 10.2, 10.3, 9.9, 10000),
            ("2026-01-07", 10.2, 10.1, 10.3, 10.0, 12000),
            ("2026-01-08", 10.1, 10.3, 10.4, 10.0, 11000),
            ("2026-01-09", 10.3, 10.5, 10.6, 10.2, 13000),
            ("2026-01-10", 10.5, 10.7, 10.8, 10.4, 15000),
        ],
        "strategy": "ma_crossover",
        "params": {"fast": 3, "slow": 5},  # 手动调小窗口确保有信号
        "expected_signals": [
            # 最后一个交易日应该有买入信号（MA3 > MA5）
            # 这里只验证最后一行
            {"position_change": 1, "at_index": -1},  
        ],
    },
    {
        "name": "RSI超卖买入信号",
        "klines": [
            ("2026-01-06", 10.0, 10.0, 10.1, 9.9, 10000),
            ("2026-01-07", 10.0, 9.5, 10.1, 9.4, 15000),
            ("2026-01-08", 9.5, 9.0, 9.6, 8.9, 20000),
            ("2026-01-09", 9.0, 8.8, 9.1, 8.7, 18000),
            ("2026-01-10", 8.8, 8.7, 8.9, 8.6, 16000),
            ("2026-01-13", 8.7, 8.5, 8.8, 8.4, 19000),
            ("2026-01-14", 8.5, 8.6, 8.7, 8.4, 14000),
        ],
        "strategy": "rsi_strategy",
        "params": {"period": 5, "overbought": 70, "oversold": 30},
        "expected_signals": [
            {"type": "buy", "at_index": -1},  # 连续下跌后 RSI 应该 < 30
        ],
    },
]
```

然后测试函数遍历这些用例：

```python
@pytest.mark.parametrize("case", BACKTEST_CASES, ids=[c["name"] for c in BACKTEST_CASES])
def test_backtest_strategy(case):
    """数据驱动回测验证"""
    from astock_strategies import AStockStrategies
    
    # 构建 DataFrame
    df = pd.DataFrame(case["klines"], 
                      columns=["date", "open", "close", "high", "low", "volume"])
    df.set_index("date", inplace=True)
    
    # 运行策略
    strategy = getattr(AStockStrategies, case["strategy"])
    result = strategy(df, **case["params"])
    
    # 验证信号
    for exp in case["expected_signals"]:
        idx = exp["at_index"]
        if "position_change" in exp:
            # 验证 position 字段的变化
            assert result["position"].iloc[idx] == exp["position_change"], \
                f"{case['name']}: 期望 position[{idx}]={exp['position_change']}, 实际={result['position'].iloc[idx]}"
        if exp.get("type") == "buy":
            assert result["signal"].iloc[idx] == 1
```

## 回归基线比对 — 用黄金文件锁定结果

数据驱动测试验证信号的"方向"（是买入还是卖出）。但更细粒度的需求是：**每次改代码后，回测结果（年化收益、夏普比率、最大回撤）应该保持不变。**

这就需要用**回归基线（Regression Baseline）**。

步骤：
1. 第一次跑回测，把结果存为 JSON 文件（"黄金文件"）
2. 后续每次修改后跑测试，比较当前结果与黄金文件
3. 如果结果变了，测试失败——必须确认是预期变化还是 bug

```python
# regression_tests.py
import pytest
import json
import os
import pandas as pd
from astock_strategies import AStockStrategies

BASELINE_DIR = "baselines"

def load_baseline(name):
    path = os.path.join(BASELINE_DIR, f"{name}.json")
    if not os.path.exists(path):
        pytest.skip(f"基线文件不存在: {path}")
    with open(path) as f:
        return json.load(f)

def save_baseline(name, data):
    os.makedirs(BASELINE_DIR, exist_ok=True)
    path = os.path.join(BASELINE_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_backtest(strategy_func, klines, **strategy_params):
    """运行一次回测并返回关键指标"""
    df = pd.DataFrame(klines, 
                      columns=["date", "open", "close", "high", "low", "volume"])
    result = AStockStrategies.backtest(df, strategy_func, 
                                       initial_capital=10000, 
                                       commission=0.0003)
    return {
        "total_return": round(result["total_return"], 4),
        "sharpe_ratio": round(result["sharpe_ratio"], 4),
        "max_drawdown": round(result["max_drawdown"], 4),
        "trade_count": result["trade_count"],
        "win_rate": round(result["win_rate"], 4),
    }

# ---------- 测试数据 ----------

SAMPLE_60D_KLINES = [
    # 这里放真实股票 60 个交易日的 K线数据
    # 为了简洁，只展示结构，实际使用真实数据
]

def test_ma_crossover_regression():
    """MA金叉死叉策略回归验证"""
    from astock_strategies import AStockStrategies.ma_crossover_strategy
    
    baseline = load_baseline("ma_crossover_60d")
    result = run_backtest(
        AStockStrategies.ma_crossover_strategy,
        SAMPLE_60D_KLINES,
        fast=5, slow=20
    )
    
    for key in baseline:
        assert abs(result[key] - baseline[key]) < 0.001, \
            f"{key}: 基线={baseline[key]}, 当前={result[key]}, 差异>阈值"

def test_bollinger_regression():
    """布林带策略回归验证"""
    baseline = load_baseline("bollinger_60d")
    result = run_backtest(
        AStockStrategies.bollinger_strategy,
        SAMPLE_60D_KLINES,
        period=20, std=2
    )
    
    for key in baseline:
        assert abs(result[key] - baseline[key]) < 0.001
```

**更新基线**：当策略逻辑有意识变更时，运行：

```bash
python -c "from regression_tests import save_baseline, ...; save_baseline('ma_crossover_60d', run_backtest(...))"
```

**回归基线像什么？** 就像摄影里的"对焦锁定"——你调好了镜头（回测逻辑），锁定参数后每次微调都有参照。哪天不小心碰了调焦环（引入了 bug），拿基线一比较就发现了。

## 给定输入→期望输出：可复现的回测黄金三定律

### 第一定律：固定随机种子

回测中任何涉及"随机"的地方（比如蒙特卡洛模拟、随机参数生成），必须固定种子：

```python
import numpy as np

def test_backtest_deterministic():
    np.random.seed(42)
    result1 = run_backtest_with_random()
    
    np.random.seed(42)
    result2 = run_backtest_with_random()
    
    assert result1["total_return"] == result2["total_return"]
```

### 第二定律：固定数据样本

不要每次测试都去腾讯 API 拉数据。把一段历史数据固化在测试中或存为 CSV/Parquet：

```python
# conftest.py
@pytest.fixture(scope="session")
def fixed_klines():
    """仅加载一次，所有测试共享"""
    df = pd.read_csv("tests/fixtures/000009_60d.csv")
    return df
```

### 第三定律：浮点数比较用容差

股票价格、收益率都是浮点数。不同机器、不同 Python 版本的浮点运算可能有微小差异。

```python
# ❌ 不好
assert result["sharpe_ratio"] == 1.2345

# ✅ 好
assert result["sharpe_ratio"] == pytest.approx(1.2345, rel=1e-3)
```

## 实战：回测完整测试流水线

```python
def test_backtest_end_to_end():
    """
    端到端回测测试：
    1. 给定中国宝安 60 天历史数据
    2. 用 MA(5,20) 金叉死叉策略
    3. 期望最后 5 天内有一次买入信号
    """
    klines = pd.read_csv("tests/fixtures/000009_60d.csv")
    df = AStockStrategies.ma_crossover_strategy(klines, fast=5, slow=20)
    
    # 最后5天是否有信号
    last_5 = df.tail(5)
    buy_signals = last_5[last_5["position"] == 1]
    sell_signals = last_5[last_5["position"] == -1]
    
    # 至少有一个信号（无论是买还是卖），说明策略在活跃
    assert len(buy_signals) > 0 or len(sell_signals) > 0, \
        "MA策略在最后5天无任何信号，可能数据异常或策略失效"
    
    # 回测收益应为正
    result = AStockStrategies.backtest(klines, AStockStrategies.ma_crossover_strategy)
    assert result["total_return"] > -0.5, f"回测亏损超过50%: {result['total_return']:.2%}"
    assert result["trade_count"] > 0, "回测交易次数为0"
```

## 我踩过的坑

1. **未来数据泄露**：回测信号用了当天的收盘价 — `position_change > 0` 时买入，但判断条件依赖 `close - MA`，而 MA 计算用了当天收盘价——这就是未来数据。修复：用 `shift(1)` 让信号基于前一天的 MA 值。

2. **基线太敏感**：某次改了一行 `round(x, 4)` 变成 `round(x, 6)`，基线对比全挂了。修复：浮点数用 `pytest.approx(rel=1e-3)` 而不是精确相等。

3. **测试数据太"人工"**：手动构造的 K 线数据太理想化（每天涨 0.1%）。真实数据有停牌、涨跌停板。修复：用真实股票的历史 CSV 做 fixture，并在测试数据里加入停牌日。

4. **回测结果不能保证正向收益**：这是最容易犯的逻辑错误——测试里 assert 回测收益 > 0。回测收益应该是什么就是什么，不能因为"期望赚钱"就让它通过。正确做法：**对比基线值**。

## 总结

| 概念 | 量化类比 | 一句话记住 |
|------|---------|-----------|
| 数据驱动测试 | 策略参数表 | 把测试用例写成 K线数据 + 期望信号表格 |
| 回归基线 | 回测的"对比基准" | 锁定一份黄金结果，每次改代码后比对 |
| 未来数据检测 | 用前一天的信号做今天决策 | 信号永远 shift(1)，不碰未来信息 |
| 确定性问题 | 随机种子 + 固定数据 | 回测可以不是真的，但必须是可复现的 |

`run_backtest → 出结果 → 存基线 → 改代码 → 比对基线` 这个循环就是量化测试的核心节奏。

下一步：有了单元测试、覆盖率和回测验证，怎么把它们集成到持续集成中？看第4课。
