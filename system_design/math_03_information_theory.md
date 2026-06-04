# 第3课：信息论深潜 — 熵、散度与信息瓶颈

> 前置：已熟悉交叉熵损失，本课聚焦信息论核心概念的numpy实现和ML/量化实战

## 1. 熵（Entropy）— 不确定性的度量

### 1.1 自信息与熵

$$I(x) = -\log p(x), \quad H(X) = E[-\log p(X)] = -\sum p(x) \log p(x)$$

```python
import numpy as np
from scipy.stats import entropy as scipy_entropy

def entropy_manual(p, base=np.e):
    """手写熵计算"""
    p = np.array(p, dtype=float)
    p = p / p.sum()  # 归一化
    return -np.sum(p * np.log(p) / np.log(base))  # log base conversion

def entropy_demo():
    """熵的理解：不同分布的随机性度量"""
    
    print("=== 熵：不确定性度量 ===")
    
    # 1. 确定事件 vs 随机事件
    certain = [1, 0]     # 一定正面
    fair = [0.5, 0.5]    # 公平硬币
    biased = [0.9, 0.1]  # 偏倚硬币
    
    print("\n二元分布的熵:")
    print(f"  确定事件 [1,0]: H={entropy_manual(certain):.3f} bits")
    print(f"  公平硬币 [0.5,0.5]: H={entropy_manual(fair):.3f} bits (最大熵)")
    print(f"  偏倚硬币 [0.9,0.1]: H={entropy_manual(biased):.3f} bits")
    
    # 2. 均匀分布的熵随维度增长
    print("\n均匀分布的熵 vs 维度:")
    for n in [2, 4, 8, 16, 32]:
        uniform = np.ones(n) / n
        h = entropy_manual(uniform)
        print(f"  n={n:2d}: H={h:.3f} nats = {h/np.log(2):.3f} bits")
    
    # 3. 理解"bits"的含义
    fair_entropy = entropy_manual(fair)
    print(f"\n公平硬币的熵 = {fair_entropy:.3f} bits")
    print(f"含义：平均需要{fair_entropy:.3f}个比特来编码每次投掷结果")
    print(f"(最优编码：用1bit表示正/反，无法压缩更低)")

entropy_demo()
```

### 1.2 联合熵、条件熵与链式法则

```python
def joint_conditional_entropy():
    """联合熵、条件熵与链式法则"""
    
    # 构造联合分布 P(X,Y)
    # X: 天气 {晴,雨}, Y: 情绪 {高兴,低落}
    P = np.array([[0.4, 0.1],   # P(晴,高兴), P(晴,低落)
                   [0.2, 0.3]])  # P(雨,高兴), P(雨,低落)
    
    # 边缘分布
    Px = P.sum(axis=1)  # P(X)
    Py = P.sum(axis=0)  # P(Y)
    
    # 条件分布 P(Y|X)
    Py_given_x = P / Px[:, np.newaxis]
    
    # 联合熵 H(X,Y)
    H_xy = -np.sum(P * np.log(P + 1e-10))
    
    # 边缘熵 H(X)
    Hx = -np.sum(Px * np.log(Px))
    
    # 条件熵 H(Y|X) = Σ P(x) * H(Y|X=x)
    Hy_given_x = np.sum(Px * -np.sum(Py_given_x * np.log(Py_given_x + 1e-10), axis=1))
    
    # 链式法则：H(X,Y) = H(X) + H(Y|X)
    chain_rule = Hx + Hy_given_x
    
    print("=== 联合熵与条件熵 ===")
    print(f"联合分布 P(X,Y):\n{P}")
    print(f"\nH(X)     = {Hx:.3f}")
    print(f"H(Y|X)   = {Hy_given_x:.3f}")
    print(f"H(X,Y)   = {H_xy:.3f}")
    print(f"链式法则 = {chain_rule:.3f} (H(X) + H(Y|X))")
    print(f"验证一致: {np.allclose(H_xy, chain_rule)}")
    
    # 相关性意味着条件熵 < 边缘熵
    print(f"\n知识减少不确定性:")
    print(f"H(Y)   = {-np.sum(Py * np.log(Py)):.3f}")
    print(f"H(Y|X) = {Hy_given_x:.3f}")
    print(f"知道天气后情绪的不确定性减少了 {(-np.sum(Py * np.log(Py)) - Hy_given_x):.3f}")
    print(f"即互信息 I(X;Y)")

joint_conditional_entropy()
```

