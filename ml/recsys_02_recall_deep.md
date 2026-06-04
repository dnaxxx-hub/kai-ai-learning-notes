# 推荐系统 #2：召回阶段深度 — 从协同过滤到向量化

> 召回是推荐系统的第一道闸门，决定了推荐效果的天花板。本篇深入召回阶段的经典与前沿技术，包含完整 PyTorch 实战。

---

## 第一单元：召回的本质

### 1.1 召回要解决什么问题

物品池可能有百万到十亿级别，排序模型即使再快，也无法对全量物品做精密打分。召回的任务是：**在极短时间内，从海量物品中筛选出数百到数千个「最可能被用户喜欢的候选」**。

### 1.2 召回的评估指标

| 指标 | 含义 | 公式 |
|------|------|------|
| HitRate@K | 用户真实交互的物品是否出现在召回 Top-K 中 | HitRate = 1/N · Σ I(item_i ∈ topK(u)) |
| Recall@K | 召回覆盖了多少用户的历史正样本 | Recall = 正样本命中数 / 总正样本数 |
| Precision@K | 召回的 K 个中有多少是正样本 | Precision = 命中数 / K |

### 1.3 召回的发展脉络

```
[无个性化] → [协同过滤] → [矩阵分解] → [向量化双塔] → [图召回]
    2010        2012         2014          2018          2020
```

每个阶段解决的核心问题：
- **协同过滤**：利用用户-物品交互矩阵，依赖"邻居"做推演
- **矩阵分解**：将交互矩阵分解为隐向量，突破稀疏性瓶颈
- **向量化**：用 DNN 学习用户/物品的语义向量，支持 Side Information
- **图召回**：利用用户-物品二部图的高阶连通性，探索长尾

---

## 第二单元：协同过滤（Collaborative Filtering）

### 2.1 User-Based CF

**核心思想**：找到与目标用户兴趣相似的其他用户，把那些用户喜欢的物品推荐过来。

**步骤**：
1. 计算用户相似度矩阵（通常用余弦相似度或 Pearson 相关系数）
2. 找到 Top-K 个最相似用户
3. 聚合这些用户对某个物品的评分作为推荐得分

**相似度计算**（以余弦相似度为例）：

```
sim(u, v) = (r_u · r_v) / (|r_u| · |r_v|)
```

其中 r_u 是用户 u 对所有物品的评分向量。

**评分预测**：

```
pred(u, i) = (Σ_{v∈N(u)} sim(u, v) · r_{v,i}) / (Σ_{v∈N(u)} |sim(u, v)|)
```

### 2.2 Item-Based CF

**核心思想**：如果用户喜欢物品 A，那么和 A 相似的物品也值得推荐。这比 UserCF 更稳定——**物品相似度变化慢，可离线预计算**。

**步骤**：
1. 计算物品间相似度矩阵
2. 找到用户历史交互物品最相似的 Top-K 物品
3. 按相似度加权聚合，得到候选集

**优势**：
- 可解释性强（"因为你看过《黑客帝国》，推荐《盗梦空间》"）
- 离线计算，线上只需查表
- 用户多、物品相对少的场景效果好（电商）

**劣势**：
- 冷启动问题：新物品无交互，无法计算相似度
- 覆盖度有限：推荐结果往往局限在用户历史偏好附近（"信息茧房"）

### 2.3 UserCF vs ItemCF 对比

| 维度 | UserCF | ItemCF |
|------|--------|--------|
| 核心 | 找相似用户 | 找相似物品 |
| 计算成本 | 用户数平方（用户数量大） | 物品数平方（物品通常少于用户） |
| 离线友好 | 否（用户交互实时变化） | 是（物品属性相对稳定） |
| 可解释性 | 弱 | 强 |
| 多样性 | 较好（跨领域推荐） | 较差（同质化） |
| 适用场景 | 新闻/短视频（兴趣多变） | 电商/电影（偏好稳定） |

---

## 第三单元：矩阵分解（Matrix Factorization）

### 3.1 从协同过滤到隐向量

协同过滤的缺点：交互矩阵 **极度稀疏**（Amazon 商品矩阵稀疏度高达 99.9%+），基于邻居的推测极易过拟合。

