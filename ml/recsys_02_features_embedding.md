# 推荐系统 #2：特征工程与 Embedding

## 目录
1. [推荐系统中的特征类型](#1-推荐系统中的特征类型)
2. [特征交叉（Feature Crossing）](#2-特征交叉feature-crossing)
3. [类别特征的 Embedding 化](#3-类别特征的-embedding-化)
4. [序列特征建模](#4-序列特征建模)
5. [多模态特征](#5-多模态特征)
6. [Embedding 训练方法](#6-embedding-训练方法)
7. [特征重要性分析](#7-特征重要性分析)
8. [工程实践](#8-工程实践)

---

## 1. 推荐系统中的特征类型

推荐系统的本质是**利用特征预测用户与物品之间的匹配度**。特征的质量直接决定了模型能力的上限。

### 1.1 用户特征（User Features）

描述用户画像的静态与动态属性。

| 特征类别 | 示例 | 特征类型 | 说明 |
|---------|------|---------|------|
| 人口属性 | 年龄、性别、职业、学历 | 数值/类别 | 基础画像，长期稳定 |
| 地域 | 国家、省份、城市、LBS | 类别/层级 | 用于地域化推荐 |
| 设备 | 手机品牌、型号、操作系统、网络类型 | 类别 | 影响 App 行为模式 |
| 用户分层 | 新/老、VIP/普通、活跃度分桶 | 类别 | 策略差异化基础 |
| 兴趣标签 | L1/L2/L3 兴趣分类 | 多值类别 | 从行为中间接推断 |

```python
# 用户特征加工示例
user_features = {
    "user_id": 12345,
    "gender": "male",
    "age_bucket": "25-34",
    "city": "北京",
    "device_brand": "Apple",
    "os": "iOS 17",
    "network_type": "WiFi",
    "user_level": "vip_silver",
    "interest_tags": ["科技", "游戏", "运动"]
}
```

### 1.2 物品特征（Item Features）

描述待推荐对象的属性。

| 特征类别 | 示例 | 说明 |
|---------|------|------|
| 类目体系 | L1类目「电子产品」→ L2「手机」→ L3「旗舰机」 | 层级类目，天然树结构 |
| 标签 | 多值标签如「热销」「新品」「限时折扣」 | 稀疏高维特征 |
| 价格 | 价格绝对值、价格分桶、价格相对排名 | 数值特征，常做分桶 |
| 品牌 | 品牌 ID、品牌偏好度 | 品牌效应显著 |
| 内容属性 | 标题、描述、图文/视频 | 文本/多模态特征 |
| 统计属性 | 点击率、转化率、收藏数（需谨慎防数据泄露） | 时效性强 |

### 1.3 上下文特征（Context Features）

描述推荐发生时的场景信息。

| 特征类别 | 示例 | 说明 |
|---------|------|------|
| 时间 | 时段（早/中/晚）、星期几、是否节假日 | 用户行为有强时间模式 |
| 位置 | GPS、商圈、室内/室外 | 位置感知推荐 |
| 天气 | 晴/雨/雪、温度、空气质量 | 影响品类偏好（如雨天外卖↑） |
| 设备状态 | 电量、屏幕亮度、横竖屏 | 微妙但有时有用 |
| 网络 | WiFi/4G/5G、网络质量 | 影响视频/图片加载策略 |

**时段特征的核心价值**：用户在不同时间段的意图截然不同。
```
06:00-09:00 → 早间新闻/早餐推荐
12:00-14:00 → 午间休闲/外卖
18:00-22:00 → 娱乐消费/购物高峰
22:00-02:00 → 深夜内容（直播/短视频）
```

### 1.4 行为特征（Behavior Features）

**推荐系统中信息密度最高的特征。**

| 特征类别 | 示例 | 说明 |
|---------|------|------|
| 统计行为 | 近7天点击数、近30天购买数、平均停留时长 | 统计聚合 |
| 序列行为 | 最近 50 个点击物品的 ID 序列 | 保留时序信息 |
| 实时行为 | 当前 Session 内的点击流 | 短时意图捕捉 |
| 跨域行为 | 其他业务线的行为（短视频→商城） | 扩展用户画像 |
| 负向行为 | 跳过、负反馈、举报 | 隐式负信号 |

**行为特征的时效性分层**：
```
实时行为（秒级） → Session行为（分钟级） → 短期行为（天级） → 长期行为（月/年级）
```

---

## 2. 特征交叉（Feature Crossing）

### 2.1 为什么需要特征交叉？

**单一特征是线性可分的，交叉特征才能表达"条件依赖关系"。**

举例：不交叉时，模型只能学到「男性」「学生」各自的独立效应；交叉出 `性别=男 & 职业=学生` 才能表达"男大学生更爱打游戏"这个非线性关系。

### 2.2 二阶交叉（Paried Crossing）

最简单的交叉方式：人工构造 `(f_i, f_j)` 组合。

```
原始特征：
  age_bucket=25-34   ×   gender=male   →   (25-34_male)
  city=北京           ×   hour=12        →   (北京_12点)
  category=手机       ×   os=Android     →   (手机_Android)
```

**工程挑战**：交叉后的特征空间呈指数级增长。
- 1000 个城市 × 24 个时段 → 24000 个交叉组合
- 实践中需要添加频率过滤：只保留出现次数 > 阈值的组合

### 2.3 高阶交叉

**FM / FFM**：隐式建模高阶特征交叉，无需人工构造全部组合。
- FM：每个特征学习一个隐向量 v_i，交叉权重 = v_i · v_j
- DeepFM / xDeepNet：用 DNN + 显式交叉网络自动学习高阶交叉

**DCN（Deep & Cross Network）**：Cross Network 层实现显式高阶交叉。
```
x_{l+1} = x_0 · (W_l · x_l + b_l) + x_l
```
每一层都在统计原始输入 x_0 与当前层 x_l 的交叉，自动学到任意阶交叉。

### 2.4 工程实践建议

```yaml
交叉策略：
  人工先验: 基于业务理解构造高价值交叉（如性别×品类）
  模型自动: FM/DCN 自动学习剩余交叉
  频率控制: 低频交叉合并到 "其它" 桶
  稀疏性: 交叉后特征维度爆炸时，使用 Embedding 化
```

---

## 3. 类别特征的 Embedding 化

### 3.1 为什么需要 Embedding？

One-Hot 编码的问题：
- 维度爆炸：百万级物品 ID 输入无法直接训练
- 缺乏语义关联：item_1 和 item_2 编码正交，无法表达相似性
- 泛化能力差：新物品无任何统计信息

Embedding 将高维稀疏向量映射到低维稠密空间（d ~ 8~256），且相似物品的向量距离近。

### 3.2 Hash 技巧（Feature Hashing / Hash Trick）

**原理**：将类别特征通过 Hash 函数映射到固定大小的桶。

```python
def hash_trick(feature, num_buckets=100000):
    """Hash trick: 将任意数量的类别映射到固定数量桶"""
    bucket = hash(feature) % num_buckets
    return bucket
```

**优点**：
- 预定义输出维度，无需维护映射表
- 适合分布式训练中未知词表大小的情况
- 内存可控

**缺点**：
- **Hash 冲突**：不同特征映射到同一桶时互相污染
- 不可解释，冲突后无法区分

**效果排序**：完整 Embedding Table > Hash Trick（适当桶数） > One-Hot

### 3.3 OOV（Out-Of-Vocabulary）处理

OOV 问题：训练时未见过的特征值（新物品、新用户）在推理时出现。

**常见解决方案**：

| 方法 | 描述 | 适用场景 |
|------|------|---------|
| **UNK Token** | 设一个统一 OOV 向量，所有未知特征共享 | 简单通用 |
| **默认向量** | 初始化一个固定的默认向量（全 0 或正态随机） | 快速实现 |
| **特征细化** | OOV 时回退到高层级（物品 → 类目 → 品牌） | 层级类目体系 |
| **多级 Hash** | 同时映射到多个 Hash 表，取 concat/avg | Tradeoff |
| **Side Information** | OOV 时用内容特征（文本/图像）生成的 Embedding | 冷启动 |

**工业界的做法**：层级回退（Hierarchical Lookup）是最实用的方案。
```python
def get_item_embedding(item_id, embedding_table, category_table):
    if item_id in embedding_table:
        return embedding_table[item_id]          # 精确命中
    elif item_id in category_table:
        return category_table[item_id]            # 回退到类目
    else:
        return default_embedding                 # UNK
```

### 3.4 Embedding 维度选择经验法则

没有绝对标准，但有业界共识：

**经验法则 1：4√n ~ 100√n**
- n 为类别数（词汇表大小）
- 类别较少时（百级）：d = 8~32
- 类别中等时（万级）：d = 32~128
- 类别海量时（百万级）：d = 64~256

**经验法则 2：按特征重要性分配维度**
- 重要特征（如 item_id）：大维度
- 次要特征（如 hour_of_day）：小维度

**经验法则 3：**`d ≈ log₂(n)` **作为下限**
- 过小的维度会限制模型表达能力
- Google Play 推荐系统经验：item_id 使用 256 维

```yaml
维度参考：
  user_id:          64~128
  item_id:          64~256
  category_l3:      16~32
  gender:            4~8
  hour_of_day:       4~8
  city:              8~16
```

---

## 4. 序列特征建模

用户行为序列包含最丰富的**用户动态兴趣**信号。

### 4.1 用户行为序列的 Pooling 方法

**简单方法（无参数）**：

```python
# 用户历史行为序列: [item_1, item_2, ..., item_n]
# 对应 Embedding: [e_1, e_2, ..., e_n]

def mean_pooling(embeddings):
    return np.mean(embeddings, axis=0)        # 平均池化

def sum_pooling(embeddings):
    return np.sum(embeddings, axis=0)         # 求和池化

def max_pooling(embeddings):
    return np.max(embeddings, axis=0)         # 最大池化
```

**问题**：
- 丢失序列顺序信息
- 等权对待所有行为（购买和点击一样重要）
- 无法处理兴趣漂移

### 4.2 DIN（Deep Interest Network）

**核心思想**：不同物品对用户历史行为的不同部分关注度不同。

> 给用户推荐"手机"时，他的历史里"手机购买记录"远比"零食购买记录"重要。

**注意力机制**：
```
α_i = Softmax(MLP([e_item; e_history_i; e_item - e_history_i; e_item * e_history_i]))
user_interest_vector = Σ α_i · e_history_i
```

**关键差异**：DIN 的注意力权重是**输入相关的**（query-dependent），不同的候选物品会激活不同的历史行为子集。

**图示**：
```
Candidate Item ──→ e_item
                      ↓
History Items → [e_1, e_2, ..., e_n]
                      ↓
          注意力权重计算（MLP）
                      ↓
          加权求和 → user_interest_vector
```

**DIEN vs DIN**：DIN 是静态的，DIEN 是动态的（加入了时序演化建模，见下文）。

### 4.3 DIEN（Deep Interest Evolution Network）

**核心思想**：用户兴趣不仅在品类间变化，还在**时间维度上演化**。

DIEN 比 DIN 新增两个模块：

**模块一：兴趣抽取层（Interest Extractor）**
- 使用 GRU 对行为序列建模，捕获行为间的依赖性
- 辅助损失（Auxiliary Loss）：用 GRU 隐状态预测下一时刻的行为

```python
# GRU 兴趣抽取
h_t = GRU(e_t, h_{t-1})       # 隐状态表达当前兴趣

# 辅助损失：让隐状态预测下一个行为
loss_aux = -log(σ(h_t · e_{t+1})) - log(1 - σ(h_t · e_{negative}))
```

**模块二：兴趣演化层（Interest Evolving）**
- 注意力更新的 GRU（AUGRU）：GRU 的更新门由注意力分数控制
- 兴趣随着时间平滑演化，而不是突变

```
AUGRU 更新公式：
  u_t' = α_t · u_t          # 注意力加权的更新门
  h_t = (1 - u_t') · h_{t-1} + u_t' · h̃_t  # 新隐状态
```

### 4.4 SIM（Search-based Interest Model）

**核心思想**：当用户行为序列非常长（几千到上万）时，DIN/DIEN 受限于计算能力无法处理全部历史。SIM 采用**先搜索后建模**的两阶段方案。

**阶段一：硬搜索（Hard Search / GSU）**
- 从用户的长序列中检索出与候选物品相关的 subset
- 检索条件：相同类目、相同店铺、关键词匹配
- 将万级序列压缩到百级

**阶段二：软搜索（Soft Search / ESU）**
- 对检索出的子序列做注意力计算（类似 DIN）
- 可以叠加更复杂的模型（如 Transformer）

```yaml
SIM 流程：
  [用户完整序列]  ── GSU: 类目匹配/SIM  ──→  [相关子序列（~100）]
                                                    ↓
                                        ESU: 注意力/Transformer
                                                    ↓
                                         用户兴趣向量
```

**SIM 的价值**：
- 突破了 DIN/DIEN 的序列长度限制（< 100）
- 可以捕捉到"一个月前买的"远距离兴趣
- 在电商推荐中效果提升显著（淘宝公开报告 +7%+ CTR）

**变体**：ETA（End-to-end Target Attention），用 LSH 近似替代精确检索，进一步加速。

---

## 5. 多模态特征

### 5.1 图像特征提取

物品图片中包含丰富的视觉信号（款式、颜色、材质等）。

**预训练 CNN 提取**：
```yaml
常用模型:
  ResNet-50:      经典，平衡精度与速度
  EfficientNet:   更 Efficient，SOTA 之一
  ViT:            Vision Transformer，需要更多数据
  CLIP:           图文对比预训练，零样本能力强
  
提取方式:
  1. 取全连接层前一层的特征向量（~2048维）
  2. 通过 MLP 压缩到目标维度（~128维）
  3. 可在训练中 Fine-tune 或 Freeze
```

**实践注意**：
- 图像特征一般离线预计算，存储到特征库
- Fine-tune 场景需要在训练框架中实现图像前向
- 时效性强的物品（如新闻）图片变化快，需要实时抽取

### 5.2 文本特征提取

**传统方法**：
```yaml
TF-IDF / BM25:   稀疏向量，可解释性强，但维度过高
Word2Vec / FastText: 词级别 Embedding，平均/加权得句向量
```

**深度方法**：
```yaml
BERT:            句级 Embedding，语义理解最强但计算量大
Sentence-BERT:   优化后的句向量，适合大规模相似度计算
GloVe:           全局词向量，比 Word2Vec 更好地利用统计信息
```

**文本特征在推荐中的典型应用**：
- 物品标题/描述的语义 Embedding（冷启动物品使用）
- 用户评论的情感分析特征
- 搜索 query 的语义向量匹配

### 5.3 特征对齐（Mapping to Shared Semantic Space）

**为什么需要对**：图像特征（ResNet 输出）和文本特征（BERT 输出）来自不同模型，不共享语义空间，无法直接比较。

**对齐方法**：

| 方法 | 描述 | 代表工作 |
|------|------|---------|
| **MLP 映射** | 各自过 MLP 到同一维度后拼接 | 常见 baseline |
| **对比学习** | 图文对做 Contrastive Loss，拉近正样例 | CLIP, ALIGN |
| **跨模态注意力** | Transformer 交叉注意力融合 | M6, ALBEF |
| **多模态双塔** | 图像塔+文本塔共享底层语义 | 多模态双塔 |

```python
# 最简单的对齐：各自的映射 MLP
vision_embed = vision_mlp(vit_output)       # 图像 → 128维
text_embed   = text_mlp(bert_output)         # 文本 → 128维
fused_feature = concat([vision_embed,        # 拼接 → 256维
                        text_embed,
                        vision_embed * text_embed])  # 加交叉
```

---

## 6. Embedding 训练方法

### 6.1 Item2Vec

**核心思想**：将 NLP 中 Word2Vec 的 Skip-gram 思想应用到物品序列。

**Word2Vec vs Item2Vec**：

| | Word2Vec | Item2Vec |
|--|---------|----------|
| 语料 | 句子中的词序列 | 用户 Session 中的物品序列 |
| 上下文 | 滑动窗口内相邻词 | 同一 Session 内的相邻物品 |
| 目标 | 预测上下文词 | 预测上下文物品 |

**训练方式**：
```python
# Session [手机, 耳机, 充电宝, 手机壳]
# 正样本：(手机, 耳机), (手机, 充电宝), (耳机, 充电宝), ...
# 负样本：随机选取

loss = -log(σ(v_j · v_i)) - Σ log(σ(-v_k · v_i))  # 负采样 NCE loss
```

**价值**：
- 无监督训练，不需要 CTR 标注
- 学到物品的相似语义（经常一起购买的就相近）
- 可作为下游 CTR 模型的冷启动初始化

### 6.2 Graph Embedding

**场景**：用户-物品交互天然构成二部图，Item2Vec 只考虑了序列共现，没能利用高阶关联。

**Node2Vec**：
```yaml
流程:
  1. 构建物品相似图（共现为边，权重为共现频率）
  2. 在图上做随机游走（BFS/DFS 混合策略）
  3. 对游走序列跑 Word2Vec → 得到物品 Embedding

游走策略参数:
  p（Return param）: 控制返回上一节点的概率（偏向 BFS）
  q（In-out param）: 控制探索远处节点的概率（偏向 DFS）

BFS 倾向 → 结构性相似（功能相似物品）
DFS 倾向 → 同质性相似（同一社区/风格物品）
```

**EGES（Enhanced Graph Embedding with Side Information）**：
- 阿里巴巴提出的改进版
- 不仅使用 item_id，还融合 side information（品牌、类目、店铺）
- 每个 item 的最终 Embedding 是多个 Embedding 加权和

```
e_item = Σ λ_i · e_side_i     # λ_i 为可学习的注意力权重
```

### 6.3 多任务联合训练 Embedding

**核心思想**：Item2Vec 和 Graph Embedding 是**独立训练**的 Embedding，可能不适用于 CTR 任务的最终目标。更好的方式是将 Embedding 作为主模型的一部分**端到端训练**。

**多任务学习框架（MMOE / PLE）**：
```yaml
共享底部: 
  Embedding 层被多个任务共享
  
专家网络:
  Shared Experts + Task-specific Experts
  Gating Network 为不同任务动态选择专家

任务塔:
  Task A: CTR（点击率）
  Task B: CVR（转化率） 
  Task C: 时长（停留时长回归）
```

**共享 Embedding 的好处**：
- 稀疏任务（如转化）可以从丰富任务（如点击）中借力
- 减少过拟合
- 统一物品 Embedding，降低存储和维护成本

**对比总结**：

| 方法 | 监督信号 | 语义丰富度 | 端到端 | 适用场景 |
|------|---------|-----------|--------|---------|
| Item2Vec | 共现 | ⭐⭐⭐ | ❌ | 冷启动初始化 |
| Node2Vec | 图结构 | ⭐⭐⭐⭐ | ❌ | 关系丰富的场景 |
| EGES | 图+属性 | ⭐⭐⭐⭐⭐ | ❌ | 冷启动物品 |
| 多任务联合 | CTR/CVR | ⭐⭐⭐⭐⭐ | ✅ | 主模型 Embedding |

---

## 7. 特征重要性分析

### 7.1 为什么需要特征重要性

- **特征筛选**：删除无用特征，降低维度和过拟合
- **排除冗余**：发现高度相关特征，减少计算量
- **模型简化**：小而快的模型更适合在线推理
- **业务理解**：发现哪些因素最影响推荐结果

### 7.2 SHAP（SHapley Additive exPlanations）

基于博弈论的 Shapley Value，为每个特征分配贡献度。

**核心公式**：
```
ϕ_i = Σ (|S|!(|F|-|S|-1)! / |F|!) × (f_{S∪{i}}(x) - f_S(x))
```
其中 S 为不包含特征 i 的特征子集，对所有可能的子集求和。

**SHAP 优缺点**：
```yaml
优点:
  - 一致性：特征重要性的排序可靠
  - 可解释性强：每个样本都有 SHAP 解释
  - 支持 Tree 模型和深度学习

缺点:
  - 计算量大（指数级子集），需用近似方法
  - 深度模型上近似精度有折扣
  - 高维特征（百万级 ID）上实用困难
```

**实用方法**：
- 使用 `KernelSHAP`（近似版）
- 对 Tree 模型使用 `TreeSHAP`（高效）
- 只对 Top-N 重要特征做深入分析

### 7.3 GBDT 特征重要性（Internal Importance）

树模型天然提供特征重要性：

**基于分裂次数**（Split Count）：
```python
importance_i = feature_i 被选为分裂特征的次数
```

**基于信息增益**（Gain）：
```python
importance_i = feature_i 所有分裂节点带来的信息增益之和
# 信息增益 = Gini 不纯度减少 / MSE 减少
```

**基于覆盖度**（Cover）：
```python
importance_i = feature_i 分裂点覆盖的样本数之和
```

**工程建议**：
```yaml
特征筛选流程:
  1. 训练 LightGBM/XGBoost baseline 模型
  2. 基于 Gain Importance 排序特征
  3. 保留累计贡献 > 95% 的特征
  4. 删除重要性为 0 的特征
  5. 遍历删除 Top-k 不重要特征，观察模型效果
```

### 7.4 嵌入特征的重要性评估

ID 类 Embedding 特征难以直接用 SHAP 分析（百万级维度）。

**间接评估方法**：
1. **消融实验**：去掉 Embedding 特征后看指标下降幅度
2. **激活分析**：可视化 Embedding 空间，看同类物品是否聚簇
3. **最近邻分析**：某个物品的 Top-K 最近邻是否语义合理

---

## 8. 工程实践

### 8.1 特征存储

在线推理系统对特征存储的要求：**低延迟（< 10ms）、高吞吐、支持批量读取**。

| 存储方案 | 延迟 | 适用场景 | 典型用法 |
|---------|------|---------|---------|
| **Redis** | ~1ms | 实时特征/ID Embedding | 用户 Embedding、排序特征 |
| **LevelDB** | ~100μs | SSD 本地的 Embedding 查找 | Embedding Table |
| **RocksDB** | ~100μs | 大容量 Embedding 存储 | 百万级物品 Embedding |
| **Pika** | ~1ms | 类 Redis 大容量存储 | 大数据量的备选 |
| **HBase** | ~5ms | 海量用户特征 | 用户画像宽表 |

**工业界常见架构**：
```
离线训练 → Embedding 导出 → Param Server / Redis Cluster → 在线推理
                                    ↑
实时计算 → 增量更新 Embedding ───────┘
```

**Redis 缓存的 Embedding 读取优化**：
```python
# 批量读取（Pipeline）
pipe = redis.pipeline()
for item_id in item_ids:
    pipe.get(f"item_emb:{item_id}")
embeddings = [parse_embedding(r) for r in pipe.execute()]

# 预序列化为 Protocol Buffers / FlatBuffers 减少反序列化开销
```

### 8.2 实时特征计算

**实时特征的计算链路**：
```
用户行为事件 → Kafka → Flink/Spark Streaming → 特征写入 Redis → 在线服务读取
```

**典型实时特征**：
```yaml
实时统计特征:
  - 过去 1h/6h/24h 用户点击数
  - 过去 1h 最常点击的类目 Top-3
  - 当前 Session 停留时长
  - 最近一次点击时间戳（时间差）

实时序列特征:
  - 当前 Session 的最后 20 个 item_id
  - 实时更新的用户即时兴趣向量
```

**Flink 实时特征计算示例**：
```sql
-- Flink SQL 实时统计
INSERT INTO redis_sink
SELECT
    user_id,
    COUNT(*) AS click_1h,
    COUNT(DISTINCT item_id) AS distinct_item_1h
FROM click_events
WHERE event_time >= NOW() - INTERVAL '1' HOUR
GROUP BY user_id
```

### 8.3 特征校验

特征错误是线上效果波动的常见原因，必须建立特征校验机制。

**校验维度**：

| 校验项 | 检查方式 | 报警阈值 |
|--------|---------|---------|
| 缺失率 | 特征 N/A 占比 | > 5% 报警 |
| 异常值 | 数值特征是否超出合理范围 | > 3σ 或固定阈值 |
| 分布漂移 | PSI（Population Stability Index） | PSI > 0.1 告警 |
| ID 覆盖率 | 实时特征在 Redis 中的命中率 | < 95% 告警 |
| 时序一致性 | 最近 7 天特征均值变化 | 突变 > 10% 报警 |
| 空值逻辑 | 应不为空的字段出现 null | 任何 null 报警 |

**PSI 计算**：
```python
def calculate_psi(expected, actual, buckets=10):
    """衡量特征分布是否漂移"""
    eps = 1e-10
    psi = 0
    for i in range(buckets):
        p_i = expected[i] / sum(expected) + eps
        q_i = actual[i] / sum(actual) + eps
        psi += (q_i - p_i) * np.log(q_i / p_i)
    return psi  # PSI < 0.1 稳定, 0.1-0.2 需关注, > 0.2 严重漂移
```

**特征管线的最佳实践**：
```yaml
上线前:
  - 特征生产与模型训练的离线对账（特征值一致）
  - 在线 Serving 的特征提取逻辑加单元测试

上线后:
  - 持续监控特征分布（PSI + 缺失率）
  - A/B 实验的特征一致性校验
  - 特征回放（Replay）验证历史一致性

异常处理:
  - Redis 不可用 → 回退到本地缓存 / 默认值
  - 特征缺失 → 用均值/众数填充，打标 missing 位
  - 分布漂移 → 重新训练模型或调整特征
```

### 8.4 特征管线的完整流程

```
离线训练管道                         在线推理管道
                                     ↓
原始日志 → 特征工程 → 样本 → 训练    用户请求 → 实时特征 → 排序模型
                ↓                              ↑
         特征存储（HDFS/Abase） ←────────── 特征读取
                ↓                              ↑
         特征元数据管理 ←───────────────── 特征校验
```

**特征版本管理**：每次特征变更都需要版本号，确保训练和推理使用相同版本的特征逻辑。

---

## 总结与关键思维

1. **特征优先**：在工业界，好的特征工程>模型结构的差异。花 70% 的时间做特征工程。
2. **交叉为王**：特征交叉是模型非线性表达的核心来源，FM/DCN 自动交叉 + 人工高阶交叉两手抓。
3. **Embedding 是桥梁**：将稀疏 ID 映射到稠密语义空间，是深度推荐系统的基础设施。
4. **序列特征 > 统计特征**：用户行为序列包含时序信息和顺序关系，比单纯统计特征信息量大得多。
5. **冷启动靠内容特征**：新物品/新用户没有行为，必须依靠图文/文本特征做 Zero-shot 推荐。
6. **特征治理是硬功夫**：特征校验、监控、版本管理这些工程基础设施决定了模型的持续迭代效率。

---

## 参考资料

- Zhou et al. "Deep Interest Network for Click-Through Rate Prediction" (DIN, KDD 2018)
- Zhou et al. "Deep Interest Evolution Network for Click-Through Rate Prediction" (DIEN, AAAI 2019)
- Pi et al. "Search-based User Interest Modeling with Lifelong Sequential Behavior Data" (SIM, CIKM 2020)
- Wang et al. "Billion-scale Commodity Embedding for E-commerce Recommendation in Alibaba" (EGES, KDD 2018)
- Cheng et al. "Wide & Deep Learning for Recommender Systems" (Google, DLRS 2016)
- Wang et al. "Deep & Cross Network for Ad Click Predictions" (DCN, ADKDD 2017)
- Lundberg & Lee. "A Unified Approach to Interpreting Model Predictions" (SHAP, NeurIPS 2017)
- Mikolov et al. "Distributed Representations of Words and Phrases and their Compositionality" (Word2Vec, NeurIPS 2013)
