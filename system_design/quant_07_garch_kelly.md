# GARCH波动率 + Kelly仓位管理

> 从GARCH(1,1)实现到动态仓位系统 — 集成到monitor_v3

---

## 1. GARCH(1,1) numpy实现

```python
import numpy as np
from scipy import optimize

class GARCH11:
    """GARCH(1,1) 波动率模型 — 纯numpy实现"""
    
    def __init__(self):
        self.params = None  # [omega, alpha, beta]
        self.conditional_vol = None
        self.log_likelihood = None
    
    def _compute_variance(self, returns, omega, alpha, beta):
        """递归计算条件方差"""
        T = len(returns)
        sigma2 = np.zeros(T)
        sigma2[0] = np.var(returns)
        
        for t in range(1, T):
            sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
        
        return sigma2
    
    def _neg_log_likelihood(self, params, returns):
        """负对数似然函数"""
        omega, alpha, beta = params
        
        # 参数约束
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
            return 1e10
        
        sigma2 = self._compute_variance(returns, omega, alpha, beta)
        sigma2 = np.maximum(sigma2, 1e-8)  # 防止除零
        
        # 正态分布对数似然
        ll = -0.5 * np.sum(np.log(2 * np.pi * sigma2[1:]) + 
                           returns[1:]**2 / sigma2[1:])
        return -ll  # 返回负值供最小化
    
    def fit(self, returns):
        """拟合GARCH(1,1)参数"""
        result = optimize.minimize(
            self._neg_log_likelihood,
            x0=[np.var(returns) * 0.05, 0.1, 0.8],
            args=(returns,),
            bounds=[(1e-8, None), (0, 1), (0, 1)],
            method='L-BFGS-B'
        )
        
        self.params = result.x
        self.log_likelihood = -result.fun
        self.conditional_vol = np.sqrt(
            self._compute_variance(returns, *self.params))
        
        return self
    
    def predict(self, returns, steps=5):
        """预测未来波动率"""
        if self.params is None:
            raise ValueError("请先调用 fit()")
        
        omega, alpha, beta = self.params
        
        # 最后一天的方差
        sigma2_t = self.conditional_vol[-1]**2
        last_return = returns[-1]
        
        predictions = []
        for i in range(steps):
            sigma2_t1 = omega + alpha * last_return**2 + beta * sigma2_t
            predictions.append(np.sqrt(sigma2_t1))
            
            # 更新：长期均值回归
            sigma2_t = sigma2_t1
            last_return = 0  # 预期收益为0
        
        return np.array(predictions)
    
    def get_long_run_vol(self):
        """长期平均波动率 sqrt(omega / (1 - alpha - beta))"""
        omega, alpha, beta = self.params
        long_run_var = omega / (1 - alpha - beta)
        return np.sqrt(long_run_var)

# 测试
np.random.seed(42)
n = 1000

# 生成GARCH数据
true_omega = 0.000012
true_alpha = 0.12
true_beta = 0.85
true_long_vol = np.sqrt(true_omega / (1 - true_alpha - true_beta))

returns = np.zeros(n)
sigma2 = np.ones(n) * true_long_vol**2

for t in range(1, n):
    sigma2[t] = true_omega + true_alpha * returns[t-1]**2 + true_beta * sigma2[t-1]
    returns[t] = np.sqrt(sigma2[t]) * np.random.randn()

garch = GARCH11().fit(returns)
pred_vol = garch.predict(returns, steps=5)

print("GARCH(1,1)拟合结果:")
print(f"  omega: {garch.params[0]:.6f} (真实={true_omega:.6f})")
print(f"  alpha: {garch.params[1]:.4f} (真实={true_alpha:.2f})")
print(f"  beta:  {garch.params[2]:.4f} (真实={true_beta:.2f})")
print(f"  α+β:   {garch.params[1]+garch.params[2]:.4f} (应<1)")
print(f"  长期波动率: {garch.get_long_run_vol():.4f} (真实={true_long_vol:.4f})")
print(f"  未来5期波动率预测: {pred_vol}")
```

