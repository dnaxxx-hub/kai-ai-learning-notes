# 第6课：动态规划 — LCS + LIS

> 日期: 2026-05-08
> 代码: `dp_sequence.py`
> 图: `figures/lcs_table.png`, `figures/lis_visualization.png`

## 最长公共子序列 (LCS)

### DP公式
```
         ┌ 0,                      if i=0 or j=0
dp[i][j] =├ dp[i-1][j-1] + 1,       if a[i]=b[j]
         └ max(dp[i-1][j], dp[i][j-1]), else
```

### 时空
- 完整表: O(N²) 时间, O(N²) 空间
- 只求长度: O(N²) 时间, O(min(N,M)) 空间 (滚动数组)

## 最长递增子序列 (LIS)

### 贪心+二分 (O(N log N))
- `tails[k]` = 长度为 k+1 的递增子序列的最小末尾值
- 对每个元素 x: 二分查找第一个 >= x 的位置替换
- 路径重建: 额外记录 predecessor 数组

### 注意
- 严格递增: `bisect_left` (不允许相等)
- 非严格递增: `bisect_right` (允许相等)

## 运行结果

```
── LCS ──
  A=ABCBDAB, B=BDCAB
  LCS=BCAB (长度=4)
  LCS(AGGTAB,GXTXAYB)=4 ✓
  LCS(AAAA,AAAA)=4 ✓
  LCS(ABC,DEF)=0 ✓

── LIS ──
  [10,9,2,5,3,7,101,18] → 长度4, 序列[2,3,7,18]
  [7,7,7,7,7] → 长度1, 序列[7] (严格递增)
  [0,1,0,3,2,3] → 长度4, 序列[0,1,2,3]

── 性能 ──
  LCS N=1000: 150ms (二次方)
  LIS N=1000: 0.3ms (对数)
```
