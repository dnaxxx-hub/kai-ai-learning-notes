# 时间序列分析深潜

> 从平稳性到卡尔曼滤波 — 金融时序分析实战

---

## 1. 平稳性

### 1.1 严平稳 vs 弱平稳

```python
import numpy as np
import matplotlib.pyplot as plt

# 弱平稳的3个条件（金融数据通常只要求弱平稳）：
# 1. 均值恒定：E[Y_t] = μ（与t无关）
# 2. 方差恒定：Var[Y_t] = σ²（与t无关）
# 3. 自协方差只与滞后k有关：Cov[Y_t, Y_{t+k}] = γ(k)

# 生成平稳 vs 非平稳序列
np.random.seed(42)
n = 1000

# 白噪声（平稳）
white_noise = np.random.normal(0, 1, n)

# 随机游走（非平稳）
random_walk = np.cumsum(np.random.normal(0, 1, n))

# 带趋势（非平稳）
trend = np.arange(n) * 0.1 + np.random.normal(0, 1, n)

# 可视化
fig, axes = plt.subplots(3, 1, figsize=(12, 8))
axes[0].plot(white_noise, label='White Noise (Stationary)')
axes[0].axhline(y=0, color='r', linestyle='--', alpha=0.3)
axes[0].legend()
axes[1].plot(random_walk, label='Random Walk (Non-stationary)')
axes[1].legend()
axes[2].plot(trend, label='Trend + Noise (Non-stationary)')
axes[2].legend()
plt.tight_layout()
plt.savefig('/tmp/stationarity.png')
print("Plots saved")
```

### 1.2 ADF检验

```python
from statsmodels.tsa.stattools import adfuller
import warnings
warnings.filterwarnings('ignore')

def adf_test(series, name=''):
    result = adfuller(series, autolag='AIC')
    print(f"--- {name} ---")
    print(f"ADF Statistic: {result[0]:.4f}")
    print(f"p-value: {result[1]:.4f}")
    print(f"Critical Values:")
    for key, value in result[4].items():
        print(f"  {key}: {value:.4f}")
    print(f"结论: {'平稳' if result[1] < 0.05 else '非平稳'}")
    return result[1] < 0.05

adf_test(white_noise, 'White Noise')
adf_test(random_walk, 'Random Walk')
# 对随机游走做一阶差分
adf_test(np.diff(random_walk), 'Random Walk (1st diff)')
```

## 2. ARIMA模型

### 2.1 ACF和PACF

```python
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.arima.model import ARIMA

# 生成AR(1)过程：y_t = 0.7*y_{t-1} + ε_t
ar1 = np.zeros(n)
for t in range(1, n):
    ar1[t] = 0.7 * ar1[t-1] + np.random.normal(0, 0.5)

# 生成MA(1)过程：y_t = ε_t + 0.5*ε_{t-1}
ma1 = np.zeros(n)
eps = np.random.normal(0, 0.5, n)
for t in range(1, n):
    ma1[t] = eps[t] + 0.5 * eps[t-1]

print("ARIMA(1,0,0) 拟合 AR(1) 数据:")
model = ARIMA(ar1, order=(1, 0, 0))
result = model.fit()
print(result.summary().tables[1])
```

### 2.2 自动定阶

```python
# 简单版：遍历p,d,q寻找最小AIC
def auto_arima_simple(series, max_p=5, max_q=5, max_d=2):
    best_aic = np.inf
    best_order = None
    
    for d in range(max_d + 1):
        diff_series = series
        if d > 0:
            diff_series = np.diff(series, d)
        
        for p in range(1, max_p + 1):
            for q in range(1, max_q + 1):
                try:
                    model = ARIMA(diff_series, order=(p, d, q))
                    result = model.fit()
                    if result.aic < best_aic:
                        best_aic = result.aic
                        best_order = (p, d, q)
                except:
                    continue
    
    print(f"Best ARIMA order: {best_order}, AIC: {best_aic:.2f}")
    return best_order

# 用股价数据测试
# arima_order = auto_arima_simple(stock_close.values, max_p=5, max_q=5, max_d=2)
print("Auto ARIMA would run here on real price data")
```

## 3. GARCH波动率建模

