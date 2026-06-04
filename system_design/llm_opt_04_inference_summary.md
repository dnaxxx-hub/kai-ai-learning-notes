# LLM 推理优化 · 第4弹：推理优化总览

## 推理优化的全景图

LLM 推理优化是一个系统工程，从**模型本身**到**推理引擎**再到**服务架构**，每一层都有优化空间。

```
┌─────────────────────────────────────────────────────────────┐
│                   LLM 推理优化全貌                            │
├─────────────┬─────────────────────┬─────────────────────────┤
│  模型压缩    │  推理引擎优化        │  服务架构优化             │
├─────────────┼─────────────────────┼─────────────────────────┤
│ 量化        │ FlashAttention      │ Continuous Batching      │
│ 蒸馏        │ PagedAttention      │ Prefix Caching           │
│ 剪枝        │ Kernel Fusion       │ Speculative Decoding     │
│ MoE         │ 算子优化             │ 调度 & 负载均衡          │
│ GQA/MQA     │ 计算图优化           │ 流式输出                 │
└─────────────┴─────────────────────┴─────────────────────────┘
```

---

## 1. 模型压缩

### 1.1 量化（Quantization）

#### 权重量化

| 方法 | 位宽 | 内存节省 | 推理加速 | 质量损失 | 特点 |
|------|------|---------|---------|---------|------|
| **GPTQ** | 4-bit | ~4x | ~2-3x | 极小 | 基于Hessian的二次量化 |
| **AWQ** | 4-bit | ~4x | ~2-3x | 极小 | 激活感知权重量化 |
| **GGUF** | 2-8bit | 2-8x | ~1-2x | 根据位宽 | CPU友好, 分层量化 |
| **SqueezeLLM** | 3-4bit | ~3x | ~2x | 小 | 非均匀量化 |
| **QLoRA NF4** | 4-bit | ~4x | - | 小 | 训练时量化 |

**GPTQ 与 AWQ 对比**
```
GPTQ:
1. 收集少量校准数据
2. 逐列量化: 用 Hessian 矩阵指导误差最小化
3. 一次量化，推理时不需要反量化

AWQ:
1. 统计激活分布，找出重要通道 (0.1%-1%)
2. 重要通道更高精度，次要通道更低
3. 比 GPTQ 更简单更快

结论: AWQ ≈ GPTQ 精度 + 更简单, GPTQ ≈ 更成熟
```

**GGUF (llama.cpp)**
- CPU 推理主流方案
- **分层量化**：不同层用不同位宽
- K-quants (Q2_K, Q3_K, Q4_K, Q5_K, Q6_K, Q8_0)
- **Q4_K_M**: 推荐通用方案（~4.5 bit 加权平均）

#### KV Cache 量化
- 参考第2弹：FP8 > INT8 > INT4
- 推荐组合：GQA + FP8量化 → 内存降8倍

### 1.2 蒸馏（Distillation）

```
Teacher Model (70B) ──→ 输出分布 (logits)
                          ↓
Student Model (7B)  ──→ 学习 logits 分布
                          ↓
                    KL散度 + Token-level 匹配
```

- **Logit 蒸馏**: 学习教师模型输出分布
- **特征蒸馏**: 学习中间层表示
- **在线蒸馏**: 实时学习
- **代表**: DistilBERT, TinyLLaMA, Phi 系列

### 1.3 剪枝（Pruning）

| 方法 | 效果 | 代价 |
|------|------|------|
| **结构化剪枝**（整层/整头） | 推理加速 | 质量下降显著 |
| **非结构化剪枝** | 压缩大（理论） | 硬件不友好 |
| **SparseGPT** | 50%稀疏, 无损 | 结构友好 |
| **Wanda** | 50%稀疏, 几乎无损 | 更简单 |

---

## 2. 服务优化

### 2.1 Continuous Batching（连续批处理）

**传统 VS 连续批处理**
```
传统批处理:
[Req1 Req2 Req3] - prefill → [all generate together] → done
                                                    ↑ 所有请求必须同进同出
连续批处理:
time →
Req1 |P|D|D|D|D|D|D|
Req2   |P|D|D|D|D|
Req3     |P|D|D|D|D|D|D|D|
                  ↑ 请求可以随时加入/退出
```

**优势**
- GPU 利用率从 ~30% → ~80%+
- 低延迟（请求不用等待 batch 满）
- 最早由 **ORCA** 提出，vLLM、TensorRT-LLM 都实现

### 2.2 Prefix Caching（前缀缓存）

```
场景: 多个请求共享相同的 prompt 前缀

Request 1: "把第一行的数据按照第三列排序..."
         └─────── 相同前缀 ───────┘───────── 不同后缀

Request 2: "把第一行的数据按照第五列排序..."

Prefix Cache: 第一次计算完直接缓存前半截的 KV Cache
                  ↓
第二次直接复用 → 只计算 "按照第五列排序..."
```

**实现**
- vLLM: **自动检测**相同前缀（基于 block hash）
- 需要 hash 匹配整个 block
- **树结构前缀缓存**: 共享前缀的层级关系
- 最佳效果: 系统 prompt、few-shot 场景（常见）

**性能提升**
```
长系统 prompt (1K+ tokens): 
- 30-50% 延迟降低（多请求共享时）
- 更多节省取决于前缀重复率
```

### 2.3 Speculative Decoding（推测解码）

**核心思想**
大模型逐个 token 很慢 → 让小模型先猜，大模型一次性验证多个 token

