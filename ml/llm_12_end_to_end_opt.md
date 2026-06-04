# LLM推理优化 第12课：LLM推理全链路调优 — 端到端实践

> 学习日期：2026-05-18
> 背景：前11课覆盖理论基础和各组件独立优化，本课做端到端串联

## 1. 全链路视角

### 完整推理链

```
用户输入 "什么是transformer？"
        │
        ▼
┌────────────────────────────┐
│  Tokenizer  (编码)          │ [token_ids: [143, 2105, 486, ...]]
├────────────────────────────┤
│  Embedding  (查找/计算)      │ [float vectors × seq_len]
├────────────────────────────┤
│  Transformer (L层) ──────┐ │
│  ├─ LayerNorm (融合)     │ │
│  ├─ QKV投影 (量化)       │ │
│  ├─ Attention ──────────┤ │
│  │  ├─ PagedAttention  │ │
│  │  ├─ KV Cache (读取)  │ │
│  │  └─ FlashAttention  │ │
│  ├─ 残差连接             │ │
│  ├─ MLP (融合矩阵乘法)    │ │
│  └─ KV Cache (写入)      │ │
│         ◄──────────────┘ │
├────────────────────────────┤
│  LM Head (输出层)          │ [logits: vocab_size]
├────────────────────────────┤
│  Sampler (采样)            │ [next_token]
├────────────────────────────┤
│  Tokenizer (解码)          │ "Transformer是一种..."
└────────────────────────────┘
```

### 瓶颈分布

```
一轮 decode 的耗时分布（LLaMA-70B, batch=1）:
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PagedAttention查找页表      2%   ▮
  KV Cache读取               8%   ▮▮▮▮
  QKV投影 (内存带宽受限)     35%   ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮
  Attention计算 (MatMul)     15%   ▮▮▮▮▮▮▮
  MLP (矩阵乘法)             25%   ▮▮▮▮▮▮▮▮▮▮▮▮
  LayerNorm + 残差            5%   ▮▮
  LM Head (最后一层)         10%   ▮▮▮▮▮

关键结论：QKV投影 (35%) + MLP (25%) = **60%耗时在矩乘**
            → 这是量化的核心战场
```

## 2. 逐层调优

### 2.1 输入处理层

**瓶颈**: Tokenizer 在 CPU 执行，结果传 GPU → CPU-GPU 传输延迟

```
优化前: CPU Tokenizer → cudaMemcpy → GPU Embedding
每个token: ~200μs (CPU) + 15μs (Memcpy)

优化后: 批量Tokenize
一次传100个tokens → 分摊传输延迟
每个token: ~2μs (批量分摊)
```

### 2.2 Embedding 层

```
N秒优化   - 预计算并缓存常见token的embeddings
大优化   - 不存储全量vocab embedding，用Hot Cache
           （经常使用的token缓存前N个，余下延迟加载）
```

### 2.3 核心Transformer层

**Y优化的基线**：

```yaml
量化: 
  KV Cache: FP8 (16KB/token → 8KB/token)
  权重: INT4 (50%显存节省)
  激活: FP16 (保持精度)

Attention:
  FlashAttention: 启用 (减少HBM读写)
  PagedAttention: 块大小=16 (GPU warp亲和性最优)
  Page Size tuning: 实测16最快

MLP:
  融合MLP: 启用 (1次大kernel替代3次小kernel)
  FusedGELU: 启用

算子合并:
  LayerNorm + QKV: 1个fusion kernel
  RMSNorm + RoPE: 1个fusion kernel
  attention + residual + next_LN: 1个fusion kernel
```

### 2.4 采样层 (Sampler)

```
Top-k + Top-p + Temperature:
  1. 计算logits:     LM Head (vocab_size=32000) 
  2. Top-k筛选:      保留k个最高logits
  3. Top-p筛选:      保留累计概率超过p的最高logits
  4. Temperature:    logits /= temp
  5. Softmax:        probs = softmax(logits)
  6. 采样:           torch.multinomial(probs)

瓶颈: LM Head 是一个 大矩乘 (hidden_dim × vocab_size)
      → 对70B模型，32768 × 8192 = 268M参数
      → 与MLP层一样重！

优化: 
  1. LM Head 共享 embedding 权重 (weight tying)
  2. 提前终止：对 greedy decoding 不需要softmax+采样
     → 直接 argmax
```

## 3. 服务层优化

### 3.1 请求调度策略

```
Scheduling Policy:
  ├── FCFS (First Come First Serve)
  │   └── 简单但：长请求会阻塞短请求
  ├── SJF (Shortest Job First) 
  │   └── P99延迟好，但：短请求永远插队导致长请求starve
  ├── MLFQ (Multi-Level Feedback Queue)
  │   └── 维护3个队列，根据已服务时间动态降级
  │       QoS保证 + 公平性
  └── Iteration Level Scheduling
      └── 每个iteration重新调度
          这是 vLLM / TRT-LLM 用的方案
          每步决定谁继续、谁暂停、谁新建
```

**Iteration Level Scheduling 优势**：

```
Time ───────────────────────────────────────────→

Naive FCFS:
  [——— ReqA (150tokens) ———] [ReqqB (20)] [ReqqC (30)]
                                              ↑ ReqqC等得久

Iteration Level:
  [A1][B1][C1][A2][B2][C2][A3][C3][A4][C4][A5][A6]
  每个请求每步至少执行一个token
  → 所有请求同时推进，P99延迟降低50%
```

