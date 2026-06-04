# Lesson 7: Options Strategies — Beyond Vanilla

## 1. Option Basics

### Call vs Put

| Type | Right to | Bet on |
|------|----------|--------|
| **Call** | Buy underlying @ strike | Bullish (price up) |
| **Put** | Sell underlying @ strike | Bearish (price down) |

### Intrinsic Value vs Time Value

```
Option Price = Intrinsic Value + Time Value
```

- **Intrinsic Value (IV)**: `max(S - K, 0)` for calls; `max(K - S, 0)` for puts. Floor is zero.
- **Time Value**: The remainder — decays as expiration approaches (theta).

**Example**: S=105, K=100 call → IV=5, premium=8 → time value=3.

### Moneyness

| State | Condition | Call Intrinsic | Put Intrinsic |
|-------|-----------|---------------|---------------|
| ITM  | S > K (call), S < K (put) | > 0 | > 0 |
| ATM  | S ≈ K | ≈ 0 | ≈ 0 |
| OTM  | S < K (call), S > K (put) | 0 | 0 |

---

## 2. Black-Scholes Model

### Assumptions
- European option (exercise at expiry only)
- No dividends, constant volatility & interest rate
- Log-normal price, no arbitrage, frictionless

### Formula

```
d1 = [ln(S/K) + (r + σ²/2) T] / (σ√T)
d2 = d1 - σ√T

Call = S·N(d1) - K·e^(-rT)·N(d2)
Put  = K·e^(-rT)·N(-d2) - S·N(-d1)
```

Where `N(·)` = standard normal CDF.

### The Greeks

| Greek | Definition | What it measures |
|-------|-----------|------------------|
| **Δ (Delta)** | ∂V/∂S | Price sensitivity to underlying |
| **Γ (Gamma)** | ∂²V/∂S² | Delta's sensitivity (convexity) |
| **Θ (Theta)** | ∂V/∂t | Time decay ($-$ daily for longs) |
| **ν (Vega)** | ∂V/∂σ | Sensitivity to volatility |
| **ρ (Rho)** | ∂V/∂r | Sensitivity to interest rate |

**Delta ranges**: Call Δ ∈ [0,1], Put Δ ∈ [-1,0].

---

## 3. Black-Scholes Implementation in NumPy

```python
# pip install numpy scipy
import numpy as np
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type='call'):
    """
    Black-Scholes pricing for European options.
    
    Parameters
    ----------
    S : float or array : spot price
    K : float or array : strike price
    T : float or array : time to expiry (years)
    r : float : risk-free rate (annualized, e.g. 0.05)
    sigma : float or array : volatility (annualized, e.g. 0.20)
    option_type : str : 'call' or 'put'
    
    Returns
    -------
    float or array : option price
    """
    S, K, T = np.asarray(S), np.asarray(K), np.asarray(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return price

def greeks(S, K, T, r, sigma, option_type='call'):
    """Return a dict of all Greeks."""
    S, K, T = float(S), float(K), float(T)
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    phi_d1 = norm.pdf(d1)  # standard normal PDF
    
    delta = norm.cdf(d1) if option_type == 'call' else norm.cdf(d1) - 1
    gamma = phi_d1 / (S * sigma * sqrt_T)
    theta = - (S * phi_d1 * sigma) / (2 * sqrt_T)
    if option_type == 'call':
        theta -= r * K * np.exp(-r * T) * norm.cdf(d2)
    else:
        theta += r * K * np.exp(-r * T) * norm.cdf(-d2)
    vega = S * phi_d1 * sqrt_T / 100          # per 1% vol change
    rho = K * T * np.exp(-r * T) * norm.cdf(d2) if option_type == 'call' \
          else -K * T * np.exp(-r * T) * norm.cdf(-d2)
    rho /= 100  # per 1% rate change
    
    return {'delta': delta, 'gamma': gamma, 'theta': theta,
            'vega': vega, 'rho': rho}

# --- demo ---
S, K, T, r, sigma = 100, 105, 0.5, 0.03, 0.20
price = black_scholes(S, K, T, r, sigma, 'call')
g = greeks(S, K, T, r, sigma, 'call')
print(f"Call price: {price:.4f}")
for k, v in g.items():
    print(f"{k}: {v:.6f}")
```

