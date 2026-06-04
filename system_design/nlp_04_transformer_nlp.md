# Transformer详解（NLP视角）

> 日期：2026-05-07 20:03 | 课程：NLP路线 Phase 2-2
> 目标：深入Transformer在NLP中的具体设计

## 为什么Transformer取代了Seq2Seq

```python
# Seq2Seq: 
# - 顺序处理（t步等t-1步） → 无法并行
# - Attention帮助了但仍然是RNN的补丁

# Transformer:
# - 完全并行（一次看到所有词）
# - Attention本身就是核心（不是补丁）
# - 训练速度比LSTM快10-100倍
```

## 从NLP角度看Transformer的组件

### 1. 输入表示

```python
# 每个词 → Embedding (512维,可学习)
# + 位置编码（sin/cos, 模型才知道词的顺序）

# BERT和GPT的差别:
# BERT用 WordPiece 分词 (30k词表)
# GPT用 BPE (Byte Pair Encoding, 50k词表)
```

### 2. Encoder vs Decoder

| 结构 | 特点 | 代表模型 |
|------|------|---------|
| Encoder-Only | 双向注意力 | BERT, RoBERTa |
| Decoder-Only | 单向(因果)注意力 | GPT系列, LLaMA |
| Encoder-Decoder | 编码器双向+解码器单向 | T5, BART |

### 3. Decoder的Masked Attention

```python
# 解码器生成时：
# "I love [____]"
# 预测下一个词时，不能看到"cats"（未来的词）
# 
# Masked Self-Attention:
# 把未来位置遮住（变成 -inf → softmax后为0）
# 解码器只能关注当前位置和之前的位置

# 这是Causal LM的核心设计
```

## Transformer的堆叠

```python
# 一个Transformer层:
# Self-Attention → Add & LayerNorm → FFN → Add & LayerNorm

# BERT-Base:  12层, 110M参数
# BERT-Large: 24层, 340M参数
# GPT-3:      96层, 175B参数
# GPT-4:      ~120层, ~1.7T参数（推测）
```

## Transformer的局限

```python
# 1. 计算量 O(n²)
#    每个词都要注意所有其他词 → 序列越长，计算量平方增长
#    处理10万词 → 100亿次注意力计算

# 2. 位置编码
#    正弦编码是固定的 → 学习能力有限
#    现在用 RoPE (Rotary Position Embedding)

# 3. 没有递归偏置
#    CNN有"局部性"偏置，RNN有"顺序"偏置
#    Transformer什么偏置都没有 → 需要更多数据训练
```

## 今日收获
- Transformer = 完全并行，完全注意力
- Encoder-Only(BERT) vs Decoder-Only(GPT) vs Encoder-Decoder(T5)
- Decoder用Masked Attention防止看到未来词
- 局限：O(n²)计算量，大序列显存爆炸
- 主流的NLP预训练模型就是Transformer的三种变体
