# Bloom Filter V2 Enhanced Practice Notes

## 项目

- 目录：`projects/bloom_filter_v2/`
- 文件：`bloom_filter_v2.py` + `test_bloom_filter_v2.py`

## 实现内容

### 1. 基础布隆过滤器 (BloomFilter)
- 64-bit 整型数组存储位，支持任意容量
- 双哈希 SHA256 生成 k 个位置
- 支持容量/假阳性率参数自动计算最优 k 和 m

### 2. 计数布隆过滤器 (CountingBloomFilter)
- uint16 (`array('H')`) 计数器替代位数组
- `add()` 增加计数，`remove()` 减少计数
- 防止减到负数（先检查 `contains`）

### 3. 可扩展布隆过滤器 (ScalableBloomFilter)
- Bloomlet 层列表，每层容量按 `scaling_factor` 递增
- 填充 >75% 时自动添加新层
- `contains` 查询所有层

### 4. 布谷鸟过滤器 (CuckooFilter)
- 指纹 + 双桶哈希
- 每个桶 4 个位置
- 支持 `insert/search/delete` O(1)
- 冲突时 kicking（最多 500 次尝试）

### 5. 分区布隆过滤器 (PartitionedBloomFilter)
- k 个独立子数组，每个子数组对应一个哈希函数
- 独立哈希，适合 SIMD 优化

### 6. 布隆过滤器运算
- `union` / `intersect` / `jaccard` / `estimate_cardinality`

### 7. 统一接口
- `BloomFilterABC` 抽象基类
- `add(item)` / `contains(item)` / `remove(item)`（可选）
- `__len__()` / `info()` / `__contains__`

## 测试结果: 15/15 ✅

| # | 测试 | 状态 |
|---|------|------|
| 1 | 基础布隆 add/contains | ✅ |
| 2 | 假阳性率 < 1% (实测 0.02%) | ✅ |
| 3 | 计数布隆 add/remove/contains | ✅ |
| 4 | 计数布隆防负数 | ✅ |
| 5 | 可扩展自动扩容 (3 layers) | ✅ |
| 6 | 可扩展大量数据 (5000 items, 4 layers) | ✅ |
| 7 | 布谷鸟插入/查找/删除 | ✅ |
| 8 | 布谷鸟删除后查找 | ✅ |
| 9 | 分区布隆过滤 | ✅ |
| 10 | union 合并 | ✅ |
| 11 | intersect 交集 | ✅ |
| 12 | jaccard 相似度 (~0.36 vs 真值 0.33) | ✅ |
| 13 | 基数估计 (误差 0.03%) | ✅ |
| 14 | 大规模测试 (100k 元素) | ✅ |
| 15 | 空过滤器正确性 | ✅ |

## 关键知识点

1. **计数布隆**用 `array('H')` 比 `[0]*n` 节省 8x 内存
2. **可扩展布隆**的 tightening_ratio 逐层降低假阳性率
3. **布谷鸟过滤器**指纹碰撞影响假阳性率，16-bit 指纹 ≈ 1/65536
4. **基数估计**公式: n ≈ -m/k * ln(1 - X/m)

## 同步路径

- Source: `C:\Users\Admin\.openclaw\workspace\projects\bloom_filter_v2\`
- Dest: `D:\OpenClaw\projects\bloom_filter_v2\`
