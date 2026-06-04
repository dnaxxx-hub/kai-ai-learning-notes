# 课时5：内存优化——让显存塞下更大的模型

## 概述

深度学习训练的内存压力来自三个层次：模型参数、优化器状态、中间激活值（activations）。以 GPT-3 175B 为例，仅参数就需要 700GB（FP16），这是单张 A100 80GB 完全无法容纳的。本课深入内存优化的核心技术：从 ZeRO 系列策略到重计算（重算 + 检查点），再到内存碎片管理。

## 核心概念

### 1. ZeRO 系列优化

**ZeRO（Zero Redundancy Optimizer）** 是 DeepSpeed 提出的一系列内存优化策略。核心思想是：**将模型状态（参数、梯度、优化器状态）分布到多个设备上，而不是每个设备都存一份完整副本**。

**三种优化状态的分布需求**（以 Adam 优化器、FP16 训练为例）：

| 状态 | 每参数所需内存 | 说明 |
|------|---------------|------|
| 参数 (Parameters) | 2 bytes (FP16) | 前向/反向计算所需 |
| 梯度 (Gradients) | 2 bytes (FP16) | 反向传播时累积 |
| 优化器状态 (Optimizer States) | 12 bytes | Adam: 2×FP32 (momentum+方差) + 1×FP32 (参数副本) |

总计：每参数 **16 bytes**。175B 模型 → 2.8TB，远超单卡容量。

```python
class ZeROOptimizer:
    """
    ZeRO 分阶段内存优化的概念实现。
    """
    def __init__(self, model, world_size, rank):
        self.model = model
        self.world_size = world_size
        self.rank = rank
        
    # === ZeRO Stage 1: 优化器状态分片 ===
    def zero_stage1(self):
        """
        将优化器状态分割到 world_size 个 GPU。
        节省 ~12 bytes/参数。
        每个 GPU 只负责管理 (总参数数 / world_size) 的优化器状态。
        """
        # 每个 rank 只维护一部分参数的优化器状态
        param_chunks = self._partition_params(self.model.parameters())
        my_params = param_chunks[self.rank]
        self.optimizer_states = {
            p: self._init_adam_state(p) for p in my_params
        }
    
    # === ZeRO Stage 2: 梯度分片 ===
    def zero_stage2(self):
        """
        在前一阶段基础上，再将梯度分片。
        节省额外 ~2 bytes/参数。
        """
        # 反向传播后，对梯度执行 allreduce 均值
        # 但每个 rank 只保留自己负责的部分
        for param in self.model.parameters():
            # all-reduce 梯度的简化版：
            # global_grad = allreduce(param.grad)
            # 只保留自己分片的梯度
            param.grad = self._reduce_scatter(param.grad)
    
    # === ZeRO Stage 3: 参数分片 ===
    def zero_stage3(self):
        """
        在前述基础上，参数也分片。每个 rank 只持有部分参数。
        节省额外 ~2 bytes/参数。
        
        关键挑战：参数需要在需要时"动态收集"。
        前向传播到某个层时，从拥有该层参数的 rank 广播过来。
        计算完毕后丢弃。
        """
        for layer in self.model.layers:
            # 阶段3：动态参数收集
            with self._gather_layer_params(layer):
                # 前向计算时，本 rank 已拥有所有参数
                hidden = layer(hidden)
            # 前向结束后立即丢弃其他 rank 的参数
            # 仅保留自己的分片
    
    def _partition_params(self, params):
        """将参数均匀分配到各个 rank"""
        param_list = list(params)
        chunk_size = (len(param_list) + self.world_size - 1) // self.world_size
        chunks = []
        for i in range(0, len(param_list), chunk_size):
            chunks.append(param_list[i:i + chunk_size])
        return chunks
    
    def _gather_layer_params(self, layer):
        """临时收集模型参数（上下文管理器风格）"""
        class GatherContext:
            def __enter__(self):
                # 从其他 rank 收集参数
                for param in layer.parameters(recurse=False):
                    # broadcast from owning_rank
                    owning_rank = self._param_owner(param)
                    if owning_rank != self.rank:
                        param.data = broadcast(param.data, owning_rank)
                return self
            
            def __exit__(self, *args):
                # 退出时丢弃收集来的参数
                for param in layer.parameters(recurse=False):
                    if self._param_owner(param) != self.rank:
                        param.data = None  # 释放内存
        
        return GatherContext()

    def _param_owner(self, param):
        """返回拥有该参数的 rank"""
        # 根据参数 ID 哈希决定归属
        return hash(id(param)) % self.world_size
```

