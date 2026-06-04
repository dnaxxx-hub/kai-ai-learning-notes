# LLM推理优化 #10：MoE推理优化与稀疏门控

> 系列：LLM推理优化 | 第10课 | 2026-05-13

## 概述

混合专家模型（Mixture of Experts, MoE）是当前大语言模型扩展的核心架构。与传统的Dense模型不同，MoE通过稀疏激活机制，在不显著增加计算量的前提下大幅提升模型参数量。Mixtral 8x7B以45B总参数仅12.9B激活参数的表现，展示了MoE在"更多知识、相同计算"方面的巨大潜力。

然而MoE给推理带来了一系列独特的挑战：所有Expert必须加载到显存（显存占用几乎是Dense的2倍），稀疏路由导致的负载不均衡，以及Expert之间复杂的通信模式。本课系统梳理MoE推理优化的核心技术，从架构原理到工程实践，覆盖Expert并行、稀疏门控优化、容量因子调优、Expert offloading等关键主题。

---

## 1. MoE架构基础

### 1.1 标准MoE层结构

MoE层的核心思想是将一个FFN层替换为 **N个并行的Expert FFN**，并通过一个 **Gating Network（门控网络）** 来决定每个Token由哪些Expert处理。

```
输入 Token x
     │
     ▼
┌─────────────┐
│ Gating      │──→ 路由权重 w₁, w₂, ..., wₙ
│ Network     │     （softmax over N experts）
└─────────────┘
     │
     ▼  Top-K 选择
┌─────┴─────┐
│ Expert 1  │──→ y₁ = FFN₁(x)   │
│ Expert 2  │──→ y₂ = FFN₂(x)   │← 仅选中的K个Expert
│    ...     │                   │   被激活计算
│ Expert N  │──→ yₙ = FFNₙ(x)   │
└───────────┘
     │
     ▼  加权求和
输出 = Σᵢ wᵢ · yᵢ
```

**数学表达**：
- Gating输出：`g(x) = softmax(TopK(W_g · x, k))`
  - `W_g` 是门控权重矩阵，维度 `[hidden_dim, N]`
  - TopK保留最大的K个值，其余设为 -∞（softmax后为0）
- Expert输出：`y = Σᵢ g(x)ᵢ · FFNᵢ(x)`
  - `FFNᵢ` 是第i个Expert的前馈网络

### 1.2 Token选择策略

#### Top-2 Routing（最常见）
- 每个Token选择权重最高的2个Expert
- Gating输出维度为N（Expert总数），仅2个非零元素
- 优点：负载均衡较好，训练稳定
- 代表模型：Mixtral 8x7B（8个Expert，Top-2）

#### Top-1 Routing（Switch Transformer）
- 每个Token只选择1个Expert
- Gating输出仅1个非零元素
- 优点：计算量最小，通信开销最低
- 缺点：负载均衡更难，专业度可能下降
- 代表模型：Switch Transformer

**为什么Top-2最常见？** Top-1每个token只用一个Expert，路由错误代价大；Top-3及以上路由稀疏性降低，计算收益递减。Top-2是稀疏性与鲁棒性的最佳平衡点。

### 1.3 Load Balancing Loss（负载均衡损失）

MoE训练的核心难题是 **路由坍缩**：门控网络倾向于把所有Token都路由到少数几个"强Expert"，导致其余Expert"失活"。为此引入辅助损失：

**辅助负载均衡损失**：
```
L_aux = α · N · Σᵢ fᵢ · Pᵢ
```
- `fᵢ`：Expert i 被分配的Token比例
- `Pᵢ`：门控网络对Expert i的平均概率
- `N`：Expert总数
- `α`：权重系数（典型值0.01）

当分布均匀时，`Σ fᵢ · Pᵢ` 接近 1/N；不均匀时该值增大。`N` 系数保证损失量级与Expert数目无关。

#### 专家容量约束（Expert Capacity）
除了辅助损失，还引入硬约束——每个Expert最多处理的Token数：

