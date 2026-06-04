# 安全多方计算 (Secure Multi-Party Computation, MPC)

## 1. MPC 问题模型

### 1.1 定义

**安全多方计算** 解决的是这样一个问题：有 n 个参与方 $P_1, \ldots, P_n$，每方拥有一个秘密输入 $x_i$，他们希望联合计算一个公开函数 $f(x_1, \ldots, x_n) = (y_1, \ldots, y_n)$，使得：

- **正确性**：每方得到正确的输出 $y_i$
- **隐私性**：每方除了自己的输出外，得不到其他方的输入信息

### 1.2 敌手模型

| 模型 | 描述 |
|------|------|
| **半诚实 (Semi-honest)** | 敌手遵守协议，但试图从协议记录中推断额外信息 |
| **恶意 (Malicious)** | 敌手可以任意偏离协议，主动破坏 |
| **隐蔽 (Covert)** | 敌手可能作弊，但不想被抓到 |

### 1.3 安全类型

| 类型 | 描述 |
|------|------|
| **两方安全计算 (2PC)** | 恰好两个参与方，如 Yao's GC |
| **多方安全计算 (MPC)** | 任意 n 个参与方，如 GMW, SPDZ |
| **信息论安全** | 即使在无限计算能力下也安全 |
| **计算安全** | 对多项式时间敌手安全 |

### 1.4 安全性阈值

- **t-out-of-n**: 最多 t 个腐败方时协议仍安全
- **诚实多数**: $t < n/2$，可以实现信息论安全
- **恶意环境**: $t < n/3$，无需广播信道也可实现

---

## 2. 姚氏百万富翁问题 (Yao's Millionaire Problem)

### 2.1 问题描述

姚期智于 1982 年提出：两个百万富翁 Alice 和 Bob 想比较谁更有钱，但都不愿透露自己的真实财富数字。

**输入**：
- Alice 有财富 $a$（1～10 之间的整数）
- Bob 有财富 $b$（1～10 之间的整数）

**输出**：谁更有钱（$a > b$?）

**约束**：双方都不能知道对方的具体数值

### 2.2 直观解法（混淆电路思路）

Yao 的解法是第一个通用 MPC 协议——**混淆电路**的前身：

1. Alice 生成 10 个带锁的箱子，每个箱子对应一个财富值
2. 每个箱子有两把钥匙，分别代表"Alice 更富"和"Bob 更富"
3. Bob 只能打开与自己财富值对应的那个箱子
4. Bob 告知 Alice 箱子内容（比较结果）

> 核心思想：**Alice 构造电路，Bob 用自己的输入评估**

---

## 3. 混淆电路 (Garbled Circuits)

### 3.1 核心思想

Yao 于 1986 年正式提出混淆电路，是 2PC（两方安全计算）的基础协议：

1. **Alice (混淆者/Garbler)**：
   - 将布尔电路中的每条导线用随机密钥代替（混淆）
   - 为每个门的真值表加密（混淆表）
   - 将混淆电路发送给 Bob

2. **Bob (评估者/Evaluator)**：
   - 通过**不经意传输**获得自己输入对应的混淆密钥
   - 逐个解密门的混淆表，得到最终输出

### 3.2 混淆门示例 (AND Gate)

原始门：

| a | b | out |
|---|---|---|
| 0 | 0 | 0 |
| 0 | 1 | 0 |
| 1 | 0 | 0 |
| 1 | 1 | 1 |

**Alice 的混淆过程**：

1. 为每根导线分配两个随机密钥：
   - 导线 a: $k_a^0, k_a^1$
   - 导线 b: $k_b^0, k_b^1$
   - 导线 out: $k_c^0, k_c^1$

2. 加密真值表的每一行（将输出密钥加密两次）：
   - 第 1 行: $E_{k_a^0}(E_{k_b^0}(k_c^0))$
   - 第 2 行: $E_{k_a^0}(E_{k_b^1}(k_c^0))$
   - 第 3 行: $E_{k_a^1}(E_{k_b^0}(k_c^0))$
   - 第 4 行: $E_{k_a^1}(E_{k_b^1}(k_c^1))$

3. **打乱顺序**后发送给 Bob

**Bob 的评估过程**：
- 已知 $k_a^{x_a}$（Alice 直接给）和 $k_b^{x_b}$（来自 OT）
- 尝试用这两个密钥解密混淆表中的每一行
- 只有一行能解密成功，得到 $k_c^{out}$
- 得到一把输出密钥，但不知道对应 0 还是 1

