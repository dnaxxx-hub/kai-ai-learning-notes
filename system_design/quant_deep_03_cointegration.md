# 量化深度第3课：协整检验与配对套利

## 1. 协整 vs 相关 — 伪回归陷阱

### 伪回归（Spurious Regression）

两个无关的随机游走，相关系数可能很高、回归也"显著"：
```python
x = np.cumsum(np.random.randn(1000))
y = np.cumsum(np.random.randn(1000))
np.corrcoef(x,y)[0,1]  # 可能高达 0.8+
```
**原因**：非平稳序列方差发散，经典 OLS 失效。

### 协整定义

`x_t ~ I(1)`，`y_t ~ I(1)`，存在 `β` 使：
```
y_t - β·x_t = ε_t ~ I(0)
```
则 `(y,x)` 协整。`β` 是协整向量，`ε_t` 是价差/均衡误差。

### 相关 ≠ 协整

| 维度 | 相关 | 协整 |
|------|------|------|
| 概念 | 线性关联强度 | 长期均衡 |
| 前提 | 任意序列 | 同阶单整 |
| 伪回归 | 不区分 | 专门规避 |
| 时间 | 静态 | 动态跨期 |

---

## 2. Engle-Granger 两步法

**第1步：协整回归**（OLS 估计 β）
```python
beta = np.polyfit(x, y, deg=1)[0]   # y = β·x + α
spread = y - beta * x                # 残差 = 价差
```

**第2步：残差 ADF 检验**。H0: 残差有单位根（不协整）。p < 0.05 拒绝 H0。
```python
from statsmodels.tsa.stattools import adfuller
adf_stat, p_value = adfuller(spread, maxlag=1, autolag=None)
```

> EG 的临界值比标准 ADF 更严，通常查 MacKinnon 表。这里用 p 值近似。

**无 statsmodels 时手动 ADF**：
```python
def adf_test(y, maxlag=1):
    dy = np.diff(y); y_lag = y[:-1]
    dy_lag = np.hstack([[0],dy[:-1]])
    X = np.column_stack([np.ones(len(dy)), y_lag, dy_lag])
    coeff = np.linalg.lstsq(X, dy, rcond=None)[0]
    resid = dy - X @ coeff
    se = np.sqrt(np.diag(np.linalg.inv(X.T@X)) * np.var(resid, ddof=len(coeff)))
    t_stat = coeff[1]/se[1]
    return t_stat  # 5% ≈ -2.86
```

---

## 3. Johansen 检验（概念层）

- EG 只能检验 **一个** 协整向量；Johansen 可检测 **多个**
- 基于 VECM 模型 `ΔY_t = Π·Y_{t-1} + ΣΓ_i·ΔY_{t-i} + ε_t`
- `rank(Π)` = 协整关系个数 r
- 两种检验：
  - **迹检验**：H0: r = r0 vs H1: r > r0
  - **最大特征值**：H0: r = r0 vs H1: r = r0+1
- 适用：多资产篮子、行业板块筛选。两两配对用 EG 足够。

---

## 4. 配对套利流程

```
候选池 → 协整检验(EG) → OLS beta → 价差 = P1-β·P2
→ 滚动z-score(窗口60) → 信号：|z|≥2σ入场，z≈0出场
```

**信号规则**：
| z-score | 操作 |
|---------|------|
| ≥ +2σ | 做空价差（卖 P1，买 β·P2） |
| ≤ -2σ | 做多价差（买 P1，卖 β·P2） |
| 回归 0 | 平仓 |

---

## 5. 完整可运行 Python 代码

