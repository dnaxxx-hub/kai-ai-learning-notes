# LLM推理框架与部署实践

> **目标读者**：已经理解 Transformer 推理流程和模型量化原理的 AI 工程师
> **版本**：v1.0 | **日期**：2024

---

## 目录

1. [vLLM 深度解析](#vllm-深度解析)
2. [TensorRT-LLM](#tensorrt-llm)
3. [llama.cpp / Ollama](#llamacpp--ollama)
4. [推理服务的部署架构](#推理服务的部署架构)
5. [框架对比](#框架对比)

---

## vLLM 深度解析

### 架构概述

vLLM 采用了模块化的高性能推理架构，核心组件包括：

```
┌─────────────────────────────────────────────────────────────┐
│                      vLLM Engine                              │
│  ┌──────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │  LLM Engine   │  │  Block Manager  │  │  Scheduler      │  │
│  │  · PagedAttn │  │  · KV Cache     │  │  · 任务调度     │  │
│  │  · BatchMgmt │  │  · 显存管理     │  │  · 请求队列     │  │
│  └──────────────┘  └─────────────────┘  └────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Scheduler                           │  │
│  │  · FCFS/SJF/等待时间优先策略                          │  │
│  │  · Continuous Batching                                │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    GPU Memory (PagedAttention)          │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │  Request Pool  │  Request Pool  │  ...           │   │  │
│  │  └────────────────┴────────────────┴────────────────┴───┴─┘│
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**组件职责**：
- **LLM Engine**：执行前向传播，维护活跃的 request 集合
- **Block Manager**：管理显存中的 KV Cache 块
- **Scheduler**：处理请求队列，决定哪些请求进入 decode 阶段

### Continuous Batching

与传统批处理不同，vLLM 采用了**迭代级批处理**机制：

**工作流程**：

```
时间轴：
  ↓
┌─────┐
│  1  │←─ 初始一批请求
└─────┘

┌─────┐         ┌─────┐
│  2  │←─ 在1号请求的  │  3  │←─ 在2号请求的
│     │←─ 空闲间隙插入 │     │←─ 空闲间隙插入
└─────┘         └─────┘

┌─────┐     ┌─────┐     ┌─────┐
│  2  │←─ 继续          │  3  │     │  4  │
│     │←─ 继续          │     │←─ 新插入
└─────┘     └─────┘     └─────┘
```

**关键特性**：

1. **动态插入**：在 decode 间隙插入新请求，无需等待所有请求完成
2. **请求重排序**：按照 block 状态重新组织 batch，提高 GPU 利用率
3. **早退机制**：已完成生成长度请求可立即移出 batch

**性能优势**：
- 减少 GPU 空闲时间
- 提高吞吐量 30-50%
- 降低首 token 延迟 (TTFT)

### PagedAttention

接第一课，PagedAttention 是 vLLM 的核心创新：

**问题背景**：
```
传统 KV Cache 显存布局：
┌──────────────────────────────────┐
│  Request A                        │
│  ┌────────────────────────────┐  │
│  │ Block 00-xx    Block xx-xx │  │
│  └────────────────────────────┘  │
│  Request B                       │
│  ┌────────────────────────────┐  │
│  │ Block 00-xx    Block xx-xx │  │
│  └────────────────────────────┘  │
│  Request C (显存碎片化！)         │
│  ┌────────────────────────────┐  │
│  │                         │  │
│  │       (浪费)            │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
显存利用率：<60%
```

**PagedAttention 解决方案**：

```
PagedAttention 显存布局：
┌──────────────────────────────────┐
│  Block Pool (统一块管理)          │
│  ┌────────────────────────────┐  │
│  │ Block 0   Block 1  Block 2 │  │
│  │  (1×1MB)   (1×1MB)   (1×1MB)│  │
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │ Request A ─Block 00, 02,07│  │
│  │ Request B ─Block 01, 03,08│  │
│  │ Request C ─Block 04, 05,09│  │
│  └────────────────────────────┘  │
│                                  │
│  每个请求独立，无碎片化            │
│  支持 Prefix Caching             │
└──────────────────────────────────┘
显存利用率：>95%
```

**技术细节**：

- **块大小**：默认 16 blocks (每块约 1MB)
- **页表**：每个请求维护块索引映射表
- **前向传播**：将多个块拼接为连续内存执行 attention
- **Prefix Caching**：缓存共享的 prompt KV Cache

**Prefix Caching 优化**：

```
用户 A:  "你好，今天天气很好" → 模型输出 100 tokens
用户 B:  "你好，今天风很大"     → 复用"你好"的 KV Cache

优化流程：
1. 用户 A: 计算并缓存"你好"的 KV Cache (block=10,11)
2. 用户 B: 直接复用"你好"的 KV Cache (减少66%的 decode 时间)
3. 剩余部分各自计算
```

### 调度策略

vLLM 提供多种调度策略：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **FCFS** (First-Come-First-Served) | 先到先服务 | 简单场景，保证公平性 |
| **SJF-like** (Shortest-Job-First) | 优先处理短请求 | 批量短文本生成任务 |
| **Waiting Time Priority** | 等待时间优先 | 减少队列延迟，提升用户体验 |

**调度器算法**：

```python
# 简化版调度决策
scheduler = vLLM.Scheduler()
scheduler.update_num_available_blocks()  # 更新可用块
scheduler.add_batch(new_requests)        # 添加新请求
scheduler.schedule()                      # 调度决策

# 调度结果包含：
# - 哪些请求进入decode阶段
# - 哪些请求等待
# - batch的block分配
```

### vLLM API 接口

vLLM 提供 OpenAI 兼容 API：

**部署方式**：

```bash
# 启动服务
python -m vllm.entrypoints.api_server \
    --model meta-llama/Llama-2-7b \
    --served-model-name my-model

# 默认端口8000，访问：http://localhost:8000
```

**API 调用**：

```bash
# 聊天完成
curl http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "my-model",
        "messages": [
            {"role": "user", "content": "写首诗给我"}
        ],
        "max_tokens": 500,
        "temperature": 0.7
    }'
```

**关键参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `max_tokens` | int | 最大生成 token 数 |
| `temperature` | float | 温度采样参数 (0-2) |
| `top_p` / `top_k` | float / int | 核采样/截断采样 |
| `seed` | int | 随机种子 (固定可复现) |
| `stop` | list | 停止 token |

**高级功能**：

```python
from vllm import LLM, SamplingParams

llm = LLM(model="model_path")

# 生成参数
sampling_params = SamplingParams(
    temperature=0.8,
    top_p=0.9,
    max_tokens=500,
    repetition_penalty=1.1
)

# 批量生成
outputs = llm.generate(
    prompt=prompts,
    sampling_params=sampling_params,
    use_tqdm=True  # 显示进度
)
```

---

## TensorRT-LLM

### 概述

**NVIDIA 官方推理框架**，面向 GPU 极致优化，深度学习推理框架中的性能天花板。

**核心目标**：
- 最大化 GPU 利用率
- 支持大规模模型并行
- 端到端优化 (图优化)

### 图优化

**核心优势**：算子融合与 Layers 合并

```
原始计算图：
Layer1: Linear → ReLU → Layer2: Linear → ReLU
      ↓                    ↓
   CUDA kernel A        CUDA kernel B
   (分离运行，传输显存)

优化后 (Fused Layer)：
Layer1+2: Linear → ReLU → Linear → ReLU
      ↓
   CUDA kernel C (单算子，零传输开销)
```

**优化技术**：

1. **算子融合** (Operator Fusion)
   - 融合多个小算子为一个大核
   - 减少内核启动开销
   - 提高内存带宽利用率

2. **Layers 合并**
   - 将连续的 transformer layer 合并
   - 共享权重加载
   - 减少全局批处理效应 (GBF)

3. **多版本生成**
   - FP16、INT8、FP8 等混合精度计算
   - 支持 Tensor Core 指令集

### 量化插件

TensorRT-LLM 提供全功能量化支持：

| 量化类型 | 精度 | 特点 | 性能提升 |
|----------|------|------|----------|
| **FP16** | 16-bit | 基础半精度 | 基准 |
| **INT8** | 8-bit | 权重量化 | 27% 吞吐提升 |
| **INT4** | 4-bit | AWQ 风格 | 40% 吞吐提升 |
| **FB8** | 2-bit/4-bit | 分块量化 | 50% 吞吐提升 |

**量化流程**：

```
1. Profile (校准数据集)
   ↓
2. 分析激活值分布
   ↓
3. 生成量化映射表
   ↓
4. 生成 TRT Engine (量化模型)
   ↓
5. 推理加速
```

**量化命令示例**：

```bash
# 生成校准数据
python calibrator.py \
    --datadir /data/calibration \
    --batch-size $BATCH_SIZE

# 构建 engine
trtllm-build \
    --model_dir ./models \
    --calib_file ./calibration_data.bin \
    --calib_batch_size $BATCH_SIZE \
    --int8 \
    --output_trt_engine ./engine.plan

# 支持AWQ权重解析
--awq_config_path ./awq_config.json
```

### In-flight Batching

TensorRT-Variable 支持类似 vLLM 的 In-flight Batching：

```
┌─────────────────────────────────────┐
│  Flight Queue (飞行队列)             │
│                                     │
│  Request A (80% 完成)              │
│  Request B (20% 完成)              │
│  Request C (0% 等待插入)              │
│  ↓                                   │
│  在间隙动态插入新请求                    │
└─────────────────────────────────────┘

与传统 Batch 对比：
传统：等待所有请求完成 → 统一输出
In-flight: Decode 间隙插入新请求 → 逐步输出
```

### 多GPU支持

TensorRT-LLM 原生支持大规模多GPU部署：

**Tensor Parallelism (TP)**：

```
单卡8B模型：
┌────────────────────────┐
│    Transformer Layer    │
│  Query/Key/Value (KV)  │
│                       │
└────────────────────────┘
         ↓

TP8 (8卡并行)：
┌────┬────┬────┬────┬────┬────┬────┬────┐
│ TP0│ TP1│ TP2│ TP3│ TP4│ TP5│ TP6│ TP7│
├────┼────┼────┼────┼────┼────┼────┼────┤
│   ┌────────────────────┐│
│   │    Layer 0          ││
│   └────────────────────┘│
└─────────────────────────┴─┴───┴───┴─┴───┴─┴───┘
每卡负责部分 QKV → 通信同步 → 逐层并行
```

**Pipeline Parallelism (PP)**：

```
多机分布式部署：
Machine 1         Machine 2         Machine 3
┌─────────┐       ┌─────────┐       ┌─────────┐
│ Layers1-3│  PP→ │ Layers4-6│  PP→ │ Layers7-12│
│         │       │         │       │         │
└─────┬───┘       └─────┬───┘       └─────┬───┘
      │ Pipeline Bubble │                 │
      └─────────────────┘                 │
               │ TP4卡                    │
               └───────────────────────────┘

PP 数据流：
Layer0-2 → Layer3-5 → Layer6-9 → Layer10-12
     (Microbatch0)  (Microbatch1)  (Microbatch2)
```

**混合并行**：

```
2x TP4 + 2x PP4 = 32B LLaMA 模型
单机 8 卡，双机 16 卡，总计 32 张 GPU
```

---

## llama.cpp / Ollama

### llama.cpp

**特点**：纯C/C++实现，极致轻量，无GPU也能跑

**架构极简**：

```
┌─────────────────────────────────────┐
│              llama.cpp               │
│                                     │
│  CPU 推理 (无GPU) / 量化模型支持       │
│  GGUF 格式                          │
│                                     │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│          Ollama (Go封装)             │
│                                     │
│  REST API + Docker 化                │
│  GPU 自动检测 + CUDA 优化              │
└─────────────────────────────────────┘
```

**技术亮点**：

1. **纯CPU支持**：无GPU也能流畅推理
2. **多核优化**：充分利用CPU多核
3. **AVX-512 指令集**：Intel 高端CPU优化
4. **量化支持**：Q2_0, Q3_0, Q4_0, Q5_0, Q8_0 等多种

**GGUF 格式**：

```
GGUF 文件结构：
┌──────────────────────────────────┐
│  Magic Number: 0x47575747(GGUF)  │
│  Version: 3                      │
│  Architecture: x86_64            │
│  ┌────────────────────────────┐  │
│  │ Weights (INT8/INT4混合)     │  │
│  └────────────────────────────┘  │
│  Metadata (参数量、版本等)         │
└──────────────────────────────────┘

支持的量化：
- Q2_K 2-bit  ~70% 精度保留，5x 显存节省
- Q3_K_S 3-bit~90% 精度保留，3x 显存节省
- Q4_K_M 4-bit~95% 精度保留，CPU 流畅推理
- Q5_K_M 5-bit~97% 精度保留，兼容性好
- Q8_0   8-bit  ~99% 精度保留，接近FP16
```

### Ollama

**Ollama 简介**：llama.cpp 的 Go 语言封装，提供开箱即用体验

**一键运行**：

```bash
# 安装 Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 拉取模型
ollama pull llama3

# 运行模型
ollama run llama3 "你好，请介绍一下你自己"

# 查看运行状态
ollama ps
```

**REST API**：

```bash
# 聊天接口
curl http://localhost:11434/api/generate \
    -d '{
        "model": "llama3",
        "prompt": "写一首短诗",
        "stream": false
    }'

# 流式响应
ollama run llama3 "为什么天空是蓝色的?"

# 查看模型信息
ollama show llama3 --format json
```

**Docker 化部署**：

```bash
docker pull ollama/ollama
docker run -d \
    --gpus all \
    -v "$PWD:/root/.ollama" \
    -p 11434:11434 \
    -e "OLLAMA_MODELS=/root/.ollama/models" \
    -e "OLLAMA_MAX_QUEUE=256" \
    -e "OLLAMA_NUM_PARALLEL=4" \
    ollama/ollama
```

**适用场景**：

| 场景 | 适用性 | 说明 |
|------|--------|------|
| 个人电脑 | ✅ 完美 | 单卡/集成显卡均可 |
| 边缘设备 | ✅ 推荐 | Raspberry Pi、Jetson 等 |
| 小模型 (<7B) | ✅ 首选 | CPU 推理速度快 |
| 大模型 (70B+) | ❌ 限制 | 推荐vLLM/TensorRT-LLM |

---

## 推理服务的部署架构

### 单机多卡 vs 多机多卡

**单机多卡 (Single-Node Multi-GPU)**：

```
┌────────────────────────────────────────┐
│           Server Node                   │
│  ┌──────────┐  ┌──────────┐            │
│  │  GPU 0   │  │  GPU 1   │  NCCL  │
│  │  LLM A   │  │  LLM A   │  通信   │
│  │ (vLLM)  │  │ (vLLM)  │            │
│  │ TP=1    │  │ TP=1    │            │
│  └──────────┘  └──────────┘            │
│  ┌──────────┐  ┌──────────┐            │
│  │  GPU 2   │  │  GPU 3   │            │
│  │  LLM B   │  │  LLM B   │            │
│  │ (vLLM)  │  │ (vLLM)  │            │
│  │ TP=2    │  │ TP=2    │            │
│  └──────────┘  └──────────┘            │
└────────────────────────────────────────┘

优点：
- 通信延迟低 (NVLink)
- 简单部署
- 适合中小规模部署

缺点：
- 扩展性受限
- 单机性能上限
```

**多机多卡 (Multi-Node Multi-GPU)**：

```
┌─────────────────────────────────────────────────────────┐
│              Multi-Cluster Architecture                   │
├──────────────┬──────────────────────────┬───────────────┤
│              │      Load Balancer       │               │
│         ┌───►└──────────────────────────┘│         ┌───┐│
│         │                                 │         │   ││
│  ┌─────►│  Node 1 (TP=4) TP=4            │         │   ││
│  │GPU x8   │  ┌────┬────┐               │         │   ││
│  │         │  │LLM LLM│                │         │   ││
│  └─────┐   └─┤A  │  A│                │         │   ││
│         │     └────┴────┘               │         │   ││
│         │                                 │         │   ││
│         ▼                                 │         │   ││
│  ┌─────►│  Node 2 (TP=4) TP=4            │         │ 🔄 ││
│  │GPU x8   │  ┌────┬────┐               │         │ 🔄 ││
│  │         │  │LLM LLM│                │         │ 🔄 ││
│  └─────┐   └─┤A  │  A│                │         │ 🔄 ││
│         │     └────┴────┘               │         │   ││
│         │                                 │         │   ││
│         │                                 │         │   ││
│         │       Nginx/gRPC LB            │         │   ││
│         │         (路由)                 │         │   ││
│         │                                 │         │   ││
│         └─────────────────────────────────┘         │ 🔄 ││
└──────────────────────────────────────────────────────┴─┴──┴─┴─┴────────┘

优化技术：
- 请求亲和性：同一请求的 token 在同一节点完成
- 预取策略：提前加载下一个请求的权重
- 故障转移：节点故障时请求自动转移
```

### 推理吞吐量指标

**关键指标定义**：

1. **TTFT (Time To First Token)** - 首 token 延迟
   ```
   TTFT = 模型加载 + 编码时间 + 首层解码
        ≈ Encoding Time + 1st Layer Decode
   ```

2. **TPOT (Token Per Output Token)** - 每 token 延迟
   ```
   TPOT = Decode Time / Token
   ```

3. **Throughput (tokens/s)** - 吞吐量
   ```
   Throughput = 总生成 token 数 / 总时间
   ```

**指标公式**：

```
总响应时间 = TTFT + (TPOT × 生成长度)

示例：
TTFT = 50ms, TPOT = 2ms, 长度 = 200 tokens
总时间 = 50ms + 2ms × 200 = 450ms

如果 TPOT=1ms, 总时间 = 50ms + 1ms × 200 = 250ms (50% 改进)
```

### 负载均衡与请求排队

**负载均衡策略**：

```
请求到达 → [排队] → [调度决策] → [GPU 选择] → [队列插入] → [请求处理]

┌───────────────────────────────────────────────┐
│              Load Balancer                     │
│                                               │
│  请求队列:                                     │
│  ├── Queue A (GPU 0, QPS=50)                  │
│  ├── Queue B (GPU 1, QPS=55)                  │
│  └── Queue C (GPU 2, QPS=48)                  │
│                                               │
│  调度算法:                                     │
│  ├── 轮询 (Round-Robin)                       │
│  ├── 最小延迟优先 (Least Latency)              │
│  ├── 加权轮询 (Weighted RR - 按 QPS 权重)      │
└───────────────────────────────────────────────┘
```

**NATS 消息队列示例**：

```bash
# 部署 NATS 作为中间件
docker run -d --name nats \
    -p 4222:4222 \
    nats:latest

# 发布请求到 NATS
curl -XPOST "nats://nats:4222/request.stream" \
    -d '{"model":"llama3","prompt":"你好"}'

# 消费请求
docker run -d --name nats-consumer \
    --link nats \
    -e NATS_SERVER=nats:4222 \
    my-inference-service
```

### 缓存策略

**Prefix Caching (前缀缓存)**：

```
共享前缀的 KV Cache 复用：

Request A: "你好，今天天气很" → [Cache] → 好
Request B: "你好，今天风很"   → [Cache] → 大
Request C: "你好，下雨了"     → [Cache] → 了

Request D: "再见，明天见"     → [计算]  → 了

缓存命中率 = (共享前缀请求数) / 总请求数

优化效果：
- 减少50-70%的decode时间
- 提高系统整体吞吐
```

**RadixAttention (Radix Attention)**：

```
RadixAttention 数据结构：

┌─────────────────────────────────────┐
│         Radix Tree                   │
│                                     │
│           ┌───────┐                │
│           │ Root  │                │
│           └───────┘                │
│               │                     │
│        ┌──────┴──────┐             │
│        │             │             │
│   ┌────┴──┐    ┌────┴──┐          │
│   │  "你" │    │  "再" │          │
│   └───┬───┘    └───┬───┘          │
│   ┌───┴──┐        │               │
│   │  好  │        │               │
│   └──────┘        │               │
│                  ┌──┴───┐          │
│                  │  见  │          │
│                  └──────┘          │
└─────────────────────────────────────┘

工作原理：
1. 构建共享前缀树
2. 查询时查找最长匹配前缀
3. 复用已计算 KV Cache
4. 新 token 扩展路径
5. 内存共享，零拷贝

性能提升：
- 3-5x 前缀复用效率
- 适用于多用户聊天场景
```

---

## 框架对比

### 综合对比表

| 特性 | vLLM | TensorRT-LLM | llama.cpp |
|------|------|--------------|------------|
| **GPU 优化** | ✅ 良好 | ✅✅ 最极致 | ⚠️ 通用 (CPU 为主) |
| **CPU 推理** | ❌ 不支持 | ❌ 不支持 | ✅ 完美支持 |
| **量化支持** | AWQ/GPTQ | 全量NVIDIA量化 | GGUF K-quants |
| **部署复杂度** | 低 | 高 (需要编译) | 极低 (单命令) |
| **生产环境** | ✅ 常用 | ✅ 大厂首选 | ❌ 个人/边缘 |
| **吞吐量** | 高 (30-50% 提升) | 极高 (50%+ 提升) | 中 (依赖硬件) |
| **显存利用率** | >95% | >90% | 中等 |
| **文档完善度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **社区活跃度** | 高 | ⭐⭐⭐ (NVIDIA内部) | 极高 |
| **调试友好度** | 中等 | 困难 (二进制优化) | 极高 (源码级别) |

### 详细对比分析

#### 1. 性能表现

**吞吐量对比 (7B 模型，NVIDIA A100)**：

| 框架 | 单卡 TPOT | 多卡 TP=4 | 吞吐量 |
|------|-----------|-----------|--------|
| **vLLM** | 5.2ms | 5.6ms | 200+ tokens/s |
| **TensorRT-LLM** | 2.1ms | 2.3ms | 450+ tokens/s |
| **llama.cpp** | 15ms | - | 60+ tokens/s |

#### 2. 显存对比 (7B 模型)

| 框架 | FP16 (GB) | INT8 (GB) | INT4 (GB) |
|------|-----------|-----------|-----------|
| **vLLM** | 14.0 | 7.5 | 5.5 |
| **TensorRT-LLM** | 13.5 | 7.0 | 4.8 |
| **llama.cpp** | - | - | 5.2 |

#### 3. 适用场景推荐

**生产环境选择建议**：

```
┌────────────────────────────────────────┐
│           场景决策树                    │
├────────────────────────────────────────┤
│                                        │
│  大模型 (>70B) ──► TensorRT-LLM       │
│         └─多机部署─┤                  │
│                    │                  │
│  中小模型 (7-70B) ─┬─► vLLM           │
│                     │ 单机多卡         │
│                     └─► llama.cpp      │
│                           CPU 场景      │
│                     ├──► llama.cpp     │
│                     └─► CPU推理         │
│                                        │
│  延迟敏感型 ──► vLLM (等待时间优先)    │
│         吞吐敏感型 ──► TensorRT-LLM    │
└────────────────────────────────────────┘
```

### 架构选择指南

**单机部署**：

- **GPU < 8G**：llama.cpp (CPU 推理)
- **GPU 8-48G**：vLLM (最佳平衡)
- **GPU > 48G/多卡**：TensorRT-LLM (多卡并行)

**云端部署**：

```
云厂商推荐配置：

AWS Sagemaker:
  - 使用 vLLM (已有 Sagemaker 镜像)
  - 多 GPU 实例启动 vLLM 服务
  - 自动扩展基于请求量

Azure AI:
  - TensorRT-LLM 镜像
  - 支持多卡A100/A100-80GB
  - 与Azure ML集成

阿里云百炼/PAI:
  - 支持vLLM镜像
  - 支持TensorRT-LLM
  - 自动弹性伸缩
```

### 最佳实践

**vLLM 最佳实践**：

```bash
# 生产环境启动配置
python -m vllm.entrypoints.api_server \
    --model meta-llama/Llama-2-7b \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --swap-space 4GB \
    --tensor-parallel-size 1 \
    --distributed-executor-backend ray \
    --served-model-name my-model

# 使用PagedAttention
--enable-chunk-prefilling
```

**TensorRT-LLM 最佳实践**：

```bash
# 使用INT8量化
trtllm-build \
    --model_dir ./models \
    --fp16 \
    --calib_data_path ./calibration \
    --calib_batch_size 16 \
    --output ./engine

# 多卡部署
trtllm-run \
    --engine_dir ./engine \
    --tp-size 4 \
    --world-size 2
```

**llama.cpp 最佳实践**：

```bash
# CPU 优化编译
make LLAMA_CUDA=1 \
    CUBLAS=1 \
    CUBLAS_PATH=/usr/local/cuda \
    CUDART=/usr/local/cuda \
    OPENMP=1

# 运行
./main -m quantized.gguf -p "你好" -n 500
```

---

## 总结与建议

### 选型决策表

| 场景 | 推荐框架 | 理由 |
|------|----------|------|
| **初创公司/单卡** | vLLM | 部署简单，性能优秀 |
| **大厂生产环境** | TensorRT-LLM | 极致性能，多卡支持 |
| **个人开发者** | llama.cpp/Ollama | 开箱即用，量化灵活 |
| **边缘设备** | llama.cpp | CPU兼容，体积小 |
| **延迟敏感服务** | vLLM + 等待时间优先调度 | 低首token延迟 |
| **吞吐敏感服务** | TensorRT-LLM + In-flight batch | 高吞吐处理能力 |
| **多租户环境** | vLLM + Prefix Cache | 前缀复用优化 |

### 核心知识点回顾

1. **vLLM 架构精髓**：
   - PagedAttention 减少显存碎片
   - Continuous Batching 提升吞吐量
   - 调度策略影响用户体验

2. **TensorRT-LLM 优势**：
   - 图形优化极致性能
   - 多GPU 并行支持
   - 高级量化加速

3. **llama.cpp 适用性**：
   - 纯CPU实现兼容性好
   - GGUF格式简单实用
   - Ollama 一键运行

4. **部署关键指标**：
   - TTFT 影响用户体验
   - TPOT 影响生成速度
   - 吞吐量决定服务成本

5. **架构设计原则**：
   - 负载均衡减少等待
   - 缓存策略复用计算
   - 多机多卡水平扩展

---

## 附录

### 参考资源

1. **vLLM 官方文档**: https://docs.vllm.ai/
2. **TensorRT-LLM 文档**: https://docs.nvidia.com/deeplearning/tensorrt/
3. **llama.cpp 仓库**: https://github.com/ggerganov/llama.cpp
4. **Ollama 官方**: https://ollama.ai/

### 推荐阅读顺序

1. 先掌握 vLLM (最常用，部署简单)
2. 理解 TensorRT-LLM (大厂性能需求)
3. 了解 llama.cpp (个人/边缘设备)

---

*本文档为学习笔记，内容基于公开资料整理。*
