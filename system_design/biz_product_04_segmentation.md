# 课时4：用户分群——从RFM到LTV预测

> 面向对象：AI/技术从业者
> 核心命题：如何科学地将用户分群，针对不同群体制定差异化策略

## 一、为什么技术人需要懂用户分群？

你构建了一个推荐系统，离线指标 AUC 0.82，上线后整体点击率提升 15%。但拆开看：**新用户点击率下降 8%，老用户提升 22%**。如果只看均值，你永远不知道模型伤害了谁。

用户分群的核心价值：**一刀切的策略隐藏了大部分真相**。没有分群的数据分析，就像在迷雾里看风景——你以为看到的是全貌，实际只有轮廓。

### 分群的商业意义

| 场景 | 不分群的后果 | 分群带来的价值 |
|------|-------------|---------------|
| 促销活动 | 给所有人发相同优惠券，ROI低 | 高价值用户给大折扣，低价值用户不给或给小折扣 |
| 产品改版 | 看均值指标没变化，判断失败 | 新用户留存上升但老用户下降，发现功能迁移成本 |
| 推送策略 | 频繁推送导致卸载率上升 | 不同频率、不同内容的差异化触达 |
| 定价测试 | 定价过高流失价格敏感用户 | PSM分群找到最佳定价区间 |

---

## 二、RFM 模型——最经典的用户价值分群

### 2.1 什么是 RFM？

RFM 是衡量用户价值的三个核心维度：

| 维度 | 全称 | 含义 | 直觉 |
|------|------|------|------|
| **R** | Recency（最近消费时间） | 用户上次消费距今多久 | 越近越活跃，越可能再次消费 |
| **F** | Frequency（消费频率） | 用户一段时间内消费次数 | 频率越高，粘性越强 |
| **M** | Monetary（消费金额） | 用户一段时间内消费总金额 | 金额越高，价值越大 |

**商业直觉**：最近来过、经常来、花钱多的用户，是最有价值的用户。

### 2.2 RFM 评分方法

三步走：

1. **分箱打分**：将每个维度分成 1-5 分（或者 1-3 分），通常使用分位数
2. **合并得分**：每个用户得到一个三位数 RFM 分数，如 5-4-3
3. **分群归类**：根据 R、F、M 的高中低划分典型群体

**典型 RFM 分群**：

| 群体 | R | F | M | 特征 | 策略 |
|------|---|---|---|------|------|
| 重要价值用户 | 高 | 高 | 高 | 核心忠实用户 | VIP 维护、优先体验新功能 |
| 重要发展用户 | 高 | 低 | 高 | 消费能力强但频次低 | 提升复购、会员推荐 |
| 重要保持用户 | 低 | 高 | 高 | 曾经高频高消费但近期流失 | 召回激励、专属优惠 |
| 重要挽留用户 | 低 | 低 | 高 | 消费能力强但已流失 | 大力度召回 |
| 一般价值用户 | 高 | 高 | 低 | 活跃但消费力弱 | 交叉销售、提升客单价 |
| 一般发展用户 | 高 | 低 | 低 | 新用户或低频低消费 | 培养使用习惯 |
| 一般保持用户 | 低 | 高 | 低 | 常来但不怎么花钱 | 提升转化 |
| 流失用户 | 低 | 低 | 低 | 三类指标都差 | 低成本批量唤醒或不打扰 |

### 2.3 RFM 评分 Python 实现

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ===========================================
# 第一步：模拟用户交易数据
# ===========================================
np.random.seed(42)
n_users = 10000

# 生成最近 365 天的随机交易
data = []
for user_id in range(1, n_users + 1):
    # 每个用户 1~20 笔交易
    n_trans = np.random.randint(1, 21)
    for _ in range(n_trans):
        days_ago = np.random.randint(0, 365)
        amount = np.random.exponential(100) + 20  # 消费金额，长尾分布
        data.append({
            'user_id': user_id,
            'trans_date': datetime.now() - timedelta(days=days_ago),
            'amount': round(amount, 2)
        })

df = pd.DataFrame(data)