## 2. KL散度与JS散度

### 2.1 KL散度定义和性质

$$KL(P\|Q) = \sum_x P(x) \log\frac{P(x)}{Q(x)}$$

```python
def kl_divergence_manual(p, q):
    """手写KL散度"""
    p = np.array(p, dtype=float) + 1e-10
    q = np.array(q, dtype=float) + 1e-10
    p = p / p.sum()
    q = q / q.sum()
    return np.sum(p * np.log(p / q))

def kl_demo():
    """KL散度性质演示"""
    
    print("=== KL散度的性质 ===")
    
    # 1. 非负性
    p = np.array([0.2, 0.3, 0.5])
    q = np.array([0.25, 0.25, 0.5])
    
    print("\n1. 非负性:")
    print(f"  KL(p||p) = {kl_divergence_manual(p, p):.6f} (自身=0)")
    print(f"  KL(p||q) = {kl_divergence_manual(p, q):.4f} (正数)")
    print(f"  KL(q||p) = {kl_divergence_manual(q, p):.4f} (不对称!)")
    print(f"  不对称: KL(p||q) ≠ KL(q||p)")
    
    # 2. 前向KL vs 反向KL
    print("\n2. 前向KL (moment projection) vs 反向KL (mode projection):")
    # 真实分布是双峰，近似分布是单峰
    true_dist = np.array([0.3, 0.2, 0.2, 0.3])
    
    # 两个候选近似
    approx_broad = np.array([0.25, 0.25, 0.25, 0.25])  # 宽
    approx_mode = np.array([0.5, 0.2, 0.2, 0.1])  # 抓主峰
    
    print(f"  真实:       {true_dist}")
    print(f"  近似-宽:    {approx_broad}")
    print(f"  近似-主峰:  {approx_mode}")
    print(f"  前向KL(真||宽)   = {kl_divergence_manual(true_dist, approx_broad):.4f}")
    print(f"  前向KL(真||主峰) = {kl_divergence_manual(true_dist, approx_mode):.4f}")
    print(f"  反向KL(宽||真)   = {kl_divergence_manual(approx_broad, true_dist):.4f}")
    print(f"  反向KL(主峰||真) = {kl_divergence_manual(approx_mode, true_dist):.4f}")
    print(f"\n  前向KL → 平均值行为（在P有概率的地方Q都要覆盖）")
    print(f"  反向KL → 模式寻找行为（Q集中在P的一个峰上）")
    print(f"  这是 variational inference 的核心直觉")
    
    # 3. 数值稳定性
    print("\n3. 数值稳定性:")
    print(f"  KL([0.999,0.001] || [0.001,0.999]) = {kl_divergence_manual([0.999,0.001], [0.001,0.999]):.2f}")
    print(f"  当Q趋于0时KL趋于无穷 → 注意避免零概率")

kl_demo()
```

### 2.2 JS散度

$$JS(P\|Q) = \frac{1}{2}KL(P\|M) + \frac{1}{2}KL(Q\|M), \quad M = \frac{P+Q}{2}$$