## 2. Kelly公式推导与实现

```python
class KellyCriterion:
    """Kelly仓位管理"""
    
    @staticmethod
    def full_kelly(win_prob, win_loss_ratio):
        """
        完整Kelly公式（已知胜率和赔率）
        f* = (p * (b + 1) - 1) / b
        其中 p=胜率, b=赔率(赢/输的比率)
        """
        p = win_prob
        b = win_loss_ratio
        f = (p * (b + 1) - 1) / b
        return max(0, f)  # 非负
    
    @staticmethod
    def partial_kelly(full_kelly_fraction, k=0.25):
        """分数Kelly：full Kelly * fraction"""
        return full_kelly_fraction * k
    
    @staticmethod
    def kelly_from_returns(returns_series, confidence=0.25):
        """从历史收益率估计Kelly仓位
        f* = μ / σ² （假设收益率正态分布）
        """
        mu = np.mean(returns_series)
        sigma = np.std(returns_series)
        if sigma == 0:
            return 0
        f = mu / (sigma**2)
        return max(0, min(f * confidence, 1))  # 置信度缩放
    
    @staticmethod
    def half_kelly_vol_target(vol_target, predicted_vol):
        """波动率目标化的Kelly
        f = vol_target / predicted_vol
        """
        if predicted_vol <= 0:
            return 0
        f = vol_target / predicted_vol
        return min(f, 1)  # 满仓封顶

# 测试不同Kelly
np.random.seed(42)
print("Kelly仓位计算:")

# 情景1：高胜率交易
f1 = KellyCriterion.full_kelly(0.7, 1.5)  # 胜率70%，赔率1.5
print(f"  高胜率交易(70%/1.5): f*={f1:.2%}")

# 情境2：趋势跟踪（低胜率高赔率）
f2 = KellyCriterion.full_kelly(0.35, 3.0)  # 胜率35%，赔率3
print(f"  趋势跟踪(35%/3.0): f*={f2:.2%}")

# 情境3：分数Kelly
print(f"  分数Kelly(25%): {KellyCriterion.partial_kelly(f1):.2%}")
print(f"  分数Kelly(50%): {KellyCriterion.partial_kelly(f1, 0.5):.2%}")

# 情景4：从历史收益估计
sim_returns = np.random.normal(0.001, 0.02, 500)  # 日均0.1%收益, 2%波动
f3 = KellyCriterion.kelly_from_returns(sim_returns)
print(f"  历史估计Kelly: f={f3:.2%} (μ={sim_returns.mean():.4f}, σ={sim_returns.std():.4f})")
```

## 3. 动态仓位管理系统

