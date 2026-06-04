# Advanced Factor Models & Decorrelation

## 1. Fama-French Models

### FF3 (Market, Size, Value)

```python
import numpy as np

n, t = 5, 252
np.random.seed(42)
excess_ret = np.random.randn(t, n) * 0.02
mkt = np.random.randn(t) * 0.015
smb = np.random.randn(t) * 0.01
hml = np.random.randn(t) * 0.01

X = np.column_stack([np.ones(t), mkt, smb, hml])
betas = np.linalg.lstsq(X, excess_ret, rcond=None)[0]
print("FF3 betas (a, b_mkt, b_smb, b_hml):\n", betas.round(3))
```

### FF5 (adds Profitability, Investment)

```python
rmw = np.random.randn(t) * 0.01
cma = np.random.randn(t) * 0.01
X5 = np.column_stack([np.ones(t), mkt, smb, hml, rmw, cma])
betas5 = np.linalg.lstsq(X5, excess_ret, rcond=None)[0]
print("FF5 betas:\n", betas5.round(3))

# GRS test: tests if all alpha = 0
alpha = betas5[0]
resid = excess_ret - X5 @ betas5
Sigma = np.cov(resid, rowvar=False)
mu_f = X5[:, 1:].mean(axis=0)
Omega_f = np.cov(X5[:, 1:], rowvar=False)
T, K, N = t, 5, n
grs = (T/K) * ((T-N-K)/(T-K-1)) * (alpha @ np.linalg.inv(Sigma) @ alpha) / \
      (1 + mu_f @ np.linalg.inv(Omega_f) @ mu_f)
print(f"GRS (~F({N},{T-N-K})): {grs:.3f}")
```

---

## 2. Barra Risk Factor Model

Industry dummies + style factors -> covariance matrix.

```python
S, I, F = 100, 10, 5
np.random.seed(42)

ind_exposure = np.zeros((S, I))
for i in range(S):
    ind_exposure[i, np.random.randint(I)] = 1.0
style_exposure = np.random.randn(S, F)
X_barra = np.column_stack([ind_exposure, style_exposure])

F_cov = np.eye(I + F)
F_cov[I:, I:] = 0.3 ** np.abs(np.subtract.outer(np.arange(F), np.arange(F)))
spec_var = np.abs(np.random.randn(S)) * 0.01 + 0.005

total_cov = X_barra @ F_cov @ X_barra.T + np.diag(spec_var)

w = np.full(S, 1.0 / S)
port_risk = np.sqrt(w @ total_cov @ w)
print(f"EW portfolio risk (daily): {port_risk:.4f}")

factor_contrib = (w @ X_barra @ F_cov) * (X_barra.T @ w) / (port_risk ** 2)
top_idx = np.argsort(-np.abs(factor_contrib))[:5]
print("Top-5 factor risk contributions:", top_idx, factor_contrib[top_idx].round(3))
```

---

## 3. Factor Decorrelation Methods

### 3a. Residual Regression

Regress F1 on F2, keep residual as orthogonal factor.

```python
def orthogonalize_residual(F, ref_idx=0):
    """Orthogonalize all factors relative to factor at ref_idx."""
    F = np.asarray(F, dtype=float)
    T, K = F.shape
    F_ortho = F.copy()
    ref = F[:, [ref_idx]]
    for k in range(K):
        if k == ref_idx:
            continue
        X = np.column_stack([np.ones(T), ref])
        beta = np.linalg.lstsq(X, F[:, k], rcond=None)[0]
        F_ortho[:, k] = F[:, k] - X @ beta
    return F_ortho

# Demo with 3 correlated factors
T = 1000
rho = 0.7
F_raw = np.random.randn(T, 3)
F_raw[:, 1] = F_raw[:, 0] * rho + F_raw[:, 1] * np.sqrt(1 - rho ** 2)
F_raw[:, 2] = F_raw[:, 0] * 0.5 + F_raw[:, 1] * 0.3 + np.random.randn(T) * 0.5

F_ortho = orthogonalize_residual(F_raw, ref_idx=0)
print("Raw corr:\n", np.corrcoef(F_raw.T).round(3))
print("Ortho corr:\n", np.corrcoef(F_ortho.T).round(3))
```

