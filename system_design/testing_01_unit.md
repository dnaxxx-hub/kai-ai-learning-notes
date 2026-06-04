# 第1课：单元测试（pytest 实战）

> 自学笔记 — 量化系统的测试基础

## 我为什么要学这个？

在写 `strategy_engine.py` 时，我一直靠 "跑一遍看结果" 来验证。但行情数据每天变，今天看到 "大涨信号 ✅" 可能只是因为代码逻辑是对的，也可能只是恰好撞对。我需要一种方法：**每次改代码后，都能快速确认核心逻辑没坏**。这就是单元测试做的事。

## pytest 的核心三板斧

### 1. Fixture — 就像量化策略的"历史回测环境"

写测试之前要准备数据。在量化里，这相当于准备好一段历史行情数据，而不是每次都去腾讯接口拉实时的。

```python
# tests/conftest.py 或 test_signals.py

import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def sample_kline():
    """模拟5根日K线数据"""
    return pd.DataFrame({
        'date': ['2026-05-12', '2026-05-13', '2026-05-14', '2026-05-15', '2026-05-16'],
        'open': [10.0, 10.2, 10.1, 10.5, 10.3],
        'close': [10.2, 10.1, 10.5, 10.3, 10.6],
        'high': [10.3, 10.3, 10.6, 10.6, 10.8],
        'low': [9.9, 10.0, 10.1, 10.2, 10.2],
        'volume': [10000, 12000, 15000, 11000, 13000],
    })

@pytest.fixture
def mock_stock_api(monkeypatch):
    """模拟腾讯行情API，不真的发HTTP请求"""
    def fake_batch(self, symbols):
        return {
            '中国宝安': {
                'name': '中国宝安', 'code': '000009',
                'price': 10.5, 'yclose': 10.2,
                'open': 10.3, 'high': 10.8, 'low': 10.1,
                'change_pct': 2.94, 'volume': 50000,
                'pe': 15.0, 'turnover': 2.5, 'market_cap': 100,
            }
        }
    from strategy_engine import StockAPI
    monkeypatch.setattr(StockAPI, 'batch', fake_batch)
```

**Fixture 像什么？** 就像量化回测中固定的历史数据切片。你设置好一段行情，所有策略都在这段行情上跑，结果可复现。没有 fixture，你每次 `pytest` 都会去真实拉行情——测试就变成了看运气。

### 2. Mock — 把外部依赖"断网测试"

我的 `analyze_stock` 依赖 `StockAPI.batch()` 返回的字典。测试时我不想真的连腾讯服务器——那不叫单元测试，那叫集成测试。

用 `monkeypatch` 或 `unittest.mock` 可以"偷换"这个依赖：

```python
# test_signals.py

from strategy_engine import analyze_stock, factor_score

def test_analyze_stock_normal(mock_stock_api):
    """正常行情数据的分析结果"""
    d = mock_stock_api.batch(['sz000009'])['中国宝安']
    result = analyze_stock(d)
    
    assert result['signal'] == '🟢 上涨'  # 2.94% 在1%-3%区间
    assert result['pos'] == '中位'        # 日内位置在30-70之间
    assert result['gap_up'] == True       # 10.3 > 10.2*1.01 = 10.302，略跳空
    assert result['support'] == 10.1 * 0.98

def test_analyze_stock_yclose_zero():
    """昨收为0时的边缘情况"""
    d = {
        'price': 0, 'yclose': 0, 'high': 0, 'low': 0,
        'open': 0, 'change_pct': 0, 'volume': 0,
        'pe': 0, 'turnover': 0, 'market_cap': 0,
    }
    result = analyze_stock(d)
    assert result == {}  # yclose==0 直接返回空字典
```

**Mock 像什么？** 就像量化中的"Paper Trading"模拟盘——你假装有行情、假装下单、假装成交，但不碰真金白银。Mock 让测试跑得快、不依赖网络、结果可预测。

### 3. Parametrize — 一条测试用例跑遍所有场景

写量化时最烦的是：涨的测了，跌的测了，平盘的测了没？`@pytest.mark.parametrize` 就是干这个的——把输入和期望输出列成表格，pytest 自动生成多个测试案例。

```python
import pytest

@pytest.mark.parametrize("change_pct,expected_signal", [
    (5.0,  '📈 大涨'),   # >=3%
    (3.0,  '📈 大涨'),   # 边界
    (2.0,  '🟢 上涨'),   # >=1%
    (1.0,  '🟢 上涨'),   # 边界
    (0.5,  '⚪ 横盘'),   # >=-1%
    (-0.5, '⚪ 横盘'),
    (-1.0, '⚪ 横盘'),   # 边界
    (-2.0, '🔻 下跌'),   # >=-3%
    (-3.0, '🔻 下跌'),   # 边界
    (-5.0, '🔴 大跌'),   # <-3%
])
def test_signal_classification(change_pct, expected_signal):
    """涨跌幅信号分类的边界值全覆盖"""
    d = {
        'price': 10.0, 'yclose': 10.0, 'high': 10.2, 'low': 9.8,
        'open': 10.0, 'change_pct': change_pct, 'volume': 10000,
        'pe': 15, 'turnover': 2, 'market_cap': 100,
    }
    result = analyze_stock(d)
    assert result['signal'] == expected_signal
```

这段代码里 10 个输入，pytest 会生成 10 个独立的测试用例。如果第 5 个失败，其余 9 个照常运行，不会阻断。

