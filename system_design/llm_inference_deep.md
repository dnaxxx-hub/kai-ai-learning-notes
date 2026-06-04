# LLM 推理优化深潜笔记

## 1. LLM 推理过程详解：Prefill + Decode 两阶段

### 1.1 自回归解码基础
LLM 本质上是自回归模型：一次生成一个 token，将新生成的 token 拼接到输入序列，再继续预测下一个 token。

```
输入: "今天天气真"
输出: "好" → 拼接 → "今天天气真好" → 继续预测
```

### 1.2 Prefill 阶段（预填充）
- **输入**: 整个 prompt（如 512 个 token）
- **计算**: 一次前向传播，对所有 prompt token 并行计算
- **产出**: 所有位置的 KV 向量（用于后续 Decode）+ 第一个输出 token
- **特点**: 计算密集型（compute-bound），矩阵乘占主导

### 1.3 Decode 阶段（逐 token 生成）
- **输入**: 每次只输入 1 个新 token
- **计算**: 每次前向传播只计算新 token 的 QKV，利用之前缓存的 KV
- **产出**: 1 个新 token + 新增的 KV 向量
- **特点**: 访存密集型（memory-bound），瓶颈在 DRAM 带宽而非算力

```
Prefill:  ... QKV 全部计算 → K_cache[0..N], V_cache[0..N]
Decode 1: Q_new → attention(Q_new, K_cache, V_cache) → token_1
Decode 2: Q_new → attention(Q_new, K_cache_new, V_cache_new) → token_2
...
```

### 1.4 Attention 计算在 Prefill vs Decode 的区别

| 阶段 | Q 维度 | K 维度 | 计算模式 |
|------|--------|--------|----------|
| Prefill | [1, seq_len, d] | [1, seq_len, d] | 大矩阵 × 大矩阵 (compute-bound) |
| Decode | [1, 1, d] | [1, total_len, d] | 小向量 × 大矩阵 (memory-bound) |

---

## 2. KV Cache 原理

### 2.1 为什么需要 KV Cache？

如果不使用 KV Cache，Decode 阶段每次都要从头计算所有 token 的 K 和 V：

```
# 没有 KV Cache（n 次生成）
第1步: QKV(prompt),    K = [k0],       V = [v0]       → token1
第2步: QKV(prompt+1),  K = [k0, k1],   V = [v0, v1]   → token2
第3步: QKV(prompt+2),  K = [k0, k1, k2], V = [v0, v1, v2] → token3
```

这样每一步都在重复计算之前已有的 K/V，O(n²) 的总复杂度。

**KV Cache 方案**：把每步计算的 K/V 缓存起来，Decode 时只需计算新 token 的 K/V，然后加载缓存：

```
# 有 KV Cache（n 次生成）
Prefill: QKV(prompt), K_cache = [k0..kp], V_cache = [v0..vp], 产出 token1
Decode1: QKV(token1), K_cache += [k1], V_cache += [v1], attention(Q1, K_cache, V_cache) → token2
Decode2: QKV(token2), K_cache += [k2], V_cache += [v2], attention(Q2, K_cache, V_cache) → token3
```

### 2.2 内存消耗分析

对于批量大小为 B、序列长度为 L、隐藏维度为 d、层数为 N、KV 头数为 H、每个头维度为 h（d = H × h）的模型：

```
每层每个 token 的 KV Cache 大小 = 2 × H × h (K 和 V 各一份)
总 KV Cache 大小 = B × L × N × 2 × H × h
                 = 2 × B × L × N × d  (bytes, 假设 FP16)
```

**实例：LLaMA-13B**
- d = 5120, N = 40, FP16 (2 bytes/param)
- B = 1, L = 2048
- 每 token 消耗 = 2 × 40 × 5120 × 2 = 819,200 bytes ≈ 0.8 MB
- 总消耗 = 2048 × 0.8 MB ≈ 1.6 GB

**实例：LLaMA-70B**
- d = 8192, N = 80, FP16
- B = 1, L = 4096
- 每 token 消耗 = 2 × 80 × 8192 × 2 = 2,621,440 ≈ 2.6 MB
- 总消耗 = 4096 × 2.6 MB ≈ 10.5 GB
- B = 64 时 → 672 GB（远超单 GPU 显存）

### 2.3 显存占用公式

```
Model Weights: W = N × d² × 2 (FP16)
KV Cache: KV = 2 × B × L × N × d × 2 (FP16)
Total = W + KV + Activation Memory
```

---

## 3. FlashAttention：IO 感知算法

### 3.1 问题：标准 Attention 的 IO 瓶颈

