# 量化深度第 1 课：因子 IC / IR 体系

> 因子评价的核心指标：IC（Information Coefficient）衡量因子预测能力，IR（Information Ratio）衡量因子稳定性。

## 1. 核心概念

### 1.1 IC —— Information Coefficient（信息系数）

| 概念 | 说明 |
|------|------|
| **定义** | 因子值与**未来收益**之间的相关性 |
| **范围** | [-1, 1]，正值表示因子越高收益越大 |
| **意义** | 因子能否预测收益方向，越大越强 |

### 1.2 IR —— Information Ratio（信息比率）

```
IR = mean(IC) / std(IC)
```

- `mean(IC)`：因子预测收益的**平均大小**
- `std(IC)`：预测能力的**波动风险**
- 通常跨时间序列计算（如 252 个交易日窗口）
- **IR > 0.5 算合格，IR > 1.0 算优秀**

### 1.3 两种 IC

| 类型 | 计算方式 | 适用场景 |
|------|---------|---------|
| **Pearson IC** | 因子值与收益的 Pearson 线性相关系数 | 因子值服从正态分布，线性关系 |
| **Spearman Rank IC** | 因子值与收益的**秩相关系数** | 因子值有极端值、非线性关系（**业界更常用**） |

> **业界普遍采用 Spearman Rank IC**，因为因子值常有极端值，秩相关天然鲁棒。

---

## 2. Spearman Rank IC 计算

秩相关系数 = 对因子值排秩后的 Pearson 相关系数。

### 数学公式

```
Spearman IC = Pearson(rank(factor), rank(return))
```

等价于：列出截面内每只股票的因子排名和收益排名，计算排名的线性相关。

### NumPy 实现

```python
import numpy as np
from scipy.stats import rankdata

def spearman_rank_ic(factor_values: np.ndarray,
                     forward_returns: np.ndarray) -> float:
    """计算截面 Spearman Rank IC

    Parameters
    ----------
    factor_values : (n_stocks,)  截面所有股票的因子值
    forward_returns : (n_stocks,) 对应的未来一期收益

    Returns
    -------
    ic : float  单期 Spearman Rank IC
    """
    rank_f = rankdata(factor_values)
    rank_r = rankdata(forward_returns)
    return np.corrcoef(rank_f, rank_r)[0, 1]


# ── 演示 ──
np.random.seed(42)
n = 200
# 模拟因子值：隐含预测能力
true_ret = np.random.randn(n) * 0.02
factor = true_ret * 100 + np.random.randn(n) * 0.5  # 加噪声
ret    = true_ret + np.random.randn(n) * 0.01        # 未来收益

ic = spearman_rank_ic(factor, ret)
print(f"Spearman Rank IC = {ic:.4f}")
# 预期输出 ≈ 0.66（噪声不大时接近 0.7）
```

---

## 3. 单只股票滚动窗口 IC

对**单只股票**计算「过去 N 天的因子预测收益」与「实际收益」的相关系数，沿时间滚动。

### 用途

- 分析因子在**个股层面**的时变预测能力
- 观察因子是否在某段时间失效

### NumPy 实现

```python
def rolling_stock_ic(factor_series: np.ndarray,
                     return_series: np.ndarray,
                     window: int = 60) -> np.ndarray:
    """单只股票的滚动窗口 Spearman IC

    Parameters
    ----------
    factor_series  : (T,)  时间序列的因子值
    return_series  : (T,)  对应每期的实际收益
    window         : int   滚动窗口长度

    Returns
    -------
    ic_series : (T - window + 1,)  每个窗口的 IC
    """
    T = len(factor_series)
    ic_list = []
    for i in range(T - window):
        f = factor_series[i : i + window]
        r = return_series[i : i + window]
        ic_list.append(spearman_rank_ic(f, r))
    return np.array(ic_list)


# ── 演示 ──
np.random.seed(42)
T = 500
# 前 300 天有预测能力，后 200 天退化
true_signal = np.concatenate([
    np.sin(np.linspace(0, 4*np.pi, 300)) * 0.03,
    np.random.randn(200) * 0.005,
])
factor_series = true_signal * 100 + np.random.randn(T) * 0.5
return_series = true_signal + np.random.randn(T) * 0.02

ic_series = rolling_stock_ic(factor_series, return_series, window=60)
print(f"滚动 IC 均值: {ic_series.mean():.4f}")
print(f"前 100 个窗口 IR: {ic_series[:100].mean() / ic_series[:100].std():.4f}")
print(f"后 100 个窗口 IR: {ic_series[-100:].mean() / ic_series[-100:].std():.4f}")
```