**Parametrize 像什么？** 就像跑回测时遍历不同的参数组合（`fast=12, slow=26` vs `fast=14, slow=18`），一表打尽所有可能性。

## 完整可运行示例

把以下代码存为 `tests/test_quant_signals.py`：

```python
"""量化系统信号函数测试"""
import pytest
import sys
sys.path.insert(0, '..')

from strategy_engine import analyze_stock, factor_score

# ---------- Fixtures ----------

@pytest.fixture
def mock_bull_data():
    """多头行情模拟"""
    return {
        'price': 11.0, 'yclose': 10.0, 'high': 11.2, 'low': 9.9,
        'open': 10.3, 'change_pct': 10.0, 'volume': 100000,
        'pe': 18, 'turnover': 5, 'market_cap': 150,
    }

@pytest.fixture
def mock_bear_data():
    """空头行情模拟"""
    return {
        'price': 9.0, 'yclose': 10.0, 'high': 10.1, 'low': 8.9,
        'open': 9.8, 'change_pct': -10.0, 'volume': 80000,
        'pe': 25, 'turnover': 1.5, 'market_cap': 120,
    }

# ---------- analyze_stock 测试 ----------

@pytest.mark.parametrize("price,low,high,expected_pos", [
    (10.5, 10.0, 11.0, '中位'),  # (10.5-10)/(11-10)*100=50
    (10.8, 10.0, 11.0, '高位'),  # (10.8-10)/1*100=80
    (10.1, 10.0, 11.0, '低位'),  # (10.1-10)/1*100=10
])
def test_day_position(price, low, high, expected_pos):
    """日内位置判定"""
    d = {'price': price, 'yclose': 10.0, 'high': high, 'low': low,
         'open': 10.0, 'change_pct': 0, 'volume': 10000,
         'pe': 15, 'turnover': 2, 'market_cap': 100}
    result = analyze_stock(d)
    assert result['pos'] == expected_pos

# ---------- factor_score 测试 ----------

def test_factor_score_pe_zero():
    """市盈率为0时的评分"""
    d = {'pe': 0, 'turnover': 2, 'change_pct': 1, 'market_cap': 100}
    scores = factor_score(d)
    assert scores['价值'] == 30  # pe<=0给30分

def test_factor_score_pe_negative():
    """市盈率为负时的评分"""
    d = {'pe': -5, 'turnover': 2, 'change_pct': 1, 'market_cap': 100}
    scores = factor_score(d)
    assert scores['价值'] == 30

def test_factor_score_small_cap():
    """小市值加分"""
    d = {'pe': 15, 'turnover': 2, 'change_pct': 1, 'market_cap': 30}
    scores = factor_score(d)
    assert scores['规模'] == 80  # <50亿
    assert scores['综合'] > 50

def test_factor_score_large_cap():
    """大市值扣分"""
    d = {'pe': 15, 'turnover': 2, 'change_pct': 1, 'market_cap': 600}
    scores = factor_score(d)
    assert scores['规模'] == 30  # >=500亿

def test_comprehensive_score():
    """综合评分 = 各因子评分的算术平均"""
    d = {'pe': 15, 'turnover': 2, 'change_pct': 1, 'market_cap': 100}
    scores = factor_score(d)
    expected_avg = (60 + 55 + 70 + 60) / 4  # 见下表
    # 价值: 20<=pe<=50 → 60 - (15-20)*0.5 = 62.5 → wait, pe=15 < 20
    
    # 手动算一遍验证：
    # 价值: 0 < 15 < 20 → 80 + (20-15) = 85
    # 动量: 50 + 1*5 = 55
    # 活跃度: 1 < 2 < 5 → 70
    # 规模: 50 <= 100 < 200 → 60
    expected = round((85 + 55 + 70 + 60) / 4, 1)
    assert scores['综合'] == expected
```

运行测试：

```bash
cd tests
pytest test_quant_signals.py -v
```

输出会像：

```
test_quant_signals.py::test_day_position[10.5-10.0-11.0-中位] PASSED
test_quant_signals.py::test_day_position[10.8-10.0-11.0-高位] PASSED
test_quant_signals.py::test_day_position[10.1-10.0-11.0-低位] PASSED
test_factor_score_pe_zero PASSED
...
```

## 我踩过的坑

1. **测试污染**：第一个测试修改了全局状态，第二个测试以为状态是初始的。用 fixture + 每次重新创建数据对象来避免。
2. **Mock 太宽泛**：最初我把整个 `StockAPI` 都 mock 掉了，导致后来改了 API 签名测试却不报错。现在只 mock 具体方法。
3. **边界值不完整**：`change_pct = 3.0` 落哪个区间？`3.0 >= 3`=True，属于大涨。但我之前没写边界测试，光靠脑补。
4. **浮点数比较**：`assert 0.1 + 0.2 == 0.3` 会挂。量化里用 `pytest.approx`：

```python
assert result['support'] == pytest.approx(9.9 * 0.98, rel=1e-6)
```

## 总结

| 概念 | 量化类比 | 一句话记住 |
|------|---------|-----------|
| Fixture | 历史回测数据切片 | 准备好固定行情，别跑真实数据 |
| Mock | Paper Trading 模拟盘 | 假装连了服务器，实际返回假数据 |
| Parametrize | 参数遍历优化 | 一张表测完所有边界值 |

单元测试不是"锦上添花"，而是量化系统的"安全网"。没有测试的回测，可能只是在验证 bug 的一致性。

下一步：覆盖率达到多少才算够？看第2课。
