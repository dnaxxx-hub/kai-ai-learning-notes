# LLM 推理优化 · 第3弹：vLLM + PagedAttention 深度

## 1. PagedAttention 分页

### 问题的起点
- KV Cache 是**动态增长**的
- 传统方案：**预分配最大长度** → 内部碎片严重
  ```
  ┌─── request A (实际生成了50 tokens, 预分配4096) ───┐
  │ [■■■...■■■][□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□] │
  │  已用 50             4046 未使用（浪费）             │
  └─────────────────────────────────────────────────────┘
  ```
- 或者动态分配，但**内存碎片**和**管理开销**很大

### PagedAttention 的核心
**借鉴操作系统虚拟内存的分页思想**：
- KV Cache 不再连续存储
- 切成固定大小的 **KV Block**（如 16 个 token/block）
- 使用 **Logical → Physical Block Mapping** 管理

### 映射机制
```
Logical (请求视角):
Request A: Token 1-16 | Token 17-32 | Token 33-48 | ...（连续的）
           Block 0       Block 1      Block 2

Physical (GPU内存视角):
Block 0 → Physical Page 5
Block 1 → Physical Page 12
Block 2 → Physical Page 3
...

Block Table:
┌─────────┬─────────────┬──────────┐
│  L.Page │  P.Page      │  Num Tok │
├─────────┼─────────────┼──────────┤
│  0      │  5           │ 16       │
│  1      │  12          │ 16       │
│  2      │  3           │ 8(partial)│
└─────────┴─────────────┴──────────┘
```

### Block Attention 计算
```
Q[i] ← 当前 query token

对每个 logical block:
  1. 从 Block Table 查到 physical block 地址
  2. 加载整个 physical block 的 K/V 到 SRAM
  3. 只对该 block 内有效的 token 做 attention
  4. 累加结果
```

---

## 2. 内部碎片 vs 外部碎片

### 内部碎片（Internal Fragmentation）
- **定义**: Block 内未使用的 token 空间
- **来源**: 最后一个 block 不满（如 block_size=16，序列长度=130 → 最后一个block用了2个，浪费14个）
- **计算**:
  ```
  内部碎片率 ≈ (block_size-1) / (2 × average_seq_len)
  对于 block_size=16, avg_seq=256:
  碎片率 ≈ 15 / 512 ≈ 3%
  对于短序列 (avg=32):
  碎片率 ≈ 15 / 64 ≈ 23% ← 短序列碎片严重
  ```

### 外部碎片（External Fragmentation）
- **定义**: 物理块之间无法利用的空隙
- **PagedAttention**: **外部碎片消除**（物理页可以放在任意位置）
- 对比旧方案中连续分配导致的「内存漏洞」

### 碎片对比
| 方案 | 内部碎片 | 外部碎片 | 合计 |
|------|---------|---------|------|
| 连续预分配 | 极大 (max-min) | 0 | 极大 |
| 连续动态分配 | 0 | 大（碎片化） | 大 |
| PagedAttention | 小(<block_size per seq) | **0** | 最小 |

---

## 3. Block 大小对吞吐的影响

### 关键因素
Block 大小是 PagedAttention 最关键的参数（通常 16 或 32）：

| Block 大小 | 优点 | 缺点 |
|-----------|------|------|
| **16** (vLLM默认) | 内部碎片少 | Block Table 大, 管理开销大 |
| **32** | 管理更少 | 短序列浪费更多 |
| **64** | 极端少的管理 | 短序列严重浪费 |
| **8** | 碎片极少 | 表太大, 每次要访问更多block |
| **1** | 没碎片 | 完全无法利用局部性, 极慢 |

### 实验数据（近似）