**矩阵分解的核心洞察**：用户和物品都可以用低维隐向量表示，交互行为是隐向量的内积结果。

### 3.2 SVD 与 FunkSVD

**经典 SVD**：将交互矩阵 R (m×n) 分解为：

```
R ≈ U · Σ · V^T
```

其中 U ∈ ℝ^(m×k) 是用户隐向量矩阵，V ∈ ℝ^(n×k) 是物品隐向量矩阵。

**问题**：经典 SVD 要求矩阵完整——但现实交互矩阵 >99% 是缺失值。强行填充缺失值（如填 0）会导致巨大偏差。

**FunkSVD（Simon Funk, 2006）**：只对观测到的评分做分解，用梯度下降优化：

```
min Σ_{(u,i)∈R_obs} (r_{ui} − p_u · q_i^T)² + λ(|p_u|² + |q_i|²)
```

其中 p_u 是用户 u 的隐向量，q_i 是物品 i 的隐向量。

**SGD 更新公式**：

```
e_{ui} = r_{ui} − p_u · q_i^T
p_u ← p_u + η · (e_{ui} · q_i − λ · p_u)
q_i ← q_i + η · (e_{ui} · p_u − λ · q_i)
```

### 3.3 Bias SVD（加上偏置项）

在预测中引入用户偏置和物品偏置：

```
r̂_{ui} = μ + b_u + b_i + p_u · q_i^T
```

- μ：全局平均分
- b_u：用户偏置（某些用户打分天然偏高）
- b_i：物品偏置（某些物品评分普遍偏高）

### 3.4 SVD++（加入隐式反馈）

用户行为除了显式评分，还有点击、浏览、收藏等隐式反馈。SVD++ 将隐式反馈也编码进用户向量：

```
r̂_{ui} = μ + b_u + b_i + (p_u + |N(u)|^{−½} Σ_{j∈N(u)} y_j) · q_i^T
```

其中 N(u) 是用户 u 产生过隐式交互的物品集合，y_j 是物品 j 的隐式反馈向量。

### 3.5 ALS（交替最小二乘法）

SGD 适合小规模，大规模场景常用 **ALS**：
- 固定物品矩阵，求解用户矩阵（最小二乘闭式解）
- 固定用户矩阵，求解物品矩阵
- 交替迭代直到收敛

**优势**：可并行化（每个用户/物品独立求解），适用于 Spark 等分布式框架。Spark MLlib 的推荐模块就是基于 ALS。

---

## 第四单元：向量化召回 — 从 Word2Vec 到 Item2Vec

### 4.1 Word2Vec 的思想迁移

**Word2Vec（Mikolov, 2013）**：通过上下文预测目标词（CBOW）或通过目标词预测上下文（Skip-gram），学习词的向量表示。

**关键洞察**：用户的**行为序列**可以看作一个"句子"，用户点击/购买的物品就是"词"。于是 Word2Vec 可以直接迁移到推荐场景。

### 4.2 Item2Vec

**核心思想**：将用户的行为序列视为文档，每个 item 是 word，用 Skip-gram 训练物品向量。

**公式**：给定序列 [i_1, i_2, ..., i_T]，最大化：

```
Σ_{t=1}^{T} Σ_{c∈[−w, w], c≠0} log P(i_{t+c} | i_t)
```

其中：

```
P(j | i) = exp(v_j'^T · v_i) / Σ_{k∈Items} exp(v_k'^T · v_i)
```

**工业技巧**：
- **负采样**：softmax 的分母需要遍历所有物品，用负采样近似：用 K 个随机负样本替代全量
- **滑动窗口**：窗口大小 w 通常 3-5，控制局部共现范围
- **序列构造**：同一 session 内的点击序列 > 跨 session 的全局序列

**Airbnb 的改进（2018）**：
- **全局负采样 + 房间类型负采样**：解决冷门物品被负采样严重打压的问题
- **用户短期意图 vs 长期偏好**：使用两个不同的嵌入做联合训练

### 4.3 向量化召回的优势

