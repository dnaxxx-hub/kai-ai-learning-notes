# #8 逆向强化学习（Inverse Reinforcement Learning, IRL）

## 1. IRL 的动机

**标准 RL**：已知奖励函数 $R(s, a)$，学策略 $\pi(a|s)$ 最大化累积奖励。
**现实困境**：很多场景下的奖励函数根本无法定义——

- 自动驾驶：怎么样的驾驶行为是"好的"？安全、舒适、快速之间的权重怎么定？
- 机器人抓杯子：怎么定义"正确"的抓取姿势？最佳轨迹长什么样？
- 人机交互：机器人怎么模仿人类自然的行为？

但好消息是：**人类/专家的演示是现成的**。IRL 就是去回答这个问题：

> 给定专家的行为轨迹（无奖励信号），能否推断出专家内心隐含的奖励函数？

## 2. IRL 核心问题

- **输入**：专家轨迹 $\mathcal{D} = \{\tau_1, \tau_2, \dots, \tau_N\}$，其中 $\tau = (s_0, a_0, s_1, a_1, \dots)$
- **输出**：一个奖励函数 $R_\psi(s, a)$，使得专家轨迹在该奖励下是最优的
- **假设**：专家是在最大化某个未知奖励函数

**数学表达**：
$$
\max_\psi \mathbb{E}_{\tau \sim \pi^*}[ \log P(\tau | R_\psi) ]
$$
即找到最可能解释专家行为的那一个奖励函数。

## 3. 歧义性问题和最大熵原则

### 3.1 歧义性（Ambiguity）

IRL 本质上是病态（ill-posed）问题：
- 无数个奖励函数都可以解释同一条专家轨迹
- 极端情况：$R(s,a) = 0$ 对任何轨迹都成立，但它无法指导任何行为

### 3.2 最大熵原则（Maximum Entropy）

Ziebart 等人（2008）的经典工作：
- 在所有能解释专家轨迹的奖励函数中，选择使专家轨迹分布**熵最大**的那个
- 意味着：不引入任何额外的假设，只解释观察到的数据，不做无关的断言

**最大熵 IRL 的目标**：
$$
\max_R \sum_{\tau \in \mathcal{D}} \log P(\tau | R), \quad \text{其中 }
P(\tau | R) = \frac{\exp(\sum_t R(s_t, a_t))}{Z}
$$
- $Z = \sum_{\tau} \exp(\sum_t R(s_t, a_t))$ 是配分函数
- 专家轨迹概率 = 奖励总和越大，概率越高
- 这就是一个**指数族分布**（Boltzmann 分布）

## 4. 经典算法

### 4.1 线性 IRL（Linear IRL）

**Ng & Russell, 2000** — IRL 的奠基性工作。

- 假设奖励是特征的**线性组合**：
  $$
  R(s) = w^T \phi(s) = w_1 \phi_1(s) + w_2 \phi_2(s) + \cdots
  $$
- $\phi(s)$ 是状态的特征向量，$w$ 是待学习的权重
- **核心思想**：专家的特征期望 $\mathbb{E}[\phi(\tau)]$ 应该匹配最优策略的特征期望

**算法**：
1. 计算专家轨迹的特征期望 $\mu_E$
2. 初始化策略，计算当前策略的特征期望 $\mu_\pi$
3. 更新 $w$，使得 $w^T \mu_E \geq w^T \mu_\pi$
4. 用新 $w$ 重新求解 MDP，得到新策略
5. 重复直到收敛

**局限性**：
- 线性假设太强，真实奖励往往是非线性的
- 需要多次求解 MDP，计算开销大
- 没有解决歧义性问题

### 4.2 最大熵 IRL（MaxEnt IRL）

**Ziebart et al., 2008** — 用最大熵原则解决歧义性问题。

**核心流程**：
1. 给定 $R_w(s) = w^T \phi(s)$，计算访问状态 $s$ 的概率 $P(s | R_w)$
2. 用 Soft Value Iteration 求解：
   - $V_{\text{soft}}(s) = \text{softmax}_a (R(s) + \gamma \mathbb{E}_{s'} V_{\text{soft}}(s'))$
   - $P(a|s) \propto \exp(R(s) + \gamma \mathbb{E}_{s'} V_{\text{soft}}(s'))$
3. 计算当前奖励下的**状态访问频率**（state visitation frequency）
4. 与专家状态访问频率对比，梯度更新 $w$

**梯度**：
$$
\nabla_w \mathcal{L} = \mathbb{E}_{\tau \sim \pi}[\nabla_w R_w(\tau)] - \mathbb{E}_{\tau \sim \pi_E}[\nabla_w R_w(\tau)]
$$
让模型生成轨迹的特征期望**匹配**专家轨迹的特征期望。

