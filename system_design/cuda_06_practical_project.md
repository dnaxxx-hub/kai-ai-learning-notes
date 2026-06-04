# CUDA 06 — 实战项目：量化加速器

将 CUDA 应用到量化交易管线中。

## 项目：GPU 加速 K 线分析

### 1. SMA 并行计算

```python
@cuda.jit
def sma_gpu(prices, window, output):
    """并行滑动平均"""
    idx = cuda.grid(1)
    if idx >= output.size:
        return
    
    total = 0.0
    for i in range(window):
        total += prices[idx + i]
    output[idx] = total / window
```

相比 CPU 的 O(n×w)，GPU 通过并行每个输出点达到 O(n) 的 wall time。

### 2. 并行回测

```python
@cuda.jit
def backtest_kernel(prices, signals, capital, positions):
    """每个线程执行一个策略的参数回测"""
    tid = cuda.grid(1)
    if tid >= signals.shape[0]:
        return
    
    cash = capital[tid]
    pos = 0.0
    
    for t in range(1, prices.size):
        action = signals[tid, t]  # -1:卖, 0:持有, 1:买
        if action == 1 and cash > 0:
            pos = cash / prices[t]
            cash = 0.0
        elif action == -1 and pos > 0:
            cash = pos * prices[t]
            pos = 0.0
    
    # 最终价值
    positions[tid] = cash + pos * prices[-1]
```

### 3. 蒙特卡洛模拟

```python
@cuda.jit
def monte_carlo_gbm(start_price, mu, sigma, days, paths, results):
    """几何布朗运动并行模拟"""
    tid = cuda.grid(1)
    if tid >= paths:
        return
    
    price = start_price
    dt = 1.0 / 252  # 日频
    
    for d in range(days):
        # Box-Muller 生成正态随机数
        u1 = cuda.random.xoroshiro128p_uniform_float32(...)
        u2 = cuda.random.xoroshiro128p_uniform_float32(...)
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        
        price *= math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * z * math.sqrt(dt))
    
    results[tid] = price
```

### 4. 实时数据处理管线

```
行情数据 → GPU 全局内存
   ↓
Kernel 1: 数据清洗（并行逐元素）
   ↓  (留在 GPU)
Kernel 2: 技术指标计算（SMA/RSI/MACD）
   ↓  (留在 GPU)
Kernel 3: 策略信号生成
   ↓  (留在 GPU)  
Kernel 4: 评分矩阵
   ↓
数据拷回 CPU → 最终决策
```

**关键**：尽量减少 CPU↔GPU 数据传输，数据尽量在 GPU 上流水线处理。

## 预期加速

| 操作 | CPU (单核) | GPU | 加速比 |
|------|:---------:|:---:|:-----:|
| 10年日线 SMA(20) | ~5ms | ~0.05ms | 100x |
| 10000参数回测 | ~10s | ~0.1s | 100x |
| 百万路径蒙特卡洛 | ~30s | ~0.5s | 60x |

## 工具箱集成

- `projects/cuda_quant/` 目录下会有：
  - `sma_cuda.py` — GPU SMA
  - `backtest_cuda.py` — 并行参数搜索
  - `mc_cuda.py` — 蒙特卡洛
  - `benchmark.py` — CPU vs GPU 性能对比

> 需要 numba + CUDA runtime 才能跑
