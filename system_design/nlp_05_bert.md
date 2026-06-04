# BERT：双向编码器表示

> 日期：2026-05-07 20:04 | 课程：NLP路线 Phase 3-1
> 目标：理解BERT怎么"读完一句话"

## 核心思想

```
之前的方法: 
- Word2Vec: 每个词一个固定向量（"bank"只有一种意思）
- ELMo: 上下文相关但只是LSTM
- GPT: 从左到右的单向

BERT: 同时看左右 → 真正理解上下文
```

## BERT的两个任务

### 1. Masked Language Model (MLM)

```python
# 类似于"完形填空"

# 输入: "I [MASK] NLP"
# 输出: "I [love] NLP"
# 预测: love 概率 0.89, like 0.05, ...

# 训练时随机遮住15%的词
# 模型根据上下文双向预测被遮住的词

# 不同于GPT: BERT看到了左右两边
# GPT: "I love [____]" → 只能看左边
# BERT: "I [MASK] NLP" → 同时看"我"和"自然语言处理"
```

### 2. Next Sentence Prediction (NSP)

```python
# 判断两个句子是不是连续的
#
# "我今天去了公园" + "天气很好" → Yes (连续)
# "我今天去了公园" + "Python是一种语言" → No (不连续)

# 学会句间关系 → 对QA/推理任务有帮助
# 后来发现NSP帮助不大 → RoBERTa去掉了它
```

## BERT的输入表示

```python
# BERT输入 = Token Embedding + Segment Embedding + Position Embedding

# [CLS] | 我 | 爱 | 猫 | [SEP] | 它 | 很 | 乖 | [SEP]
#  ↑                                                   ↑
#  分类标记                                             句子分隔符
#
# [CLS]的最终表示 = 整个句子的表示（用于分类）
```

## Fine-tuning（微调）

```python
# BERT的威力: 预训练 + 微调

# 预训练: 在海量语料（BookCorpus + Wikipedia = 3.3B词）上训练
# 学到了通用的语言知识

# 微调: 在下游任务上加一个小分类器，再训练几轮
#
# 情感分类: BERT + [CLS] → 分类器
# NER: BERT + 每个token → 分类器
# QA: BERT + 特殊设计 → 预测答案起始/结束位置

# 以前每个任务都要设计复杂的模型
# 现在: BERT + 简单微调 = SOTA
```

## BERT的影响

```python
# BERT (2018): 11项NLP任务刷新SOTA
# → NLP的"ImageNet时刻"

# BERT家族:
# RoBERTa: 去掉NSP + 更多数据 + 更长训练
# ALBERT: 参数共享 + 嵌入分解 → 更小更快
# DistilBERT: 蒸馏版 → 40%参数, 97%性能
# BERT-wwm: 全词掩码（中文版更好）
# TinyBERT: 极轻量版

# 中文预训练:
# BERT-Base-Chinese: 谷歌发布的
# RoBERTa-wwm-ext: 哈工大版
# ERNIE: 百度版（知识增强）
```

## 今日收获
- BERT = 双向 + Masked LM
- 两个预训练任务：MLM（完形填空）+ NSP（句间关系）
- **预训练 + 微调 = 2018年后的NLP范式**
- BERT开启了"大模型+微调"路线
- 影响：任何NLP任务都可以0.5小时搞定
