# Transformer 从零实现 — 学习笔记

## 概述

用纯 NumPy 实现了一个迷你 Transformer 模型（无 PyTorch/TensorFlow 依赖），包含完整的前向传播、反向传播（手写梯度）和训练循环。

## 模型架构

| 组件 | 说明 |
|------|------|
| Embedding | Token Embedding + 可学习的 Positional Embedding |
| Multi-Head Self-Attention | QKV 投影 → 分头 → Scaled Dot-Product → Concat → 输出投影 |
| Feed-Forward Network | Linear → ReLU → Linear |
| Layer Normalization | 可学习的 γ, β，沿最后一维归一化 |
| Residual Connections | 每个子层输出加输入 |
| Transformer Block | LayerNorm → Attn → Residual → LayerNorm → FFN → Residual |
| LM Head | 线性层投影到 vocab_size |

## 关键实现细节

### Attention
- 分头：`(B, S, D)` → `(B, H, S, D/H)`，用 transpose + reshape
- Scaled Dot-Product：`Q @ K.T / sqrt(d_k)`
- Causal Mask：上三角设为 `-1e10`（softmax 后 ≈ 0），下三角和对角线为 0
- 反向传播：手动实现 softmax 的雅可比

### LayerNorm 反向传播
```
dx = dx_hat / sqrt(var + eps) + dvar * 2 * (x - mean) / N + dmean / N
```
其中：
- `dx_hat = d_output * gamma`
- `dvar = sum(dx_hat * (x - mean) * -0.5 * (var + eps)^(-1.5))`
- `dmean = sum(dx_hat * -1/sqrt(var+eps)) + dvar * sum(-2*(x-mean))/N`

### Cross-Entropy Loss 反向传播
```
d_logits = (probs - one_hot(targets)) / (B * S)
```
非常简洁——softmax 的梯度反传到这里变得优雅。

### 优化器
- **SGD**：带 momentum 支持
- **Adam**：带 bias correction 的完整实现

### 参数统计
小模型配置（vocab=20, d_model=32, heads=2, layers=2, d_ff=64）：**19,456 个参数**

## 测试结果（全部通过 ✅）

| 测试 | 描述 |
|------|------|
| Model Construction | 参数计数、各组件存在性 |
| Forward Pass | 无 mask 和有 mask 前向 |
| Embedding Lookup | Token + Position 组合正确 |
| Causal Mask | 三角矩阵结构正确 |
| Loss Value | Cross-Entropy 正确比错误置信度低 |
| Backward Pass | 梯度存在且非零 |
| Gradient Flow | 37 个参数组全部收到梯度 |
| Optimizers | SGD 和 Adam 正常 step |
| Training (random) | 100 步 loss 3.07 → 0.86 ↓ |
| Training (pattern) | 100 步 loss 2.40 → 1.59 ↓ |
| Generation | 能生成有效序列 |

## 架构图

```
Input (B, S)
    ↓
Embedding (Token + Position)
    ↓  (B, S, D)
┌───────────────────────────────────┐
│ LayerNorm                         │
│ Multi-Head Self-Attention (+mask) │
│ Residual (+)                      │
│ LayerNorm                         │
│ FFN (Linear-ReLU-Linear)          │
│ Residual (+)                      │
├───────────────────────────────────┤  x N blocks
│ LayerNorm                         │
│ LM Head (Linear, no bias)         │
└───────────────────────────────────┘
    ↓
Logits (B, S, V)
```

## 学到的东西

1. **Attention 的反向传播**——softmax 梯度反传是 `P * (dP - sum(P * dP)) / scale`，需要在 d_scores 时先还原 scale 因子
2. **LayerNorm 的反向**——链式法则展开后涉及均值、方差的梯度，需要仔细推导
3. **残差连接的梯度累加**——forward 时 x_attn = x + attn_out，backward 时从 x_attn 的梯度要同时流向 x 和 attn_out
4. **头拆分与合并**——用 reshape + transpose 即可，反向同理
5. **纯 NumPy 训练**——没有自动求导，每个 backward 都要手动实现，有助于加深理解

## 文件位置

- 工作区：`C:\Users\Admin\.openclaw\workspace\projects\mini_transformer\`
- 知识库：`D:\kai_knowledge\projects\mini_transformer\`
