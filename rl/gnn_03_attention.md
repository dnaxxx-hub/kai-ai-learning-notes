# GNN 第3课：GAT — 图注意力网络

> 论文: Velickovic et al., "Graph Attention Networks", ICLR 2018

## 1. 为什么需要注意力？

GCN 的聚合是**固定的**（对称归一化平均），但现实中：
- 有些邻居更重要（朋友 vs 陌生人）
- 重要性因**节点而异**（不同节点的"重要邻居"不同）
- 需要**动态学习**权重而非静态归一化

## 2. GAT 核心公式

### 注意力系数计算

```
e_ij = LeakyReLU(a^T · [W·h_i || W·h_j])
α_ij = softmax_j(e_ij) = exp(e_ij) / Σ_k∈N(i) exp(e_ik)
```

其中：
- h_i / h_j — 节点特征
- W — 共享的线性变换矩阵
- a — 可学习的注意力向量（attention parameter）
- || — 向量拼接
- N(i) — 节点 i 的邻居集合
- LeakyReLU — 负斜率为 0.2 的 ReLU

### 更新公式

```
h_i' = σ( Σ_j∈N(i) α_ij · W · h_j )
```

## 3. 多头注意力

GAT 用 **多头注意力（Multi-Head Attention）** 增强稳定性：

```
h_i' = ||_{k=1..K} σ( Σ_j∈N(i) α_ij^k · W^k · h_j )
```

最后拼接 K 个头（如果输出维度不够，用平均代替拼接）

## 4. 纯 NumPy 实现

```python
import numpy as np

class GATLayer:
    def __init__(self, in_dim, out_dim, n_heads=4, concat=True):
        self.n_heads = n_heads
        self.concat = concat
        
        # 每个头的线性变换 + 注意力向量
        std = np.sqrt(2.0 / (in_dim + out_dim))
        self.W = np.random.randn(n_heads, in_dim, out_dim) * std
        self.a = np.random.randn(n_heads, 2 * out_dim) * std
        
        # 最终输出维度
        self.out_dim = out_dim * n_heads if concat else out_dim
    
    def forward(self, H, A):
        """
        H: (N, d_in) — 节点特征
        A: (N, N) — 邻接矩阵（二值，含自环）
        """
        N = H.shape[0]
        outputs = []
        
        for head in range(self.n_heads):
            # 1. 线性变换
            Wh = H @ self.W[head]  # (N, d_out)
            
            # 2. 计算每对节点的注意力分数
            # a^T · [Wh_i || Wh_j]
            # 技巧：Wh_i @ a_left + Wh_j @ a_right
            a_left = self.a[head, :self.out_dim]
            a_right = self.a[head, self.out_dim:]
            
            e = Wh @ a_left + (Wh @ a_right)[:, None]  # (N, N)
            e = np.maximum(e, 0.2 * e)  # LeakyReLU
            
            # 3. 掩码 — 只保留有边的注意力
            e = e - 1e9 * (1 - A)  # 无边处设为 -inf
            
            # 4. Softmax 归一化
            e_max = np.max(e, axis=1, keepdims=True)
            exp = np.exp(e - e_max)
            alpha = exp / (np.sum(exp, axis=1, keepdims=True) + 1e-10)
            
            # 5. 加权聚合
            out = alpha @ Wh  # (N, d_out)
            out = np.maximum(out, 0)  # ELU 近似
            
            outputs.append(out)
        
        # 6. 多头合并
        if self.concat:
            return np.concatenate(outputs, axis=1)  # (N, d_out * n_heads)
        else:
            return np.mean(outputs, axis=0)  # (N, d_out)
```

## 5. 两层 GAT 模型

```python
class GATClassifier:
    def __init__(self, in_dim, hidden=8, n_heads=8, n_classes=7):
        self.layer1 = GATLayer(in_dim, hidden, n_heads, concat=True)
        self.layer2 = GATLayer(hidden * n_heads, n_classes, 1, concat=False)
    
    def forward(self, X, A):
        H = self.layer1.forward(X, A)
        H = np.maximum(H, 0)  # ELU
        # Dropout
        if self.training:
            mask = np.random.binomial(1, 0.4, H.shape)
            H = H * mask / 0.6
        out = self.layer2.forward(H, A)
        exp = np.exp(out - np.max(out, axis=1, keepdims=True))
        return exp / np.sum(exp, axis=1, keepdims=True)
```

## 6. GCN vs GAT 对比

| 特性 | GCN | GAT |
|------|-----|-----|
| 邻居权重 | 固定（度归一化） | 可学习（注意力） |
| 参数数 | O(d_in·d_out) | O(K·d_in·d_out + 2K·d_out) |
| 计算复杂度 | O(N·d·C) | O(N·d·C + E·d) |
| Inductive 学习 | ❌ (需要全图拉氏矩阵) | ✅ (只依赖邻居特征) |
| 有向图 | 难处理 | 天然支持 |
| 不同权重邻居 | ❌ 平等对待 | ✅ 区分重要性 |

## 7. 实际经验

1. **头数选择**：8头是经典配置，4头对小图也够用
2. **Dropout**：训练时强烈推荐（特别在边级注意力上）
3. **负斜率**：LeakyReLU 的 0.2 是论文中的默认值，一般不用调
4. **大图问题**：GAT 计算所有节点对的注意力，O(N²) 在十万级图上不可行

---

**下一篇**: GNN 实战应用（推荐系统/量化/分子）
