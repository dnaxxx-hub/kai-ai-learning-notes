# Quant Deep Lesson 5: Statistical Arbitrage

## 1. Review: Cointegration (from Lesson 3)

Two price series `P1[t]` and `P2[t]` are **cointegrated** if each is I(1) but there exists `β` such that:

```
spread[t] = P1[t] - β·P2[t]   is   I(0)   (stationary)
```

**Engle-Granger two-step procedure:**
1. OLS regression: `P1 = α + β·P2 + ε` → get `β_hat`
2. ADF test on residuals `ε` → reject unit root → cointegrated

When spread deviates from its mean by > `k` standard deviations, we take a contrarian bet:
- **spread too high**: short P1, long P2 (expect spread to mean-revert downward)
- **spread too low**: long P1, short P2 (expect spread to mean-revert upward)

---

## 2. Pairs Screening Pipeline

```
[Universe] → Correlation filter → Cointegration test → Half-life check → Tradeable pairs
```

### Step 1: Correlation filter
Cheap pre-filter. For each pair (i,j), compute Pearson `r` over a rolling window. Keep pairs with `|r| > threshold` (e.g. 0.8).

### Step 2: Cointegration test (ADF on residuals)
Engle-Granger ADF on regression residuals. P-value < 0.05 → pass.

### Step 3: Half-life of mean reversion
Halflife < some max (e.g. 60 days) → tradeable speed.

### Reference code

```python
import numpy as np
from scipy import stats
from scipy.linalg import LinAlgError

def correlation_matrix(prices: np.ndarray) -> np.ndarray:
    """Pearson correlation of price returns (n_assets, n_days → (n, n) corr)."""
    rets = np.diff(prices, axis=1)
    # demean and normalize each row
    demeaned = rets - rets.mean(axis=1, keepdims=True)
    stds = np.sqrt((demeaned ** 2).sum(axis=1))
    stds = np.maximum(stds, 1e-12)
    normed = demeaned / stds[:, None]
    return normed @ normed.T


def adf_test(residuals: np.ndarray, max_lag: int = 1) -> float:
    """Augmented Dickey-Fuller test (no constant, no trend) via OLS.
    Returns: approximate p-value under the null of unit root.
    Uses MacKinnon critical values for the no-constant case.
    """
    n = len(residuals)
    dy = np.diff(residuals, axis=0)
    y_lag = residuals[:-1]

    n_obs = n - 1
    K = min(max_lag, n_obs - 2)
    if K <= 0:
        X = y_lag.reshape(-1, 1)
        dy_used = dy
    else:
        lags = np.zeros((n_obs, K))
        for k in range(K):
            lags[k + 1:, k] = dy[:n_obs - k - 1]
        X = np.column_stack([y_lag, lags])
        valid = ~np.any(np.isnan(X), axis=1)
        X = X[valid]
        dy_used = dy[valid]

    try:
        beta = np.linalg.lstsq(X, dy_used, rcond=None)[0]
        resid = dy_used - X @ beta
        dof = len(dy_used) - X.shape[1]
        if dof <= 0:
            return 1.0
        s2 = (resid @ resid) / dof
        inv_xtx = np.linalg.inv(X.T @ X)
        se = np.sqrt(s2 * inv_xtx[0, 0])
        tau = beta[0] / se
    except (LinAlgError, np.linalg.LinAlgError):
        return 1.0

    # MacKinnon (1994) critical values for no-constant case, N=500
    # 1%: -2.57, 5%: -1.94, 10%: -1.62
    cv = {0.01: -2.57, 0.05: -1.94, 0.10: -1.62}
    # Simple interpolation: if tau < 1% cv, p < 0.01
    if tau < cv[0.01]:
        return 0.005  # approx p-value
    elif tau < cv[0.05]:
        return 0.03
    elif tau < cv[0.10]:
        return 0.07
    else:
        # tau > 10% cv, approximate with a scaled logistic
        return min(1.0, 0.15 + 0.85 / (1 + np.exp(-3 * (tau - cv[0.10]))))


def pairs_screening(prices: np.ndarray, corr_thresh: float = 0.8,
                    adf_pval_thresh: float = 0.05,
                    max_half_life: float = 60.0) -> list:
    """Full pairs screening pipeline.

    prices: (n_assets, n_days) numpy array
    Returns list of (i, j, corr, beta, half_life) for tradeable pairs.
    """
    n = prices.shape[0]
    corr = correlation_matrix(prices)
    results = []

    for i in range(n):
        for j in range(i + 1, n):
            if abs(corr[i, j]) < corr_thresh:
                continue

            p1, p2 = prices[i], prices[j]
            # Engle-Granger: regress P1 on P2
            A = np.column_stack([np.ones_like(p2), p2])
            try:
                coeffs = np.linalg.lstsq(A, p1, rcond=None)[0]
            except LinAlgError:
                continue
            alpha, beta = coeffs[0], coeffs[1]
            spread = p1 - beta * p2

            # ADF test on spread
            pval = adf_test(spread)
            if pval > adf_pval_thresh:
                continue

            # Half-life
            hl = half_life(spread)
            if hl is None or hl > max_half_life:
                continue

            results.append((i, j, corr[i, j], beta, hl))
    return results
```

