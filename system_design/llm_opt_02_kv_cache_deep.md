# LLM 推理优化 · 第2弹：KV Cache 深度

## 1. KV Cache 内存分析

### 基本公式

```
KV Cache Size = 2 × L × N_heads × H × seq_len × precision_bytes
```

- **L**: 层数（decoder layers）
- **N_heads**: 每层注意力头数
- **H**: 每个头的维度（d_head）
- **seq_len**: 当前序列长度（预填充 + 已生成 token）
- **2**: key 和 value 各一份
- **precision_bytes**: FP16=2, FP32=4, INT8=1, FP8=1

### 常见模型精确计算

| 模型 | 参数量 | L | N_heads | d_head | d_model | 每 token 大小 | 8K seq |
|------|-------|---|--------|--------|---------|---------------|--------|
| **LLaMA 7B** | 6.7B | 32 | 32 | 128 | 4096 | 2×32×32×128×2B = **512KB/token** | **~4.0 GB** |
| **LLaMA 13B** | 13B | 40 | 40 | 128 | 5120 | 2×40×40×128×2B = **800KB/token** | **~6.25 GB** |
| **LLaMA 30B** | 33B | 60 | 52 | 128 | 6656 | 2×60×52×128×2B = **1.56MB/token** | **~12.2 GB** |
| **LLaMA 65B** | 65B | 80 | 64 | 128 | 8192 | 2×80×64×128×2B = **2.5MB/token** | **~20 GB** |
| **LLaMA 70B (GQA)** | 69B | 80 | 64 | 128 | 8192 | 用8 KV头: 2×80×8×128×2B = **320KB/token** | **~2.5 GB** |

> **关键观察**: 7B 模型 8K 序列下 KV Cache ≈ 4GB，而模型权重本身约 14GB（FP16）。
> 长序列（32K+）时，KV Cache 可能超过模型权重大小！

### 内存增长趋势

```
序列长度  | KV Cache (7B, FP16)
1K       | 0.5 GB
2K       | 1.0 GB
4K       | 2.0 GB
8K       | 4.0 GB
16K      | 8.0 GB
32K      | 16 GB
128K     | 64 GB ← 爆显存
```

**KV Cache 是推理服务的头号内存瓶颈**。

---

## 2. Multi-Query Attention (MQA)

### 动机
传统 MHA：每层有 N 个 query 头 + N 个 key/value 头 → KV cache 随头数线性增长

### MQA 的核心思想
- **多个 query 头共享同一个 key/value 头**
- 即：N_query_heads = N (多), N_kv_heads = 1 (单)
- KV Cache 直接减少到 **1/N**

### 结构对比
```
MHA:  Q₁ Q₂ ... Q₃₂    K₁ K₂ ... K₃₂    V₁ V₂ ... V₃₂
      └──32个头独立──┘   └──每个都有KV──┘

MQA:  Q₁ Q₂ ... Q₃₂    K₁    V₁
      └──32个头──┘      └──共享1个KV──┘
```

### 性能影响
| 方面 | 效果 |
|------|------|
| KV Cache | 减少到 **1/N**（7B: 32x 减少, ~125MB/token 变 ~16MB/token） |
| 质量 | **轻微下降**（共享 KV 降低了表达力） |
| 训练 | 需要特殊处理（通常是 trained from scratch） |
| 推理 | 快（访存减少 + cache 友好） |

### 代表模型
- **PaLM** (Google): 使用 MQA
- **Falcon** (TII): Falcon-40B, Falcon-7B 使用 MQA
- **GPT-3 (推测)**: 内部可能使用了类似技术

---

## 3. Grouped Query Attention (GQA)

### 核心思想
MHA 和 MQA 的折中方案：
- **分组共享**：将 N 个 query 头分成 G 组，每组共享一个 KV 头
- N_kv_heads = G（G 是组数，通常 4-8）
- KV Cache 减少到 **G/N**

### 结构
```
GQA (G=4, N=32):
Group 1: Q₁ Q₂ ... Q₈  ── K₁ V₁
Group 2: Q₉ Q₁₀ ... Q₁₆ ── K₂ V₂
Group 3: Q₁₇ ... Q₂₄    ── K₃ V₃
Group 4: Q₂₅ ... Q₃₂    ── K₄ V₄

KV Cache 大小: MHA 的 4/32 = 1/8
```

### GQA 速查表

| G (KV头数) | KV Cache 比例 | 质量 | 典型用途 |
|-----------|--------------|------|---------|
| N（=MHA） | 100% | 最好 | 训练 |
| 8 | 25%（32头） | 非常好 | LLaMA 70B |
| 4 | 12.5%（32头） | 很好 | LLaMA 2 70B |
| 2 | 6.25%（32头） | 较好 | 中间方案 |
| 1（=MQA） | 3.125%（32头） | 够用 | 推理优化 |

