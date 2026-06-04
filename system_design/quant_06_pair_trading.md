# 协整配对交易回测

> 从协整发现到资金管理 — 完整配对交易回测框架

---

## 1. 配对发现

```python
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint, adfuller
from scipy import stats

class PairFinder:
    """在股票池中发现协整对"""
    
    def __init__(self, price_df, p_threshold=0.05):
        """
        price_df: DataFrame, rows=日期, columns=股票代码
        """
        self.price_df = price_df
        self.p_threshold = p_threshold
        self.pairs = []
    
    def find_pairs(self):
        """遍历所有股票对做协整检验"""
        n = self.price_df.shape[1]
        stocks = self.price_df.columns
        
        for i in range(n):
            for j in range(i+1, n):
                s1, s2 = stocks[i], stocks[j]
                p1 = self.price_df[s1].dropna()
                p2 = self.price_df[s2].dropna()
                
                # 取交集
                common = p1.index.intersection(p2.index)
                if len(common) < 60:  # 至少60个交易日
                    continue
                
                p1 = p1.loc[common]
                p2 = p2.loc[common]
                
                try:
                    score, pvalue, crit = coint(p1, p2)
                    
                    if pvalue < self.p_threshold:
                        # 计算hedge ratio
                        slope, intercept, *_ = stats.linregress(p2, p1)
                        
                        self.pairs.append({
                            'stock1': s1,
                            'stock2': s2,
                            'p_value': pvalue,
                            'hedge_ratio': slope,
                            'intercept': intercept,
                            'n_obs': len(common)
                        })
                except:
                    continue
        
        # 按p值排序
        self.pairs.sort(key=lambda x: x['p_value'])
        return self.pairs

# 测试
np.random.seed(42)
n_days = 500
stocks = [f'Stock_{i}' for i in range(20)]

# 生成相关价格序列
common_trend = np.cumsum(np.random.normal(0, 0.5, n_days))

price_data = {}
# 前5只股票与common趋势协整
for i in range(5):
    price_data[stocks[i]] = common_trend + np.random.normal(0, 2, n_days) + i * 50

# 后15只是噪声
for i in range(5, 20):
    price_data[stocks[i]] = np.cumsum(np.random.normal(0, 1, n_days)) + 100

price_df = pd.DataFrame(price_data, index=pd.date_range('2024-01-01', periods=n_days))

finder = PairFinder(price_df, p_threshold=0.05)
pairs = finder.find_pairs()
print(f"发现 {len(pairs)} 个协整对")
for p in pairs[:3]:
    print(f"  {p['stock1']} - {p['stock2']}: p={p['p_value']:.4f}, "
          f"hedge={p['hedge_ratio']:.3f}, obs={p['n_obs']}")
```

## 2. 价差分析与交易信号

```python
class SpreadAnalyzer:
    """价差分析：归一化、平稳性检验、信号生成"""
    
    def __init__(self, hedge_ratio, intercept=0):
        self.hedge_ratio = hedge_ratio
        self.intercept = intercept
        self.spread_mean = None
        self.spread_std = None
    
    def calc_spread(self, price1, price2):
        """计算价差 spread = P1 - β * P2 - α"""
        spread = price1 - self.hedge_ratio * price2 - self.intercept
        return spread
    
    def normalize_spread(self, spread, window=60):
        """滚动归一化价差 (z-score)"""
        mean = spread.rolling(window).mean()
        std = spread.rolling(window).std()
        zscore = (spread - mean) / (std + 1e-10)
        return zscore
    
    def generate_signals(self, zscore, entry=2.0, exit=0.5):
        """
        交易信号：
        zscore >  entry: 做空价差（卖P1买P2）
        zscore < -entry: 做多价差（买P1卖P2）
        |zscore| < exit: 平仓
        """
        signals = np.zeros(len(zscore))
        position = 0  # 0=空仓, 1=做多价差, -1=做空价差
        
        for i in range(len(zscore)):
            z = zscore[i]
            
            if position == 0:
                if z > entry:
                    signals[i] = -1  # 做空价差
                    position = -1
                elif z < -entry:
                    signals[i] = 1   # 做多价差
                    position = 1
            elif position == 1:  # 做多价差中
                if z > -exit:
                    signals[i] = 0  # 平仓
                    position = 0
                else:
                    signals[i] = 1  # 继续持仓
            elif position == -1:  # 做空价差中
                if z < exit:
                    signals[i] = 0  # 平仓
                    position = 0
                else:
                    signals[i] = -1  # 继续持仓
        
        return pd.Series(signals, index=zscore.index)

# 测试
n = 500
p1 = np.cumsum(np.random.normal(0, 0.3, n)) + np.random.normal(0, 0.5, n) + 100
p2 = p1 * 1.5 + np.random.normal(0, 2, n) + 50  # 价差平稳

p1 = pd.Series(p1, index=pd.date_range('2024-01-01', periods=n))
p2 = pd.Series(p2, index=pd.date_range('2024-01-01', periods=n))

analyzer = SpreadAnalyzer(hedge_ratio=1.5, intercept=50)
spread = analyzer.calc_spread(p1, p2)
zscore = analyzer.normalize_spread(spread, window=60)
signals = analyzer.generate_signals(zscore)

print(f"价差均值: {spread.mean():.2f}, 标准差: {spread.std():.2f}")
print(f"信号统计: 做多={sum(signals==1)}次, 做空={sum(signals==-1)}次, 平仓={sum(signals==0)}个交易日")
```

