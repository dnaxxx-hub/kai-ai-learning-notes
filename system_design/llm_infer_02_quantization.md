# LLM 模型量化笔记

> **目标读者**：已理解 Transformer 推理流程、KV Cache 概念的 AI 工程师  
> **更新日期**：2024

---

## 1. 为什么需要量化

### 1.1 显存节省

```
FP32 (4B) → FP16/BF16 (2B) → INT8 (1B) → INT4 (0.5B)
          ↓           ↓       ↓        ↓
        原大小      50%      25%      12.5%
```

- **1 个 13B 参数量化对比**：
  | 精度 | 显存占用 | 推理显存带宽压力 |
  |------|----------|------------------|
  | FP16 | 26 GB    | 高               |
  | INT8 | 13 GB    | 中               |
  | INT4 | 6.5 GB   | 低               |

### 1.2 计算加速

- **INT8 vs FP16**：2-4 倍加速（Tensor Core 利用）
- **INT4 vs INT8**：额外 2 倍加速
- **INT4 理论加速比**：FP16 的 8-16 倍

### 1.3 带宽瓶颈分析

```
LLM 推理是 memory-bound 而非 compute-bound：
- 数据加载带宽：~940 GB/s（H100）
- 模型计算性能：~300 TOPS
- 瓶颈在数据供应，而非计算能力

减少数据量 → 减少显存带宽压力 → 天然加速
```

---

## 2. 量化基础

### 2.1 对称量化 vs 非对称量化

#### **对称量化 (Symmetric Quantization)**
```
假设激活值/权重分布约以 0 为中心：
Q(x) = round(x / S)

其中 S (scale) 选择：
    S = max(|x|)    # 最大化利用精度范围
```

**适用场景**：激活值分布（ReLU 后接近对称）

#### **非对称量化 (Asymmetric Quantization)**
```
Q(x) = round((x - min) / S) + Z

其中：
    S = (max - min) / (2^n - 1)     # scale
    Z = round(-min / S)              # zero point

完整转换：
    Q(x) = round(S * (x - Z))        # 反向：x = (Q - Z) / S * S
```

**适用场景**：权重数据（通常非对称分布）

### 2.2 逐层 vs 逐通道量化

#### **Per-Layer Quantization（逐层）**
- **优势**：实现简单，推理速度快
- **劣势**：单层 scale 无法适配不同激活模式

#### **Per-Channel/Group-wise Quantization（逐通道）**
```
分组量化策略：
  将输入特征通道分成 G 组（G=16/32/64 常见）
  每组独立计算 (S, Z)

优点：
  ✓ 能更好地保留信息
  ✓ 适应不同通道的激活分布
  ✓ 精度损失小

典型分组大小：
  输入：128 → 分成 32 个组，每组 4 通道
  权重：2048 → 分成 16 个组，每组 128 通道
```

### 2.3 量化误差来源

```
总误差 = 舍入误差 + 裁剪误差 + 近似误差
```

#### **舍入误差 (Rounding Error)**
- 有限精度表示导致的误差
- 使用 round 或 saturating round
- 分布：均匀分布，标准差 ≈ 1/√12

#### **裁剪误差 (Clipping Error)**
```
x 被裁剪到 [-S, S] 范围

当 x > S 时：Q(x) = S（信息丢失）
当 x < -S 时：Q(x) = -S

误差分析：
  假设激活值分布：P(|x| > S) = α
  裁剪误差期望：α * E[x|x|>S]
```

#### **量化噪声传播**
```
对于深度网络：
  误差累积 ∝ L × (error_per_layer)
  
  解决方案：GPTQ/AWQ 使用优化方式控制误差
```

---

## 3. 主流量化方法

### 3.1 GPTQ (GGPTQ, Quantized Generative Pre-trained Transformer)

#### **核心思想**
- 继承 **OPTQ/OBQ** (Outlier-Bounded Quantization)
- **基于 Hessian 矩阵**的权重量化
- **自适应量化顺序**，减少误差传播