### 3b. PCA Extraction

```python
def orthogonalize_pca(F, n_components=None):
    F = np.asarray(F, dtype=float)
    Fc = F - F.mean(axis=0)
    T, K = F.shape
    if n_components is None:
        n_components = K
    U, s, Vt = np.linalg.svd(Fc, full_matrices=False)
    PCs = U[:, :n_components] * s[:n_components]
    ev_ratio = s[:n_components] ** 2 / (s ** 2).sum()
    return PCs, ev_ratio, Vt[:n_components]

PCs, ev_ratio, _ = orthogonalize_pca(F_raw)
print("Explained variance per PC:", ev_ratio.round(3))
print("PC correlations:\n", np.corrcoef(PCs.T).round(3))
```

### 3c. Comparison: 4 Weighting Methods

```python
T = 2000
np.random.seed(42)
F = np.random.randn(T, 3)
F[:, 1] = 0.6 * F[:, 0] + 0.8 * np.random.randn(T)
F[:, 2] = 0.4 * F[:, 0] + 0.3 * F[:, 1] + 0.7 * np.random.randn(T)
future_ret = np.random.randn(T, 3) * 0.02
future_ret[:, 0] = 0.001 + future_ret[:, 0]
future_ret[:, 1] = -0.0005 + future_ret[:, 1]
future_ret[:, 2] = 0.0008 + future_ret[:, 2]

ic = np.array([np.corrcoef(F[:, i], (future_ret @ np.ones(3) / 3))[0, 1]
               for i in range(3)])

w_equal = np.ones(3) / 3
w_ic = ic / ic.sum()

F_ortho = orthogonalize_residual(F, ref_idx=0)
ic_ortho = np.array([np.corrcoef(F_ortho[:, i], (future_ret @ np.ones(3) / 3))[0, 1]
                     for i in range(3)])
w_ortho = ic_ortho / np.sum(np.abs(ic_ortho))

PCs, _, _ = orthogonalize_pca(F, 3)
ic_pc = np.array([np.corrcoef(PCs[:, i], (future_ret @ np.ones(3) / 3))[0, 1]
                  for i in range(3)])
w_pc = ic_pc / np.sum(np.abs(ic_pc))

def ann_sharpe(F_mat, w):
    c = F_mat @ w
    return c.mean() / c.std() * np.sqrt(252)

results = {"Equal-weight": ann_sharpe(F, w_equal),
           "IC-weight": ann_sharpe(F, w_ic),
           "Orthogonal": ann_sharpe(F_ortho, w_ortho),
           "PCA": ann_sharpe(PCs, w_pc)}

print(f"{'Method':<15} {'Ann. Sharpe':>12}")
print("-" * 28)
for name, s in results.items():
    print(f"{name:<15} {s:>12.3f}")
```

---

## 4. Runnable Demo: 3-Factor Orthogonalization

```python
def factor_orthogonalization_demo():
    """Momentum + Reversal + LowVol: raw vs orthogonalized vs PCA."""
    np.random.seed(42)
    T = 2000
    mom = np.random.randn(T) * 0.03
    mom[1:] += 0.1 * mom[:-1]
    rev = -0.5 * mom + np.random.randn(T) * 0.025
    lvol = 0.3 * rev + 0.2 * mom + np.random.randn(T) * 0.02
    F = np.column_stack([mom, rev, lvol])

    print("===== 3-Factor Orthogonalization Demo =====\n")
    print("Raw correlation matrix:")
    print(np.array_str(np.corrcoef(F.T), precision=3))

    F_ortho = orthogonalize_residual(F, ref_idx=0)
    print("\nOrthogonalized correlation matrix:")
    print(np.array_str(np.corrcoef(F_ortho.T), precision=3))

    print(f"\n{'Method':<15} {'Ann.Sharpe':>10}")
    print("-" * 27)
    for name, Fm in [("Raw", F), ("Orthogonalized", F_ortho)]:
        w = np.ones(Fm.shape[1]) / Fm.shape[1]
        c = Fm @ w
        s = c.mean() / c.std() * np.sqrt(12)
        print(f"{name:<15} {s:>10.3f}")

    PCs, _, _ = orthogonalize_pca(F, 3)
    w_pc = np.ones(3) / 3
    s_pc = (PCs @ w_pc).mean() / (PCs @ w_pc).std() * np.sqrt(12)
    print(f"{'PCA':<15} {s_pc:>10.3f}")

factor_orthogonalization_demo()
```

