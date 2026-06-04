# 图论与网络分析

> 从拉普拉斯矩阵到股票相关性网络 — 图论在量化中的实战

---

## 1. 图的基本表示

```python
import numpy as np
from scipy.sparse import csgraph

# 图的三种矩阵表示
# 邻接矩阵 A：A[i,j] = 1 如果 i,j 相连
# 度矩阵 D：D[i,i] = sum(A[i,:])
# 拉普拉斯矩阵 L = D - A

# 示例：5个节点的简单图
n = 5
A = np.array([
    [0, 1, 1, 0, 0],
    [1, 0, 1, 1, 0],
    [1, 1, 0, 0, 1],
    [0, 1, 0, 0, 1],
    [0, 0, 1, 1, 0]
])

D = np.diag(A.sum(axis=1))
L = D - A

print("拉普拉斯矩阵:\n", L)

# 拉普拉斯矩阵的特征值
eigvals = np.linalg.eigvalsh(L)
print("\n拉普拉斯特征值:", np.sort(eigvals))
print("第二个最小特征值(代数连通度):", np.sort(eigvals)[1])
# 代数连通度 > 0 表示图连通，值越大表示图越难分割
```

## 2. 谱聚类

```python
from scipy.cluster.vq import kmeans2

def spectral_clustering(A, k=2):
    """谱聚类：用拉普拉斯矩阵的特征向量做聚类"""
    n = A.shape[0]
    
    # 度矩阵
    D = np.diag(A.sum(axis=1))
    
    # 归一化拉普拉斯 L_norm = D^(-1/2) * L * D^(-1/2)
    D_inv_sqrt = np.diag(1.0 / np.sqrt(np.diag(D)))
    L_norm = D_inv_sqrt @ (D - A) @ D_inv_sqrt
    
    # 取最小的k个特征值对应的特征向量
    eigvals, eigvecs = np.linalg.eigh(L_norm)
    X = eigvecs[:, :k]
    
    # 归一化每行
    X = X / np.linalg.norm(X, axis=1, keepdims=True)
    
    # 对行向量做k-means
    _, labels = kmeans2(X, k, minit='points')
    return labels

# 测试
np.random.seed(42)
# 生成两个簇的数据
n_per_cluster = 20

# 簇内连接强，簇间连接弱
A_cluster = np.zeros((40, 40))
A_cluster[:20, :20] = np.random.rand(20, 20) > 0.3  # 簇1内部 70%连接
A_cluster[20:, 20:] = np.random.rand(20, 20) > 0.3  # 簇2内部 70%连接
A_cluster[:20, 20:] = np.random.rand(20, 20) > 0.95  # 簇间 5%连接
A_cluster[20:, :20] = A_cluster[:20, 20:]  # 对称

A_cluster = A_cluster.astype(float)
A_cluster[A_cluster < 0.5] = 0  # 二值化

labels_pred = spectral_clustering(A_cluster, 2)
accuracy = max(
    np.mean(labels_pred[:20] == 0) + np.mean(labels_pred[20:] == 1),
    np.mean(labels_pred[:20] == 1) + np.mean(labels_pred[20:] == 0)
) / 2
print(f"谱聚类准确率: {accuracy:.2%}")
```

## 3. PageRank

```python
def pagerank(A, alpha=0.85, max_iter=100, tol=1e-6):
    """PageRank算法"""
    n = A.shape[0]
    
    # 列归一化（概率转移矩阵）
    col_sums = A.sum(axis=0)
    P = A / col_sums[np.newaxis, :]
    P[:, col_sums == 0] = 1.0 / n  # 悬空节点
    
    # 初始均匀分布
    r = np.ones(n) / n
    
    for i in range(max_iter):
        r_new = alpha * P @ r + (1 - alpha) * np.ones(n) / n
        if np.linalg.norm(r_new - r) < tol:
            break
        r = r_new
    
    return r

# 测试：简单的网页链接结构
# A -> B, A -> C, B -> C, C -> A
links = np.array([
    [0, 1, 0, 0],  # A
    [0, 0, 1, 0],  # B
    [1, 0, 0, 1],  # C
    [0, 0, 0, 0]   # D（悬空节点）
]).T.astype(float)  # A[i,j] = 1 表示 j -> i

scores = pagerank(links)
pages = ['A', 'B', 'C', 'D']
sorted_pages = sorted(zip(pages, scores), key=lambda x: -x[1])
print("PageRank结果:")
for page, score in sorted_pages:
    print(f"  {page}: {score:.4f}")
```