```
capacity = CF · (B/N) · K
```
- `B`：总Token数（batch_size × sequence_length）
- `N`：Expert总数
- `K`：Top-K值
- `CF`：容量因子（Capacity Factor），典型值1.0~1.25

**容量溢出的处理**：
- 超出容量的Token被 **丢弃（dropped）**——当前层不处理，直接传入残差连接
- 或者在容量允许时由其他Expert接管

### 1.4 对比Dense模型

| 特性 | Dense模型 | MoE模型 |
|------|-----------|---------|
| **总参数量** | 固定 | 约Dense的2x~8x（取决于Expert数） |
| **激活参数量** | ≈总参数 | 约与同等FLOPs的Dense模型相当 |
| **单Token计算量** | 固定 | 仅K/N的Expert被激活 |
| **显存占用** | 所有参数 | 所有Expert + 门控（很大） |
| **Batch Size受限因素** | 显存 | 显存 + Expert容量 |
| **通信开销** | 无额外通信 | All-to-All通信（Expert间） |
| **训练效率** | 稳定 | 负载均衡是关键 |
| **推理延迟** | 可预测 | 受负载不均衡影响 |

**关键洞察**：MoE的核心优势是"参数效率"——在相同FLOPs下拥有更多参数（更多知识），但代价是显存和通信开销大幅增加。

---

## 2. MoE推理挑战

### 2.1 显存压力

MoE推理的显存压力是核心瓶颈，原因在于**所有Expert必须加载到显存中**，即使每个Token只激活其中的K个。

**以Mixtral 8x7B为例（纯推理，无优化措施）**：
- 总参数：~45B（8 × 7B = 56B - 共享层 ≈ 45B）
- 激活参数：~12.9B（每个Token只激活2个Expert）
- 显存占用（FP16）：约45B × 2B ≈ **90GB**
- 对比同等FLOPs的Dense模型：约13B × 2B ≈ **26GB → 3.5x差距**

**这意味着什么**？
- 单张A100 80GB勉强能放一个MoE模型（45B参数刚好接近极限），但如果加上KV Cache（#1课程）和中间激活，基本不可能单卡运行
- 必须依赖多卡分布式推理（Expert Parallelism）

### 2.2 Batch Size受限

Dense模型中，batch size只受显存总量限制，可以自由增加。MoE中每个Expert处理Token数量由容量因子决定：

```
Expert容量 = CF · (B/N) · K
```

假设总Token数B=4096，Expert数N=8，K=2，CF=1.0：
- 每个Expert理想容量 = 1.0 × (4096/8) × 2 = 1024个Token
- 但负载不均衡可能导致某个Expert收到1500个Token，其中476个被丢弃

**Token丢弃的影响**：被丢弃的Token直接跳过该MoE层，等价于丢失模型容量。高丢弃率下模型质量显著下降。

### 2.3 通信瓶颈

MoE推理涉及两种核心通信模式：

#### All-to-All通信（Expert并行核心）
当Expert分布在不同GPU上时，需要在门控计算后将Token发送到对应Expert所在的GPU，计算完成后再返回：

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│  GPU 0  │     │  GPU 1  │     │  GPU 2  │
│ Token A │     │ Token B │     │ Token C │
│ Token D │     │         │     │         │
└────┬────┘     └────┬────┘     └────┬────┘
     │               │               │
     ▼               ▼               ▼
┌─────────────────────────────────────────┐
│         All-to-All 通信阶段              │
│  GPU 0 → 发送需Expert 2处理的Token到GPU2 │
│  GPU 1 → 发送需Expert 0处理的Token到GPU0 │
│  GPU 2 → 发送需Expert 1处理的Token到GPU1 │
└─────────────────────────────────────────┘
     │               │               │
     ▼               ▼               ▼
┌─────────┐     ┌─────────┐     ┌─────────┐
│  GPU 0  │     │  GPU 1  │     │  GPU 2  │
│ Expert 0 │     │ Expert 1 │     │ Expert 2 │
│ Expert 3 │     │         │     │         │
└────┬────┘     └────┬────┘     └────┬────┘
     │               │               │
     ▼               ▼               ▼
