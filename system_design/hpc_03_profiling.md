# 性能优化 #3：Profiling 与性能分析

> 2026-05-17
> 前置：内存布局 #2

## 1. 为什么要 Profiling

### 1.1 猜测是性能优化的头号敌人

```python
# 你猜测的瓶颈：数据库查询
def compute_signals(data):
    db.save(data)        # 你认为这里慢
    for item in data:    # 你认为这里快
        item.signal = complex_calc(item)
```

实际瓶颈往往是意想不到的地方。所以：**先测定，再优化，不要猜。**

### 1.2 量化系统的 Profiling 目标

```
我需要知道：
  1. 最低延迟 — 实时信号推送必须在 N ms 内完成
  2. 吞吐瓶颈 — 回测 10 年数据，哪里卡住
  3. 资源使用 — 内存涨到哪里，CPU 在等什么
  4. 热点分布 — 80% 的时间花在 20% 的代码上
```

## 2. Python Profiling

### 2.1 cProfile

内置的确定性分析器，记录每个函数的调用次数和耗时：

```python
import cProfile, pstats, io

def run_backtest():
    data = load_market_data()
    signals = compute_all_strategies(data)
    results = evaluate_performance(signals)
    return results

# 方法 1：命令行
# python -m cProfile -o profile.out backtest.py

# 方法 2：代码内
profiler = cProfile.Profile()
profiler.enable()
run_backtest()
profiler.disable()

s = io.StringIO()
ps = pstats.Stats(profiler, stream=s).sort_stats('cumtime')
ps.print_stats(20)  # 最耗时的前 20 个函数
print(s.getvalue())
```

输出解读：

```
ncalls  tottime  percall  cumtime  percall  filename:lineno(function)
  1000    0.002    0.000    1.245    0.001  strategies.py:42(compute_ma)
  1000    0.891    0.001    0.891    0.001  {method 'mean' of 'numpy.ndarray'}
```

`cumtime`（累计耗时）是排查热点最重要的指标。

### 2.2 line_profiler

逐行分析，精确到代码行：

```bash
pip install line_profiler
kernprof -l -v backtest.py
```

代码内：

```python
@profile  # ← kernprof 会注入这个装饰器
def compute_signals(data):
    signals = []
    for bar in data:
        sma = bar.close.rolling(14).mean()  # 这行花了多少时间？
        std = bar.close.rolling(14).std()   # 还是这行？
        upper = sma + 2 * std               # 或是这里？
        signals.append(upper)
    return signals
```

输出：

```
Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
     5                                            @profile
     6                                            def compute_signals(data):
     7      1000      80000.0     80.0     10.2      signals = []
     8      1000     500000.0    500.0     63.9      for bar in data:
     9      1000     100000.0    100.0     12.8          sma = bar.close.rolling(14).mean()
    10      1000      80000.0     80.0     10.2          std = bar.close.rolling(14).std()
    11      1000      24000.0     24.0      3.1          upper = sma + 2 * std
```

### 2.3 memory_profiler

```bash
pip install memory_profiler
python -m memory_profiler backtest.py
```

```python
@profile
def load_data():
    df = pd.read_csv('market_data.csv')  # 占用多少内存？
    df = df[df.volume > 0]               # 筛选后剩多少？
    return df
```

### 2.4 py-spy（采样分析器）

无需修改代码，对生产环境无害：

```bash
# 采样运行中的进程
py-spy record -o profile.svg --pid 12345 --duration 30

# 火焰图输出：
#   每个矩形框代表一个函数
#   宽度 = 占总执行时间的比例
#   从下到上 = 调用栈浅→深
```

## 3. Rust Profiling

### 3.1 perf（Linux）

```bash
# 编译时保留符号
RUSTFLAGS="-g" cargo build --release

# 采样
perf record -g -- ./target/release/backtest
perf report
# 火焰图
perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg
```

### 3.2 代码内计时

```rust
use std::time::Instant;

let start = Instant::now();
compute_signals(&data);
let elapsed = start.elapsed();
println!("compute_signals: {}ms", elapsed.as_millis());
```

Rust 的零成本抽象有时会编译器优化得很神奇——`perf` 是更可靠的方式。

## 4. 量化引擎的核心瓶颈示例

对一个典型的回测流程做 Profiling：

```
load_kline_data      → 5%  (I/O)
compute_all_ma       → 30% (numpy 计算)
compute_all_rsi      → 25% (numpy 计算)
compute_signals      → 10% (条件判断)
evaluate_trades      → 20% (有序遍历)
generate_report      → 10% (聚合)

关键发现：
  compute_all_ma + compute_all_rsi = 55% → 都是 numpy 的 rolling 操作
  evaluate_trades = 20% → 可以用 Rust 重写加速
```

**优化策略**：numpy 的 rolling 已经是 C 级别快，瓶颈通常在数据复制（pandas 的 overhead）和多次遍历。用 NumPy 的 `stride_tricks` 或 Numba/JIT 可以把多次遍历合并为一次。

## 5. 量化中常见的 "变慢" 场景

### 5.1 pandas 链式操作

```python
# ❌ 多次遍历 DataFrame
df = df[df.volume > 10000]               # 1 次
df['ma_14'] = df.close.rolling(14).mean() # 1 次
df['ma_28'] = df.close.rolling(28).mean() # 1 次
# 以上共 3 次遍历

# ✅ 用 NumPy 合并
close = df.close.values
volume = df.volume.values

mask = volume > 10000
ma14 = np.convolve(close, np.ones(14)/14, mode='same')
ma28 = np.convolve(close, np.ones(28)/28, mode='same')

# 一次输出
```

### 5.2 不必要的类型转换

```python
# ❌ DataFrame → list → DataFrame 来回传
signals = df['signal'].tolist()  # numpy → list
# ... 处理 ...
df['signal'] = signals           # list → numpy

# ✅ 保持在 numpy/DataFrame 中
signals = df['signal'].values.copy()  # 还是 numpy
signals[signals > 0] = 1
df['signal'] = signals
```

### 5.3 过紧的循环

```python
# ❌ Python 循环（慢 100x）
for i in range(len(df)):
    df.iloc[i, 'signal'] = compute(df.iloc[i-14:i, 'close'])

# ✅ 向量化
window_mean = df.close.rolling(14).mean()
window_std = df.close.rolling(14).std()
df['signal'] = (df.close > window_mean + 2 * window_std)
```

## 6. 火焰图解读

```
火焰图读法：
  1. 顶层 = 正在执行的函数
  2. 宽度 = CPU 占用比例
  3. 从下到上 = 调用栈

快速诊断：
  ✅ 宽 + 平 → 这个函数是真实热点，值得优化
  ❌ 窄 + 长 → 调用栈深但不耗 CPU（可能是 I/O 等待）

在量化系统中的典型火焰图模式：
  - 大平层在 numpy 内部矩阵运算 → 已优化，不用动
  - 零星细长的 pandas 操作 → 可以合并
  - 最底层 I/O 的横条 → 可以预加载
```

## 总结

```
Profiling 三阶：
  1. 宏观：cProfile / py-spy → 找出热点函数
  2. 微观：line_profiler → 定位热点代码行
  3. 内存：memory_profiler → 内存占用的瓶颈

量化引擎的常见瓶颈：
  pandas 链式操作（多次遍历）
  不必要的类型转换
  Python 循环替代向量化
  I/O 瓶颈（多余的数据加载）

规则：先 profile，再优化，再 profile 验证，猜就是浪费时间的来源
```
