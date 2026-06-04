# 第2课：测试覆盖率与测试策略

> 自学笔记 — 哪些该测、哪些不该测、怎么衡量够没够

## 我为什么要学这个？

第1课写完，我兴冲冲跑了 `pytest`，绿一片。然后我心想：「代码覆盖率多少？」一测发现才 30%——`factor_score` 函数里有一整个 if-else 分支从没进过。

问题是：**把覆盖率堆到 100% 有意义吗？** 测试工具代码还是测业务逻辑？测试覆盖率只是起点，真正的洞察在于：知道哪些代码值得测、哪些不值得。

## 覆盖率工具：pytest-cov

安装：

```bash
pip install pytest-cov
```

跑覆盖率：

```bash
pytest tests/ --cov=strategy_engine --cov-report=term-missing
```

这会列出：哪些行没覆盖到、整体覆盖率百分比。

更直观的 HTML 报告：

```bash
pytest tests/ --cov=strategy_engine --cov-report=html
```

浏览器打开 `htmlcov/index.html`，绿的行已覆盖，红色是漏网之鱼。

## 实战：为我量化代码做覆盖率分析

拿 `finance/config.py` 的 `validate_config()` 函数来说：

```python
def validate_config():
    errors = []
    if BACKTEST_CONFIG['initial_capital'] <= 0:
        errors.append("初始资金必须大于0")
    if not 0 <= BACKTEST_CONFIG['commission_rate'] <= 0.01:
        errors.append("手续费率必须在0-1%之间")
    ...
    return True
```

覆盖测试：

```python
# test_config.py
import pytest
from config import validate_config, BACKTEST_CONFIG

def test_default_config_valid():
    """默认配置应该通过验证"""
    assert validate_config() == True

def test_initial_capital_negative():
    """初始资金为负数应报错"""
    original = BACKTEST_CONFIG['initial_capital']
    BACKTEST_CONFIG['initial_capital'] = -1000
    with pytest.raises(ValueError, match="初始资金必须大于0"):
        validate_config()
    BACKTEST_CONFIG['initial_capital'] = original  # 恢复

def test_commission_rate_too_high():
    """手续费率超过1%应报错"""
    original = BACKTEST_CONFIG['commission_rate']
    BACKTEST_CONFIG['commission_rate'] = 0.02
    with pytest.raises(ValueError, match="手续费率"):
        validate_config()
    BACKTEST_CONFIG['commission_rate'] = original
```

跑完后看报告，哪个 if 分支漏掉了，一目了然。

## 边界值分析 — 量化测试的核心武器

量化系统的 Bug 往往不发生在 "正常数据" 上，而发生在**边界**上。

```
analyze_stock 中 change_pct 的边界：
  >= 3    → 📈 大涨
  >= 1    → 🟢 上涨
  >= -1   → ⚪ 横盘
  >= -3   → 🔻 下跌
  < -3    → 🔴 大跌
```

边界值有 5 个「切换点」：3, 1, -1, -3 以及从没定义过的 < -3 之外的值。

**边界值分析（Boundary Value Analysis）** 建议：每个边界测试 3 个点（边界-1、边界、边界+1）。

```python
# 边界：3
(2.999, '🟢 上涨'),  # 差0.001就不是大涨
(3.000, '📈 大涨'),  # 刚好够
(3.001, '📈 大涨'),  # 远远够

# 边界：1
(0.999, '⚪ 横盘'),  # 差0.001就不是上涨
(1.000, '🟢 上涨'),  # 刚好够
(1.001, '🟢 上涨'),
```

**为什么量化系统特别吃这套？** 因为股票收盘价 10.50 和 10.51 本来就是离散的，一个浮点精度错误就可能让 3.000（大涨）变成 2.999（上涨），信号完全不一致。

下面是完整的边界测试示例：

```python
@pytest.mark.parametrize("change_pct,expected", [
    # 大涨边界 (3%)
    (2.999, '⚪ 横盘'),
    (3.000, '📈 大涨'),
    (3.001, '📈 大涨'),
    
    # 上涨边界 (1%)
    (0.999, '⚪ 横盘'),
    (1.000, '🟢 上涨'),
    (1.001, '🟢 上涨'),
    
    # 横盘下界 (-1%)
    (-0.999, '⚪ 横盘'),
    (-1.000, '🔻 下跌'),
    (-1.001, '🔻 下跌'),
    
    # 下跌下界 (-3%)
    (-2.999, '🔻 下跌'),
    (-3.000, '🔴 大跌'),
    (-3.001, '🔴 大跌'),
])
def test_signal_boundaries(change_pct, expected):
    """涨跌幅信号的边界全覆盖"""
    d = fake_stock_dict(change_pct=change_pct)
    assert analyze_stock(d)['signal'] == expected
```

