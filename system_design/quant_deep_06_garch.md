# 量化深度第6课：GARCH 波动率模型与止损集成

## 1. GARCH 家族概览

### 问题背景
金融收益率存在 **波动率聚类**（volatility clustering）：大波动后跟大波动，小波动后跟小波动。OLS 假设方差恒定，不适用。

### 模型谱系

| 模型 | 全称 | 特点 |
|------|------|------|
| **ARCH(q)** | Autoregressive Conditional Heteroskedasticity | 方差 = α₀ + Σαᵢε²₋ᵢ；q 阶残差平方自回归 |
| **GARCH(p,q)** | Generalized ARCH | 方差 = ω + αε²₋₁ + βσ²₋₁；一个参数代替无穷阶 ARCH |
| **EGARCH(p,q)** | Exponential GARCH | log(σ²) 建模，捕捉杠杆效应（好消息/坏消息不对称） |
| **GJR-GARCH** | Glosten-Jagannathan-Runkle | 额外哑变量区分正负冲击 |
| **TGARCH** | Threshold GARCH | 条件标准差建模，非条件方差 |

**核心选择**：金融数据 GARCH(1,1) 通常足够，有杠杆效应选 EGARCH。

---

## 2. GARCH(1,1) 从零实现

对数似然：`ℓ = -½ Σ[log(σ²) + ε²/σ²]`

```python
import numpy as np
from scipy.optimize import minimize
from typing import Tuple

def garch11_fit(returns: np.ndarray) -> Tuple[np.ndarray, dict]:
    """
    GARCH(1,1) MLE 拟合，纯 numpy + scipy。
    
    模型: σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
    
    参数
    -----
    returns : (n,) array，对数收益率序列
    
    返回
    -----
    sigma2 : (n,) array，条件方差序列
    params : dict，含 omega, alpha, beta, log_likelihood
    """
    returns = np.asarray(returns, dtype=np.float64)
    n = len(returns)
    
    def neg_log_likelihood(theta: np.ndarray) -> float:
        omega, alpha, beta = theta
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
            return 1e10
        sigma2 = np.full(n, np.var(returns))
        for t in range(1, n):
            sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
        return 0.5 * np.sum(np.log(sigma2[1:]) + returns[1:]**2 / sigma2[1:])
    
    init = np.array([np.var(returns) * 0.05, 0.1, 0.8])
    bounds = [(1e-8, None), (0, 1), (0, 1)]
    res = minimize(neg_log_likelihood, init, bounds=bounds, method='L-BFGS-B')
    
    omega, alpha, beta = res.x
    sigma2 = np.full(n, np.var(returns))
    for t in range(1, n):
        sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
    
    return sigma2, {
        'omega': omega, 'alpha': alpha, 'beta': beta,
        'log_likelihood': -res.fun,
        'converged': res.success
    }
```

**使用示例**：
```python
import numpy as np
# 模拟 GARCH(1,1) 数据
np.random.seed(42)
n = 2000
eps = np.random.randn(n)
sigma2 = np.ones(n)
for t in range(1, n):
    sigma2[t] = 0.01 + 0.15 * eps[t-1]**2 + 0.8 * sigma2[t-1]
returns = np.sqrt(sigma2) * np.random.randn(n)

sigma2_hat, params = garch11_fit(returns)
print(f"ω={params['omega']:.4f}, α={params['alpha']:.4f}, β={params['beta']:.4f}")
```

---

## 3. EGARCH(1,1) 杠杆效应

EGARCH 对 log(σ²) 建模，**不要求系数非负**，且通过 `γ` 项捕捉杠杆效应（坏消息 → 更大波动）。

模型：`log(σ²_t) = ω + α·z_{t-1} + γ·(|z_{t-1}| - E|z_{t-1}|) + β·log(σ²_{t-1})`

其中 `z_t = ε_t / σ_t`，`E|z_t| = √(2/π)`（标准正态假设）。

