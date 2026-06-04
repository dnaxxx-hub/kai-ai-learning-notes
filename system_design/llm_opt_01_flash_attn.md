# LLM 推理优化 · 第1弹：FlashAttention 核心

## 1. 问题：标准 Attention 的内存带宽瓶颈

### 标准 Attention 计算流程

```
Q (N×d), K (N×d), V (N×d)

S = Q @ K^T        → N×d × d×N → N×N 矩阵  [HBM 读写]
P = softmax(S)     → 行归一化              [HBM 读写]
O = P @ V          → N×N × N×d → N×d      [HBM 读写]
```

**瓶颈分析**：每个步骤都需要从 HBM（高带宽内存，~1.5TB/s）读写完整矩阵。
- S 是 N×N 矩阵，N=4096 时约 128MB
- 每次 softmax 要读整个 S，写回 P
- **O(n²) 内存访问** — 序列变长时，计算量 O(n²) 但**带宽需求**才是真瓶颈

> GPU 计算速度远超 HBM 带宽（A100: 312TFLOPS vs 1.5TB/s）。Attention 是**内存受限**的，典型的「内存墙」问题。

### 计算 vs 内存：Roof-line 分析

| 序列长度 | 计算量 (FLOPs) | 内存访问 (bytes) | 瓶颈 |
|---------|---------------|-----------------|------|
| 512     | O(n²) 较小    | O(n²) 较小      | 计算 |
| 2048    | 中等          | 中等            | 内存 |
| 8192    | 大            | 很大            | 内存 ← Attention |
| 32768   | 很大          | 极大            | 内存 ← 严重瓶颈 |

---

## 2. 核心思想：IO-Aware 算法

### 关键洞察
- GPU 有 **HBM**（大容量但慢）和 **SRAM**（小容量但极快）
  - A100: HBM 40/80GB (1.5TB/s), SRAM 192KB/108 SM ≈ 20MB (19TB/s)
- 标准 Attention：所有操作都在 HBM 上进行
- **FlashAttention**: 让 HBM 只做输入/输出，中间的 S、P 矩阵完全在 SRAM 中计算

### 两个核心技术

**① 分块 (Tiling)**
- 把 Q、K、V 切成小块，每次只把一块加载到 SRAM
- 在 SRAM 内完成局部 S、P、O 的计算
- 最后累加局部 O 得到全局结果

**② 重计算 (Recomputation / No Exact Softmax)**
- 标准 softmax 需要全局统计量（分母 sum）
- 分块后需要在块间传递统计量
- **Online Softmax**: 增量式更新 softmax 的归一化因子，避免保存中间矩阵

```
算法伪代码：
1. 将 Q 分成 Q₁...Q_T 块，K/V 分成 K₁...K_T 块
2. 对每个 Q_i 块：
   a. 初始化局部 softmax 统计量 m=0, l=0
   b. 对每个 (K_j, V_j) 块：
      - 计算 S_ij = Q_i @ K_j^T         [SRAM]
      - 计算 m_new, l_new (online softmax更新)
      - O_i 更新 += 修正后的局部值       [SRAM]
   c. 写回 O_i 到 HBM
```

---

## 3. FlashAttention-1 (2022, Tri Dao)

### 核心创新
- **SRAM 分块策略**：精心设计块大小，确保 S、P 矩阵完全放在 SRAM 内
- **Online Softmax**：Safe softmax 的增量版本
  - 无需保存 N×N 的 softmax 中间结果
  - 只需要传递两个统计量 (m, l) 到下一块
- **反向传播重计算**：反向传播时不保存大矩阵，重新前向计算一次
  - 比起保存 P 矩阵的内存节省，多算一次前向更划算

### 性能
- 相比 PyTorch 标准 Attention: **2-4x 加速**
- 相比 cuBLAS: **3-5x 加速**
- **内存从 O(N²) 降低到 O(N)**

### 算法细节

```python
# Online Softmax 的递推形式
# 常规 softmax: p_i = exp(x_i - max_x) / sum(exp(x_j - max_x))
#
# 分块版本：假设已处理了前 t 块，得到 max=m_old, sum=l_old
# 新块到来，新 max = m_new
# 修正因子 = exp(m_old - m_new)
# diag(修正因子) 用于调整之前的结果
# 最终 softmax 在新 max 下是正确的
```

### 局限
- 非矩阵乘法操作（element-wise 运算）占比高
- **warp 间并行**不够充分

---

## 4. FlashAttention-2 (2023, Tri Dao)

### 改进点

| 特性 | FA-1 | FA-2 |
|-----|------|------|
| 循环方向 | Q 外循环, K/V 内循环 | K/V 外循环, Q 内循环 |
| 非矩阵计算 | 较多 element-wise | 减少 non-matmul |
| 并行策略 | block 级并行 | **thread block 级并行** |
| 序列维度 | 全体块 | 重排 + 前向/反向对齐 |