---

## 4. Implied Volatility — Newton-Raphson Solver

Market prices tell you what the "vol" is. We invert BS via Newton-Raphson:

```python
def implied_volatility(market_price, S, K, T, r, option_type='call',
                       tol=1e-6, max_iter=100):
    """
    Newton-Raphson solver for implied volatility.
    
    Parameters
    ----------
    market_price : float : observed option price
    S, K, T, r    : standard BS inputs
    option_type   : 'call' or 'put'
    tol           : convergence tolerance
    max_iter      : max iterations
    
    Returns
    -------
    float : implied volatility (annualized)
    """
    sigma = 0.3  # initial guess
    for i in range(max_iter):
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        
        vega = S * norm.pdf(d1) * np.sqrt(T)  # vega w.r.t. σ, not %-scaled
        if abs(vega) < 1e-12:  # avoid zero-divide
            break
        sigma -= diff / vega
        sigma = max(sigma, 0.01)  # keep positive
    
    raise ValueError(f"IV did not converge after {max_iter} iterations")

# --- demo ---
S, K, T, r = 100, 105, 0.5, 0.03
true_vol = 0.25
price = black_scholes(S, K, T, r, true_vol, 'call')
iv = implied_volatility(price, S, K, T, r, 'call')
print(f"True vol: {true_vol:.4f} | Implied vol: {iv:.4f} | Error: {abs(iv-true_vol):.2e}")
```

---

## 5. Options Strategies

### Covered Call (Hold stock + Sell call)

```
Payoff = S_T - S_0 + max(K - S_T, 0)  # capped upside, limited downside
```
- **Use**: Generate income on long stock, mild bearish.
- **Risk**: Miss upside beyond K.

### Protective Put (Hold stock + Buy put)

```
Payoff = S_T - S_0 + max(K - S_T, 0)  # floor at K
```
- **Use**: Insurance for long position.
- **Risk**: Premium cost decays your P&L.

### Straddle (Buy call + Buy put, same strike & expiry)

```
Payoff = max(S_T-K, 0) + max(K-S_T, 0) - (call_prem + put_prem)
```
- **Use**: Bet on large move in either direction (e.g. earnings).
- **Breakevens**: K ± total premium.

### Strangle (Buy OTM call + Buy OTM put)

```
Payoff = max(S_T-K_call,0) + max(K_put-S_T,0) - premia
```
- **Use**: Same as straddle but cheaper; needs larger move.
- **Risk**: Both legs could expire worthless.

### Iron Condor (Sell OTM put spread + Sell OTM call spread)

| Leg | Buy/Sell | Strike |
|-----|----------|--------|
| 1 | Sell put | K₁ (low) |
| 2 | Buy put | K₂ (lower, K₂ < K₁) |
| 3 | Sell call | K₃ (high) |
| 4 | Buy call | K₄ (higher, K₄ > K₃) |

- **Use**: Profit from low volatility / range-bound market.
- **Max profit**: Net credit received; **max loss**: wing width minus credit.

```python
def strategy_payoff(S_range, strikes, premia, strategy):
    """
    Compute payoff at expiry for a multi-leg strategy.
    
    Parameters
    ----------
    S_range : array-like : spot prices at expiry
    strikes : list of (type, K, pos) where pos=+1 for long, -1 for short
    premia  : list of premiums paid (positive) or received (negative)
    
    Returns
    -------
    array : P&L at each S_T
    """
    S_range = np.asarray(S_range)
    pnl = np.zeros_like(S_range) - sum(premia)
    for typ, K, pos in strikes:
        if typ == 'call':
            pnl += pos * np.maximum(S_range - K, 0)
        else:
            pnl += pos * np.maximum(K - S_range, 0)
    return pnl

# Iron Condor example
S_range = np.linspace(80, 140, 200)
strikes = [('put', 95, -1), ('put', 90, 1),   # put spread
           ('call', 110, -1), ('call', 115, 1)]  # call spread
premia = [-3.2, 1.5, -2.8, 1.2]  # net credit = 3.2-1.5+2.8-1.2 = 3.3
# You receive the net credit if S_T ∈ [95,110]
print(f"Net credit: {abs(sum(premia)):.2f}")
```