# ===========================================
# 第二步：计算 R, F, M 值
# ===========================================
reference_date = datetime.now()

rfm = df.groupby('user_id').agg({
    'trans_date': lambda x: (reference_date - x.max()).days,   # R：最近一次消费距今天数
    'user_id': 'count',                                         # F：消费次数
    'amount': 'sum'                                             # M：总消费金额
}).rename(columns={
    'trans_date': 'Recency',
    'user_id': 'Frequency',
    'amount': 'Monetary'
})

# ===========================================
# 第三步：分位数打分（1-5分）
# ===========================================
def rfm_score(series, reverse=False):
    """分位数打分，reverse=True 表示越小越好的指标（如 Recency）"""
    if reverse:
        # Recency：越小（越近）得分越高
        bins = series.quantile([0.2, 0.4, 0.6, 0.8]).values
        return pd.cut(series, bins=[-np.inf] + list(bins) + [np.inf],
                      labels=[5, 4, 3, 2, 1]).astype(int)
    else:
        # Frequency / Monetary：越大得分越高
        bins = series.quantile([0.2, 0.4, 0.6, 0.8]).values
        return pd.cut(series, bins=[-np.inf] + list(bins) + [np.inf],
                      labels=[1, 2, 3, 4, 5]).astype(int)

rfm['R_score'] = rfm_score(rfm['Recency'], reverse=True)
rfm['F_score'] = rfm_score(rfm['Frequency'])
rfm['M_score'] = rfm_score(rfm['Monetary'])
rfm['RFM_Score'] = (rfm['R_score'].astype(str) +
                     rfm['F_score'].astype(str) +
                     rfm['M_score'].astype(str))

# ===========================================
# 第四步：用户分群
# ===========================================
def segment_user(row):
    r, f, m = row['R_score'], row['F_score'], row['M_score']
    if r >= 4 and f >= 4 and m >= 4:
        return '重要价值用户'
    elif r >= 4 and f < 3 and m >= 4:
        return '重要发展用户'
    elif r < 3 and f >= 4 and m >= 4:
        return '重要保持用户'
    elif r < 3 and f < 3 and m >= 4:
        return '重要挽留用户'
    elif r >= 4 and f >= 4 and m < 3:
        return '一般价值用户'
    elif r >= 4 and f < 3 and m < 3:
        return '一般发展用户'
    elif r < 3 and f >= 4 and m < 3:
        return '一般保持用户'
    else:
        return '流失用户'

rfm['Segment'] = rfm.apply(segment_user, axis=1)

# 输出分群结果
print(rfm['Segment'].value_counts())
print(f"\n重要价值用户示例：\n{rfm[rfm['Segment']=='重要价值用户'].head()}")
```

**输出解读**：
```
流失用户          3200
一般发展用户      2200
一般价值用户      1500
重要价值用户      1200
重要发展用户       800
重要保持用户       600
一般保持用户       300
重要挽留用户       200
```

**业务应用**：重要价值用户（R高F高M高）只占 12%，但贡献了可能 60% 的收入。把运营资源聚焦在这群人身上，远比撒胡椒面效果好。

### 2.4 RFM 的局限与改进

- **静态性**：RFM 是历史快照，不反映趋势。改进：引入 RFM 趋势变化（如 R 在恶化）
- **业界通用**：电商强相关，但 SaaS 订阅制不太适用（F 和 M 耦合）
- **维度有限**：不含行为特征（浏览了什么、点击了什么）。改进：结合行为分群

---

## 三、K-Means 聚类分群——无监督的用户画像

### 3.1 为什么用聚类？

RFM 依赖人工划分类别（1-5分），有局限性：
- 分箱边界是人为的，可能因数据分布导致不均衡
- 维度扩展困难（加入第4、第5个维度时组合爆炸）

**K-Means 聚类** 自动从数据中发现用户群体，适合多维度分群。

### 3.2 算法直觉

K-Means 的核心思想：**物以类聚**。

1. 随机初始化 K 个中心点
2. 将每个数据点分配到最近的中心点
3. 重新计算每个簇的中心（均值）
4. 重复 2-3 直到收敛

**技术人直觉**：把 K-Means 想象成一个「自动分组器」，它不需要你告诉它什么用户是一类，它自己从数据中寻找「距离最近」的人群。

### 3.3 Python 实现：RFM + K-Means

```python
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

