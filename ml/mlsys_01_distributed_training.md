# MLSys 第1课：分布式训练与模型并行

> 核心问题：模型太大，训练太久，怎么分？

## 1. 为什么需要分布式训练

### 1.1 模型太大，单卡放不下

| 模型 | 参数量 | 显存需求 (FP32) | 显存需求 (FP16) |
|------|--------|-----------------|-----------------|
| BERT-Large | 340M | ~1.36 GB | ~680 MB |
| GPT-3 175B | 175B | ~700 GB | ~350 GB |
| Llama 3 405B | 405B | ~1.6 TB | ~810 GB |

参数之外，中间激活值（activation memory）在训练时也需要存储。训练时总显存 ≈ 参数 × (optimizer_states + gradients + params) + activations。

**量化示例：** GPT-3 175B 在 FP16 下训练：
- 参数：175B × 2B = 350 GB
- 梯度：175B × 2B = 350 GB  
- Adam 优化器状态：m + v = 175B × 2B × 2 = 700 GB
- **总计：~1.4 TB，单张 A100 (80GB) 完全装不下**

### 1.2 单卡训练太久

- 单张 V100 (32TFLOPS FP32) 训练 GPT-3：约 **355 年**
- 单张 A100 (312TFLOPS FP16) 训练 GPT-3：约 **36 年**
- 1024 张 A100 分布式训练 GPT-3：约 **34 天**（考虑通信开销后实际更长）

**结论：** 不分布式，大模型根本训不了。

---

## 2. 数据并行（Data Parallelism）

### 2.1 基本原理

每张卡持有**完整**模型副本，各自处理不同的 mini-batch 数据。

```
Worker 0: [batch_0] → Forward → Loss → Backward → Gradients
Worker 1: [batch_1] → Forward → Loss → Backward → Gradients
Worker 2: [batch_2] → Forward → Loss → Backward → Gradients
Worker 3: [batch_3] → Forward → Loss → Backward → Gradients
                            ↓
                    AllReduce(Gradients)
                            ↓
所有 Worker 得到相同平均梯度 → 各自更新参数
```

### 2.2 同步 SGD vs 异步 SGD

| 特性 | 同步 SGD | 异步 SGD |
|------|----------|----------|
| 梯度同步 | 所有 worker 算完才更新 | 谁算完谁更新 |
| 收敛质量 | 等同单卡 SGD | 有 stale gradient 问题，收敛慢 |
| 吞吐量 | 受最慢 worker 拖累（straggler） | 无 straggler 限制 |
| 实现复杂度 | 需要 barrier 同步 | 简单，各 worker 独立 |
| 实际使用 | **主流**（配合 batch size warmup） | 少用 |

### 2.3 Parameter Server 架构（PS）

**经典设计：** M 个 worker + S 个 server

```
Worker → Push(gradients) → Server → Pull(params) → Worker
          ↑                                    ↓
          +--- 每个 worker 只和 server 通信 ---+
```

- Server 存储参数和优化器状态，负责聚合梯度、更新参数
- Worker 拿完整参数 → 前向/反向 → 推梯度到 server
- 瓶颈：server 带宽成为中心瓶颈；M 越大，server 压力越大

### 2.4 Ring AllReduce

**解决中心瓶颈：** 所有设备排成环，每个设备只和邻居通信，带宽 O(N)。

**两阶段算法：**

**阶段1：Scatter-Reduce**（N-1 步）
- 每步每个节点发送一个 chunk 给下一个节点
- 接收后求和累加
- 结束时每个节点持有**一个 chunk 的完整聚合结果**

```
初始：       [A0, A1, A2, A3]   [B0, B1, B2, B3]   [C0, C1, C2, C3]   [D0, D1, D2, D3]
                                                                        ↑ 环中每个节点
步1: D发D3→A收+D3, A发A1→B收+A1 ... 每个 chunk 在不同节点累加
步2: 继续旋转
步3: 结束 → 每个节点持有一个完全聚合的 chunk
```

**阶段2：AllGather**（N-1 步）
- 每个节点把它那一个已聚合的 chunk 沿环传播出去
- 其他节点收到后直接覆盖（不求和）
- 结束时每个节点持有完整的聚合梯度

**通信量分析：**
- 总数据量 = 2(N-1) × chunk_size
- 每个节点发送/接收的数据 = 2(N-1)/N × 总参数量
- 当 N 很大时，每节点通信量 ≈ 2× 参数量（最优）

**对比：**

