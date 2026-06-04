# 推荐系统 #3：协同过滤与矩阵分解

> 从"物以类聚"到隐向量分解，协同过滤家族全景

---

## 1. 协同过滤的核心思想

**核心假设**：过去行为模式相似的用户，未来偏好也相似。

**两大前提**：
- **用户-物品交互矩阵**存在（评分、点击、购买等）
- 矩阵中隐含**低秩结构**——即用户偏好由少量隐因子驱动

**两大流派**：
| 流派 | 思路 | 代表 |
|------|------|------|
| 基于记忆（Memory-based） | 直接用邻居的行为做预测 | User-based / Item-based CF |
| 基于模型（Model-based） | 学习参数化模型拟合行为 | Matrix Factorization, FM |

---

## 2. 基于记忆的协同过滤

### 2.1 User-based CF

**流程**：
1. 计算目标用户 u 与所有其他用户的相似度
2. 选出 Top-K 最相似用户（邻居）
3. 聚合邻居对物品 i 的评分，预测 u 对 i 的评分

**预测公式**（均值中心化版）：
```
r̂_ui = μ_u + Σ_{v∈N(u)} sim(u,v) · (r_vi - μ_v) / Σ_{v∈N(u)} |sim(u,v)|
```

> 用 `μ_u`（用户均值评分）做基准，邻居评分减去其自身均值，消除用户打分习惯差异。

### 2.2 Item-based CF

**流程**：
1. 对用户已评分的每个物品，找到最相似的 K 个物品
2. 加权聚合这些相似物品的评分

**优势**：
- 物品间相似度相对稳定，可离线预计算 → 在线预测快
- 推荐理由直观："因为你看过 X，所以推荐 Y"
- **Amazon 早期主力算法**

**预测公式**：
```
r̂_ui = Σ_{j∈N(i;u)} sim(i,j) · r_uj / Σ_{j∈N(i;u)} |sim(i,j)|
```

> `N(i;u)` = 用户 u 评分过的、且与物品 i 最相似的物品集合。

### 2.3 相似度计算方法

#### 余弦相似度（Cosine Similarity）
```
sim(u,v) = (r_u · r_v) / (||r_u|| · ||r_v||)
```
- 忽略向量长度，只关心方向
- **问题**：未评分位置视为 0，会引入偏差

#### 皮尔逊相关系数（Pearson Correlation）
```
sim(u,v) = Σ_i (r_ui - μ_u)(r_vi - μ_v) / sqrt(Σ_i (r_ui - μ_u)² · Σ_i (r_vi - μ_v)²)
```
- 减去均值，消除用户打分尺度的偏差
- 只对**共同评分**的物品计算

#### Jaccard 系数
```
J(A,B) = |A ∩ B| / |A ∪ B|
```
- 适用场景：隐式反馈（点击/收藏）而非评分
- 只关心是否互动，不关心程度

### 2.4 归一化问题

**人口偏差**：活跃用户评分多但方差大，冷门用户评分少但可能更精确。有些用户整体打分偏高，有些偏低。

**活跃度偏差**：热门物品被广泛评价，相似度计算时应降低其权重。

**常用策略**：
- **均值中心化**（Mean Centering）：`r_ui - μ_u`
- **Z-score 归一化**：`(r_ui - μ_u) / σ_u`
- **逆文档频率加权**（类似 TF-IDF）：稀有物品打分权重更高

---

## 3. 矩阵分解（Matrix Factorization）

### 3.1 SVD 分解数学原理

**经典 SVD**：任意矩阵 R ∈ ℝ^{m×n} 可分解为：
```
R = U · Σ · V^T
```
- U：m×k 正交矩阵（用户-隐因子）
- Σ：k×k 对角矩阵（奇异值，降序排列）
- V^T：k×n 正交矩阵（物品-隐因子）

**问题**：评分矩阵稀疏（>95% 缺失），直接 SVD 需先填充缺失值 → 计算量大、效果差。

### 3.2 FunkSVD（隐因子模型）

Simon Funk 在 Netflix Prize 提出：**只对已知评分建模，忽略缺失值**。

**思想**：学习两个低维矩阵的乘积来近似 R：
```
R ≈ P · Q^T
```
- P ∈ ℝ^{m×k}：用户隐因子矩阵（每行 p_u 表示用户 u 的隐向量）
- Q ∈ ℝ^{n×k}：物品隐因子矩阵（每行 q_i 表示物品 i 的隐向量）

**预测公式**：
```
r̂_ui = p_u · q_i^T = Σ_{f=1}^{k} p_uf · q_if
```