**输出解码**：
- Alice 发送一个"解码表"将输出密钥映射到明文 0/1
- Bob 查看自己得到的密钥对应的明文值

### 3.3 安全性分析

- **半诚实安全**：Bob 只能正确解密一行，看不到其他行
- **Alice 看不到 Bob 的输入**：Alice 只给 Bob 提供了密钥，不知道 Bob 实际用了哪个
- **Bob 不知道 Alice 的输入**：Bob 只有混淆电路，没有 Alice 的原始输入

### 3.4 完整流程

```
1. Alice: 构建电路 → 混淆电路 → 发送给 Bob
2. Alice: 将自己的输入密钥直接发送给 Bob
3. Bob:   通过 OT 得到自己输入的密钥
4. Bob:   评估混淆电路，得到输出密钥
5. Bob:   根据解码表得到明文结果
6. Bob:   将结果告知 Alice（可选）
```

---

## 4. 秘密共享 (Secret Sharing)

### 4.1 问题定义

将一个秘密 $s$ 拆分成 $n$ 个份额（shares），分发给 $n$ 个参与方，要求：
- 任意 $t$ 个份额可以恢复秘密（**$t$ 阈值**）
- 任意 $< t$ 个份额得不到秘密的任何信息

### 4.2 Shamir 秘密共享方案

由 Adi Shamir（RSA 中的 S）于 1979 年提出，基于**拉格朗日插值**：

**核心思想**：一个 $t-1$ 次多项式可以唯一由 $t$ 个点确定

#### 算法描述

**共享阶段 (Share)**：
1. 选择一个大素数 $p$
2. 构建 $t-1$ 次多项式：
   $$f(x) = s + a_1 x + a_2 x^2 + \cdots + a_{t-1} x^{t-1} \mod p$$
   其中 $s$ 是秘密，$a_i$ 是随机系数
3. 计算份额：$share_i = f(i)$ for $i = 1, 2, \ldots, n$

**恢复阶段 (Reconstruct)**：
1. 收集任意 $t$ 个份额 $(x_i, y_i)$
2. 使用拉格朗日插值：
   $$f(x) = \sum_{i=1}^{t} y_i \cdot \prod_{j \neq i} \frac{x - x_j}{x_i - x_j} \mod p$$
3. 秘密 $s = f(0)$

#### 数学原理

拉格朗日基多项式：
$$\ell_i(x) = \prod_{j \neq i} \frac{x - x_j}{x_i - x_j}$$

对于 $x = 0$：
$$s = \sum_{i=1}^{t} y_i \cdot \prod_{j \neq i} \frac{-x_j}{x_i - x_j} \mod p$$

系数 $\lambda_i = \prod_{j \neq i} \frac{-x_j}{x_i - x_j}$ 称为**拉格朗日系数**。

### 4.3 安全性证明（直观）

- 给定 $< t$ 个点，存在无数个 $t-1$ 次多项式通过它们
- 对于任意可能的秘密值 $s'$，都有一个多项式通过已知点 + $(0, s')$
- 所以 $< t$ 个份额不泄露任何信息

### 4.4 应用场景

- **门限签名**: t 个签名者共同签署
- **密钥管理**: 私钥拆分到多台服务器
- **多方计算**: 输入的秘密共享形式
- **拜占庭协议**: 可靠广播

---

## 5. 不经意传输 (Oblivious Transfer, OT)

### 5.1 问题定义

**1-out-of-2 OT**：发送者 Alice 有两个消息 $(m_0, m_1)$，接收者 Bob 选择 $b \in \{0, 1\}$，协议满足：
- Bob 得到 $m_b$，不知道 $m_{1-b}$
- Alice 不知道 Bob 选择了哪个

### 5.2 为什么 OT 很重要

OT 是 MPC 的基础原语，通过 OT + 混淆电路可以实现通用安全计算。

实际上，**OT 是密码学完备的**（与混淆电路结合可以计算任意函数）。

### 5.3 经典构造（基于 RSA 或 DH）

**协议流程**：

Alice 有 $(m_0, m_1)$，Bob 有选择位 $b$。

