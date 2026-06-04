# 迷你PagedAttention推理引擎 — LLM推理优化#4 实践笔记

> 日期: 2026-05-24 | 文件: `projects/paged_attention/paged_attention.py` (18KB, 零依赖)
> 测试: 61/61 全部通过

## 1. 项目架构

```
┌─────────────────────────────────────────────────────┐
│              PagedAttention Simulator                │
├──────────────┬─────────────┬───────────┬────────────┤
│ KVBlockMgr   │ PrefixCache │ Scheduler │ InferEng   │
│ - alloc/free │ - hash match│ - priority│ - prefill  │
│ - CoW        │ - LRU evict │ - preempt │ - decode   │
│ - refcount   │ - hit rate  │ - queue   │ - compute  │
│ - fragment   │             │           │            │
└──────────────┴─────────────┴───────────┴────────────┘
```

## 2. 核心设计

### KVBlockManager — 逻辑块管理（类似OS分页）
- 固定块大小（16 tokens/block）
- **分配**：从空闲列表取物理块，引用计数+1
- **释放**：引用计数-1，归0才真正的free
- **写时复制(CoW)**：beam search共享KV块，ref_count=1直接共享，>1才拷贝
- **碎片率**：统计空闲块中不连续的比例

### PrefixCache — 前缀缓存
- 每block计算MD5哈希
- **匹配策略**：从头扫描prompt，逐block匹配缓存hash
- 命中则跳过计算，未命中处开始全量计算
- **LRU淘汰**：物理块不足时逐出最久未用

### Scheduler — 请求调度
- 优先级队列（min-heap，但存储原始priority）
- **调度时**：先处理被抢占的请求，再处理队列
- **抢占策略**：lowest_priority_first，不抢占更高优先级的
- Backoff机制（通过queue自然实现）

### InferenceEngine — 推理模拟
- **Prefill**：检查缓存 → 计算未命中部分 → 分配并缓存新块
- **Decode**：逐token生成，每16 tokens新增一个block
- 报告：compute_blocks、cached_tokens、time_taken

### BenchmarkRunner
- 随机请求生成（可变prompt长度+生成长度）
- 共享前缀请求生成（测试前缀缓存效果）
- 完整报告：吞吐量、缓存命中率、KV利用率、延迟

## 3. Benchmark结果（15请求）

```
Requests:        15 (15 done)
Avg latency:     0.000062s
Sim time:        0.5550s (wall: 0.0012s)
Throughput:      27.03 req/s
Cache hit rate:  34.78% (16/46)
KV util:         86.72% (preempt: 0)
Compute blocks:  111 (prefill=67, decode=44)
```

10个随机请求 + 5个共享前缀请求，缓存命中率34.78%，KV利用率86.72%。

## 4. 实现难点

1. **Property与Method冲突**：`free`既是property又是method名，导致`@property`和`.free(pid)`冲突 → 改名为`free_count`和`free_block`
2. **alloc_n不追踪逻辑块**：批量分配只分配物理块但不建立逻辑→物理映射，导致`free_req`找不到要释放的块
3. **min-heap优先级反转**：Python的heapq是min-heap，存储(priority, request)时数字越小优先级越高，与直觉相反
4. **start_time依赖prefill调用**：手动设置`prefilled=True`后忘记设`start_time`导致latency为None

## 5. 与真实vLLM的差异
- vLLM使用GPU显存管理，这里是纯CPU模拟
- vLLM的PagedAttention实际计算attention分数，这里仅模拟块分配
- 真实前缀缓存需要精确token ID匹配，这里用MD5简化
- 真实的调度器更复杂（continuous batching、动态batching）
