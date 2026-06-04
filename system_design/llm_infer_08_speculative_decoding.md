# LLM 推理加速 #8：Speculative Decoding（推测解码）

> 学习笔记 — 用"草稿+验证"打破自回归的串行枷锁
> 日期：2026-05-13 | 笔记编号：llm_infer_08
> 前置知识：Transformer Decode 机制（llm_infer_01）、KV Cache（llm_infer_01）、PagedAttention（llm_infer_07）

---

## 0. 引言：Decode 阶段的"GPU 摸鱼"问题

### 0.1 自回归的串行诅咒

LLM 生成是逐 token 的——必须等第 t 个 token 生成完才能开始第 t+1 个。但问题不止在串行本身，更在**硬件利用率**：

```
Decode 阶段单步计算：
  y = softmax(W_q × x_t)               ← 矩阵向量乘 (GEMV)，不是矩阵矩阵乘 (GEMM)
  
特点：一次只算一个 token，计算量极小，但需要加载整个模型权重 + KV Cache
```

**Memory-bound 瓶颈**：每一步 decode 的计算强度（arithmetic intensity）极低。

```
估算 Llama 3 8B FP16 single token decode：
- 模型参数读取：8B × 2B = 16 GB
- KV Cache 读取（4K 上下文）：2 × 32 × 4096 × 4096 × 2 ≈ 2 GB
- 计算量：约 2 × 8B FLOPS ≈ 16 GFLOPS
- 算术强度 ≈ 16G / 18G ≈ 0.9 FLOP/byte  ← 远低于 GPU 峰值（A100: ~312 TFLOPS/2TBps ≈ 156 FLOP/byte）

结论：GPU 95%+ 的时间在等数据，实际计算只占 5%。
```

### 0.2 核心直觉：批处理 Batch 能解决吗？

传统方案是把多个请求 batch 在一起做 decode，让 GEMV 变成 GEMM。但这受限于：
- 请求到达率不够高时，batch size 做不大
- 即使做成 batch，**单请求内部仍然是串行的**

**推测解码的核心思想**：既然 GPU 等数据的时间 > 算数据的时间，那能不能让 GPU 一次"猜"多个 token，然后批量验证？

---

## 1. 核心原理

### 1.1 直观理解

```
普通自回归（每步一次前向）：
Step:  1 → 2 → 3 → 4 → 5 → ...
       p1   p2   p3   p4   p5      ← 每次只产出一个 token

推测解码（一次猜 K 个，批量验证）：
1. 用轻量方法快速猜出 γ 个候选 token：[t₁, t₂, ..., t_γ]
2. 大模型一次前向，并行验证这 γ 个 token 在 true distribution 下的 logits
3. 逐个对照概率判断接收还是拒绝（拒绝后从该位置重新采样）
4. 一次验证可能产出一组连续 token（平均 > 1 个）
```

### 1.2 "草稿+验证"的两阶段范式

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Draft（草稿阶段）                                   │
│  轻量模型 Mq（通常是小模型或简化模型）快速生成 γ 个 token    │
│  输出: D = [d₁, d₂, ..., d_γ]                                │
│                                                             │
│  Step 2: Verify（验证阶段）                                  │
│  大模型 Mp 以 D 作为输入（+已有的所有历史 token）            │
│  并行前向一次，得到 D 中每个位置的真实验证分布 p_i            │
│  同时得到草稿模型在每个位置的分布 q_i                        │
│                                                             │
│  Step 3: Accept/Reject（拒绝采样）                           │
│  对于每个位置 i:                                              │
│    如果 p_i(d_i) ≥ q_i(d_i) → 接受草稿 token d_i            │
│    否则 → 以 (p_i - q_i)_+ 的归一化比例重新采样              │
│    遇到第一个拒绝 → 停止，输出该位置重新采样的 token          │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 拒绝采样的数学细节（Leviathan et al.）

给定草稿分布 `q(x)` 和真实分布 `p(x)`，对草稿样本 `x̂ ~ q(x)`，做以下修正：

1. 以概率 `min(1, p(x̂)/q(x̂))` **接受** x̂
2. 若拒绝，从修正分布 `(p(x) - q(x))_+ / Z` 中重新采样

这个过程的输出分布 **严格等于 p(x)**，即不损失模型质量。

> 重要：推测解码在不修改大模型权重的前提下，保证输出分布与原始模型一致。这是一个"无损加速"技术。

---

## 2. 主要方案

### 2.1 标准 Speculative Decoding（草稿模型法）

| 论文 | 核心思想 |
|------|----------|
| **Leviathan et al. 2022** | 独立小模型做草稿，大模型验证 |
| **Chen et al. 2023** | 同上，独立发表，更工程化的视角 |