| 架构 | 每节点通信量 | 中心瓶颈 | 拓扑要求 |
|------|-------------|---------|---------|
| PS | O(N) 参数量 | 有 (server) | star |
| Ring AllReduce | O(1) 参数量 | 无 | ring |
| Tree AllReduce | O(log N) 步数 | 无 | tree |

---

## 3. 模型并行（Model Parallelism）

### 3.1 层内切分（Tensor Parallelism / TP）

将一个**矩阵乘法**切分到多卡上并行计算。

**例：Y = X × W，将 W 按列切分成 2 份**

```
标准：   X(1×d) × W(d×2d) → Y(1×2d)
TP:      X × [W_0 | W_1] → [Y_0 | Y_1]

GPU0:   X × W_0 → Y_0
GPU1:   X × W_1 → Y_1
        ↓ AllGather(Y_0, Y_1) → 完整 Y
```

对于 Transformer 的 MLP 层和 Attention 层，TP 是标准做法（源自 Megatron-LM）：

- **MLP 前向：** ffn1 按列切分 → 激活 → ffn2 按行切分（减少一次 AllReduce）
- **Self-Attention：** 多头注意力天然可并行，每卡负责部分头

**通信：** 每个 TP 层前后各一次 AllReduce（或 ReduceScatter + AllGather）

### 3.2 层间切分（Pipeline Parallelism / PP）

不同层放在不同 GPU 上：

```
GPU0: [Layer 1-4]  GPU1: [Layer 5-8]  GPU2: [Layer 9-12]  GPU3: [Layer 13-16]
         ↓                 ↓                  ↓                   ↓
      FWD(1-4) → 中间激活 → FWD(5-8) → 中间激活 → FWD(9-12) → FWD(13-16) → Loss
      BWD(1-4) ← 梯度传递 ← BWD(5-8) ← 梯度传递 ← BWD(9-12) ← BWD(13-16)
```

**朴素流水线的问题：** GPU3 等待 GPU0、1、2 完成前向后才能开始工作 → 大量空闲时间（pipeline bubble）

**空闲率公式：** bubble = (P-1) / (P + M - 1)，其中 P = 流水线级数，M = micro-batch 数

当 P 很大、M 很小时，bubble 严重。

### 3.3 GPipe 与 PipeDream

**GPipe（Google, 2019）：**
- 将 batch 拆成 micro-batch，依次送入流水线
- 前向全部完成后统一反向 → 累加梯度 → 更新参数
- 简单但 bubble 仍然存在
- 通过增大 micro-batch 数来减少 bubble 占比

**PipeDream（Microsoft, 2019）：**
- **1F1B 调度**（One Forward One Backward）：尽早开始反向传播
- 一个 micro-batch 前向完成后立即反向，无需等待全部完成
- 节省约一半激活内存（不需要同时保存所有 micro-batch 的激活值）
- 但引入参数版本问题：反向时用的参数版本不一致

```
GPipe 调度:
    时间→
  GPU0: [F0][F1][F2][F3]        [B3][B2][B1][B0]
  GPU1:      [F0][F1][F2][F3]   [B3][B2][B1][B0]
  大量空闲

PipeDream (1F1B):
    时间→
  GPU0: [F0][F1][F2][F3][B0][B1][B2][B3]
  GPU1:      [F0][F1][F2][F3][B0][B1][B2]
  空闲少得多
```

---

## 4. 混合并行

### 4.1 3D Parallelism

同时使用数据并行 × 张量并行 × 流水线并行，三者互为"正交"维度。

**典型配置（NVIDIA Megatron-LM + DeepSpeed）：**

```
数据并行度 = 64（64 组模型副本）
  每组内部：
    张量并行度 = 8（单层切 8 卡，TP 通信频繁 → 放同一节点内）
    流水线并行度 = 4（切 4 段，跨节点）
  总 GPU = 64 × 8 × 4 = 2048
```

**通信层次：**
- TP：高带宽（节点内 NVLink/NVSwitch，~600 GB/s），AllReduce 频繁
- PP：中带宽（点对点，传输激活值和梯度）
- DP：低带宽（跨节点 InfiniBand/RoCE），梯度同步 AllReduce

**设计原则：** 通信最频繁的放在速度最快的连接上。

### 4.2 ZeRO（Zero Redundancy Optimizer）

**洞察：** 数据并行中，每卡都存了完整参数、梯度、优化器状态 → 大量冗余。

**ZeRO 三阶段：**

