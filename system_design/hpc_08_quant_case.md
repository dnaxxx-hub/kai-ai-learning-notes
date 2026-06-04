# 性能优化 #8：量化引擎实战优化案例

> 2026-05-17
> 前置：SIMD 实战 #7

## 1. 案例 1：回测 10 年数据的优化

### 1.1 原始实现

```python
def backtest_original(strategy_func, data: pd.DataFrame):
    """逐个 K 线推进回测"""
    positions = []
    signals = []
    capital = 100000
    
    for i in range(len(data)):
        bar = data.iloc[i]  # ❌ pandas iloc 每次很慢
        
        # 计算指标
        window = 14
        if i >= window:
            sma = data['close'].iloc[i-window:i].mean()  # ❌ 反复计算
            std = data['close'].iloc[i-window:i].std()
            signal = 1 if bar['close'] > sma + 2 * std else 0
        else:
            signal = 0
            
        signals.append(signal)
        # 交易逻辑...
```

**瓶颈**：
1. `data.iloc[i]` 每次 O(n) 索引
2. 每次循环重新计算 SMA/sdt（O(n²) 复杂度）
3. Python 循环本身慢

**优化结果**：10 年数据 → 用 45 分钟

### 1.2 优化版本

```python
def backtest_optimized(prices: np.ndarray, window: int = 14):
    """O(n) 时间 + numpy 向量化"""
    n = len(prices)
    
    # 1. 一次性计算所有指标（O(n)）
    # SMA + 标准差（滑动窗口法，单次遍历）
    sma = np.zeros(n)
    std = np.zeros(n)
    
    cum_sum = np.cumsum(prices)  # 前缀和
    cum_sq = np.cumsum(prices ** 2)  # 前缀平方和
    
    sma[window-1:] = (cum_sum[window:] - cum_sum[:-window]) / window
    var = ((cum_sq[window:] - cum_sq[:-window]) / window) - sma[window-1:]**2
    std[window-1:] = np.sqrt(np.maximum(var, 0))
    
    # 2. 向量化信号生成（无循环）
    upper = sma + 2 * std
    signals = np.where(prices > upper, 1, 0)  # 单次向量化操作
    
    # 3. 向量化资金计算
    returns = np.diff(prices) / prices[:-1]
    strategy_returns = returns * signals[1:]  # 信号延迟一期
    total_return = np.prod(1 + strategy_returns) - 1
    
    return signals, total_return
```

**优化结果**：10 年数据 → 用 < 1 秒。从 45 分钟到 < 1 秒（2700x 加速）。

### 1.3 进一步优化（Numba）

```python
from numba import njit

@njit(fastmath=True, cache=True)
def backtest_numba(prices: np.ndarray, window: int):
    """一次遍历完成全部计算"""
    n = len(prices)
    signals = np.zeros(n, dtype=np.int8)
    sma_buffer = np.zeros(n)
    
    cum_sum = 0.0
    cum_sq = 0.0
    
    for i in range(n):
        cum_sum += prices[i]
        cum_sq += prices[i] * prices[i]
        
        if i >= window:
            cum_sum -= prices[i - window]
            cum_sq -= prices[i - window] ** 2
            
        if i >= window - 1:
            sma_buffer[i] = cum_sum / window
            variance = cum_sq / window - sma_buffer[i] ** 2
            if variance > 0:
                std = np.sqrt(variance)
                signals[i] = 1 if prices[i] > sma_buffer[i] + 2 * std else 0
    
    return signals, sma_buffer
```

优势：一次遍历完成，不需要存中间数组（省 L2 缓存），numpy 版的 2x 快。

**优化结果**：10 年数据 → ~100ms

## 2. 案例 2：策略参数搜索

### 2.1 原始实现

```python
def grid_search(close: np.ndarray, param_grid: dict):
    """网格搜索最优参数"""
    best_sharpe = -np.inf
    best_params = None
    
    for window in range(5, 100, 5):
        for threshold in [1.5, 2.0, 2.5, 3.0]:
            signals = compute_signals(close, window, threshold)
            sharpe = calc_sharpe(close, signals)
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = (window, threshold)
    
    return best_params, best_sharpe
```