```
架构：
┌──────────────┐     γ tokens     ┌──────────────┐
│              │ ──────────────→  │              │
│  Draft Model │    候选序列      │  Target      │
│  (小模型)    │                  │  Model       │
│  如 1.5B     │                  │  (大模型)    │
│              │                  │  如 70B      │
└──────────────┘                  └──────────────┘
    串行生成 γ 步                     单次并行验证
```

**优缺点**：
- ✅ 通用性：任何小模型+大模型对都能用
- ❌ 需要额外加载草稿模型（显存开销翻倍对标配的小模型）
- ❌ 小模型和大模型的词汇表必须对齐（vocab alignment）

### 2.2 Self-Speculative Decoding

**核心 idea**：不用额外小模型，同一模型的前几层自己当草稿。

```
通常假设：Transformer 的早期层已经能预测一些"简单"的 token，
后面的层主要是 refine/correct。

方法：
1. 只跑模型的浅层（如前 L/2 层）+ 一个早退分类头（early exit head）
2. 用浅层输出逐 token 生成 γ 个候选
3. 用全模型前向验证

优点：
- 不需要额外加载草稿模型（节省显存）
- 浅层前向比全模型快得多

缺点：
- 浅层的预测质量有限，接受率可能较低
- 需要训练早退头
```

### 2.3 Staged Speculative Decoding（多级草稿链）

```
多级推测：小→中→大 的草稿链

Draft Lv1 (1.5B)  →  γ₁ tokens →  Draft Lv2 (7B)  →  γ₂ →  Target (70B)
   串行生成           验证+拒绝采样      串行生成         验证
```

每一级去"猜"更多 token，同时接受率随难度递减。典型配置：
- Level 1: 猜 8 个，接受率 0.8
- Level 2: 在前 3 个基础上再猜 5 个，接受率 0.6
- Level 3: 在前 5 个基础上再猜 3 个，接受率 0.4

### 2.4 Medusa / Eagle（多头并行预测）

**核心 idea**：在模型最后加多个轻量 head（MLP），每个 head 预测未来第 k 个位置的 token。

```
Medusa Head 架构（在原始模型的最后一层 hidden state 上接）：

Original Model (例如 LLaMA) 
         │
    hidden_state (d_model)
         │
    ┌────┼────┬────┬────┐
    │ H0 │ H1 │ H2 │ H3 │  ← 多个预测 head
    └─┬──┴─┬──┴─┬──┴─┬──┘
      │    │    │    │
   next t   t+1  t+2  t+3   ← 并行预测多个位置
```

**H0 = 原始的语言模型头（预测 next token），H1-Hk = 额外加的 head 分别预测第 2, 3, ..., k+1 个位置**

**Medusa-1**：冻结 LLM backbone，只训练多个 MLP head
**Medusa-2**：jointly train heads + LLM（对 backbone 做轻微 LoRA 微调）

**Eagle**：类似 Medusa，但每个 head 不仅基于 final hidden state，还基于前面 head 的预测 embedding

```
Eagle 结构（考虑依赖关系）：
H0: f(h_last)
H1: f(h_last + embed(H0_pred))
H2: f(h_last + embed(H1_pred))  
...
这种"自回归式的并行"比 Medusa 的独立 head 预测更准
```

**优缺点**：
- ✅ 不需要额外加载大模型（一个模型搞定）
- ✅ 训练成本低（只训练小 head）
- ✅ 推理时 model parallelism 友好
- ❌ 需要通过 tree attention 处理多个候选路径（beam search-like）
- ❌ head 数量有限（通常 3-5 个），猜测范围受限

### 2.5 Lookahead Decoding（n-gram 猜测）

基于 n-gram 缓存：记录之前生成的 n-gram 序列，遇到重复的 prompt/上下文时复用。

```
实现：
1. 维护一个 n-gram cache（如 4-gram）
2. 在当前生成前缀中找到最长匹配的 n-gram
3. 用匹配的后缀作为草稿候选
4. 大模型验证

优势：
- 零额外模型开销
- 对重复性高的场景（代码生成、模板化文本）特别有效

劣势：
- 对原创性内容（自由创作）几乎无效
- 纯粹基于频次，不包含语义信息
```

---

## 3. 性能分析

### 3.1 理论加速比公式

给定草稿模型每步耗时 `T_draft`，目标模型每步耗时 `T_verify`（验证步并行前向），草稿长度 γ，接受率 α：