**优点**：
- 最大熵原则提供了概率解释
- 处理了歧义性
- 能够生成多样化的专家行为

### 4.3 结构化最大边际（Structured Max-Margin）

**Ratliff et al., 2006** — MMP（Maximum Margin Planning）。

- 类似 SVM 的思路：找到一个奖励函数，使得专家轨迹的累积奖励**远大于**其他所有轨迹
- 约束：$R(\tau_E) \geq R(\tau) + \mathcal{L}(\tau_E, \tau)$
  - $\mathcal{L}$ 是损失函数，衡量专家轨迹和其他轨迹之间的"差距"
- 优化：最小化边际损失，同时对权重做正则化

**优点**：鲁棒性较好
**缺点**：需要定义损失函数 $\mathcal{L}$，且只关注最差的错误轨迹而非整体分布

## 5. 深度 IRL / 对抗式 IRL

传统 IRL 的痛点：
- 需要特征工程（线性/手工特征）
- 需要求解 MDP（状态空间大时不可行）
- 扩展到高维连续空间困难

### 5.1 GAIL（Generative Adversarial Imitation Learning）

**Ho & Ermon, 2016** — 把 GAN 引入 IRL。

**架构**：
```
Generator π_θ（策略）          Discriminator D_ω（判别器）
  ↓ 生成轨迹                       ↑ 区分专家 vs 生成
  生成轨迹                          专家轨迹
  ──────────────────────────────────────────
```

- **Generator（策略 $\pi_\theta$）**：像 GAN 的生成器，生成轨迹试图骗过判别器
- **Discriminator $D_\omega(s,a)$**：判断 $(s,a)$ 是来自专家还是来自 agent
- **目标函数**：
  $$
  \min_\theta \max_\omega \mathbb{E}_{\pi_E}[\log D_\omega(s,a)] + \mathbb{E}_{\pi_\theta}[\log(1 - D_\omega(s,a))]
  $$
- **Generator 的优化**：用 TRPO/PPO 最大化 $- \log D_\omega(s,a)$（即让判别器以为自己是专家）

**GAIL 的本质**：
- 不显式输出奖励函数
- 所学的 Discriminator 相当于一个**隐含的奖励函数**
- 但它原始设计的目的是模仿，而不是恢复奖励

### 5.2 AIRL（Adversarial Inverse Reinforcement Learning）

**Fu et al., 2018** — 在 GAIL 基础上，**显式恢复奖励函数**。

**关键改进**：
- Discriminator 的结构做了函数分解：
  $$
  D_\omega(s,a) = \frac{\exp(f_\omega(s,a))}{\exp(f_\omega(s,a)) + \pi(a|s)}
  $$