标准 Attention 计算：
```
S = Q × K^T      (1) 写入 HBM: S
P = softmax(S)   (2) 读取 S, 写入 P
O = P × V        (3) 读取 P 和 V, 写入 O
```

**问题**：中间结果 S 和 P 必须写入 HBM（高带宽内存），再读回来。Attention 本身就是访存密集的，这么做放大了瓶颈。

```
HBM ←→ SRAM 带宽约 1:10 ~ 1:20
```

### 3.2 FlashAttention 核心思想

**IO 感知**：不要等算完整个矩阵再写回 HBM，而是分块计算，在 SRAM 中完成所有中间计算。

### 3.3 Tiling 分块

将 Q、K、V 切成小块，每次加载一块到 SRAM：
```
Q: [B, N, d] → 切成 [B, N, Tr] 和 [B, N, Tr] ...
K: [B, N, d] → 切成 [B, N, Tc] 和 [B, N, Tc] ...

对于每个 Q 块 q_i:
    O_i = 0, m_i = -inf, l_i = 0
    对于每个 K/V 块 k_j, v_j:
        S_ij = q_i × k_j^T        # 在 SRAM
        m_ij = rowmax(S_ij)        # 在 SRAM
        P_ij = exp(S_ij - m_ij)   # 在 SRAM
        l_ij = rowsum(P_ij)       # 在 SRAM

        # Online Softmax 合并
        m_new = max(m_i, m_ij)
        O_i = O_i × exp(m_i - m_new) + P_ij × exp(m_ij - m_new) × v_j
        l_i = l_i × exp(m_i - m_new) + l_ij × exp(m_ij - m_new)
        m_i = m_new

    O_i = O_i / l_i    # 最后归一化
```

### 3.4 Online Softmax（关键创新）

传统的 safe softmax 需要两次 pass：先找最大值，再计算 exp/sum。

**Online Softmax**：在不完整的块上也能计算正确的 softmax，通过"在线校正"：

```
# 算法：一次 pass 完成 softmax
算法核心思想：
1. 维护运行中的最大值 m_i 和归一化和 l_i
2. 遇到新块时，用新的最大值 (m_new = max(m_i, m_block)) 来校正之前的结果
3. 校正因子 exp(m_old - m_new) 让所有已处理的块"对齐"到新的最大值

数学上等价于标准 softmax（逐块校正后累加），数值上完全一致。
```

### 3.5 FlashAttention 的收益

| 指标 | 标准 Attention | FlashAttention |
|------|---------------|----------------|
| HBM 访问 | O(N²d) | O(N²d/B_M) |
| 实际加速 | 1x | 2-4x |
| 精度 | 相同（FP16） | 相同（数值等价） |

其中 B_M 是 SRAM 大小/块大小。

### 3.6 Block-Sparse FlashAttention（扩展）

利用 attention 矩阵的稀疏性，跳过值为 0 的块。常见的稀疏模式：
- **局部注意力**: 只关注附近 token
- **全局注意力**: 少数 token 关注全局
- **滑动窗口**: 窗口内密集，窗外稀疏

---

## 4. PagedAttention：vLLM 的分页管理

### 4.1 问题：KV Cache 碎片化

传统实现中，KV Cache 是连续存储的：
```
Sequence A (长度 128):  [A0][A1][A2]...[A127]
Sequence B (长度 64):   [B0][B1]...[B63]  [空闲...]
```

**问题**：
- 内部碎片：预留空间但未使用
- 外部碎片：不同序列间无法共享
- 无法高效共享公共前缀

### 4.2 PagedAttention 分页方案

灵感来自操作系统的分页内存管理：

```
逻辑视图:        [token0][token1]...[token63][token64]...
                    ↓         ↓           ↓        ↓
物理块:        Block 0: [0,1,2,...,15]  (16 tokens/block)
               Block 1: [16,17,...,31]
Block Table:   Seq A → [Block 3, Block 7, Block 2, ...]  (非连续)
```

### 4.3 关键机制

1. **分块管理**：每个 Block 固定大小（通常 16 或 32 tokens）
2. **Block Table**：逻辑到物理的映射表，类似页表
3. **Copy-on-Write (CoW)**：多个序列共享 prefix block 时，写时才复制
4. **提前释放**：序列生成结束后立即回收 Block
5. **Prefix Caching**：相同前缀的 block 自动共享

### 4.4 注意力计算

PagedAttention 在计算 attention 时，需要通过 Block Table 将逻辑位置映射到物理位置，取出对应的 KV block 进行计算。

```
物理 KV 存储在 [Block_3, Block_7, Block_2] 中
逻辑访问位置 17 → Block_3[1] (物理块3的索引1)
```

