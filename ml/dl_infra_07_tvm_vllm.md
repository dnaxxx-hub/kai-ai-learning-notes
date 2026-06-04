# DL Infra 07：推理引擎 — TVM & vLLM

> 课程定位：本课深入现代深度学习推理引擎的核心设计，覆盖 TVM 的编译优化体系和 vLLM 等大模型推理加速器的调度机制。

---

## 一、TVM：深度学习编译器

### 1.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                  深度学习框架                     │
│          (PyTorch / TensorFlow / ONNX)           │
└──────────────────┬──────────────────────────────┘
                   │  Import
                   ▼
┌─────────────────────────────────────────────────┐
│               Relay IR (图级 IR)                  │
│    算子融合 / 常量折叠 / 布局转换 / 量化插入        │
└──────────────────┬──────────────────────────────┘
                   │  Lower
                   ▼
┌─────────────────────────────────────────────────┐
│               TensorIR (张量级 IR)               │
│          循环分块 / 向量化 / 流水线               │
└──────────────────┬──────────────────────────────┘
                   │  Auto-tuning
                   ▼
┌─────────────────────────────────────────────────┐
│         AutoTVM / Ansor (自动调度搜索)            │
│        基于 ML 的代价模型 + 进化搜索               │
└──────────────────┬──────────────────────────────┘
                   │  Build
                   ▼
┌─────────────────────────────────────────────────┐
│           目标代码生成 (LLVM / CUDA / OpenCL)     │
└─────────────────────────────────────────────────┘
```

### 1.2 Relay IR

Relay 是 TVM 的高层计算图 IR，支持：
- **函数式语义**：纯函数、let 绑定、模式匹配
- **自动微分**：内建的 `@grad` 变换
- **类型系统**：静态类型，支持形状推导
- **变换 passes**：
  - FuseOps：算子融合（减少 kernel launch 开销）
  - FoldScaleAxis：量化缩放折叠
  - AlterOpLayout：内存布局转换（NCHW ↔ NHWC）
  - QNN Canonicalize：量化算子标准化

```python
# Relay IR 示例（简化）
# 原始：conv2d + bias_add + relu → 融合为单 kernel
def fuse_conv2d_bias_relu(x, w, b):
    # FuseOps pass 自动识别并合并
    conv = relay.nn.conv2d(x, w, padding=(1, 1))
    bias = relay.add(conv, b)
    act = relay.nn.relu(bias)
    return act
```

### 1.3 AutoTVM 调度搜索

**核心问题**：张量程序的调度优化是一个组合爆炸问题。相同算子在不同硬件上的最优调度完全不同。

**AutoTVM 流程**：
```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 模板定义  │ →  │ 搜索空间  │ →  │ 代价模型  │ →  │ 最优调度  │
│(调度模板) │    │ (参数化)  │    │(XGBoost) │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

```python
# AutoTVM 模板示例
@autotvm.template("matmul")
def matmul_template(N):
    A = te.placeholder((N, N), name="A")
    B = te.placeholder((N, N), name="B")
    k = te.reduce_axis((0, N), name="k")
    C = te.compute((N, N), lambda i, j: te.sum(A[i, k] * B[k, j], axis=k))

    s = te.create_schedule(C.op)
    y, x = s[C].op.axis

    # 搜索参数：分块大小
    cfg = autotvm.get_config()
    cfg.define_knob("tile_y", [2, 4, 8, 16, 32])
    cfg.define_knob("tile_x", [2, 4, 8, 16, 32])

    yo, yi = s[C].split(y, cfg["tile_y"].val)
    xo, xi = s[C].split(x, cfg["tile_x"].val)
    s[C].reorder(yo, xo, yi, xi)

    return s, [A, B, C]
```

### 1.4 Ansor：免模板自动搜索

Ansor (AutoScheduler) 解决了 AutoTVM 需要人工编写调度模板的问题。

**核心创新**：
1. **程序采样**：基于统计的随机搜索，生成多样化的调度候选项
2. **基于进化的细调**：对 top-K 候选项进行进化优化
3. **代价模型**：轻量级 MLP 预测性能，无需 XGBoost 训练开销

**关键区别**：
| 特性 | AutoTVM | Ansor |
|------|---------|-------|
| 模板需求 | 每个算子手写模板 | 自动生成 |
| 搜索空间 | 参数化模板 | 统计采样 + 进化 |
| 代价模型 | XGBoost | MLP |
| 适用场景 | 固定算子集合 | 任意计算图 |

