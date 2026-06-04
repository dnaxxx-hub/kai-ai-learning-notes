# 第5课：数值计算与稳定性

> 在量化交易中，看似微小的浮点误差累积到一定程度就会造成灾难——回测曲线漂亮但实盘惨败，K线计算出现负数成交量，风险指标计算不收敛。本课深入数值计算的底层机制，连根拔起这些隐患。

---

## 1. IEEE 754 浮点数陷阱

### 1.1 浮点数不是实数

```python
import numpy as np
import math
import warnings
warnings.filterwarnings('ignore')

print("=== 浮点数基础测试 ===")
print(f"0.1 + 0.2 == 0.3 ? {0.1 + 0.2 == 0.3}")
print(f"0.1 + 0.2 = {0.1 + 0.2:.30f}")
print(f"0.3       = {0.3:.30f}")
print(f"eps(1)    = {np.finfo(np.float64).eps}")
print(f"eps(1e10) = {np.spacing(1e10)}")  # 大数附近精度更低
print()

# 浮点数的机器精度演示
x = 1.0
while 1.0 + x != 1.0:
    x /= 2
print(f"float64 机器精度: {x * 2}")  # 约 2.22e-16

# 大数加小数被吞噬
big = 1e16
small = 1.0
print(f"1e16 + 1.0 = {big + small:.1f}")  # 等于 1e16，1被吞噬！
```

### 1.2 Catastrophic Cancellation（灾难性抵消）

这是量化交易中最常见也最隐蔽的陷阱。

**本质**：两个很近的值相减，**有效数字全部丢失**。

```python
print("=== Catastrophic Cancellation 演示 ===")

def bad_variance(x):
    """教科书式方差公式：Σx² - (Σx)²/n —— 有灾难性抵消风险"""
    n = len(x)
    return (np.sum(x**2) - (np.sum(x)**2) / n) / (n - 1)

def good_variance(x):
    """Welford在线算法：无灾难性抵消"""
    n = len(x)
    if n <= 1:
        return 0.0
    mean = x[0]
    M2 = 0.0
    for i in range(1, n):
        delta = x[i] - mean
        mean += delta / (i + 1)
        M2 += delta * (x[i] - mean)
    return M2 / (n - 1)

# 构造一个均值很大、方差很小的序列
np.random.seed(42)
x = 1e10 + np.random.randn(1000) * 1e-3

bad_var = bad_variance(x)
good_var = good_variance(x)
true_var = np.var(x, ddof=1)

print(f"真实方差:       {true_var:.15e}")
print(f"教科书公式:     {bad_var:.15e}")
print(f"Welford算法:    {good_var:.15e}")
print(f"教科书误差倍数: {abs(bad_var - true_var) / true_var:.0f}x")
print()

# 更直观的例子：二次方程求根
def bad_quadratic_root(a, b, c):
    """直接用求根公式，当b>>4ac时有抵消"""
    sqrt_d = math.sqrt(b*b - 4*a*c)
    x1 = (-b + sqrt_d) / (2*a)
    x2 = (-b - sqrt_d) / (2*a)
    return x1, x2

def good_quadratic_root(a, b, c):
    """用韦达定理避免抵消"""
    sqrt_d = math.sqrt(b*b - 4*a*c)
    # 选取绝对值大的项避免抵消
    if b >= 0:
        x1 = (-b - sqrt_d) / (2*a)  # 两个负数相加，无抵消
    else:
        x1 = (-b + sqrt_d) / (2*a)  # 两个正数相加，无抵消
    x2 = c / (a * x1)  # 韦达定理：x1 * x2 = c/a
    return x1, x2

a, b, c = 1, 1e8, 1
x1_bad, x2_bad = bad_quadratic_root(a, b, c)
x1_good, x2_good = good_quadratic_root(a, b, c)

print(f"二次方程: x² + {b}x + {c} = 0")
print(f"朴素法:  x1={x1_bad:.10f}, x2={x2_bad:.10f}")
print(f"稳定法:  x1={x1_good:.10f}, x2={x2_good:.10f}")
print(f"真解:    x1={-1e-8:.10f}, x2={-1e8:.10f}")
print()

# ✅ 量化交易中的抵消场景
print("=== 量化场景：价格差抵消 ===")
# 两个价格很接近的资产价差计算
p1 = 100.05
p2 = 100.03
spread = p1 - p2  # 0.02，精度OK
print(f"价差: {spread}")

# 但如果是千分之一级别的小价差
p1_big = 100000.05
p2_big = 100000.03
spread_big = p1_big - p2_big
print(f"大数价差: {spread_big:.10f}")  # 可能只有 6-7位有效数字
print(f"相对误差: {abs(spread_big - 0.02) / 0.02:.2e}")
```