1. Alice 生成 RSA 公私钥对 $(N, e, d)$，发送 $(N, e)$ 给 Bob
2. Bob 生成随机数 $k$，计算两个盲化值：
   - $x_0 = k^e \mod N$（如果 $b=0$，这是真正的盲化）
   - $x_1 = k^e \cdot m_0^{-1} \mod N$（迷惑值）
   - 实际发送时：$x_b = k^e \mod N$，$x_{1-b}$ 为随机值
   
   **简化版协议**：
   - Bob 选择随机 $k$，发送 $v = (b == 0) ? k^e : k^e \cdot m_0^{-1}$
   
3. Alice 解密两个值：
   - $k_0 = v^d \mod N$
   - $k_1 = (v \cdot m_0^{-1})^d \mod N$
   
4. Alice 发送：
   - $c_0 = m_0 \oplus k_0$
   - $c_1 = m_1 \oplus k_1$

5. Bob 计算 $m_b = c_b \oplus k$

### 5.4 OT 扩展

- **1-out-of-n OT**: 从 n 个消息中选择 1 个
- **相关 OT (COT)**: 消息之间有关联
- **OT 扩展**: 从少量基础 OT 扩展出大量 OT

> OT 扩展 (Ishai et al., 2003) 使实际 MPC 成为可能：用 $\kappa$ 次基础 OT 可以得到任意数量的 OT。

---

## 6. GMW 协议概述

由 Goldreich, Micali 和 Wigderson 于 1987 年提出。

### 6.1 核心思想

将 Yao 的 2PC 推广到 n 方场景，每方将自己的输入通过**秘密共享**分享给所有参与方，然后在共享值上逐门计算。

### 6.2 协议流程

1. **输入共享**: 每方将输入 $x_i$ 做加法秘密共享（或 Shamir 共享）给所有 n 方
2. **电路评估**:
   - XOR 门: 每方在本地计算共享值的 XOR（加法共享）
   - AND 门: 需要交互，通过 OT 或 Beaver Triple 计算
3. **输出重建**: 评估完成后，各方广播自己的输出份额，重建明文

### 6.3 与 Yao's GC 的对比

| 特性 | Yao's GC | GMW |
|------|----------|-----|
| 参与方数 | 2 | n |
| 轮数 | 1（在线阶段） | 与电路深度成正比 |
| 通信量 | 与门数成正比 | 与门数成正比 |
| XOR 门 | 有开销 | 免费（本地操作） |
| AND 门 | 有开销 | 需要交互 |

### 6.4 Beaver Triple 技术

预生成称为 Beaver Triple 的随机三元组 $(a, b, c = a \cdot b)$，在线阶段只需：

```
对一个 AND 门：
[z] = [x] ∧ [y]
1. [u] = [x] ⊕ [a]
2. [v] = [y] ⊕ [b]
3. 广播 u, v（重建后是明文值）
4. [z] = c ⊕ (a ∧ v) ⊕ (b ∧ u) ⊕ (u ∧ v)
```

其中 $[x]$ 表示 $x$ 的共享值。

---

## 7. 总结与宏观图景

### 各协议关系

```
                        Yao's GC (2PC)
                       /              \
                混淆电路             OT
                (Garbler-Evaluator)  (Oblivious Transfer)
                       \              /
                        \            /
                     GMW (n-Party MPC)
                       /      |      \
                秘密共享    Beaver    OT扩展
               (Secret    Triple   (OT Extension)
                Sharing)
```

### 效率瓶颈

1. **混淆电路**: 混淆表的生成和传输（每门 ~ 256 bytes 的 ciphertext）
2. **秘密共享**: 通信量随 n 平方增长
3. **OT**: 公钥操作昂贵（RSA 指数运算）

### 现代优化

- **Free-XOR**: XOR 门不产生混淆表
- **Half-Gates**: 每 AND 门只需 2 个 ciphertext
- **FleXOR**: 平衡 Free-XOR 的灵活性
- **恶意安全**: 通过牺牲成本抵抗恶意敌手
- **SPDZ/BMR**: 预生成材料实现快速在线阶段

---

## 参考资源

- Yao, "Protocols for Secure Computations" (1982)
- Yao, "How to Generate and Exchange Secrets" (1986) — 混淆电路
- Goldreich, Micali, Wigderson, "How to Play any Mental Game" (1987) — GMW
- Shamir, "How to Share a Secret" (1979) — Secret Sharing
- Beaver, "Efficient Multiparty Protocols using Circuit Randomization" (1991) — Beaver Triple
- Ishai, Kilian, Nissim, Petrank, "Extending Oblivious Transfers Efficiently" (2003)