### 1.5 BYOC (Bring Your Own Codegen)

支持将子图卸载到自定义加速器或专用库：

```
                计算图
                  │
           Relay 图分区
                  │
    ┌─────────────┼─────────────┐
    │             │             │
  CPU 算子     GPU 算子    NPU/FPGA 算子
    │             │             │
  LLVM 后端    CUDA 后端   自定义 Codegen
```

适用于：TensorRT 子图、Vitis AI、ARM Compute Library 等。

---

## 二、vLLM：大模型推理加速

### 2.1 问题背景

LLM 推理的瓶颈：
- **KV Cache 巨大**：一个 70B 模型，batch=32，seq_len=4096，KV cache ≈ 40GB+
- **显存碎片**：传统 PyTorch 预分配导致大量碎片
- **调度效率低**：一个 batch 内请求到达/完成时间不同

### 2.2 PagedAttention

**核心思想**：借鉴操作系统虚拟内存分页，将 KV Cache 分块管理。

```
传统方案（连续内存）：
┌──────────────────────────────────────────────┐
│  [请求1]         [请求2]           [请求3]     │
│  ████████░░░░    ████████████░░░  ████░░░░░   │ ← 碎片
└──────────────────────────────────────────────┘

PagedAttention（分页）：
┌──────────────────────────────────────────────┐
│ 物理块表                                        │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┐  │
│  │ 页A  │ 页B  │ 页C  │ 页D  │ 页E  │ 页F  │  │ ← 紧凑排列
│  └──┬───┴──┬───┴──┬───┴──┬───┴──┬───┴──┬───┘  │
│     │      │      │      │      │      │       │
│ 请求1: A→B→C  请求2: D→E  请求3: F→A→D       │
│  (虚拟页表映射到任意物理页)                     │
└──────────────────────────────────────────────┘
```

**Attention 计算**：
```
标准 Attention：
    O = softmax(Q × K^T / √d) × V

PagedAttention：
    O = softmax(Q × (分页 K)^T / √d) × (分页 V)
    // 分页 K/V 是逻辑连续的，但物理上分散在不同块中
```

**关键收益**：
- 零显存碎片（紧凑分配）
- 共享 prefix（相同 prompt 前缀只需一份 KV 块）
- Copy-on-Write（支持 beam search 的增量解码）

### 2.3 KV Cache 管理

```python
# 简化版 vLLM KV Cache Manager 逻辑
class KVBlockManager:
    """类似操作系统物理内存管理器"""

    def __init__(self, total_blocks, block_size=16):
        self.total_blocks = total_blocks
        self.block_size = block_size  # 每个块存放多少 token 的 K/V
        self.free_blocks = set(range(total_blocks))
        self.allocated = {}  # request_id → [block_ids]

    def alloc(self, request_id, num_tokens):
        """为请求分配足够的 KV 块"""
        need_blocks = (num_tokens + self.block_size - 1) // self.block_size
        if len(self.free_blocks) < need_blocks:
            raise OOMError("GPU OOM")
        blocks = []
        for _ in range(need_blocks):
            b = self.free_blocks.pop()
            blocks.append(b)
        self.allocated[request_id] = blocks
        return blocks

    def free(self, request_id):
        """请求完成时释放 KV 块"""
        if request_id in self.allocated:
            self.free_blocks.update(self.allocated.pop(request_id))

    def can_allocate(self, num_tokens):
        need = (num_tokens + self.block_size - 1) // self.block_size
        return len(self.free_blocks) >= need
```

### 2.4 连续批处理 (Continuous Batching)

**传统批处理**（静态）：
```
时间 →
请求1: [████████████]                    ← 必须等所有请求完成
请求2: [████████████████]
请求3: [████████]

实际：batch 中短的请求必须等长的，GPU 利用率低
```

**连续批处理**（动态）：
```
时间 →
请求1: [█ █ █ █ █ █ █ █ █ █ █]
请求3: [█ █ █ █ █]                   ← 被调度器提前踢出
请求2: [█ █ █ █ █ █ █ █ █ █ █ █ █]
请求4:         [█ █ █ █ █ █]         ← 新请求插入空闲 slot

每个 step 调度器决定：哪些请求继续生成、哪些踢出、哪些新加入
```