### 1.3 Overflow与Underflow

```python
print("=== Overflow / Underflow ===")

# Underflow: 太小到0
tiny = 1e-300
print(f"1e-300 ** 2 = {tiny ** 2:.0e}")  # → 0 (下溢)
print(f"1e-200 ** 2 = {1e-200 ** 2:.0e}")  # → 0 (下溢)
print(f"log(1e-300) = {math.log(1e-300)}")  # 还能算
print(f"log(1e-400) = ", end="")
try:
    print(math.log(1e-400))
except ValueError as e:
    print(f"ValueError: {e}")  # 负无穷

# Overflow: 太大到inf
print(f"1e200 ** 2 = {1e200 ** 2}")
print(f"exp(800) = ", end="")
try:
    print(math.exp(800))
except OverflowError:
    print("OverflowError")

# ✅ Softmax直接计算的风险
def softmax_naive(x):
    """朴素Softmax —— 数值不稳定"""
    exp_x = np.exp(x)
    return exp_x / np.sum(exp_x)

x_large = np.array([1000, 1001, 1002])
try:
    p = softmax_naive(x_large)
    print(f"\n朴素Softmax(大输入): {p}")
except:
    print(f"\n朴素Softmax(大输入): 溢出/NaN!")
```

---

## 2. Log-Sum-Exp Trick

这是数值稳定性的**皇冠上的明珠**，在ML/量化中无处不在。

### 2.1 核心思想

```python
def logsumexp_naive(x):
    """朴素 log(Σexp(x_i)) —— 数值危险"""
    return math.log(sum(math.exp(xi) for xi in x))

def logsumexp_stable(x):
    """稳定 log(Σexp(x_i)) = c + log(Σexp(x_i - c))
    其中 c = max(x) 是最优选择"""
    c = max(x)
    return c + math.log(sum(math.exp(xi - c) for xi in x))

print("=== Log-Sum-Exp Trick ===")
x = [1000, 1001, 1002, 999]
try:
    result = logsumexp_naive(x)
    print(f"朴素LSE: {result}")
except:
    print("朴素LSE: 溢出!")

result_stable = logsumexp_stable(x)
print(f"稳定LSE: {result_stable}")
print(f"理论值:  1002 + log(1 + exp(-1) + exp(-2) + exp(-3)) ≈ {1002 + math.log(1 + math.exp(-1) + math.exp(-2) + math.exp(-3)):.6f}")
print()

# 向量化版本
def logsumexp_numpy(x, axis=None):
    """numpy向量化，支持多维"""
    c = np.max(x, axis=axis, keepdims=True)
    return c + np.log(np.sum(np.exp(x - c), axis=axis, keepdims=True))

x_vec = np.array([[1000, 1001, 1002], [2000, 2001, 2002]])
print(f"向量化LSE: {logsumexp_numpy(x_vec, axis=1).ravel()}")

# 梯度也是稳定的
def softmax_gradient_stable(x):
    """Softmax的雅可比矩阵，数值稳定"""
    s = softmax_stable(x)
    return np.diag(s) - np.outer(s, s)

def softmax_stable(x):
    """完整数值稳定的Softmax"""
    shift_x = x - np.max(x)
    exp_x = np.exp(shift_x)
    return exp_x / np.sum(exp_x)

x_test = np.array([2.0, 1.0, 0.1])
print(f"\n稳定Softmax: {softmax_stable(x_test)}")
print(f"概率和: {np.sum(softmax_stable(x_test)):.6f}")
```