| Block大小 | 内存效率 | Attention 速度 | 适用场景 |
|-----------|---------|---------------|---------|
| 8 | ~95% | 较慢 (多次IO) | 延迟敏感, 短sequence |
| 16 | ~92% | 中 | 推荐通用 |
| 32 | ~85% | 快 | 吞吐优先, 长sequence |
| 64 | ~75% | 很快 | 超长sequence, 批处理 |

### 自适应 Block 大小
vLLM 后续版本支持根据序列长度自动选择 block 大小，
或用**可变大小块**（大块在前，小块在后）。

---

## 4. vLLM 调度系统

### 总体调度流程图
```
请求到达 → 排队（Scheduler）
              │
    ┌─────────┴──────────┐
    │   Prefill Phase     │  ← 预填充（并行处理 prompt）
    │   (整个 prompt 做前向)│
    └─────────┬──────────┘
              │  ← 分配 KV Block
    ┌─────────┴──────────┐
    │   Decode Phase      │  ← 逐个 token 生成
    │   (逐 token 推理)   │
    └─────────┬──────────┘
              │
  ┌───────────┴───────────┐
  │  是否可以继续?          │
  │  - 有足够的 GPU 内存?   │
  │  - 未达到 max_tokens?  │
  └───────────┬───────────┘
              │
      ┌───────┴───────┐
      │   是: 继续      │
      │   否: 需要处理   │
      └───────┬───────┘
              │
    ┌─────────┴──────────┐
    │  抢占 (Preemption)  │
    │  或 重新调度 (Reschedule)│
    └─────────────────────┘
```

### 请求排队
- **FIFO**: 先到先服务
- **优先级队列**: 高优先级请求插队
- **等待队列** vs **运行队列**

### Block 分配策略

**① 预填充分配**
```
prompt = "今天天气怎么样？" (10 tokens)
→ 需要 N = ceil(10 / 16) = 1 个 block
→ 先只占1个block，后续按需扩张
```

**② 按需分配**
```
每生成一个 token：
  1. 当前 block 是否满了？
  2. 满了 → 分配新 block（从空闲列表中取一个物理页）
  3. 更新 Block Table
```

**③ 空闲列表管理**
```
Free Block Pool: [Page 0, Page 3, Page 7, Page 15, ...]
                ↑ 按需取出
```

### 抢占（Preemption）

当 GPU 内存不足时，vLLM 必须踢掉部分请求：

**① Swap Out（最优）**
```
1. 选中要踢掉的请求（通常是序列最长的）
2. 把它所有的 KV Block 拷贝到 CPU RAM
3. 释放 GPU Block
4. 给新请求分配 Block
```
- **优点**: 请求可以恢复
- **缺点**: CPU↔GPU 传输慢（~10GB/s PCIe）

**② Recomputation（次优）**
```
1. 直接释放选中的请求的 GPU Block
2. 重新调度时需要重新计算 KV Cache
```
- **优点**: 无传输开销
- **缺点**: 浪费之前计算

**③ 选择策略**
```
通常选择策略（Greedy）:
- 选择最大序列（占用最多block，释放最多）
- 选择最早请求（后续可以重算）
- 避免频繁抢占同一请求
```

### 重新调度
```
抢占完成后:
1. 被踢请求放入「交换队列」（swap out 的等待恢复）
2. 新请求开始接受服务
3. 当有足够内存 + 被踢请求恢复时:
   - 重新加载 CPU (swap in) 或 重算
   - 恢复到 decode 阶段继续生成
```

---

## 5. vLLM vs TensorRT-LLM vs TGI