```python
# 简化版 vLLM 调度器逻辑
class SimpleScheduler:
    def __init__(self, max_batch=8, max_tokens_per_batch=4096):
        self.max_batch = max_batch
        self.max_tokens = max_tokens_per_batch
        self.waiting_queue = []   # 等待加入的请求
        self.running = {}         # 当前正在生成的请求
        self.block_mgr = KVBlockManager(total_blocks=4096)

    def add_request(self, req_id, prompt_len, max_new_tokens):
        self.waiting_queue.append((req_id, prompt_len, max_new_tokens))

    def schedule(self):
        """在每次前向传播前调用，决定 batch 构成"""
        # 1. 踢出已完成的请求
        finished = [r for r in self.running if self.running[r].done]
        for r in finished:
            self.block_mgr.free(r)
            del self.running[r]

        # 2. 从等待队列加入新请求
        batch_tokens = sum(r.num_tokens for r in self.running.values())
        while self.waiting_queue and len(self.running) < self.max_batch:
            req_id, plen, max_t = self.waiting_queue[0]
            tokens_needed = plen + max_t
            if (batch_tokens + tokens_needed <= self.max_tokens
                    and self.block_mgr.can_allocate(tokens_needed)):
                self.waiting_queue.pop(0)
                blocks = self.block_mgr.alloc(req_id, plen)
                self.running[req_id] = RunningRequest(req_id, blocks)
                batch_tokens += tokens_needed
            else:
                break

        # 3. 执行一次前向传播
        return list(self.running.keys())
```

### 2.5 vLLM vs TGI vs Triton

| 特性 | vLLM | TGI (Text Generation Inference) | Triton Inference Server |
|------|------|------|------|
| 核心创新 | PagedAttention | 动态 batching + 规则引擎 | 通用推理服务框架 |
| KV Cache | 分页管理 | 连续缓存 | 不内置（依赖后端） |
| 调度策略 | 穷举式搜索 | 基于启发式 | 可自定义调度器 |
| 模型支持 | LLM 为主 | LLM 为主 | 任意模型（通过后端） |
| 多 GPU | 张量并行 | 张量并行 | 模型并行 + 流水线 |
| 优势 | 吞吐最高 | 延迟优化 | 通用性、多框架 |

**Triton Inference Server** 重点：
- 模型仓库（Model Repository）：版本管理、模型平滑切换
- 并发模型执行：多模型共存，动态路由
- 自定义后端（C++/Python）：任何框架都可以集成
- 性能分析工具：perf_analyzer

---

## 三、代码实践：简化版 vLLM 调度引擎