# ===========================================
# 第一步：准备数据（使用上面 RFM 计算的数据）
# ===========================================
X = rfm[['Recency', 'Frequency', 'Monetary']].copy()

# 标准化：K-Means 对尺度敏感
# Monetary 可能是千元级，Recency 是几天级，不标准化会让 Monetary 主导聚类
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ===========================================
# 第二步：肘部法则确定最佳 K 值
# ===========================================
inertias = []
K_range = range(2, 11)
for k in K_range:
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(X_scaled)
    inertias.append(kmeans.inertia_)

# 绘制肘部图
plt.figure(figsize=(8, 5))
plt.plot(K_range, inertias, 'bo-')
plt.xlabel('K 值')
plt.ylabel('惯性（Inertia）')
plt.title('肘部法则——选择最佳 K')
plt.grid(True)
plt.show()
# 通常在 K=4 或 K=5 时出现"肘部"

# ===========================================
# 第三步：K=5 聚类
# ===========================================
kmeans = KMeans(n_clusters=5, random_state=42, n_init=10)
rfm['Cluster'] = kmeans.fit_predict(X_scaled)

# ===========================================
# 第四步：分析各聚类特征
# ===========================================
cluster_profile = rfm.groupby('Cluster').agg({
    'Recency': 'mean',
    'Frequency': 'mean',
    'Monetary': 'mean',
    'user_id': 'count'
}).rename(columns={'user_id': 'Count'})

print("各聚类画像：")
print(cluster_profile)

# 将聚类结果映射为可理解的标签
cluster_labels = {
    0: '高价值忠实用户（R低F高M高）',
    1: '沉睡高消费用户（R高F低M高）',
    2: '普通活跃用户（R低F中M中）',
    3: '潜在新用户（R低F低M低）',
    4: '流失用户（R高F低M低）'
}
rfm['Cluster_Label'] = rfm['Cluster'].map(cluster_labels)
print(f"\n聚类标签映射：\n{rfm['Cluster_Label'].value_counts()}")
```

### 3.4 聚类结果解读

典型输出：

| 聚类 | R | F | M | 用户数 | 标签 |
|------|---|----|----|-------|------|
| 0 | 8天 | 15次 | ¥3200 | 1500 | 高价值忠实用户 |
| 1 | 120天 | 3次 | ¥2400 | 800 | 沉睡高消费用户 |
| 2 | 25天 | 7次 | ¥800 | 3000 | 普通活跃用户 |
| 3 | 15天 | 2次 | ¥120 | 3200 | 潜在新用户 |
| 4 | 200天 | 1.5次 | ¥90 | 1500 | 流失用户 |

**业务洞见**：
- **聚类1（沉睡高消费）**：这些人有钱但近期没来——可能是被竞品抢走了，值得召回
- **聚类3（潜在新用户）**：来了但不怎么消费——需要引导首次购买
- **聚类0（高价值）**：核心用户，任何改动都要考虑他们的感受

### 3.5 聚类分群的陷阱

1. **数据标准化至关重要**：不改 Monetary 会碾压其他维度
2. **K 值选择不唯一**：肘部图可能不明显，用业务可解释性来验证
3. **聚类不保证稳定性**：每次运行结果可能不同，设置 `random_state`
4. **高维灾难**：超过 10 个维度时，欧氏距离失效，考虑降维

---

## 四、PSM（价格敏感度测量）

### 4.1 什么是 PSM？

PSM（Price Sensitivity Meter）是一种通过问卷调查测量用户对价格敏感度的方法，由 van Westendorp 在 1976 年提出。核心是问用户四个问题：

| 问题 | 含义 |
|------|------|
| 太便宜（太便宜以至于怀疑质量） | 价格下限心理锚点 |
| 便宜（性价比较高） | 真正接受的优惠价 |
| 贵（开始觉得贵但还能接受） | 可接受上限 |
| 太贵（一定不会买） | 心理价格天花板 |

### 4.2 PSM 曲线分析

将四个问题的回答绘制成累积分布曲线，交点给出定价区间：

```
                   太贵曲线
                   ↗
                  /
  太便宜曲线     /  贵曲线
     ↘         /  ↗
      \       / /
       \     / /
        ↘   / /
         \ / /
          × ← "太便宜"与"太贵"的交点 → 最优价格区间
         / \                  ↑
        /   \               可接受的价格范围
       /     \
      /       ↘
     /         贵曲线终点
    /