| 维度 | 矩阵分解 | Item2Vec |
|------|---------|----------|
| 输入 | 评分矩阵 | 行为序列 |
| 序列信息 | 无 | 有（共现窗口） |
| 冷启动 | 差 | 差（仍依赖共现） |
| 训练方式 | SGD/ALS | Skip-gram |
| 产出 | 用户向量 + 物品向量 | 物品向量（用户向量需要额外处理） |

---

## 第五单元：双塔模型 — 深度学习召回的工业标准

### 5.1 为什么是双塔

召回需要将用户和物品都映射到一个共同的向量空间，然后通过 **最近邻搜索（ANN: Approximate Nearest Neighbor）** 快速检索。

**双塔架构**：
```
用户侧特征 → User Tower → 用户向量 u_emb
物品侧特征 → Item Tower → 物品向量 v_emb
score = cos(u_emb, v_emb) 或 u_emb · v_emb
```

**关键优势**：
- 用户和物品两塔**独立计算**，物品向量可离线预计算 + 建索引
- 线上推理：用户向量实时计算 → ANN 检索 Top-K → 完成召回
- 支持任意特征输入（不只是交互矩阵）

### 5.2 DSSM（Deep Structured Semantic Model）

DSSM 最初用于搜索（Query-Document 匹配），迁移到推荐后称为 **经典双塔**。

**网络结构**：
```
用户特征 → Dense → BatchNorm → ReLU → Dense → ... → u_emb
物品特征 → Dense → BatchNorm → ReLU → Dense → ... → v_emb
```

**损失函数**：采用 **Sampled Softmax**，对每个正样本采样 K 个负样本：

```
L = −log( exp(s(u, v⁺)/τ) / (exp(s(u, v⁺)/τ) + Σ_{j=1}^{K} exp(s(u, vⱼ⁻)/τ) )
```

其中 τ 是温度系数（temperature），控制分布的"尖锐度"。

### 5.3 双塔模型的关键技巧

**1) Batch Negative Sampling**
在一个 batch 内，假设每条记录是 (user_i, item_i⁺)，那么 batch 内的其他 item 可以当作该用户的负样本。这样无需额外采样，且负样本数量 = batch_size - 1。

**2) 特征交叉的位置**
双塔的弱点：**用户和物品特征只在最后一层做点积交互**，缺乏早期特征交叉（这是排序模型的优势）。

**缓解方案**：
- 在用户塔/物品塔各自内部做特征交叉（如 FM 层）
- 使用 **SENet** 对输入特征做自适应加权
- 引入 **Multi-head Attention** 处理用户行为序列

**3) 实时特征 vs 离线索引**
物品塔的输出需要在索引构建时就确定。如果物品特征包含实时信息（如实时 CTR），则索引更新频率非常高。

**4) 向量检索工具**
- **Faiss**（Facebook）：支持 IVF、HNSW、PQ 等多种索引结构
- **Milvus**：云原生向量数据库
- **HNSWlib**：基于 Hierarchical Navigable Small World 图的高效检索

### 5.4 Sentence-BERT 与双塔

Sentence-BERT（SBERT, 2019）虽然来自 NLP，但其架构与双塔召回一致：将句子编码为固定长度向量，用余弦相似度做语义匹配。

**推荐场景的应用**：
- 物品描述文本 → BERT → 物品语义向量
- 用户历史描述 → BERT → 用户偏好向量
- 适合冷启动（仅依赖文本特征，无需交互数据）

**局限**：BERT 模型太大，线上推理延迟高。工程上常用 **蒸馏**：用大 BERT 蒸馏到小双塔。

---

## 第六单元：图召回 — 从 PinSage 到 EGES

### 6.1 为什么需要图

传统协同过滤和双塔只利用一阶交互（用户←→物品），但推荐系统中存在**高阶关联**：
```
用户A → 物品X ← 用户B → 物品Y ← 用户C
```
用户 A 和物品 Y 有**二阶路径**，传统方法无法建模这种关系。

### 6.2 PinSage（Pinterest, 2018）

PinSage 将 **GraphSAGE（归纳式图神经网络）** 应用到 Pinterest 的 20 亿 Pin 物品图。

**核心步骤**：

**1) 邻居采样**
每个节点采样固定数量的邻居（如 K=50），而非使用全部邻居。这使得训练可以批量化和固定计算图。

