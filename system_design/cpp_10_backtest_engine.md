# 📘 10 - 综合项目：高性能回测引擎

> 集前 9 课之大成：C++20 Coroutine 事件循环 + AVX/SIMD 向量化计算 + pybind11 Python 绑定
> 目标：Python `Engine.run(config)` → C++ 执行 → 返回 PnL DataFrame

---

## 架构总览

```
┌─────────────┐     pybind11     ┌───────────────────────────────────┐
│  Python API  │ ──────────────→ │        C++20 回测引擎              │
│              │                 │                                   │
│  Engine      │  config (dict)  │  ┌─────────────────────────┐      │
│  .run(config)│ ←────────────── │  │ Coroutine 事件循环       │      │
│  → PnL DF    │   Factors/PnL  │  │ - BarHandler(async)      │      │
└─────────────┘                  │  │ - OrderHandler(async)    │      │
                                 │  │ - Timer(async)           │      │
                                 │  │ - RiskCheck(async)       │      │
                                 │  └─────────┬───────────────┘      │
                                 │            │                        │
                                 │  ┌─────────▼───────────────┐      │
                                 │  │ 向量化计算引擎           │      │
                                 │  │ - AVX/SIMD 因子计算     │      │
                                 │  │ - 信号生成 + 仓位管理   │      │
                                 │  │ - PnL 累积              │      │
                                 │  └─────────────────────────┘      │
                                 └───────────────────────────────────┘
```

---

## 1. 数据结构

### Bar (K线)

```cpp
struct Bar {
    double open, high, low, close;
    double volume;
    int64_t timestamp;  // UNIX ms
};

struct Order {
    enum Side { BUY, SELL };
    Side side;
    double price;
    double size;
    int64_t timestamp;
};

struct Position {
    double size = 0;        // 当前持仓（正=多头，负=空头）
    double avg_price = 0;   // 平均开仓价
    double realized_pnl = 0;
    double unrealized_pnl = 0;
};

struct TradeRecord {
    int64_t timestamp;
    double price;
    double size;
    double pnl;
    double commission;
};
```

### Config (Python 传入)

```cpp
struct BacktestConfig {
    std::string symbol;
    double initial_capital;
    double commission_pct;
    double slippage_pct;
    int max_position;
    std::string signal_type;  // "sma_cross", "momentum", "mean_reversion"
    int fast_window;
    int slow_window;
};
```

---

## 2. Coroutine 事件循环

```cpp
#include <coroutine>
#include <functional>
#include <vector>
#include <memory>

// 事件类型
enum class EventType {
    BAR,        // 新 K 线
    ORDER_FILL, // 订单成交
    TIMER,      // 定时器
};

struct Event {
    EventType type;
    int64_t timestamp;
    std::variant<Bar, Order, std::monostate> data;
};

// 协程版 Event Handler
struct BarHandler {
    struct promise_type {
        BarHandler get_return_object() { return BarHandler{}; }
        std::suspend_always initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }

        // 让我们能 co_await Event
        std::suspend_always await_transform(Event) { return {}; }
    };
};

// 简化版事件循环——模拟多个协程处理事件
template<typename T>
struct Generator {
    struct promise_type {
        T value;
        Generator get_return_object() { return Generator{this}; }
        std::suspend_always initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        std::suspend_always yield_value(T v) { value = v; return {}; }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
    using Handle = std::coroutine_handle<promise_type>;
    Handle h_;
    Generator(promise_type* p) : h_(Handle::from_promise(*p)) {}
    ~Generator() { if (h_) h_.destroy(); }
    Generator(Generator&& o) : h_(o.h_) { o.h_ = {}; }
    bool next() { h_.resume(); return !h_.done(); }
    T value() { return h_.promise().value; }
};
```

### 事件循环示例