┌─────────────────────────────────────────┐
│        All-to-All 反向通信阶段            │
│  处理完的Token返回原始GPU                │
└─────────────────────────────────────────┘
```

**All-to-All vs All-Reduce**：Dense模型（#6分布式推理）使用All-Reduce同步梯度，通信量固定且可预测。MoE推理的All-to-All通信量与路由决策相关，每个Token去哪个GPU是不确定的，导致通信模式动态变化。

**通信开销占比**：在部署测试中，All-to-All通信可占总推理延迟的**20%~40%**（8卡场景），Expert数越多、单卡Token越少时占比越高。

### 2.4 负载不均衡

即使有负载均衡损失约束，推理时的实时负载仍可能严重不均衡：

**热门Expert现象**：
- 部分Expert成为"通用专家"（如处理"the"、"a"等高频Token）
- 部分Expert成为"专业专家"（仅处理特定领域Token，如代码、数学）
- 推理时通用Expert可能超过容量，而专业Expert闲置

**负载不均衡的实际影响**：

| 场景 | Expert 0 | Expert 1 | Expert 2 | Expert 3 | 丢弃率 |
|------|----------|----------|----------|----------|--------|
| 均衡 | 512 | 512 | 512 | 512 | 0% |
| 轻度不均衡 | 600 | 500 | 480 | 452 | 3% |
| 严重不均衡 | 800 | 450 | 350 | 232 | 18% |
| 极端（无负载均衡） | 1200 | 280 | 200 | 152 | 37% |

*假设：总Token 2048，N=4，K=2，CF=1.0，Expert容量=1024*

---

## 3. 推理优化技术

### 3.1 Expert并行（Expert Parallelism, EP）

Expert并行是MoE推理的最核心优化手段。其思路：将N个Expert分布到G个GPU上，每个GPU负责N/G个Expert的计算。

**EP的关键设计**：
- **Token分发**：门控网络在每个GPU上独立计算，然后通过All-to-All将Token发送到对应Expert所在的GPU
- **本地计算**：每个GPU在自己的Expert上计算分配的Token
- **结果收集**：All-to-All将计算结果送回原始GPU
- **门控副本**：门控网络在所有GPU上都有一份副本（参数极少，不值一提）

**Expert分布策略**：
```
GPU 0: Expert 0, Expert 1   ← 每个GPU负责 2/8 = 25% 的Expert
GPU 1: Expert 2, Expert 3
GPU 2: Expert 4, Expert 5
GPU 3: Expert 6, Expert 7
```

**EP + TP混合**：实际部署中，EP常与Tensor Parallelism (TP, #6课程) 混合使用。
- EP负责Expert维度切分
- TP负责单个Expert内部的矩阵乘法切分
- 典型配置：4路EP × 2路TP = 8卡，兼顾通信效率和Expert容量

**EP的通信模式图解**（以4卡、8Expert、Top-2为例）：

```
                    All-to-All 通信（Token分发）
                    ┌────────────────────────────┐
                    │                            │
    GPU0 ───────────┤  Token路由矩阵（稀疏）        ├─────────── GPU0
    (Expert 0,1)   │  GPU0→GPU0: 需要E0/E1的Token│           (接收Token)
                    │  GPU0→GPU1: 需要E2/E3的Token│
    GPU1 ───────────┤  GPU0→GPU2: 需要E4/E5的Token├─────────── GPU1
    (Expert 2,3)   │  GPU0→GPU3: 需要E6/E7的Token│
                    │                            │
    GPU2 ───────────┤  每个GPU的发送量取决于路由    ├─────────── GPU2
    (Expert 4,5)   │  决策，动态变化              │
                    │                            │
    GPU3 ───────────┤  通信量 = 每个Token的hidden  ├─────────── GPU3
    (Expert 6,7)   │  × 需要跨卡传输的Token数     │
                    └────────────────────────────┘
                                │
                                ▼
                    反向All-to-All（结果返回）
                    每个GPU将处理完的Token发回
                    原始GPU进行加权求和