### 2.2 Negative Log-Likelihood（NLL）的数值优化

```python
# 交叉熵损失的数值稳定版本
def cross_entropy_naive(y_true, logits):
    """朴素交叉熵 —— logits很大时爆炸"""
    p = softmax_naive(logits)
    return -np.sum(y_true * np.log(p + 1e-15))

def cross_entropy_stable(y_true, logits):
    """稳定交叉熵 —— 直接合并log和softmax
    log(softmax(x)_i) = x_i - logsumexp(x)
    """
    lse = logsumexp_numpy(logits)
    return -np.sum(y_true * (logits - lse))

y = np.array([1.0, 0.0, 0.0])
logits = np.array([1000.0, 999.0, 998.0])

try:
    ce_naive = cross_entropy_naive(y, logits)
    print(f"朴素交叉熵: {ce_naive}")
except:
    print("朴素交叉熵: NaN!")

ce_stable = cross_entropy_stable(y, logits)
print(f"稳定交叉熵: {ce_stable:.6f}")
print(f"理论值:     {1000 - logsumexp_stable(logits):.6f}")
```

### 2.3 Log-Space是一切的核心

```python
# 概率乘法在log空间进行
def log_prob_product(log_probs):
    """log空间概率乘积：避免underflow"""
    return np.sum(log_probs)

# 概率加法在log空间进行
def log_prob_add(log_a, log_b):
    """log空间概率加法：log(a + b)"""
    # 方法：log(a+b) = log(exp(log_a) + exp(log_b))
    # 用logsumexp思想
    c = max(log_a, log_b)
    return c + math.log(math.exp(log_a - c) + math.exp(log_b - c))

def log_prob_add_numpy(log_a, log_b):
    """向量化版本"""
    c = np.maximum(log_a, log_b)
    return c + np.log(np.exp(log_a - c) + np.exp(log_b - c))

# 应用：HMM中的前向算法
probs = np.array([-1000.0, -1001.0, -1002.0])  # log空间概率
print(f"log空间概率加法: {log_prob_add_numpy(probs[0], probs[1]):.6f}")
print(f"朴素加法会underflow: {math.exp(-1000) + math.exp(-1001):.0e}")
```

---

## 3. Softmax的数值稳定实现

### 3.1 生产级Softmax

```python
class NumericallyStableSoftmax:
    """完整数值稳定的Softmax实现（C++化思路）"""
    
    @staticmethod
    def forward(x, axis=-1):
        """前向传播，支持多维"""
        # Step 1: 减去最大值（LSE trick核心）
        x_max = np.max(x, axis=axis, keepdims=True)
        x_shifted = x - x_max
        
        # Step 2: 对相对值做exp（安全）
        exp_x = np.exp(x_shifted)
        
        # Step 3: 归一化
        sum_exp = np.sum(exp_x, axis=axis, keepdims=True)
        
        # ✅ 安全检查：detect NaN or Inf
        if not np.all(np.isfinite(exp_x)):
            warnings.warn("Softmax detected non-finite values, clipping")
            exp_x = np.clip(exp_x, -1e100, 1e100)
        
        return exp_x / sum_exp
    
    @staticmethod
    def log_softmax(x, axis=-1):
        """log(softmax(x)) —— 直接合并"""
        x_max = np.max(x, axis=axis, keepdims=True)
        x_shifted = x - x_max
        log_sum_exp = np.log(np.sum(np.exp(x_shifted), axis=axis, keepdims=True))
        return x - x_max - log_sum_exp
    
    @staticmethod
    def backward(dout, out):
        """反向传播梯度（雅可比矩阵高效版本）"""
        # dL/dx = (dL/ds) · (diag(s) - s·s^T)
        # 更高效的实现: dL/dx = s * (dL/ds - sum(dL/ds * s))
        s = out
        ds = dout
        return s * (ds - np.sum(ds * s, axis=-1, keepdims=True))

# 测试
print("=== 生产级Softmax测试 ===")
x = np.array([[1000, 1001, 1002], [2000, 2001, 2002]], dtype=np.float64)
sns = NumericallyStableSoftmax()
probs = sns.forward(x)
log_probs = sns.log_softmax(x)
print(f"Softmax:    {probs}")
print(f"LogSoftmax: {log_probs}")
print(f"Softmax sum by row: {np.sum(probs, axis=1)}")
```