#### **算法流程**
```
For each layer (L = 1..N):
  1. 随机选择权重子块
  2. 计算 Hessian 矩阵近似：
       H[i][j] ≈ ∂L/∂w_i * ∂L/∂w_j
  3. 量化误差敏感性 = Σ H[i][j] * w_j
  4. 按误差敏感性降序分配量化比特
  5. 更新误差补偿（error compensation scheme）

关键优势：
  ✓ 误差补偿：e_i = Q(w_i) - w_i
  ✓ 量化顺序：先量化误差小的权重
  ✓ 精度保持好：7B 模型 INT4 → PPL 增加 < 0.01
```

### 3.2 AWQ (Activation-aware Weight Quantization)

#### **核心思想**
```
并非所有权重通道同等重要！

观察：
  - 仅 1% 的权重通道对输出影响最大
  - 其余 99% 对精度贡献有限

解决方案：
  保护"Important"的 1% 权重通道
  其余用低精度量化
```

#### **算法流程**
```
1. Forward 运行，收集激活值统计：
   max_activation_per_channel

2. 计算重要性评分：
   importance_score = average(max_activation_per_channel)

3. 选择关键通道：
   top_1_percent_by_importance_score

4. 混合精度量化：
   - 关键通道：FP16/BF16 保持
   - 其他通道：INT8 量化

5. 误差补偿（可选）
```

#### **代码示例**
```python
# AWQ 量化伪代码
importance = torch.mean(activation_max, dim=0)
keep_mask = importance > torch.quantile(importance, 0.99)

quantized_weights = torch.where(
    keep_mask,
    weights.float(),           # FP16 保留
    quantize(weights.float(), 8)  # INT8 量化
)
```

### 3.3 GGUF / llama.cpp - K-Quants

#### **核心思想**
- **分块量化 (Block Quantization)**
- **混合精度**，灵活配置
- **开源实现**，广泛支持

#### **K-Quant 系列**
```
K-quants 表示法：Q{K}_{M}
  - K = 量化方案（如 Q4_K_M）
  - M = 混合精度策略

常用方案：
  - Q2_K    : 20% FP16 + 80% INT2
  - Q3_K_M  : 33% FP16 + 66% INT2 + 1% FP4
  - Q4_K_M  : 25% FP16 + 75% INT4  (推荐)
  - Q5_K_M  : FP16 + INT4 混合     (高精度)
  - Q8_0    : FP8           (最高精度)
```

#### **分块策略**
```
分块大小：n_bits = 2-8
- 块内使用统一 scale/zero
- 块间混合精度

示例（Q4_K_M）：
  [
    Q4: scale=0.03, zero=0.12
    Q4: scale=0.045, zero=0.089
    Q2: scale=0.02,  zero=0.15
    Q3: scale=0.055, zero=0.067
  ]

每块 32 浮点 → 压缩到 8 整数
```

### 3.4 SmoothQuant

#### **核心思想**
```
问题：量化激活值遇到的"Outlier"（大值）
  这些值来自：
  - Attention 的 scale (1/√d_model)
  - Dropout 未激活

平滑方案：
  将 activation 的 outlier 移到权重上
  使激活值近似对称 → 适合对称量化
```

#### **算法步骤**
```
1. 分析激活值：a = W × x
2. 分解：
     a_outlier = S_smooth × s
     a_smooth = a_outlier + a_rest

3. 定义：W' = W × S_smooth + z
   W' 包含 outlier → 非对称量化
   a' = a_rest → 对称量化

4. 推理时：
   output = Q(W') × Q(a')
```

---

## 4. LLM.int8() 与混合精度

### 4.1 Emerging Outlier Features (EoF)

#### **现象**
```
Transformer 的注意力层中：
  Q × K^T / √d 中会出现极大值
  这些值不是"噪声"，而是有意义 feature

原因：
  - 注意力模式在特定维度高度集中
  - 对应某些 token 间的强关系
  - 这些维度对推理很重要

如果 INT8 量化：
  - EoF 被量化误差掩盖或丢失
  - 导致性能下降 15-20%
```