## 哪些该测、哪些不该测

这是测试策略中最难的问题。我的判断标准：

### 该测 ✅

| 类别 | 例子 | 理由 |
|------|------|------|
| 核心业务逻辑 | `analyze_stock`, `factor_score` | 改坏就没信号了 |
| 边界值密集处 | 涨跌幅分类、PE 评分条件 | 最容易出 Bug |
| 数据转换逻辑 | K线接口的 parse 部分 | 腾讯 API 格式说变就变 |
| 配置验证 | `validate_config` | 配错参数直接亏钱 |

### 不必测 ❌

| 类别 | 例子 | 理由 |
|------|------|------|
| 纯数据类 | `config.py` 的字典定义 | 靠类型检查就够 |
| 外部 API 调用 | `StockAPI.batch()` | 测试里已经 mock 了 |
| print/日志输出 | 报错信息格式 | 不值得自动化验证 |
| 第三方库的行为 | `numpy.std` 计算结果 | 相信库作者（他们自己测过了） |
| 临时脚本 | 一次性的数据迁移工具 | 写完就扔 |

### 需要权衡 ⚖️

| 类别 | 决策依据 |
|------|---------|
| 报告生成逻辑 | 如果报告中有计算（如 `backtest_report` 的评分逻辑），测；只是堆字符串，不测 |
| UI/输出格式 | 不看内容看结构（比如断言 Json 有某些字段），不测具体排版 |
| 异常处理路径 | 测关键异常（数据缺失），不测 Python 内置异常（KeyError 由 Python 保证） |

## 80/20 法则在测试中的应用

帕累托原则在量化测试中很管用：**80% 的 Bug 藏在 20% 的代码里**。

```
finance/ 目录代码行数估算：
  strategy_engine.py  ~300 行  ← 核心信号逻辑, 重点覆盖
  mini_realtime.py    ~200 行  ← 数据接口 + 技术指标, 重点覆盖
  config.py           ~100 行  ← 配置, 轻量测试
  daily_report.py     ~80 行   ← 报告格式, 看情况
  fourier_analyzer.py ~60 行   ← 特殊场景, 边界测试
```

我的策略：
1. `strategy_engine.py` → 覆盖目标 **95%+**（影响决策）
2. `mini_realtime.py` → 覆盖 **85%+**（技术指标计算）
3. `config.py` → 覆盖 **70%+**（配置验证）
4. 报告类 → 覆盖 **50%+**（核心字段校验即可）

## 用 pytest.ini 配置默认参数

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
markers =
    slow: 慢速测试（需要网络或大文件）
    smoke: 冒烟测试（基本功能验证）
addopts = -v --tb=short --strict-markers
```

然后在跑覆盖率时加上：

```bash
pytest --cov=strategy_engine --cov-report=term-missing --cov-fail-under=80
```

`--cov-fail-under=80` 的意思是：覆盖率低于 80% 就报错退出。在 CI 里这个很有用（第4课会展开）。

## 我踩过的坑

1. **为了覆盖率而测**：之前测 `config.py` 时为了让每个变量都被覆盖，写了个 `test_all_config_values_exist` 循环检查每个字典的 key。但实际业务逻辑压根不依赖这些 key 是否存在——测试绿了，但没意义。

2. **Mock 导致覆盖率虚高**：mock 了整个 `StockAPI.batch` 后，`batch` 函数里的 parse 逻辑（`p[1].split('~')` 那部分）永远跑不到，但覆盖率报告说走了 100%。需要把 parse 逻辑抽出来单独测。

3. **边界值只测了正负**：`change_pct` 测了 ±5 但没测 0。结果重构时把 `>=` 写成 `>`，`0 <= change_pct < 3` 变成 `0 < change_pct < 3`——change_pct=0 这个最常出现的值被误判了。

## 总结

| 概念 | 量化类比 | 一句话记住 |
|------|---------|-----------|
| 覆盖率 | 策略的参数覆盖率 | 不是越高越好，核心路径必须全覆盖 |
| 边界值分析 | 止损/止盈的精确触发点 | 差别 0.001% 就可能是完全不同的信号 |
| 80/20 法则 | 80% 超额收益来自 20% 的持仓 | 80% 的 Bug 藏在 20% 的代码里 |
| 测试分层 | 核心/辅助/报告 | 不同的代码承担不同的测试责任 |

覆盖率不是目标，**信心**才是。当你说"这个模块改了没问题"的时候，支撑这句话的应该是测试，而不是运气。

下一步：有了单元测试和覆盖率，怎么验证整个回测逻辑的正确性？看第3课。
