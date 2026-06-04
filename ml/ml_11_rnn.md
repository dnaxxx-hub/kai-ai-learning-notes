# RNN & LSTM：序列建模的利器

> 日期：2026-05-07 16:30 | 课程：ML/DL路线 Phase 3-3
> 目标：理解RNN如何处理"时间"维度，以及它的问题

## 核心直觉

### 为什么需要RNN？

前几课学的都是**单样本→单输出**，但很多问题是**序列→序列**：
- 文本翻译：一句话→另一句话（长度不定）
- 语音识别：声音→文字
- 股票预测：历史价格→未来价格

CNN对输入顺序不敏感（打乱像素图片内容不变），但序列的顺序就是信息。

### RNN的哲学
> **每个时间步的隐藏状态 h_t 携带"到目前为止的全部信息"**

```
h_t = tanh(W·x_t + U·h_{t-1} + b)
y_t = V·h_t + c

其中 h_t 是"记忆"，把历史信息传递到未来
```

## 两种核心问题

### 1. 梯度消失（Vanishing Gradient）
RNN在不同时间步共享W参数，反向传播时梯度经过多个时间步：
```
grad = W^t · dL/dh_t

如果 W < 1:  W^t → 0  (梯度消失，学不到长距离依赖)
如果 W > 1:  W^t → ∞  (梯度爆炸，训练不稳定)
```
这导致**RNN在实践中只能记住约5-10步**。

### 2. 长期依赖（Long-term Dependencies）
"我需要记住第1个词的信息来预测第50个词"——RNN做不到。

## LSTM（长短期记忆网络）

### 核心创新：**门控机制**
```python
# LSTM有三个门：
# 遗忘门:  f_t = σ(W_f · [h_{t-1}, x_t] + b_f)   记住多少旧信息？
# 输入门:  i_t = σ(W_i · [h_{t-1}, x_t] + b_i)   吸收多少新信息？
# 输出门:  o_t = σ(W_o · [h_{t-1}, x_t] + b_o)   输出多少信息？

# 细胞状态（信息高速公路）:
# C_t = f_t * C_{t-1} + i_t * C_tilde_t

# 隐藏状态:
# h_t = o_t * tanh(C_t)
```

### LSTM vs RNN
| 特性 | RNN | LSTM |
|------|-----|------|
| 记忆范围 | ~5步 | ~100步 |
| 梯度消失 | 严重 | 大幅缓解 |
| 参数量 | 少 | 多4倍 |
| 训练速度 | 快 | 慢 |
| 实际效果 | 差 | **好很多** |

### GRU（门控循环单元）— LSTM的简化版
```
只有2个门（重置门 + 更新门）
参数比LSTM少，效果差不多
训练更快，数据少时更好
```

## 可视化

![RNN vs LSTM](11_rnn_lstm.png)

**左图**：RNN单元结构——循环连接传递隐藏状态
**中图**：展开后的RNN——5个时间步，每个A共享权重
**右图**：梯度传播问题——W<1时指数衰减（消失），W>1时指数增长（爆炸）

## 纯numpy RNN实现

```python
import numpy as np

class RNN:
    def __init__(self, input_size, hidden_size):
        # 初始化权重（不能太大，否则梯度爆炸）
        self.W = np.random.randn(hidden_size, hidden_size) * 0.1
        self.U = np.random.randn(hidden_size, input_size) * 0.1
        self.b = np.zeros(hidden_size)
    
    def forward(self, x_seq):
        # x_seq: (seq_len, input_size)
        h = np.zeros(self.W.shape[0])
        outputs = []
        for x in x_seq:
            h = np.tanh(self.U @ x + self.W @ h + self.b)
            outputs.append(h)
        return np.array(outputs)

# 简单演示：RNN计数器
rnn = RNN(2, 4)
seq = np.array([[1,0], [0,0], [0,0], [0,0], [0,0]])  # 只在第一时间步有输入
h_seq = rnn.forward(seq)
print(f"Input only at t=0, hidden persists: {h_seq.shape}")
```

## 与Transformer的关联

LSTM解决了RNN的梯度消失，但：
1. **仍是顺序处理**——t步必须等t-1步算完（无法并行）
2. **长距离不够长**——100步够，但长文本不够

→ **Transformer彻底抛弃RNN结构，用Self-Attention替代**

## 今日收获
- RNN的核心是**共享权重的循环连接**
- 梯度消失/爆炸是RNN的"先天性疾病"
- LSTM用门控机制（遗忘/输入/输出）解决了这个问题
- GRU是LSTM的轻量版
- 但LSTM/GRU仍是顺序处理，**无法并行**——这是Transformer要解决的关键