```

**关键优化**：All-to-All通信可以通过 **NVLink/NVSwitch** 加速。在H100 SXM上8卡NVLink带宽可达900GB/s，将通信延迟降到最低。

### 3.2 动态容量（Dynamic Capacity）

固定容量因子（CF）的问题：设置大了浪费显存（Expert分配过多Token槽位），设置小了丢弃率高。

**动态容量策略**：
- 不预先分配固定容量，而是根据该层实际路由结果分配
- 每个Expert的实际容量 = max(理想容量, 实际路由到的Token数)
- 或使用"软容量"：允许超容量一定比例（如10%）而不丢弃

**实践经验**：
- 推理时CF可设为1.25~1.5（比训练时大），因为推理通常batch较小，容量浪费可接受
- 大batch推理时CF应适当降低（1.0~1.15），避免显存紧张
- 更激进的方案：**无容量限制** + Token优先级排队

### 3.3 Token Dropping与优先级排队

当Expert过载时，需要决定哪些Token被丢弃（或延迟处理）。好的策略可以最大化模型质量。

**优先级排队策略**：
1. 所有Token按门控权重降序排列
2. 每个Expert按分配到的Token权重排序
3. 权重最低的Token优先丢弃

**负载感知路由**：门控网络在计算时不仅考虑Token本身的embedding，还考虑当前各Expert的负载状态：

```
g'(x) = g(x) + bias · load_penalty(e)
```

其中 `load_penalty(e)` 是Expert e当前负载的惩罚项，bias为调整系数。

**不丢弃策略**：一些部署选择宁肯让延迟变长也不丢弃Token。做法是动态调整容量上限，让慢的Expert占用更多时间，最终以最慢Expert的完成时间作为该层延迟。

### 3.4 Expert负载预测

通过预测下一层的Expert负载分布，可以提前进行容量调整，减少All-to-All通信的等待时间。

**EWMA预测（指数加权移动平均）**：
```
predicted_load(e)_t = β · actual_load(e)_{t-1} + (1-β) · predicted_load(e)_{t-1}
```
- `β` 为平滑系数，典型值0.7~0.9
- 基于历史负载预测当前负载
- 适用于负载分布变化较慢的场景

**序列级预测**：同一序列中连续Token倾向于分配到相同Expert（连续性假设），可以利用前一个Token的路由结果预测当前Token。

### 3.5 流水线并行 + EP混合

纯EP方案的问题：All-to-All通信发生在每个MoE层之间，Transformer模型中如果有N个MoE层，则需要进行N次All-to-All。

**PP+EP混合策略**：
```
Pipeline Stage 0:  Embedding + L0-L7  MoE    (GPU 0-3, EP=4)
                                       ↓ All-to-All in stage
Pipeline Stage 1:  L8-L15 MoE                (GPU 4-7, EP=4)
                                       ↓ 
Pipeline Stage 2:  L16-L23 MoE               (GPU 8-11, EP=4)
                                       ↓