**2) 聚合（AGGREGATE）**
邻居信息通过聚合函数合并：
- Mean aggregator：取邻居向量的均值
- Pooling aggregator：逐元素 max-pooling
- LSTM aggregator：用 LSTM 处理邻居序列（需随机排序）

**3) 节点更新**
```
h_v^{(k)} = ReLU(W · AGG({h_u^{(k−1)} : u ∈ N(v)}) + B · h_v^{(k−1)})
```

**4) 损失函数（最大间隔损失）**
```
L = Σ_{(q, i)∈正样本} Σ_{(j)∈负样本} max(0, d(q, i) − d(q, j) + margin)
```

**PinSage 的工业贡献**：
- 高效 mini-batch 训练：通过重要性采样，避免全图计算
- **个人化 PageRank 采样**：用 PPR 分数来定义"邻居"的权重，比简单 BFS 更有效
- 支持多维特征（文本、图像、标签）作为节点初始向量

### 6.3 EGES（Enhanced Graph Embedding with Side Information）

**EGES（Alibaba, 2018）**：在 Item2Vec 的基础上引入 Side Information（品牌、品类、店铺等），并自动学习各属性权重。

**创新点**：
1. 基于用户行为序列构建物品共现图
2. 将 Side Information 的嵌入加权融合：

```
h_v = Σ_{s=0}^{S} α_v^{(s)} · W_s · e_v^{(s)}
```

其中 α_v^{(s)} 是**自适应权重**（通过 Softmax 归一化），e_v^{(s)} 是属性 s 的嵌入向量。

3. 权重 α_v^{(s)} 随模型一起训练，自动学习不同属性对最终表征的贡献

**为什么 EGES 有效**：
- 冷门物品可能交互少，但它的品牌、品类可能很热门 → Side Information 提供了跨物品共享信号
- 不同属性的影响力不同：电商场景中"价格带"可能比"颜色"更重要

### 6.4 图召回 Vs 双塔

| 维度 | 双塔 | 图召回 |
|------|------|--------|
| 关系建模 | 一对一（用户×物品） | 高阶邻居（多跳） |
| 冷启动 | 依赖 Side Information | 图的传播特性更强 |
| 训练复杂度 | O(batch) | O(batch × K^L)，K=邻居数，L=层数 |
| 索引友好 | 非常友好 | 需要 node embedding |
| 工业落地 | 最广泛 | 资源消耗大，大规模应用有限 |

---

## 第七单元：多路召回融合策略

### 7.1 为什么需要多路

没有一种召回策略是完美的：
- 协同过滤 → 能发现热门相似关系，但冷启动差
- 双塔 → 泛化能力强，但对尾部兴趣覆盖有限
- 图召回 → 能探索长尾，但延迟高、索引复杂
- 内容召回（Tag/LDA）→ 理解语义，但交互信号弱

**工业界通常同时跑 5-15 路召回**，每一路产出自己的候选列表。

### 7.2 融合策略

**1) 简单合并且去重**
```
候选池 = {A路 Top-200} ∪ {B路 Top-200} ∪ {C路 Top-200}
```
问题：不考虑各路质量差异。

**2) 加权融合**
各路召回得分乘以权重后合并，权重可通过 AutoML 或搜索方法调优。

**3) 分层融合（Stacking）**
召回的结果输入一个轻量级模型（如 LR、GBDT）做二次排序，学习各路召回的权重和互补关系。

**4) 动态路由（MoE 思想）**
根据用户画像、上下文选择不同的召回组合。例如：新用户侧重内容召回，老用户侧重协同过滤。

### 7.3 各路召回量的分配

经验法则：
- 主召回路（双塔/协同过滤）：50%-60%
- 辅助召回路（热门/新物品补充）：15%-20%
- 探索召回（冷启动/长尾）：10%-15%
- 个性化召回（图/序列）：10%-20%

---

## 第八单元：实战 — PyTorch 简易双塔模型

### 8.1 整体架构

本实战实现一个面向 MovieLens 场景的双塔召回模型：

```
用户特征(age, gender, occupation) → User Tower → u_emb (64维)
电影特征(genre, year) → Item Tower → v_emb (64维)
score = dot(u_emb, v_emb)
loss = sampled_softmax_loss
```