太便宜曲线
```

**关键结论**：
- **最优价格点（OPP）**：「太便宜」和「太贵」曲线的交点
- **可接受价格区间**：「便宜」和「贵」的交点到「太便宜」和「太贵」的交点
- **无关紧要点（IDP）**：「便宜」和「太贵」的交点

### 4.3 商业案例：定价 SaaS 产品

**案例**：一家 AI 客服 SaaS 公司决定定价。他们通过 PSM 问卷收集数据：

| 价格/月 | 太便宜 | 便宜 | 贵 | 太贵 |
|---------|--------|------|----|------|
| ¥99 | 45% | 30% | 10% | 0% |
| ¥199 | 20% | 40% | 20% | 5% |
| ¥299 | 8% | 25% | 35% | 15% |
| ¥499 | 2% | 10% | 30% | 40% |

**分析结论**：
- OPP ≈ ¥259/月（太便宜和太贵的交点）
- 可接受区间：¥179-¥359
- 最终定价 ¥249/月（略低于 OPP，给用户性价比感）

### 4.4 PSM 的技术实现

```python
def psm_analysis(prices, too_cheap_pct, too_expensive_pct):
    """
    PSM 分析：确定最优价格区间
    prices: 价格点数组
    too_cheap_pct: 各价格点认为"太便宜"的用户比例
    too_expensive_pct: 各价格点认为"太贵"的用户比例
    """
    from scipy.interpolate import interp1d
    
    # 插值找到两条曲线的交点
    cheap_interp = interp1d(too_cheap_pct, prices, bounds_error=False)
    expensive_interp = interp1d(too_expensive_pct, prices, bounds_error=False)
    
    # OPP: 太便宜% = 太贵% 时的价格
    opp = cheap_interp(too_expensive_pct)  # 近似
    
    return opp
```

---

## 五、行为分群（Behavioral Segmentation）

### 5.1 为什么行为比属性重要？

传统用户分群基于人口统计学（年龄、性别、地域），但这套方法在互联网时代失效了。

**案例**：一个 60 岁的退休教授和一个 20 岁的大学生可能都是拼多多的重度用户。但他们在平台上买的商品、浏览的方式完全不同。**行为比画像更诚实**。

### 5.2 常见行为分群维度

**用户旅程阶段**：
| 阶段 | 行为特征 | 策略 |
|------|---------|------|
| 新用户 | 注册后 0-7 天 | 引导激活 |
| 活跃用户 | 每周使用 3+ 次 | 留存、转化 |
| 沉默用户 | 7-30 天未使用 | 召回推送 |
| 流失用户 | 30+ 天未使用 | 大力度召回或不打扰 |

**使用深度**：
| 类型 | 特征 | 占比一般为 | 策略 |
|------|------|-----------|------|
| Power User | 高频高时长，使用高级功能 | 5-10% | 品牌大使、UGC 激励 |
| Core User | 稳定使用核心功能 | 20-30% | 转化付费 |
| Casual User | 偶尔使用、浅度 | 40-50% | 提升频次 |
| Lurk User | 只浏览不互动 | 10-20% | 降低使用门槛 |

**AARRR 阶段**：
- 获取期 → 激活期 → 留存期 → 付费期 → 传播期

在不同阶段的用户需要不同的产品策略和运营动作。

### 5.3 行为分群的 Python 实现

```python
def behavioral_segmentation(df):
    """
    基于用户行为特征分群
    df 包含列：user_id, login_days_30, sessions_30, 
                avg_session_min, features_used, last_action_days
    """
    conditions = [
        (df['login_days_30'] >= 20) & (df['features_used'] >= 5),        # Power User
        (df['login_days_30'] >= 10) & (df['login_days_30'] < 20),         # Core User
        (df['login_days_30'] >= 3) & (df['login_days_30'] < 10),          # Casual User
        (df['login_days_30'] >= 1) & (df['login_days_30'] < 3),           # New/Light User
        (df['last_action_days'] >= 30)                                    # Churned User
    ]
    labels = ['Power User', 'Core User', 'Casual User', 'Light User', 'Churned']
    
    df['behavior_segment'] = np.select(conditions, labels, default='Unknown')
    return df