## 3. 完整回测框架

```python
class PairTradingBacktest:
    """协整配对交易回测"""
    
    def __init__(self, price1, price2, hedge_ratio, intercept=0,
                 entry_z=2.0, exit_z=0.5, stop_loss=3.0, 
                 initial_capital=100000, commission=0.0003):
        """
        entry_z: 开仓阈值
        exit_z: 平仓阈值
        stop_loss: 止损阈值（z-score）
        """
        self.price1 = price1
        self.price2 = price2
        self.hedge_ratio = hedge_ratio
        self.intercept = intercept
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.stop_loss = stop_loss
        self.initial_capital = initial_capital
        self.commission = commission
        
        self.spread = None
        self.zscore = None
        self.signals = None
        self.portfolio = None
    
    def prepare_data(self, window=60):
        """准备价差和信号"""
        self.spread = self.price1 - self.hedge_ratio * self.price2 - self.intercept
        self.zscore = (self.spread - self.spread.rolling(window).mean()) / \
                      (self.spread.rolling(window).std() + 1e-10)
        
        # 生成信号
        self.signals = np.zeros(len(self.zscore))
        position = 0
        
        for i in range(window, len(self.zscore)):
            z = self.zscore.iloc[i]
            
            # 止损检查
            if position != 0 and abs(z) > self.stop_loss:
                self.signals[i] = 0  # 强制平仓
                position = 0
                continue
            
            if position == 0:
                if z > self.entry_z:
                    self.signals[i] = -1
                    position = -1
                elif z < -self.entry_z:
                    self.signals[i] = 1
                    position = 1
            elif position == 1:
                self.signals[i] = 1 if z < -self.exit_z else 0
                position = self.signals[i]
            elif position == -1:
                self.signals[i] = -1 if z > self.exit_z else 0
                position = self.signals[i]
        
        self.signals = pd.Series(self.signals, index=self.price1.index)
    
    def run(self, window=60):
        """执行回测"""
        self.prepare_data(window)
        n = len(self.price1)
        
        # 记录每日持仓
        positions_p1 = np.zeros(n)
        positions_p2 = np.zeros(n)
        cash = self.initial_capital
        equity = np.zeros(n)
        trades = []
        
        # 初始仓位状态
        pos_p1 = 0
        pos_p2 = 0
        cost_basis_p1 = 0
        cost_basis_p2 = 0
        
        for i in range(n):
            if i < window:
                equity[i] = cash
                continue
            
            signal = self.signals.iloc[i]
            p1 = self.price1.iloc[i]
            p2 = self.price2.iloc[i]
            
            # 执行信号
            if signal != 0 and pos_p1 == 0:  # 开仓
                # 做多价差：买P1卖P2
                # 做空价差：卖P1买P2
                units = cash * 0.8 / (abs(p1) + abs(self.hedge_ratio * p2))
                
                if signal == 1:  # 做多价差
                    pos_p1 = units
                    pos_p2 = -units * self.hedge_ratio
                else:  # 做空价差
                    pos_p1 = -units
                    pos_p2 = units * self.hedge_ratio
                
                cost_basis_p1 = p1
                cost_basis_p2 = p2
                
                # 扣除交易成本
                trade_cost = (abs(pos_p1) * p1 + abs(pos_p2) * p2) * self.commission
                cash -= trade_cost
                
                trades.append({
                    'date': self.price1.index[i],
                    'action': 'open',
                    'signal': signal,
                    'p1_price': p1,
                    'p2_price': p2,
                    'units': units
                })
            
            elif signal == 0 and pos_p1 != 0:  # 平仓
                # 计算盈亏
                pnl_p1 = pos_p1 * (p1 - cost_basis_p1)
                pnl_p2 = pos_p2 * (p2 - cost_basis_p2)
                pnl = pnl_p1 + pnl_p2
                
                # 平仓交易成本
                close_cost = (abs(pos_p1) * p1 + abs(pos_p2) * p2) * self.commission
                
                cash += pnl - close_cost
                
                trades.append({
                    'date': self.price1.index[i],
                    'action': 'close',
                    'pnl': pnl,
                    'cost': close_cost,
                    'duration': i - len([t for t in trades if t['action']=='open']) if trades else 0
                })
                
                pos_p1 = 0
                pos_p2 = 0
            
            # 市值
            market_value = pos_p1 * p1 + pos_p2 * p2
            equity[i] = cash + market_value
        
        self.portfolio = pd.Series(equity, index=self.price1.index)
        
        # 绩效指标
        returns = self.portfolio.pct_change().dropna()
        total_return = (self.portfolio.iloc[-1] / self.initial_capital - 1)
        annual_return = (1 + total_return) ** (252 / n) - 1
        sharpe = returns.mean() / (returns.std() + 1e-10) * np.sqrt(252)
        max_dd = self._max_drawdown()
        win_rate = self._win_rate(trades)
        
        print("=" * 50)
        print("配对交易回测结果")
        print("=" * 50)
        print(f"总收益: {total_return:.2%}")
        print(f"年化收益: {annual_return:.2%}")
        print(f"夏普比率: {sharpe:.2f}")
        print(f"最大回撤: {max_dd:.2%}")
        print(f"胜率: {win_rate:.2%}")
        print(f"交易次数: {len([t for t in trades if t['action']=='open'])}")
        
        return self.portfolio, trades
    
    def _max_drawdown(self):
        peak = self.portfolio.expanding().max()
        dd = (self.portfolio - peak) / peak
        return dd.min()
    
    def _win_rate(self, trades):
        closed = [t for t in trades if t['action'] == 'close']
        if not closed:
            return 0
        wins = sum(1 for t in closed if t.get('pnl', 0) > 0)
        return wins / len(closed)

# 测试回测
np.random.seed(42)
n = 500

# 生成协整价格序列
spread_series = np.random.normal(0, 2, n)  # 平稳价差
common_drift = np.cumsum(np.random.normal(0.001, 0.5, n))

price_a = common_drift + spread_series * 0.7 + 100
price_b = (common_drift - spread_series * 0.3) / 1.2 + 50

pa = pd.Series(price_a, index=pd.date_range('2024-01-01', periods=n))
pb = pd.Series(price_b, index=pd.date_range('2024-01-01', periods=n))

bt = PairTradingBacktest(pa, pb, hedge_ratio=1.2, intercept=50,
                          entry_z=2.0, exit_z=0.5, stop_loss=3.0)

portfolio, trades = bt.run(window=60)
```