---

## 5. 量化推理

### 5.1 为什么量化

- FP16 权重 → 显存减半（W8A16 权重 8-bit）
- 计算加速：INT8 矩阵乘比 FP16 快 2-4x
- 显存瓶颈（尤其是 KV Cache）大幅缓解

### 5.2 W8A16（权重 8-bit，激活 16-bit）

```
量化过程（Per-Channel / Per-Tensor）:
  W_fp16 → scale = max(|W_fp16|) / 127 → W_int8 = round(W_fp16 / scale)
  
反量化计算:
  Y = Q × K_int8^T × scale_k × scale_q   (注意缩放因子合并)
  # 激活保持 FP16，只在权重加载时反量化

实际推理流程:
  for each layer:
    W_int8 → dequantize to FP16 → matmul with FP16 activation
    等效于: FP16_gemm(W_quant * scale, activation)
```

**为什么 W8A16 精度损失小？**
- 权重分布通常比较均匀，8-bit 量化损失 < 1%
- 逐通道（per-channel）量化保持精度
- 激活保持 FP16 没有额外损失

### 5.3 W4A16（权重 4-bit，激活 16-bit）

```
分组量化（通常 group_size=128）:
  for g = 0 to d/128:
    W_fp16[g] → scale_g, zero_point_g
    W_int4[g] = clamp(round(W_fp16[g] / scale_g + zero_point_g), 0, 15)

反量化推理:
  W_int4 → dequantize(W_int4, scale, zero_point) → FP16 → GEMM

反量化开销:
  额外加载 scale/zero 参数
  通常用 lookup table (LUT) 加速反量化
```

**GPTQ / AWQ / GGUF 的区别**：
- **GPTQ**: 基于 Hessian 矩阵的二次量化，最优精度但校准耗时
- **AWQ**: 激活值感知，保留重要权重通道的精度
- **GGUF**: llama.cpp 的格式，支持多种量化级别

### 5.4 INT8/FP8 KV Cache 量化

KV Cache 是显存消耗大户，将其量化为 INT8 或 FP8：
```
KV Cache: FP16 → INT8
每 token 显存减半
精度影响：小模型较明显，大模型（>30B）几乎无损失
```

---

## 6. 推理优化技术全家桶

### 6.1 Continuous Batching（连续批处理）

**Static Batching（传统）**:
```
请求 A ──┐
请求 B ──┤====== Batch 1 ======── 等所有完成 → 下一批
请求 C ──┘
```

问题：先完成的请求空等，浪费 GPU。

**Continuous Batching**:
```
时间轴 →
A: [Prefill] [Decode1] [Decode2] [Done]
B:           [Prefill] [Decode1] [Decode2] [Decode3] [Done]
C:                              [Prefill] [Decode1] [Done]

GPU: [A+B] [A+B+C] [B+C] [B] ...
```

- 请求完成后立即退出 batch
- 新请求可以立即加入下一个 iteration
- 吞吐量提升 2-4x

### 6.2 Prefix Caching（前缀缓存）

```
用户1: "告诉我如何用 Python 实现排序算法..."
用户2: "告诉我如何用 Python 实现搜索算法..."

相同前缀 "告诉我如何用 Python 实现"
→ K/V 缓存可以重用
→ Prefill 阶段跳过前 8 个 token 的计算
```

**实现**：
- 基于内容的哈希匹配前缀
- vLLM 的 Automatic Prefix Caching (APC)
- 适用于 system prompt 相同或相似的场景

### 6.3 Speculative Decoding（推测解码）

**核心矛盾**：LLM Decode 慢但访存瓶颈，小模型 Decode 快但质量差。

**思路**：用小模型"草稿"大模型的输出，然后验证。

```
第1步（草稿）：小模型生成了 k 个候选 token
第2步（验证）：大模型一次前向传播验证所有候选
第3步（接受/拒绝）：接受匹配的 token，拒绝不匹配的

如果接受率 80-90%，加速比约 2-3x
```

**算法**：
1. Draft model 生成 k 个 token（快速自回归）
2. Target model 一次 forward 计算这些 token 的 logits
3. 逐位置接受：如果 draft 的分布与 target 一致则接受
4. 遇到第一个不匹配的位置，用 target 的采样替换
5. 丢弃后续未验证的 draft token

### 6.4 其他技术

- **Tensor Parallelism**: 在多个 GPU 上分拆注意力头
- **Pipeline Parallelism**: 按层切分
- **FlashAttention**: 减少显存读写
- **FP8 Training/Inference**: 原生 FP8 计算
- **Quantization**: W4A16 / W8A8
- **Sparsity**: 激活值稀疏性