**ZeRO 各阶段内存节省对比**（N 卡训练）：

| 阶段 | 每参数内存 | 总内节省 | 通信开销 |
|------|-----------|---------|---------|
| 无 ZeRO | 16bytes | 1x | - |
| Stage 1 | 4 + 12/N | ~3x | 低 |
| Stage 2 | 2 + (2+12)/N | ~8x | 中 |
| Stage 3 | (2+2+12)/N | ~Nx | 高 |

### 2. 重计算与梯度检查点

**重计算（Recomputation / 梯度检查点）** 是内存优化的经典技术。核心思想是：前向传播时不保存所有中间激活值，而是只在某些"检查点"保存；反向传播时，需要梯度时重新执行一次前向来恢复中间值。

**数学基础**：
- 无检查点：前向存储 O(L) 个中间张量，L=网络层数
- 有检查点：存储 O(√L) 个检查点，反向重算每个分段需要 O(√L) 的额外前向

```python
class CheckpointEngine:
    """
    梯度检查点引擎的完整实现。
    支持选择不同的检查点策略。
    """
    def __init__(self, model):
        self.model = model
        self.checkpointed_segments = []
    
    def set_checkpoints_every(self, n_layers):
        """每隔 n 层设置一个检查点"""
        layers = list(self.model.layers)
        segments = []
        for i in range(0, len(layers), n_layers):
            segment = layers[i:i + n_layers]
            segments.append(segment)
        self.checkpointed_segments = segments
    
    # 前向传播（有检查点）
    def forward_with_checkpoint(self, x):
        """
        前向传播时，只保存检查点输入，丢弃中间结果。
        """
        saved_inputs = [x]
        
        for segment in self.checkpointed_segments:
            # 保存此段输入到检查点
            x_checkpoint = x.detach().clone()
            saved_inputs.append(x_checkpoint)
            
            # 执行前向（不保存中间激活）
            with torch.no_grad():
                for layer in segment:
                    x = layer(x)
        
        self.saved_inputs = saved_inputs
        return x
    
    def backward_with_checkpoint(self, grad_output):
        """
        反向传播：从最近的检查点开始重算前向，恢复中间值。
        """
        for i in range(len(self.checkpointed_segments) - 1, -1, -1):
            segment = self.checkpointed_segments[i]
            
            # 从检查点恢复输入
            segment_input = self.saved_inputs[i]
            
            # 重算前向传播（会创建新的计算图）
            # 这样反向传播时就有中间值了
            with torch.enable_grad():
                x = segment_input
                for layer in segment:
                    x = layer(x)
                # 此时 x 包含完整的计算图
            
            # 使用保存的梯度回传
            torch.autograd.backward(x, grad_output)
            
            # 获取输入部分的梯度，传递给下一段
            grad_output = segment_input.grad
    
    def auto_select_checkpoints(self, memory_budget_gb):
        """
        根据内存预算自动选择检查点位置。
        基于贪心策略：在内存超出预算的"热点"区域插入检查点。
        """
        # 实际实现会：
        # 1. 先用小 batch profile 每层的激活内存
        # 2. 自顶向下分析哪段值得检查点
        # 3. 在有检查点的情况下重新评估内存预算
        # 4. 迭代调整直到满足预算
        pass

# 梯度检查点与重计算的效率分析
recv = """
内存-时间权衡曲线：
无检查点:  memory=O(L),  time=O(L)
均匀检查点: memory=O(√L), time=O(L + √L * L/seg) ≈ O(L) + O(L/seg * √L)

当 seg = √L 时，内存降到 O(√L)，时间增加约 √L 次额外前向。
对于 100 层的网络，检查点间隔 10 层：
  内存: 100 → 20 个单位  (5x 节省)
  时间: 100 → 110 个单位 (10% 额外)
"""

# PyTorch 中直接使用方法
def pytorch_checkpoint_demo():
    """PyTorch 的梯度检查点 API"""
    model = nn.Sequential(
        nn.Linear(1024, 1024),
        nn.ReLU(),
        nn.Linear(1024, 1024),
        nn.ReLU(),
    )
    
    x = torch.randn(32, 1024, requires_grad=True)
    
    # 方案1：普通前向（保存所有中间值）
    y = model(x)
    y.sum().backward()
    
    # 方案2：使用梯度检查点（分段重算）
    from torch.utils.checkpoint import checkpoint
    
    def forward_segment(x, seg1, seg2):
        x = seg1(x)
        x = seg2(x)
        return x
    
    # 将连续的一段包装为 checkpoint 函数
    x2 = torch.randn(32, 1024, requires_grad=True)
    y2 = checkpoint(forward_segment, x2, model[0], model[1])
    y2 = checkpoint(forward_segment, y2, model[2], model[3])
    y2.sum().backward()
    # 内存从 4 个中间张量降为 2 个，节省约 50%
```

