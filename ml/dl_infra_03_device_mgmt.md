# 课时3：设备管理——GPU 执行的指挥艺术

## 概述

现代深度学习训练依赖 GPU 等加速器，设备管理是框架底层的核心基础设施。高效的设备管理需要处理：并发流的调度、性能剖析、内存分配、异步执行和事件同步。本课深入 CUDA 编程模型中的关键组件，展示框架如何管理设备资源。

## 核心概念

### 1. CUDA Stream 与异步执行

**CUDA Stream**（流）是一个 GPU 操作序列，所有操作按提交顺序执行（FIFO）。不同流之间的操作可以并发执行（取决于 GPU 硬件资源）。Stream 是 GPU 并行性的核心抽象。

**默认流 vs 非默认流**：
- 默认流（Default Stream / Stream 0）：所有未指定流的操作默认在其中执行
- 非默认流：用户创建的流，可以与默认流并发

```python
class CUDAStream:
    """
    CUDA Stream 的简化模拟。
    展示框架如何管理 GPU 并发执行。
    """
    def __init__(self, priority=0):
        self.id = id(self)
        self.priority = priority
        self._pending_ops = []
    
    def submit(self, kernel_fn, *args, **kwargs):
        """
        提交操作到流中。
        实际框架中这是异步的——立即返回，在 GPU 上排队执行。
        """
        op = {
            'kernel': kernel_fn,
            'args': args,
            'stream_id': self.id,
        }
        self._pending_ops.append(op)
        # 真正的 CUDA API: cudaLaunchKernel(kernel, ...)
        return op

class DeviceManager:
    """
    设备管理器：管理 GPU 资源、流和多设备。
    """
    def __init__(self, device_id=0):
        self.device_id = device_id
        self.streams = {}       # name → CUDAStream
        self.events = {}        # name → CudaEvent
        self.default_stream = self.create_stream("default")
    
    def create_stream(self, name, priority=0):
        stream = CUDAStream(priority=priority)
        self.streams[name] = stream
        return stream
    
    def synchronize(self, stream_name=None):
        """同步：等待指定流（或所有流）完成"""
        if stream_name:
            self.streams[stream_name].barrier()
        else:
            for s in self.streams.values():
                s.barrier()
        # 实际 CUDA API:
        # cudaStreamSynchronize(stream)  # 单个流
        # cudaDeviceSynchronize()        # 所有流

# 多流并发示例
device = DeviceManager(device_id=0)

# 创建两个流：计算流和传输流
compute_stream = device.create_stream("compute")
transfer_stream = device.create_stream("transfer")

# 场景：使用多流水线隐藏数据传输延迟
# 1. 传输流将数据从 CPU 复制到 GPU（占用 PCIe 带宽）
transfer_stream.submit(cuda_memcpy_h2d, host_data_chunk_0, gpu_buffer_0, size)
# 2. 计算流在 GPU 上执行（占用 GPU 计算单元）
compute_stream.submit(compute_kernel, gpu_buffer_1, output_1)
# 这两个操作可以在 GPU 上并发执行！
```

**异步执行的陷阱**：
- CUDA 操作默认是**异步的**：`cudaMemcpyAsync` 等函数立即返回，实际传输在后台进行
- 必须在读取结果之前正确同步
- PyTorch/NVIDIA 的性能优化大量依赖异步执行和流并发

### 2. 事件同步（Event Synchronization）

**CUDA Event** 是流之间的同步原语。可以记录一个事件到流中，然后在另一个流中等待该事件，实现流间依赖。

