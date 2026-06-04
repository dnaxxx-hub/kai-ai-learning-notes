# 推荐系统 #4：深度学习推荐模型

> 从 FM 到深度模型的演进，理解了这些模型才算真正入门推荐系统。

---

## 1. 从 FM 到深度模型的演进路线

```
FM / FFM（线性+二阶交叉）
    ↓
Wide & Deep（记忆+泛化，DNN骨架）
    ↓
DeepFM（FM替代LR，端到端）
DCN（显式高阶交叉网络）
    ↓
DIN / DIEN（用户行为序列建模）
DIEN（兴趣演化）
    ↓
Multi-task（MMoE / PLE）
    ↓
工程部署（Serving / A/B实验）
```

核心思路：从 **特征工程** 到 **自动特征学习**，从 **静态表征** 到 **动态建模**。

---

## 2. Wide & Deep Learning（Google 2016）

论文：*Wide & Deep Learning for Recommender Systems* (Google Play 商店推荐)

### 核心思想

将模型拆为两个部分，各司其职：

```
                   输出（CTR预估）
                  /           \
             Wide            Deep
         (记忆能力)        (泛化能力)
         LR + 交叉特征    DNN + 特征Embedding
              |                |
           原始特征         原始特征
```

### Wide 部分：记忆能力

- 就是一个 **线性模型（LR）**
- 核心是**人工构建的交叉特征**：`φ(x) = ∏ x_i^{c_{ki}}`
- 典型做法：用户已安装App × 当前曝光App → 交叉特征
- **优点**：善于记忆**高频共现模式**（"装了微信的用户容易装QQ"）
- **局限**：只能记忆见过的组合，不会"举一反三"

### Deep 部分：泛化能力

- 标准的 DNN（通常是3层左右 MLP）
- 输入是特征的 Embedding 向量拼接
- **优点**：学习到特征的深层表示，对**未出现过的特征组合**也能泛化
- **局限**：容易过拟合稀疏特征，对低频组合记忆不牢

### 为什么结合？

| | Wide（记忆） | Deep（泛化） |
|---|---|---|
| 熟悉模式 | ✅ 精准记忆 | ❌ 可能泛化跑偏 |
| 新组合 | ❌ 无法处理 | ✅ 泛化预测 |
| 稀疏特征 | ✅ 有用 | ❌ 容易过拟合 |
| 密集特征 | ❌ 表达能力弱 | ✅ 自动学习 |

**A/B 测试效果**：Wide & Deep 相比纯 Wide（LR）或纯 Deep 均有显著提升，Google Play 的 App 下载量提升 3.9%。

### 工程要点

- Wide 和 Deep 部分**共享特征输入**（但处理方式不同）
- Wide 用原始 one-hot，Deep 用 Embedding
- 联合训练：Wide 部分用 FTRL（带 L1 正则），Deep 部分用 AdaGrad / Adam

---

## 3. DeepFM（华为 2017）

论文：*DeepFM: A Factorization-Machine based Neural Network for CTR Prediction*

### 改进点

```
Wide & Deep:
LR ------------ 需要人工交叉特征
DNN

DeepFM:
FM ------------ 自动二阶交叉，不需要特征工程
DNN
```

### FM 替代 LR

- FM 自动做二阶特征交叉：`y = w0 + Σwixi + ΣΣ<vi, vj>xixj`
- **不需要人工构建交叉特征**
- 对稀疏特征天然友好（通过隐向量内积学习交叉）

### 共享 Embedding 层

```
原始特征
    ↓
 [Embedding Layer] ← 共享
   ↗        ↘
 FM Layer    DNN Layer
   ↓           ↓
 [输出层] ← 拼接
    ↓
   CTR
```

- FM 和 DNN 用的是**同一套 Embedding**，端到端训练
- FM 负责二阶交叉（低阶模式），DNN 负责高阶非线性
- 相比 Wide & Deep：
  - **不需要特征工程**（FM 自动交叉）
  - **Embedding 共享**（参数更少，训练更充分）

### 评估

- 相比 Wide & Deep，DeepFM 在多个数据集上 AUC 更好
- 特别是**不需要人工特征工程**这一点，在工业界极具吸引力

---

## 4. DCN（Deep & Cross Network）

论文：*Deep & Cross Network for Ad Click Predictions* (Google 2017)

### 问题

- DNN 学习高阶交叉**效率低**（需要大量参数）
- FM 只能到二阶交叉

### Cross Network：显式高阶交叉

核心公式（每一层）：

```
x_l+1 = x0 × (x_l^T × w_l) + b_l + x_l
       ↑        ↑             ↑     ↑
    原始输入  权重参数(标量)  bias  residual
```

关键洞察：
- `w_l` 是**标量**（shape: `[d]`，d 是特征维度），不是矩阵
- 每层只有 **2个参数**（w + b），极其轻量
- 通过多层叠加实现**任意阶显式交叉**

### Cross vs DNN

| | Cross Network | DNN |
|---|---|---|
| 参数效率 | 每层 O(d) | 每层 O(d²) |
| 交叉阶数 | 显式控制 | 隐式学习 |
| 可解释性 | 强 | 弱 |
| 非线性 | 弱（本质是线性交叉） | 强 |

