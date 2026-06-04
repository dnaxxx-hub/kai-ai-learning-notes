# LLM 推理加速 #7：PagedAttention & vLLM 架构深入

> 学习笔记 — 从操作系统分页思想到 LLM 推理引擎的工程革命
> 日期：2026-05-13 | 笔记编号：llm_infer_07
> 前置知识：Transformer Attention、KV Cache（llm_infer_01）、分布式推理（llm_infer_06）

---

## 0. 引言：KV Cache 管理的核心矛盾

回顾第1课 KV Cache 的显存计算：

```
单条 4K 序列 KV Cache ≈ 2 × (num_layers) × (seq_len) × (hidden_dim) × (dtype_bytes)
- Llama 3 8B (32层, 4096dim, FP16):  2 × 32 × 4096 × 4096 × 2 ≈ 2GB
- Llama 3 70B (80层, 8192dim, FP16): 2 × 80 × 8192 × 8192 × 2 ≈ 20GB
```

**传统 KV Cache 分配的核心问题：**

| 问题 | 描述 | 后果 |
|------|------|------|
| **预分配浪费** | 每个请求预先分配最大序列长度的连续显存 | 大部分请求实际序列短，显存利用率极低 |
| **内部碎片** | 分配粒度太大，无法细粒度共享 | GPU 显存被切分成一系列"预留"但未使用的小块 |
| **外部碎片** | 请求结束后释放空间，但新请求大小不匹配 | 显存总容量够但无法分配，OOM |
| **无法共享** | 不同请求间相同前缀（system prompt）的 KV Cache 无法复用 | 相同 prompt 反复计算 |

PagedAttention 的灵感来源：**操作系统的虚拟内存分页机制**。

---

## 1. PagedAttention 核心原理

### 1.1 基本思想

把 continuous KV cache 切分成固定大小的 **blocks**（页），通过 **block table**（页表）实现逻辑地址到物理地址的映射。

```
传统方式（连续显存）：
┌──────┬──────┬──────┬──────┬──────┬──────┐
│ ReqA │ ReqA │ ReqA │ ReqA │ free │ free │   ← 预分配后浪费
│ t0   │ t1   │ t2   │ t3   │      │      │
└──────┴──────┴──────┴──────┴──────┴──────┘

PagedAttention（不连续物理页）：
逻辑视图：  [t0][t1][t2][t3][t4][t5]...  ← 序列的逻辑连续

物理页表：  block_table = [3, 7, 1, 5, ...]  ← 物理地址可以不连续
物理视图：  ┌───┬───┬───┬───┬───┐
           │ 1 │ 2 │ 3 │ 4 │ 5 │ ... (GPU 全局显存按 block 管理)
           └───┴───┴───┴───┴───┘
            block 1 （给 C 用）← 物理地址完全灵活
            block 3 （给 A 用）
            block 7 （给 A 用）
            block 5 （给 B 用）
```

### 1.2 KV Block 数据结构

每个 block 存储固定数量 token（默认 **block_size=16**）的 Key 和 Value。

```
对于 L 层模型，每个 block 的显存消耗：
一个 block = block_size × (2 × num_layers × num_kv_heads × head_dim) × dtype_size

例：Llama 3 8B (32层, 8KV头的 GQA, FP16)
block_size=16 → 一个 block = 16 × (2×32×8×128) × 2 = 2MB/block

对于 4K 序列 → 4096/16 = 256 blocks → 512MB
```

### 1.3 Block Table（页表）

核心数据结构，类似 OS 页表：

```python
class BlockTable:
    """
    每个 sequence 维护一个 block table
    实现从 logical block 到 physical block 的映射
    """
    def __init__(self):
        self.blocks: List[PhysicalBlock] = []
        # 按需追加，类似 mmap 惰性分配

    def append(self, block: PhysicalBlock):
        """追加一个物理 block（sequence 增长时触发）"""
        self.blocks.append(block)

    def get_physical_block(self, logical_idx: int) -> int:
        """逻辑 block 索引 → 物理 block ID"""
        return self.blocks[logical_idx].block_id

    def get_kv_slice(self, logical_start: int, num_tokens: int):
        """获取连续逻辑地址对应的物理 KV 切片"""
        # 可能跨多个物理 block
        ...
```

### 1.4 Paged Attention Kernel

PagedAttention 的 CUDA kernel 与非分页 Attention 的关键区别：