```python
class CudaEvent:
    """
    CUDA Event 的简化版本。
    用于测量时间和同步流。
    """
    def __init__(self, name=""):
        self.name = name
        self.recorded_stream = None
        self._timestamp = None
    
    def record(self, stream):
        """在指定流上记录事件"""
        self.recorded_stream = stream
        stream._pending_ops.append({
            'type': 'event_record',
            'event': self,
        })
        # CUDA API: cudaEventRecord(event, stream)
    
    def wait(self, stream):
        """
        让指定流等待此事件完成。
        这是流间同步的关键机制。
        """
        assert self.recorded_stream is not None, "Event not recorded"
        stream._pending_ops.append({
            'type': 'event_wait',
            'event': self,
        })
        # CUDA API: cudaStreamWaitEvent(stream, event)
    
    def elapsed_time(self, other):
        """计算两个事件之间的时间差（毫秒）"""
        # CUDA API: cudaEventElapsedTime(&ms, start, end)
        pass

# 事件同步应用：多阶段流水线

def pipeline_example():
    """
    三阶段流水线：数据加载 → 前向计算 → 梯度更新
    使用事件同步确保流水线正确性。
    """
    stream_data = CUDAStream()
    stream_fwd = CUDAStream()
    stream_bwd = CUDAStream()
    
    # 阶段1：数据传输（CPU→GPU）
    e_data_ready = CudaEvent("data_ready")
    stream_data.submit(h2d_copy, batch_0, gpu_input)
    e_data_ready.record(stream_data)
    
    # 阶段2：前向传播（等待数据就绪）
    e_fwd_done = CudaEvent("fwd_done")
    e_data_ready.wait(stream_fwd)  # 在数据就绪之前，不执行前向
    stream_fwd.submit(forward_kernel, gpu_input, gpu_output)
    e_fwd_done.record(stream_fwd)
    
    # 阶段3：反向传播（等待前向完成）
    e_bwd_done = CudaEvent("bwd_done")
    e_fwd_done.wait(stream_bwd)
    stream_bwd.submit(backward_kernel, gpu_output, gpu_grad)
    e_bwd_done.record(stream_bwd)
    
    # 同时，数据流可以开始加载下一批数据
    # （流水线并行）
    stream_data.submit(h2d_copy, batch_1, gpu_input_next)

# PyTorch 中的等效操作
# torch.cuda.synchronize(device)  # 同步设备
# torch.cuda.Event  # 事件对象
# stream.wait_event(event)  # 流等待事件
# event.record(stream)  # 流中记录事件
```

### 3. CUPTI：性能剖析基础设施

**CUPTI（CUDA Profiling Tools Interface）** 是 NVIDIA 提供的性能分析接口。深度学习框架使用 CUPTI 来：
1. 跟踪 kernel 执行时间
2. 测量数据传输带宽
3. 分析 GPU 利用率
4. 检测性能瓶颈

```python
class CUPTIProfiler:
    """
    CUPTI 性能剖析器的概念演示。
    实际实现使用 CUPTI Callback 和 Activity API。
    """
    def __init__(self):
        self.kernel_timings = []
        self.memcpy_timings = []
        self._is_recording = False
    
    def start_recording(self):
        """开始记录 GPU 活动"""
        self._is_recording = True
        # CUPTI: cuptiSubscribe(callback, ...)
    
    def stop_recording(self):
        self._is_recording = False
        # CUPTI: cuptiUnsubscribe(...)
    
    def _on_kernel_launch(self, kernel_name, grid, block, shared_mem):
        """CUPTI callback：每次 kernel 启动时触发"""
        if self._is_recording:
            # 实际会通过 cuptiGetTimestamp 获取精确时间
            pass
    
    def report(self):
        """生成性能报告"""
        if not self.kernel_timings:
            return "No data recorded"
        
        total_time = sum(t['duration'] for t in self.kernel_timings)
        print(f"Total GPU time: {total_time:.2f} ms")
        
        # 按 kernel 名称聚合
        from collections import defaultdict
        by_kernel = defaultdict(float)
        for t in self.kernel_timings:
            by_kernel[t['name']] += t['duration']
        
        print("\nTop 5 kernels by time:")
        for name, time in sorted(by_kernel.items(), 
                                  key=lambda x: -x[1])[:5]:
            print(f"  {name}: {time:.2f} ms ({100*time/total_time:.1f}%)")

# PyTorch 的 CUPTI 集成
# 自动记录 kernel 活动到 Chrome trace 格式
# torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CUDA])
```

### 4. 内存池（Memory Pool）

GPU 显存分配（cudaMalloc/cudaFree）是一个昂贵的操作（~10-100μs）。深度学习框架使用**内存池**来复用已分配显存，避免频繁调用底层分配器。