---

## 5. Integration: `orthogonalize_factors()`

```python
def orthogonalize_factors(F, method="residual", ref_idx=0,
                          n_components=None, keep_original_scale=True):
    """
    Decorrelate factor exposure matrix.

    Parameters
    ----------
    F : ndarray, shape (T, K)  --  raw factor returns
    method : str  --  "residual" | "pca" | "symqr"
    ref_idx : int  --  reference factor (residual method)
    n_components : int or None  --  PCs to retain
    keep_original_scale : bool  --  rescale PCA to match original vol

    Returns
    -------
    F_out : ndarray, shape (T, K) or (T, n_components)
    """
    F = np.asarray(F, dtype=float)
    T, K = F.shape

    if method == "residual":
        F_out = F.copy()
        ref = F[:, [ref_idx]]
        for k in range(K):
            if k == ref_idx:
                continue
            X = np.column_stack([np.ones(T), ref])
            beta = np.linalg.lstsq(X, F[:, k], rcond=None)[0]
            F_out[:, k] = F[:, k] - X @ beta
        return F_out

    elif method == "pca":
        Fc = F - F.mean(axis=0)
        U, s, Vt = np.linalg.svd(Fc, full_matrices=False)
        n_components = n_components or K
        PCs = U[:, :n_components] * s[:n_components]
        if keep_original_scale:
            scale = np.std(F, axis=0).mean()
            pc_scale = np.std(PCs, axis=0).mean()
            PCs = PCs * (scale / pc_scale) if pc_scale > 0 else PCs
        return PCs

    elif method == "symqr":
        Q, R = np.linalg.qr(F)
        for k in range(Q.shape[1]):
            if np.dot(Q[:, k], F[:, k]) < 0:
                Q[:, k] *= -1
        return Q

    raise ValueError(f"Unknown method: {method}")

if __name__ == "__main__":
    np.random.seed(42)
    F_test = np.random.randn(500, 4)
    F_test[:, 1] = 0.7 * F_test[:, 0] + 0.5 * np.random.randn(500)
    F_test[:, 2] = 0.3 * F_test[:, 0] + 0.4 * F_test[:, 1] + 0.6 * np.random.randn(500)
    F_test[:, 3] = 0.2 * F_test[:, 1] - 0.3 * F_test[:, 2] + 0.8 * np.random.randn(500)

    for method in ["residual", "pca", "symqr"]:
        Fo = orthogonalize_factors(F_test, method=method)
        corr = np.corrcoef(Fo.T)
        max_off = np.max(np.abs(corr - np.eye(Fo.shape[1])))
        print(f"{method:>10}: max off-diag corr = {max_off:.6f}")
```

---

## Summary

| Method | Pros | Cons |
|--------|------|------|
| **Residual regression** | Intuitive, directional, interpretable | Order-dependent |
| **PCA** | Dense decorrelation, dim reduction | Sign ambiguity, no factor ID |
| **QR (symqr)** | Symmetric, order-independent | Sign ambiguity |
| **IC-weighting** | Simple, no look-ahead | No true decorrelation |

**Tip:** Use residual against strongest factor for interpretability. Use PCA for large factor sets where identity is secondary.