---

## 3. Half-Life of Mean Reversion

Model the spread as an **Ornstein-Uhlenbeck** process:

```
dS = λ (μ - S) dt + σ dW
```

Discretize:

```
S[t+1] - S[t] = α + β S[t] + ε
```

where `β = -(1 - exp(-λ Δt))`. The half-life is:

```
half_life = ln(2) / λ
```

Since `λ ≈ -ln(1 + β)` for small Δt, and `β ≈ -(1 - e^{-λ})`, we can estimate via OLS and compute `λ = -ln(1 + β_hat)`.

**Simpler approach (used below):** OLS `ΔS ~ S_lag`, then `λ = -log(1 + β)` or approximate `half_life ≈ -ln(2) / ln(1 + β)`.

```python
def half_life(spread: np.ndarray) -> float | None:
    """Estimate half-life of mean reversion via OLS.

    ΔS[t] = α + β·S[t-1] + ε
    half_life = -ln(2) / ln(1 + β)
    """
    y = np.diff(spread)
    x = spread[:-1]
    A = np.column_stack([np.ones_like(x), x])
    try:
        coeffs = np.linalg.lstsq(A, y, rcond=None)[0]
    except LinAlgError:
        return None
    beta = coeffs[1]

    if beta >= 0:
        return None  # not mean-reverting
    hl = -np.log(2) / np.log(1 + beta)
    return float(hl) if np.isfinite(hl) and hl > 0 else None
```

---

## 4. Kalman Filter for Dynamic Hedge Ratio

Static OLS `β` breaks when the relationship drifts. **Kalman filter** lets `β` evolve over time.

### State-space model:
- **State** (hedge ratio): `β[t] = β[t-1] + w[t]`,   `w ~ N(0, Q)`
- **Observation**: `P1[t] = β[t] · P2[t] + v[t]`,   `v ~ N(0, R)`

### Kalman recursion:

```
Predict:
  β_pred[t] = β[t-1]
  P_pred[t] = P[t-1] + Q

Update:
  K[t] = P_pred[t]·P2[t] / (P_pred[t]·P2[t]² + R)
  β[t] = β_pred[t] + K[t]·(P1[t] - β_pred[t]·P2[t])
  P[t] = (1 - K[t]·P2[t])·P_pred[t]
```

```python
def kalman_beta(p1: np.ndarray, p2: np.ndarray,
                Q: float = 1e-5, R: float = 1e-2) -> np.ndarray:
    """Time-varying hedge ratio via Kalman filter.

    Returns: array of beta[t] for each observation.
    """
    n = len(p1)
    beta = np.zeros(n)
    P = np.ones(n)  # state variance

    beta[0] = p1[0] / max(p2[0], 1e-12)
    P[0] = 1.0

    for t in range(1, n):
        # Predict
        beta_pred = beta[t - 1]
        P_pred = P[t - 1] + Q

        # Update
        K = P_pred * p2[t] / (P_pred * p2[t]**2 + R)
        innovation = p1[t] - beta_pred * p2[t]
        beta[t] = beta_pred + K * innovation
        P[t] = (1 - K * p2[t]) * P_pred

    return beta


def spread_dynamic(p1: np.ndarray, p2: np.ndarray,
                   Q: float = 1e-5, R: float = 1e-2) -> np.ndarray:
    """Spread using time-varying beta from Kalman filter."""
    beta = kalman_beta(p1, p2, Q, R)
    return p1 - beta * p2
```

