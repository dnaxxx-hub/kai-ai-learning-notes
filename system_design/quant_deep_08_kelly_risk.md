# Lesson 8: Kelly Criterion, Position Sizing & Risk Parity

## 1. Kelly Criterion

### Discrete (binary outcome) form

For a bet with probability $p$ of winning, probability $q = 1-p$ of losing, and net odds $b$ (profit per unit wagered):

$$f^* = \frac{bp - q}{b} = \frac{bp - (1-p)}{b}$$

- $f^*$ = fraction of capital to bet
- If $bp - q \leq 0$, no bet (negative expectation)

### Continuous (Gaussian) form for trading

Assume returns $r \sim \mathcal{N}(\mu, \sigma^2)$ and risk-free rate $r_f$:

$$f^* = \frac{\mu - r_f}{\sigma^2}$$

This maximizes the expected logarithm of wealth (long-run growth rate):

$$g(f) = \mu f - \frac{1}{2} \sigma^2 f^2 + r_f$$

Maximum at $f^* = (\mu - r_f)/\sigma^2$, with optimal growth rate:

$$g(f^*) = r_f + \frac{(\mu - r_f)^2}{2\sigma^2}$$

**Intuition:** Kelly bets proportional to Sharpe ratio divided by vol. Higher Sharpe → larger bet. Higher vol → smaller bet.

### Limitations of Full Kelly
- **Extreme volatility:** drawdowns of 50-80% are common
- **Over-concentration:** one model error can wipe out most capital
- **Path-dependence:** underestimates risk in fat-tailed real markets

---

## 2. Fractional Kelly

Reduce the Kelly fraction by a constant multiplier $\alpha \in (0,1)$:

$$f_\alpha = \alpha \cdot f^*$$

Common choices: $\alpha = 0.25$ (Quarter-Kelly), $\alpha = 0.5$ (Half-Kelly).

**Why it works:** Growth rate is very flat near the Kelly optimum. Halving $f$ reduces growth by only ~25% but cuts drawdowns by ~50%.

---

## 3. Half-Kelly — The Industry Standard

Half-Kelly ($\alpha = 0.5$) is the most common practical choice:

- **CAGR:** typically 85-95% of Full Kelly CAGR
- **Max drawdown:** typically 40-60% lower than Full Kelly
- **Sharpe ratio:** often *higher* than Full Kelly (better risk-adjusted return)
- **Robustness:** far less sensitive to estimation errors in $\mu$ and $\sigma$

**Rule of thumb:** If you can't stomach a 50% drawdown, don't use Full Kelly.

---

## 4. Monte Carlo Simulation

Below is a self-contained simulation comparing Full Kelly, Half Kelly, and equal-weight allocation on A-share-like returns (annualized Sharpe ~0.6, vol ~25%).