## 4. 股票相关性网络

```python
def stock_correlation_network(returns_df, threshold=0.3):
    """从收益率数据构建股票相关性网络"""
    import pandas as pd
    
    # 相关系数矩阵
    corr = returns_df.corr()
    n = len(corr)
    
    # 阈值过滤：只保留 |corr| > threshold 的连接
    A = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            if abs(corr.iloc[i, j]) > threshold:
                A[i, j] = corr.iloc[i, j]
                A[j, i] = corr.iloc[i, j]
    
    return A, corr

def find_communities(A, n_clusters=3):
    """用谱聚类在股票网络中找到行业聚类"""
    labels = spectral_clustering(A, n_clusters)
    
    # 对每个聚类，找中心节点（度最大的）
    degrees = A.sum(axis=1)
    centers = []
    for c in range(n_clusters):
        mask = labels == c
        if mask.sum() > 0:
            center = np.argmax(degrees * mask)
            centers.append(center)
    
    return labels, centers

# 模拟股票数据
np.random.seed(42)
n_stocks = 30
n_days = 500

# 3个行业，每个行业10只股票
sectors = np.repeat([0, 1, 2], 10)
industry_factor = np.random.normal(0, 0.5, (n_days, 3))
returns = np.zeros((n_days, n_stocks))

for i in range(n_stocks):
    sector = sectors[i]
    # 行业因子 + 个股特有噪声
    returns[:, i] = industry_factor[:, sector] + np.random.normal(0, 1, n_days)

df = pd.DataFrame(returns)
A, corr = stock_correlation_network(df, threshold=0.2)

labels_pred, centers = find_communities(A, 3)
# 评估聚类效果
from sklearn.metrics import adjusted_rand_score
ari = adjusted_rand_score(sectors, labels_pred)
print(f"行业聚类 ARI: {ari:.4f} (1=完美, 0=随机)")
```

## 5. 最小生成树

```python
from scipy.sparse.csgraph import minimum_spanning_tree

def plot_mst(corr_matrix, stock_names):
    """从相关系数构建MST：保留最强相关性，去掉冗余边"""
    n = len(stock_names)
    
    # 距离矩阵：距离 = sqrt(2*(1-corr))，使得距离满足三角不等式
    dist = np.sqrt(2 * (1 - corr_matrix))
    np.fill_diagonal(dist, 0)
    
    # 最小生成树
    mst = minimum_spanning_tree(dist).toarray()
    
    # 获取边列表
    edges = []
    for i in range(n):
        for j in range(i+1, n):
            if mst[i, j] > 0 or mst[j, i] > 0:
                edges.append((stock_names[i], stock_names[j], 
                             1 - dist[i, j]**2 / 2))  # 恢复相关系数
    
    # 按相关性排序
    edges.sort(key=lambda x: -x[2])
    print("MST top 5 strongest edges:")
    for edge in edges[:5]:
        print(f"  {edge[0]} - {edge[1]}: ρ={edge[2]:.3f}")
    
    return mst

# 测试
stock_names = [f"Stock_{i}" for i in range(30)]
mst = plot_mst(corr.values, stock_names)
print(f"\nMST 边数: {(mst > 0).sum()} (vs 全连接 {30*29/2:.0f} 条)")
```