### 8.2 完整代码实现

```python
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import defaultdict
import random

# ==============================
# 1. 数据准备（模拟 MovieLens 风格）
# ==============================

def build_vocab_and_data(num_users=1000, num_items=1000, num_interactions=50000):
    """
    生成模拟交互数据：
    - 每个交互：user_id, item_id, label(0/1)
    - 用户特征：age(18-60), gender(0/1), occupation(0-20)
    - 物品特征：genre(0-18), year(1990-2020)
    """
    users_feat = {}
    items_feat = {}
    interactions = []

    random.seed(42)
    np.random.seed(42)

    for uid in range(num_users):
        users_feat[uid] = {
            'age': np.random.randint(18, 61),
            'gender': np.random.randint(0, 2),
            'occupation': np.random.randint(0, 21),
        }

    for iid in range(num_items):
        items_feat[iid] = {
            'genre': np.random.randint(0, 19),
            'year': np.random.randint(1990, 2021),
        }

    for _ in range(num_interactions):
        uid = np.random.randint(0, num_users)
        iid = np.random.randint(0, num_items)
        label = 1 if np.random.random() > 0.5 else 0
        interactions.append((uid, iid, label))

    # 80/20 split
    random.shuffle(interactions)
    split = int(len(interactions) * 0.8)
    train = interactions[:split]
    test = interactions[split:]

    return users_feat, items_feat, train, test


# ==============================
# 2. 特征处理
# ==============================

class FeatureProcessor:
    """处理稀疏特征，生成嵌入索引和连续特征"""

    def __init__(self, users_feat, items_feat):
        self.users_feat = users_feat
        self.items_feat = items_feat
        # 计算词汇大小
        self.age_vocab = 61   # 18-60
        self.gender_vocab = 2
        self.occ_vocab = 21   # 0-20
        self.genre_vocab = 19
        self.year_vocab = 31  # 1990-2020

    def get_user_features(self, uid):
        feat = self.users_feat[uid]
        return {
            'age': feat['age'],
            'gender': feat['gender'],
            'occupation': feat['occupation'],
        }

    def get_item_features(self, iid):
        feat = self.items_feat[iid]
        return {
            'genre': feat['genre'],
            'year': feat['year'] - 1990,  # 映射到 0-30
        }


# ==============================
# 3. 双塔模型定义
# ==============================

class UserTower(nn.Module):
    def __init__(self, emb_dim=32):
        super().__init__()
        # 稀疏特征嵌入
        self.age_emb = nn.Embedding(61, 8)
        self.gender_emb = nn.Embedding(2, 4)
        self.occ_emb = nn.Embedding(21, 8)
        # DNN层
        self.fc = nn.Sequential(
            nn.Linear(8 + 4 + 8, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, emb_dim),
            nn.BatchNorm1d(emb_dim),
        )

    def forward(self, age, gender, occupation):
        age_e = self.age_emb(age)               # [B, 8]
        gender_e = self.gender_emb(gender)      # [B, 4]
        occ_e = self.occ_emb(occupation)         # [B, 8]
        x = torch.cat([age_e, gender_e, occ_e], dim=1)
        return self.fc(x)                        # [B, emb_dim]


class ItemTower(nn.Module):
    def __init__(self, emb_dim=32):
        super().__init__()
        self.genre_emb = nn.Embedding(19, 8)
        self.year_emb = nn.Embedding(31, 4)
        self.fc = nn.Sequential(
            nn.Linear(8 + 4, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Linear(64, emb_dim),
            nn.BatchNorm1d(emb_dim),
        )

    def forward(self, genre, year):
        genre_e = self.genre_emb(genre)    # [B, 8]
        year_e = self.year_emb(year)       # [B, 4]
        x = torch.cat([genre_e, year_e], dim=1)
        return self.fc(x)


class TwoTowerModel(nn.Module):
    """
    双塔召回模型
    - 用户塔和物品塔独立计算嵌入
    - 通过点积计算相似度
    - 训练时使用 Sampled Softmax 损失
    """

    def __init__(self, emb_dim=32, temperature=0.1):
        super().__init__()
        self.user_tower = UserTower(emb_dim)
        self.item_tower = ItemTower(emb_dim)
        self.temperature = temperature

    def forward(self, user_feats, item_feats):
        """
        前向计算：返回用户和物品的嵌入向量
        """
        u_emb = self.user_tower(**user_feats)   # [B, emb_dim]
        v_emb = self.item_tower(**item_feats)   # [B, emb_dim]
        return u_emb, v_emb

    def compute_scores(self, u_emb, v_emb):
        """计算点积相似度 (with temperature scaling)"""
        return torch.sum(u_emb * v_emb, dim=1) / self.temperature


# ==============================
# 4. Sampled Softmax 损失
# ==============================

class SampledSoftmaxLoss(nn.Module):
    """
    采样 Softmax 损失：
    - 每个 batch 内，取所有 item 作为候选
    - 正样本是当前 (user, item)，其他 item 作为负样本
    - 等价于 batch negative sampling
    """

    def forward(self, u_emb, v_emb, temperature=0.1):
        """
        u_emb: [B, D] 用户嵌入
        v_emb: [B, D] 正样本物品嵌入
        """
        # 计算所有用户和所有物品的相似度矩阵 [B, B]
        logits = torch.matmul(u_emb, v_emb.T) / temperature

        # 对角线是正样本 (user_i, item_i)
        batch_size = u_emb.size(0)
        labels = torch.arange(batch_size, device=u_emb.device)

        # Cross-entropy loss
        loss = nn.CrossEntropyLoss()(logits, labels)
        return loss


# ==============================
# 5. 训练流程
# ==============================

def train_epoch(model, loss_fn, optimizer, train_data,
                feature_processor, batch_size=256, device='cpu'):
    model.train()
    total_loss = 0
    n_batches = 0

    random.shuffle(train_data)
    for i in range(0, len(train_data), batch_size):
        batch = train_data[i:i + batch_size]

        uids = torch.tensor([x[0] for x in batch], device=device)
        iids = torch.tensor([x[1] for x in batch], device=device)

        # 提取特征
        user_feats = {
            'age': torch.tensor(
                [feature_processor.users_feat[uid.item()]['age']
                 for uid in uids], device=device),
            'gender': torch.tensor(
                [feature_processor.users_feat[uid.item()]['gender']
                 for uid in uids], device=device),
            'occupation': torch.tensor(
                [feature_processor.users_feat[uid.item()]['occupation']
                 for uid in uids], device=device),
        }
        item_feats = {
            'genre': torch.tensor(
                [feature_processor.items_feat[iid.item()]['genre']
                 for iid in iids], device=device),
            'year': torch.tensor(
                [feature_processor.items_feat[iid.item()]['year'] - 1990
                 for iid in iids], device=device),
        }

        # 前向
        u_emb, v_emb = model(user_feats, item_feats)
        loss = loss_fn(u_emb, v_emb, model.temperature)

        # 反向
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()

        total_loss += loss.item()
        n_batches += 1

    return total_loss / n_batches


# ==============================
# 6. 召回评估
# ==============================

def recall_at_k(model, test_data, all_item_ids,
                feature_processor, k=20, device='cpu'):
    """
    评估 Recall@K：对每个测试交互，用户嵌入 vs 所有物品嵌入做检索
    """
    model.eval()
    hits = 0
    total = 0

    # 预计算所有物品嵌入
    with torch.no_grad():
        all_iids = torch.tensor(list(all_item_ids), device=device)
        all_item_feats = {
            'genre': torch.tensor(
                [feature_processor.items_feat[iid.item()]['genre']
                 for iid in all_iids], device=device),
            'year': torch.tensor(
                [feature_processor.items_feat[iid.item()]['year'] - 1990
                 for iid in all_iids], device=device),
        }
        all_v_emb = model.item_tower(**all_item_feats)  # [N_items, D]

    for uid, iid, _ in test_data:
        # 用户嵌入
        feat = feature_processor.get_user_features(uid)
        user_tensor = {
            'age': torch.tensor([feat['age']], device=device),
            'gender': torch.tensor([feat['gender']], device=device),
            'occupation': torch.tensor([feat['occupation']], device=device),
        }
        with torch.no_grad():
            u_emb = model.user_tower(**user_tensor)  # [1, D]

        # 计算与所有物品的相似度
        scores = torch.matmul(u_emb, all_v_emb.T).squeeze(0)  # [N_items]
        topk = torch.topk(scores, k).indices.cpu().numpy()
        topk_ids = set(all_iids[topk].cpu().numpy())

        if iid in topk_ids:
            hits += 1
        total += 1

    return hits / total


# ==============================
# 7. 主程序
# ==============================

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # 数据准备
    users_feat, items_feat, train, test = build_vocab_and_data()
    fp = FeatureProcessor(users_feat, items_feat)

    # 模型初始化
    model = TwoTowerModel(emb_dim=32, temperature=0.1).to(device)
    loss_fn = SampledSoftmaxLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)

    # 训练
    epochs = 10
    all_item_ids = set(items_feat.keys())

    for epoch in range(epochs):
        loss = train_epoch(model, loss_fn, optimizer, train,
                           fp, batch_size=256, device=device)
        recall = recall_at_k(model, test[:200], all_item_ids,
                             fp, k=20, device=device)
        print(f"Epoch {epoch+1:2d} | Loss: {loss:.4f} | Recall@20: {recall:.4f}")

    print("\n训练完成！双塔模型已就绪，可以导出物品向量用于 ANN 索引构建。")


if __name__ == '__main__':
    main()
```