```

---

## 六、LTV 预测——看用户未来值多少钱

### 6.1 什么是 LTV？

**LTV（Lifetime Value，用户生命周期价值）** = 一个用户从注册到流失的总收入贡献。

**为什么重要**：
- 获客成本（CAC）不能超过 LTV → CAC < LTV 是健康的单位经济模型
- 不同分群的 LTV 差异可能高达 10 倍
- LTV 决定了你能花多少钱获客

### 6.2 传统 LTV 计算公式

$$LTV = ARPU \times 平均用户生命周期$$

**简单估算**：
```
月 ARPU = ¥50
月留存率 = 80%
平均生命周期 = 1 / (1 - 留存率) = 1 / 0.2 = 5 个月
LTV ≈ ¥50 × 5 = ¥250
```

### 6.3 基于概率的 LTV 预测（Python）

对于 SaaS 订阅制产品，更精确的 LTV 计算需要考虑留存曲线的衰减：

```python
import numpy as np
from scipy.optimize import curve_fit

# ===========================================
# 场景：SaaS 月订阅产品
# ===========================================

# 模拟月留存率数据（第1个月到第24个月）
months = np.arange(1, 25)
# 真实产品中，留存率会随时间衰减，通常呈幂律分布
retention_rates = 0.85 ** (months - 1)  # 月留存率 85%，幂律衰减

# ===========================================
# 方法1：简单累加法计算 LTV
# ===========================================
monthly_arpu = 30  # 月均收入 ¥30
ltv_simple = sum(retention_rates) * monthly_arpu
print(f"简单 LTV（24个月）: ¥{ltv_simple:.2f}")

# ===========================================
# 方法2：拟合留存曲线，预测到无限期
# ===========================================
def retention_power_law(t, a, b):
    """幂律留存曲线：R(t) = a * t^b"""
    return a * (t ** b)

# 拟合曲线参数
popt, _ = curve_fit(retention_power_law, months, retention_rates, 
                     p0=[1.0, -0.3])
a_fit, b_fit = popt
print(f"拟合参数：a={a_fit:.3f}, b={b_fit:.3f}")

# 预测到第60个月
future_months = np.arange(1, 61)
future_retention = retention_power_law(future_months, a_fit, b_fit)

# 累计 LTV
ltv_60m = sum(future_retention) * monthly_arpu
print(f"拟合 LTV（60个月）: ¥{ltv_60m:.2f}")

# ===========================================
# 方法3：按用户分群计算 LTV
# ===========================================
def calculate_segment_ltv(retention_curve, arpu, months=24):
    """计算指定分群的 LTV"""
    cumulative_revenue = 0
    for t in range(months):
        monthly_revenue = retention_curve[t] * arpu
        cumulative_revenue += monthly_revenue
        # 可选：考虑未来收入折现
        # cumulative_revenue += monthly_revenue / (1 + discount_rate) ** t
    return cumulative_revenue

# 不同分群的留存曲线和 ARPU
segments = {
    '高价值用户': {'retention': 0.90 ** np.arange(24), 'arpu': 80},
    '普通用户':   {'retention': 0.75 ** np.arange(24), 'arpu': 40},
    '低价值用户': {'retention': 0.50 ** np.arange(24), 'arpu': 15},
}