```python
from scipy import optimize

# 手动实现GARCH(1,1)
class SimpleGARCH:
    """GARCH(1,1) 波动率模型"""
    def __init__(self):
        self.params = None
        self.conditional_vol = None
    
    def _garch_likelihood(self, params, returns):
        omega, alpha, beta = params
        if alpha + beta >= 1:  # 稳定性约束
            return 1e10
        
        T = len(returns)
        sigma2 = np.zeros(T)
        sigma2[0] = np.var(returns)
        
        for t in range(1, T):
            sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
        
        # 负对数似然
        ll = 0.5 * np.sum(np.log(sigma2[1:]) + returns[1:]**2 / sigma2[1:])
        return ll
    
    def fit(self, returns):
        result = optimize.minimize(
            self._garch_likelihood,
            x0=[0.0001, 0.1, 0.8],
            args=(returns,),
            bounds=[(1e-6, 1), (0, 1), (0, 1)],
            method='L-BFGS-B'
        )
        self.params = result.x
        self._compute_vol(returns)
        return self
    
    def _compute_vol(self, returns):
        omega, alpha, beta = self.params
        T = len(returns)
        self.conditional_vol = np.zeros(T)
        self.conditional_vol[0] = np.std(returns)
        
        for t in range(1, T):
            sigma2 = omega + alpha * returns[t-1]**2 + beta * self.conditional_vol[t-1]**2
            self.conditional_vol[t] = np.sqrt(sigma2)
    
    def predict(self, returns, steps=5):
        last_vol = self.conditional_vol[-1]
        last_return = returns[-1]
        omega, alpha, beta = self.params
        
        predictions = []
        for _ in range(steps):
            sigma2 = omega + alpha * last_return**2 + beta * last_vol**2
            predictions.append(np.sqrt(sigma2))
            last_vol = np.sqrt(sigma2)
            last_return = 0  # E[r_t] = 0
        
        return np.array(predictions)

# 测试
np.random.seed(42)
returns = np.random.normal(0, 1, 1000) * 0.01  # 模拟日收益率

garch = SimpleGARCH().fit(returns)
print(f"GARCH(1,1) params: omega={garch.params[0]:.6f}, "
      f"alpha={garch.params[1]:.4f}, beta={garch.params[2]:.4f}")
print(f"Alpha+Beta={garch.params[1]+garch.params[2]:.4f} (should be < 1)")
```

## 4. 卡尔曼滤波

```python
import numpy as np

class KalmanFilter:
    """卡尔曼滤波 K线平滑/状态估计"""
    
    def __init__(self, A, H, Q, R, x0, P0):
        """
        A: 状态转移矩阵
        H: 观测矩阵
        Q: 过程噪声协方差
        R: 观测噪声协方差
        x0: 初始状态
        P0: 初始协方差
        """
        self.A = A
        self.H = H
        self.Q = Q
        self.R = R
        self.x = x0
        self.P = P0
    
    def predict(self, u=None):
        # 先验估计
        if u is not None:
            self.x = self.A @ self.x + u
        else:
            self.x = self.A @ self.x
        self.P = self.A @ self.P @ self.A.T + self.Q
        return self.x.copy()
    
    def update(self, z):
        # 卡尔曼增益
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # 后验估计
        y = z - self.H @ self.x  # 残差
        self.x = self.x + K @ y
        self.P = (np.eye(len(self.x)) - K @ self.H) @ self.P
        
        return self.x.copy(), y

# 应用：股价趋势跟踪
np.random.seed(42)
n = 200
true_trend = np.sin(np.arange(n) * 0.05) * 10 + 100
observations = true_trend + np.random.normal(0, 2, n)

# 一维卡尔曼滤波
kf = KalmanFilter(
    A=np.array([[1.0]]),      # 状态不变化
    H=np.array([[1.0]]),      # 直接观测
    Q=np.array([[0.01]]),     # 很小的过程噪声
    R=np.array([[4.0]]),      # 观测噪声方差
    x0=np.array([observations[0]]),
    P0=np.array([[1.0]])
)

filtered = []
for z in observations:
    kf.predict()
    state, _ = kf.update(np.array([z]))
    filtered.append(state[0])

filtered = np.array(filtered)
mse = np.mean((filtered - true_trend)**2)
print(f"Kalman Filter MSE: {mse:.4f} (vs raw observation MSE: {np.mean((observations - true_trend)**2):.4f})")
```

## 5. 协整检验