```python
"""
配对套利 - 合成数据→EG检验→z-score→信号→回测
依赖：numpy, scipy；statsmodels/matplotlib 可选
"""
import numpy as np; from scipy import stats

# ── 5.1 生成两个协整序列 ──
np.random.seed(42); n = 500
trend = np.cumsum(np.random.randn(n)*0.5)
P1 = trend + np.random.randn(n)*0.3
beta_true = 1.5
P2 = beta_true * P1 + np.random.randn(n)*0.5
print(f"真实 beta = {beta_true}")

# ── 5.2 Engle-Granger 检验 ──
def eg_test(x, y):
    A = np.vstack([x, np.ones(len(x))]).T
    coeff = np.linalg.lstsq(A, y, rcond=None)[0]
    b, a = coeff[0], coeff[1]
    sp = y - (b*x + a)

    dy = np.diff(sp); yl = sp[:-1]
    dl = np.hstack([[0], dy[:-1]])
    X = np.column_stack([np.ones(len(dy)), yl, dl])
    bc = np.linalg.lstsq(X, dy, rcond=None)[0]
    rs = dy - X@bc
    mse = np.sum(rs**2)/(len(rs)-len(bc))
    vc = mse * np.linalg.inv(X.T@X)
    t = bc[1]/np.sqrt(vc[1,1])
    return b, a, sp, t, t < -2.86

b_est, a_est, spread, t_stat, ok = eg_test(P1, P2)
print(f"beta={b_est:.4f}, alpha={a_est:.4f}")
print(f"ADF t={t_stat:.3f}, 临界=-2.86, 协整={'✓' if ok else '✗'}")

# 可选：statsmodels 验证
try:
    from statsmodels.tsa.stattools import adfuller
    print(f"ADF p={adfuller(spread,1,autolag=None,regression='c')[1]:.5f}")
except: print("无 statsmodels")

# ── 5.3 滚动静 z-score ──
def roll_z(series, w=60):
    m = np.convolve(series, np.ones(w)/w, mode='same')
    s = np.sqrt(np.convolve(series**2, np.ones(w)/w, mode='same')-m**2)
    s[s<1e-8]=1e-8; z=(series-m)/s; z[:w]=0; return z

z = roll_z(spread)

# ── 5.4 交易信号 ──
def signals(z, entry=2.0, exit=0.0):
    pos = np.zeros(len(z)); inp = 0
    for i in range(len(z)):
        if abs(z[i])<1e-8: continue
        if inp==0:
            if z[i]>=entry: pos[i]=-1; inp=-1
            elif z[i]<=-entry: pos[i]=1; inp=1
        elif inp==1:
            if z[i]>=-exit: pos[i]=0; inp=0
            else: pos[i]=1
        elif inp==-1:
            if z[i]<=exit: pos[i]=0; inp=0
            else: pos[i]=-1
    return pos

sig = signals(z)

# ── 5.5 回测 ──
sp = P2 - (b_est*P1 + a_est)
ds = np.diff(sp); pnl = np.zeros(n)
for i in range(1,n):
    if sig[i-1]!=0:
        pnl[i] = sig[i-1]*ds[i-1]
        if sig[i]!=sig[i-1] and sig[i]!=0:
            pnl[i] -= 0.001
cp = np.cumsum(pnl)
sr = np.mean(pnl[pnl!=0])/(np.std(pnl[pnl!=0])+1e-10)*np.sqrt(252)
print(f"\n总收益={cp[-1]:+.4f}, 夏普={sr:.2f}")
print(f"交易={np.sum(np.abs(np.diff(sig))>0)}, 持仓={np.sum(sig!=0)/n:.1%}")

# ── 5.6 可视化（可选）──
try:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3,1,figsize=(12,8),sharex=True)
    ax[0].plot(P1,label='P1'); ax[0].plot(P2,label='P2'); ax[0].legend(); ax[0].set_title('价格')
    ax[1].plot(spread); ax[1].axhline(0,color='k',ls='--'); ax[1].set_title('价差')
    ax[2].plot(z,color='purple')
    ax[2].axhline(2,color='r',ls='--',alpha=.5)
    ax[2].axhline(-2,color='g',ls='--',alpha=.5)
    ax[2].scatter(np.where(sig==1),z[sig==1],marker='^',color='g',s=50)
    ax[2].scatter(np.where(sig==-1),z[sig==-1],marker='v',color='r',s=50)
    ax[2].set_title('z-score + 信号')
    plt.tight_layout(); plt.show()
except: print("无 matplotlib")
```

---

## 6. 集成 multi_factor 因子评分筛选多配对

```python
def select_pairs(scores, universe, top_k=50):
    """取因子评分 Top-K 股票，两两协整检验，按 |t-stat| 排序"""
    ranked = sorted(universe, key=lambda s: scores.get(s,0), reverse=True)[:top_k]
    cand = []
    for i in range(len(ranked)):
        for j in range(i+1, len(ranked)):
            _,_,_,t,ok = eg_test(prices[ranked[i]], prices[ranked[j]])
            if ok: cand.append((ranked[i], ranked[j], abs(t)))
    cand.sort(key=lambda x: x[2], reverse=True)
    return cand

class PairPortfolio:
    def __init__(self, pairs, capital=1e6):
        self.pairs = pairs; self.per = capital/len(pairs)
    def update(self, df):
        sig = {}
        for a,b,bt in self.pairs:
            sp = df[b]-bt*df[a]
            z = (sp-sp.rolling(60).mean())/sp.rolling(60).std()
            sig[(a,b)] = self._signal(z.iloc[-1])
        return sig
```

---

## 7. GARCH 监控价差波动率（从第6课）

固定 ±2σ 阈值的问题：波动率变化时阈值失效。GARCH 动态调整。

```python
def garch_vol(spread, lam=0.94):
    """EWMA 近似 GARCH(1,1)，RiskMetrics 标准 λ=0.94"""
    vt = np.full(len(spread), np.nan); vt[0]=spread[0]**2
    for t in range(1, len(spread)):
        vt[t]=lam*vt[t-1]+(1-lam)*spread[t-1]**2
    return np.sqrt(vt)  # 时变波动率

# 完整 GARCH：from arch import arch_model
# model = arch_model(spread, vol='Garch',p=1,q=1).fit(disp='off')
# dyn_threshold = 2 * model.conditional_volatility

def dyn_entry(vol_ratio, base=2.0):
    """波动率↑→阈值↑ 防假信号；波动率↓→阈值↓ 捕小机会"""
    if vol_ratio > 1.5: return base*1.3
    if vol_ratio < 0.7: return base*0.8
    return base
```

| 场景 | 固定阈值问题 | GARCH 动态阈值 |
|------|-------------|----------------|
| 财报季波动飙升 | 频繁假信号 | 自动放宽 |
| 盘整期波动萎缩 | 无法触发 | 自动收紧 |
| 趋势性波动扩大 | 连续亏损 | 减少暴露 |

---

## 参考

- Engle & Granger (1987), *Econometrica*
- Johansen (1988), *J of Economic Dynamics and Control*
- Gatev, Goetzmann & Rouwenhorst (2006), *J of Finance*
- 延伸：Kalman Filter 动态 beta、高频配对、跨交易所套利