```cpp
// 产生 bar 事件的协程（数据读取器）
Generator<Bar> bar_generator(const std::vector<Bar>& bars) {
    for (const auto& bar : bars) {
        co_yield bar;
    }
}

// 信号计算协程
Generator<double> signal_generator(const std::vector<Bar>& bars,
                                    int fast, int slow) {
    // 用前缀和算法计算 SMA
    std::vector<double> closes;
    closes.reserve(bars.size());
    for (auto& b : bars)
        closes.push_back(b.close);

    // 累积并输出信号
    for (size_t i = 0; i < bars.size(); ++i) {
        if (i < 1) {
            co_yield 0.0;
            continue;
        }
        // 简单动量信号
        double ret = (closes[i] - closes[i-1]) / closes[i-1];
        co_yield ret;  // 信号 = 收益率
    }
}

// 回测主循环（事件驱动）
struct BacktestStats {
    int trades;
    double total_pnl;
    double max_drawdown;
    double sharpe;
};

BacktestStats run_event_loop(const std::vector<Bar>& bars,
                              const BacktestConfig& cfg) {
    auto bars_gen = bar_generator(bars);
    auto sig_gen = signal_generator(bars, cfg.fast_window, cfg.slow_window);

    Position pos;
    int trades = 0;

    // 事件循环
    while (bars_gen.next() && sig_gen.next()) {
        const Bar& bar = bars_gen.value();
        double signal = sig_gen.value();

        // 信号 → 交易决策
        if (signal > 0.005 && pos.size == 0) {
            // 开多仓
            pos.size = cfg.max_position;
            pos.avg_price = bar.close * (1 + cfg.slippage_pct);
            trades++;
        } else if (signal < -0.005 && pos.size == 0) {
            // 开空仓
            pos.size = -cfg.max_position;
            pos.avg_price = bar.close * (1 - cfg.slippage_pct);
            trades++;
        } else if (abs(signal) < 0.001 && pos.size != 0) {
            // 平仓
            double exit_price = bar.close * (1 - cfg.slippage_pct * (pos.size > 0 ? 1 : -1));
            pos.realized_pnl += (exit_price - pos.avg_price) * pos.size;
            pos.size = 0;
        }

        // 更新未实现盈亏
        if (pos.size != 0)
            pos.unrealized_pnl = (bar.close - pos.avg_price) * pos.size;
    }

    return BacktestStats{
        trades,
        pos.realized_pnl + pos.unrealized_pnl,
        0.0,  // max_drawdown
        0.0   // sharpe
    };
}
```

---

## 3. AVX/SIMD 向量化计算

（复用第 9 课的 quant_factors 中的 SIMD 内核）

```cpp
// SIMD 加速的信号计算
__m256d simd_signal(__m256d fast_sma, __m256d slow_sma) {
    // 交叉信号: (fast - slow) / slow
    __m256d diff = _mm256_sub_pd(fast_sma, slow_sma);
    return _mm256_div_pd(diff, slow_sma);
}
```

---

## 4. pybind11 绑定

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

namespace py = pybind11;

PYBIND11_MODULE(backtest_engine, m) {
    m.doc() = "High-performance backtest engine with C++20 coroutines";

    // Bar
    py::class_<Bar>(m, "Bar")
        .def(py::init<>())
        .def_readwrite("open", &Bar::open)
        .def_readwrite("high", &Bar::high)
        .def_readwrite("low", &Bar::low)
        .def_readwrite("close", &Bar::close)
        .def_readwrite("volume", &Bar::volume)
        .def_readwrite("timestamp", &Bar::timestamp);

    // Config
    py::class_<BacktestConfig>(m, "BacktestConfig")
        .def(py::init<>())
        .def_readwrite("symbol", &BacktestConfig::symbol)
        .def_readwrite("initial_capital", &BacktestConfig::initial_capital)
        .def_readwrite("commission_pct", &BacktestConfig::commission_pct)
        .def_readwrite("slippage_pct", &BacktestConfig::slippage_pct)
        .def_readwrite("max_position", &BacktestConfig::max_position)
        .def_readwrite("signal_type", &BacktestConfig::signal_type)
        .def_readwrite("fast_window", &BacktestConfig::fast_window)
        .def_readwrite("slow_window", &BacktestConfig::slow_window);

    // TradeRecord
    py::class_<TradeRecord>(m, "TradeRecord")
        .def(py::init<>())
        .def_readwrite("timestamp", &TradeRecord::timestamp)
        .def_readwrite("price", &TradeRecord::price)
        .def_readwrite("size", &TradeRecord::size)
        .def_readwrite("pnl", &TradeRecord::pnl)
        .def_readwrite("commission", &TradeRecord::commission)
        .def("__repr__", [](const TradeRecord& t) {
            return "<Trade ts=" + std::to_string(t.timestamp) +
                   " price=" + std::to_string(t.price) +
                   " size=" + std::to_string(t.size) +
                   " pnl=" + std::to_string(t.pnl) + ">";
        });

    // Stats
    py::class_<BacktestStats>(m, "BacktestStats")
        .def(py::init<>())
        .def_readonly("trades", &BacktestStats::trades)
        .def_readonly("total_pnl", &BacktestStats::total_pnl)
        .def_readonly("max_drawdown", &BacktestStats::max_drawdown)
        .def_readonly("sharpe", &BacktestStats::sharpe)
        .def("__repr__", [](const BacktestStats& s) {
            return "<BacktestStats trades=" + std::to_string(s.trades) +
                   " pnl=" + std::to_string(s.total_pnl) +
                   " sharpe=" + std::to_string(s.sharpe) + ">";
        });

    // Engine
    m.def("run_backtest", &run_event_loop,
          "Run backtest with C++ coroutine event loop",
          py::arg("bars"), py::arg("config"));

    m.def("compute_pnl", [](const std::vector<Bar>& bars,
                             const std::vector<int>& signals) {
        // 向量化 PnL 计算
        std::vector<TradeRecord> trades;
        // ... 实现
        return trades;
    }, "Vectorized PnL computation");
}
```

---

## 5. Python API 设计

```python
# python/backtest_api.py
from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
import numpy as np