### 3. 内存碎片整理

**内存碎片** 是长期训练中的隐形杀手。随着不断分配和释放各种大小的张量，显存会出现大量不连续的小块空闲内存，导致"明明有空闲内存，但因为不连续而无法分配大张量"的 OOM。

```python
class MemoryProfiler:
    """内存碎片分析和整理"""
    
    def __init__(self):
        self.block_map = {}  # ptr → (size, is_free)
    
    def analyze_fragmentation(self):
        """
        计算内存碎片率：
        fragmentation = 1 - (largest_free_block / total_free_memory)
        """
        total_free = 0
        max_free_block = 0
        free_blocks = []
        
        for ptr, (size, is_free) in self.block_map.items():
            if is_free:
                total_free += size
                max_free_block = max(max_free_block, size)
                free_blocks.append(size)
        
        fragmentation = 1 - (max_free_block / total_free) if total_free > 0 else 0
        return {
            'fragmentation': fragmentation,
            'total_free_mb': total_free / 1024**2,
            'max_free_block_mb': max_free_block / 1024**2,
            'free_block_count': len(free_blocks),
        }
    
    def recommend_defrag(self):
        """
        推荐碎片整理策略。
        
        由于 GPU 不允许重新映射指针（除非支持虚拟地址管理），
        实际碎片整理非常困难。常用的替代方案：
        """
        report = self.analyze_fragmentation()
        
        if report['fragmentation'] > 0.3 and report['free_block_count'] > 100:
            return {
                'action': 'clear_cache',
                'reason': f"碎片率 {report['fragmentation']:.1%}，存在大量小块碎片",
                'effect': '可能释放显存给操作系统，但会丢失缓存',
                'code': "torch.cuda.empty_cache()"
            }
        elif report['fragmentation'] > 0.5:
            return {
                'action': 'defrag_and_compact',
                'reason': "严重碎片化，建议重启训练进程",
                'effect': '新进程重新分配所有显存，消除碎片',
                'code': "重启后使用更大的块分配策略"
            }
    
    def adaptive_block_allocation(self, requested_size):
        """
        智能分配策略：对齐到 2MB 块，减少碎片。
        这是 PyTorch/CUDACachingAllocator 的核心策略。
        """
        # 实际策略
        ALIGNMENT = 2 * 1024 * 1024  # 2MB 对齐
        aligned_size = ((requested_size + ALIGNMENT - 1) // ALIGNMENT) * ALIGNMENT
        
        # 选择最合适的空闲块（best-fit 策略 + 分割）
        best_block = None
        best_block_size = float('inf')
        
        for ptr, (size, is_free) in self.block_map.items():
            if is_free and size >= aligned_size:
                if size < best_block_size:
                    best_block = ptr
                    best_block_size = size
        
        # 如果找到合适的块，分割它
        if best_block is not None:
            if best_block_size > aligned_size + ALIGNMENT:
                # 分割：剩余部分作为新的空闲块
                remaining_ptr = best_block + aligned_size
                remaining_size = best_block_size - aligned_size
                self.block_map[remaining_ptr] = (remaining_size, True)
            
            del self.block_map[best_block]
            return best_block
        
        # 没有合适块，从 GPU 申请新的
        return cuda_malloc(aligned_size)
```

### 4. 生命周期分析

**张量生命周期分析** 是高级内存优化的基础。通过分析计算图中每个中间张量的"最后使用点"（Last Use Point），可以及时释放内存，甚至复用已释放的张量。

