# Seq2Seq与注意力机制

> 日期：2026-05-07 20:02 | 课程：NLP路线 Phase 2-1
> 目标：理解"变长序列→变长序列"的核心框架

## 核心问题

```
输入: "我爱猫"   (3个词)
输出: "I love cats" (3个词)
两者长度不同 → 怎么对齐？
```

## 朴素Seq2Seq

### 结构

```python
# 编码器(Encoder):   逐词读入 → 最后一个h_n = "语义向量"
# 解码器(Decoder):   从语义向量开始 → 逐词生成输出

# "我" → LSTM → h1
# "爱" → LSTM → h2
# "猫" → LSTM → h3  ← 这个h3是"整个句子的压缩"
#
# h3 → LSTM → "I"
# h3 + "I" → LSTM → "love"
# h3 + "love" → LSTM → "cats"
```

### 问题

```python
# 1. 信息瓶颈
#    "语义向量"h3要承载整句话的信息
#    句子越长 → 信息丢失越严重
    
# 2. 对齐问题
#    翻译"猫"时 → 解码器应该"注意"输入里的"猫"
#    但解码器只看到h3 → 不知道该注意哪里
```

## Attention（注意力机制）— 解决信息瓶颈

### 核心思想

```python
# 解码时，不要只看一个"语义向量"
# 而是让解码器"看向"输入序列的相关部分
#
# 翻译"猫"时 → 注意力权重集中在输入"猫"上
# 翻译"love"时 → 注意力权重集中在输入"爱"上
```

### Bahdanau Attention（加性注意力）

```python
# 1. 解码器当前状态 h_t
# 2. 与每个编码器状态 s_i 计算相似度
# 3. Softmax归一化成注意力权重 α_{ti}
# 4. 加权上下文向量 c_t = Σ α_{ti}·s_i
# 5. c_t + h_t → 预测下一个词

# 现在解码器能看到"整个输入序列"
# 但知道"该看哪里"——这就是"注意力"
```

### Luong Attention（乘法注意力）

```python
# 简化的注意力计算
# score(h_t, s_i) = h_t^T · W · s_i
# 比Bahdanau的 concat + tanh + linear 简单

# 两种变体:
# Global: 注意所有输入位置
# Local: 只注意一个窗口内的位置（更快）
```

## Attention的数学

```bash
三个公式统一了所有注意力机制:

1. score = Q · K^T / √d_k        # 点积注意力（Transformer）
2. score = score(Q, K)           # 双线性/加性（各种变体）
3. weights = softmax(score)       # 归一化
4. output = weights · V           # 加权求和
```

## 意义

```python
# Attention机制 = 2010年代NLP最重要的创新之一

# 1. 解决了长序列的"信息瓶颈"问题
# 2. 解码器能"关注"输入的相关部分
# 3. 提供了可解释性（注意力权重 → 翻译"对齐"的可视化）
# 4. 为Transformer铺平了道路（"Attention Is All You Need"）

# 后来发现: 连RNN都不需要了 → Transformer
```

## 今日收获
- Seq2Seq = 编码器-解码器框架
- 朴素Seq2Seq有"信息瓶颈"——一个向量存不下长句
- Attention = 解码时动态"看"输入的不同位置
- Bahdanau = 加性，Luong = 乘法
- 注意力机制 = Transformer的前身