| 特性 | vLLM | TensorRT-LLM | Text Generation Inference (TGI) |
|------|------|-------------|-------------------------------|
| **公司** | UC Berkeley/SJTU | NVIDIA | Hugging Face |
| **内存管理** | PagedAttention (细粒度) | 预分配 + 优化 | 预分配 + 连续批处理 |
| **批处理** | Continuous Batching | In-flight Batching | Continuous Batching |
| **量化** | AWQ/GPTQ/SqueezeLLM | NVIDIA 原生量化 | GPTQ/AWQ/EETQ |
| **性能** | ⭐⭐⭐ (通用) | ⭐⭐⭐⭐ (NV卡) | ⭐⭐ (通用) |
| **易用性** | ⭐⭐⭐⭐⭐ (API友好) | ⭐⭐ (复杂) | ⭐⭐⭐⭐ (简单) |
| **模型支持** | 广泛 | 有限（NV优化） | 较广 |
| **SPEC DECODE** | ✅ (v0.6+) | ✅ | ✅ |
| **Prefix Cache** | ✅ (自动) | ✅ | ✅ |
| **社区活跃度** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

### 详细对比

**vLLM 优势**
- PagedAttention = 更高效的内存利用（内存节省 60-80% vs 传统方案）
- open-source, 社区最活跃
- OpenAI API 兼容性最好
- 快速支持新模型

**TensorRT-LLM 优势**
- NVIDIA 亲儿子，H100 优化最好
- **FP8 推理**（in-flight quantization）
- **In-flight Batching** 更动态
- 多 GPU 分散且性能好

**TGI 优势**
- HuggingFace 生态，简单易用
- 内置安全校验
- API Server 一体化

### 吞吐量对比（近似）

| 模型 | 配置 | vLLM (tok/s) | TRT-LLM (tok/s) | TGI (tok/s) |
|------|------|-------------|-----------------|-------------|
| LLaMA-7B | A100-80G | ~3000 | ~3500 | ~2000 |
| LLaMA-13B | A100-80G | ~1800 | ~2200 | ~1200 |
| LLaMA-70B | 2×A100-80G | ~400 | ~500 | ~250 |

> 数据为大致参考，具体取决于 batch size、seq length、量化方式等

### 选型建议

| 场景 | 推荐 |
|------|------|
| 个人/小团队 API 部署 | **vLLM**（易用, 活跃） |
| NVIDIA GPU 企业部署 | **TensorRT-LLM**（性能） |
| HuggingFace 生态 | **TGI**（集成） |
| 想快速上手 | **vLLM** |

---

## 6. vLLM 核心架构

### 组件总览
```
vLLM
├─ Scheduler (调度)
│   ├─ SchedulingPolicy
│   ├─ BlockManager
│   └─ PreemptionHandler
├─ BlockManager (KV管理)
│   ├─ BlockTable
│   ├─ PhysicalBlockAllocator
│   └─ SwapManager (CPU↔GPU)
├─ Worker (GPU执行)
│   ├─ ModelRunner
│   ├─ AttentionBackend
│   └─ Sampler
├─ LLM Engine (上层API)
└─ AsyncLLM Engine (流式服务)
```

### 关键数据结构
```python
# Block Table (每请求)
{
  "request_id": "abc",
  "block_table": [5, 12, 3, 8],   # logical→physical映射
  "num_blocks": 4,
  "num_tokens": 54                # 实际token数
}

# Block 分配
{
  "physical_blocks": [
    {"id": 0, "ref_count": 2, "request_ids": ["abc", "def"]},
    {"id": 1, "ref_count": 1, "request_ids": ["abc"]},
    ...
  ],
  "free_blocks": [23, 45, 67, ...]
}
```

### 连续批处理原理
```
时间 →
Request A: |P|D|D|D|D|...|D|
Request B: |   |P|D|D|D|D|...|D|
Request C: |       |P|D|D|D|...|D|

P = Prefill (prompt 全做前向)
D = Decode (逐 token 生成)

Continuous Batching:
在A的某个decode step时, B的prefill可以同时进行
→ GPU 利用率更高
```
---

## 参考
- vLLM: Efficient Memory Management for Large Language Model Serving with PagedAttention (Kwon et al., 2023)
- TensorRT-LLM: https://github.com/NVIDIA/TensorRT-LLM
- TGI: https://github.com/huggingface/text-generation-inference