### 3.2 C语言实现思路

```c
/*
 * C语言数值稳定Softmax（libkds思路）
 * 
 * 关键设计：
 * 1. 所有计算使用 double（非 float）
 * 2. 先找最大值再exp，避免overflow
 * 3. 使用 restrict 关键字允许编译器优化
 * 
 * void softmax_stable(const double* input, double* output, int n) {
 *     // Step 1: find max
 *     double max_val = input[0];
 *     for (int i = 1; i < n; i++) {
 *         if (input[i] > max_val) max_val = input[i];
 *     }
 *     
 *     // Step 2: exp with shift
 *     double sum = 0.0;
 *     for (int i = 0; i < n; i++) {
 *         output[i] = exp(input[i] - max_val);
 *         sum += output[i];
 *     }
 *     
 *     // Step 3: normalize
 *     double inv_sum = 1.0 / sum;  // 乘法代替除法
 *     for (int i = 0; i < n; i++) {
 *         output[i] *= inv_sum;
 *     }
 * }
 */
```

---

## 4. 矩阵运算的条件数

### 4.1 条件数的本质

```python
print("=== 矩阵条件数 ===")

def condition_number(A):
    """计算条件数 κ(A) = ||A|| · ||A⁻¹|| """
    return np.linalg.cond(A)

# 病态矩阵演示
A_well = np.array([[2, 0], [0, 1]])  # 良态
A_ill = np.array([[1, 0.999], [0.999, 1]])  # 病态

print(f"良态矩阵 cond={condition_number(A_well):.4f}")
print(f"病态矩阵 cond={condition_number(A_ill):.4f}")

b = np.array([1.0, 1.0])
x_well = np.linalg.solve(A_well, b)
x_ill = np.linalg.solve(A_ill, b)

print(f"良态解: {x_well}")
print(f"病态解: {x_ill}")

# 微小扰动 → 巨大变化
b_noisy = np.array([1.0, 1.001])
x_ill_noisy = np.linalg.solve(A_ill, b_noisy)
print(f"病态(扰动b): {x_ill_noisy}")
print(f"病态解变化: {np.linalg.norm(x_ill - x_ill_noisy):.4f}")
```

### 4.2 量化应用：协方差矩阵的条件数