### 4.2 解决方案：混合精度方案

```
方案 1：LLM.int8() —— 原始实现
  - 激活值：INT8（大部分）+ FP16（EoF）
  - 权重：全部 INT4

方案 2：AWQ 混合精度
  - 关键权重通道：FP16
  - 其他权重：INT4/8
  - 激活值：INT8

方案 3：bitsandbytes INT4 + NF4
  - 权重：4-bit NF4 distribution
  - 激活值：8-bit FP8 或 INT8
```

### 4.3 精度保持策略

```
激活值 INT8 量化时：
  Q(a) = clip(round(a / S), -128, 127)
  
  关键：
  - scale S 选择大 enough 避免 EoF 饱和
  - 但 S 太大会损失动态范围
  
折中方案：
  S = max(activation) / 2
  或使用 adaptive scale
```

---

## 5. 量化感知训练（QAT）

### 5.1 QAT vs PTQ

| 特性 | PTQ (Post-Training) | QAT (Quantization-Aware) |
|------|---------------------|---------------------------|
| 精度 | 中等（PPL +1~2） | 高（PPL +0.1~0.5） |
| 训练成本 | 0 | 需要 retrain/fine-tune |
| 适用场景 | 资源受限，精度可容忍 | 对精度要求高 |
| 实现难度 | 简单 | 复杂 |

### 5.2 Straight-Through Estimator (STE)

#### **核心思想**
```
在训练中模拟量化操作：
  x_quant = quantize(x, S)  # 量化操作

反向传播：
  dL/dx ≈ dL/dx_quant  # 直通估计器
  
伪代码：
  def forward(x):
      x_q = round(x / S) * S
      return model(x_q)
  
  def backward(x_grad):
      return x_grad  # 直通
    
问题：梯度不传递到量化操作本身
解决：梯度直接穿过去（直通）
```

#### **QAT 训练流程**
```
for epoch in epochs:
  # 正向：量化前馈
  x_quant = quantize(x, S_current)
  y = model(x_quant)
  
  # 反向
  loss = criterion(y, target)
  loss.backward()  # STE 传递梯度
  
  # 更新参数 + 更新 scale
  optimizer.step()
  compute_new_S(y_quantized)
```

### 5.3 QAT 配置建议

```
对于 7B+ 模型：
  - QAT epochs: 1-3
  - Learning rate: 2e-5 ~ 5e-5
  - Quantize dtype: int8（PTQ）or sim_int8（模拟量化）
  - Target PPL increase: < 0.5

对于 13B+ 模型：
  - QAT 收益递减
  - 考虑 AWQ/GGUF PTQ 先
  - 如需要进一步精度：LoRA + QAT
```

---

## 6. 量化对推理的影响

### 6.1 精度损失分析

#### **Perplexity (PPL) 变化**
```
典型量化模型 PPL 对比：

Model      FP16   INT8   INT4      差异
--------------------------------------------------------------------------------
7B         20.5   21.2   22.1      +0.7 ~ +1.6
13B        23.8   24.5   25.8      +0.7 ~ +2.0
30B        26.5   27.4   29.2      +0.9 ~ +2.7
70B        28.9   29.8   32.1      +0.9 ~ +3.2

结论：
  - 通常 PPL 增加 < 2
  - 实际应用中影响有限
  - 推理速度提升远超精度损失价值
```

### 6.2 推理速度提升

#### **理论加速比**
```
Bandwidth-bound 场景：
  Speedup = (FP16 Bandwidth / Quantization Bandwidth)
  
假设 H100 (FP16 BW = 940 GB/s, INT8 BW = 940 GB/s):
  FP16 → INT8:    理论 2x（同样带宽，实际 ~1.8x）
  INT8 → INT4:    理论 2x（实际 ~1.6x，内存访问模式变化）
  
综合：
  FP16 → INT4:   理论 4x（实际 ~3.0~3.5x）
  
实际测试（7B 模型，A100）：
  FP16        :  33 tokens/s
  INT8        :  65 tokens/s   (1.96x)
  INT4 (GGUF) : 105 tokens/s    (3.18x)
```