---

## 7. 推理引擎对比

| 特性 | vLLM | TensorRT-LLM | TGI | llama.cpp |
|------|------|-------------|-----|-----------|
| **核心创新** | PagedAttention, APC | TensorRT 编译优化 | 易用性, Token Streaming | CPU 推理优化 |
| **GPU 支持** | ✅ 优秀 | ✅ 最佳（NVIDIA） | ✅ 良好 | ⚠️ 有限 |
| **CPU 推理** | ❌ | ❌ | ❌ | ✅ 最佳 |
| **量化支持** | AWQ, GPTQ, FP8 | INT8, FP8, INT4 | GPTQ, AWQ | GGUF 全系列 |
| **连续批处理** | ✅ 原生 | ✅ | ✅ | ❌（静态批） |
| **Prefix Caching** | ✅ APC | ✅ | ⚠️ 有限 | ❌ |
| **推测解码** | ✅ | ✅ | ✅ | ❌ |
| **多 GPU** | TP, PP | TP, PP, EP | TP | ❌ |
| **显存效率** | 极高（Paged） | 高 | 中 | 中 |
| **部署难度** | 低 | 高 | 低 | 低 |
| **生产就绪** | ✅ | ✅ | ✅ | ⚠️ 实验 |

### 选型建议

- **云 GPU 推理**：vLLM（显存效率最高，生态好）
- **极致性能（NVIDIA）**：TensorRT-LLM（编译优化收益大）
- **快速原型**：TGI（HuggingFace 生态，易用）
- **本地/CPU 推理**：llama.cpp（GGUF 格式 + CPU 优化）
- **Edge 设备**：llama.cpp, MLX (Apple)

---

## 8. 服务化部署

### 8.1 吞吐量优化

**目标**: 单位时间内处理更多请求（requests/sec）

**策略**:
1. **增大 Batch Size**: 批处理更多请求 → 提高 GPU 利用率
2. **优化显存分配**: PagedAttention 减少碎片
3. **Prefill/Decode 调度**: 不要混合计算模式（Prefill 计算密集，Decode 访存密集）
4. **Chunked Prefill**: 大 Prompt 分块处理，避免长时间占 GPU
5. **FlashDecoding**: Decode 阶段在 sequence 维度并行

**Chunked Prefill 调度**:
```
Iteration 1: Prefill(Chunk A) + Decode(req_1) + Decode(req_2)
Iteration 2: Prefill(Chunk B) + Decode(req_1) + Decode(req_2) + Decode(req_3)
Iteration 3: Prefill(Chunk C) + Decode(req_1) + Decode(req_2) + Decode(req_3)
```

### 8.2 延迟优化

**目标**: 减少首 token 延迟和每个 token 的生成延迟

**策略**:
1. **KV Cache 预填充**: Prefill 阶段批量处理
2. **模型并行**: 大模型多 GPU 切分
3. **Streaming**: 逐 token 返回（不等待完整输出）
4. **Speculative Decoding**: 小模型加速大模型
5. **CUDA Graph**: 减少 Kernel Launch 开销

**首 token 延迟公式**:
```
TTFT = Prompt_Process_Time + First_Decode_Time
     ≈ prefill_time + attention_time
```

### 8.3 QoS 保障

**关键指标**:
- **TTFT** (Time To First Token): 首 token 延迟，通常 < 500ms
- **TPOT** (Time Per Output Token): 每 token 生成延迟，通常 < 50ms
- **ITL** (Inter-Token Latency): token 间延迟，TPOT 同义
- **Throughput**: 吞吐量 (req/s 或 tokens/s)

**SLO (Service Level Objective)**:
```
P99 TTFT < 500ms
P99 TPOT < 50ms
Throughput > 50 req/s (7B 模型单卡)
```

**调度策略**:
- **FIFO**: 简单但无法保障延迟
- **优先级调度**: 高 QoS 请求优先
- **抢占调度**: 低优请求让出资源
- **请求排队 + 负载均衡**: 多实例部署

**实际考虑**:
- 不要将所有 GPU 打满（预留 20% 显存应对突发）
- TTFT 和 Throughput 不可兼得（trade-off）
- 长序列更耗显存，需要特殊处理

---

## 参考资料
- FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness (Dao et al., 2022)
- FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning
- vLLM: Easy, Fast, and Cheap LLM Serving with PagedAttention
- Efficient Memory Management for Large Language Model Serving with PagedAttention
- LLM Inference Performance Engineering: A Comprehensive Guide
- TensorRT-LLM Documentation
- llama.cpp GitHub Repository