```
单次推测循环的期望产出 token 数：
  E[N] = (1 - α^γ) / (1 - α)    ← 几何分布期望

单次推测循环耗时：
  T_loop = γ × T_draft + T_verify

加速比：
  Speedup = T_target_step / T_loop_per_token
          = T_target / ( (γ × T_draft + T_verify) / E[N] )
          = E[N] × T_target / (γ × T_draft + T_verify)

若 T_draft << T_verify（草稿极快）：
  Speedup ≈ E[N]

若 γ 足够大（草稿长度大）：
  Speedup ≈ 1 / (1 - α)          ← 主要受 α 限制
```

**数值示例**：

| 草稿模型 | γ | α | E[N] | T_draft/T_target | 理论加速 |
|---------|---|---|------|-----------------|---------|
| 1.5B → 70B | 5 | 0.8 | 3.36 | 0.02 | ~2.8× |
| 1.5B → 70B | 8 | 0.7 | 3.04 | 0.02 | ~2.5× |
| 早退 6/32 层 | 4 | 0.6 | 2.36 | 0.25 | ~1.5× |
| Medusa-3 head | 3 | 0.75 | 2.63 | 0.03 | ~2.4× |

### 3.2 实际加速效果

业界报告的实际效果（不同模型/场景）：

| 方案 | 模型规模 | 场景 | 实测加速 |
|------|---------|------|---------|
| Leviathan et al. | Chinchilla 70B | 阅读理解 | 2.0-2.5× |
| Medusa-2 | LLaMA-2 13B | MT-Bench | 2.3× |
| Eagle | Vicuna 13B | 对话 | 2.0-2.7× |
| vLLM speculation | LLaMA-2 70B | ShareGPT | 1.8-2.1× |
| Lookahead | LLaMA-2 7B | 代码生成 | 1.3-2.5× |

**接受率 α 的经验规律**：
- 简单任务（翻译、摘要）→ 接受率 0.7-0.9
- 复杂推理（数学、编程）→ 接受率 0.4-0.7
- 创造性写作 → 接受率 0.3-0.5

### 3.3 显存开销

```
额外显存 = 草稿模型显存（或早退头参数）+ verification buffer

场景一：独立草稿模型（1.5B → 70B）
  - 额外加载 1.5B 参数（FP16 ≈ 3GB）
  - 需要存储草稿的 KV Cache（较小）
  - 总计额外约 3-5GB

场景二：Self-Speculative（浅层早退）
  - 只需要额外的早退分类头参数（极小）
  - 但需要保留中间层的 hidden states（activation memory）
  - 额外约 0.5-1GB

场景三：Medusa/Eagle
  - Medusa heads: MLP 参数极少（< 100MB）
  - 但需要 tree attention 的 beam path 缓存
  - 额外约 0.2-0.5GB
```

---

## 4. 工程实现要点

### 4.1 草稿模型选择

| 策略 | 推荐场景 | 注意事项 |
|------|---------|---------|
| **同族小模型** | LLaMA-7B → LLaMA-70B | 词汇表天然对齐，分布相似，接受率高 |
| **剪枝/蒸馏模型** | 从目标模型蒸馏 | 分布最接近，但额外训练成本 |
| **N-gram 模型** | 重复性内容 | 零参数开销，但只在局部有效 |
| **共享部分层** | 显存受限 | 显存节省但无法独立流水 |

**词汇表对齐（Vocabulary Alignment）**：草稿和目标模型必须使用相同的 tokenizer 和 vocabulary，否则无法直接拒绝采样。这是实践中最大的工程约束。

### 4.2 推测长度 γ 的自适应

γ 不是固定值，需要根据当前接受率动态调整：

```
常见策略：
1. 滑动窗口统计：维护最近 N 步的平均接受率 α_avg
2. 目标 γ：使得期望产出 token 数 E[N] 最大
3. 调整公式：若 α_avg 高 → 增大 γ；α_avg 低 → 减小 γ
4. 上限约束：γ ≤ max_spec_tokens（通常 5-10）

经验值：
- 首次生成：从 γ=5 开始
- 计算效率最优时，γ 约为 1/(1-α) 左右
```

### 4.3 批处理时的推测调度

在在线服务（vLLM/SGLang）中，推测解码需要与 continuous batching 协同：

```
Batch 中的每个请求都有自己的推测状态：
  - 每个请求在推测阶段独立用草稿模型生成 γ 个 token
  - 但所有请求的验证阶段可以合并为一个大的 batch
  
调度策略：
1. 对 batch 中所有 pending 的请求，串行调用草稿模型
   （草稿模型小，串行开销可接受）
2. 将所有请求的候选 token（sequence_length × γ）拼接
3. 一次大模型前向，并行验证所有候选
4. 每个请求独立做拒绝采样

关键优化：
- 草稿阶段的 KV Cache 管理（用草稿模型的 KV Cache，更小更快）
- 验证阶段的 KV Cache 共享：prefix caching 对 spec 场景尤其重要
```