```python
# 协整：两个或多个非平稳时间序列的线性组合是平稳的
# 这是配对交易的理论基础

from statsmodels.tsa.stattools import coint

def find_cointegrated_pairs(prices_dict, p_threshold=0.05):
    """在多个股票中找到协整对"""
    import pandas as pd
    df = pd.DataFrame(prices_dict)
    n = df.shape[1]
    pairs = []
    
    for i in range(n):
        for j in range(i+1, n):
            score, pvalue, _ = coint(df.iloc[:, i], df.iloc[:, j])
            if pvalue < p_threshold:
                pairs.append((df.columns[i], df.columns[j], pvalue, score))
    
    pairs.sort(key=lambda x: x[2])  # 按p值排序
    return pairs

# 模拟两对协整序列
np.random.seed(42)
n = 500

# 共同趋势
common = np.cumsum(np.random.normal(0, 0.5, n))

# 协整对：价差是平稳的
stock_a = common + np.random.normal(0, 1, n)
stock_b = common + np.random.normal(0, 1, n) + 50  # 固定偏移

# 非协整对
stock_c = np.cumsum(np.random.normal(0, 1, n))
stock_d = np.cumsum(np.random.normal(0, 1.5, n))

# 检验
score, pvalue, _ = coint(stock_a, stock_b)
print(f"A-B 协整检验 p-value: {pvalue:.4f} {'✅ 协整' if pvalue < 0.05 else '❌ 非协整'}")

score, pvalue, _ = coint(stock_c, stock_d)
print(f"C-D 协整检验 p-value: {pvalue:.4f} {'✅ 协整' if pvalue < 0.05 else '❌ 非协整'}")

# 价差交易信号
spread = stock_a - stock_b - np.mean(stock_a - stock_b)
zscore = (spread - np.mean(spread)) / np.std(spread)

# 当 zscore > 2 时做空价差，zscore < -2 时做多
signals = np.where(zscore > 2, -1, np.where(zscore < -2, 1, 0))
print(f"信号统计: 做多={sum(signals==1)}次, 做空={sum(signals==-1)}次, 持仓={sum(signals!=0)}个交易日")
```

## 6. HMM识别市场状态

```python
# 隐马尔可夫模型识别牛/熊/震荡状态
from hmmlearn import hmm

def fit_hmm_market(returns, n_states=3):
    """用HMM识别市场状态"""
    model = hmm.GaussianHMM(
        n_components=n_states,
        covariance_type='full',
        n_iter=1000,
        random_state=42
    )
    
    # 用收益率和成交量的2D特征
    features = np.column_stack([returns, np.abs(returns)])
    model.fit(features)
    
    states = model.predict(features)
    
    # 按均值排序：0=熊市, 1=震荡, 2=牛市
    state_means = [np.mean(returns[states == i]) for i in range(n_states)]
    state_order = np.argsort(state_means)
    
    # 重映射
    state_map = {old: new for new, old in enumerate(state_order)}
    mapped_states = np.array([state_map[s] for s in states])
    
    return model, mapped_states

# 模拟三状态市场
np.random.seed(42)
n = 1000
states_true = np.zeros(n)
returns = np.zeros(n)

# 状态0: 熊市（负收益，高波动）
# 状态1: 震荡（零均值，低波动）
# 状态2: 牛市（正收益，中等波动）

current_state = 1
for t in range(n):
    if np.random.random() < 0.01:  # 1%概率切换状态
        current_state = np.random.choice([0, 1, 2])
    
    states_true[t] = current_state
    if current_state == 0:  # 熊市
        returns[t] = np.random.normal(-0.002, 0.025)
    elif current_state == 1:  # 震荡
        returns[t] = np.random.normal(0.0005, 0.015)
    else:  # 牛市
        returns[t] = np.random.normal(0.003, 0.02)

model, states_pred = fit_hmm_market(returns, 3)
accuracy = np.mean(states_pred == states_true)
print(f"HMM 状态识别准确率: {accuracy:.2%}")

# 各状态的统计
for s in range(3):
    mask = states_pred == s
    r = returns[mask]
    print(f"状态{s}: 出现{sum(mask)}次, 日均收益{r.mean():+.4f}, "
          f"波动率{r.std():.4f}, 夏普{r.mean()/r.std()*np.sqrt(252):.2f}")
```

## 在量化实战中的应用

```python
# 1. 用卡尔曼滤波做实时均线
class KFMA:
    """卡尔曼滤波移动平均（比SMA/EMA更平滑）"""
    def __init__(self):
        self.kf = KalmanFilter(
            A=np.array([[1.0]]),
            H=np.array([[1.0]]),
            Q=np.array([[0.001]]),
            R=np.array([[1.0]]),
            x0=np.array([0.0]),
            P0=np.array([[1.0]])
        )
    
    def update(self, price):
        self.kf.predict()
        state, residual = self.kf.update(np.array([price]))
        return state[0], residual[0]

# 2. HMM + 策略：不同状态用不同参数
def regime_based_strategy(price_series, hmm_model, states):
    """根据HMM市场状态切换策略参数"""
    current_state = states[-1]
    
    if current_state == 0:  # 熊市
        return {'sma_fast': 20, 'sma_slow': 50, 'stop_loss': 0.03}
    elif current_state == 1:  # 震荡
        return {'sma_fast': 10, 'sma_slow': 30, 'stop_loss': 0.05}
    else:  # 牛市
        return {'sma_fast': 5, 'sma_slow': 20, 'stop_loss': 0.08}

print("\n实战要点:")
print("- KFMA 适合高频数据平滑（比SMA延迟更低）")
print("- 协整是配对交易的基础策略")
print("- HMM识别的市场状态可作为策略开关")
print("- GARCH波动率可用于动态止损和仓位管理")
```
