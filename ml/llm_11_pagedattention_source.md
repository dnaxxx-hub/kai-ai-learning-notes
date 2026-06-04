# LLM推理优化 第11课：PagedAttention 深度源码解析

> 学习日期：2026-05-18
> 背景：在了解 vLLM/TRT-LLM 整体架构后，深入最核心的 PagedAttention 实现机制

## 1. 从虚拟内存到 PagedAttention

### 核心洞察

Attention的计算模式：
```
Attention(Q, K, V) = softmax(QK^T/√d) × V

关键:
- Q: (batch, head, seq_len, d)
- K: (batch, head, seq_len, d)
- V: (batch, head, seq_len, d)
- 输出: (batch, head, seq_len, d)
```

**问题1：KV Cache 显存碎片化**

传统实现中，每个请求预分配最大序列长度的连续显存：
```
传统分配（假设max_seq=2048）:
┌──────────────────────────────────────────────┐
│  ReqA (已用512/2048)       ░░░░ 浪费 75%      │
├──────────────────────────────────────────────┤
│  ReqB (已用128/2048)       ░░░░░░ 浪费 93%    │
├──────────────────────────────────────────────┤
│  ReqC (已用1024/2048)      ░░ 浪费 50%        │
├──────────────────────────────────────────────┤
│  内部碎片合计 ≈ 72% 的KV Cache被浪费          │
└──────────────────────────────────────────────┘
```

**PagedAttention 把空间当作操作系统虚拟内存：**
```
分页 (Page = 16 tokens):
┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐
│A1│A2│A3│A4│B1│B2│C1│C2│C3│C4│C5│C6│A5│A6│A7│C7│
├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
│   ReqA (7页，浪费1/16=6%)                     │
│   ReqB (2页，浪费0%)                          │
│   ReqC (7页，浪费1/16=6%)                     │
└──────────────────────────────────────────────┘
内存利用率从~30%提升到~94%
```

## 2. 核心数据结构

### 2.1 BlockTable（页表）

相当于操作系统的页表：

```python
# 关键数据结构 (vLLM源码简化)

class BlockTable:
    """
    将逻辑块 (logical blocks) 映射到物理块 (physical blocks)
    
    逻辑视角:
    ReqA.tokens = [t0, t1, ..., t15, t16, t17] (18个token)
    逻辑页: [Block0(t0-t15), Block1(t16-t17)]
    
    物理视角:
    BlockTable = [PhysicalBlock_42, PhysicalBlock_78]
    """
    
    def __init__(self):
        self.blocks: List[PhysicalBlock] = []
    
    def append_token(self, token, kv_cache):
        """添加新token"""
        if self._current_block_full():
            # 申请新物理块
            new_block = kv_cache.alloc()
            self.blocks.append(new_block)
        # 写入当前块
        self._write_token(token)
```

### 2.2 PhysicalBlock（物理块）

```c
// 一个物理块 = 16个token的K和V
// shape: (16, 2, num_heads, head_dim)

struct PhysicalBlock {
    int block_id;           // 物理块ID
    int ref_count;          // 引用计数（共享时>1）
    float* kv_data;         // K和V的连续内存
    int num_used_slots;     // 已用槽位数 (0-16)
};
```

### 2.3 BlockManager（块分配器）

```
BlockManager:
  ├── allocator: 管理所有可用物理块的分配和回收
  ├── gpu_allocator: GPU显存块池
  ├── cpu_allocator: CPU内存块池（swap）
  └── swap_space: 块交换空间管理

分配策略:
  优先用空闲块 → 无可空闲 → 用等待块SWAP到CPU → OOM处理
```

## 3. 前置计算（Prefill）阶段

