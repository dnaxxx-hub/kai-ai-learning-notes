# LLM 分布式推理与服务部署

> 学习笔记：从单卡部署到集群服务，Tensor/Pipeline/Sequence并行全攻略

---

## 1. 为什么需要分布式推理

### 单卡瓶颈

| 模型 | 参数 | INT4显存 | 序列(4K) KV Cache | H100 80GB | 5090 32GB |
|------|------|---------|-------------------|-----------|-----------|
| Llama 3 8B | 8B | ~4.5GB | ~2GB | ✅ | ✅ |
| Llama 3 70B | 70B | ~40GB | ~16GB | ✅ | ❌ (溢出) |
| Llama 3 405B | 405B | ~230GB | ~96GB | ❌ | ❌ |
| DeepSeek-V3 | 671B(MoE) | ~190GB(激活37B) | ~48GB | ❌ | ❌ |

**推理延迟要求**：
- **交互式**（聊天）：TTFT < 500ms, TPOT < 50ms
- **流式**（实时翻译）：TPOT < 20ms
- **离线**（批量处理）：追求Throughput，延迟不太敏感

---

## 2. Tensor Parallelism（张量并行）

将**单个层**的计算切分到多张GPU上。

### 前馈网络（FFN）切分

标准FFN：`output = activation(X @ W1) @ W2`

**列并行**（沿隐藏维度切分W1）：
```
W1 = [W1_1 | W1_2]   → 每张卡持有W1的一半
W2 = [W2_1; W2_2]     → 每张卡持有W2的一半
GPU0: activation(X @ W1_1) @ W2_1  → 部分结果
GPU1: activation(X @ W1_2) @ W2_2  → 部分结果
最终: GPU0 + GPU1 (all-reduce)
```

### 多头注意力切分

多头注意力天然适合TP：
```
GPU0: head 0,1,2,3
GPU1: head 4,5,6,7
→ 每张卡独立计算后concat输出
→ 输出时一次all-reduce
```

### 通信开销

每层TP需要2次all-reduce：
- 一次在Attention输出
- 一次在FFN输出

**通信量公式**：`2 × batch_size × seq_len × hidden_size × 2(bytes) × 2(all-reduce)`

TP的最佳实践：**单机多卡用NVLink/NVSwitch**（高速互联），跨机TP不可取（网络延迟太大）。

---

## 3. Pipeline Parallelism（流水线并行）

按层切分：GPU0负责层1-20，GPU1负责层21-40...

### GPipe（标准流水线）

```
时间→
GPU0: |F0|F1|F2|F3| |B0|B1|B2|B3|
GPU1: |  |F0|F1|F2|F3| |B0|B1|B2|B3|
GPU2: |  |  |F0|F1|F2|F3| |B0|B1|B2|
```
- micro-batch = 将大batch分成小份连续送入
- **bubble开销**：启动和收尾阶段的空闲时间
- 4个stage的bubble ≈ 37.5%

### 1F1B（One-Forward-One-Backward）

推理时只有forward，PP更简单：
- **逐层传递**：GPU0处理完 → 结果给GPU1 → GPU1处理完 → 结果给GPU2...
- 通信：仅层间中间结果，每次约 hidden_size × batch_size

### Interleaved 1F1B

进一步减少bubble：
- 每张GPU负责多个非连续的层切片
- 比如GPU0负责层1-10和层41-50（交错分配）

### PP vs TP 对比

| 特性 | Tensor Parallelism | Pipeline Parallelism |
|------|-------------------|---------------------|
| 切分方式 | 层内切分 | 层间切分 |
| 通信频率 | 每层2次all-reduce | 每层边界1次点对点 |
| 通信量 | 大（全量激活） | 小（仅中间激活） |
| NVLink需求 | 强依赖 | 不依赖 |
| 跨机扩展 | ❌ 太慢 | ✅ 可行 |

**推荐组合**：DP × TP × PP（3D并行，核心在"内部TP + 外部PP + 整体DP"）

---

## 4. Sequence Parallelism + Expert Parallelism

### 序列并行（Ring Attention）

当序列很长时（128K+），单卡放不下整个attention矩阵，需要序列并行：