Pipeline Stage 3:  L24-L31 MoE + Output      (GPU 12-15, EP=4)
```

- 每个PP Stage内部包含多个MoE层，Expert分布在Stage内GPU上
- All-to-All只在Stage内部进行，Stage之间通过PP通信（更可预测）
- 适合超大规模MoE模型（超过100B参数）
- DeepSpeed-MoE 和 Megatron-LM 均支持此模式

---

## 4. 稀疏门控优化

门控网络（Gating Network）是MoE架构的"大脑"，负责决定每个Token去哪个Expert。门控网络的质量直接影响模型性能和负载均衡。

### 4.1 Top-2门控的细节

标准Top-2门控的计算流程：

```
1. logits = x · W_g          # [batch, hidden] × [hidden, N] → [batch, N]
2. logits +=噪声 (训练时)     # Gaussian noise × softplus(可学习参数)
3. weights = softmax(logits)  # [batch, N] 归一化
4. top_k_vals, top_k_idx = topk(weights, k=2)  # 取最大的2个
5. 非Top-2位置置0
6. 重新归一化：weights = weights / sum(weights)
```

**噪声扰动（Noise）**：训练时在logits上添加可学习的高斯噪声，鼓励门控网络探索不同Expert，避免过早收敛到不平衡的解。推理时噪声关闭。

**Noisy Top-K Gating**（原始MoE论文）：
```
noise = N(0, 1) · softplus(W_noise · x)     # 可学习噪声
logits_noisy = logits + noise
weights = softmax(keep_top_k(logits_noisy, k))
```

### 4.2 辅助负载均衡损失的权重调优

辅助损失的权重 `α` 是关键超参数：

| α值 | 负载均衡 | 模型质量 | 适用场景 |
|-----|---------|---------|---------|
| 0.001 | 弱 | 最高 | 追求极致模型质量，可容忍轻度不均衡 |
| 0.01 | 中 | 高 | 默认值，大多数场景推荐 |
| 0.1 | 强 | 可能轻微下降 | 训练不稳定或Expert数量很大时 |
| 0.5 | 很强 | 明显下降 | 仅测试用，实际不用 |

**实践建议**：从α=0.01开始，观察负载均衡指标（Expert利用率方差），若不均衡则逐步增大到0.05~0.1。

### 4.3 Z-loss正则化

Z-loss是Google在GLaM论文中提出的稳定训练技巧，直接在门控的softmax logits上添加正则化：

```
L_z_loss = β · log(Σ_j exp(z_j))²
```

其中 z_j 是门控logits，β是系数（典型值0.001）。

**Z-loss的作用**：
- 防止门控logits过大（会导致softmax输出极端化）
- 保持门控的"熵"在合理范围
- 训练稳定性显著提升，允许使用更大学习率

对比辅助损失：辅助损失调节Expert间的负载分布，Z-loss调节门控本身的数值稳定性，两者互补。

### 4.4 容量因子(CF)调优

容量因子是MoE推理的关键旋钮，直接影响延迟、显存和模型质量。

**CF的实践经验**：

- **训练阶段**：CF=1.0~1.25 —— 越低越快但丢弃率高，越高越慢但质量好
- **推理阶段**：CF=1.0~1.5 —— 小batch用高CF（1.25~1.5），大batch用低CF（1.0~1.15）

**CF调优步骤**：
1. 从CF=1.25开始
2. 运行一批测试数据，统计Token丢弃率
3. 如果丢弃率超过1%，增大CF（到1.5）
4. 如果丢弃率为0%，尝试降低CF（到1.0）以节省显存
5. 监控P99延迟：降低CF会减少Expert空闲等待，但可能增加丢弃导致的retry

**丢弃率vs质量的实证数据**（来自Mixtral部署实践）：

| CF值 | Token丢弃率 | P99延迟 | 模型质量（MMLU） |
|------|-----------|--------|----------------|
| 1.0 | ~3.5% | 基准 | 65.2(-0.8) |
| 1.1 | ~1.2% | +3% | 65.6(-0.4) |
| 1.25 | ~0.1% | +8% | 65.9(-0.1) |
| 1.5 | <0.01% | +20% | 66.0(基准) |

*结论：CF=1.25是延迟-质量权衡的最佳点。*

### 4.5 Switch Transformer：单Expert + 更激进稀疏

Switch Transformer（Google, 2021）提出了Top-1路由方案：

**与Top-2的核心差异**：
- 每个Token只激活1个Expert（K=1）
- 计算量减半，但路由"选择精度"降低
- 每个Expert的容量：`capacity = CF · (B/N)`（去掉K项）
- 对负载均衡更敏感

**Switch的优点**：
- 计算效率更高（50%的FFN计算量节省）
- 通信量减半（All-to-All传输的hidden维度少一半）
- 适合超大规模部署（如1.6T参数的Switch-C）

**Switch的缺点**：
- 路由错误一次就损失整个FFN层
- 负载不均衡更严重
- 通常需要更大的CF（1.2~1.5）

---

## 5. 工程实践

### 5.1 DeepSpeed-MoE

微软DeepSpeed提供了工业级的MoE训练和推理方案。

**DeepSpeed-MoE核心机制**：

- **EP + ZeRO-3混合**：
  - Expert参数由EP管理：分布在不同GPU上
  - 非Expert参数（Attention层、Embedding层）由ZeRO-3管理：跨GPU分片
  - 推理时ZeRO-3参数在forward时动态All-Gather，然后丢弃

- **分层All-to-All**：DeepSpeed将All-to-All通信与计算重叠（overlap），在Expert计算的同时进行下一批Token的传输

- **动态Token调度**：自动监测Expert负载，调整路由策略

- **典型配置示例**（32卡部署175B MoE）：
  ```
  模型参数：175B（16 Expert，每Expert约11B）
  激活参数：22B（Top-2）
  分布式策略：8路EP × 4路TP
  显存分配：每卡约48GB参数 + KV Cache
  ```

### 5.2 Megablocks：块稀疏矩阵乘

Megablocks是斯坦福提出的MoE计算加速技术，核心思想是将多个小矩阵乘法合并为大块连续运算。

**问题**：标准MoE中，每个Token去不同的Expert，导致Expert的计算是分散的小矩阵乘（M×N × N×K，其中M很小），GPU利用率低。

**Megablocks方案**：
- 将所有分配到同一Expert的Token合并成"块"
- 对每个Expert，将其Token块组织成连续的矩阵
- 使用块稀疏矩阵乘（Block-Sparse MatMul）一次性计算

```
标准方式：
  Expert 0: Token[0, 3, 7] → 3个token × hidden → 3 × 4096 × 4096  ← 小矩阵，低利用率
  Expert 1: Token[1, 5]    → 2个token × hidden → 2 × 4096 × 4096  ← 更小