```python
import numpy as np

def simulate_kelly_comparison(n_assets=5, n_years=10, n_paths=2000,
                              seed=42, alpha_half=0.5, alpha_quarter=0.25):
    """
    Monte Carlo comparison of Kelly variants on synthetic A-share style returns.

    Parameters
    ----------
    n_assets : int       Number of assets in portfolio
    n_years  : int       Simulation horizon in years
    n_paths  : int       Number of Monte Carlo paths
    alpha_half, alpha_quarter : Fractional Kelly multipliers
    """
    rng = np.random.default_rng(seed)

    # A-share-like parameters (annualized)
    target_sharpe = 0.6
    target_vol = 0.25
    mu_annual = target_sharpe * target_vol  # ~0.15
    sigma_annual = target_vol

    # Convert to daily (252 trading days)
    dt = 1/252
    mu_daily = mu_annual * dt
    sigma_daily = sigma_annual * np.sqrt(dt)

    n_days = n_years * 252

    # Generate asset returns with moderate cross-correlation
    corr = 0.3 * np.ones((n_assets, n_assets)) + 0.7 * np.eye(n_assets)
    L = np.linalg.cholesky(corr)

    # Shape: (n_paths, n_days, n_assets)
    z = rng.normal(size=(n_paths, n_days, n_assets))
    correlated = z @ L.T
    returns = mu_daily + sigma_daily * correlated  # (n_paths, n_days, n_assets)

    # Equal-weight portfolio (1/n)
    w_eq = np.ones(n_assets) / n_assets
    ret_eq = returns @ w_eq  # (n_paths, n_days)

    # Kelly portfolio — assumes equal Sharpe for simplicity
    # f* = mu / sigma^2 (per asset, ignoring rf ≈ 0)
    # For n assets with equal vol and correlation:
    #   optimal is to size each at f* / n (balanced allocation)
    sample_mu = returns.mean(axis=(0, 1))  # overall mean
    sample_sigma = returns.std(axis=(0, 1))
    f_star_per_asset = sample_mu[0] / (sample_sigma[0]**2) if n_assets == 1 else \
        (sample_mu.mean() / (sample_sigma.mean()**2)) / n_assets

    # Weights
    w_full = np.full(n_assets, f_star_per_asset)
    w_half = w_full * alpha_half
    w_quarter = w_full * alpha_quarter

    def run_strategy(w):
        """Compute path-wise equity curves for a weighting scheme."""
        w_abs = np.abs(w).sum()  # total leverage
        ret_strat = returns @ w  # (n_paths, n_days)
        equity = np.cumprod(1 + ret_strat, axis=1)
        return equity, ret_strat

    eq_full, ret_full = run_strategy(w_full)
    eq_half, ret_half = run_strategy(w_half)
    eq_quarter, ret_quarter = run_strategy(w_quarter)
    eq_eq,   ret_eq   = run_strategy(w_eq)

    def metrics(equity, ret, name):
        """Compute CAGR, max drawdown, Sharpe from path-level data."""
        final = equity[:, -1]
        cagr = np.percentile(final**(1/n_years) - 1, [5, 50, 95])

        # Max drawdown per path
        peak = np.maximum.accumulate(equity, axis=1)
        dd = (equity - peak) / peak
        mdd = np.min(dd, axis=1)
        mdd_pct = np.percentile(mdd, [5, 50, 95])

        # Sharpe (annualized)
        ann_ret = ret.mean(axis=1) * 252
        ann_vol = ret.std(axis=1) * np.sqrt(252)
        sharpe = ann_ret / (ann_vol + 1e-10)
        sharpe_pct = np.percentile(sharpe, [5, 50, 95])

        return {
            'name': name,
            'CAGR_p5' : cagr[0], 'CAGR_p50' : cagr[1], 'CAGR_p95' : cagr[2],
            'MDD_p5'  : mdd_pct[0], 'MDD_p50'  : mdd_pct[1], 'MDD_p95'  : mdd_pct[2],
            'Sharpe_p5': sharpe_pct[0], 'Sharpe_p50': sharpe_pct[1], 'Sharpe_p95': sharpe_pct[2],
        }

    return [
        metrics(eq_full, ret_full, 'Full Kelly'),
        metrics(eq_half, ret_half, 'Half Kelly'),
        metrics(eq_quarter, ret_quarter, 'Quarter Kelly'),
        metrics(eq_eq,   ret_eq,   'Equal Weight'),
    ]


if __name__ == '__main__':
    results = simulate_kelly_comparison(n_assets=5, n_years=10, n_paths=2000)

    print(f"{'Strategy':<16} {'CAGR(50%)':>10} {'CAGR(5%)':>10} {'CAGR(95%)':>10} "
          f"{'MDD(50%)':>10} {'MDD(5%)':>10} {'Sharpe(50%)':>10}")
    print("-" * 90)
    for r in results:
        print(f"{r['name']:<16} {r['CAGR_p50']:>10.4f} {r['CAGR_p5']:>10.4f} "
              f"{r['CAGR_p95']:>10.4f} {r['MDD_p50']:>10.4f} {r['MDD_p5']:>10.4f} "
              f"{r['Sharpe_p50']:>10.3f}")
```

**Expected output pattern:**
| Strategy | CAGR (median) | Max DD (median) | Sharpe (median) |
|----------|:----:|:----:|:----:|
| Full Kelly | highest | worst (e.g. -55%) | ~0.6 |
| Half Kelly | ~90-95% of Full | much better (-25%) | ~0.7-0.8 |
| Quarter Kelly | ~70-80% of Full | best (-15%) | ~0.7 |
| Equal Weight | varies | varies | lower |

---

## 5. Risk Parity

Risk parity equalizes the **risk contribution** of each asset, not the capital allocation.

### Definitions

**Portfolio volatility:**
$$\sigma_p = \sqrt{\mathbf{w}^T \Sigma \mathbf{w}}$$

**Marginal risk contribution** of asset $i$ (derivative w.r.t weight):
$$MRC_i = \frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma \mathbf{w})_i}{\sigma_p}$$

**Total risk contribution** of asset $i$:
$$TRC_i = w_i \times MRC_i = \frac{w_i (\Sigma \mathbf{w})_i}{\sigma_p}$$

**Risk parity condition:** $TRC_i = TRC_j \quad \forall i,j$

### Why Risk Parity Works