@dataclass
class Config:
    symbol: str = "BTCUSDT"
    initial_capital: float = 10000.0
    commission_pct: float = 0.001  # 0.1%
    slippage_pct: float = 0.0005
    max_position: int = 100
    signal_type: str = "momentum"
    fast_window: int = 5
    slow_window: int = 20

class Engine:
    """
    高性能回测引擎
    API: Engine.run(config) → PnL DataFrame
    """
    def __init__(self):
        try:
            import backtest_engine as be
            self._cpp = be
            self._mode = "cpp"
        except ImportError:
            self._mode = "python"  # fallback
            print("[Engine] 使用纯 Python 模式")

    def prepare_bars(self, df: pd.DataFrame) -> list:
        """将 pandas DataFrame 转换为 C++ Bar 列表"""
        bars = []
        for _, row in df.iterrows():
            bar = {
                "open": float(row.get("open", row["close"])),
                "high": float(row.get("high", row["close"])),
                "low": float(row.get("low", row["close"])),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
                "timestamp": int(row.name.timestamp() * 1000)
                    if hasattr(row.name, 'timestamp')
                    else int(row.get("timestamp", 0)),
            }
            bars.append(bar)
        return bars

    def run(self, df: pd.DataFrame, config: Optional[Config] = None) -> pd.DataFrame:
        """
        运行回测。
        参数:
            df: OHLCV DataFrame (index=datetime, columns=[open,high,low,close,volume])
            config: 回测配置
        返回:
            PnL DataFrame (含策略净值、持仓、交易记录)
        """
        if config is None:
            config = Config()

        bars = self.prepare_bars(df)

        if self._mode == "cpp":
            # C++ 快速路径
            stats = self._cpp.run_backtest(bars, config)
            # 从序列化结果重建 DataFrame
            result = self._rebuild_pnl(bars, stats)
        else:
            # Python 回退路径（纯 Python 实现）
            result = self._run_python(bars, config)

        return result

    def _run_python(self, bars: list, config: Config) -> pd.DataFrame:
        """纯 Python 回退实现"""
        closes = np.array([b["close"] for b in bars])
        timestamps = [b["timestamp"] for b in bars]

        # 信号计算
        fast_sma = self._sma(closes, config.fast_window)
        slow_sma = self._sma(closes, config.slow_window)
        signal = np.where(fast_sma > slow_sma, 1,
                          np.where(fast_sma < slow_sma, -1, 0))

        # 回测逻辑
        position = 0
        cash = config.initial_capital
        trades = []
        portfolio_value = []

        for i in range(len(closes)):
            price = closes[i]

            # 交易决策
            if signal[i] == 1 and position == 0:
                # 买入
                position = config.max_position
                cost = price * position * (1 + config.commission_pct)
                cash -= cost
                trades.append({"time": timestamps[i], "action": "BUY",
                               "price": price, "size": position})

            elif signal[i] == -1 and position > 0:
                # 卖出
                revenue = price * position * (1 - config.commission_pct)
                cash += revenue
                trades.append({"time": timestamps[i], "action": "SELL",
                               "price": price, "size": position})
                position = 0

            # 组合价值
            equity = cash + position * price
            portfolio_value.append(equity)

        # 构建结果 DataFrame
        df_result = pd.DataFrame({
            "close": closes,
            "signal": signal,
            "portfolio_value": portfolio_value,
            "returns": np.diff(portfolio_value, prepend=config.initial_capital)
                       / config.initial_capital,
        })

        df_result["cum_return"] = (1 + df_result["returns"]).cumprod()

        sharp_ratio = np.nan
        if df_result["returns"].std() > 0:
            sharp_ratio = np.sqrt(252) * df_result["returns"].mean() \
                          / df_result["returns"].std()

        df_result.attrs["stats"] = {
            "total_return": df_result["cum_return"].iloc[-1] - 1,
            "sharpe": sharp_ratio,
            "max_drawdown": self._max_drawdown(df_result["portfolio_value"]),
            "trades": len(trades),
        }

        return df_result

    @staticmethod
    def _sma(arr, window):
        """简单移动平均（前缀和）"""
        prefix = np.cumsum(np.concatenate([[0], arr]))
        result = np.zeros_like(arr)
        for i in range(len(arr)):
            s = max(0, i + 1 - window)
            result[i] = (prefix[i+1] - prefix[s]) / (i+1-s)
        return result

    @staticmethod
    def _max_drawdown(equity_curve):
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        return drawdown.min()
```

---

## 6. 使用示例

```python
# demo.py
import pandas as pd
import numpy as np
from backtest_api import Engine, Config