### 核心变化

**① 交换循环顺序**
- FA-1: Q 外循环 + K/V 内循环 → 需要在线更新 O
- FA-2: K/V 外循环 + Q 内循环 → Q 块可独立计算，**减少同步开销**

**② 减少非矩阵乘法操作**
- 把更多的计算转移到 matmul 中（tensor core 友好）
- FA-1 中有大量 element-wise + reduciton 操作
- FA-2 将这些转化为矩阵乘法
- 实测 non-matmul FLOPs 从 40% → 5%

### 性能
- FA-1 vs FA-2: **1.5-2x 进一步提升**
- 前向: 比 PyTorch 快 2-5x，比 FA-1 快 ~2x
- 反向: 比 PyTorch 快 3-10x
- 大序列（8K+）优势更明显

---

## 5. FlashAttention-3 (2024, Hopper GPU)

### 硬件基础：H100 Hopper
- **FP8 Tensor Core**: 支持 FP8 矩阵乘法，比 FP16 快 2x
- **WGMMA (Warp Group Matrix Multiply-Accumulate)**: 
  - 新的异步 warp 组级矩阵乘法指令
  - 计算和访存可以 overlap
- **更大的 SRAM**: 256KB/SM → 可以处理更大块

### 关键创新

**① FP8 计算 + FP32 累积**
- 用 FP8 做矩阵乘法（快）
- 用 FP32 做累积（精度）
- 混合精度，无损最终精度

**② Async WGMMA**
- 在计算当前块时，**异步预取**下一块数据
- 大幅减少访存 stall
- 计算和访存流水线重叠

**③ 块调度优化**
- 利用 Hopper 的张量内存加速器 (TMA)
- 更高效的数据搬移

### 性能
- FA-2 vs FA-3: **1.5-2x（FP16）~ 2-3x（FP8）**
- A100(HBM80) → B200: FlashAttention 的跨代演进

---

## 6. 与标准 Attention 的计算图对比

### 标准 Attention (PyTorch)
```
Q ──┐         K ──┐
    ├─ matmul ─┤   |
    ↓              |
    S (N×N) ───────┘
    ↓
  softmax  ───── [HBM读写S, P]
    ↓
    P ─┐         V ──┐
       ├─ matmul ────┤
       ↓              ↓
       O              |
```

**HBM 访问**: Q, K, V 各一次 + S(写读) + P(写读) + O(写) = **5回大矩阵读写**

### FlashAttention
```
                    ┌─────────────────────┐
                    │       SRAM           │
                    │                      │
Q_block ──→ matmul ──→ online_softmax ──→ matmul ──→ O_accum
K_block ──→         │                      │
V_block ──→         └─────────────────────┘
    ↑                       ↑
  HBM读块                HBM只写最终O
```

**HBM 访问**: Q, K, V 各一次(分块读) + O 一次(写) = **4回小矩阵读写**
- **没有 N×N 中间矩阵的读写**
- 内存开销从 O(N²) 降到 O(N)

---

## 7. 数学基础：Online Softmax

### 标准 Softmax
```python
m = max(x)                    # 最大值
p = exp(x - m)                # 安全指数
l = sum(p)                    # 归一化因子
softmax = p / l               # 结果
```

### Online (分块) Softmax
```python
# 处理第1块
m1 = max(x₁)
l1 = sum(exp(x₁ - m₁))

# 处理第2块
m₂ = max(m₁, max(x₂))
# 修正因子：之前结果在新最大值下的权重
l₂ = exp(m₁ - m₂) * l₁ + sum(exp(x₂ - m₂))
# 最终结果 = diag(exp(m₁ - m₂)) * prev_result 合并新结果
```
整个过程**无需保存完整的 x，只需传递两个标量 (m, l)**。

---

## 总结

| 版本 | 硬件 | 加速 vs Baseline | 关键创新 |
|------|------|-----------------|---------|
| FA-1 | A100 | 2-4x | 分块到 SRAM + online softmax |
| FA-2 | A100 | 3-6x | 减少 non-matmul + 更好并行 |
| FA-3 | H100 | 5-12x | FP8 + async WGMMA |

**一句话总结**: FlashAttention 通过 IO-aware 的分块算法，把 Attention 的瓶颈从「内存带宽」转移到「计算上」，使 GPU 的算力得到充分利用。

---

### 参考
- FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness (Tri Dao, 2022)
- FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning (Tri Dao, 2023)
- FlashAttention-3: Fast and Accurate Attention with Asynchronicity and Low-precision (Tri Dao, 2024)