```
常规解码:
[大模型]: "I" → "am" → "a" → "student" → ... (每步一个 forward)

推测解码 (Speculative Decoding):
                       ┌─ "I am a"
[小模型]: 快速猜: "I am a student" (草稿)
[大模型]: 验证 → ✅ 一次性接受 4 个 token!
                       └─ 一次 forward = 4 tokens

命中率好时: 2-3x 加速！
```

**关键技术**
1. **草稿模型**（Draft Model）: 小的、快的模型（≈大模型的1/10）
2. **验证**（Verification）: 大模型一次验证多个候选
3. **拒绝采样**（Rejection Sampling）: 保证分布一致

**变体**
- **Medusa**: 在同一模型上加多个预测头
- **Eagle**: 利用特征层做预测
- **Lookahead Decoding**: 无草稿模型，利用自预测
- **Staged Speculative Decoding**: 多级草稿

### 2.4 流式输出

- **Server-Sent Events (SSE)**: 逐 token 推送给客户端
- **低延迟**: 第一个 token 生成后立即发送
- **Chunked Prefill**: 把长 prompt 拆块处理
- **Beam Search + Streaming**: 流式支持搜索

---

## 3. 系统优化

### 3.1 Kernel Fusion（算子融合）

**问题**
LLM 推断时有很多小的 CUDA kernel 串行执行 → kernel launch overhead 大

```
未融合: [LayerNorm] → [Silu] → [MatMul] → [Add] → [Softmax] → [MatMul]
          └── 5次 kernel launch, 5次内存读写 ──┘

融合后: [LayerNorm+Silu+MatMul+Add+Softmax+MatMul]
          └── 1次 kernel launch, 1次读写 ──┘
```

**常见融合**
- **QKV Projection 融合**: 三个分开的 matmul → 一个大 matmul
- **Fused Attention**: FlashAttention 本身就是大融合
- **Fused MLP**: gate_proj + up_proj → 一次 matmul
- **LayerNorm + 量化**: LayerNorm 后直接量化
- **Residual + 量化**: skip connection 合并

### 3.2 Custom Attention Kernels

| Kernel | 优点 | 缺点 | 适用 |
|--------|------|------|------|
| **FlashAttention** | IO-save, 内存高效 | 实现复杂 | 通用, 长序列 |
| **xFormers** | 灵活, 多种 attention | 性能不如 FA | 研究 |
| **FlexAttention** (PyTorch) | 可编程 attention | 性能折中 | 自定义 attention |
| **Triton** | Python 编写 | 调试困难 | 高性能自定义 |
| **CUTLASS** | NVIDIA 官方 | C++ 复杂 | 极致性能 |

### 3.3 图编译（Graph Compilation）

**为什么需要图编译？**
- PyTorch eager mode: 逐算子执行 → 无法跨算子优化
- 图编译: 把整个模型变成计算图 → 全局优化

| 方案 | 效果 | 缺点 |
|------|------|------|
| **torch.compile** | 10-30% 加速 | 不稳定, 兼容性 |
| **TensorRT** | 20-50% 加速 | 编译时间长 |
| **XLA** | 中等 | 灵活差 |
| **Triton/JIT** | 自定义 | 手写多 |

---

## 4. 推理优化实施路线

### 维度一：按场景选择

| 场景 | 推荐方案 | 关键优化 |
|------|---------|---------|
| **API 服务** | vLLM + AWQ + Continuous Batching | 吞吐优先 |
| **个人本地** | llama.cpp (GGUF) + flash attention | 硬件适配 |
| **企业大规模** | TensorRT-LLM + FP8 + 多GPU | 极致性能 |
| **移动端** | 4-bit量化 + 蒸溜模型 | 体积优先 |

### 维度二：优化收益递进

```
1. 选对模型架构
   ↓ (GQA/MoE → 自然减内存)
2. 权重量化
   ↓ (4-bit → 4x 内存减少)
3. KV Cache 优化
   ↓ (GQA + FP8 → 8x 内存减少)
4. 推理引擎选择
   ↓ (vLLM / TRT-LLM → 2-3x 吞吐提升)
5. 服务层优化
   ↓ (连续批处理 + Speculative Decoding → 2-3x 加速)
6. 系统级优化
   ↓ (Kernel fusion + 图编译 → 10-30%)
7. 硬件升级
   (A100 → H100 → H200 → B200 → ...)
```

### 维度三：实际收益估算

| 优化项 | 单项增益 | 组合后 |
|--------|---------|--------|
| AWQ 4-bit | ~3x 吞吐 | baseline |
| + GQA | ~4x 内存 | ~4x |
| + PagedAttention | ~1.5x 内存 | ~6x |
| + Continuous Batching | ~2x 吞吐 | ~12x |
| + Speculative Decoding | ~2x 延迟 | ~24x |

> 组合优化时，收益不是简单相乘，要注意瓶颈转移。

---

## 5. 总结

```
推理优化 = 模型压缩 + 推理引擎 + 系统服务

核心原则：
1. 减少内存占用 (量化, GQA, PagedAttention)
2. 减少内存带宽需求 (FlashAttention, KV cache优化)
3. 提高计算利用率 (连续批处理, 图编译)
4. 减少延迟 (Speculative Decoding, 流式输出)

实践中：从最容易入手的开始（量化→引擎→服务→系统）
```

---

## 参考

- GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers
- AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration
- ORCA: A Distributed Serving System for Transformer-Based Generative Models
- SpecInfer: Accelerating Generative LLM Serving with Speculative Inference
- Medusa: Simple LLM Inference Acceleration Framework with Multiple Decoding Heads
- TensorRT-LLM: https://github.com/NVIDIA/TensorRT-LLM
