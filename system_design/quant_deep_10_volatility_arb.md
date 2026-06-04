# 波动率套利：曲面套利与策略

## 1. 波动率曲面

**隐含波动率（IV）** 不是常数 — 在不同行权价和到期日之间变化：

```
           行权价（Strike）
          K-20  K-10  ATM  K+10  K+20
到期日 T+1  25%   22%   20%   22%   25%  ← 波动率微笑（Smile）
到期日 T+7  24%   21%   19%   21%   24%  ← 波动率 skew
到期日 T+30 23%   20%   18%   19%   22%  ← 期限结构
```

### 波动率微笑（Volatility Smile）

1987年股灾后出现的现象：
- **OTM Put** 的IV > ATM Put的IV（尾部风险定价）
- 股票市场呈现 **Skew**（左偏）：低行权价IV更高
- 外汇市场呈现 **Smile**（对称）：两端都高

### 期限结构（Term Structure）

- **远期波动率曲线**：不同到期日的隐含波动率
- 牛市：近月 < 远月（Contango，波动率预期上升）
- 恐慌：近月 > 远月（Backwardation，恐慌即时）

## 2. 波动率曲面套利策略

### 策略1：日历价差（Calendar Spread）

```
卖近月ATM期权 + 买远月ATM期权
→ 赌近月IV相对远月下降
```

```python
def calendar_spread_pnl(near_iv, far_iv, position_size):
    """
    日历价差：做多VIX期货的替代方案
    输入：near_iv, far_iv 为百分比格式如 20.5
    """
    near_price = bs_price(option_type='call', iv=near_iv/100, ...)
    far_price = bs_price(option_type='call', iv=far_iv/100, ...)
    
    # 卖出近月，买入远月（净支出）
    net_cost = far_price - near_price
    return -net_cost * position_size  # 负值为成本，后续波动变化
```

### 策略2：风险反转（Risk Reversal）

```
卖OTM Put + 买OTM Call
→ 对方向性波动率不对称的赌注
→ 偏多：Call的IV被低估，Put的IV被高估
```

### 策略3：蝶式价差（Butterfly）

```
买1份K-Δ Call + 卖2份K Call + 买1份K+Δ Call
→ 赌波动率处于一个窄区间（低IV环境）
→ 最大利润在ATM，两端亏损有限
```

## 3. Delta对冲实战

```python
class DeltaHedger:
    def __init__(self, initial_positions, hedge_cost=0.0001):
        """
        initial_positions: [{'option': ..., 'qty': 10}, ...]
        hedge_cost: 每笔对冲的交易成本比例
        """
        self.positions = initial_positions
        self.hedge_cost = hedge_cost
        self.hedge_position = 0  # 标的持仓
        self.trades = 0
    
    def rebalance(self, spot_price, spot_delta=1.0):
        """
        对冲逻辑：
        1. 计算总Delta
        2. 计算目标对冲量
        3. 考虑交易成本，确定是否对冲
        """
        total_delta = sum(
            pos['qty'] * calc_delta(pos['option'], spot_price)
            for pos in self.positions
        )
        
        target_hedge = -total_delta  # 卖出标的中和期权Delta
        delta_change = abs(target_hedge - self.hedge_position)
        
        # 交易成本阈值：Delta变化超过0.5%才对冲
        if delta_change > 0.005 * spot_price:
            cost = delta_change * spot_price * self.hedge_cost
            self.hedge_position = target_hedge
            self.trades += 1
            return {'hedge_qty': delta_change, 'cost': cost, 'new_pos': self.hedge_position}
        
        return {'hedge_qty': 0, 'cost': 0, 'new_pos': self.hedge_position}
```

## 4. 波动率策略比较

| 策略 | 方向性 | 收益来源 | 适用环境 |
|------|--------|---------|---------|
| 做多波动率（买跨式） | 中性 | IV上升 | 财报/黑天鹅 |
| 做空波动率（卖跨式） | 中性 | Theta + Vega | 低波动横盘 |
| 日历价差 | 中性 | 期限结构扭曲 | 正常contango |
| 风险反转 | 偏多/偏空 | Skew不对称 | 恐慌时Put过于昂贵 |
| Delta 1期权 | 方向性 | 期权杠杆 | 趋势明确 |

---

**下一篇**: 高频交易 — HFT架构与延迟优化