**损失函数**（含正则化）：
```
min Σ_{(u,i)∈R_known} (r_ui - p_u · q_i^T)² + λ(||p_u||² + ||q_i||²)
```

### 3.3 BiasSVD

加入偏置项来捕获系统性偏差：

**预测公式**：
```
r̂_ui = μ + b_u + b_i + p_u · q_i^T
```
- μ：全局平均评分
- b_u：用户偏置（用户 u 比平均水平高/低多少）
- b_i：物品偏置（物品 i 比平均水平高/低多少）

**损失函数**（含正则化）：
```
min Σ (r_ui - μ - b_u - b_i - p_u·q_i^T)² + λ(||p_u||² + ||q_i||² + b_u² + b_i²)
```

**直觉**：
- 某用户平均打分 3.0，但整体平均 3.5 → b_u = -0.5
- 某电影平均 4.2，整体平均 3.5 → b_i = +0.7
- 预估该用户对该电影的基线分：3.5 - 0.5 + 0.7 = 3.7

### 3.4 SVD++

**改进**：显式评分 + 隐式反馈（浏览历史、收藏等）。

**预测公式**：
```
r̂_ui = μ + b_u + b_i + (p_u + |N(u)|^{-1/2} Σ_{j∈N(u)} y_j) · q_i^T
```
- N(u)：用户 u 发生过隐式行为的物品集合
- y_j：物品 j 的隐式反馈隐向量
- `p_u + 隐式反馈因子` 拼接为用户综合表示

> SVD++ 效果好于 BiasSVD，尤其在隐式反馈丰富的场景。

### 3.5 TimeSVD++

**改进**：用户和物品的偏置会随时间漂移。

```
b_u(t) = b_u + α_u · dev_u(t) + b_u,t
b_i(t) = b_i + b_i,bin(t)
```
- α_u · dev_u(t)：用户偏置随时间线性变化
- b_u,t：用户偏置的周期微调（如周、月）
- b_i,bin(t)：物品偏置按时间段分桶（如年份区间）

**优势**：捕获用户口味漂移、物品流行度变化。

---

## 4. ALS vs SGD

| 维度 | SGD（随机梯度下降） | ALS（交替最小二乘） |
|------|-------------------|-------------------|
| **更新方式** | 逐个样本更新参数 | 固定 Q 解 P，固定 P 解 Q，交替迭代 |
| **收敛速度** | 快（大数据集） | 较慢（每轮 O(k³)，小数据集尚可） |
| **并行性** | 难并行（依赖顺序更新） | **天然并行**（用户独立、物品独立） |
| **稀疏处理** | 天然适合稀疏数据 | 适合中等稀疏数据 |
| **隐式反馈** | 需改造损失函数 | **直接支持**（置信度加权 ALS） |
| **超参数** | 学习率敏感 | 正则化系数敏感 |
| **代表系统** | 大多数 DL 框架 | Spark MLlib ALS |

**推荐选择**：
- 数据量大、在线更新 → SGD
- 分布式环境、隐式反馈 → ALS
- 学术界普遍喜欢 SGD（灵活 + 易加偏置项）

---

## 5. 冷启动问题

| 类型 | 问题 | 方案 |
|------|------|------|
| **用户冷启动** | 新用户无行为 | ① 热点榜（Popularity） ② 注册时收集兴趣标签 ③ 跨域迁移 ④ 社交好友推荐 |
| **物品冷启动** | 新物品无人评 | ① 基于内容特征（属性/描述） ② 随机曝光探索 ③ 让老用户打标签 |
| **系统冷启动** | 新系统无数据 | ① 导入外部知识库 ② 人工编排冷启规则 ③ 逐步积累，从规则→统计→模型 |

**混合策略**：冷启动阶段用 Content-based 或 Popularity，积累足够数据后切到 CF。

---

## 6. 扩展模型

### 6.1 Factorization Machines（FM）

**核心**：将特征之间的二阶交互分解为隐向量内积。

**特征工程**：把所有信息（用户ID、物品ID、时间、上下文）合成为一个特征向量 x。

**预测公式**：
```
ŷ(x) = w₀ + Σ w_i x_i + Σ_{i<j} (v_i · v_j) x_i x_j
```
- w₀：全局偏置
- w_i：一阶权重（类似线性回归）
- v_i · v_j：特征 i, j 隐向量内积（二阶交互）

**优势**：
- 统一处理稀疏高维特征
- 泛化到未出现的特征组合
- 预测时间复杂度 O(k·n)（线性）

