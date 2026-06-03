# GNN 第1课：图神经网络基础

> 前置知识：ML基础（线性代数、矩阵运算、神经网络）

## 1. 什么是图？— 非欧几里得数据

**图 G = (V, E)** 由节点集 V 和边集 E 组成。
- 节点（Node/Vertex）：实体（用户、原子、股票）
- 边（Edge）：关系（好友、化学键、相关性）

### 与结构化数据的区别

| 类型 | 数据形式 | 卷积适用性 |
|------|---------|-----------|
| 图像 (CNN) | 2D 欧几里得网格（像素有固定位置） | ✅ 完美匹配 |
| 文本 (RNN/Transformer) | 1D 序列（字有前后依赖） | ✅ 顺序匹配 |
| 图 (GNN) | 任意拓扑（节点邻居数不等） | ❌ 传统卷积用不了 |

### 图的数学表示

- **邻接矩阵 A**：n×n 矩阵，A[i][j]=1 表示 i→j 有边
- **度矩阵 D**：对角阵，D[i][i]=sum(A[i])
- **拉普拉斯矩阵 L = D - A**：图傅里叶变换的基础
- **归一化拉普拉斯 L_norm = I - D^{-0.5} A D^{-0.5}**

## 2. 消息传递范式（Message Passing）

GNN 的核心思想：每个节点通过**聚合邻居信息**来更新自身表示。

```
h_v^(k+1) = UPDATE(h_v^(k), AGGREGATE({h_u^(k) for u in N(v)}))
```

其中：
- h_v^(k) — 节点 v 在第 k 层的特征向量
- N(v) — v 的所有邻居节点
- AGGREGATE — 聚合函数（sum/mean/max/attention）
- UPDATE — 更新函数（MLP/GRU）

## 3. 三种基本 GNN 架构

### GCN（图卷积网络）
AGGREGATE = mean(邻居特征) → 线性变换 → ReLU
```python
def gcn_layer(H, A, W):
    # H: (n_nodes, d_in), A: (n_nodes, n_nodes), W: (d_in, d_out)
    D_inv = np.diag(1.0 / np.sqrt(np.sum(A, axis=1)))
    A_hat = D_inv @ A @ D_inv  # 对称归一化
    return np.maximum(A_hat @ H @ W, 0)  # ReLU
```

### GAT（图注意力网络）
AGGREGATE = 注意力加权（学习每条边的权重）
```python
def gat_layer(H, A, W_a, W_b):
    # 注意力系数 = softmax(LeakyReLU(H@Wa || H@Wb))
    e = LeakyReLU(H @ W_a + H @ W_b.T)  # 边注意力分数
    alpha = softmax(e * A)  # 只在有边的位置上做softmax
    return alpha @ H
```

### GraphSAGE（采样聚合）
AGGREGATE = 采样固定数量邻居 → 拼接 → 线性变换
```python
def sage_layer(H, edges, W1, W2, k=5):
    sampled_neighbors = random_sample_neighbors(edges, k)
    neighbor_feat = mean_by_index(H, sampled_neighbors)
    return ReLU(concat(H, neighbor_feat) @ W)
```

## 4. GNN vs 传统 DL 对比

| | 传统NN | GNN |
|--|--------|-----|
| 输入 | 固定维度向量 | 图结构 + 节点特征 |
| 不变性 | 平移不变 | 置换不变（节点重排不影响） |
| 感受野 | 固定核大小 | 取决于层数（k层=聚合k跳邻居） |
| 计算 | 批量矩阵运算 | 稀疏矩阵操作 |

## 5. 为什么要叠加多层？

- 1层 GNN：只看直接邻居
- 2层 GNN：看2跳邻居（朋友的朋友）
- k层 GNN：看k跳邻居
- ⚠️ 太深会过平滑（所有节点表示趋向一致）

## 6. 核心设计选择

1. **AGGREGATE 函数**：sum(保持基数信息) / mean(归一化) / max(找最关键邻居) / attention(可学习的加权)
2. **UPDATE 函数**：简单MLP / GRU(序列化多层) / JumpingKnowledge(跨层连接)
3. **Loss 类型**：节点分类(cross-entropy) / 链接预测(BPR loss) / 图分类(图readout + CE)

---

**下一篇**: GCN 深度实现（频域+空域两派）