### 4.4 vLLM 中的推测解码实现

vLLM 从 v0.4.0 开始支持 speculative decoding，核心架构：

```
vLLM SpecDecodeEngine
├── DraftModelRunner（草稿模型运行器）
│   ├── 可以是独立的 LLM 模型
│   ├── 或 Medusa/Eagle heads
│   └── 或 n-gram 匹配器
├── TargetModelRunner（目标模型运行器）
│   └── 与常规 vLLM 使用相同 engine
└── SpecDecodeWorker
    ├── 协调草稿和验证阶段
    ├── 管理推测长度 γ 的自适应调整
    └── 处理拒绝采样逻辑
```

**vLLM 实现的特色**：
- 支持多种草稿类型（model / medusa / ngram / eagle）
- 通过 `--speculative-model` 参数指定草稿模型
- 草稿模型的 KV Cache 独立管理，不占主模型显存池
- 与 PagedAttention 完全兼容：验证阶段的 KV block 映射直接复用

**启动示例**：
```bash
# 标准推测解码
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-2-70b-hf \
    --speculative-model lmsys/vicuna-7b-v1.3 \
    --num-speculative-tokens 5 \
    --speculative-draft-tensor-parallel-size 1

# Medusa
python -m vllm.entrypoints.openai.api_server \
    --model lmms-lab/Medusa-2-Llama-2-7B \
    --speculative-model-type medusa
```

### 4.5 与 PagedAttention / KV Cache 的配合

推测解码和之前学的内容深度配合：

```
┌───────────────────────────────────────────────────┐
│                  推理 Pipeline                     │
│                                                     │
│  [Prefill] → [Draft × γ] → [Verify × 1] → [output]│
│     ↑              ↑           ↑                   │
│  PagedAttention  草稿 KV  验证 KV（复用前缀缓存）  │
│  (连续+去碎片)   (小block)  (与prefill共享block)   │
└───────────────────────────────────────────────────┘
```

1. **草稿阶段的 KV Cache**：草稿模型生成的 K 步，每步更新草稿模型的 KV Cache
   - 草稿模型 block_size 可以设小（如 8），减少碎片
   - 草稿流水不参与主 vLLM block table 管理

2. **验证阶段的 KV Cache**：
   - 被接受的 token → 接续到主模型 KV Cache
   - PagedAttention 的 copy-on-write 机制在这里天然适配：
     被接受的 token 只需增加 block 引用计数
   - **Prefix caching 的完美应用场景**：候选序列与前缀大量重叠

3. **拒绝后的回滚**：
   - 拒绝点之后的所有 KV block 可以整体释放
   - 被拒绝的 token 在 block table 中分配了但未 commit → 直接回收

---

## 5. Medusa / Tree Attention 深入

Medusa 的核心工程难点在于**候选路径管理**。多个 head 各自预测多个 token，
它们的组合形成一棵候选树。

```
示例：Medusa-2 (head H0, H1, H2)
H0 预测 3 个可能的 next token:  [A, B, C]
H1 在 A 的基础上预测:            [D, E]
H1 在 B 的基础上预测:            [F]
H2 在 D 的基础上预测:            [G, H]

形成的候选树：
        A ── D ── G
       /    └── H
root ──B ── F
       └── C
       
共 6 条候选路径，但 Attention 只用一次（tree attention）
```

**Tree Attention**：用 special attention mask 让每个 token 只能看到自己的"祖先"位置，实现单次前向验证所有路径。

```
Tree Attention Mask:
      0   A   B   C   D   E   F   G   H
0     ✓   ✓   ✓   ✓   ✓   ✓   ✓   ✓   ✓   ← prompt 位置
A         ✓         ✓   ✓
B             ✓             ✓
C                 ✓
D                     ✓         ✓   ✓
E                         ✓
F                             ✓
G                                 ✓
H                                     ✓
```

通过 tree attention，一条 prompt + 全部候选 token 可以**一次前向**完成验证，
极大减少了验证阶段的串行开销。

---

## 6. 动手实验 Idea

### 实验 1：vLLM Speculative Decoding 对比测试

**目标**：在本地验证推测解码的实际加速效果。