### 6.2 Field-aware FM（FFM）

**改进**：每个特征对每个域（Field）学习不同的隐向量。
```
ŷ = w₀ + Σ w_i x_i + Σ_{i<j} (v_i,f(j) · v_j,f(i)) x_i x_j
```
- f(j)：特征 j 所属的域
- v_i,f(j)：特征 i 相对于域 f(j) 的隐向量

**特点**：
- 参数更多（O(n·k·f) vs FM 的 O(n·k)）
- 效果更好，但训练更慢
- Criteo CTR 大赛夺冠利器

### 6.3 Neural CF（NeuMF）

**思想**：用神经网络替换 MF 内积。

**架构**：
```
输出层（预测评分/点击率）
     ↑
  融合层（拼接 + MLP）
     ↑
┌────┴────┐
GMF       MLP
(p_u⊙q_i) (MLP([p_u, q_i]))
```

- **GMF**（Generalized MF）：元素乘 → 线性交互
- **MLP**：拼接 → 非线性交互
- **NeuMF**：两者融合 → 同时捕获线性和非线性

**优势**：表达能力比内积更强；**劣势**：参数多，调参复杂。

---

## 7. 评估指标

### 7.1 Recall@K

```
Recall@K = 正样本被推荐到 Top-K 的比例 = |推荐∩正样本| / |正样本全体|
```

目标：看推荐列表命中了多少用户真正喜欢的物品。

### 7.2 HitRate（命中率）

```
HitRate = 推荐列表中是否包含正样本（0/1）
```

常用来评估「用户至少喜欢一个推荐」的概率。

### 7.3 MRR（Mean Reciprocal Rank）

```
MRR = (1/|U|) Σ_u 1 / rank_u
```

rank_u：第一个正样本在推荐列表中的位置。**越靠前分越高**。

### 7.4 NDCG@K（Normalized Discounted Cumulative Gain）

```
DCG@K = Σ_{i=1}^{K} (2^{rel_i} - 1) / log₂(i+1)
NDCG@K = DCG@K / IDCG@K (理想排序下的 DCG)
```

**特点**：
- 位置越靠前权重越大（对数折扣）
- 考虑相关性等级（rel_i ∈ {0,1,...}）
- **推荐系统最常用的排名指标之一**

---

## 8. 代码：PyTorch 实现 FunkSVD 和 BiasSVD

> 以下为完整实现代码，可用于 MovieLens 100K/1M 数据集。

### 8.1 数据准备（MovieLens 格式）

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

# 读取 MovieLens 数据
# 典型格式：userId, movieId, rating, timestamp
df = pd.read_csv('ml-100k/u.data', sep='\t',
                 names=['userId', 'movieId', 'rating', 'timestamp'])

# 构建用户/物品 ID 映射
user_ids = df['userId'].unique()
item_ids = df['movieId'].unique()
user2idx = {uid: i for i, uid in enumerate(user_ids)}
item2idx = {iid: j for j, iid in enumerate(item_ids)}
n_users = len(user_ids)      # ≈ 943
n_items = len(item_ids)     # ≈ 1682

df['user_idx'] = df['userId'].map(user2idx)
df['item_idx'] = df['movieId'].map(item2idx)

# 拆分为训练集和测试集
train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)

# 计算全局均值
global_mean = train_df['rating'].mean()
```

### 8.2 数据集封装

```python
class RatingDataset(Dataset):
    def __init__(self, df):
        self.users = torch.tensor(df['user_idx'].values, dtype=torch.long)
        self.items = torch.tensor(df['item_idx'].values, dtype=torch.long)
        self.ratings = torch.tensor(df['rating'].values, dtype=torch.float32)

    def __len__(self):
        return len(self.ratings)

    def __getitem__(self, idx):
        return self.users[idx], self.items[idx], self.ratings[idx]

train_loader = DataLoader(RatingDataset(train_df), batch_size=256, shuffle=True)
test_loader = DataLoader(RatingDataset(test_df), batch_size=256, shuffle=False)
```

### 8.3 FunkSVD 模型

```python
class FunkSVD(nn.Module):
    """FunkSVD（隐因子模型），无偏置项"""
    def __init__(self, n_users, n_items, n_factors=50):
        super().__init__()
        self.user_factors = nn.Embedding(n_users, n_factors)
        self.item_factors = nn.Embedding(n_items, n_factors)
        # 初始化：均值 0，标准差 0.01
        nn.init.normal_(self.user_factors.weight, std=0.01)
        nn.init.normal_(self.item_factors.weight, std=0.01)

    def forward(self, user, item):
        pu = self.user_factors(user)       # (batch, k)
        qi = self.item_factors(item)       # (batch, k)
        return (pu * qi).sum(dim=1)        # (batch,) r̂_ui = p_u · q_i
