# 信息论 Information Theory

## 熵（Shannon Entropy）

离散随机变量 $X \sim p(x)$ 的熵：
$$H(X) = -\sum_{x} p(x) \log p(x)$$

**连续变量**（微分熵）：
$$h(X) = -\int p(x) \log p(x) \, dx$$

### 微积分约束下的最大熵
在约束 $\int p(x)\,dx = 1$、$\int xp(x)\,dx = \mu$、$\int (x-\mu)^2 p(x)\,dx = \sigma^2$ 下最大化 $h(X)$：
- Lagrange: $L = -\int p \log p \, dx + \lambda_1(\int p \, dx - 1) + \lambda_2(\int xp \, dx - \mu) + \lambda_3(\int (x-\mu)^2 p \, dx - \sigma^2)$
- 变分导数为零 → $-\log p - 1 + \lambda_1 + \lambda_2 x + \lambda_3 (x-\mu)^2 = 0$
- 解得 $p(x) \propto \exp\left(-\frac{(x-\mu)^2}{2\sigma^2}\right)$ → **固定方差下，正态分布熵最大**。

### 与交叉熵的关系
- 交叉熵：$H(p,q) = -\sum p(x) \log q(x) = H(p) + D_{\text{KL}}(p\|q)$
- 机器学习中最小化交叉熵 $\Leftrightarrow$ 最小化 KL 散度（当 $p$ 为真实分布固定时）

---

## KL 散度（相对熵）

$$D_{\text{KL}}(p\|q) = \sum_x p(x) \log \frac{p(x)}{q(x)} = \mathbb{E}_{p}[\log p - \log q]$$

### 性质
- **非负性**：$D_{\text{KL}}(p\|q) \geq 0$，等号当且仅当 $p = q$（Gibbs 不等式）
- **非对称性**：$D_{\text{KL}}(p\|q) \neq D_{\text{KL}}(q\|p)$
  - $D_{\text{KL}}(p\|q)$：均值遍历性（$p$ 支撑在 $q$ 内部时有限）
  - $D_{\text{KL}}(q\|p)$：零避免性（$q=0$ 处 $p$ 必须为 0）

### JS 散度（对称化）
$$D_{\text{JS}}(p\|q) = \frac{1}{2} D_{\text{KL}}(p\|m) + \frac{1}{2} D_{\text{KL}}(q\|m), \quad m = \frac{p+q}{2}$$
- 有界：$[0, \log 2]$
- 对称，且是 $\sqrt{D_{\text{JS}}}$ 是距离度量

---

## 互信息

$$I(X;Y) = D_{\text{KL}}(p(x,y)\|p(x)p(y)) = H(X) - H(X|Y)$$

**链式法则**：$I(X_1,...,X_n; Y) = \sum_{i=1}^n I(X_i; Y | X_1,...,X_{i-1})$

**数据处理不等式**：$X \to Y \to Z \Rightarrow I(X;Y) \geq I(X;Z)$（处理不会增加信息）。

---

## 最大熵原理

在满足已知约束的所有分布中，选择熵最大的分布（最不偏颇、假设最少的分布）。

### 指数族分布
最大熵分布是指数族形式：
$$p_\theta(x) = \frac{1}{Z(\theta)} \exp\left(\sum_{i=1}^k \theta_i f_i(x)\right)$$

| 约束 | 最大熵分布 |
|------|-----------|
| 均值固定 | 指数分布（非负） |
| 均值 + 方差固定 | 正态分布 |
| 支撑在 $[a,b]$ | 均匀分布 |
| 均值固定（正整数） | 几何分布 |

---

## 信息瓶颈理论

压缩变量 $X$ 到 $\tilde{X}$，同时保留对 $Y$ 的信息：

$$\mathcal{L}_{\text{IB}} = I(\tilde{X}; Y) - \beta I(\tilde{X}; X)$$

- $\beta$ 控制压缩与保信的权衡
- 最优解形式：$p(\tilde{x}|x) \propto p(\tilde{x}) \exp(-\beta D_{\text{KL}}(p(y|x)\|p(y|\tilde{x})))$
- 用于理解深度网络的表示学习：深层倾向于丢弃与任务无关的细节

---

## 在 ML 中的应用

### 变分推理与 ELBO
对数边际似然的证据下界：

$$\log p(x) \geq \mathbb{E}_{q(z|x)}[\log p(x|z)] - D_{\text{KL}}(q(z|x)\|p(z)) = \text{ELBO}$$

**VAE**：编码器输出 $q(z|x)$，解码器输出 $p(x|z)$，
- 重构损失 $\approx - \mathbb{E}_q[\log p(x|z)]$
- KL 正则项 $\approx D_{\text{KL}}(q(z|x)\|p(z))$
- 训练目标：最大化 ELBO，即最小化 $D_{\text{KL}}(q(z|x)\|p(z|x))$（让变分后验逼近真实后验）

### 其他应用
- **决策树**：用信息增益（互信息）选择分裂特征
- **GAN**：$D_{\text{JS}}$ 散度最小化（原版）
- **对比学习**：互信息下界估计（InfoNCE 损失）