## 4. 滚动窗口参数更新

```python
class RollingPairTrader:
    """滚动窗口参数更新的配对交易"""
    
    def __init__(self, price1, price2, 
                 roll_window=120,  # 滚动窗口大小
                 update_freq=20,   # 每N日更新一次参数
                 entry_z=2.0, exit_z=0.5):
        
        self.price1 = price1
        self.price2 = price2
        self.roll_window = roll_window
        self.update_freq = update_freq
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.hedge_ratio_history = []
    
    def update_hedge_ratio(self, p1_window, p2_window):
        """滚动窗口更新hedge ratio"""
        slope, intercept, _, _, _ = stats.linregress(p2_window, p1_window)
        return slope, intercept
    
    def run(self):
        n = len(self.price1)
        portfolio = np.ones(n) * 100000
        position = 0  # 0=空, 1=多价差, -1=空价差
        hedge = 1.0
        intercept = 0.0
        
        for i in range(self.roll_window, n):
            # 每update_freq日更新参数
            if i % self.update_freq == 0:
                p1_win = self.price1.iloc[i-self.roll_window:i]
                p2_win = self.price2.iloc[i-self.roll_window:i]
                hedge, intercept = self.update_hedge_ratio(p1_win, p2_win)
                self.hedge_ratio_history.append((i, hedge, intercept))
            
            # 计算当前价差z-score
            spread = self.price1.iloc[i] - hedge * self.price2.iloc[i] - intercept
            spread_hist = self.price1.iloc[i-self.roll_window:i] - \
                          hedge * self.price2.iloc[i-self.roll_window:i] - intercept
            
            z = (spread - spread_hist.mean()) / (spread_hist.std() + 1e-10)
            
            # 交易逻辑
            if position == 0 and abs(z) > self.entry_z:
                position = 1 if z < -self.entry_z else -1
            elif position != 0 and abs(z) < self.exit_z:
                position = 0
            
            # 更新市值
            pnl = 0
            if position != 0:
                spread_change = (self.price1.iloc[i] - self.price1.iloc[i-1]) \
                                - hedge * (self.price2.iloc[i] - self.price2.iloc[i-1])
                pnl = position * spread_change * 1000
            
            portfolio[i] = portfolio[i-1] + pnl
        
        # 绩效
        total_ret = portfolio[-1] / portfolio[self.roll_window] - 1
        annual_ret = (1 + total_ret) ** (252 / (n - self.roll_window)) - 1
        returns = pd.Series(portfolio).pct_change().dropna()
        sharpe = returns.mean() / (returns.std() + 1e-10) * np.sqrt(252)
        
        print("滚动参数更新回测:")
        print(f"  总收益: {total_ret:.2%}")
        print(f"  年化收益: {annual_ret:.2%}")
        print(f"  夏普: {sharpe:.2f}")
        print(f"  参数更新次数: {len(self.hedge_ratio_history)}")
        print(f"  Hedge Ratio范围: {min(h for _,h,_ in self.hedge_ratio_history):.3f} ~ "
              f"{max(h for _,h,_ in self.hedge_ratio_history):.3f}")
        
        return pd.Series(portfolio, index=self.price1.index)

rpt = RollingPairTrader(pa, pb)
rolling_portfolio = rpt.run()
```

