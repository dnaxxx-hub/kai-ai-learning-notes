# Kelly 仓位管理进阶

> 从 quant_deep_08_kelly_risk.md 延伸

## 1. 经典 Kelly 公式回顾

```
f* = (b × p - q) / b = p - q/b

其中：
f* = 最优仓位比例
p = 胜率
q = 1-p = 败率
b = 赔率（盈亏比）
```

## 2. 分数凯利（Fractional Kelly）

全凯利太激进（账户波动极大），所以使用分数凯利：

```python
def fractional_kelly(win_rate, odds, fraction=0.25):
    """
    分数凯利
    fraction: 取值 0.1~0.5
    """
    full_kelly = (win_rate * (odds + 1) - 1) / odds
    return full_kelly * fraction

# 实战经验
# 0.25 Kelly（建议起点）— 回撤温和，长期复利好
# 0.5 Kelly（激进）—— 回撤大但增长快
# 1.0 Kelly（全仓）—— 极大概率大幅回撤
```

## 3. 多资产凯利

### 协方差矩阵法

```python
def multi_asset_kelly(expected_returns, cov_matrix, risk_free=0.03):
    """
    多资产凯利仓位
    expected_returns: (n,) — 各标的预期超额收益率
    cov_matrix: (n,n) — 协方差矩阵
    """
    # 多资产凯利的解析解
    # f* = Σ^(-1) × μ
    inv_cov = np.linalg.inv(cov_matrix)
    weights = inv_cov @ expected_returns
    
    # 归一化（限制杠杆）
    if np.sum(np.abs(weights)) > 1.0:
        weights = weights / np.sum(np.abs(weights))
    
    return weights
```

### 简化版：独立仓位分配

```python
def independent_kelly_allocation(strategies, total_capital):
    """
    多个不相关策略的仓位分配
    strategies: [{'win_rate': 0.6, 'odds': 2.0}, ...]
    """
    # 每个策略独立计算凯利
    kelly_fractions = [
        fractional_kelly(s['win_rate'], s['odds'], fraction=0.25)
        for s in strategies
    ]
    
    # 如果总和超过1，按比例缩放
    total = sum(kelly_fractions)
    if total > 1.0:
        kelly_fractions = [k / total for k in kelly_fractions]
    
    # 分配资金
    allocations = [f * total_capital for f in kelly_fractions]
    return allocations
```

## 4. 动态凯利

```python
def dynamic_kelly(position_history, window=100):
    """
    动态调整凯利参数
    position_history: 近期交易记录
    """
    # 切片最近 window 笔交易
    recent = position_history[-window:]
    
    # 动态胜率（近期表现优先）
    wins = [t for t in recent if t['pnl'] > 0]
    win_rate = len(wins) / len(recent)
    
    # 动态赔率
    avg_win = np.mean([t['pnl'] for t in wins])
    avg_loss = abs(np.mean([t['pnl'] for t in recent if t['pnl'] <= 0]))
    odds = avg_win / avg_loss if avg_loss > 0 else 0
    
    # 波动率调整
    returns = [t['return'] for t in recent]
    vol = np.std(returns)
    
    # 波动率高 → 降低仓位
    vol_adj = max(0.5, min(1.0, 0.15 / (vol * np.sqrt(252))))
    
    # 计算凯利
    kelly = (win_rate * (odds + 1) - 1) / odds if odds > 0 else 0
    
    return {
        'win_rate': win_rate,
        'odds': odds,
        'kelly': kelly * vol_adj,
        'vol_adj': vol_adj
    }
```

## 5. 风险平价 vs 凯利

| 方法 | 目标 | 原理 |
|------|------|------|
| 最大回撤最小化 | 风险预算=1/N | 每个标的贡献相等波动率 |
| 经典凯利 | 最大化复利 | 最优的长期增长率 |
| 风险预算 | 指定风险敞口 | 灵活度最高 |

```python
def risk_parity_weights(cov_matrix):
    """
    风险平价权重
    每个标的贡献相等的波动率
    """
    n = len(cov_matrix)
    # 初始等权
    w = np.ones(n) / n
    
    # 通过优化求解：min Σ(risk_contrib_i - 1/n)^2
    # 其中 risk_contrib_i = w_i × (Σw)_i / sqrt(w^T Σ w)
    
    def risk_contribution(weights):
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        return weights * (cov_matrix @ weights) / portfolio_vol
    
    # 用 SLSQP 优化
    from scipy.optimize import minimize
    
    def objective(weights):
        rc = risk_contribution(weights)
        target = 1.0 / n
        return np.sum((rc - target) ** 2)
    
    constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
    bounds = [(0, 1) for _ in range(n)]
    
    result = minimize(objective, w, method='SLSQP', bounds=bounds, constraints=constraints)
    return result.x
```

## 6. 实盘建议

| 阶段 | Kelly分数 | 理由 |
|------|-----------|------|
| 回测验证中 | 0.1 | 最小化试错成本 |
| 实盘前3月 | 0.15 | 验证实盘滑点/延迟/成本 |
| 实盘稳定6月 | 0.25 | 经典推荐值 |
| 实盘一年以上 | 0.25~0.33 | 根据夏普微调 |

### 凯利使用的三个禁忌

1. **不要用回测的胜率/赔率直接代入** — 回测数据过拟合
2. **不要忽略相关性** — 策略之间高度相关时同时按凯利加仓会爆炸
3. **不要在杠杆上再用凯利** — 凯利已经是杠杆倍数了

---

**附**: 更新后的量化深度 Roadmap（16课）
