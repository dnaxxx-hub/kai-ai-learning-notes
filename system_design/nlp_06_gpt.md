# GPT系列：自回归语言模型

> 日期：2026-05-07 20:05 | 课程：NLP路线 Phase 3-2
> 目标：理解"GPT怎么生成长文本"

## BERT vs GPT

| 特性 | BERT | GPT |
|------|------|-----|
| 方向 | 双向（Masked LM） | 单向（从左到右） |
| 目标 | 理解文本 | 生成文本 |
| 训练 | MLM完形填空 | 预测下一个词 |
| 适合 | 分类/标注/QA | 生成/对话/翻译 |
| 解码 | 不能生成 | 逐词生成 |

## GPT的核心机制

### 自回归

```python
# 自回归 = 用"历史"预测"未来"

# P(今天) = softmax(...)
# P(天气|今天) = softmax(...)
# P(很|今天天气) = softmax(...)
# ...

# 联合概率: P(整个序列) = P(w₁)·P(w₂|w₁)·P(w₃|w₁,w₂)·...

# 这就是Causal LM (因果语言模型)
# 和BERT的区别：GPT只看左边
```

### In-context Learning

```python
# 最神奇的能力:
# "把英文翻译成法文:
#  sea otter → loutre de mer
#  cheese →" → 模型自动输出 fromage

# 这完全在"预测下一个词"框架内
# 没有微调，没有梯度更新
# → 只是"从上下文推断模式"

# 这是GPT-3 (2020) 最惊人的发现
# 当时很多人不相信
```

## GPT家族

### GPT-1 (2018)

```python
# 12层Transformer Decoder
# 117M参数
# 证明: 无监督预训练 + 微调 = SOTA
# （当时BERT同期发布，盖过了GPT-1）
```

### GPT-2 (2019)

```python
# 1.5B参数
# 核心: Zero-shot能力
# "我不微调也能做翻译/问答/摘要"

# 发布争议: OpenAI起初不敢全开（怕被滥用）
# 最终开源
```

### GPT-3 (2020)

```python
# 175B参数（GPT-2的100倍）
# 训练费: 1200万美元
# 核心: In-context learning

# 不再需要微调
# 给几个例子（Few-shot）→ 模型自己学会任务

# 但GPT-3有很多缺陷:
# - 说胡话（Hallucination）
# - 数学差
# - 长文本逻辑不一致
```

### InstructGPT / GPT-3.5 (2022)

```python
# 关键改进: RLHF
# 
# 1. SFT: 人类标注高质量问答 → 微调GPT-3
# 2. Reward Model: 让人类排序多个输出 → 训练奖励模型
# 3. PPO: 用奖励模型训练 → 生成人类喜欢的输出

# 效果: 1.3B的InstructGPT打爆175B的GPT-3
# 证明: 对齐(Alignment) > 规模
```

### GPT-4 (2023)

```python
# 多模态（看图 + 理解文字）
# 更强推理能力
# 更长上下文
# 参数: 推测 ~1.7T（MoE架构）

# 达到了"在大多数考试中超过人类"
```

## Scaling Law（缩放定律）

```python
# 2020年OpenAI发现:
# 模型大小 ↑  数据量 ↑  计算量 ↑  
# → Loss持续下降
# → 没有"天花板"

# 这意味着:
# 给更多算力 → 模型一定更好
# 掀起了大模型军备竞赛

# 但Scaling Law也有边界:
# 数据不够了（互联网文本快被用完了）
# 算力成本指数增长
```

## 今日收获
- GPT = Decoder-Only Transformer + 自回归
- **In-context Learning = GPT-3最神奇的发现**
- RLHF让GPT-3.5比GPT-3好用100倍
- GPT-4 = 多模态 + 更强推理
- Scaling Law: 越大越好（但有边界）