```
实验步骤：
1. 环境准备
   pip install vllm>=0.4.0
   # 准备目标模型和草稿模型（可以用 LLaMA-7B 当目标，TinyLLaMA-1.1B 当草稿）

2. 启动基准（无推测）
   python -m vllm.entrypoints.openai.api_server \
       --model TinyLlama/TinyLlama-1.1B-Chat-v1.0

3. 启动推测模式
   python -m vllm.entrypoints.openai.api_server \
       --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
       --speculative-model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
       --num-speculative-tokens 5
   # 这里刻意用同模型：观察自推测（Self-Speculative）的加速效果

4. 测试负载
   - 批量发送 50 个不同 prompt
   - 记录: latency per token, total decode time, acceptance rate
   - 改变 batch size (1, 4, 8, 16) 观察推测效果的 batch 缩放性
   
5. 对比分析
   - 加速比 vs 理论值
   - 接受率随 prompt 类型的变化
   - batch size 增大时推测收益的变化趋势
```

**预期发现**：
- batch=1 时，推测解码加速最明显（~2×）
- batch 增大后，推测收益递减（因为原始 batch decode 已经利用了 GPU 并行性）
- 小模型的 self-speculative 接受率高于大模型（小模型 token 预测更容易）

### 实验 2：自定义草稿模型 + 接受率分析

**目标**：深入理解接受率 α 的影响因素。

```
实验步骤：
1. 选三组模型对
   a) 同族: llama-13b-draft + llama-13b-base（用相同规模看接受率上限）
   b) 跨族: pythia-1.4b + llama-13b（词汇表不同 → 需要做映射）
   c) 蒸馏: 从目标模型蒸馏的草稿（如果有条件）

2. 编写评估脚本
   # 伪代码
   for each pair:
       for γ in [1, 2, 3, 5, 8, 10]:
           for each prompt in test_set:
               draft_output = draft_model.generate(prompt, max_new_tokens=γ)
               target_logits = target_model.verify(prompt + draft_output)
               acceptance = compute_acceptance_rate(draft_output, target_logits)
               record(γ, acceptance, num_accepted_tokens)

3. 分析
   - 接受率随 γ 增长如何衰减？（通常是幂律衰减）
   - 不同 prompt 类型的接受率差异
   - 找到最优 γ 的拐点

4. 可视化
   - 绘制 acceptance_rate vs γ 曲线
   - 绘制实际加速比 vs γ 曲线
   - 标出最优 γ 点
```

---

## 7. 总结与展望

### 7.1 技术决策树

```
Q: Token-to-token 延迟太高，想减少 decode 步数？
├─ 有多余显存？
│  ├─ 是 → 独立草稿模型法（标准 Speculative Decoding）
│  └─ 否 → Self-Speculative（早退层）+ 跳过层
└─ 能修改模型？
   ├─ 是 → Medusa/Eagle（训练轻量 head，效果最好）
   └─ 否 → Lookahead Decoding（零成本但范围有限）
```

### 7.2 与之前课程的配合

| 技术 | 与 Speculative Decoding 的协同 |
|------|-------------------------------|
| **KV Cache (01)** | 草稿模型有自己的小 KV Cache；验证阶段复用 prefix cache |
| **量化 (02)** | 草稿模型可以更激进量化（INT4），验证模型保持 FP16/INT8 |
| **分布式推理 (06)** | 草稿模型可以跑在 CPU 或边缘设备，验证模型在 GPU |
| **PagedAttention (07)** | 验证阶段的 block table 管理天然适配推测的回滚/接续 |
| **Continuous Batching** | 同一 batch 中混入常规请求和推测请求，调度复杂度增加 |

### 7.3 未来方向

1. **草稿模型即服务**：草稿模型作为独立微服务，多目标模型共享
2. **动态 γ 的强化学习**：用 RL 学习最优推测长度
3. **多模态推测**：视觉 token 也能用推测解码
4. **投机式并行 Pipeline**：草稿和验证阶段流水重叠

---

## 参考文献

1. Leviathan, Y., Kalman, M., & Matias, Y. (2022). Fast Inference from Transformers via Speculative Decoding. ICML 2023.
2. Chen, C., et al. (2023). Accelerating Large Language Model Decoding with Speculative Decoding.
3. Cai, T., et al. (2024). Medusa: Simple LLM Inference Acceleration Framework with Multiple Decoding Heads. ICML 2024.
4. Li, Y., et al. (2024). Eagle: Speculative Sampling with Low-Rank Approximation.
5. Fu, Y., et al. (2024). Lookahead Decoding: Accelerating LLM Inference with n-gram Speculation.
6. Stern, M., et al. (2018). Blockwise Parallel Decoding for Deep Neural Network. (思想先驱)
7. vLLM Blog: Speculative Decoding in vLLM (2024).