### 8.3 代码结构说明

| 模块 | 功能 |
|------|------|
| `build_vocab_and_data` | 构造模拟数据：用户特征、物品特征、交互记录 |
| `FeatureProcessor` | 特征处理器，管理各字段的词汇表大小 |
| `UserTower` / `ItemTower` | 独立 DNN，将稀疏特征映射到统一嵌入空间 |
| `TwoTowerModel` | 双塔整合，包含温度系数（temperature） |
| `SampledSoftmaxLoss` | Batch Negative Sampling 实现 |
| `recall_at_k` | 模拟 ANN 检索过程，评估召回效果 |

### 8.4 工业落地的关键差异

1. **特征规模**：工业场景特征数几百到几千，嵌入表可达数亿级别，需分布式 Parameter Server
2. **ANN 检索**：上述代码用暴力扫描（不实用），工业用 Faiss HNSW 索引，召回延迟 <10ms
3. **负采样策略**：除了 Batch Negative，还会加入全局随机负采样 + Hard Negative（精排淘汰的物品）
4. **多级特征**：工业级双塔包含几十个类别特征 + 数值特征 + 序列特征
5. **蒸馏**：用复杂精排模型蒸馏双塔，提升召回质量

---

## 召回阶段总结

```
召回策略全景图：

┌─────────────────────────────────────────────┐
│      基于交互的方法                            │
│  ┌─────────────────────────────────────┐     │
│  │ 协同过滤（UserCF / ItemCF）           │ 起步 │
│  │ 矩阵分解（FunkSVD / SVD++ / ALS）    │ 泛化 │
│  │ 图召回（PinSage / EGES）              │ 深探 │
│  └─────────────────────────────────────┘     │
├─────────────────────────────────────────────┤
│      基于内容的方法                            │
│  ┌─────────────────────────────────────┐     │
│  │ Embedding 召回（Item2Vec / Word2Vec）│ 序列 │
│  │ 双塔模型（DSSM / SBERT）              │ 主流 │
│  └─────────────────────────────────────┘     │
├─────────────────────────────────────────────┤
│      基于规则的方法                            │
│  ┌─────────────────────────────────────┐     │
│  │ 热门召回（Top Popular）                │ 保底 │
│  │ 新物品召回（New Released）             │ 冷启 │
│  │ 类别/标签召回                         │ 语义 │
│  └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
         ↓
    多路融合 → 候选池供排序阶段使用
```

**核心 takeaways**：
1. 没有一招制胜的召回策略，工业界用多路召回互补
2. 双塔模型是当前工业召回的事实标准，核心在特征工程和负采样
3. 图召回在长尾探索方面有独特价值，但工程成本高
4. 融合策略和排序质量同样重要，召回≠推荐

---
*下一篇：[推荐系统 #3：排序阶段深度 — 从 LR 到 DeepFM] →*