| 阶段 | 分片内容 | 内存节省（相对DP） | 通信量 |
|------|---------|-------------------|--------|
| ZeRO-1 | 优化器状态 (m, v) | 4× | 同 DP |
| ZeRO-2 | + 梯度 | 8× | 同 DP |
| ZeRO-3 | + 参数 | 16× | 增加约 1.5× |

**ZeRO-1 原理：**

```
常规 DP（N 卡）:
  每卡: params + gradients + m + v = 全量 × N 份冗余

ZeRO-1（N 卡）:
  每卡: params + gradients + (1/N 的 m + 1/N 的 v)
  每卡只更新自己的那 1/N 参数
  更新完后广播给所有人
```

**ZeRO-3 原理（参数分片）：**
- 前向时：动态 AllGather 获取所需参数 → 计算 → 丢弃其他卡的参数
- 反向时：再次 AllGather 获取参数来计算梯度
- 梯度计算后：ReduceScatter 分片存储

**ZeRO vs 模型并行：**
- ZeRO **不涉及计算切分**，每卡仍然计算完整图
- 模型并行切分计算，但通信模式不同
- ZeRO + TP + PP 可叠加使用（实际训练中经常同时使用）

---

## 5. Python 分布式训练模拟

### 5.1 核心组件

```
训练模拟 = {
    "模型": SimpleMLP(d_in=64, d_hidden=256, d_out=10),
    "优化器": SGD(lr=0.01),
    "通信": AllReduce / ParameterServer / Pipeline,
    "数据": DataLoader(batch_size=32, num_batches=100),
}
```

### 5.2 代码实现

详见 `memory/learning/code/mlsys_01_distributed_training.py`

模拟了三个核心场景：

**场景1：数据并行 + Ring AllReduce**
- 4 个 worker，100 batch
- 每个 worker 独立计算梯度 → AllReduce 聚合 → 同步更新
- GPU 模拟：每步耗时随参数量线性增长，通信耗时随梯度量线性增长

**场景2：Parameter Server 架构**
- 4 worker + 2 server
- Worker 计算梯度 → Push 到 server → Server 聚合 → 更新参数 → Pull 回 worker
- 模拟 server 带宽瓶颈：server 侧通信时间随 worker 数增长

**场景3：流水线并行（PipeDream 1F1B）**
- 4 级流水线，每级 4 层
- 16 个 micro-batch，1F1B 调度
- 前向 → 反向交错执行，减少 bubble 空闲
- 统计每级 GPU 时间线

### 5.3 模拟结果要点

```
AllReduce 通信量: 每次同步 2(N-1)/N × 参数量
  N=4: 1.5× 参数量
  N=8: 1.75× 参数量
  N=16: 1.875× 参数量

PS 架构:
  Server 总带宽负担 = M × 参数量 × 精度（push + pull）
  M=4 时 server 侧负担是 AllReduce 的 2.7×
  M=8 时差 5.3×

流水线 bubble:
  P=4, M=16: 空闲率 ≈ 15.8%
  P=8, M=16: 空闲率 ≈ 30.4%
  P=8, M=64: 空闲率 ≈ 9.9%
```

---

## 总结：分布式训练的关键权衡

| 技术 | 优点 | 缺点 | 何时使用 |
|------|------|------|---------|
| 数据并行 (DP) | 实现简单，batch 增大，吞吐线性增长 | 每卡需存完整模型 | 模型能放进单卡时 |
| 张量并行 (TP) | 减少单卡显存，计算拆分 | 通信频繁，需高带宽 | 超大层（Transformer MLP/Attn） |
| 流水线并行 (PP) | 减少单卡显存，通信适中 | 流水线 bubble | 模型层数多时 |
| ZeRO | 不切计算，仅去冗余，几乎无通信开销增加 | ZeRO-3 需要频繁 AllGather | 数据并行显存不足时 |

**实际 LLM 训练配置（参考 GPT-3）：**
- TP=8（节点内，NVLink）
- PP=4（跨节点，点对点）
- DP=64（跨节点，梯度 AllReduce）
- ZeRO-1（优化器状态分片）
- 总计：8×4×64 = 2048 GPU

### 课后思考

1. AllReduce 通信量公式中，为什么是 2(N-1)/N 而不是 2 ？
2. 如果将 Ring AllReduce 用在跨节点低速网络上，有什么优化手段？
3. 为什么 TP 通常只在节点内部使用，而 PP 可以跨节点？
4. ZeRO-3 在计算/通信比小的情况下会有性能问题吗？（提示：AllGather 开销）
5. 1F1B 调度中的参数版本不一致问题如何解决？（PipeDream 的解法：weight stashing + vertical sync）