```python
class GPUMemoryPool:
    """
    GPU 显存池的简化实现。
    核心思想：使用过的显存不释放，缓存起来复用。
    """
    def __init__(self, device_id=0, pool_size_gb=8):
        self.device_id = device_id
        self.total_bytes = pool_size_gb * 1024**3
        self.used_bytes = 0
        self.pool = {}      # size → [block1, block2, ...] (free list)
        self.allocated = {} # id → (ptr, size)
        self.hits = 0       # 缓存命中统计
        self.misses = 0
    
    def allocate(self, size_bytes):
        """从内存池中分配显存"""
        # 对齐到 256 字节（CUDA 对齐要求）
        aligned_size = ((size_bytes + 255) // 256) * 256
        
        # 查找可复用的块
        bucket = self.pool.get(aligned_size, [])
        if bucket:
            block = bucket.pop()  # 复用已分配的块
            self.hits += 1
        else:
            # 必须向 GPU 申请新内存
            if self.used_bytes + aligned_size > self.total_bytes:
                raise RuntimeError(f"OOM: {self.used_bytes + aligned_size} > {self.total_bytes}")
            block = cuda_malloc(aligned_size)  # 真正的 CUDA API
            self.misses += 1
        
        block_id = id(block)
        self.allocated[block_id] = (block, aligned_size)
        self.used_bytes += aligned_size
        return block, block_id
    
    def free(self, block_id):
        """释放：实际是放回缓存池，而不是还给了操作系统"""
        block, size = self.allocated.pop(block_id)
        
        # 放入 free list
        if size not in self.pool:
            self.pool[size] = []
        self.pool[size].append(block)
        self.used_bytes -= size
    
    def defragment(self):
        """
        内存碎片整理（实际中很难做到，因为 GPU 不允许指针重映射）。
        替代方案：在 OOM 时尝试释放所有缓存。
        """
        freed = 0
        for size, blocks in self.pool.items():
            for block in blocks:
                cuda_free(block)
                freed += 1
            blocks.clear()
        return freed
    
    def stats(self):
        hit_rate = self.hits / (self.hits + self.misses) * 100
        return {
            'hit_rate': f"{hit_rate:.1f}%",
            'pool_fragments': sum(len(v) for v in self.pool.values()),
            'total_allocated': self.total_bytes / 1024**3,
        }

# PyTorch 中的内存池管理
# torch.cuda.memory_allocated()     # 已分配的内存
# torch.cuda.memory_reserved()      # 保留给缓存池的内存
# torch.cuda.memory_summary()       # 完整内存报告
# torch.cuda.empty_cache()          # 清空缓存池（释放给操作系统）
```

## 实用技巧

### 使用 Nsight Systems 分析 Stream 并发

```python
# 分析多流并发的标志性技巧
def debug_stream_concurrency():
    """
    使用 nsys 命令行分析 GPU 活动：
    nsys profile -o trace -t cuda,nvtx python train.py
    
    观察要点（在 Timeline 视图中）：
    1. 两个流的 kernel 是否有时间重叠 → 并发度
    2. H2D/D2H 传输是否与计算重叠 → 传输隐藏
    3. 是否存在不必要的同步（Stream 间的空泡）
    """
    # 在代码中标注关键区域
    # torch.cuda.cudart().cudaProfilerStart()
    # 
    # 红色区域：数据传输
    # stream_data.submit(memcpy, ...)
    # torch.cuda.nvtx.range_push("data_transfer")
    # 
    # 绿色区域：计算
    # torch.cuda.nvtx.range_push("compute")
    # compute_stream.submit(kernel, ...)
    # torch.cuda.nvtx.range_pop()
```

## 延伸阅读

- [CUDA C++ Programming Guide - Streams](https://docs.nvidia.com/cuda/cuda-c-programming-guide/index.html#streams)
- [PyTorch CUDA Semantics](https://pytorch.org/docs/stable/notes/cuda.html)
- [CUPTI Documentation](https://docs.nvidia.com/cuda/cupti/index.html)

## 关键总结

1. **CUDA Stream** 是 GPU 并发执行的核心抽象，多流可以实现计算与传输的重叠
2. **事件同步**（Event）是流间同步的标准机制，用于构建流水线依赖
3. **CUPTI** 提供 GPU 活动的精确追踪，是性能分析的基础
4. **内存池** 通过缓存复用避免高开销的 cudaMalloc/cudaFree 调用
5. **异步执行** 是 GPU 编程的核心范式，正确使用可以最大化硬件利用率