#### **延迟分布变化**
```
FP16 模型：
  首字延迟 (TTFT): 80ms
  吞吐延迟：33 t/s

INT4 模型：
  首字延迟：75ms (-5/6%)
  吞吐延迟：105 t/s (+3x)

量化对延迟分布影响：
  - TTFT 可能因加载速度变化
  - 连续生成速度大幅加快
```

### 6.3 实际部署建议

#### **按场景选择量化级别**

```
应用场景                      推荐方案                  理由
--------------------------------------------------------------------------------
本地推理（消费级显卡）        INT4 (GGUF)              内存有限，性能重要
API 服务（A100/A800）        INT8 + AWQ (可选)        有带宽优势
云端训练/微调                FP16/BF16                需要精度
实时对话（手机/边缘）         INT4-NF4 (Llama.cpp)   极小内存占用
高精度任务（科研）            FP16/BF16 + LoRA        精度优先
```

#### **生产环境最佳实践**

```
建议配置：
  - 使用 GGUF Q4_K_M 或 AWQ INT4
  - 配合量化感知推理引擎（vLLM 等）
  - 监控 PPL 和生成质量
  - 对于多用户：考虑动态量化 scale

监控指标：
  ✓ PPL 增加 < 1（可接受）
  ✓ 首字延迟提升 < 2ms
  ✓ 吞吐量增加 > 20%
  ✓ 用户生成的困惑分数
```

#### **迁移路径**

```
现有 FP16 模型 → 量化迁移流程：
  
  1. 模型转换：
     llama-quantize model.ggml.wft model.q4_k_m.ggml 8
  
  2. 精度验证：
     - PPL 对比
     - 生成示例抽样检查
     - 用户反馈收集
  
  3. 回滚机制：
     - 保留 FP16 副本
     - 精度差 > 阈值 → 自动降级
    
  4. 部署策略：
     - 灰度发布（10% → 50% → 100%）
     - 监控告警配置
```

---

## 附录：常用工具与命令

### 量化工具对比

| 工具 | 优点 | 缺点 | 典型场景 |
|------|------|------|----------|
| **GPTQ** | 精度高，支持大模型 | 只支持指定框架格式 | 生产部署 |
| **AWQ** | 保护关键通道 | 转换稍慢 | 精度敏感部署 |
| **GGUF** | 灵活，开源 | 需要转换脚本 | 本地/边缘推理 |
| **SmoothQuant** | 精度高 | 仅用于激活值 | 配合其他方法 |

### 量化命令示例

```bash
# GGUF 量化（llama-quantize）
llama-quantize model.bin model.Q4_K_M.gguf Q4_K_M

# AWQ 量化（python 脚本）
python awq_inference.py --model-name Llama-2-7b --quantize-awq --bits 4

# vLLM 部署量化模型
vllm serve --model-dir ./model \
           --limit-mm-Per-batch 2 \
           --max-model-len 8192 \
           --enforce-eager
```

### 推荐资源

- **论文**：
  - [GPTQ: Accurate Post-Training Quantization for Generative Transformer](https://arxiv.org/abs/2210.17671)
  - [AWQ: Activation-aware Weight Quantization for LLMs](https://arxiv.org/abs/2306.00573)
  - [SmoothQuant: Accurate and Efficient Post-Training Quantization for Large Language Models](https://arxiv.org/abs/2211.10410)

- **代码库**：
  - [llama.cpp](https://github.com/ggerganov/llama.cpp)
  - [AWQ](https://github.com/casper-hansen/AutoAWQ)
  - [GGUF](https://github.com/abetlen/llama-cpp-python)

- **基准测试**：
  - HuggingFace LM Evaluation Harness
  - LMSYS Chatbot Arena