## 5. 多对配对资金管理

```python
class MultiPairPortfolio:
    """同时交易多个配对"""
    
    def __init__(self, pairs_config, initial_capital=100000):
        """
        pairs_config: [{'p1': Series, 'p2': Series, 'hedge': float}, ...]
        """
        self.pairs = [PairTradingBacktest(
            p['p1'], p['p2'], p['hedge'], p.get('intercept', 0)
        ) for p in pairs_config]
        
        self.initial_capital = initial_capital
        self.n_pairs = len(pairs_config)
    
    def run_all(self, window=60):
        """同时运行所有配对，等权重分配资金"""
        capital_per_pair = self.initial_capital / self.n_pairs
        
        portfolios = []
        for i, pair in enumerate(self.pairs):
            pair.initial_capital = capital_per_pair
            port, trades = pair.run(window)
            portfolios.append(port)
        
        # 组合净值 = 各配对净值之和
        combined = sum(portfolios) / capital_per_pair * self.initial_capital
        
        combined_returns = combined.pct_change().dropna()
        total_ret = combined.iloc[-1] / combined.iloc[window] - 1
        annual = (1 + total_ret) ** (252 / (len(combined) - window)) - 1
        sharpe = combined_returns.mean() / (combined_returns.std() + 1e-10) * np.sqrt(252)
        
        print("=" * 50)
        print(f"多配对组合 ({self.n_pairs}对)")
        print("=" * 50)
        print(f"总收益: {total_ret:.2%}")
        print(f"年化收益: {annual:.2%}")
        print(f"组合夏普: {sharpe:.2f}")
        print(f"最大回撤: {self._max_drawdown(combined):.2%}")
        
        return combined
    
    def _max_drawdown(self, portfolio):
        peak = portfolio.expanding().max()
        dd = (portfolio - peak) / peak
        return dd.min()

# 创建多个配对测试
np.random.seed(42)
n = 500
pairs_config = []

for pair_idx in range(3):
    common = np.cumsum(np.random.normal(0.001 * (pair_idx+1), 0.5, n))
    p1 = common + np.random.normal(0, 1.5, n) + 100
    p2 = (common + np.random.normal(0, 1.5, n)) / 1.3 + 30 + pair_idx * 10
    
    pa = pd.Series(p1, index=pd.date_range('2024-01-01', periods=n))
    pb = pd.Series(p2, index=pd.date_range('2024-01-01', periods=n))
    
    pairs_config.append({'p1': pa, 'p2': pb, 'hedge': 1.3, 'intercept': 30 + pair_idx * 10})

mpp = MultiPairPortfolio(pairs_config, 300000)
combined_portfolio = mpp.run_all(window=120)
```

## 实战要点

```python
print("""
实战注意事项：

1. 选股池选择
   - 同行业股票协整概率更高（银行/保险/地产）
   - 流通市值相近
   - 日均成交额 > 5000万

2. 参数设置
   - entry_z=2.0（约95%分位），适合日频
   - roll_window=60（3个月），平衡稳定性和灵敏度
   - 止损设为 entry_z * 1.5

3. 风险控制
   - 单配对最大仓位 < 15%
   - 总配对敞口 < 50%
   - 定期重平衡（每月）
   - 关注价差结构突变

4. C++加速建议
   - 价差计算用环形缓冲区（参考libkds的rbuf）
   - rolling窗口统计用前缀和
   - 协整检验的ADF统计量可以用numpy优化
""")
```
