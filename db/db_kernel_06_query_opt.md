# 数据库内核第6课：查询优化

> 日期：2026-05-11 | 实践代码：`code/db_kernel_06_query_opt.py`

---

## 一、优化器流程

```
SQL → Parser → Binder → Rewriter → Optimizer → Executor
                (AST)  (逻辑计划)   (物理计划)
```

### 优化器输入/输出
- **输入**：逻辑计划（Logical Plan），如 JOIN、SELECT、PROJECT
- **输出**：物理计划（Physical Plan），如 HashJoin、IndexScan、Sort

---

## 二、规则优化（RBO）

基于启发式规则的优化，不需要统计信息：

| 规则 | 示例 |
|------|------|
| 谓词下推 | Filter 下推到 Scan 之前 |
| 投影消除 | 去掉不必要的列 |
| 连接消除 | 主键完全在另一表中时可消除 |
| 子查询上提 | 将 EXISTS 相关的子查询转为 Semi-Join |
| 常量折叠 | WHERE 1=1 消除 |
| 外连接转内连接 | 当 NULL 被过滤时 |

---

## 三、成本优化（CBO）

### 3.1 统计信息

CBO 依赖的元数据：

| 统计量 | 含义 | 用途 |
|--------|------|------|
| Row Count | 行数 | 基础 |
| Distinct Count | 不同值数 (NDV) | 等值选择性 = 1/NDV |
| Null Count | NULL 数 | WHERE IS NULL |
| Min/Max | 极值 | 范围选择性 |
| Histogram | 分布直方图 | 非均匀分布估计 |

### 3.2 直方图

```
桶1: 18-23    [*******] 120人
桶2: 23-28    [********] 150人
桶3: 28-33    [****]     80人
桶4: 33-38    [***********] 200人
...
```

支持**等宽**（等距分割）和**等高**（等频分割，更精确）。

### 3.3 基数估计

基数估计的准确度直接影响 Join 顺序选择：

```
SELECT * FROM users WHERE age > 30
  → 估计行数 = users.row_count * (1 - (30-min)/(max-min))
  → 但实际可能均匀分布，用直方图更精确
```

---

## 四、Join Order 枚举

### 4.1 DPccp 算法

动态规划 + 连通互补对（Connected Complements）：

```
for size = 2 to n:
    for 每个 size 的子集 S:
        for 每个 S 的 proper 子集 L (R = S - L):
            cost(S) = min(cost(L) + cost(R) + join_cost(L,R))
```

### 4.2 复杂度

| 表数 | 搜索空间 |
|------|----------|
| n=5 | 168 种 |
| n=8 | 76,440 种 |
| n=10 | 17.6M 种 |

实用限制：
- 大部分 CBO 限制在 n ≤ 12
- 超出后使用贪心/遗传算法

---

## 五、成本模型

### 5.1 成本组成

```
Total Cost = CPU Cost + I/O Cost + Network Cost
CPU Cost  = rows × cpu_cost_per_row
I/O Cost  = pages_read × seq_io_cost + random_reads × random_io_cost
```

### 5.2 各操作成本

| 操作 | 成本公式 |
|------|----------|
| Seq Scan | pages × seq_io_cost |
| Index Scan | matched_rows × (random_io_cost + cpu_cost) |
| Hash Join | build_rows + probe_rows（CPU） |
| Sort-Merge Join | sort(L) + sort(R) + merge |
| Nested Loop | |L| × |R| × 匹配代价 |

---

## 六、实践代码

`db_kernel_06_query_opt.py` 包含：

| 模块 | 内容 |
|------|------|
| `TableStats` | 统计信息：行数/NDV/选择性 |
| `Histogram` | 等宽直方图 + 范围估计 |
| `CostModel` | CPU + I/O 成本模型 |
| `DPSize (DPccp)` | 动态规划 Join Order 枚举 |
| `demo_optimizer()` | 3表连接的最优计划搜索 |
| `demo_plan_selection()` | 不同查询的计划选择 |

### 运行

```bash
python code/db_kernel_06_query_opt.py
```
