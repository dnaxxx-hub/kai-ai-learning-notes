# 第8课：随机化与近似算法

## 1. Fisher-Yates 洗牌算法

### 原理
从数组末尾向前遍历，每次从 [0, i] 范围内随机选一个元素与当前位置交换。

```python
def fisher_yates(arr):
    import random
    for i in range(len(arr) - 1, 0, -1):
        j = random.randint(0, i)
        arr[i], arr[j] = arr[j], arr[i]
```

### 正确性证明
- 每个元素出现在每个位置的概率均为 1/n
- 第 i 步时，选中位置 j (0 ≤ j ≤ i) 的概率为 1/(i+1)
- 最终排列均匀分布在 n! 种可能中

### 复杂度
- 时间：O(n)，单次遍历
- 空间：O(1) in-place

---

## 2. 蓄水池采样（Reservoir Sampling）

### 原理
从 N 个元素中等概率抽取 k 个，N 未知或不可一次性加载。

```python
def reservoir_sampling(stream, k):
    reservoir = []
    for i, item in enumerate(stream):
        if i < k:
            reservoir.append(item)
        else:
            j = random.randint(0, i)
            if j < k:
                reservoir[j] = item
    return reservoir
```

### 正确性证明
- 最终每个元素留在蓄水池中的概率为 k/n
- 归纳法证明：处理第 i 个元素时，前 i 个元素被选中的概率为 k/i

### 复杂度
- 时间：O(N)，每个元素常数操作
- 空间：O(k)

### 应用场景
- 大规模数据流随机抽样
- 日志文件随机采样
- 网络流量分析

---

## 3. Bloom Filter

### 原理
用一个 m 位的位数组和 k 个独立的哈希函数判断元素是否在集合中。插入时将 k 个哈希位置为 1；查询时若所有 k 位均为 1 则"可能在集合中"，否则"一定不在"。

### 假阳性率分析
$$
P(\text{false positive}) \approx \left(1 - e^{-\frac{kn}{m}}\right)^k
$$

其中：
- m：位数组大小
- n：插入元素数量
- k：哈希函数个数

### 最优哈希函数数量
$$
k_{opt} = \frac{m}{n} \ln 2
$$

### 优缺点
- ✅ 空间效率极高，远低于传统集合存储
- ✅ 插入和查询均为 O(k) 时间
- ❌ 不支持删除元素（Counting BF 可支持）
- ❌ 存在假阳性（可控制概率）
- ✅ 无假阴性

### 应用场景
- 缓存穿透防护
- 垃圾邮件过滤
- 网页爬虫 URL 去重
- 数据库查询优化

---

## 4. MinHash

### 原理
用于近似估计两个集合的 Jaccard 相似度：$J(A,B) = \frac{|A \cap B|}{|A \cup B|}$

### 算法
1. 对集合中的每个元素计算 k 个哈希函数的值
2. 取每个哈希函数在集合上的最小值，得到 k 维签名向量
3. 两个集合的 Jaccard 相似度 ≈ 签名向量中相等位置的占比

### 性质
- $P(\min(h(A)) = \min(h(B))) = J(A, B)$
- 用 k 个哈希函数可显著降低估计方差，方差约为 $\frac{J(1-J)}{k}$

### 复杂度
- 构建签名：O(k|S|)
- 相似度比较：O(k)

---

## 5. SimHash

### 原理
用于大规模文本去重和相似度检测。

### 算法步骤
1. 初始化 f 维权重向量 V = [0, 0, ..., 0]
2. 对每个特征（词/ngram）计算 f 位哈希
3. 若某位为 1，则 V 的该位 + 权重；否则 V 的该位 - 权重
4. 最终指纹：V[i] > 0 → 1，否则 0

### 性质
- 将高维特征映射到 f 位二进制指纹
- **海明距离**与文本相似度相关
- 支持"多对多"相似度计算（不同于 MinHash 的"集合对"）

### 复杂度
- 计算指纹：O(n·f)，n为特征数
- 相似度比较：O(f)（海明距离）

---

## 6. 算法对比总结

| 算法 | 输入 | 输出 | 时间复杂度 | 空间复杂度 | 应用场景 |
|------|------|------|------------|------------|----------|
| Fisher-Yates | 数组 | 随机排列 | O(n) | O(1) | 游戏抽卡、随机排序 |
| Reservoir Sampling | 数据流 | 随机样本 | O(N) | O(k) | 数据流采样 |
| Bloom Filter | 元素集合 | 存在性判断 | O(k) 查/插 | O(m) 位 | 去重、缓存 |
| MinHash | 集合对 | Jaccard估计 | O(k\|S\|) 构建 | O(k) 签名 | 文档去重推荐 |
| SimHash | 文本 | 二进制指纹 | O(n·f) | O(f) 指纹 | 大规模文本去重 |

## 7. 概率分析总结

- **Fisher-Yates**：确定性随机，1/n 均匀分布
- **Reservoir Sampling**：K/n 概率被选中
- **Bloom Filter**：假阳性率 $(1-e^{-kn/m})^k$，可精确控制
- **MinHash**：期望 = J(A,B)，方差 ≈ J(1-J)/k
- **SimHash**：海明距离与余弦相似度正相关