### 优势
- **训练便宜**：相比 MQA，GQA 更容易训练（可以从 MHA 权重做 **up-training**）
- **质量接近 MHA**：分组使得每个 KV 仍有一定容量
- **推理高效**：KV Cache 大幅减少

### 代表模型
- **LLaMA 2 70B** (Meta): 使用 GQA (8 KV heads)
- **LLaMA 3** (Meta): 全面采用 GQA
- **Gemma** (Google): 使用 GQA
- **Mixtral 8x7B** (Mistral): 使用 GQA

### Up-training (MHA → GQA)
```
1. 对 MHA 的 KV 权重做 group-wise average
   K_new_group_i = mean(K_old_head_{i₁}, ..., K_old_head_{iₘ})
2. 继续微调一小段时间
3. 好处：不需要重头训练
```

---

## 4. KV Cache 量化

### 动机
FP16 KV Cache 占用太大，但 KV Cache 的分布相对**规律**，量化损失较小。

### 方法

**① INT8 量化**
```
KV int8 = round(KV_fp16 / scale)
scale = max(|KV|) / 127
```
- KV Cache 减半（FP16→INT8）
- 逐 token 或逐个向量量化
- 精度损失：约 0.1-0.3 perplexity
- **K 对量化更敏感**（因为 softmax 指数运算放大了误差）

**② FP8 量化**
- E4M3 (4指数位+3尾数位) vs E5M2 (5+2)
- H100 原生支持 FP8 存储和计算
- 精度比 INT8 稍好（动态范围更大）
- **NVidia 推荐方案**：K 用 FP8(E4M3), V 用 FP8(E4M3)

**③ 混合精度量化**
```
KV Cache = K (FP8) + V (INT8)   → 综合权衡
           或
KV Cache = K (FP16) + V (INT8)  → 精度更好
```

### 量化方式对比

| 方式 | 内存节省 | Perplexity 上升 | 实现难度 |
|------|---------|----------------|---------|
| FP16 (baseline) | 1x | - | 简单 |
| FP8 | 2x | ~0.05-0.1 | 中等 |
| INT8 | 2x | ~0.1-0.3 | 较难 |
| INT4 | 4x | ~0.5-1.0 | 很复杂 |
| NF4 (QLoRA) | 4x | ~0.3-0.5 | 复杂 |

### KV Cache 量化 vs 权重量化

| | 权重量化 | KV Cache 量化 |
|--|---------|--------------|
| 量化时机 | 一次完成 (load time) | **每步推理**都做 |
| 反量化 | 不用，直接计算 | 每次 attention 前要反量化 |
| 开销 | 很小 | **额外计算量** |
| 保存 | 静态 | **动态**，每步新内容 |
| 难点 | 精度影响质量 | 量化/反量化的**流水线** |

### 实际部署建议
1. **先用 GQA** (比如 8 KV heads) → 内存降 4x
2. **再加 FP8 KV Cache** → 总内存降 8x
3. 如果还不够，再用 INT8 量化
4. **长上下文场景**优先优化 KV Cache，这是最大瓶颈

---

## 5. KV Cache 优化总表

| 技术 | 减少比例 | 额外开销 | 质量影响 | 推荐场景 |
|------|---------|---------|---------|---------|
| MQA | ~N (如32x) | 训练改造大 | 明显 | 从零训练的模型 |
| GQA | ~N/G (如4-8x) | up-training | 极小 | 大部分推荐 |
| INT8量化 | 2x | 反量化计算 | ~0.1-0.3 ppl | 离线推理 |
| FP8量化 | 2x | 反量化计算 | ~0.05-0.1 ppl | H100等新卡 |
| 滑动窗口 | 窗口/batch长度 | 长上下文受限 | 窗口外遗忘 | 对话场景 |
| PagedAttention | 减少碎片 | 管理开销 | 无 | vLLM 场景 |

### 组合最佳实践
```
GQA (8 KV heads)    → 4x 减少
+ FP8 KV Cache       → 2x 减少  
────────────────────
总共                 → 8x 减少
7B模型 8K seq: 4GB → 0.5GB ✓
```

---

## 参考
- MQA: Fast Transformer Decoding: One Write-Head is All You Need (Shazeer, 2019)
- GQA: GQA: Training Generalized Multi-Query Transformer Models from Multi-Head Checkpoints (Ainslie et al., 2023)
- KV Cache Quantization: KIVI: A Tuning-Free Asymmetric 2bit Quantization for KV Cache (Liu et al., 2024)