```
GPU0: tokens 0-4095
GPU1: tokens 4096-8191
GPU2: tokens 8192-12287
GPU3: tokens 12288-16383
```

Ring Attention流程：
1. 每卡持有一段K/V
2. 逐轮传递Q到下一卡，计算局部attention
3. 汇总所有局部结果

**优点**：序列长度可无限扩展（受总显存限制）
**缺点**：通信开销随序列数线性增长

### MoE的Expert Parallelism

MoE模型（如Mixtral 8×7B、DeepSeek-V3）天然适合分布式：

```
GPU0: Expert A, B
GPU1: Expert C, D
GPU2: Expert E, F
GPU3: Expert G, H
```

路由过程：
1. Gate Network决定每个token去哪些expert
2. **all-to-all通信**：每个GPU把token发送到对应expert所在的GPU
3. Expert处理完后，**all-to-all通信**把结果返回

**通信量**：all-to-all是分布式中最重的通信模式之一
**优化**：
- Expert Balancing：尽量让每个expert负载均衡
- MegaBlocks：合并多个expert的token处理，减少all-to-all次数

### DeepSeek-V2的分布式架构

DeepSeek-V2采用三种并行组合：
- **Tensor Parallelism**：每台机器内部用NVLink做TP
- **Expert Parallelism**：不同expert放在不同机器
- **Sequence Parallelism**：处理超长序列

---

## 5. Prefix Caching

### 显存复用

LLM推理的大量显存被KV Cache占据。如果多个请求有相同前缀（system prompt），可以共享KV Cache：

```
Request1: "你是一个助手。请问今天天气怎么样？"
Request2: "你是一个助手。请问上海的天气？"
         └────────┬─────────┘
              共享这部分KV Cache
```

### RadixAttention（vLLM实现）

用radix tree管理KV Cache的公共前缀：

```
根
├── "你是一个助手。" (共享)
│   ├── "请问今天天气怎么样？" (Request1)
│   └── "请问上海的天气？" (Request2)
├── "翻译成英文：" 
└── "总结以下内容："
```

**核心操作**：
1. 新请求来 → 从树根开始匹配最长公共前缀
2. 匹配到的block直接复用（指针引用）
3. 未匹配的部分新分配block
4. 被复用的block增加引用计数，不被驱逐

**实际收益**：
- 多轮对话：每轮复用之前的上下文 → 节省80%+ KV Cache分配
- 带system prompt的应用：所有请求共享system prompt → 节省30-50%
- 代码补全：相同文件头/import部分共享 → 节省60%

### Copy-on-Write（写时复制）

当beam search或多种生成需要共享KV Cache时：
- 多个序列共享相同的前缀blocks
- 当某个序列要写（修改）某个block时 → 复制该block，单独持有
- 类似OS COW：共享读，复制写

---

## 6. 推理服务的Serving策略

### Dynamic Batching（动态批处理）

传统batching：等请求数凑够batch_size → 一起处理 → 延迟高

vLLM的**Continuous Batching**（迭代级批处理）：
```
传统方式：
|   请求1   |   等待   |   请求1+2+3  |   等待   |
                ↑
         浪费时间等待batch凑够

Continuous Batching：
|请求1|请求1+2|请求1+2+3|请求1+2+3+4|...
    ↑
 新请求随时插入当前位置的decode间隙
```

**效果**：吞吐量提升2-4x，延迟降低50%+

### 请求优先级

| 请求类型 | 优先级 | 示例 | 策略 |
|---------|--------|------|------|
| 交互式 | 高 | 聊天消息 | 立即处理，抢占长任务 |
| 近实时 | 中 | API调用 | 有优先级队列 |
| 离线 | 低 | 批量文档处理 | 排队，利用空闲资源 |

### Preemption（抢占）

当高优请求打断低优请求时：
1. 保存被打断请求的KV Cache状态到CPU内存（swap）
2. 高优请求执行完后恢复
3. 恢复后从断点继续生成

**代价**：CPU→GPU转移KV Cache需要时间（取决于cache大小）

### Guided Decoding（引导解码）

约束输出格式，提升可用性：
- **outlines库**：定义JSON Schema → 自动构建logit mask
- **lm-format-enforcer**：类似
- **结构化生成**：让LLM输出合法JSON/XML/代码