```cuda
// 传统 Attention（连续内存）：直接指针偏移
// float* K = k_cache + head_idx * seq_len * head_size + token_idx * head_size;

// PagedAttention（分页内存）：需要 block table 间接寻址
// block_id = block_table[logical_block_idx];
// float* K_block = k_cache + block_id * block_size * head_size;
// 还需要在 block 内定位：token_idx_in_block = token_idx % BLOCK_SIZE;
```

vLLM 实现的 `paged_attention_kernel` 核心特征：

| 参数 | 含义 |
|------|------|
| `BLOCK_SIZE` | 编译时确定，通常 16 |
| `k_cache` shape | `[num_blocks, num_kv_heads, head_size/x, BLOCK_SIZE, x]` |
| `v_cache` shape | `[num_blocks, num_kv_heads, head_size, BLOCK_SIZE]` |
| `block_table` | 每个 sequence 的物理 block 映射表 |

**数据布局优化**：k_cache 使用特殊的交错布局（`head_size/x` 维度）以优化共享内存加载效率。

### 1.5 与 OS 虚拟内存的类比

| OS 虚拟内存 | PagedAttention |
|------------|---------------|
| 虚拟地址空间 | 序列的连续逻辑 token 空间 |
| 物理页框 | GPU 显存中的 KV block |
| 页表 | block table |
| 页错误 → 分配物理页 | 序列增长 → 分配新 block |
| 页共享（共享内存） | 相同 prefix 的 block 共享 |
| Copy-on-Write | 并行解码时的 fork 场景 |
| 交换到磁盘 | 将来可能支持的 KV Cache offload |

---

## 2. vLLM 调度策略

### 2.1 整体架构

```
Request Queue
     │
     ▼
  Scheduler  ◄──── Block Manager
     │                  │
     ▼                  ▼
  Worker (GPU) ──── PagedAttention Kernel
     │
     ▼
  Output Queue
```

核心组件：
- **Scheduler**：决定每个 iteration 运行哪些请求
- **Block Manager**：管理物理 block 的分配、释放、共享
- **Worker**：在 GPU 上执行模型 forward

### 2.2 Continuous Batching（连续批处理）

vLLM 的标志性调度策略，与 Orca 论文一脉相承。

**传统批处理（Static Batching）：**
```
Batch 1: [ReqA, ReqB, ReqC] → 全部结束后 → Batch 2: [ReqD, ReqE]
问题：慢请求拖累整批，气泡（bubble）大
```

**Continuous Batching vLLM 版本：**
```
Iteration 1: [ReqA(prefill), ReqB(prefill)]  → 两个新请求做 prefill
Iteration 2: [ReqA(decode), ReqB(decode), ReqC(prefill)] → 新请求 C 加入
Iteration 3: [ReqA(decode), ReqC(decode)] → B 结束，D 等待下轮
Iteration 4: [ReqA(decode), ReqC(decode), ReqD(prefill)]
...
```

**核心优势**：每个 iteration 都重新决定批次组成，请求可以随时加入/离开：
- 先到的请求先开始处理（无等待）
- 短请求先完成，长请求不阻塞别人
- 新请求零等待即可加入下一个 iteration

### 2.3 Prefill / Decode 两阶段

**Prefill（预填充）阶段：**
- 处理输入 prompt 的所有 token
- 计算第一个输出 token
- **计算密集型**（矩阵乘法为主）
- 对这个请求来说是第一次 forward

**Decode（解码）阶段：**
- 逐 token 生成
- 每次 forward 只处理 1 个新 token
- **访存密集型**（主要读 KV Cache，少量计算）
- 问题：decode 的 GPU 利用率天然低

**混合调度**：vLLM 可以在同一个 batch 里混入 prefill 和 decode 请求，通过**动态分割**解决序列长度差异：

```
混批策略：
Batch = [ReqA(decode, 1 个新 token), ReqB(prefill, 512 个 prompt token)]
         ↑ 短序列                    ↑ 长序列

问题：直接拼 batch 会做大量 padding，浪费算力
vLLM 解法：将 prefill 的序列分割成小块，和 decode 请求拼在一起
```

### 2.4 抢占策略（Preemption）

当显存不足时（新请求没有可用 block），vLLM 必须抢占已有请求。

**两种抢占模式：**

