# GNN 第2课：GCN — 图卷积网络深度实现

> 论文: Kipf & Welling, "Semi-Supervised Classification with Graph Convolutional Networks", ICLR 2017

## 1. GCN 核心公式

标准 GCN 层 (Kipf & Welling)：

```
H^(l+1) = σ( D̂^{-0.5} Â D̂^{-0.5} · H^(l) · W^(l) )
```

其中：
- Â = A + I — 加自环的邻接矩阵（节点也能看到自己）
- D̂ = diag(sum(Â)) — 度矩阵
- σ = ReLU（隐藏层）或 softmax（输出层）

## 2. 为什么加自环？

不加自环的话，节点只聚合邻居信息，丢失了自己的特征。加自环等于 "说一句话之前先想想自己知道什么"。

## 3. 对称归一化的意义

D̂^{-0.5} Â D̂^{-0.5} 的作用是**防止度数高的节点特征爆炸**。

直觉：
- 度数为1000的节点，不加归一化：聚合1000个邻居特征 → 值爆炸
- 对称归一化：每个邻居贡献 weighted by 1/sqrt(deg) → 尺度稳定

## 4. 纯 NumPy 实现

```python
import numpy as np
from scipy import sparse

class GCNLayer:
    def __init__(self, in_dim, out_dim, activation='relu'):
        # Xavier 初始化
        std = np.sqrt(2.0 / (in_dim + out_dim))
        self.W = np.random.randn(in_dim, out_dim) * std
        self.b = np.zeros(out_dim)
        self.act = activation
        self.cache = {}  # 存反向传播用
    
    def forward(self, H, A):
        """
        H: (N, d_in) — 节点特征
        A: (N, N) — 邻接矩阵（二值）
        """
        N = H.shape[0]
        
        # 1. 加自环
        A_hat = A + np.eye(N)
        
        # 2. 度矩阵的 -0.5 次方
        D = np.sum(A_hat, axis=1)
        D_inv_sqrt = np.diag(1.0 / np.sqrt(D + 1e-10))
        
        # 3. 对称归一化
        A_norm = D_inv_sqrt @ A_hat @ D_inv_sqrt
        
        # 4. 消息传递 + 线性变换
        out = A_norm @ H @ self.W + self.b
        
        # 5. 激活函数
        if self.act == 'relu':
            out = np.maximum(out, 0)
        elif self.act == 'softmax':
            exp = np.exp(out - np.max(out, axis=1, keepdims=True))
            out = exp / np.sum(exp, axis=1, keepdims=True)
        
        self.cache = (H, A_norm)
        return out
```

## 5. 两层 GCN 分类器（CorA 风格）

```python
class GCNClassifier:
    def __init__(self, n_features, n_hidden=16, n_classes=7):
        self.layer1 = GCNLayer(n_features, n_hidden, 'relu')
        self.layer2 = GCNLayer(n_hidden, n_classes, 'softmax')
        self.dropout_rate = 0.5
    
    def forward(self, X, A):
        H = self.layer1.forward(X, A)
        # Dropout（训练时）
        if self.training:
            mask = np.random.binomial(1, 1-self.dropout_rate, H.shape)
            H = H * mask / (1 - self.dropout_rate)
        out = self.layer2.forward(H, A)
        return out
    
    def predict(self, X, A):
        self.training = False
        return self.forward(X, A)
```

## 6. 训练（半监督 + 掩码）

GCN 开山论文的标志性贡献：**只用少量标注节点**就能学习。

```python
def train_gcn(gcn, X, A, Y, train_mask, lr=0.01, epochs=200):
    losses = []
    for epoch in range(epochs):
        gcn.training = True
        pred = gcn.forward(X, A)
        
        # 只计算标注节点的 loss
        loss = cross_entropy(pred[train_mask], Y[train_mask])
        
        # 梯度下降（简略版，实际用 Adam）
        grads = compute_gradients(loss, gcn)
        for layer in [gcn.layer1, gcn.layer2]:
            layer.W -= lr * grads[f'W_{id(layer)}']
        
        losses.append(loss)
    return losses
```

## 7. GCN 的局限

1. **Transductive 学习** — 训好的模型不能直接用在没见过的节点上，需要重新跑全图
2. **内存 O(n²)** — 邻接矩阵是 n×n，大图（百万节点）难搞
3. **过平滑** — 超过 3-4 层，所有节点趋同
4. **不能处理异构图** — 不同类型的节点/边需要扩展

## 8. 实际改进

- **GraphSAGE**（Hamilton 2017）— 采样邻居，inductive 学习
- **GIN**（Xu 2019）— 证明 sum 聚合比 mean/max 更能区分图结构
- **JK-Net**（Xu 2018）— 跨层连接缓解过平滑
- **ClusterGCN**（Chiang 2019）— 图分割解决大图内存问题

---

**下一步**: GAT — 为什么注意力机制让图学习更强