### Tuning Q and R
- **Q** (process noise): larger = beta changes faster
- **R** (observation noise): larger = smoother beta, less responsive

Rule of thumb: start with `Q ≈ 1e-5 * var(p1)`, `R ≈ 1e-2 * var(p1)`.

---

## 5. Multi-Pair Portfolio: Kelly Allocation

### Spread z-score per pair

Normalize each spread to z-score, then size each leg:

```python
def spread_zscore(spread: np.ndarray) -> float:
    """Latest spread expressed as z-score of rolling history."""
    mu = np.mean(spread)
    sigma = np.std(spread, ddof=1)
    if sigma < 1e-12:
        return 0.0
    return (spread[-1] - mu) / sigma
```

### Kelly allocation across pairs

For each pair, the expected excess return from a mean-reversion bet is approximately:

```
E[ΔS] ≈ -z · (1 - exp(-λ)) · σ_S
```

where `z` is current z-score, `λ = ln(2)/half_life`, `σ_S` is spread volatility.

**Kelly fraction** for a binary-like mean-reversion bet (simplified):

```python
def kelly_fraction(z: float, half_life: float, sigma_spread: float,
                   win_prob: float | None = None) -> float:
    """Approximate Kelly fraction for a single pair.

    Uses the approximation: f* ≈ (p * b - q) / b
    where p = probability spread reverts toward mean, b = expected return ratio.
    """
    if win_prob is not None:
        b = 1.0  # assume 1:1 (rough parity)
        q = 1 - win_prob
        return max(0.0, (win_prob * b - q) / b)

    # Fallback: position size proportional to |z|, capped at Kelly fraction
    z_abs = min(abs(z), 3.0)
    # Simple Kelly proxy: f = z_abs / 3 * 0.2 (max 20% per pair)
    return min(z_abs / 3.0 * 0.2, 0.2)
```

### Full multi-pair allocation

```python
def multi_pair_allocation(pairs: list[dict],
                          total_capital: float = 1_000_000.0) -> dict:
    """Compute position sizes across pairs using Kelly allocation.

    pairs: list of dicts with keys:
        - p1, p2: price arrays
        - z: current z-score of spread (positive means P1 expensive)
        - half_life: half-life in days
        - sigma_spread: spread standard deviation

    Returns: dict mapping pair_id -> (position_p1, position_p2, weight)
    """
    allocations = {}
    total_kelly = 0.0
    kellys = []

    # First pass: compute raw Kelly fractions
    for p in pairs:
        k = kelly_fraction(p['z'], p['half_life'], p['sigma_spread'])
        kellys.append(k)
        total_kelly += k

    if total_kelly < 1e-12:
        return {i: (0.0, 0.0, 0.0) for i in range(len(pairs))}

    # Scale to total capital (Kelly sum may exceed 1, so normalize)
    scale = min(1.0, 1.0 / total_kelly) if total_kelly > 1.0 else 1.0

    for i, p in enumerate(pairs):
        weight = (kellys[i] / total_kelly) * scale
        cap = total_capital * weight

        # Position sizing: dollar-neutral long/short
        z = p['z']
        sigma = max(p['sigma_spread'], 1e-8)
        p1_price = p['p1'][-1]
        p2_price = p['p2'][-1]

        # Spread notional: if z > 0, short P1 / long P2
        # Normalize to 1 standard deviation move = 1 unit of capital risk
        notional_per_unit = sigma  # 1σ spread move per unit
        units = cap / max(notional_per_unit, 1e-8)

        if z > 0:
            pos_p1 = -units / max(p1_price, 1e-8)   # short shares
            pos_p2 = units / max(p2_price, 1e-8)    # long shares
        else:
            pos_p1 = units / max(p1_price, 1e-8)
            pos_p2 = -units / max(p2_price, 1e-8)

        allocations[i] = (pos_p1, pos_p2, weight)

    return allocations
```

