# 第17课：Transformer 从零实现

> 日期: 2026-05-08
> 代码: `ml_transformer.py`

## 核心组件

### 1. 缩放点积注意力
```
Attention(Q,K,V) = softmax(Q·K^T / √d_k) · V
```
- √d_k 缩放防止softmax梯度消失
- attention权重和=1 ✅

### 2. 多头注意力
- d_model=16, n_heads=4 → d_k=4
- 每个head独立注意力 → 拼接 → 输出投影
- 不同head关注不同特征子空间

### 3. 位置编码 (正弦)
```
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
```
- 相近位置点积更大 (7.3 vs 3.8) ✅

### 4. Decoder Block
- 因果掩码: 位置i只看i之前token ✅
- 残差连接 + LayerNorm
- 前馈网络: d_model→d_ff→d_model (ReLU)

### 5. Mini Transformer
- 2层Decoder, 2头, d_model=32
- 前向传播形状正确 ✅
- 因果掩码验证: 第3token权重在位置0-2 ✅
- 自回归生成 ✅