```
1. Swap（交换到 CPU）
   被抢占请求的 block → 拷贝到 CPU pinned memory
   之后恢复时 → 拷贝回 GPU
   代价：PCIe 传输，几十微秒级

2. Recompute（重计算）
   直接丢弃被抢占请求的 block
   之后恢复时 → 从原始 prompt 重新 prefill
   代价：重算更慢，但不需要 PCIe 带宽
   好处：如果 KV Cache 已量化，重算精度更高
```

**vLLM 的抢占选择策略：**
- **抢占最近到达的**请求（LIFO 策略），因为其已消耗的 compute 最少
- 配合 block table，可以精确地只释放被抢占请求的 block
- 恢复时按 block table 重新分配物理 block

### 2.5 Block Manager 核心算法

```
allocate(seq, num_required_blocks):
    if num_free_blocks < num_required_blocks:
        trigger_preemption()
    for i in 0..num_required_blocks:
        block = alloc_free_block()
        block_table.append(block)

free(seq):
    for block in block_table:
        # 如果 block 被多个序列共享（共享前缀），
        # 减少引用计数，ref_count=0 时才真正释放
        block.ref_count--
        if block.ref_count == 0:
            free_block(block)
```

---

## 3. 内存节省技术

### 3.1 共享前缀（Shared Prefix / Automatic Prefix Caching）

**场景**：多个请求共享相同的 system prompt 或对话历史前缀。

```
System Prompt: "You are a helpful assistant..."
             ┌──────────────────────────┐
ReqA:        │ Shared prefix (5 blocks) │ + ReqA specific
ReqB:        │ Shared prefix (5 blocks) │ + ReqB specific
             └──────────────────────────┘
               ↑ 相同物理 block，ref_count=2
```

**实现**：vLLM 通过 hash 匹配前缀 block。

```python
def match_prefix(prompt_tokens):
    """匹配已有缓存的前缀"""
    blocks = tokenize_to_blocks(prompt_tokens)
    cached_blocks = []
    for block in blocks:
        h = hash(block.tokens)
        if h in global_block_hash:
            block_id = global_block_hash[h]
            physical_block[block_id].ref_count += 1
            cached_blocks.append(block_id)
        else:
            break  # 一旦不匹配，后续 block 都不能共享
    return cached_blocks
```

**启用方式**：`vllm serve ... --enable-prefix-caching`

**效果**：
- 相同 system prompt 的请求完全共享 prefill 计算
- 多轮对话：历史 token 全部缓存，只需处理最新一轮
- 在聊天场景中可节省 **30-50%** 的 prefill 时间和显存

### 3.2 Copy-on-Write（写时复制）

**场景**：并行解码（比如 beam search、speculative decoding 的树状解码）。

```
初始状态：
ReqA block table: [Block3(共享), Block7(共享)]
                          ↑ 共享读取

当 ReqA 需要写入 Block7 生成新 token 时：
检查 Block7 的 ref_count
if ref_count > 1:
    new_block = alloc_free_block()   // 分配新 block
    copy(Block7 → new_block)         // 拷贝内容
    Block7.ref_count--               // 减少旧 block 引用
    block_table[7] = new_block       // 使用新 block
    new_block.ref_count = 1          // 新 block 只由当前序列独占
    // 此时其他序列仍然可以读取原始 Block7
```

**注意**：写时复制触发频率很低，因为大多数情况下每个序列写入的是自己的新 token（追加到新 block），只有对已有 block 的修改才会触发。

### 3.3 浪费率分析

**PagedAttention 的典型内存浪费来源：**

```
每个序列最后一个 block 可能用不满：
block_size = 16, 序列长度 = 1027
→ 需要 ceil(1027/16) = 65 个 block
→ 最后一个 block 只用了 3/16 = 18.75%
→ 内部碎片 = (16-3)/16 = 81.25% 在这个 block

整体浪费率 ≈ average(block_utilization_last_block)
```

**不同模型浪费率估算：**

| 场景 | 平均序列长度 | Block Size | 浪费率 |
|------|------------|-----------|--------|
| 短请求（问答） | 128-256 | 16 | ~6% |
| 中等（对话） | 1024-2048 | 16 | ~1% |
| 长文档 | 8192+ | 16 | <0.5% |
| **传统预分配** | 任意 | 无 | **~60-80%**（按最大长度分配） |