输出示例：
```
滚动 IC 均值: 0.2873
前 100 个窗口 IR: 3.4101
后 100 个窗口 IR: 0.4232
```

---

## 4. 因子相关性矩阵

当有多个候选因子时，需要检查它们之间的相关性，避免共线性。

### 步骤

1. 每月（或每日）对每个因子计算截面 Spearman Rank IC
2. 得到 `(T_periods, n_factors)` 的 IC 时间序列矩阵
3. 计算因子间的 Pearson 或 Spearman 相关矩阵

### NumPy 实现

```python
def factor_ic_matrix(factor_data: np.ndarray,
                     return_data: np.ndarray,
                     method: str = 'spearman') -> np.ndarray:
    """多因子 IC 时间序列矩阵

    Parameters
    ----------
    factor_data : (T, n_stocks, n_factors)  每期每个因子的截面值
    return_data : (T, n_stocks)             每期的收益截面
    method      : 'spearman' | 'pearson'

    Returns
    -------
    ic_ts : (T, n_factors)  每期每个因子的 IC
    """
    T, n_stocks, n_factors = factor_data.shape
    ic_ts = np.zeros((T, n_factors))
    for t in range(T):
        for f in range(n_factors):
            fv = factor_data[t, :, f]
            rv = return_data[t, :]
            if method == 'spearman':
                ic_ts[t, f] = spearman_rank_ic(fv, rv)
            else:
                ic_ts[t, f] = np.corrcoef(fv, rv)[0, 1]
    return ic_ts


# ── 演示 ──
np.random.seed(42)
T, n_stocks, n_factors = 252, 300, 4

# 模拟 4 个因子（前 2 个类似，3 独立，4 是噪声）
true_signal = np.random.randn(T, n_stocks) * 0.02
factor_data = np.zeros((T, n_stocks, n_factors))
factor_data[:, :, 0] = true_signal * 100 + np.random.randn(T, n_stocks) * 0.3
factor_data[:, :, 1] = true_signal * 100 + np.random.randn(T, n_stocks) * 0.3  # 与因子 0 高度相关
factor_data[:, :, 2] = np.random.randn(T, n_stocks) * 2                         # 独立随机因子
factor_data[:, :, 3] = np.random.randn(T, n_stocks) * 100                       # 纯噪声
return_data          = true_signal + np.random.randn(T, n_stocks) * 0.01

ic_ts = factor_ic_matrix(factor_data, return_data)

# 因子 IC 相关系数矩阵
ic_corr = np.corrcoef(ic_ts.T)
print("因子 IC 相关系数矩阵:\n", np.round(ic_corr, 3))
```

输出示例：
```
因子 IC 相关系数矩阵:
 [[ 1.     0.945 -0.007  0.009]
  [ 0.945  1.    -0.019  0.008]
  [-0.007 -0.019  1.     0.014]
  [ 0.009  0.008  0.014  1.   ]]
```

**解读**：因子 0 和 1 高度的相关 (>0.94)，合成时应该合并或只留一个，避免多重共线性。

---

## 5. IC 加权因子权重

将多个因子合成为一个综合因子，最经典的动态加权方法：**用过去 N 期滚动 IC 作为权重**。

### 策略

```
权重_{t, f} = IC_{t-1, f}  （或直接用 mean IC over rolling window）
综合因子_t = Σ 权重_f × 因子标准化值_f
```

进阶版：可以用 IR = mean(IC) / std(IC) 做权重（既考虑大小也考虑稳定性）。

### NumPy 实现