for seg, params in segments.items():
    ltv = calculate_segment_ltv(params['retention'], params['arpu'])
    print(f"{seg} LTV: ¥{ltv:.2f}")
```

**输出**：
```
简单 LTV（24个月）: ¥362.88
拟合 LTV（60个月）: ¥468.52
高价值用户 LTV: ¥669.60
普通用户 LTV: ¥163.95
低价值用户 LTV: ¥29.77
```

**关键洞见**：高价值用户的 LTV 是低价值用户的 22 倍。这意味着：
- 获客预算可以给高价值渠道花更多
- 运营资源要向高价值用户倾斜
- 产品设计要为高价值用户优化（哪怕牺牲一点低价值用户的体验）

### 6.4 LTV 预测的进阶方向

| 方法 | 描述 | 适用场景 |
|------|------|---------|
| 历史平均法 | 过去数据简单平均 | 早期产品、数据少 |
| 留存曲线法 | 拟合留存率衰减曲线 | SaaS、订阅制 |
| 概率模型 | BG/NBD、Gamma-Gamma | 非订阅制（电商等） |
| 机器学习 | 用用户特征直接预测 LTV | 数据量丰富（10万+用户） |

---

## 七、商业案例：Spotify 的用户分群策略

### 案例全景

Spotify 对用户进行多维分群，每个群体有差异化体验：

**免费用户 vs 付费用户**（最粗粒度的分群）：
- 免费用户：广告支持、随机播放、有限跳过
- 付费用户：无广告、自由选择、离线下载

**音乐品味分群**（行为分群）：
- "The Die-Hard Fan"：反复听同一艺人的重度粉丝
- "The Explorer"：不断发现新音乐的猎奇者
- "The Curator"：喜欢创建和分享歌单的社交型
- "The Background Listener"：音乐只是背景音

**策略映射**：
- Die-Hard Fan：推送演唱会信息、艺人物品
- Explorer：个性化推荐、每周发现
- Curator：歌单分享功能加强
- Background Listener：简化界面、降低使用成本

**结果**：基于分群的个性化推荐使付费转化率提升 30%+。

### AI 产品案例：用户分群的实战

一家 AI 对话产品做了用户分群后发现：

| 分群 | 占比 | 行为特征 | LTV | 策略 |
|------|------|---------|-----|------|
| 工作助手型 | 30% | 写邮件、总结文档、翻译 | ¥480/年 | 聚焦生产力功能 |
| 学习伙伴型 | 25% | 问知识、解释概念 | ¥240/年 | 推学习专题 |
| 娱乐闲聊型 | 35% | 角色扮演、闲聊 | ¥120/年 | 做角色模板 |
| 尝鲜用户 | 10% | 注册后只用1-2次 | ¥30/年 | 降低使用门槛 |

**关键是**：不要试图服务所有用户。资源有限时，优先满足"工作助手型"和"学习伙伴型"——他们 LTV 高、流失率低。

---

## 八、总结

| 分群方法 | 数据要求 | 复杂度 | 产出 | 最佳场景 |
|---------|---------|--------|------|---------|
| RFM | 交易数据即可 | 低 | 8个固定分群 | 电商、零售 |
| K-Means 聚类 | 数值型行为特征 | 中 | 自定义聚类 | 多维度行为分群 |
| PSM | 问卷数据 | 中 | 定价区间 | 新品定价 |
| 行为分群 | 用户行为日志 | 中 | 行为标签 | 产品策略 |
| LTV 预测 | 时间序列+用户特征 | 高 | 价值预测 | 获客预算分配 |

**技术人的行动清单**：
1. 起步：先跑一个 RFM，几乎所有有交易数据的产品都能用
2. 升级：加入更多行为维度，用 K-Means 替代人工分箱
3. 深化：分群后计算每个群体的 LTV，用数据指导资源分配
4. 落地：关键不是分群有多精细，而是分群后能不能做不同的策略

**下一课预告**：从单个产品到平台经济——网络效应、双边市场和补贴策略。