```python
class DynamicPositionSizer:
    """基于GARCH+Kelly的动态仓位管理器"""
    
    def __init__(self, vol_target=0.15, max_leverage=1.0, 
                 kelly_fraction=0.25, lookback=252):
        """
        vol_target: 目标年化波动率（默认15%）
        max_leverage: 最大杠杆
        kelly_fraction: 分数Kelly系数
        """
        self.vol_target = vol_target
        self.max_leverage = max_leverage
        self.kelly_fraction = kelly_fraction
        self.lookback = lookback
        self.garch = GARCH11()
        self.fitted = False
    
    def calc_position_size(self, returns, current_signal=1.0):
        """计算当前仓位
        
        Args:
            returns: 历史收益率序列（日频）
            current_signal: 策略信号强度 [0, 1]
        
        Returns:
            position: 仓位比例 [0, 1]
            vol: 预测波动率（年化）
        """
        if len(returns) < 50:
            return 0.5, 0.2
        
        # 拟合GARCH
        self.garch.fit(returns)
        self.fitted = True
        
        # 预测未来波动率
        daily_vol_pred = self.garch.predict(returns, steps=1)[0]
        annual_vol_pred = daily_vol_pred * np.sqrt(252)
        
        # 波动率目标化仓位
        vol_targeted = self.vol_target / (annual_vol_pred + 1e-6)
        
        # Kelly约束
        mu = np.mean(returns) * 252  # 年化收益
        sigma = np.std(returns) * np.sqrt(252)  # 年化波动
        kelly_f = mu / (sigma**2 + 1e-10) if sigma > 0 else 0
        kelly_f = max(0, kelly_f * self.kelly_fraction)
        
        # 综合 = min(波动率目标化, Kelly, 最大杠杆, 1)
        position = min(vol_targeted, kelly_f, self.max_leverage, 1.0)
        
        # 信号强度修正
        position *= current_signal
        
        return position, annual_vol_pred
    
    def get_position_summary(self, returns, current_signal=1.0):
        """详细的仓位建议报告"""
        pos, vol = self.calc_position_size(returns, current_signal)
        
        if self.fitted:
            omega, alpha, beta = self.garch.params
            long_vol = self.garch.get_long_run_vol() * np.sqrt(252)
        else:
            omega = alpha = beta = long_vol = 0
        
        mu = np.mean(returns) * 252
        sigma = np.std(returns) * np.sqrt(252)
        
        print("=" * 50)
        print("仓位建议报告")
        print("=" * 50)
        print(f"GARCH状态:")
        print(f"  参数: ω={omega:.6f}, α={alpha:.4f}, β={beta:.4f}")
        print(f"  α+β={alpha+beta:.4f} (半衰期={np.log(0.5)/np.log(alpha+beta):.0f}天)")
        print(f"  当前波动率: {vol:.2%} (年化)")
        print(f"  长期波动率: {long_vol:.2%} (年化)")
        print(f"\n仓位计算:")
        print(f"  波动率目标化: {self.vol_target/(vol+1e-6):.2%}")
        print(f"  Kelly建议: {max(0, mu/(sigma**2+1e-10)*self.kelly_fraction):.2%}")
        print(f"  信号强度: {current_signal:.2f}")
        print(f"  → 建议仓位: {pos:.2%}")
        print(f"\n风控:")
        print(f"  止损建议: {vol * 2:.2%} (2σ)")
        print(f"  警戒线: {vol * 1.5:.2%}")

# 测试
np.random.seed(42)
returns = np.random.normal(0.0005, 0.015, 500)  # 日均0.05%收益, 1.5%波动

sizer = DynamicPositionSizer(vol_target=0.15, kelly_fraction=0.25)
pos, vol = sizer.calc_position_size(returns)
print(f"建议仓位: {pos:.2%}, 预测年化波动: {vol:.2%}")

sizer.get_position_summary(returns)
```

## 4. 集成到monitor_v3

```python
class GarchKellyIntegrator:
    """GARCH+Kelly 集成接口 — 可直接嵌入monitor_v3"""
    
    def __init__(self, config=None):
        self.config = config or {
            'vol_target': 0.15,
            'kelly_fraction': 0.25,
            'max_leverage': 1.0,
            'lookback': 252,
            'rebalance_freq': 5  # 每5日重算一次
        }
        self.sizer = DynamicPositionSizer(
            vol_target=self.config['vol_target'],
            kelly_fraction=self.config['kelly_fraction'],
            max_leverage=self.config['max_leverage'],
            lookback=self.config['lookback']
        )
        self.last_calc_day = -1
        self.current_position = 0.5
        self.position_history = []
    
    def update(self, returns, current_signal=1.0, day_index=0):
        """
        monitor_v3调用接口
        每rebalance_freq日重算一次仓位
        """
        if day_index - self.last_calc_day >= self.config['rebalance_freq']:
            pos, vol = self.sizer.calc_position_size(returns, current_signal)
            self.current_position = pos
            self.last_calc_day = day_index
            self.position_history.append((day_index, pos, vol))
        
        return self.current_position
    
    def get_alerts(self):
        """返回风控警报（供monitor_v3推送用）"""
        if not self.position_history:
            return []
        
        _, _, vol = self.position_history[-1]
        alerts = []
        
        if vol > 0.25:  # 年化波动 > 25%
            alerts.append(('WARNING', f'高波动：{vol:.1%}，建议减仓'))
        if self.current_position < 0.3:
            alerts.append(('INFO', f'低仓位：{self.current_position:.0%}，市场波动大'))
        if self.current_position > 0.9:
            alerts.append(('INFO', f'高仓位：{self.current_position:.0%}，注意回撤风险'))
        
        return alerts

# 模拟集成测试
np.random.seed(42)
n = 500
returns = np.random.normal(0.0005, 0.015, n)
signal = np.ones(n)
signal[200:300] = 0.5  # 中间100天信号减半
signal[350:] = 0.8

integrator = GarchKellyIntegrator()
positions = [integrator.update(returns[:i+1], signal[i], i) for i in range(n)]

print(f"仓位范围: {min(positions):.2%} ~ {max(positions):.2%}")
print(f"最终仓位: {positions[-1]:.2%}")
print(f"重算次数: {len(integrator.position_history)}")

alerts = integrator.get_alerts()
for level, msg in alerts:
    print(f"  [{level}] {msg}")
```

