# 数据库内核第5课：查询执行

> 日期：2026-05-11 | 实践代码：`code/db_kernel_05_query_exec.py`

---

## 一、执行引擎的演进

| 代 | 模型 | 特点 |
|---|------|------|
| 1代 | Volcano（迭代器） | 一次一行，最通用 |
| 2代 | Push-Based | 上下游协作，减少调度开销 |
| 3代 | 向量化 | 一批一批处理，SIMD 友好 |

---

## 二、Volcano 模型（迭代器模型）

### 2.1 核心接口

```
open()   → 初始化
next()   → 返回下一条记录（或 None 表示结束）
close()  → 清理资源
```

### 2.2 执行计划树

```
Projection (name, age)
  └── Filter (age > 28)
        └── SeqScan (users)
```

### 2.3 执行流程

```
Projection.next() 触发
  → Filter.next() 触发
    → SeqScan.next() 返回第1行
      → Filter 检查谓词
        → 通过 → Projection 选列 → 返回给客户端
        → 不通过 → Filter.next() 再触发 Scan
```

**关键特性**：
- **Pull-Based**：父节点向子节点拉数据
- **流水线**：一个记录在整棵树上流式处理
- **物化点**：某些操作（如 Sort、HashJoin Build）需要暂停流水线

### 2.4 优缺点

| 优点 | 缺点 |
|------|------|
| 通用、扩展性好 | 每行一次虚函数调用，CPU 效率低 |
| 支持任意组合 | 对 cache 不友好 |
| 实现简单 | 无法利用 SIMD |

---

## 三、连接算法

### 3.1 Nested Loop Join

```
for each row in L:
    for each row in R:
        if match(L, R): output
```

- 复杂度：O(|L| × |R|)
- 适用：小表驱动大表（且右表有索引）

### 3.2 Hash Join

```
Build: for each row in R: hash[row.key] = row
Probe: for each row in L: output if L.key in hash
```

- 复杂度：O(|L| + |R|)
- 要求：等值连接，小表做 Build
- 变体：Grace Hash Join（哈希分区处理超大表）

### 3.3 Sort-Merge Join

```
1. Sort L by key
2. Sort R by key
3. Merge 两个有序列表
```

- 复杂度：O(N log N + M log M + N + M)
- 优势：数据已排序的场景（如 ORDER BY + JOIN）
- 支持：不等值连接

### 3.4 选择策略

| 条件 | 推荐算法 |
|------|----------|
| 小表驱动大表 | Nested Loop（右表有索引） |
| 等值连接 | Hash Join |
| 不等值连接 | Sort-Merge |
| 数据已排序 | Sort-Merge |
| 内存不足 | Grace Hash Join |

---

## 四、向量化执行

### 4.1 原理

一次处理一批（Batch）记录而不是一条：

```
Volcano:   [row1], [row2], [row3], ...
向量化:    [row1, row2, row3, row4], [row5, row6, ...]
```

### 4.2 优势

1. **减少虚函数调用**：每个 batch 只调用一次 next_batch
2. **缓存友好**：批量处理数据局部性好
3. **SIMD 友好**：可以对 batch 内的数据做向量化运算
4. **编译优化**：Loop Vectorization

---

## 五、物化

### 5.1 什么时候需要物化

- **排序**：需要全部数据才能排序
- **Hash Join Build**：Hash 表
- **聚合**：GROUP BY 需要全部分组
- **子查询**：有时需要物化结果集

### 5.2 物化 vs 流水线

```
流水线：  Filter → Projection → Output  (不中断)
物化点：  HashJoin 的 Build 阶段
          Sort
          Aggregate (需要全部数据)
```

---

## 六、实践代码

`db_kernel_05_query_exec.py` 包含：

| 模块 | 内容 |
|------|------|
| `ExecNode` | Volcano 基类（open/next/close） |
| `SeqScan / Filter / Projection / Limit` | Volcano 节点实现 |
| `NestedLoopJoin` | NLJ 实现 |
| `HashJoin` | Hash Join（Build + Probe） |
| `SortMergeJoin` | SMJ 实现 |
| `VectorizedScan / VectorizedFilter` | 向量化执行 |
| `Materialize` | 物化节点 |

### 运行

```bash
python code/db_kernel_05_query_exec.py
```