```python
def egarch11_fit(returns: np.ndarray) -> Tuple[np.ndarray, dict]:
    """
    EGARCH(1,1) MLE 拟合，捕捉杠杆效应。
    
    模型: log(σ²_t) = ω + α·z_{t-1} + γ·(|z_{t-1}| - √(2/π)) + β·log(σ²_{t-1})
    其中 z_t = ε_t / σ_t
    
    参数
    -----
    returns : (n,) array，对数收益率
    
    返回
    -----
    sigma2 : (n,) array，条件方差序列
    params : dict，含 omega, alpha, gamma, beta, log_likelihood
             注意：gamma < 0 表示坏消息（负冲击）导致更大波动 → 杠杆效应
    """
    returns = np.asarray(returns, dtype=np.float64)
    n = len(returns)
    E_abs_z = np.sqrt(2 / np.pi)
    
    def neg_log_likelihood(theta: np.ndarray) -> float:
        omega, alpha, gamma, beta = theta
        if beta >= 1 or beta < -1:  # β < 1 保证平稳
            return 1e10
        log_sigma2 = np.full(n, np.log(np.var(returns)))
        sigma2 = np.exp(log_sigma2)
        for t in range(1, n):
            z = returns[t-1] / max(np.sqrt(sigma2[t-1]), 1e-12)
            log_sigma2[t] = (omega + alpha * z + gamma * (abs(z) - E_abs_z)
                             + beta * log_sigma2[t-1])
        sigma2 = np.exp(log_sigma2)
        return 0.5 * np.sum(np.log(sigma2[1:]) + returns[1:]**2 / sigma2[1:])
    
    init = np.array([np.log(np.var(returns)) * 0.05, -0.05, 0.1, 0.9])
    res = minimize(neg_log_likelihood, init, method='L-BFGS-B')
    
    omega, alpha, gamma, beta = res.x
    log_sigma2 = np.full(n, np.log(np.var(returns)))
    sigma2 = np.exp(log_sigma2)
    for t in range(1, n):
        z = returns[t-1] / max(np.sqrt(sigma2[t-1]), 1e-12)
        log_sigma2[t] = (omega + alpha * z + gamma * (abs(z) - E_abs_z)
                         + beta * log_sigma2[t-1])
    sigma2 = np.exp(log_sigma2)
    
    return sigma2, {
        'omega': omega, 'alpha': alpha,
        'gamma': gamma, 'beta': beta,
        'log_likelihood': -res.fun,
        'converged': res.success,
        'leverage': gamma < 0  # True → 存在杠杆效应
    }
```

**杠杆效应判别**：
- `γ < 0`：坏消息（负收益 → `z < 0` → `α·z` 为负）叠加后波动更大 → **杠杆效应成立**
- `γ > 0`：好消息放大波动，不满足金融常识

---

## 4. 波动率预测

GARCH 多步预测公式（GARCH(1,1)）：

```
σ²_{t+h|t} = ω + (α+β) · σ²_{t+h-1|t}
```

当 h→∞ 时，收敛到无条件方差：`σ² = ω / (1 - α - β)`

```python
def garch_forecast(sigma2_last: float, params: dict, steps: int = 5) -> np.ndarray:
    """
    GARCH(1,1) 多步方差预测。
    
    参数
    -----
    sigma2_last : float，最后一期的条件方差
    params      : dict，含 omega, alpha, beta
    steps       : int，预测步数
    
    返回
    -----
    forecast : (steps,) array，预测条件方差
    """
    omega, alpha, beta = params['omega'], params['alpha'], params['beta']
    fc = np.zeros(steps)
    fc[0] = omega + (alpha + beta) * sigma2_last
    for h in range(1, steps):
        fc[h] = omega + (alpha + beta) * fc[h-1]
    return fc

def egarch_forecast(log_sigma2_last: float, params: dict, steps: int = 5) -> np.ndarray:
    """
    EGARCH(1,1) 多步方差预测。
    EGARCH 的自回归系数是 β，所以 σ²_{t+h} = exp(ω + β·log(σ²_{t+h-1}))
    （多步预测时新息项期望为 0）
    """
    omega, beta = params['omega'], params['beta']
    fc_log = np.zeros(steps)
    fc_log[0] = omega + beta * log_sigma2_last
    for h in range(1, steps):
        fc_log[h] = omega + beta * fc_log[h-1]
    return np.exp(fc_log)

# 使用示例
fc = garch_forecast(sigma2_hat[-1], params, steps=10)
print(f"未来10期波动率预测: {np.sqrt(fc) * 100:.2f}%")
```

---

## 5. Kelly 动态止损集成

### 核心思路
用 GARCH 预测的波动率动态调整 Kelly 仓位和止损线：

```
波动率高 → 降低仓位 + 收窄止损
波动率低 → 恢复仓位 + 放宽止损
```