```python
def js_divergence_manual(p, q):
    """手写JS散度（对称且有界）"""
    p = np.array(p, dtype=float) + 1e-10
    q = np.array(q, dtype=float) + 1e-10
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)
    return 0.5 * (kl_divergence_manual(p, m) + kl_divergence_manual(q, m))

def js_demo():
    """JS散度 vs KL散度对比"""
    print("=== JS散度 vs KL散度 ===")
    
    p = np.array([0.4, 0.3, 0.2, 0.1])
    
    # 不同差距的q
    qs = {
        "相同": [0.4, 0.3, 0.2, 0.1],
        "接近": [0.35, 0.3, 0.2, 0.15],
        "不同": [0.6, 0.2, 0.1, 0.1],
        "相反": [0.1, 0.2, 0.3, 0.4],
        "极端": [1.0, 0.0, 0.0, 0.0],
    }
    
    print(f"{'q分布':<8} {'KL(P||Q)':<12} {'KL(Q||P)':<12} {'JS(P,Q)':<12} {'JS^{1/2}':<10}")
    print("-" * 56)
    
    for name, q in qs.items():
        kl_pq = kl_divergence_manual(p, q)
        kl_qp = kl_divergence_manual(q, p)
        js = js_divergence_manual(p, q)
        js_sqrt = np.sqrt(js)  # JS距离 = sqrt(JS散度)
        print(f"{name:<8} {kl_pq:<12.4f} {kl_qp:<12.4f} {js:<12.4f} {js_sqrt:<10.4f}")
    
    print("\nJS散度 vs KL散度的优势:")
    print("  1. 对称: JS(P,Q) = JS(Q,P)")
    print(f"  2. 有界: 0 ≤ JS ≤ {np.log(2):.4f} (当P,Q完全不重叠时)")
    print(f"  3. 平方根JS距离是度量（满足三角不等式）")
    print("  4. GAN用JS散度代替KL，训练更稳定")

js_demo()
```

### 2.3 互信息（Mutual Information）

$$I(X;Y) = KL(P(X,Y)\|P(X)P(Y)) = H(X) - H(X|Y)$$

```python
def mutual_information_manual(X, Y, bins=20):
    """从数据估算互信息"""
    # 离散化
    x_bins = np.linspace(X.min(), X.max(), bins+1)
    y_bins = np.linspace(Y.min(), Y.max(), bins+1)
    
    x_idx = np.digitize(X, x_bins[:-1])
    y_idx = np.digitize(Y, y_bins[:-1])
    
    # 联合直方图
    joint_hist = np.zeros((bins, bins))
    for xi, yi in zip(x_idx, y_idx):
        joint_hist[xi-1, yi-1] += 1
    
    joint_hist = joint_hist / joint_hist.sum()
    
    # 边缘直方图
    px = joint_hist.sum(axis=1)
    py = joint_hist.sum(axis=0)
    
    # 互信息 = KL(联合 || 边缘乘积)
    mi = 0
    for i in range(bins):
        for j in range(bins):
            if joint_hist[i,j] > 0:
                mi += joint_hist[i,j] * np.log(joint_hist[i,j] / (px[i] * py[j]))
    
    return mi

def mi_demo():
    """互信息：检测非线性相关"""
    np.random.seed(42)
    n = 500
    
    # 线性相关
    X1 = np.random.randn(n)
    Y1 = 0.8 * X1 + 0.6 * np.random.randn(n)
    
    # 非线性相关（X^2）
    X2 = np.random.randn(n)
    Y2 = X2**2 + np.random.randn(n) * 0.3
    
    # 无相关
    X3 = np.random.randn(n)
    Y3 = np.random.randn(n)
    
    print("=== 互信息 vs 皮尔逊相关系数 ===")
    
    for name, x, y in [("线性相关", X1, Y1), 
                        ("平方关系", X2, Y2),
                        ("独立", X3, Y3)]:
        pearson = np.corrcoef(x, y)[0, 1]
        mi = mutual_information_manual(x, y)
        
        print(f"\n{name}:")
        print(f"  皮尔逊ρ = {pearson:.4f}")
        print(f"  互信息 = {mi:.4f}")
    
    print("\n互信息优势：能检测任意非线性依赖关系")

mi_demo()
```

## 3. 交叉熵损失深层理解

### 3.1 从KL散度推导交叉熵

$$KL(P\|Q) = \sum P(x)\log\frac{P(x)}{Q(x)} = \underbrace{-\sum P(x)\log Q(x)}_{H(P,Q)} - \underbrace{H(P)}_{\text{常数}}$$