```
请求到来 (prompt = "什么是Attention机制", 10 tokens)

Phase 1: 全量计算（一次过）
  计算所有token的K、V
  分配物理块存储KV Cache
  
  假设最大batch=8，每个物理块16个token:
    → 这10个token占用1个物理块（浪费6个slot）
    → 但内核块总数可容纳 8×2048/16 = 1024个物理块
  
  BlockTable: [Block_17]
  物理Block_17: [K0,K1,...,K9 | 空闲|空闲|空闲|空闲|空闲]
                          ↑10个token填充    ↑6个空闲
```

## 4. 解码（Decode）阶段

```
"什么是Attention机制" 继续生成

Step 1: 生成token "Attention"
  BlockTable: [Block_17(已满16)]
  → BlockTable: [Block_17, Block_82(新)]
  
Step 2: 生成token "是"
  BlockTable: [Block_17(满), Block_82(1/16)]

...
Step 14: 生成token "："
  BlockTable: [Block_17(满), Block_82(满)]
  → 请求完成，释放Block_17和Block_82
```

## 5. 多头注意力计算

PagedAttention 的核心算力逻辑：

```python
def paged_attention(q, page_table, k_block_tables, v_block_tables):
    """
    q: (num_heads, head_dim)
    page_table: 物理块索引表
    k_cache: (total_blocks, 2, block_size, num_heads, head_dim)
    v_cache: 同上
    """
    score = 0.0
    for block_id in page_table:
        k_block = k_cache[block_id]  # (2, 16, num_heads, head_dim)
        v_block = v_cache[block_id]
        
        # 计算注意力分数
        attn_scores = matmul(q, k_block)  # (16, num_heads)
        attn_weights = softmax(attn_scores)
        
        # 加权求和
        score += matmul(attn_weights, v_block)
    
    return score
```

但这个朴素实现**没有利用GPU的并行能力**。

### GPU优化

**问题**：不同请求的物理块不连续 → 无法合并GPU内核调用

**方案**：用CUDA kernel一次性读取页表→映射到物理块→计算

```cuda
// vLLM实际CUDA kernel（高精简化版）
__global__ void paged_attention_kernel(
    float* output,              // [batch, heads, d]
    float* q_cache,             // [batch, heads, d]
    int* block_tables,          // [batch, num_blocks]
    float* kv_cache,            // [num_blocks, block_size, 2, heads, d]
    int* seq_lens,              // [batch] 实际序列长度
    int num_blocks,
    float sm_scale
) {
    int batch_id = blockIdx.x;
    int head_id = blockIdx.y;
    
    // 获取该请求的页表
    int* page_table = &block_tables[batch_id * num_blocks];
    int seq_len = seq_lens[batch_id];
    
    // 逐块计算
    float sum_weights = 0.0;
    for (int bi = 0; bi < ceil(seq_len / BLOCK_SIZE); bi++) {
        int phys_block = page_table[bi];
        // ... 加载K、V块 → 计算attention
    }
}
```

## 6. 块共享（Block Sharing）

PagedAttention 的关键优势：**多个请求可以共享物理块**。

### 场景：前缀缓存

```
Prompt A: "什么是Attention机制，它在Transformer中扮演什么角色"
Prompt B: "什么是Attention机制，它的计算复杂度是多少"

共享前缀:
  "什么是Attention机制，" → 物理块[Block_17, Block_82]
  差异后缀各自独立 → 浪费的空间从新prompt全量计算→只补后缀
```

### 实现：写时复制（Copy-on-Write）

```python
class BlockManager:
    def alloc_for_shared(self, source_block):
        """共享已有物理块（COW）"""
        source_block.ref_count += 1
        return source_block  # 指向同一物理块
    
    def write_token(self, block, token_pos):
        """写入前检查引用计数"""
        if block.ref_count > 1:
            # COW: 分配新块，复制旧数据
            new_block = self.alloc_empty()
            copy_kv_data(new_block, block)
            block.ref_count -= 1
            block = new_block
        # 写入新token
        block.kv_data[token_pos] = ...
```

### 内存节省