Megablocks方式：
  ┌──────────────────────────────────────┐
  │ Expert 0块: [tok0; tok3; tok7] × W0  │  ← (3 × 4096) × (4096 × 14336)
  ├──────────────────────────────────────┤
  │ Expert 1块: [tok1; tok5] × W1        │  ← (2 × 4096) × (4096 × 14336)
  ├──────────────────────────────────────┤
  │ 用块稀疏矩阵统一调度，减少kernel launch│
  └──────────────────────────────────────┘
```

**收益**：Megablocks可将MoE的FFN计算速度提升2~3倍（尤其在GPU利用率较低的batch场景）。

### 5.3 vLLM MoE支持

vLLM（#7课程）近期加入了对MoE模型的支持，主要包括：

**Triton MoE Kernel**：
- 用Triton手写的MoE门控 + 稀疏矩阵计算
- 支持动态路由、Top-K选择
- 相比于原生PyTorch实现，提速约1.5~2x

**动态调度机制**：
- 在PagedAttention KV Cache管理基础上，增加Expert内存池
- 根据当前batch的Expert分布动态分配Expert计算资源
- 支持请求级和序列级的Expert负载感知调度

**配置示例**（vLLM运行Mixtral 8x7B）：
```bash
# vLLM 0.4.0+ 原生支持Mixtral
python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mixtral-8x7B-Instruct-v0.1 \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.9
```

### 5.4 Mixtral 8x7B案例分析

Mixtral 8x7B是MoE推理优化的最佳案例模型。

**核心规格**：
- 总参数量：~45B（8 × 7B - 共享部分）
- 激活参数：~12.9B（Top-2路由，每token激活2个Expert）
- 层数：32层
- 每层Expert数：8
- 每个Expert的FFN维度：14336（hidden_dim 4096）
- 上下文长度：32K tokens

**参数量/FLOPs/显存深度分析**：

| 项目 | Mixtral 8x7B | 同FLOPs Dense (13B) | 比率 |
|------|-------------|-------------------|------|
| 总参数 | ~45B | ~13B | 3.5x |
| 激活参数（单token） | ~12.9B | ~13B | 1.0x |
| 存储（FP16） | 90GB | 26GB | 3.5x |
| 单token FLOPs | ~26B FLOPs | ~26B FLOPs | 1.0x |
| KV Cache（8K seq, batch=1） | ~2GB | ~2GB | 1.0x |
| Expert并行通信量（每MoE层） | ~8MB | 0 | N/A |

**部署实践**：
- 4×A100 80GB（4路EP）：每卡约22.5B参数，~45GB
- 8×A100 40GB（8路EP）：必须配合ZeRO-3或int4量化
- All-to-All通信：每MoE层约8MB数据跨卡传输（hidden_dim × batch_tokens）
- 实际吞吐：4卡部署下约 40~60 tokens/s（batch=1），大batch下可达 1000+ tokens/s

### 5.5 DeepSeekMoE：细粒度Expert分割 + 共享Expert

DeepSeek（深度求索）在DeepSeekMoE架构中提出了两个关键创新：

**细粒度Expert分割（Fine-Grained Expert Segmentation）**：
- 将标准Expert拆分为更小的Expert单元
- DeepSeekMoE 16B：每个MoE层有64个细粒度Expert（每个只约0.1B参数）
- 激活Expert数量更多（6~8个），但每个Expert更小
- 优势：路由粒度更细，知识存储更分散

**共享Expert（Shared Expert）**：
- 在标准路由Expert之外，增加1~2个"共享Expert"
- 共享Expert被所有Token无条件激活
- 处理所有Token共性的知识（句法、语义共性）
- 路由Expert负责领域特异性知识

```
DeepSeekMoE 单层结构：
输入 x
  ├──→ 共享Expert 0 → 所有Token都计算
  ├──→ 共享Expert 1 → 所有Token都计算  
  └──→ 64个路由Expert → 每个Token激活6个（Top-6）
       门控网络选择