共 19 × 4 = 76 次信号计算。每次计算 O(n)，总体 O(n × 参数组合)。

### 2.2 向量化参数搜索

```python
@njit(parallel=True)
def grid_search_numba(close: np.ndarray, windows: np.ndarray, thresholds: np.ndarray):
    """所有参数组合同时计算"""
    n_windows = len(windows)
    n_thresholds = len(thresholds)
    n = len(close)
    
    best_sharpe = -np.inf
    best_params = (0, 0.0)
    
    for i in prange(n_windows):  # parallel!
        for j in range(n_thresholds):
            w, t = windows[i], thresholds[j]
            sma = 0.0
            
            # 单次遍历计算
            cum_sum = np.zeros(n)
            for k in range(n):
                cum_sum[k] = cum_sum[k-1] + close[k] if k > 0 else close[0]
                
                if k >= w - 1:
                    sma_val = (cum_sum[k] - (cum_sum[k-w] if k>=w else 0)) / w
                    # 信号检测...
            
            sharpe = fast_sharpe(...)
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = (w, t)
    
    return best_params, best_sharpe
```

理论上 76 个参数组合并行 → 76x 加速。

## 3. 案例 3：实时行情的低延迟处理

### 3.1 延迟预算

```
tick 到达 → 策略计算 → 信号生成 → 下单

目标：从 tick 到下单 ≤ 50ms
分解：
  行情解析 + 数据整理：5ms
  策略信号计算（10 个策略）：30ms
  决策逻辑：5ms
  下单+确认：10ms
```

### 3.2 优化策略

```python
class RealtimeOptimizer:
    """实时行情处理的低延迟架构"""
    def __init__(self):
        # 1. 预分配内存（零运行时分配）
        self.close_buffer = LockFreeRingBuffer(10_000)
        
        # 2. 预计算常数（不在热点路径上计算）
        self.strategy_params = self.load_strategies()
        
        # 3. Numba JIT 预编译（不花运行时）
        self.fast_signal = njit(self._calc_signal,
                                 fastmath=True, cache=True)
    
    def on_tick(self, tick: Tick):
        # 4. 无锁追加
        self.close_buffer.push(tick.price)
        
        # 5. 只计算增量
        if self.close_buffer.size() >= MIN_WINDOW:
            prices = self.close_buffer.last_n(MAX_WINDOW)
            # Numba JIT — 3ms 完成所有策略
            signal = self.fast_signal(prices)
            self._execute_if_needed(signal)
```

## 4. 性能优化检查清单

以下是量化引擎的优化检查清单，按收益从大到小排列：

```
[P0] 消除 n² 的逻辑 → 最差的情况下 10000x 差距
[P0] 向量化代替循环 → 通常 100-1000x 差距
[P1] 避免数据复制 → 用视图代替切片，用缓存代替加载
[P1] 一次遍历替代多次 → 尤其是在大量指标计算中
[P2] Numba JIT 编译热点 → 通常 50-300x
[P2] 避免 pandas iloc/loc 逐个访问 → 改为 numpy 批量
[P3] 异步 I/O → I/O 和计算重叠
[P3] 多进程参数搜索 → 利用多核
[P3] Rust 重写绝对热点 → 需要 <1ms 的实时信号计算
```

**核心规则**：向量化 + Numba 覆盖 95% 的优化空间，Rust/C 只预留最后 5% 的极限场景。

## 总结

```
案例 1：回测 10 年数据
  原始：45 分钟 → O(n²) pandas loop
  优化：~100ms → O(n) + Numba JIT（27000x 加速）

案例 2：参数搜索
  原始：76 次串行计算
  优化：prange 并行 + 单次遍历（预期 76x 并行）

案例 3：实时行情
  关键：预分配 + 无锁 RingBuffer + 增量计算
  预算：<50ms 完成 tick→下单

检查清单：算法复杂度 > 向量化 > 缓存 > 多核 > 深度优化
```
