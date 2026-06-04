# 时序分析深度 Time Series Analysis

## 平稳性

### 定义
**严平稳**：任意 $t_1,...,t_k$，$(X_{t_1},...,X_{t_k})$ 与 $(X_{t_1+h},...,X_{t_k+h})$ 同分布。
**弱平稳**（实际常用）：$E[X_t] = \mu$ 常数，$\text{Cov}(X_t, X_{t+h}) = \gamma(h)$ 仅依赖滞后 $h$。

### ADF 检验（Augmented Dickey-Fuller）
原假设 $H_0$：存在单位根（非平稳）。模型：
$$\Delta y_t = \alpha + \beta t + \gamma y_{t-1} + \sum_{i=1}^p \delta_i \Delta y_{t-i} + \varepsilon_t$$
检验 $\gamma = 0$（ADF 统计量 $\tau$，临界值非标准）。p 值 < 0.05 拒绝非平稳。

### KPSS 检验
原假设 $H_0$：序列平稳。与 ADF 互补使用。**联合策略**：
- ADF 不拒绝 + KPSS 拒绝 → 非平稳
- ADF 拒绝 + KPSS 不拒绝 → 平稳
- 两者都拒绝/都不拒绝 → 需进一步分析（如结构性断点）

---

## 自相关与偏自相关

### ACF（自相关函数）
$$\rho_k = \frac{\text{Cov}(Y_t, Y_{t-k})}{\text{Var}(Y_t)} = \frac{\gamma_k}{\gamma_0}$$

### PACF（偏自相关函数）
去除 $Y_{t-1},...,Y_{t-k+1}$ 影响后 $Y_t$ 与 $Y_{t-k}$ 的相关系数。通过 Yule-Walker 方程或 OLS 递归求解。

### ARIMA 阶数识别

| 模型 | ACF 特征 | PACF 特征 |
|------|---------|-----------|
| **AR(p)** | 拖尾（指数衰减） | $p$ 阶后截尾 |
| **MA(q)** | $q$ 阶后截尾 | 拖尾 |
| **ARMA(p,q)** | 拖尾 | 拖尾 |
| **ARIMA(p,d,q)** | 先差分 $d$ 次使平稳，再按 ARMA 识别 |

---

## ARIMA 建模

模型形式（$d$ 阶差分后）：
$$\Phi(B)(1-B)^d y_t = \Theta(B) \varepsilon_t$$
- $\Phi(B) = 1 - \phi_1 B - ... - \phi_p B^p$：AR 多项式
- $\Theta(B) = 1 + \theta_1 B + ... + \theta_q B^q$：MA 多项式
- $B$：滞后算子 $B y_t = y_{t-1}$

### AIC / BIC 定阶
$$\text{AIC} = -2\ln(\hat{L}) + 2k, \quad \text{BIC} = -2\ln(\hat{L}) + k\ln(T)$$
- AIC 倾向选更复杂模型（预测更优）
- BIC 倾向更简洁模型（过拟合惩罚更强）
- 实践中在 $p+q \leq 6$ 范围内网格搜索最小 AIC/BIC

---

## 季节性分解

### STL（Seasonal-Trend decomposition using LOESS）
加法分解：$Y_t = T_t + S_t + R_t$
- 内循环：用 LOESS（局部加权回归）平滑提取趋势、季节分量
- 外循环：鲁棒权重调整，抵抗异常值
- 优点：处理任意季节性、对异常值鲁棒、可指定季节平滑度

### X-13ARIMA-SEATS
美国人口普查局官方方法，含：
- **X-11**：移动平均为基础的季节调整
- **RegARIMA**：预处理（交易日效应、假日效应、异常值检测）
- **SEATS**：基于 ARIMA 模型的信号提取

---

## GARCH 波动率建模

### ARCH(q)
$$\sigma_t^2 = \alpha_0 + \sum_{i=1}^q \alpha_i \varepsilon_{t-i}^2$$

### GARCH(p,q)
$$\sigma_t^2 = \alpha_0 + \sum_{i=1}^q \alpha_i \varepsilon_{t-i}^2 + \sum_{j=1}^p \beta_j \sigma_{t-j}^2$$
- $\alpha_i$：新息冲击系数（短期波动）
- $\beta_j$：衰减系数（长期记忆）
- 约束：$\alpha_i, \beta_j \geq 0$, $\sum \alpha_i + \sum \beta_j < 1$（协方差平稳）

### 应用
金融资产收益率建模，VaR（风险价值）计算，期权定价。

---

## 卡尔曼滤波 Kalman Filter

### 状态空间模型
**状态方程**：$x_t = F_t x_{t-1} + B_t u_t + w_t, \quad w_t \sim \mathcal{N}(0, Q_t)$
**观测方程**：$z_t = H_t x_t + v_t, \quad v_t \sim \mathcal{N}(0, R_t)$

### 预测-更新循环

**预测**：
$$\hat{x}_{t|t-1} = F_t \hat{x}_{t-1|t-1} + B_t u_t$$
$$P_{t|t-1} = F_t P_{t-1|t-1} F_t^T + Q_t$$

**更新**：
$$K_t = P_{t|t-1} H_t^T (H_t P_{t|t-1} H_t^T + R_t)^{-1}$$
$$\hat{x}_{t|t} = \hat{x}_{t|t-1} + K_t (z_t - H_t \hat{x}_{t|t-1})$$
$$P_{t|t} = (I - K_t H_t) P_{t|t-1}$$

$K_t$ 是**卡尔曼增益**，平衡预测与观测的置信度。