```python
class LifetimeAnalyzer:
    """
    张量生命周期分析。
    基于 IR 来确定每个张量的创建和最后一次使用。
    """
    def __init__(self, graph):
        self.graph = graph
        self.lifetimes = {}  # tensor_id → (birth, death)
    
    def analyze(self):
        """
        计算每个张量的生命周期：
        - birth = 第一次使用的操作序号
        - death = 最后一次被引用的操作序号
        """
        # 遍历所有操作，记录使用关系
        for op_idx, op in enumerate(self.graph.ops):
            for output in op.outputs:
                if output not in self.lifetimes:
                    self.lifetimes[output] = {'birth': op_idx, 'death': op_idx}
            
            for input_tensor in op.inputs:
                if input_tensor in self.lifetimes:
                    self.lifetimes[input_tensor]['death'] = op_idx
        
        return self.lifetimes
    
    def suggest_memory_reuse(self):
        """
        根据生命周期分析建议张量复用。
        如果两个张量的生命周期不重叠，可以共享同一显存块。
        """
        lifespans = [(tid, lt['birth'], lt['death']) 
                     for tid, lt in self.lifetimes.items()]
        lifespans.sort(key=lambda x: x[1])  # 按 birth 排序
        
        reusable_pairs = []
        for i, (tid_a, birth_a, death_a) in enumerate(lifespans):
            for j, (tid_b, birth_b, death_b) in enumerate(lifespans[i+1:], i+1):
                if death_a < birth_b or death_b < birth_a:
                    # 生命周期不重叠，可以复用！
                    if self._same_size(tid_a, tid_b):
                        reusable_pairs.append((tid_a, tid_b))
        
        return reusable_pairs
    
    def _same_size(self, tid_a, tid_b):
        """检查两个张量大小是否兼容（用于复用检查）"""
        return self.graph.get_tensor_size(tid_a) == self.graph.get_tensor_size(tid_b)

# 内存分配器的优化策略
class OptimizedAllocator:
    """
    基于生命周期分析的内存分配器。
    提前规划复用，减少碎片。
    """
    def allocate_planned(self, graph):
        lifetimes = LifetimeAnalyzer(graph).analyze()
        
        # 调度策略：
        # 1. 按 birth 时间排序所有张量分配需求
        allocations = sorted(lifetimes.items(), 
                            key=lambda x: x[1]['birth'])
        
        active_blocks = {}  # tid → block_ptr
        free_blocks = []
        
        for tid, lt in allocations:
            size = graph.get_tensor_size(tid)
            birth, death = lt['birth'], lt['death']
            
            # 释放所有在 birth 之前已经 dead 的块
            active_blocks = {
                k: v for k, v in active_blocks.items()
                if lifetimes[k]['death'] >= birth
            }
            
            # 尝试从 free_blocks 复用
            allocated = False
            for i, (free_tid, free_ptr) in enumerate(free_blocks):
                if free_tid is None or graph.get_tensor_size(free_tid) >= size:
                    active_blocks[tid] = free_ptr
                    free_blocks.pop(i)
                    allocated = True
                    break
            
            if not allocated:
                active_blocks[tid] = cuda_malloc(size)
        
        return active_blocks
```

## 实用技巧

### 混合精度训练的内存优化

```python
def mixed_precision_memory_savings():
    """
    FP16/FP32 混合精度的内存节省计算。
    配合 GradScaler 使用。
    """
    param_count = 1_000_000_000  # 1B 参数
    
    fp32_memory = param_count * 4  # 4 bytes per param
    fp16_memory = param_count * 2  # 2 bytes per param
    
    # 混合精度策略
    # - 参数以 FP16 存储：2GB
    # - 维持 FP32 主副本：4GB (只在更新时用到)
    # - 梯度以 FP16 存储：2GB
    # - 反向传播时激活以 FP16 存储：约减半
    
    savings = {
        'params': "FP16 = 50% of FP32",
        'activations': "FP16 = 50% of FP32",
        'master_weights': "+100% (FP32 copy for update)",
        'net_effect': f"典型节省 40-50%",
    }
    
    return savings
```

## 延伸阅读

- [ZeRO: Memory Optimizations Toward Training Trillion Parameter Models (Rajbhandari et al., 2020)](https://arxiv.org/abs/1910.02054)
- [Training Deep Nets with Sublinear Memory Cost (Chen et al., 2016)](https://arxiv.org/abs/1604.06174)
- [PyTorch CUDACachingAllocator](https://pytorch.org/docs/stable/notes/cuda.html#cuda-memory-management)

## 关键总结

1. **ZeRO Stage 1-3** 将模型状态分布到多卡，从优化器状态分片到参数完全分片，内存节省从 3x 到 Nx
2. **梯度检查点** 以时间换空间，通过重算前向减少激活内存，典型节省 50-80%
3. **内存碎片** 来源于频繁的小块分配释放，2MB 对齐 + best-fit 策略可以有效缓解
4. **生命周期分析** 支持张量复用和预分配，是高级内存优化的基础
5. **混合精度训练** 通过 FP16 存储和计算，大幅降低激活和梯度的内存需求
