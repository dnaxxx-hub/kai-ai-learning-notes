# 第7课：编辑距离 + 最大子数组和 (Kadane)

> 日期: 2026-05-08
> 代码: `dp_edit_kadane.py`
> 图: `figures/edit_distance_table.png`, `figures/kadane_max_subarray.png`

## 编辑距离 (Levenshtein Distance)

### DP公式
```
dp[i][j] = 编辑 a[:i] → b[:j] 的最小代价
    
dp[i][0] = i,  dp[0][j] = j
dp[i][j] = min(
    dp[i-1][j] + 1,        # 删除 a[i-1]
    dp[i][j-1] + 1,        # 插入 b[j-1]  
    dp[i-1][j-1] + cost,   # 替换 (a[i]==b[j]?0:1)
)
```

### 操作回溯
EQ(保留) → DE(删除) → IN(插入) → RE(替换)

### 示例
```
kitten → sitting = 3
  替换k→s → 保留it → 替换e→i → 保留n → 插入g

horse → ros = 3  
  替换h→r → 保留o → 删除r → 保留s → 删除e
```

## 最大子数组和 (Kadane)

### 算法
```
max_ending = max_sofar = arr[0]
for i in 1..n-1:
    max_ending = max(arr[i], max_ending + arr[i])  # 重新开始 or 接续
    max_sofar = max(max_sofar, max_ending)
```

### 性质
- O(N) 时间, O(1) 空间
- 可追踪起始/结束位置
- 环形变体: max(普通Kadane, 总和 - 最小子数组和)

## 运行结果

编辑距离:
- kitten→sitting: 3 ✓
- horse→ros: 3 ✓
- intention→execution: 5 ✓

最大子数组:
- [-2,1,-3,4,-1,2,1,-5,4] → 6 (索引3-6, [4,-1,2,1]) ✓
- 全负数 → 取最大元素 ✓
- 环形 [5,-3,5] → 10 (跨越首尾: 5+5) ✓

性能: Kadane 对 N=1000 仅 0.0ms (线性秒杀DP二次方)