- Equities have high vol → get small weight
- Bonds have low vol → get large weight
- But if all assets have equal risk contribution, the portfolio is balanced across risk factors
- Historically: risk parity portfolios (e.g. 60/40 risk-balanced) outperform naive 60/40 capital allocation

### Simple Python Implementation

```python
def risk_parity_weights(cov: np.ndarray, max_iter: int = 1000,
                        tol: float = 1e-8) -> np.ndarray:
    """
    Compute risk parity weights via iterative gradient descent.

    Parameters
    ----------
    cov : (n, n) covariance matrix
    max_iter : max iterations
    tol : convergence tolerance

    Returns
    -------
    w : (n,) risk parity weights (sum = 1)
    """
    n = cov.shape[0]
    w = np.ones(n) / n  # equal start

    for _ in range(max_iter):
        port_vol = np.sqrt(w @ cov @ w)
        mrc = cov @ w / port_vol          # marginal risk contribution
        trc = w * mrc                      # total risk contribution

        # Target: equal TRC → gradient = TRC - mean(TRC)
        target = trc.mean()
        grad = trc - target

        # Newton-like step (enforce sum(w)=1)
        step = 0.5
        w_new = w - step * grad
        w_new = np.clip(w_new, 0, 1)       # long-only
        w_new /= w_new.sum()               # normalize

        if np.max(np.abs(w_new - w)) < tol:
            break
        w = w_new

    return w


# --- Example ---
if __name__ == '__main__':
    # 3 assets: equity (20% vol), bond (6% vol), commodity (18% vol)
    vols = np.array([0.20, 0.06, 0.18])
    corr = np.array([
        [1.00, 0.20, 0.40],
        [0.20, 1.00, 0.10],
        [0.40, 0.10, 1.00],
    ])
    cov = np.outer(vols, vols) * corr

    w_rp = risk_parity_weights(cov)
    print("Risk Parity Weights:")
    for name, w in zip(['Equity', 'Bond', 'Commodity'], w_rp):
        print(f"  {name:>10}: {w:.4f}")

    # Verify equal risk contribution
    port_vol = np.sqrt(w_rp @ cov @ w_rp)
    trc = w_rp * (cov @ w_rp) / port_vol
    print(f"  Risk contribs: {trc.round(4)}")
```

---

## 6. Risk Budgeting

Generalization of risk parity — target *specific* risk allocations instead of equal ones.

### Problem Statement

Given target risk budgets $b_i$ (sum to 1), find weights $w$ such that:

$$\frac{w_i (\Sigma \mathbf{w})_i}{\mathbf{w}^T \Sigma \mathbf{w}} = b_i$$

**Example — 60/40 Style Budget:**

```python
def risk_budget_weights(cov: np.ndarray, budgets: np.ndarray,
                        max_iter: int = 2000, tol: float = 1e-8) -> np.ndarray:
    """
    Risk budgeting: target specific risk contributions.

    Parameters
    ----------
    cov : (n, n) covariance matrix
    budgets : (n,) target risk budgets (must sum to 1)

    Returns
    -------
    w : (n,) weights achieving target budgets
    """
    n = cov.shape[0]
    budgets = budgets / budgets.sum()
    w = np.ones(n) / n

    for _ in range(max_iter):
        port_vol = np.sqrt(w @ cov @ w)
        trc = w * (cov @ w) / port_vol
        actual = trc / trc.sum()
        grad = actual - budgets

        step = 0.5
        w_new = w - step * grad
        w_new = np.clip(w_new, 0, 1)
        w_new /= w_new.sum()

        if np.max(np.abs(w_new - w)) < tol:
            break
        w = w_new

    return w


# --- Example: target 60% equity risk, 40% bond risk ---
if __name__ == '__main__':
    vols = np.array([0.20, 0.06])
    corr = np.array([[1.0, 0.2], [0.2, 1.0]])
    cov = np.outer(vols, vols) * corr

    budgets = np.array([0.60, 0.40])  # 60% equity risk, 40% bond risk
    w = risk_budget_weights(cov, budgets)
    print(f"Budget: {budgets}")
    print(f"Weights: Equity={w[0]:.4f}, Bond={w[1]:.4f}")

    port_vol = np.sqrt(w @ cov @ w)
    trc = w * (cov @ w) / port_vol
    print(f"Actual risk contribs: {trc / trc.sum()}")
```

---

## 7. Kelly Calculator from Return Series