### 整体架构

```
Input → Embedding → [Cross Network, DNN] → 拼接 → 输出
```

- Cross Network 负责显式特征交叉
- DNN 负责深层的非线性变换
- 两者互补

### DCN V2（改进版）

论文：*DCN V2: Improved Deep & Cross Network* (Google 2021)

改进：
1. **MoE（Mixture of Experts）**：多个 Cross 网络专家，门控融合
2. **Cross 层的矩阵变换**（从标量扩展到向量/矩阵，牺牲效率换能力）
3. 在超大规模推荐场景下 AUC 显著提升

```
DCN V2:
Input → Expert1(Cross) ─┐
         Expert2(Cross) ─┤→ Gate → 输出
         Expert3(Cross) ─┘
```

---

## 5. DIN（Deep Interest Network，阿里 2018）

论文：*Deep Interest Network for Click-Through Rate Prediction*

### 问题

传统方法把用户行为序列**简单 pooling**（SUM/AVG），丢失了信息：
- "用户看了手机、买了电脑、浏览了书" → 简单地加在一起
- 推荐"手机"时，"看手机"这条行为应该权重更高

### 核心思想：注意力机制

```
CTR输出
   ↑
[全连接层]
   ↑
[注意力池化] ← 候选物品（手机）
   ↑
[用户行为序列]（浏览手机、买电脑、看书）
```

### 注意力权重计算

```
attention_score = softmax(candidate_emb · history_emb_i)
user_interest = Σ attention_score_i × history_emb_i
```

- 候选物品（如手机）与每个历史物品做**内积**
- 内积越大 → 该历史行为与候选物品越相关 → 权重越高
- 最终用户兴趣 = 加权求和

### 局部激活单元（Local Activation Unit）

DIN 用的是**自适应权重**而不是固定权重：

```
[candidate_emb, history_emb_i, candidate_emb - history_emb_i, candidate_emb * history_emb_i]
    → [DNN] → attention_score_i
```

- 把候选物品和历史物品的**差、积**都作为输入
- DNN 学习出更精细的相关性得分

### 效果

- 阿里广告系统 AUC 提升（≈2% 相对提升）
- 对长序列行为建模尤其有效
- 注意力权重的**可解释性好**（可以展示"为什么推荐这个"）

---

## 6. DIEN（Deep Interest Evolution Network，阿里 2019）

论文：*Deep Interest Evolution Network for Click-Through Rate Prediction*

### 问题

DIN 的问题是：用户的兴趣是**动态变化**的，而不是简单加权：
- "用户先看了手机 → 买了手机 → 又在看手机壳"
- 兴趣在**演化**：手机 → 手机周边
- DIN 的注意力池化是静态的（不考虑时间顺序）

### 核心思想：GRU 建模兴趣演化

```
CTR输出
   ↑
[注意力层] ── 候选物品
   ↑
[GRU层] ← AUGRU 门控
   ↑
[行为序列]（按时间顺序）
```

### AUGRU（Attention Update GRU）

GRU 是标准的序列模型，DIEN 的改进是 AUGRU：

```
普通 GRU：  ht = GRU(ht-1, xt)
AUGRU：     ht = at * GRU(ht-1, xt) + (1-at) * ht-1
             ↑
         注意力权重（与候选物品相关）
```

- `at` 是候选物品与当前行为的相关性
- 注意力控制 GRU 的**更新门**
- 与候选物品无关的行为被抑制（信息不流入 GRU）

### DIN vs DIEN

| | DIN | DIEN |
|---|---|---|
| 时序建模 | ❌ 无 | ✅ GRU |
| 兴趣状态 | 静态加权 | 动态演化 |
| 序列信息 | 丢失 | 保留 |
| 效果 | 基线 | 更强 |

### 关键结论

用户的兴趣是 **evolve** 而非 **static** 的：
- 用户行为有明确的时间线
- 相邻行为之间有因果关系
- 兴趣演化路径和候选物品相关

---

## 7. Multi-task 推荐模型

### 为什么需要多任务？

推荐场景往往有多个目标：
- CTR（点击率）
- CVR（转化率）
- 停留时长
- 收藏/分享

传统方法：每个目标独立建模 → 浪费数据、模型间无关联

### 硬参数共享（Hard Sharing）

最朴素的多任务方法：
```
共享底层Embedding + 共享底层DNN
        ↙          ↘
     Task1 Head   Task2 Head
```

问题：**任务冲突**（task conflict）——CTR 和 CVR 的优化方向可能不同。

### MMoE（Multi-gate Mixture of Experts）

论文：*Modeling Task Relationships in Multi-task Learning* (Google 2018)

```
Input
   ↓
[Expert1] [Expert2] [Expert3] [Expert4]
   |   ↑    |    ↑    |   ↑    |
   +-- Gate1  +--- Gate2  ----+ 
        ↓           ↓
     Task1        Task2
```

核心思想：
- **多个 Expert**：每个 Expert 是一个小型网络
- **每个任务独立的 Gate**：不同任务学到如何组合 Expert
- 门控权重 = softmax(输入特征)