```
场景: 100个请求，80个共享前8个token（一个物理块）

无共享: 100 × 100tokens = 100物理块占用
有共享: 1(共享前缀) + 92 × 92tokens = 93物理块
        → 节省7%

长前缀共享（如系统prompt "You are a helpful AI" ~ 20tokens）:
无共享: 100 × 120tokens = 750物理块
有共享: 2(共享前缀) + 100 × 100tokens = 627物理块
        → 节省16.4%
```

## 7. 显存管理策略

### 7.1 预分配与动态增长

```python
class GpuAllocator:
    def __init__(self, num_gpu_blocks):
        # 预先分配所有物理块（避免碎片化）
        self.free_blocks = list(range(num_gpu_blocks))
        self.ref_counts = [0] * num_gpu_blocks
    
    def alloc(self):
        if not self.free_blocks:
            # 触发swap或OOM
            return self._handle_oom()
        block_id = self.free_blocks.pop()
        self.ref_counts[block_id] = 1
        return block_id
    
    def free(self, block_id):
        self.ref_counts[block_id] -= 1
        if self.ref_counts[block_id] == 0:
            self.free_blocks.append(block_id)
```

### 7.2 Swapping（块换出到CPU）

当GPU显存不足时，将物理块换出到CPU内存：

```
层1: GPU显存（~80GB） → 层2: CPU内存（~512GB） → 层3: 磁盘（可选）
                        ↑
                    LRU策略，根据访问时间
```

```c
// swap决策
bool should_swap(BlockStats stats) {
    // 如果GPU空闲块 < 20%，触发swap
    return stats.free_blocks / stats.total_blocks < 0.2;
}

void swap_out(PhysicalBlock* block, CPUBlock* cpu_block) {
    cudaMemcpyAsync(
        cpu_block->data, 
        block->data, 
        sizeof(block->data),
        cudaMemcpyDeviceToHost
    );
    // 标记块为"swapped out"
    block->state = SWAPPED_OUT;
}
```

### 7.3 OOM处理级联

```
GPU空闲块不足
  → 先尝试block sharing（合并共享前缀）
  → 不够就swap oldest blocks
  → 还不够就拒绝新请求（返回busy）
  → 极端情况：kill最早请求
```

## 8. 源码级性能对比

| 特性 | Naive Attention | FlashAttention | PagedAttention |
|------|:--------------:|:--------------:|:--------------:|
| 显存分配 | 最大长度预分配 | 最大长度预分配 | 动态分页 |
| 碎片浪费 | ~50-70% | ~50-70% | <6% |
| 共享前缀 | 不支持 | 不支持 | 原生支持 |
| Swapping | 不支持 | 不支持 | 块级别swap |
| 内核复杂度 | O(1) | O(n) GPU IO优化 | O(n) + 页表映射 |
| 适用场景 | 单请求 | 训练 | **推理服务** |

## 知识图谱关联

```
┌──────────────┐     ┌────────────┐     ┌──────────────┐
│ LLM推理优化#8 │     │  本课       │     │ LLM推理优化  │
│ 服务化设计    │◀────│ PagedAttn  │────▶│ #3 vLLM架构 │
└──────────────┘     └──────┬─────┘     └──────────────┘
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
        ┌──────────────┐    ┌──────────────┐
        │ FlashAttn #6 │    │ TensorRT-LLM │        
        │ IO优化       │    │ #10 Multi-   │
        │              │    │ block KV     │
        └──────────────┘    └──────────────┘
```

## 课后思考

1. **对比**：PagedAttention 的物理块和操作系统的页表在概念和实现上的异同
2. **设计**：如果块大小从16改为32或8，分别对内存利用率/GPU内核效率有什么影响？
3. **推理**：为什么PagedAttention不用4KB页而用16 tokens/page（每个token ~1KB）？
4. **优化**：在共享前缀场景下，多个请求同时生成到同一个物理块时，写时复制如何避免竞争条件？

---

**学习时间**: 2026-05-18 23:04-23:18
**笔记状态**: 完成