- 其中 $f_\omega(s,a) = r_\psi(s,a) + \gamma V_\phi(s') - V_\phi(s)$
  - $r_\psi$ 是要学习的奖励函数
  - $V_\phi$ 是 shaping term（不影响最优策略的势函数）

**为什么这样设计？**
- 标准 GAIL 的 Discriminator 输出不能直接当奖励（有偏）
- AIRL 通过分解，从 Discriminator 中**剥离出真正的奖励函数**
- 奖励函数的定义具有**不变量性质**（reward-shaping invariance）

**AIRL 的意义**：
- 不仅学会了模仿，还学会了**专家为什么这样做**
- 学到的奖励函数可以迁移到新环境（reward transfer）

## 6. IRL vs 行为克隆（Behavior Cloning）

| 维度 | 行为克隆（BC） | 逆向强化学习（IRL） |
|------|---------------|-------------------|
| 问题本质 | 监督学习 | 结构化预测/逆最优控制 |
| 学什么 | $\pi(a\|s)$ 的策略分布 | $R(s,a)$ 奖励函数 |
| 数据需求 | 大量 $(s,a)$ 配对 | 完整轨迹（含状态序列） |
| 分布偏移 | ❌ 严重（没见过的状态会乱来） | ✅ 弱（理解了目标） |
| 泛化能力 | ❌ 差（只能复现训练分布） | ✅ 强（换背景/换形态也能用） |
| 计算开销 | 低（跑一次分类器） | 高（反复求解 MDP/RL） |
| 示例 | 抄作业 | 理解题目意图自己做 |

**关键洞察**：
- BC 是**条件分布匹配**：$\min_\pi \mathbb{E}_{s \sim \pi_E}[D_{KL}(\pi_E(\cdot|s) \| \pi(\cdot|s))]$
- IRL 是**轨迹分布匹配**：$\min_R D_{KL}(P_{\pi_E}(\tau) \| P_\pi(\tau|R))$
- IRL 学到的奖励比 BC 学到的策略**更本质、更通用**

## 7. 代码：最大熵 IRL 在 GridWorld 上的实现

> 注：以下为伪代码/实现思路，不实际运行。

### 环境设定
- 4×4 GridWorld，左上角起点，右下角目标
- 动作：上下左右
- 状态特征 $\phi(s)$ = one-hot 编码（16维）或更紧凑的特征

### 算法步骤

```python
# 1. 专家轨迹生成（假设我们从最优策略采样了 N 条轨迹）
expert_trajectories = sample_from_optimal_policy(env, N=100)

# 2. 计算专家特征期望
expert_feature_expectation = compute_feature_expectation(expert_trajectories)

# 3. 初始化奖励权重 w
w = np.zeros(n_features)

for iteration in range(max_iter):
    # 4. 通过 Soft Value Iteration 计算当前 w 下的最优策略
    policy = soft_value_iteration(env, w, gamma=0.9)

    # 5. 用当前策略采样轨迹，计算特征期望
    current_feature_expectation = compute_feature_expectation(
        sample_from_policy(env, policy, N=100)
    )

    # 6. 计算梯度：让当前特征期望向专家特征期望靠近
    grad = current_feature_expectation - expert_feature_expectation

    # 7. 更新 w（梯度上升）
    w -= lr * grad

    # 8. 监控损失函数
    loss = np.linalg.norm(grad)
    print(f"Iter {iteration}, Loss: {loss:.4f}")
```

### 关键函数：Soft Value Iteration

```python
def soft_value_iteration(env, w, gamma=0.9, theta=1e-6):
    """带 softmax 的值迭代，对应最大熵策略"""
    V = np.zeros(env.n_states)
    while True:
        delta = 0
        for s in env.states:
            # 对每个动作计算 Q 值
            Q = np.array([
                w @ phi(s, a) + gamma * V[s'] for a in env.actions
            ])
            # softmax 更新 V（log-sum-exp）
            V_new = np.log(np.sum(np.exp(Q)))
            delta = max(delta, abs(V_new - V[s]))
            V[s] = V_new
        if delta < theta:
            break
    # 策略：softmax 概率
    policy = compute_softmax_policy(env, V, w, gamma)
    return policy
```

### 核心要点
- **Soft Value Iteration** 替代标准 V Iteration：用 log-sum-exp 替代 max，导出概率策略
- **梯度**等于"当前特征期望 - 专家特征期望"：让 reward 引导的策略分布对齐专家
- **收敛时**：模型生成轨迹的特征分布 ≈ 专家轨迹的特征分布

## 8. IRL 的局限性

### 计算开销巨大
- 每次迭代都要求解 MDP / 做策略评估
- 大规模状态空间下（如机器人连续控制），经典 IRL 几乎不可行

### 需要大量专家数据
- 专家轨迹的质量和数量直接影响奖励函数质量
- 样本效率低：GAIL 需要大量与环境交互

### 奖励函数可能过度拟合
- 学到的奖励函数可能在专家轨迹覆盖的区域表现好
- 但在未见过的状态上可能产生**非常奇怪的奖励值**
- 极端情况：学到"恰好"解释专家轨迹、但在其他地方完全错误的奖励

### 歧义性仍然存在
- 最大熵原则只是缓解，不能完全消除
- 不同的 $R$ 可能导致相同的专家行为但完全不同的泛化

### 专家次优性问题
- 现实中专家并非最优（人类也会犯错）
- IRL 假设专家是最优的 → 次优专家数据导致错误的奖励推断

### 环境模型需求

经典 IRL 需要环境动力学 $P(s'|s,a)$ 的模型：
- 有模型时：可以计算期望特征
- 无模型时：GAIL/AIRL 绕过了这个问题，但又引入了 GAN 训练的稳定性问题

---

## 总结

```
正向 RL：奖励函数 R → 最优策略 π*
IRL：    专家轨迹 τ → 推测隐含的奖励函数 R

IRL 的核心挑战：从"行为"反推"意图"
    能力越大（能解释所有轨迹的 R 都很多）→ 歧义性越大
    最大熵 → 最不偏不倚的解释
    
经典 vs 深度：
  经典 Linear/MaxEnt IRL → 小规模、离散、有模型
  GAIL/AIRL            → 大规模、连续、无模型

IRL 的终极目标：不仅学会"做什么"，更学会"为什么做"
```