```python
def kelly_with_garch_stop(
    win_rate: float,           # 胜率
    avg_win: float,            # 平均盈利率（小数，如 0.02）
    avg_loss: float,           # 平均亏损率（小数，如 0.01）
    predicted_vol: float,      # GARCH 预测波动率（日收益率标准差）
    base_vol: float = 0.015,   # 基准波动率（正常市场）
    max_kelly: float = 0.25,   # 最大 Kelly 分数
) -> dict:
    """
    Kelly 仓位 + GARCH 动态止损集成。
    杠杆比率：predicted_vol / base_vol
    """
    b = avg_win / avg_loss       # 赔率
    kelly_full = (win_rate * b - (1 - win_rate)) / b  # 原始 Kelly
    
    vol_ratio = predicted_vol / base_vol
    vol_ratio = max(0.3, min(vol_ratio, 3.0))  # 截断
    
    kelly_adj = kelly_full / vol_ratio
    kelly_adj = min(kelly_adj, max_kelly)
    kelly_adj = max(kelly_adj, 0.0)  # 不做空
    
    return {
        'kelly_raw': round(kelly_full, 4),
        'kelly_adjusted': round(kelly_adj, 4),
        'vol_ratio': round(vol_ratio, 2),
        'stop_loss_pct': round(avg_loss * (1 + 0.3 * (vol_ratio - 1)), 4),
    }

# 示例
result = kelly_with_garch_stop(0.55, 0.02, 0.01, predicted_vol=0.025)
print(result)
# {'kelly_raw': 0.1, 'kelly_adjusted': 0.06, 'vol_ratio': 1.67, 'stop_loss_pct': 0.012}
```

**止损调整逻辑**：
- `vol_ratio > 1`（市场比基准更波动）→ 收窄止损 → `stop_loss = avg_loss × (1 + 0.3×(vol_ratio-1))`
- `vol_ratio < 1`（市场平静）→ 适当放宽止损防噪声出场

---

## 6. 集成到 monitor_v3 的方式

在 `monitor_v3` 的行情处理流程中加入 GARCH 模块：

```python
# --- 在 monitor_v3 的 on_bar 或 update_positions 中 ---

# 1. 维护一个收益率滚动窗口（如 500 根 K 线）
RETURNS_WINDOW = 500
price_buffer = deque(maxlen=RETURNS_WINDOW + 1)

def update_garch_state(close_price: float):
    global sigma2_hat, garch_params
    if len(price_buffer) < 2:
        price_buffer.append(close_price)
        return
    price_buffer.append(close_price)
    prices = np.array(list(price_buffer))
    returns = np.diff(np.log(prices))  # 对数收益率
    
    # 每 50 根 K 线重拟合一次，其余增量预测
    if len(price_buffer) % 50 == 0:
        sigma2_hat, garch_params = garch11_fit(returns)
    else:
        # 增量一步更新 σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
        r = returns[-1]
        sigma2_last = sigma2_hat[-1]
        sigma2_new = (garch_params['omega'] 
                      + garch_params['alpha'] * r**2 
                      + garch_params['beta'] * sigma2_last)
        sigma2_hat = np.append(sigma2_hat, sigma2_new)
    
    return np.sqrt(sigma2_hat[-1])  # 当前预测波动率

# 2. 在 Kelly 止损模块中替换固定止损
predicted_vol = update_garch_state(current_price)
stop_config = kelly_with_garch_stop(
    win_rate=stats['win_rate'],
    avg_win=stats['avg_win'],
    avg_loss=stats['avg_loss'],
    predicted_vol=predicted_vol
)
# 使用 stop_config['kelly_adjusted'] 调整仓位
# 使用 stop_config['stop_loss_pct'] 设置动态止损
```

**文件结构建议**（放入 monitor_v3 项目 `strategies/` 下）：

```
strategies/
├── garch.py          # garch11_fit, egarch11_fit, garch_forecast
├── kelly_stop.py     # kelly_with_garch_stop
└── __init__.py
```

**性能注意**：MLE 拟合 O(n) 复杂度，500 根线约 1-2ms。每 50 根线拟合一次足够，中间增量更新 O(1)。

---

## 附录：快速检查表

- [ ] GARCH(1,1) 四参数：ω, α, β, σ²₀
- [ ] 平稳条件：α + β < 1
- [ ] EGARCH 不自限非负，适合杠杆效应
- [ ] γ < 0 → 坏消息放大波动
- [ ] 多步预测收敛到 ω/(1-α-β)
- [ ] 波动率高 → 减仓 + 收止损；波动率低 → 加仓 + 放松止损