```python
"""
简化版 vLLM 调度逻辑演示
仅用于教学，非生产代码
"""
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class RequestStatus(Enum):
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"


@dataclass
class Request:
    req_id: int
    prompt_len: int
    max_new_tokens: int
    status: RequestStatus = RequestStatus.WAITING
    generated: int = 0
    kv_blocks: List[int] = field(default_factory=list)

    @property
    def total_tokens(self):
        return self.prompt_len + self.generated

    @property
    def done(self):
        return self.generated >= self.max_new_tokens


class BlockAllocator:
    """简化的块分配器"""

    def __init__(self, num_blocks: int):
        self.free = list(range(num_blocks))
        self.used: Dict[int, List[int]] = {}

    def allocate(self, req_id: int, num_tokens: int, block_size: int = 16):
        need = (num_tokens + block_size - 1) // block_size
        if len(self.free) < need:
            raise MemoryError("out of GPU memory")
        blocks = [self.free.pop() for _ in range(need)]
        self.used[req_id] = blocks
        return blocks

    def free_all(self, req_id: int):
        if req_id in self.used:
            self.free.extend(self.used.pop(req_id))

    def can_allocate(self, num_tokens: int, block_size: int = 16):
        need = (num_tokens + block_size - 1) // block_size
        return len(self.free) >= need


class SimpleScheduler:
    def __init__(
        self,
        max_batch: int = 8,
        max_total_tokens: int = 4096,
        num_blocks: int = 1024,
        block_size: int = 16,
    ):
        self.max_batch = max_batch
        self.max_total_tokens = max_total_tokens
        self.allocator = BlockAllocator(num_blocks)
        self.block_size = block_size
        self.waiting: List[Request] = []
        self.running: Dict[int, Request] = {}
        self.done: List[int] = []

    def submit(self, prompt_len: int, max_new_tokens: int) -> int:
        req_id = len(self.waiting) + len(self.running) + len(self.done)
        req = Request(req_id, prompt_len, max_new_tokens)
        self.waiting.append(req)
        return req_id

    def schedule_step(self) -> List[int]:
        """调度决策：决定本轮哪些请求运行"""
        # 1. 清理已完成的请求
        finished_ids = [rid for rid, r in self.running.items() if r.done]
        for rid in finished_ids:
            self.allocator.free_all(rid)
            self.done.append(rid)
            del self.running[rid]

        # 2. 尝试加入等待队列中的请求
        current_tokens = sum(r.total_tokens for r in self.running.values())
        while self.waiting and len(self.running) < self.max_batch:
            req = self.waiting[0]
            needed = req.prompt_len + req.max_new_tokens
            if (
                current_tokens + needed <= self.max_total_tokens
                and self.allocator.can_allocate(needed, self.block_size)
            ):
                self.waiting.pop(0)
                req.status = RequestStatus.RUNNING
                blocks = self.allocator.allocate(
                    req.req_id, req.prompt_len, self.block_size
                )
                req.kv_blocks = blocks
                self.running[req.req_id] = req
                current_tokens += needed
            else:
                break  # 资源不足，不再尝试

        # 3. 本轮运行的请求生成一个 token
        running_ids = list(self.running.keys())
        for rid in running_ids:
            req = self.running[rid]
            req.generated += 1

        return running_ids

    def run_until_done(self, max_steps: int = 100):
        for step in range(max_steps):
            batch = self.schedule_step()
            if not batch and not self.waiting:
                break
            # 打印调度信息
            print(f"Step {step:3d}: batch={batch}")
            if batch:
                for rid in batch:
                    r = self.running[rid]
                    print(
                        f"  → Req#{rid}: "
                        f"prompt={r.prompt_len}, "
                        f"generated={r.generated}/{r.max_new_tokens}, "
                        f"blocks={r.kv_blocks}"
                    )


# 测试运行
if __name__ == "__main__":
    scheduler = SimpleScheduler(max_batch=4, max_total_tokens=2048)

    # 模拟提交请求：短请求、中请求、长请求交错到达
    scheduler.submit(prompt_len=10, max_new_tokens=20)   # 短
    scheduler.submit(prompt_len=50, max_new_tokens=100)  # 中
    scheduler.submit(prompt_len=200, max_new_tokens=500) # 长
    scheduler.submit(prompt_len=5, max_new_tokens=10)    # 超短
    scheduler.submit(prompt_len=30, max_new_tokens=60)   # 中
    scheduler.submit(prompt_len=100, max_new_tokens=200) # 中长

    scheduler.run_until_done(max_steps=50)

    print(f"\n完成请求: {scheduler.done}")
    print(f"剩余空闲块: {len(scheduler.allocator.free)} / "
          f"{len(scheduler.allocator.free) + sum(len(v) for v in scheduler.allocator.used.values())}")
```

---

## 四、总结对比

| 引擎 | 定位 | 核心优化策略 |
|------|------|-------------|
| TVM | 通用深度学习编译器 | 图优化 + 自动调度搜索 + 代码生成 |
| vLLM | LLM 推理加速器 | PagedAttention + 连续批处理 + 高效 KV 管理 |
| TGI | 文本生成推理服务 | 动态批处理 + 规则调度 + 生产化特性 |
| Triton | 通用推理服务框架 | 模型仓库 + 并发执行 + 自定义后端 |

**性能关键路径**：
```
模型加载 → 图优化 → 内存分配 → 调度 → kernel 执行 → 结果返回
           │           │           │          │
        TVM/    vLLM KV   vLLM     cuBLAS/
       TensorRT   Cache   调度     FlashAttn
```

---

## 进一步阅读
- [TVM 论文](https://arxiv.org/abs/1802.04799) / [Ansor 论文](https://arxiv.org/abs/2006.06762)
- [vLLM 论文](https://arxiv.org/abs/2309.06180)
- [Flash Attention](https://arxiv.org/abs/2205.14135)
- [Triton Inference Server 文档](https://github.com/triton-inference-server/server)