**对比传统方式：**
- 传统方式：为每个请求预分配 `max_seq_len` 的 continuous 显存 → 浪费率 = `(max_seq_len - actual_seq_len) / max_seq_len`
- 短请求（128 token）如果用 4096 max_len → 浪费率 96.9%
- **PagedAttention 把浪费从 O(max_seq_len) 降到 O(block_size/seq_len)**

### 3.4 显存利用率对比（4K max, 实际 512 平均）

```
传统方式：每请求 4K 预分配 = 2GB/请求
PagedAttention：实际 512/16 + 1 = 33 blocks = 66MB/请求

同 80GB GPU：
- 传统方式：最多 40 个并发请求（不考虑权重）
- PagedAttention：800+ 个并发请求（不含权重，最优情况）
```

---

## 4. 架构深度分析

### 4.1 vLLM 执行流程

```
1. 客户端发送请求 → HTTP Server (FastAPI / OpenAI API)
2. Request 进入 AsyncLLMEngine
3. Scheduler 决定当前 iteration 的调度计划：
   - 哪些请求加入 running
   - 哪些请求需要抢占（preempt）
   - 每个 running 请求需要多少新 block
4. Block Manager 分配/释放物理 block
5. Worker (GPU) 执行模型 forward：
   - PagedAttention kernel 读取分页 KV Cache
   - 计算 attention 输出
   - 新生成的 token 写入新 block
6. 生成结果通过 Detokenizer 转成文本 → HTTP Response
7. 循环回到步骤 3
```

### 4.2 Block Manager 的两层架构

```
Block Manager
  ├─ Physical Block Manager
  │    负责：GPU 显存的实际分配/释放
  │    数据结构：free_block_list, block_id → ref_count
  │
  └─ Logical Block Manager (per request)
       负责：序列的逻辑 block 映射
       数据结构：block_table {logical_idx → physical_block_id}
```

### 4.3 vLLM 1.x（新架构）的变化

vLLM 0.x（原始架构）：
- 基于 Ray 的多 worker
- Scheduler/Executor/Worker 分离
- 优秀的学术设计但有一定 overhead

vLLM 1.x（新架构）：
- 简化的单进程架构（移除 Ray 依赖选项）
- 更高效的 block manager（减少锁竞争）
- 更好的 prefix caching 支持
- **Hybrid KV Cache Manager**：支持更细粒度的缓存策略

---

## 5. 对比：vLLM vs HuggingFace Transformers vs TensorRT-LLM

### 5.1 架构对比

| 特征 | vLLM | HuggingFace Transformers | TensorRT-LLM |
|------|------|--------------------------|-------------|
| **KV Cache 管理** | PagedAttention（分页） | Continuous（连续预分配） | 连续 + 部分分页（v0.9+） |
| **批处理** | 连续批处理（每 iteration 重调度） | 静态批处理（需手动实现） | 连续批处理 |
| **CUDA Kernel** | 手写 fused kernel | PyTorch eager（未融合） | 高度优化的 TensorRT engine |
| **内存节省** | 近零浪费（分页+共享） | 高浪费（预分配） | 中等（类似预分配） |
| **模型支持** | 大量 HF 模型（社区驱动） | 绝大部分模型 | 有限（NVIDIA 官方支持） |
| **Paged prefill** | 支持 | 否 | 有限支持 |
| **Prefix Caching** | 原生支持（APC） | 不支持 | 需手动实现 |
| **量化** | AWQ/GPTQ/SqueezeLLM/FP8 | 依赖 bitsandbytes | FP8/INT4/INT8（深度集成） |
| **LoRA 适配** | 原生支持（S-LoRA） | 需要 peft 库 | 有限支持 |
| **分布式** | TP/PP/DP（Ray 或原生） | DeepSpeed 或自行分片 | TP/PP（深度优化） |

### 5.2 吞吐量对比（论文数据）

来自 vLLM 论文（SOSP 2023）：

| 系统 | Llama 7B (A100-80G) | Llama 13B | Llama 70B |
|------|---------------------|-----------|-----------|
| HuggingFace Transformers | 1.0× (baseline) | 1.0× | 1.0× |
| FasterTransformer (TRT-LLM 前身) | 1.8× | 1.9× | 2.1× |
| **vLLM** | **3.0×** | **3.3×** | **3.7×** |

