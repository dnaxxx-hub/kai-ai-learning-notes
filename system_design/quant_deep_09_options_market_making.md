# 期权做市：策略与实战

> 前置知识：期权基础（quant_deep_07_options.md）、BS模型

## 1. 期权做市商的核心问题

做市商（Market Maker）通过**双边报价**赚取买卖价差（Bid-Ask Spread）。核心挑战：

```
买入价     卖出价
  ↓          ↓
$1.00 --- $1.05 --- 价差 = $0.05
            ↑
         中间价 = $1.025
```

## 2. 希腊值管理

做市商做的是**希腊值中性**，不是方向性交易：

### Delta（Δ）— 价格敏感度
```
Δ = ∂V/∂S — 标的价格每变动$1，期权价值变化多少
- 做市商目标：Delta Neutral（每做一笔对手单，立即用标的对冲）
- 对冲方式：买入/卖出对应数量的股票或期货
```

### Gamma（Γ）— Delta的变化率
```
Γ = ∂²V/∂S² = ∂Δ/∂S
- Gamma高 = Delta变化快 = 需要频繁对冲
- ATM期权 Gamma最高
- 做市商不怕方向，怕Gamma急剧变化
```

### Vega（ν）— 波动率敏感度
```
ν = ∂V/∂σ — 波动率变化1%，期权价格变化多少
- Vega是做市商的主要利润来源
- 卖出期权 = 做空Vega（赌波动率下降）
- 做市商通过"gamma scalping"赚波动率的钱
```

### Theta（Θ）— 时间衰减
```
Θ = -∂V/∂t — 每过一天，期权贬值的速度
- 期权买方：亏损Theta
- 期权卖方：赚取Theta
- 做市商：同时赚Theta + 对冲Gamma
```

### Gamma Scalping — 做市商的利润引擎

```
1. 卖出一份ATM期权 → 赚了Theta和Vega
2. 标的价格上涨 → 期权Delta变正 → 卖出股票对冲
3. 标的价格下跌 → 期权Delta变负 → 买入股票对冲
4. 对冲中产生的"低买高卖"利润 = Gamma Scalping

关键公式：
Gamma Scalping Profit ≈ 0.5 × Γ × S² × (σ_real² - σ_implied²)

当实际波动率 < 隐含波动率 → 亏钱（买贵了波动率）
当实际波动率 > 隐含波动率 → 赚钱（波动率判断对了）
```

## 3. 做市商报价策略

### 报价宽度公式

```
Spread = Offset + Alpha(Vega) + Beta(Gamma) - Theta_daily

其中：
Offset = 固定成本（交易所费 + 清算费）
Alpha = Vega风险的定价
Beta = Gamma对冲成本的定价
```

#### 动态调整规则

```python
def calc_spread(mid_price, delta, gamma, vega, theta, position_size):
    """
    计算做市报价价差
    """
    base_spread = 0.02 * mid_price  # 基础价差：2%
    
    # Gamma调整：Gamma越大价差越宽
    gamma_adj = 0.5 * gamma * position_size
    
    # 库存调整：多仓多时压低买价，抬高卖价
    inventory_adj = 0.001 * position_size  # 每1000股调整1bp
    
    # 波动率调整：IV高时价差宽
    vega_adj = 0.01 * vega * (iv - historical_vol)
    
    spread = base_spread + gamma_adj + inventory_adj + vega_adj
    return max(spread, 0.01 * mid_price)  # 最低1%
```

## 4. 做市系统的典型架构

```
┌──────────────────────────────────────────────────┐
│                   做市引擎                        │
├──────────┬──────────┬──────────┬─────────────────┤
│ 风险计算 │ 报价引擎 │ 对冲引擎 │ 风控模块       │
│ ─ Δ/Γ/ν │ ─ Spread │ ─ 标的中│ ─ 实时VaR      │
│ ─ 实时  │ ─ Pricer │ ─ 时间  │ ─ 止损限仓     │
├──────────┴──────────┴──────────┴─────────────────┤
│                   交易所API层                      │
│                  (FIX/WebSocket)                     │
└──────────────────────────────────────────────────┘
```

---

**下一篇**: 波动率交易 — 曲面套利与delta对冲