---

## 6. Volatility Surface

IV is not constant across strikes and maturities — that's the **volatility surface**.

```python
import matplotlib.pyplot as plt

def vol_surface_example(S=100, r=0.03):
    """Simulate a typical vol surface (skew + term structure)."""
    maturities = np.array([0.1, 0.25, 0.5, 1.0, 2.0])
    strikes = np.arange(80, 125, 5)
    T_grid, K_grid = np.meshgrid(maturities, strikes)
    
    # Base vol + skew (higher vol for lower strikes) + term structure
    skew = 0.05 * (1 - (K_grid - S) / S)  # put vol > call vol
    term = 0.02 * np.sqrt(1 / T_grid)     # short-term more volatile
    vol = 0.20 + skew + 0.02 * np.sqrt(T_grid / 0.5)
    
    return K_grid, T_grid, vol

K, T, V = vol_surface_example()
print(f"ATM (K={100}) 30d vol: {V[4,1]:.3f}")  # index for K=100, T=0.25
```
*Real markets: equity indexes show negative skew (vol smile); FX shows symmetric smile.*

---

## 7. Integration — GARCH + Black-Scholes

From Lesson 6: plug GARCH-forecasted volatility into BS for more accurate pricing.

```python
def garch_bs_price(S, K, T, r, option_type, garch_params, resid_sq_history):
    """
    Price a European option using GARCH(1,1) volatility forecast.
    
    Parameters
    ----------
    garch_params : tuple : (omega, alpha, beta) — GARCH coefficients
    resid_sq_history : array : recent squared residuals (at least 1)
    
    Returns
    -------
    float : option price
    """
    omega, alpha, beta = garch_params
    
    # Forecast GARCH variance at horizon T (daily steps)
    daily_steps = max(1, int(T * 252))
    var_forecast = np.mean(resid_sq_history)  # starting point
    
    # Multi-period GARCH forecast: h_{t+n} converges to long-run
    # For simplicity, one-step iterative, but real use: path-averaged
    for _ in range(daily_steps):
        var_forecast = omega + alpha * resid_sq_history[-1] + beta * var_forecast
    
    sigma_garch = np.sqrt(var_forecast * 252)  # annualize
    return black_scholes(S, K, T, r, sigma_garch, option_type)

# --- integrated demo ---
np.random.seed(42)
rets = np.random.randn(500) * 0.015
resid_sq = rets ** 2
garch = (1e-6, 0.10, 0.85)  # omega, alpha, beta

price_bs   = black_scholes(100, 105, 0.5, 0.03, 0.20, 'call')
price_garch = garch_bs_price(100, 105, 0.5, 0.03, 'call', garch, resid_sq)
print(f"BS price:    {price_bs:.4f}")
print(f"GARCH price: {price_garch:.4f}")
```

### Why GARCH helps
- **Constant vol assumption is wrong**: BS with historical σ misprices options in turbulent vs calm periods.
- **GARCH forecasts next-period vol**, giving a more responsive price.

---

## Summary

| Concept | Key Takeaway |
|---------|-------------|
| BS Model | Analytical formula; works for European options |
| Greeks | Delta for directional, Vega for vol, Theta for time decay |
| IV / Vol Surface | Market doesn't have one vol — it has a 3D surface |
| Strategies | Covered call (income), protective put (insurance), straddle/strangle (vol plays), iron condor (range play) |
| GARCH + BS | Marry econometric vol forecasting with option pricing |

---
*End of Lesson 7 — next: stochastic volatility (Heston) and Monte Carlo methods.*