```

**DeepSeekMoE 16B vs 标准MoE 16B**：

| 特性 | 标准MoE | DeepSeekMoE |
|------|--------|------------|
| Expert总数 | 8 | 64 + 2共享 |
| 激活Expert数 | 2 | 6~8 |
| 激活参数 | ~1.4B | ~1.1B |
| 参数量效率 | 基准 | 更高（同参数量下质量更好） |
| 计算量 | 基准 | 略高（更多激活Expert） |
| 通信量 | 基准 | 更大（更多Expert需传输） |

**DeepSeek-R1的MoE规模**：DeepSeek最新的R1系列模型（~671B总参数，37B激活）即采用DeepSeekMoE架构，在MoE稀疏路由方面展现了极强的扩展性。

---

## 6. 部署优化

### 6.1 Expert Offloading

显存是MoE部署的永恒瓶颈。Expert offloading策略将**冷门Expert**卸载到CPU内存，按需加载到GPU。

**冷热Expert识别**：
- **访问频率**：统计Expert在推理过程中被选中的次数
- **时长窗口**：使用滑动窗口（如最近1000个请求）统计
- **阈值判断**：访问频率低于平均值的30%视为"冷"Expert

**Offloading策略**：
```
GPU显存（有限）               CPU内存（丰富）
┌────────────────┐           ┌──────────────────┐
│ 热门 Expert 0   │           │ 冷门 Expert 5     │
│ 热门 Expert 1   │  ←→      │ 冷门 Expert 6     │
│ 中温 Expert 2   │  PCIe    │ 冷门 Expert 7     │
│ 中温 Expert 3   │  传输    │ 极冷 Expert 8     │
│ 门控网络 + Attn │  ←→      │ 极冷 Expert 9     │
└────────────────┘           └──────────────────┘
```

**延迟影响**：Expert offloading会增加延迟（PCIe 4.0 x16约32GB/s，加载一个7B Expert约0.5~1ms）。优化措施：
- **预取**：在请求到达前提前加载冷Expert
- **缓存**：保留最近使用的Expert在GPU缓存中（类似LRU）
- **重叠**：Expert加载与计算重叠

**实际效果**：Offloading 50%的冷门Expert可节省约40%的显存，延迟增加约10~20%（取决于缓存命中率）。

### 6.2 内存管理：PagedAttention + Expert内存池

MoE的内存管理比Dense模型更复杂，因为既要管理KV Cache（#7课程），又要管理Expert的显存分配。

**Expert内存池（Expert Memory Pool）**：
- 预分配固定大小的连续显存块，用于Expert权重和中间激活
- 避免动态分配的开销和碎片化
- 与PagedAttention的KV Cache内存池共存

**两层内存池架构**：
```
GPU显存分区：
┌─────────────────────────────────────────┐
│ PagedAttention KV Cache Pool            │ ← #7课程，处理Key/Value缓存
│   - 固定大小的块（block），动态分配      │
├─────────────────────────────────────────┤
│ Expert Weight Pool                      │ ← MoE专用
│   - Expert 0 ~ Expert N 的权重          │
│   - 与offloading协同，部分Expert在CPU上  │
├─────────────────────────────────────────┤
│ Expert Activation Pool                  │ ← MoE专用
│   - 当前层激活的Expert的中间结果         │
│   - 按需分配，用完即释放                │
├─────────────────────────────────────────┤
│ 其他：门控权重、Attention权重、临时变量   │
└─────────────────────────────────────────┘
```

**显存复用技巧**：
- 同一MoE层内的不同Expert可以共享中间激活显存（串行计算时）
- Expert权重可以被同一个batch中不同请求共享（batch内复用）
- 结合int4/int8量化（#2课程）可以将Expert权重压缩2~4倍

### 6.3 推理优化总结

MoE推理优化的核心在于三个平衡：

| 优化维度 | 左端 | 平衡点 | 右端 |
|---------|------|-------|------|
| Expert并行度 | 低并行→通信少→Expert负载重 | EP度=GPU数×Expert数/G | 高并行→通信多→并行收益低 |
| 容量因子 | 小CF→显存省→丢弃多 | CF=1.25 | 大CF→显存多→质量好 |
| Offloading | 少offload→快→显存大 | 20~40% offload | 多offload→慢→显存省 |

**黄金法则**：
1. 先确定所需延迟（在线服务通常要求TTFT<500ms）
2. 在延迟约束下最大化batch size（提高吞吐）
3. 在batch size下选择最小的Expert并行度（减少通信）
4. 用CF和offloading微调研训存优

---

## 总结

MoE推理优化是本系列课程中综合性最强的一课，涉及分布式推理（#6）、显存优化（#1, #2, #7）、计算加速（#5）等多个主题的交叉。

**核心收获**：

1. **架构本质**：MoE用"更多参数、稀疏激活"换"与Dense相同计算、更强能力"。代价是显存和通信开销。

2. **Expert并行是基石**：没有EP，大MoE模型无法在有限GPU上运行。EP + TP + PP的三维并行是当前主流方案。

3. **门控质量决定上限**：负载均衡损失、Z-loss、噪声扰动等门控优化技术是MoE模型质量的关键保障。

4. **容量因子是核心旋钮**：CF=1.25是大多数场景的推荐起点，调优时遵循"够用就好"的原则。

5. **工程实践趋于成熟**：从DeepSpeed-MoE到vLLM、从Megablocks到Triton kernel，MoE推理工具链已相当完善。

**MoE推理优化检查清单**：
- [ ] 选择合适的Expert并行度（EP=GPU数/Expert数）
- [ ] 评估是否需要混合TP/PP
- [ ] 设置合理的容量因子（从CF=1.25开始）
- [ ] 配置Expert offloading策略（冷热分离）
- [ ] 监控Token丢弃率（目标：<1%）
- [ ] 评估All-to-All通信占比（目标：<30%）
- [ ] 考虑量化压缩（int8 Expert可省50%显存）

**本系列下一课预告**：#11 - 持续交付与A/B测试（模型更新策略、回滚机制、灰度发布）。

---

> **参考资源**：
> - Mixtral of Experts (Mistral AI, 2024)
> - Switch Transformers (Google, 2021)
> - GLaM: Efficient Scaling of Language Models (Google, 2021)
> - DeepSpeed-MoE (Microsoft, 2022)
> - Megablocks (Stanford, 2023)
> - DeepSeekMoE (DeepSeek, 2024)
> - vLLM MoE Implementation (2024)
> - Efficient Large-Scale Language Model Training on GPU Clusters (Megatron-LM)