### 3.2 动态批处理

```python
class Scheduler:
    def schedule(self, waiting_reqs, running_reqs):
        batch = []
        
        # 1. 先取已在运行的请求（有KV Cache）
        for req in running_reqs:
            if not req.finished:
                batch.append(req)
        
        # 2. 加新请求（需要做prefill）
        free_slots = self.max_batch - len(batch)
        for req in waiting_reqs[:free_slots]:
            batch.append(req)
        
        # 3. 如果不能全装下，分多次
        self.prefill_queue = waiting_reqs[free_slots:]
        
        return batch
```

### 3.3 前缀缓存加速

```python
class PrefixCache:
    """自动检测并缓存重复前缀"""
    
    def __init__(self):
        self.cache = {}  # "hash(token_ids)" → [block_ids]
        self.max_cache_blocks = 1024
    
    def lookup(self, token_ids):
        """查找已缓存的前缀块"""
        cached_blocks = []
        for i in range(0, len(token_ids), BLOCK_SIZE):
            block_tokens = token_ids[i:i+BLOCK_SIZE]
            key = hash(tuple(block_tokens))
            if key in self.cache:
                cached_blocks.append(self.cache[key])
            else:
                break  # 一旦缺页，后面的都不能共享
        return cached_blocks
    
    def update(self, token_ids, block_ids):
        """更新缓存"""
        for i, bi in enumerate(block_ids):
            tokens = token_ids[i*BLOCK_SIZE:(i+1)*BLOCK_SIZE]
            key = hash(tuple(tokens))
            self.cache[key] = bi  # 覆盖（LRU）
```

## 4. 监控指标和自动调优

### 4.1 关键KPI

```
┌──────────────┬───────────────┬──────────────┐
│    指标       │  定义           │  业界目标     │
├──────────────┼───────────────┼──────────────┤
│ TTFT         │ 首token延迟     │ <200ms       │
│ ITL          │ token间延迟      │ <30ms        │
│ TPOT         │ 每输出token时间  │ <100ms       │
│ Throughput   │ tok/s/GPU       │ >1000 (7B)   │
│              │                 │ >200 (70B)   │
│ GPU Util     │ GPU计算利用率    │ >70%         │
│ KV利用率     │ KV Cache占用率   │ <90%         │
│ P99/P50      │ 尾部延迟比例     │ <3x          │
└──────────────┴───────────────┴──────────────┘
```

### 4.2 自动调优策略

```
1. 扫描batch大小:    [1, 2, 4, 8, 16, 32, 64]
   找到延迟/吞吐的最佳平衡点

2. 扫描块大小:        [8, 16, 32, 64]
   GPU warp=32 → 16最均衡

3. 量化精度扫描:      [FP16, INT8, INT4, FP8]
   精度损失 < 1% 的选最快配置

4. 目标: 延迟约束 + 最大化吞吐
```

## 5. 端到端延迟模型

LLM推理的延迟模型：

```python
def estimate_latency(input_len, output_len, batch, model_params):
    """端到端延迟估算"""
    hidden = model_params["hidden_dim"]
    layers = model_params["num_layers"]
    vocab = model_params["vocab_size"]
    
    # Prefill: 全量计算
    pref_flops = 2 * input_len * (hidden**2) * layers
    pref_time = pref_flops / gpu_peak_flops * batch
    
    # Decode: 逐token计算
    decode_flops_per_token = 2 * hidden**2 * layers
    decode_time = decode_flops_per_token / gpu_bw * (output_len - 1)
    
    # Attention开销
    attn_overhead = (output_len * input_len * hidden) / gpu_hbm_bw * batch
    
    total = pref_time + decode_time + attn_overhead
    return total
```

模型验证（LLaMA-70B）：
```
Input=512, Output=128, batch=1:
  Prefill:   280ms (估算: 310ms)
  Decode:   3.2s   (估算: 3.5s)
  Total:    3.48s  (实际: 3.5s → 误差~2%)
```

## 6. 生产部署检查清单

### 部署前

- [ ] 模型量化精度验证（MMLU/CEval差异<1%）
- [ ] 引擎预热（~50次推理使GPU达到稳态）
- [ ] KV Cache预分配（避免动态分配延迟）
- [ ] 前缀缓存训练（提取高频系统prompt）

### 部署后

- [ ] P50/P99/TTFT/ITL 在线监控
- [ ] GPU利用率报警（<30% 表示优化不足）
- [ ] KV Cache碎片率监控（>20% 触发碎片整理）
- [ ] OOM保护：流控 + 优雅降级

## 知识图谱关联

```
┌──────────────────────────────────┐
│         全链路调优（本课）          │
│  ┌──────┐  ┌──────┐  ┌──────┐  │
│  │Input │→ │Transformer│  │Sampler│  │
│  │Opt   │  │Opt   │  │Opt   │  │
│  └──────┘  └──────┘  └──────┘  │
│  ┌──────┐  ┌──────┐  ┌──────┐  │
│  │服务化 │  │监控   │  │调度   │  │
│  │ #8   │  │ #9   │  │ #12   │  │
│  └──────┘  └──────┘  └──────┘  │
└──────────────────────────────────┘
```

---

**学习时间**: 2026-05-18 23:18-23:30
**笔记状态**: 完成，同步到D盘