```python
def cross_entropy_deep():
    """交叉熵损失的深层理解"""
    
    print("=== 交叉熵损失的深层理解 ===")
    print()
    
    # 分类任务：最小化交叉熵 = 最小化KL散度
    # 因为 H(P) 是常数（真实分布的熵）
    
    # 单分类（交叉熵损失）
    p_true = np.array([0, 0, 1, 0, 0])  # one-hot
            
    # 不同预测
    preds = {
        "完美": [0.01, 0.01, 0.94, 0.02, 0.02],
        "良好": [0.1, 0.1, 0.6, 0.1, 0.1],
        "中等": [0.1, 0.2, 0.4, 0.15, 0.15],
        "差":   [0.3, 0.3, 0.1, 0.15, 0.15],
        "差(低置信)": [0.35, 0.3, 0.05, 0.15, 0.15],
    }
    
    print("多分类交叉熵损失 (CE = -Σp*log(q)):")
    print(f"{'预测质量':<16} {'CE':<10} {'KL(P||Q)':<12} {'H(P)':<10} {'H(P,Q)':<12}")
    print("-" * 60)
    
    Hp = -np.sum(p_true * np.log(p_true + 1e-10))  # = 0
    
    for name, q in preds.items():
        q = np.array(q)
        ce = -np.sum(p_true * np.log(q + 1e-10))
        kl = kl_divergence_manual(p_true, q)
        H_pq = ce  # H(P,Q) = CE when P is one-hot
        
        print(f"{name:<16} {ce:<10.4f} {kl:<12.4f} {Hp:<10.4f} {H_pq:<12.4f}")
    
    print("\n关键洞察:")
    print("  最小化交叉熵 ≡ 最小化KL(P真||Q预测)")
    print("  H(P)是常数 → 优化等价")
    print("  当P是one-hot时，CE = -log(q_correct)")
    print("  这解释了为什么交叉熵损失会指数地惩罚错误预测")

cross_entropy_deep()
```

### 3.2 二元交叉熵梯度分析

```python
def bce_gradient_analysis():
    """二元交叉熵的梯度行为"""
    
    print("=== 二元交叉熵损失梯度分析 ===")
    
    def bce(pred, target):
        eps = 1e-15
        pred = np.clip(pred, eps, 1-eps)
        return -(target * np.log(pred) + (1-target) * np.log(1-pred))
    
    def bce_gradient(pred, target):
        return -(target / pred - (1-target) / (1-pred))
    
    y_true = 1.0
    
    predictions = np.array([0.001, 0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99, 0.999])
    
    print("当真实标签=1时:")
    print(f"{'预测值':>8} {'损失':>10} {'梯度':>12} {'梯度解释':<20}")
    print("-" * 52)
    
    for pred in predictions:
        loss = bce(pred, y_true)
        grad = bce_gradient(pred, y_true)
        
        if pred < 0.01:
            expl = "梯度极大！快速修正"
        elif pred < 0.5:
            expl = "较强梯度，推动预测↑"
        elif pred < 0.9:
            expl = "温和梯度，微调"
        else:
            expl = "接近收敛，梯度很小"
        
        print(f"{pred:>8.3f} {loss:>10.4f} {grad:>12.2f} {expl:<20}")
    
    print("\n为什么梯度随预测值变化？")
    print("  预测接近0时，log(p) → -∞，梯度巨大")
    print("  这解释了为什么交叉熵在训练初期收敛快")
    print("  → 它对置信但错误的预测给予无穷惩罚")

bce_gradient_analysis()
```

## 4. 最大熵原理

### 4.1 核心思想

在满足已知约束的条件下，选择熵最大的分布（最随机、最不偏不倚的分布）。

