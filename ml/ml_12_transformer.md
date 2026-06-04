# Transformer：Attention Is All You Need

> 日期：2026-05-07 17:00 | 课程：ML/DL路线 Phase 3-4
> 目标：理解为什么Transformer取代了RNN成为序列建模的王者

## 核心直觉

### RNN的问题 vs Transformer的答案

| 问题 | RNN | Transformer |
|------|-----|------------|
| 处理方式 | **顺序**（t步等t-1步） | **并行**（一步算完所有位置） |
| 长距离依赖 | 100步后梯度消失 | 任意距离直接连接 |
| 训练效率 | 无法利用GPU并行 | **完全并行，训练快10倍+** |

Transformer的核心洞察：**你不需要顺序处理序列，只需要让每个位置"看到"所有其他位置。**

## Self-Attention（自注意力）—— 核心机制

### 一个公式
```
Attention(Q, K, V) = softmax(Q · K^T / √d_k) · V
```

### 三步骤

#### Step 1: Q · K^T — 计算相似度
```
每个token的"查询"(Q)问所有token的"键"(K)：
"我跟你有多相关？"

Q_i · K_j = token_i 和 token_j 的匹配得分
```

#### Step 2: Softmax — 归一化成权重
```
每一行加起来=1
"我该放多少注意力在每个人身上？"
```

#### Step 3: · V — 加权求和
```
每个token的输出 = 其他token的值(V)的加权平均
权重 = 注意力分数
```

### 为什么叫"自"注意力？
因为Q、K、V都来自**同一个输入**X（通过三个不同的投影矩阵）。
不是"我注意别人"，而是**"每个token注意序列里的所有token（包括自己）"**。

## 为什么要除以√d_k？

```python
# 当d_k很大时，Q·K^T的值会很大（向量点积的方差∝d_k）
# 大值进softmax → 梯度极小

# 所以: scores = Q @ K.T / sqrt(d_k)
# 让方差回到1，梯度正常
```

## Multi-Head Attention（多头注意力）

```python
# 不是只做一次注意力，而是做h次
# 每个头学到不同的"关系视角"

# 头1: "词语之间的语法关系"
# 头2: "谁修饰谁"
# 头3: "指代关系"（他→约翰）
# ...

# h个头的结果拼起来，再投影
output = Concat(head_1, ..., head_h) @ W_o
```

## Transformer完整结构

```python
class TransformerBlock:
    """
    Encoder层:
    输入 → [Multi-Head Self-Attention] → Add & Norm → [FFN] → Add & Norm
    
    Decoder额外: Masked Self-Attention + Cross-Attention（注意Encoder的输出）
    """
    def forward(self, x):
        # Attention + 残差连接 + LayerNorm
        attn_out = self.mha(x, x, x)  # Self-Attention
        x = self.layer_norm(x + attn_out)
        
        # FFN + 残差连接 + LayerNorm
        ffn_out = self.ffn(x)
        x = self.layer_norm(x + ffn_out)
        return x
```

### Position Encoding（位置编码）
```python
# Self-Attention对位置不敏感（"我爱你"和"你爱我"的注意力矩阵一样）
# 需要显式注入位置信息

# 位置编码: 不同频率的正弦/余弦波
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
# 每个位置得到唯一的编码向量
```

## 可视化

![Self-Attention](12_transformer_attention.png)

**左图**：QK^T 注意力分数（红=正相关，蓝=负相关）
**中图**：Softmax归一化后的注意力权重（每行和为1）
**右图**：注意力加权后的输出

![多头注意力](12_multi_head.png)

多个注意力头并行，拼合后投影出最终表示。

## 纯numpy实现

```python
import numpy as np

def softmax(x, axis=-1):
    e_x = np.exp(x - x.max(axis=axis, keepdims=True))
    return e_x / e_x.sum(axis=axis, keepdims=True)

def scaled_dot_product_attention(Q, K, V):
    d_k = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(d_k)
    weights = softmax(scores, axis=-1)
    return weights @ V, weights

# 示例
seq_len, d_model = 5, 8
x = np.random.randn(seq_len, d_model)

# QKV投影
Wq = np.random.randn(d_model, d_model) * 0.1
Wk = np.random.randn(d_model, d_model) * 0.1
Wv = np.random.randn(d_model, d_model) * 0.1

Q, K, V = x @ Wq, x @ Wk, x @ Wv
output, attn_weights = scaled_dot_product_attention(Q, K, V)
```

## Transformer的统治地位

| 领域 | 代表模型 |
|------|---------|
| NLP | GPT-4, BERT, LLaMA, DeepSeek |
| 视觉 | ViT（Vision Transformer） |
| 语音 | Whisper, SpeechT5 |
| 多模态 | GPT-4V, CLIP |
| 代码 | GitHub Copilot |

## 今日收获
- **Self-Attention = 每个token看所有token**，并行计算
- QKV分别负责"要找什么"、"有什么"、"价值多少"
- 除以√d_k防止梯度消失
- 多头注意力学不同关系视角
- **Transformer并行 + 长距离 = 碾压RNN**
- 你正在用的AI（包括我）的底层架构