**关键发现**：
- 越大的模型，vLLM 的 PagedAttention 优势越明显（KV Cache 占比越高）
- 长序列场景优势更大（共享前缀 + 分页减少碎片）
- 比 HuggingFace 快 2-4×，比 TRT-LLM 也明显快

### 5.3 源码对比（工程复杂度）

| 方面 | vLLM | HuggingFace | TensorRT-LLM |
|------|------|-------------|-------------|
| 代码量 | ~500K lines | ~1M+ lines | ~300K lines (但依赖复杂) |
| 学习曲线 | 中等（有良好架构文档） | 平缓（API 简单） | 陡峭（TensorRT 编译） |
| 调试难度 | 中等 | 简单 | 困难（编译后黑盒） |
| 灵活性 | 高 | 极高 | 低（需重新编译） |

### 5.4 实际部署选择

| 场景 | 推荐 |
|------|------|
| 研究/原型验证 | HuggingFace（简单） |
| 生产级 LLM 服务 | **vLLM**（社区最大，性能最佳） |
| 极致优化（特定硬件） | TensorRT-LLM（NVIDIA H100/B200） |
| 边缘设备部署 | TensorRT-LLM 或 ONNX Runtime |
| MoE 模型 | vLLM 或 TensorRT-LLM 均有优化 |

**实际经验**：大多数场景选 vLLM 就对了。它的社区活跃度、模型兼容性、和性能的平衡是最好的。

---

## 6. 与之前课程的配合

### 6.1 PagedAttention + 量化（llm_infer_02）

```
量化降低的是 模型权重 的显存占用。
PagedAttention 优化的是 KV Cache 的显存管理。

两者是正交的，可以叠加：
- 权重量化（FP16→INT4）：模型权重显存减少 4×
- KV Cache 量化（FP16→INT8/INT4）：每个 KV block 大小减半/减到 1/4
- PagedAttention 的分页管理：消除碎片浪费

叠加效果（7B 模型，4K 上下文）：
  baseline:        ~2GB KV + ~14GB 权重 = 16GB → 需要 24GB 显卡  
  +INT4权重:       ~2GB KV + ~4.5GB 权重 = 6.5GB ✓
  +INT8 KV Cache:  1GB KV + 4.5GB 权重 = 5.5GB ✓
  +PagedAttention: 进一步减少碎片，可以批更多请求
```

### 6.2 PagedAttention + Efficient Attention（llm_infer_05）

FlashAttention/FlashDecoding 是 attention 计算的算法优化（减少显存读写）。
PagedAttention 是 KV Cache 存储的架构优化（分页管理）。

可以在同一个系统中同时使用：
- vLLM 的 FlashInfer backend = PagedAttention (存储) + FlashDecoding (计算)
- TensorRT-LLM 的 MLA/inflight batch = 类似思路

### 6.3 PagedAttention + 分布式（llm_infer_06）

```
TP (Tensor Parallelism):
  PagedAttention + TP = 每个 GPU 只存储部分 head 的 KV block
  每个 GPU 有独立的 block table，大小减小为 1/TP_size

PP (Pipeline Parallelism):
  各层的 KV block 分布在不同的 GPU 上
  vLLM 支持 PP (通过 Ray 或直接 worker 通信)

Disaggregated Prefill/Decode:
  最新趋势：prefill GPU 和 decode GPU 分离
  KV block 需要在 GPU 间传输 → 分页格式非常适合做块级传输
  vLLM 已经支持 MoonCake 等 disaggregated 架构
```

---

## 7. 动手实验

### 实验 1：本地部署 vLLM 观察 PagedAttention 效果

```bash
# 1. 安装 vLLM
pip install vllm

# 2. 启动服务（打开 vLLM 的统计日志）
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching \
  --max-num-seqs 256

# 3. 观察显存使用（看 block manager 统计）
# 发送多个共享相同 system prompt 的请求
# 观察 KV block ref_count > 1

# 4. 对比关掉 prefix caching 的显存差异
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --no-enable-prefix-caching
```

### 实验 2：分析 block 利用率

写一个简单的分析脚本，模拟 PagedAttention 的内存分配：