```python
def max_entropy_principle():
    """最大熵原理演示"""
    
    print("=== 最大熵原理 ===")
    print("在满足约束下选择最随机的分布")
    print()
    
    # 约束1: 均值固定为μ
    # 最大熵分布 = 指数族
    # - 无约束 → 均匀分布
    # - 固定均值 → 指数分布
    # - 固定均值和方差 → 正态分布
    # - 支持[0,1]且固定均值 → Beta分布
    # - 离散无约束 → 均匀分布
    # - 离散固定均值 → 几何分布
    
    print("常见约束 → 最大熵分布:")
    print(f"{'约束':<30} {'最大熵分布':<20}")
    print("-" * 50)
    print(f"{'无约束':<30} {'均匀分布':<20}")
    print(f"{'固定均值, 支持[0,∞)':<30} {'指数分布':<20}")
    print(f"{'固定均值, 支持R':<30} {'正态分布':<20}")
    print(f"{'固定均值, 支持[0,1]':<30} {'Beta分布':<20}")
    print(f"{'固定均值和方差, 支持(-∞,∞)':<30} {'正态分布':<20}")
    print(f"{'离散, 固定均值':<30} {'几何分布':<20}")
    print()
    
    # 手工验证：固定均值的最大熵分布
    print("手工验证：固定均值μ=5的离散分布")
    x = np.arange(1, 21)
    mu = 5.0
    
    # 在约束 Σp_i = 1, Σx_i p_i = 5 下最大化熵
    # 拉格朗日法 → p_i ∝ exp(-λ*x_i)
    # 我们需要找到λ使得均值≈5
    
    def find_lambda(target_mu):
        """数值求解λ"""
        from scipy.optimize import brentq
        def f(lam):
            p = np.exp(-lam * x)
            p /= p.sum()
            return (p * x).sum() - target_mu
        return brentq(f, 0.001, 1.0)
    
    lam_opt = find_lambda(mu)
    p_maxent = np.exp(-lam_opt * x)
    p_maxent /= p_maxent.sum()
    
    print(f"\nλ = {lam_opt:.4f}")
    print(f"实际均值: {(p_maxent * x).sum():.4f}")
    print(f"熵 H = {-np.sum(p_maxent * np.log(p_maxent)):.4f}")
    print("\n这就是几何分布（指数族的离散形式）")

max_entropy_principle()
```

## 5. 信息瓶颈理论

### 5.1 IB核心思想

$$ \min I(X;Z) - \beta I(Z;Y) $$

学习Z：压缩输入X（丢掉不相关的噪音），同时保留对Y的预测能力。

```python
def information_bottleneck_concept():
    """信息瓶颈理论可视化"""
    
    print("=== 信息瓶颈理论 ===")
    print()
    print("核心权衡公式:")
    print("  min: I(X;Z) - β·I(Z;Y)")
    print()
    print("  I(X;Z) = 编码器保留的输入信息")
    print("  I(Z;Y) = 中间表示对标签的预测信息")
    print("  β = 权衡参数（大β→更压缩，小β→更准确）")
    print()
    
    # 不同β下的最优表示
    print("不同β下的学习行为:")
    betas = [0.1, 0.5, 1.0, 5.0, 10.0]
    
    print(f"{'β':>6} {'压缩程度':<12} {'预测能力':<12} {'行为':<20}")
    print("-" * 52)
    
    for beta in betas:
        if beta < 0.5:
            comp, pred, behav = "低", "高", "过拟合：记住全部输入"
        elif beta < 2:
            comp, pred, behav = "中", "高", "最优权衡"
        elif beta < 8:
            comp, pred, behav = "高", "中", "高压缩，损失部分准确率"
        else:
            comp, pred, behav = "极高", "低", "过度压缩，接近随机"
        
        print(f"{beta:>6.1f} {comp:<12} {pred:<12} {behav:<20}")
    
    print()
    print("深度学习中信息瓶颈的体现:")
    print("  - 深层网络：逐层压缩I(X;Z)，提炼I(Z;Y)")
    print("  - Dropout: 在训练中引入噪声，降低I(X;Z)")
    print("  - BatchNorm: 稳定分布，影响I(Z;Y)")
    print("  - VAE: ELBO = E[log P(X|Z)] - KL[q(Z|X)||p(Z)]")
    print("    这是信息瓶颈的变体：重构(预测) vs KL(压缩)")

information_bottleneck_concept()
```

## 6. ML/量化实战

### 6.1 互信息特征选择