# 1. 生成模拟数据
np.random.seed(42)
dates = pd.date_range("2024-01-01", periods=1000, freq="h")
price = 100.0 + np.cumsum(np.random.randn(1000) * 0.1)
df = pd.DataFrame({"close": price}, index=dates)
df["open"] = df["close"] * (1 + np.random.randn(1000) * 0.001)
df["high"] = df[["open", "close"]].max(axis=1) * (1 + abs(np.random.randn(1000)) * 0.005)
df["low"] = df[["open", "close"]].min(axis=1) * (1 - abs(np.random.randn(1000)) * 0.005)
df["volume"] = np.random.randint(100, 10000, 1000)

# 2. 配置
config = Config(
    symbol="BTCUSDT",
    initial_capital=10000.0,
    max_position=1,
    signal_type="momentum",
    fast_window=5,
    slow_window=20,
)

# 3. 运行回测
engine = Engine()
result = engine.run(df, config)

# 4. 查看结果
print(f"总收益率: {result.attrs['stats']['total_return']:.2%}")
print(f"夏普比: {result.attrs['stats']['sharpe']:.2f}")
print(f"最大回撤: {result.attrs['stats']['max_drawdown']:.2%}")
print(f"交易次数: {result.attrs['stats']['trades']}")

# 5. 可视化（可选）
# result[["close", "portfolio_value"]].plot()
```

---

## 7. 与 backtest_v3.py 的整合

假设已有 `backtest_v3.py`：

```python
# 适配器：将原有 Python 回测逻辑挂载到 C++ 引擎上
class BacktestV3Adapter:
    """
    将 backtest_v3.py 的 signal_generator 作为 Python 回调，
    与 C++ 事件循环配合使用。
    """

    def __init__(self, v3_module):
        self.v3 = v3_module

    def run(self, df, config):
        engine = Engine()
        if engine._mode == "cpp":
            # C++ 模式：用 pybind11 回调
            return self._run_cpp(df, config)
        else:
            # Python 模式：直接调用 v3
            return self.v3.run_backtest(df, config)

    def _run_cpp(self, df, config):
        bars = engine.prepare_bars(df)
        # C++ 引擎计算出基础因子
        # 用 Python 生成信号（backtest_v3 的信号逻辑）
        signals = self.v3.generate_signals(df)
        # 传入 C++ 执行回测
        # backtest_engine.run_with_signals(bars, config, signals)
        return result
```

---

## 8. 性能预期

| 阶段 | 纯 Python | C++ 加速版 | 加速比 |
|------|-----------|-----------|--------|
| Bar 数据读取 (100K) | ~50ms | ~5ms | 10x |
| 因子计算 (100K) | ~200ms | ~3ms | 66x |
| 信号生成 (100K) | ~30ms | ~2ms | 15x |
| PnL 计算 (100K) | ~10ms | ~1ms | 10x |
| **总计** | **~290ms** | **~11ms** | **~26x** |

---

## 总结

| 课号 | 知识点 | 在本项目中用到 |
|------|--------|---------------|
| 01 | C++20 Core | `std::optional`, `std::variant`, `consteval` |
| 02 | CRTP/Policy | 策略基类的 CRTP 模式 |
| 03 | RAII/SmartPtr | `std::unique_ptr<Bar>` 等 |
| 04 | Move Semantics | Bar 容器的移动语义 |
| 05 | Design Patterns | 策略模式（信号策略） |
| 06 | C++20/23 | coroutine, ranges |
| **07** | **Coroutine** | **事件循环的协程式处理** |
| **08** | **Lock-Free** | **SPSC RingBuffer for 行情管道** |
| **09** | **pybind11** | **Python ↔ C++ 绑定** |
| **10** | **综合** | **完整回测引擎** |