---

## 6. Integration: pair_trading Function

The `pair_trading` function ties together the full pipeline and can accept a scoring function (e.g. from Lesson 4's multifactor model) to pre-filter candidate pairs.

```python
def pair_trading(prices: np.ndarray,
                 corr_thresh: float = 0.8,
                 adf_pval_thresh: float = 0.05,
                 max_hl: float = 60.0,
                 kalman_Q: float = 1e-5,
                 kalman_R: float = 1e-2,
                 total_capital: float = 1_000_000.0,
                 score_fn=None,
                 top_n: int = 5) -> dict:
    """Complete pairs trading pipeline.

    Args:
        prices: (n_assets, n_days) price matrix
        corr_thresh: minimum |correlation| for screening
        adf_pval_thresh: maximum ADF p-value for cointegration
        max_hl: maximum acceptable half-life
        kalman_Q, kalman_R: Kalman filter parameters
        total_capital: portfolio capital
        score_fn: optional callable(prices) -> array of asset scores
                  to use for pair selection (from multifactor model)
        top_n: number of top-scoring pairs to trade

    Returns:
        dict with keys:
            'pairs': list of (i, j, stats) for tradeable pairs
            'allocations': dict mapping pair index -> (pos_p1, pos_p2, weight)
            'scores': asset scores if score_fn provided
    """
    n_assets = prices.shape[0]

    # Optional scoring pre-filter
    scores = None
    if score_fn is not None:
        scores = score_fn(prices)
        # Only consider top 2*top_n assets by score
        top_idx = np.argsort(scores)[-2*top_n:]
        prices_subset = prices[top_idx]
    else:
        prices_subset = prices

    # Pairs screening
    screened = pairs_screening(prices_subset, corr_thresh, adf_pval_thresh, max_hl)

    if not screened:
        return {'pairs': [], 'allocations': {}, 'scores': scores}

    # Build pair dicts for allocation
    pair_list = []
    for i, j, r, beta, hl in screened:
        p1, p2 = prices_subset[i], prices_subset[j]
        spread = spread_dynamic(p1, p2, kalman_Q, kalman_R)
        z = spread_zscore(spread)
        sigma_s = max(np.std(spread, ddof=1), 1e-8)

        pair_list.append({
            'p1': p1, 'p2': p2,
            'z': z,
            'half_life': hl,
            'sigma_spread': sigma_s,
            'beta': beta,
            'corr': r,
            'i_orig': i,
            'j_orig': j,
        })

    # Sort by |z| (most dislocated first), take top_n
    pair_list.sort(key=lambda x: abs(x['z']), reverse=True)
    pair_list = pair_list[:top_n]

    # Kelly allocation
    allocs = multi_pair_allocation(pair_list, total_capital)

    return {
        'pairs': [(p['i_orig'], p['j_orig'],
                    {'corr': p['corr'], 'beta': p['beta'],
                     'half_life': p['half_life'], 'z_score': p['z']})
                   for p in pair_list],
        'allocations': allocs,
        'scores': scores,
    }


# ---------------------------------------------------------------------------
# Demo / smoke test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    np.random.seed(42)
    n_assets, n_days = 6, 252

    # Simulate cointegrated pairs
    # Pair (0,1): cointegrated, half-life ~20 days
    # Pair (2,3): cointegrated, half-life ~10 days
    # Pair (4,5): not cointegrated (random walks)
    common = np.cumsum(np.random.randn(n_days) * 0.5) + 100
    noise1 = np.zeros(n_days)
    noise2 = np.zeros(n_days)
    beta1, beta2 = 1.2, 0.8

    # OU process for spread: S[t] = S[t-1] + λ*(μ - S[t-1]) + ε
    lam1, lam2 = 0.03, 0.07  # λ -> half-life ≈ ln2/λ
    s1, s2 = np.zeros(n_days), np.zeros(n_days)
    s1[0], s2[0] = 0.0, 0.0
    for t in range(1, n_days):
        s1[t] = s1[t-1] + lam1 * (-s1[t-1]) + np.random.randn() * 0.3
        s2[t] = s2[t-1] + lam2 * (-s2[t-1]) + np.random.randn() * 0.2

    p0 = common + np.random.randn(n_days) * 0.5
    p1 = beta1 * p0 + s1
    p3 = common + np.random.randn(n_days) * 0.8
    p2 = beta2 * p3 + s2
    p4 = np.cumsum(np.random.randn(n_days) * 0.3) + 100
    p5 = np.cumsum(np.random.randn(n_days) * 0.3) + 100

    prices = np.array([p0, p1, p3, p2, p4, p5])

    result = pair_trading(prices, top_n=3)
    print(f"Tradeable pairs found: {len(result['pairs'])}")
    for i, j, stats in result['pairs']:
        print(f"  Pair ({i},{j}): z={stats['z_score']:.2f}, "
              f"hl={stats['half_life']:.1f}d, "
              f"corr={stats['corr']:.3f}, beta={stats['beta']:.3f}")

    print(f"\nAllocations ({len(result['allocations'])} pairs):")
    for idx, (pos1, pos2, w) in result['allocations'].items():
        print(f"  Pair {idx}: pos1={pos1:+.1f}, pos2={pos2:+.1f}, weight={w:.3f}")

    print("\n--- Unit tests ---")
    # Test correlation_matrix
    cm = correlation_matrix(prices)
    assert cm.shape == (n_assets, n_assets), "corr shape"
    assert abs(cm[0, 0] - 1.0) < 1e-6, "self-corr"
    print("  correlation_matrix: OK")

    # Test half_life
    hl = half_life(s1)
    assert hl is not None and 15 < hl < 30, f"hl={hl}"
    print(f"  half_life (pair 0,1): {hl:.1f}d, expected ~23d: OK")

    hl2 = half_life(s2)
    assert hl2 is not None and 5 < hl2 < 15, f"hl2={hl2}"
    print(f"  half_life (pair 2,3): {hl2:.1f}d, expected ~10d: OK")

    # Test Kalman beta
    kb = kalman_beta(p1, p0)
    assert len(kb) == n_days
    assert np.abs(np.mean(kb) - beta1) < 0.2
    print(f"  kalman_beta: mean={np.mean(kb):.3f}, true={beta1}: OK")

    # Test spread_zscore
    z = spread_zscore(s1)
    assert isinstance(z, float)
    print(f"  spread_zscore: {z:.3f}: OK")

    # Test kelly_fraction
    k = kelly_fraction(2.0, 20.0, 1.0)
    assert 0.0 < k <= 0.2
    print(f"  kelly_fraction: {k:.4f}: OK")

    # Test pairs_screening
    screened = pairs_screening(prices)
    pairs_found = len(screened)
    print(f"  pairs_screening: {pairs_found} tradeable pairs: OK")
    assert pairs_found >= 1, f"should find at least one pair, found {pairs_found}"

    print("\nAll tests passed ✓")
```

---

## Key Takeaways

| Concept | Formula / Method |
|---------|-----------------|
| **Cointegration** | `P1 - β·P2 ~ I(0)`, tested via Engle-Granger + ADF |
| **Pairs screening** | Correlation filter → ADF on residuals → half-life check |
| **Half-life** | `-ln(2) / ln(1 + β)` from OLS `ΔS ~ S_lag` |
| **Dynamic beta** | Kalman filter: `β[t] = β[t-1] + w`, observation `P1 = β·P2 + v` |
| **Position sizing** | Spread z-score → Kelly fraction → dollar-neutral long/short |
| **Multi-pair portfolio** | Scale Kelly fractions to total capital, normalize if sum > 1 |

### When Kalman > Static OLS
- **Yes**: structural breaks, drifting correlations, evolving fundamentals
- **No**: stable relationships, short lookbacks, low signal-to-noise (Kalman adds parameter uncertainty)

### Integration with multifactor (Lesson 4)
The `score_fn` hook allows using multifactor alpha scores to narrow the universe before pair screening — combining cross-sectional factor selection with time-series mean reversion.