```python
def ic_weighted_factors(factor_data: np.ndarray,
                        return_data: np.ndarray,
                        window: int = 60,
                        method: str = 'ic') -> np.ndarray:
    """用滚动 IC / IR 作为权重的多因子合成

    Parameters
    ----------
    factor_data : (T, n_stocks, n_factors)
    return_data : (T, n_stocks)
    window      : 滚动窗口期数
    method      : 'ic' | 'ir'  权重类型

    Returns
    -------
    composite_factor : (T, n_stocks)  合成的单因子（逐截面）
    weights_history  : (T, n_factors)  每期的权重
    """
    T, n_stocks, n_factors = factor_data.shape
    composite = np.zeros((T, n_stocks))
    weights_h = np.zeros((T, n_factors))

    # 先算出所有 IC
    ic_ts = factor_ic_matrix(factor_data, return_data)

    for t in range(T):
        if t < window:
            weights = np.full(n_factors, 1.0 / n_factors)
        else:
            ic_window = ic_ts[t - window : t]
            if method == 'ic':
                weights = ic_window.mean(axis=0)
            elif method == 'ir':
                weights = ic_window.mean(axis=0) / (ic_window.std(axis=0) + 1e-8)

            # 去负值（负 IC 的因子反转后用）
            # 简单处理：保留绝对值，乘 sign
            weights = np.abs(weights)

        # 归一化
        weights = weights / (weights.sum() + 1e-8)
        weights_h[t] = weights

        # 因子标准化后加权合成
        fv = factor_data[t]  # (n_stocks, n_factors)
        # Z-score 标准化（每只股票截面内）
        fv_z = (fv - fv.mean(axis=0)) / (fv.std(axis=0) + 1e-8)
        composite[t] = fv_z @ weights

    return composite, weights_h


# ── 演示 ──
composite, w_history = ic_weighted_factors(factor_data, return_data, window=60)
print(f"合成因子各期权重均值:\n{np.round(w_history.mean(axis=0), 4)}")
# 预期输出（因子0,1相关性强，因子2有用，因子3噪声权重接近0）
```

---

## 6. 集成点说明

> **以下为 multi_factor.py 的修改指引**

### 修改目标

将**固定等权/固定主观权重**改为**IC 动态加权**。

### 具体修改

```python
# multi_factor.py 中

# ==== 修改前 ====
weights = np.array([0.25, 0.25, 0.25, 0.25])  # 固定权重

# ==== 修改后 ====
# 从因子数据库读取最近 n 期截面因子值和收益值
# 计算 IC 时间序列 → ic_ts: (n_periods, n_factors)
ic_window = ic_ts[-60:]   # 滚动 60 期
weights = ic_window.mean(axis=0)           # IC 均值加权
# 或
weights = ic_window.mean(axis=0) / (ic_window.std(axis=0) + 1e-8)  # IR 加权
weights = np.abs(weights)
weights /= weights.sum()
```

### 完整流程

```
因子数据    ──→  逐期计算 Spearman Rank IC  ──→  IC 时间序列矩阵
                          │
                          ▼
            滚动窗口 → IC均值/IR → 权重
                          │
                          ▼
            因子标准化值 × 权重 → 合成因子
```

---

## 7. 快速参考：完整工具函数

```python
import numpy as np
from scipy.stats import rankdata

def spearman_ic(factor, ret):
    """截面 Spearman Rank IC"""
    return np.corrcoef(rankdata(factor), rankdata(ret))[0, 1]

def rolling_ic_series(factors, returns, window=60):
    """第 f 支因子的时间序列 IC（deprecated, 用下面多因子版）"""
    T = factors.shape[0]
    ics = np.array([spearman_ic(factors[i], returns[i])
                    for i in range(T)])
    return ics

def factor_ic_matrix(factors, returns):
    """(T, S, F) → (T, F) 的 IC 时间序列矩阵"""
    T, _, F = factors.shape
    ic = np.zeros((T, F))
    for t in range(T):
        for f in range(F):
            ic[t, f] = spearman_ic(factors[t, :, f], returns[t])
    return ic

def ic_dynamic_weights(factors, returns, window=60, method='ir'):
    """IC/IR 动态加权合成单因子"""
    ic_ts = factor_ic_matrix(factors, returns)
    T, F = ic_ts.shape
    weights = np.full(F, 1.0 / F)
    for t in range(T):
        if t >= window:
            w = ic_ts[t-window:t]
            if method == 'ic':
                w = w.mean(axis=0)
            else:
                w = w.mean(axis=0) / (w.std(axis=0) + 1e-8)
            w = np.abs(w)
            weights = w / (w.sum() + 1e-8)
        # ... 继续合成因子
```

---

## 8. 思考题

1. 为什么业界偏好 Spearman IC 而不是 Pearson IC？
2. IR 高但 IC 为负的因子怎么处理？
3. 如果两个因子 IC 时间序列相关系数 > 0.95，合成时应该怎么做？
4. 滚动窗口选 20 天 vs 120 天，各有什么优劣？

---

> **下一课预告**：因子分层回测、多空组合收益、夏普比率评估。