```python
print("=== 协方差矩阵条件数（量化重点） ===")

# 高度相关资产 → 病态协方差矩阵
np.random.seed(42)
n_assets = 20
n_obs = 200

# 模拟5个板块，每个板块内高度相关
colors = np.zeros(20)
colors[:4] = 1   # 板块1
colors[4:8] = 2  # 板块2
colors[8:12] = 3 # 板块3
colors[12:16] = 4 # 板块4
colors[16:] = 5  # 板块5

returns = np.random.randn(n_obs, n_assets) * 0.02
# 板块内添加相关性
for i in range(4):
    sector = returns[:, i*4:(i+1)*4]
    common = np.random.randn(n_obs) * 0.015
    sector += common[:, np.newaxis]

cov = np.cov(returns, rowvar=False)
cond_cov = np.linalg.cond(cov)
print(f"协方差矩阵条件数: {cond_cov:.2f}")

# 条件数 > 1e6 → 高度病态，逆矩阵不可靠
if cond_cov > 1e6:
    print("⚠️ 条件数过大！协方差矩阵求逆不稳定")
    print("   → 需用伪逆或正则化")

# 正则化：给对角加一个小值
def regularize_cov(cov, alpha=1e-6):
    """黎登正则化（Ridge shrinkage）"""
    return cov + alpha * np.eye(cov.shape[0])

cov_reg = regularize_cov(cov, alpha=1e-4)
cond_reg = np.linalg.cond(cov_reg)
print(f"正则化后条件数: {cond_reg:.2f}")

# 影响：Minimum Variance Portfolio
def min_variance_portfolio(cov):
    """最小方差组合 w = Σ⁻¹·1 / (1ᵀ·Σ⁻¹·1)"""
    n = cov.shape[0]
    inv_cov = np.linalg.inv(cov)
    ones = np.ones(n)
    w = inv_cov @ ones / (ones.T @ inv_cov @ ones)
    return w

w_naive = min_variance_portfolio(cov)
w_reg = min_variance_portfolio(cov_reg)
print(f"\n原始协方差组合(前5权重): {w_naive[:5].round(4)}")
print(f"正则化组合(前5权重):    {w_reg[:5].round(4)}")
print(f"组合权重的L2范数差异: {np.linalg.norm(w_naive - w_reg):.4f}")
```

---

## 5. 实战：K线计算 & 回测累积误差

### 5.1 K线计算的精度问题

```python
print("=== 实战：K线计算精度 ===")

def compute_ema_naive(prices, alpha):
    """朴素EMA实现 —— 累积浮点误差"""
    ema = prices[0]
    emas = [ema]
    for p in prices[1:]:
        ema = alpha * p + (1 - alpha) * ema
        emas.append(ema)
    return np.array(emas)

def compute_ema_stable(prices, alpha):
    """稳定EMA：使用Kahan求和抑制累积误差"""
    ema = prices[0]
    emas = [ema]
    c = 0.0  # Kahan补偿项
    for p in prices[1:]:
        # 计算更新量
        step = alpha * (p - ema)
        
        # Kahan求和: 将上一步的误差补偿回来
        y = step - c
        t = ema + y
        c = (t - ema) - y  # (a+b) - a 只留下被丢弃的低位
        ema = t
        
        emas.append(ema)
    return np.array(emas)

def compute_ema_precise(prices, alpha):
    """高精度EMA：用Decimal（基准真相）"""
    from decimal import Decimal, getcontext
    getcontext().prec = 50
    
    d_alpha = Decimal(str(alpha))
    ema = Decimal(str(prices[0]))
    emas = [float(ema)]
    for p in prices[1:]:
        ema = d_alpha * Decimal(str(p)) + (Decimal(1) - d_alpha) * ema
        emas.append(float(ema))
    return np.array(emas)

# 测试：长序列的累积误差
np.random.seed(42)
n = 100000
prices = 100.0 + np.cumsum(np.random.randn(n) * 0.1)

alpha = 0.01
ema_naive = compute_ema_naive(prices, alpha)
ema_stable = compute_ema_stable(prices, alpha)
ema_precise = compute_ema_precise(prices, alpha)

err_naive = np.abs(ema_naive[-1] - ema_precise[-1])
err_stable = np.abs(ema_stable[-1] - ema_precise[-1])

print(f"真实值(Decimal): {ema_precise[-1]:.10f}")
print(f"朴素EMA:         {ema_naive[-1]:.10f}  (误差: {err_naive:.2e})")
print(f"Kahan EMA:       {ema_stable[-1]:.10f}  (误差: {err_stable:.2e})")
print(f"误差缩小倍数:     {err_naive / err_stable:.0f}x")
```

### 5.2 回测中的累积误差