```

### 8.4 BiasSVD 模型

```python
class BiasSVD(nn.Module):
    """BiasSVD：加入用户偏置+物品偏置+全局均值"""
    def __init__(self, n_users, n_items, n_factors=50, global_mean=0.0):
        super().__init__()
        self.global_mean = global_mean
        self.user_factors = nn.Embedding(n_users, n_factors)
        self.item_factors = nn.Embedding(n_items, n_factors)
        self.user_bias = nn.Embedding(n_users, 1)
        self.item_bias = nn.Embedding(n_items, 1)

        nn.init.normal_(self.user_factors.weight, std=0.01)
        nn.init.normal_(self.item_factors.weight, std=0.01)
        nn.init.zeros_(self.user_bias.weight)
        nn.init.zeros_(self.item_bias.weight)

    def forward(self, user, item):
        pu = self.user_factors(user)          # (batch, k)
        qi = self.item_factors(item)          # (batch, k)
        bu = self.user_bias(user).squeeze()   # (batch,)
        bi = self.item_bias(item).squeeze()   # (batch,)
        # r̂_ui = μ + bu + bi + pu · qi
        return self.global_mean + bu + bi + (pu * qi).sum(dim=1)
```

### 8.5 训练函数

```python
def train_model(model, train_loader, test_loader, epochs=50, lr=0.01, reg=0.01, device='cpu'):
    model.to(device)
    optimizer = optim.SGD(model.parameters(), lr=lr, weight_decay=reg)
    # 或用 Adam: optim.Adam(model.parameters(), lr=lr, weight_decay=reg)

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for users, items, ratings in train_loader:
            users, items, ratings = users.to(device), items.to(device), ratings.to(device)

            optimizer.zero_grad()
            preds = model(users, items)
            loss = nn.MSELoss()(preds, ratings)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(ratings)

        # 验证
        model.eval()
        test_preds, test_trues = [], []
        with torch.no_grad():
            for users, items, ratings in test_loader:
                users, items = users.to(device), items.to(device)
                preds = model(users, items)
                test_preds.extend(preds.cpu().tolist())
                test_trues.extend(ratings.tolist())

        train_rmse = np.sqrt(total_loss / len(train_loader.dataset))
        test_rmse = np.sqrt(mean_squared_error(test_trues, test_preds))

        if (epoch + 1) % 10 == 0:
            print(f'Epoch {epoch+1:3d} | Train RMSE: {train_rmse:.4f} | Test RMSE: {test_rmse:.4f}')
```

### 8.6 运行

```python
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# FunkSVD
print("=== FunkSVD ===")
model_funk = FunkSVD(n_users, n_items, n_factors=50)
train_model(model_funk, train_loader, test_loader, epochs=50, device=device)

# BiasSVD
print("=== BiasSVD ===")
model_bias = BiasSVD(n_users, n_items, n_factors=50, global_mean=global_mean)
train_model(model_bias, train_loader, test_loader, epochs=50, device=device)
```

### 8.7 为 Top-K 推荐生成

```python
def recommend_topk(model, user_idx, item_indices, k=10, device='cpu'):
    """为指定用户推荐 Top-K 未评分物品"""
    model.eval()
    user_tensor = torch.tensor([user_idx] * len(item_indices), device=device)
    item_tensor = torch.tensor(item_indices, device=device)

    with torch.no_grad():
        scores = model(user_tensor, item_tensor).cpu().numpy()

    # 排除已评分物品可在外部处理，这里直接返回评分最高的 K 个
    topk_idx = np.argsort(scores)[::-1][:k]
    return topk_idx, scores[topk_idx]
```

---

## 总结

```
协同过滤 → 邻居聚类（User/Item-based CF）
          → 隐向量分解（FunkSVD → BiasSVD → SVD++ → TimeSVD++）
          → 特征交互（FM → FFM）
          → 神经网络（NeuMF）
```

**演进路线**：从简单邻居 → 线性低秩分解 → 带偏置/时间/隐式反馈的精细分解 → 特征交互泛化 → 深度神经网络。

**工程实践要点**：
- 记忆型 CF 适合**可解释性**要求高的场景
- 矩阵分解适合**离线批量**推荐，效果好
- 冷启动必须额外兜底（Popularity / Content-based）
- 评估用 NDCG@K 更贴合用户实际体验