```python
def simulate_paged_memory(
    num_requests: int,
    seq_lengths: List[int],
    block_size: int = 16,
    max_seq_len: int = 4096,
    kv_block_size_bytes: int = 2 * 1024 * 1024  # 2MB per block for 7B
):
    # 传统方式
    traditional_mem = num_requests * max_seq_len / block_size * kv_block_size_bytes
    traditional_waste = sum(
        (max_seq_len - seq_len) / max_seq_len 
        for seq_len in seq_lengths
    ) / num_requests

    # PagedAttention
    actual_blocks = sum(ceil(s / block_size) for s in seq_lengths)
    total_blocks = ceil(max_seq_len / block_size) * num_requests
    paged_mem = actual_blocks * kv_block_size_bytes
    paged_waste = sum(
        (block_size - (s % block_size or block_size)) / block_size
        for s in seq_lengths
    ) / len(seq_lengths)

    print(f"传统方式: {traditional_mem/1e9:.2f} GB, 浪费率 {traditional_waste:.1%}")
    print(f"PagedAttention: {paged_mem/1e9:.2f} GB, 浪费率 {paged_waste:.1%}")
    print(f"节省: {(traditional_mem - paged_mem)/1e9:.2f} GB ({(1-paged_mem/traditional_mem)*100:.0f}%)")
```

---

## 8. 总结

### 在实际部署中的意义

PagedAttention 和 vLLM 之所以成为 LLM 推理的事实标准，不是因为它发明了什么全新理论，而是 **把操作系统领域成熟的分页管理思想首次系统性地应用到 LLM 推理场景**。这个思想上的"降维打击"带来了几个实际收益：

1. **Batch Size 提升 2-4×**：同样的 GPU，能同时服务的请求数翻倍，直接降低部署成本
2. **显存碎片趋近于零**：不再需要猜测请求长度，显存按需分配，OOM 概率大幅降低
3. **共享前缀原生支持**：system prompt 和对话历史可以自然复用，不仅省显存还省计算
4. **调度灵活性极强**：连续批处理 + 分页管理，使得请求可以随时加入/退出，用户体验提升

### 与之前知识的配合

| 技术 | 解决什么问题 | 与 PagedAttention 的叠加效果 |
|------|------------|---------------------------|
| **KV Cache 量化** (INT8/INT4) | 每个 block 的大小减半/减到 1/4 | 同显存下并发度再翻 2-4× |
| **FlashAttention** | attention 计算更快 | 计算加速 + 存储优化 = 1+1>2 |
| **分布式推理** (TP/PP) | 单卡放不下大模型 | PagedAttention 的 block 天然适合在 GPU 间传输 |
| **权重量化** (AWQ/FP8) | 模型权重显存减少 | 量化后的模型 → 更多显存留给 KV Cache → 更大 batch |

**一句话总结**：PagedAttention 是 LLM 推理工程中最关键的"思路类"创新 — 没有引入新的数学，却通过系统架构设计解决了服务化部署中最核心的内存管理瓶颈。

---

## 9. 下一课建议

学完 PagedAttention & vLLM 架构后，本专题（LLM 推理优化深度）建议按以下顺序继续：

| 序号 | 主题 | 理由 |
|------|------|------|
| 8 | **Speculative Decoding**（推测性解码） | 与 PagedAttention 互补，解决 decode 阶段 GPU 利用率低的问题 |
| 9 | **Prefix Caching & Hybrid Cache Manager** | vLLM 的最新发展，从 block 级缓存到更细粒度的缓存策略 |
| 10 | **KV Cache量化实战** | 第2课量化知识的深化，专门聚焦 KV Cache 量化技术 |

**推荐下一课**：Speculative Decoding（推测性解码）— 用一个小 draft model 以微小的额外开销，实现 2-3× 的解码加速，且不降低生成质量。

---

## 参考资料

- [vLLM: Efficient Memory Management for Large Language Model Serving with PagedAttention](https://arxiv.org/abs/2309.06180) — Kwon et al., SOSP 2023
- [vLLM GitHub](https://github.com/vllm-project/vllm)
- [vLLM Architecture Docs](https://docs.vllm.ai/en/latest/design/arch_overview/)
- [Paged Attention Design Docs](https://docs.vllm.ai/en/latest/design/paged_attention/)
- [Automatic Prefix Caching](https://docs.vllm.ai/en/latest/design/prefix_caching/)
- [FlashAttention: Fast and Memory-Efficient Exact Attention](https://arxiv.org/abs/2205.14135)
- [Orca: A Distributed Serving System for Transformer-Based Generative Models](https://www.usenix.org/conference/osdi22/presentation/yu)