```python
def kelly_fraction(returns: np.ndarray, rf: float = 0.0) -> float:
    """
    Compute optimal Kelly fraction from a return series.

    Parameters
    ----------
    returns : (n,) array of periodic returns (e.g. daily)
    rf      : risk-free rate for the same period

    Returns
    -------
    f_star : Full Kelly fraction (may be >1 = leverage)
    """
    mu = returns.mean()
    sigma2 = returns.var(ddof=1)
    f_star = (mu - rf) / sigma2
    return f_star


def fractional_kelly(returns: np.ndarray, alpha: float = 0.5,
                     rf: float = 0.0) -> float:
    """Fractional Kelly: f = alpha * f_star"""
    return alpha * kelly_fraction(returns, rf)


# --- Example ---
if __name__ == '__main__':
    rng = np.random.default_rng(42)
    sample_returns = rng.normal(0.0006, 0.015, size=1000)  # ~0.15/252, 0.25/sqrt(252)

    f = kelly_fraction(sample_returns)
    half = fractional_kelly(sample_returns, 0.5)

    print(f"Full Kelly:       {f:.4f}")
    print(f"Half Kelly:       {half:.4f}")
    print(f"Suggested pos:    {half:.2%} of capital per signal")
```

---

## 8. Integration: Dynamic Kelly with GARCH Volatility

Combine GARCH (Lesson 6) with Kelly for time-varying position sizing:

```python
def dynamic_kelly_sizing(mu_estimate: float, garch_vol: np.ndarray,
                         alpha: float = 0.5, rf: float = 0.0) -> np.ndarray:
    """
    Compute time-varying Kelly fractions using GARCH predicted vol.

    Parameters
    ----------
    mu_estimate : float        Expected annualized return (constant assumption)
    garch_vol   : (n,) array   GARCH-predicted daily volatilities
    alpha       : float        Fractional Kelly multiplier
    rf          : float        Annual risk-free rate

    Returns
    -------
    f_dynamic : (n,) array of position sizes
    """
    mu_d = mu_estimate / 252
    rf_d = rf / 252
    sigma2_d = garch_vol ** 2
    f_star = (mu_d - rf_d) / sigma2_d
    return alpha * np.clip(f_star, 0, 2)  # cap at 2x leverage


# --- Example: combine with a GARCH(1,1) forecast ---
def simple_garch_forecast(returns: np.ndarray, omega=1e-6,
                          alpha1=0.08, beta1=0.91) -> np.ndarray:
    """Recursive GARCH(1,1) volatility forecast."""
    n = len(returns)
    sigma2 = np.zeros(n)
    sigma2[0] = np.var(returns)
    for t in range(1, n):
        sigma2[t] = omega + alpha1 * returns[t-1]**2 + beta1 * sigma2[t-1]
    return np.sqrt(sigma2)


if __name__ == '__main__':
    rng = np.random.default_rng(42)
    returns = rng.normal(0.0006, 0.015, 500)

    garch_vol = simple_garch_forecast(returns)

    mu_est = 0.15  # 15% annual expected return
    sizes = dynamic_kelly_sizing(mu_est, garch_vol, alpha=0.25)

    print(f"Position size range:  [{sizes.min():.4f}, {sizes.max():.4f}]")
    print(f"Mean position size:   {sizes.mean():.4f}")
    print("Shrink during high-vol periods, expand during low-vol periods.")
```

### Production Integration Checklist

| Step | Action |
|------|--------|
| 1 | Fit GARCH(1,1) on rolling 1-2 year window of daily returns |
| 2 | Forecast next-day vol $hat{sigma}_{t+1}$ |
| 3 | Estimate $mu$ from a regime-aware model (e.g. moving average of Sharpe) |
| 4 | Compute $f_t = alpha cdot (mu - r_f) / hat{sigma}_{t+1}^2$ |
| 5 | Clip to reasonable bounds (e.g. $[0, 2]$) |
| 6 | Scale portfolio weights by $f_t$ |

### Key Rules

1. **Always use fractional Kelly** — $\alpha = 0.25$ to $0.5$ in practice
2. **Estimate $\mu$ conservatively** — better to under-estimate than over-estimate
3. **Combine with vol scaling** — dynamic Kelly + GARCH vol forecast = robust sizing
4. **Risk parity across uncorrelated signals** — allocate Kelly budget to each signal, then risk-parity them
5. **Monitor realized vol** — if actual vol > GARCH forecast, reduce $\alpha$ further

### Summary

$$\boxed{\text{Position Size} = \alpha \cdot \frac{\hat{\mu} - r_f}{\hat{\sigma}_{\text{GARCH}}^2}}$$

Where $\alpha \in [0.25, 0.5]$ and $\hat{\sigma}_{\text{GARCH}}$ comes from a GARCH(1,1) model (Lesson 6).