## 5. 完整策略回测

```python
class VolManagedStrategy:
    """波动率管理的趋势跟踪策略"""
    
    def __init__(self):
        self.sizer = DynamicPositionSizer(vol_target=0.15)
        self.position_log = []
    
    def run(self, prices):
        n = len(prices)
        equity = np.ones(n) * 100000
        position = 0.0
        
        returns = prices.pct_change().dropna().values
        
        for i in range(60, n):  # 需要60期历史
            window_returns = returns[:i]
            
            # 趋势信号：简单MA交叉
            price = prices.iloc[:i+1]
            ma_fast = price.iloc[-20:].mean()
            ma_slow = price.iloc[-60:].mean()
            signal = 1.0 if ma_fast > ma_slow else 0.0
            
            # 仓位计算
            pos, vol = self.sizer.calc_position_size(window_returns, signal)
            position = pos
            
            # 盈亏
            daily_ret = prices.iloc[i] / prices.iloc[i-1] - 1
            equity[i] = equity[i-1] * (1 + daily_ret * position)
            
            self.position_log.append(position)
        
        total_ret = equity[-1] / equity[60] - 1
        annual = (1 + total_ret) ** (252 / (n - 60)) - 1
        dd = (equity[60:] - equity[60:].cummax()) / equity[60:].cummax()
        
        print("波动率管理策略回测:")
        print(f"  总收益: {total_ret:.2%}")
        print(f"  年化: {annual:.2%}")
        print(f"  最大回撤: {dd.min():.2%}")
        print(f"  平均仓位: {np.mean(self.position_log):.2%}")
        print(f"  仓位标准差: {np.std(self.position_log):.2%}")
        
        return equity[60:]

# 测试
np.random.seed(42)
trend = np.cumsum(np.random.normal(0.0005, 0.015, 600))
prices = pd.Series(trend + 100, 
                    index=pd.date_range('2024-01-01', periods=600))

vms = VolManagedStrategy()
equity = vms.run(prices)
```

## 实战建议

```python
print("""
实战集成建议：

1. 集成到monitor_v3
   - 在每日评分后调用 GarchKellyIntegrator.update()
   - 低波动→高仓位，高波动→低仓位
   - 风控警报走现有alert推送通道

2. 参数选择
   - 目标波动率: 10%~20%（取决于风险偏好）
   - Kelly分数: 25%（保守），50%（积极）
   - 重算频率: 每周一次足够

3. C++加速方向
   - GARCH似然计算适合并行化（多参数并行搜索）
   - 可用libkds的环形缓冲区管理收益率窗口
   - KVStore存储波动率预测日志

4. 回测验证
   - 先跑10年历史数据验证波动率预测能力
   - 对比固定仓位 vs 动态仓位的夏普改善
""")
```