```
用户: "告诉我上海的天气"
LLM正常: "上海今天晴天，温度25°C..."
Guided: {"city": "上海", "weather": "晴", "temp": 25}
```

### Automatic Prefix Caching（vLLM）

vLLM的自动前缀检测：
- 不依赖用户显式指定前缀
- 在radix tree中自动查找最长匹配
- 对多轮对话、system prompt、few-shot场景自动优化

---

## 7. 推理监控指标

| 指标 | 定义 | 目标值 | 为什么重要 |
|------|------|--------|-----------|
| **TTFT** | Time To First Token | <200ms | 用户感知到的首响应速度 |
| **TPOT** | Time Per Output Token | <30ms | 生成速度，流式体验关键 |
| **Throughput** | tokens/s | 越高越好 | 服务整体容量 |
| **ITL** | Inter-token Latency | <100ms | TPOT + 调度延迟 |
| **TTFT P99** | 最慢的5%请求的首token时间 | <500ms | 服务稳定性的硬指标 |
| **KV Cache命中率** | prefix cache命中比例 | >50% | 显存效率的关键指标 |

---

## 8. 实际部署场景

### 场景1：个人运行 70B 模型（5090 32GB × 2）

```
硬件：2×5090 (NVLink)
模型：Llama 3 70B INT4 (~40GB)

方案：
- TP=2：每卡持有半数参数（~20GB）
- KV Cache：每卡约3GB（4K上下文）
- 剩余显存：~9GB用于输入/激活

效果：
- 单token延迟：~40ms
- 吞吐量：~25 tokens/s
- 可处理8K上下文
```

### 场景2：服务多用户聊天（4×A100 80GB）

```
硬件：4×A100 80GB (NVSwitch)
框架：vLLM
模型：Llama 3 70B FP16 (~140GB, TP=4 → 每卡35GB)

优化：
- Continuous Batching：实时合并请求
- Prefix Caching：复用system prompt
- AWQ INT4量化：模型缩小到40GB

效果：
- 并发：100+用户同时对话
- P99 TTFT：<300ms
- 吞吐量：2000+ tokens/s
```

### 场景3：企业级RAG系统

```
架构：
客户端 → 负载均衡(Nginx) → vLLM集群(多节点)
                        → Embedding服务
                        → Re-ranker
                        → 知识库检索(Milvus/Pinecone)

特点：
- 每个请求：检索+重排序+生成（3步延迟叠加）
- 需要低TTFT（<1s）来补偿检索时间
- Prefix Caching对RAG特有效（查询+文档前缀）

优化：
- Query改写 → 多路检索 → 重排序 → 带引用的生成
- 知识库更新时自动刷新prefix cache
```

---

## 9. 综合对比

| 框架 | DP | TP | PP | SP | EP | Prefix Cache |
|------|-----|-----|-----|-----|-----|-------------|
| **vLLM** | ✅ | ✅ | ❌ | ✅ | ⚠️ 实验性 | ✅ (RadixAttention) |
| **TensorRT-LLM** | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| **llama.cpp** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ (全在单卡) |
| **DeepSpeed** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |

**推荐选择**：
- **个人/小团队**（≤16个用户）：vLLM + 量化，单机多卡TP
- **生产环境**（数十用户）：vLLM + Prefix Caching + TP
- **大集群**（数百用户）：vLLM + TP/PP + 多节点，结合K8s自动扩缩容
- **边缘设备**：llama.cpp GGUF量化

---

## 总结

1. **TP解决显存不够**：单层切分到多卡，适合单机NVLink环境
2. **PP解决层数太多**：层间流水线，支持跨机部署
3. **SP解决序列太长**：Ring Attention跨设备分片
4. **Prefix Caching解决重复计算**：共享相同前缀的KV Cache
5. **Continuous Batching解决请求排队**：迭代级批处理提高吞吐
6. **引导解码提升可用性**：约束输出为结构化格式

三者的组合能解决从中小模型单卡部署到大模型多机集群的全场景需求，实际部署中需要根据硬件条件、延迟要求和并发量选择合适的并行策略。
