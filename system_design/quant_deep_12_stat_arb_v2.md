# 统计套利进阶：协整配对与多资产对冲

> 从quant_deep_05_stat_arb.md延伸

## 1. 协整配对交易

### 核心思想

两只股票价格不是相关的，而是**协整的**——它们的线性组合是平稳的：

```
Spread = Price_A - β × Price_B
当 Spread 偏离均值 → 回归到均值
```

### Johansen 检验（多标量协整）

```python
import numpy as np

def johansen_test(prices, p=1):
    """
    Johansen 迹检验
    prices: (T, n_assets) — 多标的历史价格
    p: 滞后阶数
    返回：协整向量矩阵
    """
    T, n = prices.shape
    delta = np.diff(prices, axis=0)
    
    # 构造回归矩阵
    Y = delta[p:]
    X1 = np.column_stack([delta[p-i-1:-i-1] for i in range(p)])
    X2 = prices[p:-1]
    
    # 典型相关分析（CCA形式）
    R = np.corrcoef(np.column_stack([Y, X1, X2]).T)
    # ... Johansen 迹检验统计量 ...
    # 返回协整向量
    
    return coint_vectors  # 每个向量是一组权重：[1, -β1, -β2, ...]
```

## 2. 多标的资产对冲

### 最优对冲比率

```python
def optimal_hedge_ratio(target_returns, hedge_returns):
    """
    计算最优对冲比率（OLS回归）
    target: 目标标的价格变化
    hedges: 对冲标的价格变化（多列）
    
    返回：最小方差对冲比率
    """
    # 通过OLS求解：target = β1*h1 + β2*h2 + ... + ε
    X = np.column_stack([np.ones(len(hedge_returns)), hedge_returns])
    beta = np.linalg.lstsq(X, target_returns, rcond=None)[0]
    return beta[1:]  # 多标对冲系数
```

### 协整与对冲实战

```python
def coint_hedging_strategy(asset_prices, window=60, z_entry=2.0, z_exit=0.5):
    """
    协整多标对冲策略
    asset_prices: (T, n) 多标价格矩阵
    策略逻辑：
    1. 每 window 天重新检验协整关系
    2. 计算当前价差的 z-score
    3. 偏离 2σ 以上开仓
    4. 回归 0.5σ 平仓
    """
    T, n = asset_prices.shape
    positions = np.zeros(T)
    
    spread_window = []
    
    for t in range(window, T):
        # 1. 滑动窗口协整检验
        window_data = asset_prices[t-window:t]
        coint_vector = estimate_coint(window_data)  # (n,)
        
        # 2. 计算价差
        spread = window_data @ coint_vector
        spread_z = (spread[-1] - np.mean(spread)) / np.std(spread)
        
        # 3. 开平仓信号
        if abs(spread_z) > z_entry and positions[t-1] == 0:
            positions[t] = np.sign(spread_z)  # 偏离越大，开仓
        elif abs(spread_z) < z_exit and positions[t-1] != 0:
            positions[t] = 0  # 回归平仓
        else:
            positions[t] = positions[t-1]  # 持仓不动
    
    return positions
```

## 3. 日内均值回归策略

### 使用统计模型预测短期反转

```python
def intraday_mean_reversion(tick_df, lookback=20, threshold=1.5):
    """
    日内均值回归：5分钟Tick级别
    tick_df: 包含 ['price', 'volume', 'bid_ask_spread']
    """
    results = []
    
    for i in range(lookback, len(tick_df)):
        window = tick_df.iloc[i-lookback:i]
        
        # 1. 计算日内均值
        mean_price = window['price'].mean()
        
        # 2. 计算偏离程度
        current_price = tick_df.iloc[i]['price']
        deviation = (current_price - mean_price) / window['price'].std()
        
        # 3. 考虑交易成本（价差）
        spread = tick_df.iloc[i]['bid_ask_spread']
        cost = spread * 0.5  # 滑点 + 手续费
        
        # 4. 信号生成
        if deviation > threshold:
            # 远高于均值 → 做空
            expect_return = mean_price - current_price - cost
            results.append({'signal': 'SHORT', 'expected_return': expect_return})
        elif deviation < -threshold:
            # 远低于均值 → 做多
            expect_return = (mean_price - current_price) - cost
            results.append({'signal': 'LONG', 'expected_return': expect_return})
        else:
            results.append({'signal': 'HOLD', 'expected_return': 0})
    
    return results
```

## 4. 机器学习辅助统计套利

### XGBoost 预测价差回归

```python
def ml_stat_arb(features, spread_returns, lookback=60):
    """
    用XGBoost预测价差回归方向
    features: ['volume_ratio', 'volatility', 'correlation_change', 'momentum']
    target: 未来1小时价差变化方向（+1涨/-1跌）
    """
    import xgboost as xgb
    
    # 构造特征
    X = prepare_features(features, lookback)
    y = np.sign(spread_returns.shift(-lookback))  # 未来方向
    
    # 训练
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        early_stopping_rounds=10
    )
    model.fit(X[:-lookback], y[:-lookback], eval_set=[(X[-lookback:], y[-lookback:])])
    
    return model
```

## 5. 风控要点

| 风险类型 | 控制方法 | 说明 |
|---------|---------|------|
| 协整失效 | 动态协整检验 | 定期（每N天）重检验关系 |
| 流动性风险 | 单标的限仓 | 不超过总流动性的1% |
| 回归时间过长 | 止损条件 | 时间止损 + 价格止损 |
| 模型过拟合 | 样本外验证 | 严格的回测/实盘分离 |
| 黑天鹅事件 | 尾部对冲 | 远价OTM期权保护 |

---

**下一篇**: Kelly仓位进阶