```python
def mi_feature_selection():
    """用互信息做特征选择"""
    np.random.seed(42)
    
    n_samples = 500
    n_features = 20
    
    # 构造：只有前3个特征与目标相关
    X = np.random.randn(n_samples, n_features)
    
    # 非线性依赖
    y = (0.8 * X[:, 0]**2 + 
         0.6 * np.sin(X[:, 1]) + 
         0.4 * np.exp(-np.abs(X[:, 2])) +
         0.2 * np.random.randn(n_samples))
    
    print("=== 互信息特征选择 ===")
    print(f"数据: {n_samples}样本, {n_features}特征")
    print(f"真实相关: 特征0(x²), 特征1(sin), 特征2(exp)")
    print()
    
    # 计算每个特征的互信息
    n_bins = 30
    y_bins = np.linspace(y.min(), y.max(), n_bins + 1)
    y_idx = np.digitize(y, y_bins[:-1])
    
    mi_scores = []
    for j in range(n_features):
        # 离散化特征j
        x_bins = np.linspace(X[:, j].min(), X[:, j].max(), n_bins + 1)
        x_idx = np.digitize(X[:, j], x_bins[:-1])
        
        # 联合直方图
        joint = np.zeros((n_bins, n_bins))
        for xi, yi in zip(x_idx, y_idx):
            joint[xi-1, yi-1] += 1
        
        joint = joint / joint.sum()
        
        # 互信息
        px = joint.sum(axis=1)
        py = joint.sum(axis=0)
        
        mi = 0
        for i in range(n_bins):
            for jj in range(n_bins):
                if joint[i,jj] > 0:
                    mi += joint[i,jj] * np.log(joint[i,jj] / (px[i] * py[jj]))
        
        mi_scores.append(mi)
    
    # 排序
    sorted_idx = np.argsort(mi_scores)[::-1]
    
    print(f"{'排名':>4} {'特征':>6} {'MI':>10} {'相关性?':<10}")
    print("-" * 32)
    for rank, idx in enumerate(sorted_idx[:10]):
        is_relevant = "★相关" if idx < 3 else ""
        print(f"{rank+1:>4} {f'X{idx}':>6} {mi_scores[idx]:>10.4f} {is_relevant:<10}")
    
    print("\n✓ 互信息成功识别出非线性相关特征")
    print("  (皮尔逊相关在这种非线性场景下会失效)")

mi_feature_selection()
```

### 6.2 KL散度做模型蒸馏

```python
def knowledge_distillation():
    """
    知识蒸馏：用KL散度让小模型学大模型
    
    蒸馏损失 L = α·CE(y_teacher, y_student) + β·KL(p_teacher||p_student)
    其中p用softmax with temperature：p_i = exp(z_i/T) / Σexp(z_j/T)
    """
    np.random.seed(42)
    
    n_classes = 10
    n_samples = 100
    
    # 大模型的logits（"暗知识"）
    teacher_logits = np.random.randn(n_samples, n_classes) * 3
    # 让大模型在真实标签上有更高logits
    y_true = np.random.randint(0, n_classes, n_samples)
    teacher_logits[np.arange(n_samples), y_true] += 5
    
    # 小模型的logits
    student_logits = np.random.randn(n_samples, n_classes) * 2
    
    def softmax_with_temp(logits, temp=1.0):
        logits = logits / temp
        exp = np.exp(logits - logits.max(axis=1, keepdims=True))
        return exp / exp.sum(axis=1, keepdims=True)
    
    print("=== 知识蒸馏演示 ===")
    
    # 不同温度下的软标签
    for T in [1, 2, 5, 10]:
        teacher_soft = softmax_with_temp(teacher_logits, T)
        student_soft = softmax_with_temp(student_logits, T)
        
        # KL散度
        kl = np.mean([kl_divergence_manual(teacher_soft[i], student_soft[i]) 
                      for i in range(n_samples)])
        
        # 蒸馏损失
        ce_hard = -np.mean(np.log(student_soft[np.arange(n_samples), y_true] + 1e-10))
        
        print(f"\n温度 T={T}:")
        print(f"  KL(p老师||p学生) = {kl:.4f}")
        print(f"  CE(硬标签) = {ce_hard:.4f}")
        
        if T == 1:
            print(f"  → T=1: 硬标签，类间信息丢失")
        elif T == 5:
            print(f"  → T=5: 软标签好，类间相似性保留")
    
    print("\n蒸馏的核心思想:")
    print("  大模型预测'猫'的softmax输出可能是:")
    print("  猫: 0.85, 狗: 0.10, 虎: 0.03, ...")
    print("  小模型从'猫vs狗vs虎'的区分中学习，而不只是'猫vs其他'")
    print("  → 暗知识：类别间的相似性结构")

knowledge_distillation()
```