## 6. 因果发现

```python
# 格兰杰因果检验：X是否有助于预测Y
from statsmodels.tsa.stattools import grangercausalitytests

def granger_causality_network(returns_df, max_lag=5):
    """构建格兰杰因果网络"""
    n = returns_df.shape[1]
    causal_matrix = np.zeros((n, n))
    
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            try:
                test_result = grangercausalitytests(
                    returns_df.iloc[:, [j, i]],  # 测试 j 对 i 的因果
                    maxlag=max_lag, verbose=False
                )
                # 使用最小p值
                min_p = min(test_result[lag][0]['ssr_ftest'][1] 
                           for lag in range(1, max_lag+1))
                causal_matrix[j, i] = -np.log(min_p + 1e-10)  # 因果强度
            except:
                causal_matrix[j, i] = 0
    
    return causal_matrix

# 测试
causal_net = granger_causality_network(df, max_lag=3)
strongest = np.unravel_index(causal_net.argmax(), causal_net.shape)
print(f"最强因果: Stock_{strongest[0]} → Stock_{strongest[1]}, "
      f"强度={causal_net[strongest]:.2f}")
```

## 7. 随机游走与图传播

```python
def random_walk_on_graph(A, start_node, steps=100):
    """图上随机游走"""
    n = A.shape[0]
    
    # 概率转移矩阵
    P = A / A.sum(axis=1, keepdims=True)
    
    node = start_node
    visit_count = np.zeros(n)
    
    for _ in range(steps):
        visit_count[node] += 1
        node = np.random.choice(n, p=P[node])
    
    return visit_count / steps

# 用随机游走找"核心"节点
def find_central_nodes(A, n_central=3):
    n = A.shape[0]
    centrality = np.zeros(n)
    
    for start in range(n):
        visit_dist = random_walk_on_graph(A, start, steps=1000)
        centrality += visit_dist
    
    centrality /= n
    top_nodes = np.argsort(centrality)[::-1][:n_central]
    return top_nodes, centrality

central_nodes, centrality = find_central_nodes(A_cluster)
print(f"Top central nodes: {central_nodes}")
print(f"Centrality scores: {centrality[central_nodes]}")
```

## 在量化实战中的应用

```python
# 1. 用谱聚类发现未被标注的相关行业组
# 2. 用MST构建投资组合：避免过度集中于高度相关的股票
# 3. 用随机游走做资产配置：核心-卫星策略
# 4. 用因果图做风险传播分析

def portfolio_diversification_by_clustering(returns_df, n_clusters=3):
    """用谱聚类辅助分散投资"""
    import pandas as pd
    
    A, _ = stock_correlation_network(returns_df, threshold=0.2)
    labels = spectral_clustering(A, n_clusters)
    
    portfolio = []
    for c in range(n_clusters):
        cluster_stocks = np.where(labels == c)[0]
        # 从每个簇选一个代表（夏普率最高的）
        best_sharpe = -np.inf
        best_stock = None
        for s in cluster_stocks:
            r = returns_df.iloc[:, s].values
            sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else -np.inf
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_stock = s
        
        if best_stock is not None:
            portfolio.append(best_stock)
            print(f"Cluster {c}: Stock_{best_stock}, Sharpe={best_sharpe:.2f}")
    
    # 等权重构建组合
    n_assets = len(portfolio)
    weights = np.ones(n_assets) / n_assets
    port_returns = returns_df.iloc[:, portfolio] @ weights
    port_sharpe = port_returns.mean() / port_returns.std() * np.sqrt(252)
    
    print(f"Portfolio Sharpe: {port_sharpe:.2f}")
    return portfolio

print("\n谱聚类应用于投资组合分散化的核心逻辑:")
print("- 先用相关性矩阵构建图")
print("- 谱聚类发现行业/风格分组")
print("- 从每组选最优股票")
print("- 等权重配置避免集中风险")
```