```python
print("=== 实战：回测累积误差 ===")

class BacktestEngine:
    """带精度控制的回测引擎"""
    
    def __init__(self, use_kahan=False, initial_capital=1_000_000.0):
        self.capital = initial_capital
        self.position = 0.0
        self.trades = []
        self.use_kahan = use_kahan
        self.compensation = 0.0  # Kahan补偿
        self.total_pnl = 0.0
        
        # 精确日志（Decimal基准）
        self.pnl_log = []
    
    def _add_pnl(self, pnl):
        """Kahan求和方式累积PNL"""
        if self.use_kahan:
            y = pnl - self.compensation
            t = self.total_pnl + y
            self.compensation = (t - self.total_pnl) - y
            self.total_pnl = t
        else:
            self.total_pnl += pnl
    
    def execute_trade(self, price, shares, commission=0.0001):
        """执行交易"""
        cost = price * shares
        commission_fee = cost * commission
        actual_cost = cost + commission_fee
        
        if self.capital >= actual_cost:
            self.capital -= actual_cost
            self.position += shares
            self.trades.append({
                'price': price,
                'shares': shares,
                'cost': actual_cost,
                'commission': commission_fee
            })
            return True
        return False
    
    def mark_to_market(self, current_price):
        """盯市，计算PNL"""
        prev_value = self.capital  # 可能有误
        # 正确的PNL = 当前总价值 - 投入总成本
        total_cost = sum(t['cost'] for t in self.trades)
        current_value = self.capital + self.position * current_price
        pnl = current_value - total_cost
        
        self._add_pnl(pnl)
        return pnl

# 模拟大量小交易 → 累积误差
np.random.seed(42)
n_trades = 100000
prices = 100.0 + np.random.randn(n_trades) * 10

# 朴素版本
engine_naive = BacktestEngine(use_kahan=False)
for price in prices:
    if np.random.random() < 0.5:
        engine_naive.execute_trade(price, 10)

# Kahan版本
engine_kahan = BacktestEngine(use_kahan=True)
for price in prices:
    if np.random.random() < 0.5:
        engine_kahan.execute_trade(price, 10)

print(f"朴素回测PNL: {engine_naive.total_pnl:.10f}")
print(f"Kahan回测PNL: {engine_kahan.total_pnl:.10f}")
print(f"差异: {abs(engine_naive.total_pnl - engine_kahan.total_pnl):.6f}")
print()

# 更严重的问题：浮点比较
def check_stop_loss_naive(price, entry_price, stop_pct=0.05):
    """浮点比较止损 —— 有时会错过"""
    return (entry_price - price) / entry_price >= stop_pct

def check_stop_loss_stable(price, entry_price, stop_pct=0.05):
    """使用epsilon避免边界错误"""
    eps = 1e-10
    return (entry_price - price) >= stop_pct * entry_price - eps

entry = 100.05
price = 95.0475  # 刚好在5%止损线上
print(f"止损检查:")
print(f"  朴素方法: {check_stop_loss_naive(price, entry)}")
print(f"  稳定方法: {check_stop_loss_stable(price, entry)}")
```

### 5.3 数值稳定的协整检验

```python
print("=== 协整检验数值稳定性 ===")

def cointegration_test_stable(y1, y2):
    """数值稳定的协整检验"""
    from sklearn.linear_model import LinearRegression
    
    # 使用标准化值避免大数
    y1_std = (y1 - np.mean(y1)) / np.std(y1)
    y2_std = (y2 - np.mean(y2)) / np.std(y2)
    
    # OLS回归
    reg = LinearRegression().fit(y2_std.reshape(-1, 1), y1_std)
    residuals = y1_std - reg.predict(y2_std.reshape(-1, 1)).ravel()
    
    # ADF检验（用statsmodels，内部已做数值优化）
    from statsmodels.tsa.stattools import adfuller
    result = adfuller(residuals, maxlag=1, autolag=None)
    
    return {
        'adf_stat': result[0],
        'p_value': result[1],
        'residuals': residuals,
        'hedge_ratio': reg.coef_[0] * np.std(y1) / np.std(y2),  # 反标准化
        'is_cointegrated': result[1] < 0.05
    }

# 生成测试数据
np.random.seed(42)
n = 500
error = np.random.randn(n) * 0.5
z = np.cumsum(np.random.randn(n))  # 随机游走
y1 = z + error  # 协整对
y2 = z + np.random.randn(n) * 0.3

result = cointegration_test_stable(y1, y2)
print(f"ADF统计量: {result['adf_stat']:.4f}")
print(f"p-value:   {result['p_value']:.6f}")
print(f"是否协整:   {result['is_cointegrated']}")
print(f"对冲比率:   {result['hedge_ratio']:.4f}")
```