### 6.3 量化：信息论风险度量

```python
def information_theoretic_risk():
    """
    用信息论概念分析策略风险
    
    - 熵：策略收益的"随机性"（越大越随机）
    - KL散度：策略分布 vs 基准分布
    - 互信息：策略与市场因子的"信息共享"
    """
    np.random.seed(42)
    
    n_days = 500
    
    # 三个策略
    # 策略A：随机交易（白噪声）
    returns_A = np.random.randn(n_days) * 0.02
    
    # 策略B：趋势跟随
    market_ret = np.random.randn(n_days) * 0.01
    returns_B = 0.6 * market_ret + 0.016 * np.random.randn(n_days)
    
    # 策略C：有择时能力
    signal = np.where(market_ret > 0, 1, -0.5)
    returns_C = 0.8 * signal * np.abs(market_ret) + 0.01 * np.random.randn(n_days)
    
    def calc_entropy(returns, bins=30):
        hist, _ = np.histogram(returns, bins=bins, density=True)
        hist = hist / hist.sum() + 1e-10
        return -np.sum(hist * np.log(hist))
    
    print("=== 信息论风险度量 ===")
    
    for name, rets in [("策略A-白噪声", returns_A), 
                        ("策略B-趋势跟随", returns_B),
                        ("策略C-择时能力", returns_C)]:
        
        H = calc_entropy(rets)
        sharpe = np.sqrt(252) * rets.mean() / rets.std()
        
        print(f"\n{name}:")
        print(f"  熵 H(ret): {H:.3f}")
        print(f"  夏普比: {sharpe:.2f}")
        print(f"  '信息率' ≈ 可用信息/总不确定性")
    
    # 用KL散度比较策略与基准
    print("\nKL(策略||市场) — 策略的"独特性":")
    baseline_dist, _ = np.histogram(market_ret, bins=30, density=True)
    baseline_dist = baseline_dist / baseline_dist.sum() + 1e-10
    
    for name, rets in [("策略A", returns_A), ("策略B", returns_B), ("策略C", returns_C)]:
        strat_dist, _ = np.histogram(rets, bins=30, density=True)
        strat_dist = strat_dist / strat_dist.sum() + 1e-10
        kl = kl_divergence_manual(strat_dist, baseline_dist)
        print(f"  KL({name}||市场) = {kl:.4f} (越大说明越不像市场)")
    
    print("\n在量化中的应用:")
    print("  高夏普 + 低熵 = 确定性α（好）")
    print("  高夏普 + 高熵 = 可能是运气（警惕）")
    print("  KL大 = 确实跟市场不同（可能有α也可能是奇葩）")

information_theoretic_risk()
```

## 7. ML/DL关联总结

| 信息论概念 | ML/DL应用 | 量化应用 |
|---|---|---|
| 熵 | 决策树分裂准则、正则化 | 策略不确定性度量 |
| 交叉熵 | 分类损失函数、逻辑回归 | 因子预测损失 |
| KL散度 | VAE、模型蒸馏、变分推断 | 策略偏离基准度量 |
| JS散度 | GAN生成质量 | 合成数据生成做压力测试 |
| 互信息 | 特征选择、IB理论、表示学习 | 因子有效性评估 |
| 最大熵原理 | 强化学习中的最大熵策略（SAC） | 风险平价（最大熵组合） |
| 信息瓶颈 | 深度学习逐层分析、泛化理论 | 风险管理的信息权衡 |
