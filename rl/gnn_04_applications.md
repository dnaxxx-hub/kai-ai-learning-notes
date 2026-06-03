# GNN 第4课：GNN 应用场景

## 1. 推荐系统 — GraphSAGE + PinSage

**问题**：十亿级用户×十亿级商品的关系图预测

**PinSage（Pinterest 2018）**：
- 基于 GraphSAGE 的大规模推荐系统
- 核心思路：在商品关系图上做随机游走，采样邻居，聚合特征

```python
class PinSageLayer:
    def __init__(self, in_dim, out_dim):
        self.W1 = np.random.randn(in_dim, out_dim) * 0.1
        self.W2 = np.random.randn(in_dim, out_dim) * 0.1
    
    def forward(self, h_node, h_neighbors):
        """
        h_node: (1, d) — 目标节点
        h_neighbors: (k, d) — k个采样邻居
        """
        # 聚合邻居（mean + max 拼接）
        h_mean = np.mean(h_neighbors, axis=0)
        h_max = np.max(h_neighbors, axis=0)
        h_agg = np.concatenate([h_mean, h_max])
        
        # 拼接自身特征
        h_cat = np.concatenate([h_node, h_agg.reshape(1, -1)], axis=1)
        return np.maximum(h_cat @ self.W1, 0) @ self.W2
```

**对比**：
| 方法 | 图建模能力 | 冷启动 | 计算成本 |
|------|-----------|--------|---------|
| 协同过滤 | ❌ (只看共现) | ❌ | 低 |
| PinSage | ✅ (关系传播) | ✅ (内容特征) | 中 |
| LightGCN | ✅ (简化GCN) | ✅ | 低 |

## 2. 量化交易 — 股票关系图

**问题**：股票间存在复杂关系（同行业/上下游/资金流），传统时序模型忽略关系

**解决方案**：构建股票行业关系图（G = 股票节点 + 行业边连接）

```python
def build_stock_graph(stocks, industry_dict):
    """
    构建股票关系图
    stocks: [(code, industry), ...]
    returns: 邻接矩阵 (N x N)
    """
    n = len(stocks)
    A = np.eye(n)  # 自环
    for i, (code1, ind1) in enumerate(stocks):
        for j, (code2, ind2) in enumerate(stocks):
            if i != j and ind1 == ind2:
                A[i, j] = 1  # 同行业相连
    return A

def gcn_stock_predictor(stock_features, industry_graph):
    """
    用 GCN 做股票维度因子聚合
    stock_features: (N, d) — 各股因子（动量/反转/质量等）
    industry_graph: (N, N) — 同行业关系
    """
    gcn1 = GCNLayer(d, 32)
    gcn2 = GCNLayer(32, 1)
    H = gcn1.forward(stock_features, industry_graph)
    return gcn2.forward(H, industry_graph)  # 各股预测
```

## 3. 分子/药物 — GIN + 分子图

**问题**：预测分子的化学性质（毒性/药性）

**解决方案**：原子=节点、化学键=边 → 图分类

```python
def molecular_readout(h_nodes):
    """
    图读出函数：从节点特征得到全图表示
    h_nodes: (N_atoms, d)
    """
    h_mean = np.mean(h_nodes, axis=0)
    h_max = np.max(h_nodes, axis=0)
    h_sum = np.sum(h_nodes, axis=0)
    return np.concatenate([h_mean, h_max, h_sum])

# GIN (Graph Isomorphism Network) 的核心洞见
# Sum 聚合 > Mean/ Max 聚合 — 因为 sum 能区分不同的多重集
```

## 4. 社交网络 — 节点分类

**问题**：预测用户属性（兴趣/身份/欺诈）

**做法**：构建用户关系图，GCN 做半监督节点分类

```python
def fraud_detection(transaction_graph):
    """
    基于交易图的欺诈检测
    特征: 交易金额/频率/时间模式
    已知欺诈节点很少 → 半监督正好适用
    """
    # 两层 GCN + 已知欺诈标签
    # 通过信息传播发现隐藏的可疑节点
    gcn = GCNClassifier(n_features=50, n_hidden=32, n_classes=2)
    gcn.train(X=features, A=transaction_graph, 
              Y=known_labels, train_mask=labeled_idx)
    return gcn.predict(all_features, transaction_graph)
```

## 5. 知识图谱 — R-GCN / CompGCN

**问题**：知识图谱有不同类型的关系边（"属于" "创作于" "位于"）

**R-GCN**：每种关系有独立的变换矩阵 W_r

```python
class RGCNLayer:
    def forward(self, H, relations):
        """
        H: (N, d) — 节点特征
        relations: {type: edges_list}
        """
        out = self.W_self @ H  # 自环变换
        for r_type, edges in relations.items():
            # 每种关系独立的 W
            neighbor_feat = H[edges[:, 1]]  # 取出邻居
            out += self.W[relation_type] @ neighbor_feat
        return ReLU(out)
```

## 6. 场景选择指南

| 场景图特点 | 推荐模型 | 原因 |
|-----------|---------|------|
| 同质、无特征差异 | GCN | 简单够用 |
| 邻居重要性不同 | GAT | 学习动态权重 |
| 超大图（十亿级） | GraphSAGE | 邻居采样可扩展 |
| 异构图（多种边） | R-GCN | 关系特定变换 |
| 图结构分辨 | GIN | 最强表达能力 |

---

**下一篇**: GNN 全路图规划