---

## 6. 与羽的ML/DL/量化经验的关联

### 6.1 直接关联点

| 场景 | 陷阱 | 解决方案 |
|------|------|----------|
| Softmax Loss | overflow | log-softmax + LSE trick |
| Cov矩阵求逆 | rank deficient | 对角正则化 |
| 长回测 | 累积浮点误差 | Kahan求和 |
| 因子协方差 | 条件数过大 | 收缩估计 |
| 概率乘法链 | underflow | log空间计算 |

### 6.2 PyTorch/TensorFlow内部做的

```python
# PyTorch的CrossEntropyLoss已经合并了LogSoftmax+NLLLoss
# 它们的实现等价于：
def cross_entropy_torch_equivalent(logits, targets):
    """PyTorch内部的CrossEntropyLoss"""
    log_probs = logits - logsumexp_numpy(logits)
    return -np.mean(log_probs[np.arange(len(targets)), targets])

logits = np.array([[1000, 1001, 1002], 
                    [999, 998, 1000]])
targets = np.array([2, 0])
print(f"等价torch交叉熵: {cross_entropy_torch_equivalent(logits, targets)}")
```

### 6.3 对libkds/KVStore的应用建议

**libkds（C++核心库）：**
1. **Kahan求和模板**：`template<typename T> struct KahanAccumulator` — 全局用在EMA/VWAP计算
2. **数值稳定的Softmax**：`void softmax(const double* in, double* out, int n)` — 先shift再exp
3. **伪逆实现**：`void pseudoinverse(const double* A, int m, int n, double* out)` — 处理病态协方差
4. **LogSumExp**：`double logsumexp(const double* x, int n)` — 概率计算基础设施

**KVStore：**
1. 存储矩阵的条件数元数据（cond_key = f"{matrix_key}/condition_number"）
2. 存储时检查数值范围，超出精度阈值时告警
3. 用KV存储"数值稳定性日志"——记录哪些计算出现过精度丢失

---

## 附录：Cheat Sheet

```python
# ===== 数值稳定性速查表 =====

# 1. 大数 + 小数的陷阱
# ❌ result = 1e16 + 1.0  # 1被吃掉
# ✅ 使用Decimal或分解计算

# 2. 避免灾难性抵消
# ❌ var = mean(x²) - mean(x)²
# ✅ var = np.mean((x - np.mean(x))**2)  # 先减均值再平方

# 3. 概率计算在log空间
# ❌ p1 * p2 * p3  # underflow
# ✅ log(p1) + log(p2) + log(p3)

# 4. Softmax减最大值
# ✅ softmax(x) = exp(x - max(x)) / sum(exp(x - max(x)))

# 5. 协方差矩阵正则化
# ✅ cov_reg = cov + lambda * I

# 6. Kahan求和
# ✅ y = input - c; t = sum + y; c = (t - sum) - y; sum = t

# 7. 浮点数比较用阈值
# ❌ if a == b:
# ✅ if abs(a - b) < eps:
```

> **一句话总结**：量化系统中的数值问题不是"偶尔出错的极端情况"，而是"在长周期运行中必然发生的常态"。学会用log空间、Kahan求和、正则化这些工具，写出的代码才能跑5年不出错。