优点：
- 任务间共享 Expert 的能力
- 任务独有 Gate 解决任务冲突
- 参数灵活，适合任务数量不多的场景

### PLE（Progressive Layered Extraction）

论文：*Progressive Layered Extraction (PLE): A Novel Multi-Task Learning Model* (腾讯 2021)

进一步解决 MMoE 的问题：

```
Task1 Head      Task2 Head
    ↑               ↑
[Task1 Specific] [Task2 Specific]
    ↑               ↑
[     Shared Experts    ]  ← 多层渐进提取
    ↑               ↑
      [ 底层特征层 ]
```

核心改进：
1. **任务独有网络**：每个任务有自己的 Expert
2. **共享网络**：多层的、渐进式提取共享信息
3. **分层结构**：底层共享 → 高层分离

### 样本选择偏差（SSB）

多任务中最棘手的问题之一。

典型场景（CVR 预估）：
- CTR 模型在所有曝光样本上训练 ✅
- CVR 模型**只在点击样本上训练** ❌
- 线上推理时需要在所有曝光样本上预测

**问题**：训练分布 ≠ 预测分布（点击样本有偏）

**常用解法**：
1. **ESMM（Entire Space Multi-Task Model）**：在全样本空间建模，CTR × CVR = CTCVR
2. **Domain Adaptation**：将全量曝光作为源域，点击作为目标域做迁移
3. **采样修正**：逆倾向加权（IPW）

---

## 8. 排序模型的工程部署

### 特征 Pipeline

在线实时特征架构：

```
用户请求
   ↓
[特征获取层]
   ├─ 用户画像特征（HBase / Redis）
   ├─ 物品实时特征（Redis）
   ├─ 上下文特征（时间、设备等）
   └─ 实时行为特征（Flink流处理）
   ↓
[特征拼接 + 校验]
   ↓
[特征变换] → 归一化 / 离散化 / 交叉
   ↓
[模型推理]
   ↓
   排序结果
```

关键点：
- **实时性**：用户刚点击的物品要立刻反映在特征中
- **一致性**：训练时的特征分布要和上线一致（Feature Store 的重要性）
- **特征校验**：缺失值处理、异常值过滤

### 模型 Serving

| 框架 | 场景 | 特点 |
|---|---|---|
| TF Serving | TensorFlow 模型 | 成熟稳定，支持版本管理 |
| NVIDIA Triton | 多框架（TF/PyTorch/ONNX） | 高性能，GPU 优化 |
| 自研 C++ | 极致性能 | 灵活但开发成本高 |

部署方式：
```
模型导出（SavedModel / ONNX）
    ↓
模型存放（文件系统 / 对象存储 S3）
    ↓
模型加载到 Serving 进程
    ↓
暴露 gRPC / HTTP API
    ↓
上游排序服务调用
```

### 增量训练 vs 全量训练

| | 全量训练 | 增量训练 |
|---|---|---|
| 频率 | 每天/每周 | 每小时/实时 |
| 数据 | 全部历史数据 | 新数据 |
| 耗时 | 数小时 | 数分钟 |
| 效果 | 稳定 | 能快速适应分布变化 |

工业界做法：
- **全量训练**：每天凌晨跑一次，产出基线模型
- **增量训练**：基于基线模型，用新数据继续训练（warm-start）
- **在线学习**：实时更新，单条样本到达就训（FTRL 等）

### 在线 A/B 实验框架

```
[流量分配]
   /    \
  A组   B组
(控制组) (实验组)
   |      |
 老模型  新模型
   |      |
 指标对比（CTR / CVR / GMV）
```

关键设计：
1. **实验分层**：算法层、特征层、模型结构层互不干扰
2. **流量正交**：Hash 分桶保证用户一致性
3. **指标监控**：实时看板 + 统计显著性检验
4. **灰度放量**：1% → 5% → 20% → 50% → 全量
5. **回滚机制**：快速切回老版本

---

## 总结：模型演进脉络

```
特征交叉能力（DCN）          → 显式高阶交叉
         +
行为序列建模（DIN/DIEN）     → 兴趣动态建模
         +
多任务学习（MMoE/PLE）       → 多目标优化
         +
工程部署（Serving/A/B）      → 生产可用
```

推荐系统深度学习模型的演进，本质是**从特征工程走向自动学习**，**从静态建模走向动态建模**，**从单任务走向多任务**的过程。

---

## 参考资料

- Cheng et al. (2016) *Wide & Deep Learning for Recommender Systems*
- Guo et al. (2017) *DeepFM: A Factorization-Machine based Neural Network for CTR Prediction*
- Wang et al. (2017) *Deep & Cross Network for Ad Click Predictions*
- Zhou et al. (2018) *Deep Interest Network for Click-Through Rate Prediction*
- Zhou et al. (2019) *Deep Interest Evolution Network*
- Ma et al. (2018) *Modeling Task Relationships in Multi-task Learning (MMoE)*
- Tang et al. (2021) *Progressive Layered Extraction (PLE)*
- Wang et al. (2021) *DCN V2*
