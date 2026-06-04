# 推荐系统 #6：冷启动与探索利用（Bandit in RecSys）

> 2026-05-17
> 前置知识：推荐系统链路（#1）、Bandit 算法（RL #1）

## 冷启动问题

新用户/新物品没有行为数据，协同过滤无法工作：

| 类型 | 问题 | 典型场景 |
|:----|:----|:--------|
| 用户冷启动 | 新用户没有历史 | 首次注册APP |
| 物品冷启动 | 新商品没有曝光 | 新上架商品、新视频 |
| 系统冷启动 | 平台刚上线 | 新APP没有用户数据 |

## 解决方案

### 1. 基于内容的冷启动

**新用户**：用注册信息（性别、年龄、地域、兴趣标签）做初始推荐

```python
# 简单实现：基于用户画像的相似度
def cold_start_user(profile):
    user_vec = encode_profile(profile)  # 用户画像embedding
    items = get_all_items()
    scores = cosine_similarity(user_vec, items_embeddings)
    return top_k(items, scores, k=10)
```

**新物品**：用物品属性（标题、分类、标签、图像特征）做初筛

### 2. 探索 vs 利用（Explore-Exploit Dilemma）

核心矛盾：
- **利用**：推荐已知用户喜欢的内容 → 短期指标好
- **探索**：推荐不确定的内容 → 发现长期偏好

### 3. Bandit 算法在推荐中的应用

#### ε-Greedy

```python
def egreedy(state, epsilon=0.1):
    if random.random() < epsilon:
        return random_item()    # 探索：随机推荐
    else:
        return best_item(state) # 利用：推荐最优
```

**问题**：随机探索效率低，给所有冷门内容均等机会。

#### UCB（Upper Confidence Bound）

```python
def ucb(item):
    avg_reward = item.clicks / item.impressions
    confidence = sqrt(2 * log(total_impressions) / item.impressions)
    return avg_reward + confidence
```

**核心想法**：曝光少的物品加一个"置信度上界"，让它们有机会被选中。曝光越多，置信区间越小。

#### Thompson Sampling

```python
def thompson_sample(item):
    alpha = item.clicks + 1
    beta = item.impressions - item.clicks + 1
    # 从Beta分布采样 -> 不确定性高的物品有机会胜出
    sample = np.random.beta(alpha, beta)
    return sample
```

**为什么好**：不需要调 ε，自然的探索模式，不确定性高 → 采样值可能高。

### 4. 冷启动阶段的推荐策略

```
新用户注册
    ↓
1. 人口统计推荐（age/gender/region → 热门分类）
2. 信息增益推荐（弹几个兴趣标签 → 让用户自己选）
3. 快速反馈：前5次交互(skip/detail/buy) → 快速收敛用户偏好
    ↓
进入常规推荐（协同过滤/深度学习）
```

**"热身"策略**：
- 前 N 次交互用 Bandit（混合探索利用）
- 积累足够数据后切换到 ML 模型
- 阈值：电商 ~5次点击，视频 ~20次展示

## 生产实践

```
[流量分配层]
    ↓
探索流量 (10-20%) → Bandit / 随机采样
利用流量 (80-90%) → 主推荐模型
```

- **新物品保底曝光**：每个新物品至少展示 1000 次
- **探索冷却**：曝光>阈值后进入主模型排序
- **实时反馈**：点击/互动数据在 1 分钟内回流

## 与量化交易的联系

Bandit 在推荐 = 多臂老虎机在量化：

```
推荐系统 Bandit              量化交易
──────────────────────────────────────
推荐物品（arms）             交易策略（strategies）
用户点击（reward）           收益（return）
ε-Greedy                    固定比例资金分配
Thompson Sampling           贝叶斯策略选择
UCB                         探索新策略
```

这个映射关系很有趣：推荐系统的探索-利用平衡问题，和量化交易的策略选择本质相同。

## 推荐系统阶段总结

至此，推荐系统 6 课完成：

| # | 主题 | 核心内容 |
|:--|:----|:--------|
| 1 | 工业化链路 | 召回→排序→重排全流程 |
| 2 | 特征工程与Embedding | 离散连续特征处理，Embedding Lookup |
| 3 | 协同过滤与矩阵分解 | User-CF/Item-CF, MF, ALS |
| 4 | 深度学习模型 | DNN, Wide&Deep, DIN/DIEN |
| 5 | 多目标优化 | Shared-Bottom, MMoE, PLE |
| 6 | 冷启动与Bandit | ε-Greedy, UCB, Thompson Sampling |

## 参考

- "A Contextual-Bandit Approach to Personalized News Article Recommendation" (WWW 2010)
- "Thompson Sampling for Contextual Bandits with Linear Payoffs" (ICML 2013)
- YouTube: "Deep Neural Networks for YouTube Recommendations" (RecSys 2016)
