# DL Infra 08：分布式训练 — DDP / FSDP / 混合并行

> 课程定位：深入分布式训练的核心技术栈，从数据并行到全分片并行，覆盖主流通信原语和组合并行策略。

---

## 一、DDP (DistributedDataParallel)

### 1.1 基本原理

```
N个GPU，每个GPU有完整的模型副本 + 不同的数据分片

Worker 0    Worker 1    Worker 2    Worker 3
   │           │           │           │
   ▼           ▼           ▼           ▼
forward()   forward()   forward()   forward()
   │           │           │           │
   ▼           ▼           ▼           ▼
 backward()  backward()  backward()  backward()
   │           │           │           │
   ▼           ▼           ▼           ▼
  grad       grad        grad        grad
   │           │           │           │
   └───────────┼───────────┼───────────┘
               │ AllReduce │
               ▼           ▼
         [平均后的全局梯度]
   │           │           │           │
   ▼           ▼           ▼           ▼
 optimizer.step (所有 worker 得到相同参数)
```

### 1.2 PyTorch DDP 最小示例

```python
"""
PyTorch DDP 最小训练示例
启动方式：
    torchrun --nproc_per_node=4 train_ddp.py
"""

import os
import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader, Dataset
from torch.utils.data.distributed import DistributedSampler


def cleanup():
    dist.destroy_process_group()


class SimpleModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = torch.nn.Linear(784, 256)
        self.fc2 = torch.nn.Linear(256, 128)
        self.fc3 = torch.nn.Linear(128, 10)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.fc3(x)


def train_ddp(rank, world_size):
    """DDP 训练主函数"""
    # 1. 初始化进程组
    os.environ["MASTER_ADDR"] = "localhost"
    os.environ["MASTER_PORT"] = "29500"
    dist.init_process_group("nccl", rank=rank, world_size=world_size)

    # 2. 创建模型并放到对应 GPU
    torch.cuda.set_device(rank)
    model = SimpleModel().to(rank)
    ddp_model = DDP(model, device_ids=[rank])

    # 3. 分布式数据加载
    dataset = torch.randn(10000, 784), torch.randint(0, 10, (10000,))

    class RandomDataset(Dataset):
        def __getitem__(self, idx):
            return dataset[0][idx], dataset[1][idx]
        def __len__(self):
            return len(dataset[0])

    sampler = DistributedSampler(
        dataset, num_replicas=world_size, rank=rank, shuffle=True
    )
    dataloader = DataLoader(
        RandomDataset(), batch_size=64, sampler=sampler
    )

    # 4. 优化器
    optimizer = torch.optim.SGD(ddp_model.parameters(), lr=0.01)

    # 5. 训练循环
    for epoch in range(5):
        sampler.set_epoch(epoch)  # 确保每个 epoch 数据重新打乱
        for batch_idx, (data, target) in enumerate(dataloader):
            data, target = data.to(rank), target.to(rank)

            optimizer.zero_grad()
            output = ddp_model(data)
            loss = torch.nn.functional.cross_entropy(output, target)

            loss.backward()
            optimizer.step()

            if batch_idx % 50 == 0 and rank == 0:
                print(f"Epoch {epoch} Batch {batch_idx}: loss={loss.item():.4f}")

    cleanup()


def main():
    world_size = torch.cuda.device_count()
    print(f"Found {world_size} GPUs")
    mp.spawn(train_ddp, args=(world_size,), nprocs=world_size, join=True)


if __name__ == "__main__":
    main()
```

### 1.3 同步 BatchNorm

DDP 中 BatchNorm 需要跨 worker 同步统计量（均值和方差），否则每个 GPU 上的 BN 只看到本地 batch，小 batch 下效果差。

```python
# PyTorch 内置 SyncBatchNorm
from torch.nn import SyncBatchNorm as SBN

model = SimpleModel()
# 自动将所有 BatchNorm 替换为 SyncBatchNorm
model = SBN.convert_sync_batchnorm(model)
ddp_model = DDP(model.to(rank), device_ids=[rank])

# 或者在模型中直接使用
class MyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = torch.nn.Conv2d(3, 64, 3)
        self.bn = SBN(64)  # 会自动跨 rank 同步
```

### 1.4 梯度累积 (Gradient Accumulation)

在 batch 较小或 GPU 显存不足时使用。本质是用时间换空间。

```python
# 梯度累积：模拟更大的 batch size
accumulation_steps = 4  # 实际 batch_size = per_gpu_batch × accumulation_steps

optimizer.zero_grad()
for i, (data, target) in enumerate(dataloader):
    output = ddp_model(data)
    loss = criterion(output, target) / accumulation_steps
    loss.backward()

    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()
```

**⚠️ 注意**：DDP 中每个 backward() 后都会自动触发梯度同步。梯度累积时，`no_sync` 上下文可避免中间的同步开销：

```python
# 只在最后一个 micro batch 做梯度同步
for i, (data, target) in enumerate(dataloader):
    if (i + 1) % accumulation_steps == 0:
        # 正常 backward → 触发梯度 all-reduce
        output = ddp_model(data)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
    else:
        # 不触发梯度同步
        with ddp_model.no_sync():
            output = ddp_model(data)
            loss.backward()
```

---

## 二、FSDP (Fully Sharded Data Parallel)

### 2.1 核心思想

FSDP = ZERO-3（参数、梯度、优化器状态全分片）的数据并行：

```
                        GPU 0        GPU 1        GPU 2        GPU 3
                        ┌─────┐      ┌─────┐      ┌─────┐      ┌─────┐
 参数分片 (FP16)         │W0   │      │W1   │      │W2   │      │W3   │
                        │W4   │      │W5   │      │W6   │      │W7   │
                        └─────┘      └─────┘      └─────┘      └─────┘
                           │            │            │            │
                         all-gather  all-gather  all-gather  all-gather
                           │            │            │            │
 前向传播 (FP32)        ┌─────┐      ┌─────┐      ┌─────┐      ┌─────┐
                         │W0..Wn     │W0..Wn     │W0..Wn     │W0..Wn
                         └─────┘      └─────┘      └─────┘      └─────┘
                           │            │            │            │
                         reduce-scatter（反向传播后只保留本地分片梯度）
                           │            │            │            │
                         optimizer.step()（每个GPU只更新自己的分片）
```

### 2.2 FSDP 配置策略

```python
from torch.distributed.fsdp import (
    FullyShardedDataParallel as FSDP,
    ShardingStrategy,
    MixedPrecision,
    BackwardPrefetch,
    CPUOffload,
)
from torch.distributed.fsdp.wrap import (
    transformer_auto_wrap_policy,
    size_based_auto_wrap_policy,
)

# 分片策略
sharding_strategies = {
    "NO_SHARD": ShardingStrategy.NO_SHARD,           # 等于 DDP
    "SHARD_GRAD_OP": ShardingStrategy.SHARD_GRAD_OP,  # ZERO-2
    "FULL_SHARD": ShardingStrategy.FULL_SHARD,         # ZERO-3（默认）
    "HYBRID_SHARD": ShardingStrategy.HYBRID_SHARD,     # FSDP + DDP 混合
}

# 混合精度
mp_policy = MixedPrecision(
    param_dtype=torch.float16,       # 参数存储用 FP16
    reduce_dtype=torch.float16,      # reduce 用 FP16
    buffer_dtype=torch.float32,      # buffer 用 FP32
)

# CPU offload
cpu_offload = CPUOffload(offload_params=True)  # 参数卸载到 CPU

# Wrap 策略
# 方式1：基于大小
auto_wrap_policy = size_based_auto_wrap_policy(min_num_params=1e8)

# 方式2：基于 Transformer 层
auto_wrap_policy = partial(
    transformer_auto_wrap_policy,
    transformer_layer_cls={TransformerBlock},
)

# 实际配置
model = FSDP(
    model,
    sharding_strategy=ShardingStrategy.FULL_SHARD,
    mixed_precision=mp_policy,
    backward_prefetch=BackwardPrefetch.BACKWARD_PRE,
    device_id=torch.cuda.current_device(),
)
```

### 2.3 FSDP 训练循环

```python
fsdp_model = FSDP(model, ...)
optimizer = torch.optim.AdamW(fsdp_model.parameters(), lr=1e-4)

for epoch in range(num_epochs):
    for batch in dataloader:
        # FSDP 自动处理：
        # 前向：all-gather 恢复完整参数
        # 后向：reduce-scatter 分发梯度
        # 优化：每个 GPU 只更新自己的参数分片
        outputs = fsdp_model(batch["input_ids"])
        loss = criterion(outputs, batch["labels"])

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # FSDP 状态分片保存
        if rank == 0 and step % save_interval:
            dist.barrier()
            states = FSDP.state_dict(fsdp_model)
            torch.save(states, f"checkpoint_{step}.pt")
            dist.barrier()
```

---

## 三、混合并行 (Hybrid Parallelism)

### 3.1 四种并行维度

```
                    ┌──────────────────────────────┐
                    │         数据并行 (DP)          │
                    │  不同 GPU 处理不同数据样本       │
                    │  通信：AllReduce 梯度           │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │       张量并行 (TP)            │
                    │  一个算子切分到多个 GPU         │
                    │  通信：AllReduce 激活/梯度      │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │      流水线并行 (PP)           │
                    │  不同层在不同 GPU，微批次流水    │
                    │  通信：P2P 激活/梯度传输        │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │         序列并行 (SP)          │
                    │  长序列切分到多个 GPU           │
                    │  通信：Ring Attention           │
                    └──────────────────────────────┘
```

### 3.2 组合策略（以 LLM 训练为例）

```
使用 64 个 GPU 训练 175B 模型：

GPU 拓扑 (8节点 × 8GPU):
┌─────────────────────────────────────────┐
│ 节点内 (NVLink)       节点间 (RDMA)       │
│ GPU0 ─ GPU1 ─ GPU2 ─ GPU3               │
│   │       │      │      │               │
│ GPU4 ─ GPU5 ─ GPU6 ─ GPU7               │
└─────────────────────────────────────────┘

推荐组合：TP=8（节点内 NVLink） + PP=4 + DP=2
总 GPU：8 × 4 × 2 = 64 ✓

内存分布：
GPU0:  [Layer0]  [Layer4]  [Layer8]    → 流水线第0段
GPU8:  [Layer1]  [Layer5]  [Layer9]    → 流水线第1段
GPU16: [Layer2]  [Layer6]  [Layer10]   → 流水线第2段
GPU24: [Layer3]  [Layer7]  [Layer11]   → 流水线第3段

每个流水线段内：TP=8（一层切成8份，8个GPU协同计算）
不同流水线段间：PP，传递激活值
DP=2：2个流水线副本，独立处理不同数据
```

### 3.3 实现方式

```python
# PyTorch 分布式 + Megatron-LM 风格组合

# 1. 设置分布式组
tp_group = dist.new_group(ranks=[0, 1, 2, 3, 4, 5, 6, 7])      # 张量并行组
pp_group = dist.new_group(ranks=[0, 8, 16, 24])                # 流水线并行组
dp_group = dist.new_group(ranks=[0, 32])                        # 数据并行组

# 2. 张量并行：行/列切分线性层
class ColumnParallelLinear(torch.nn.Module):
    """列并行线性层"""
    def __init__(self, in_features, out_features, tp_group):
        super().__init__()
        world_size = tp_group.size()
        self.tp_group = tp_group
        self.out_features_per_rank = out_features // world_size
        self.weight = torch.nn.Parameter(
            torch.randn(self.out_features_per_rank, in_features)
        )

    def forward(self, x):
        # 每个GPU只计算自己分到的列
        output = torch.mm(x, self.weight.t())
        return output

class RowParallelLinear(torch.nn.Module):
    """行并行线性层 + AllReduce"""
    def __init__(self, in_features, out_features, tp_group):
        super().__init__()
        world_size = tp_group.size()
        self.tp_group = tp_group
        self.in_features_per_rank = in_features // world_size
        self.weight = torch.nn.Parameter(
            torch.randn(out_features, self.in_features_per_rank)
        )

    def forward(self, x):
        # 本地计算
        local_out = torch.mm(x, self.weight.t())
        # 跨 TP group AllReduce 汇总
        torch.distributed.all_reduce(local_out, group=self.tp_group)
        return local_out

# 3. 流水线并行：微批次调度
class PipelineParallel:
    """1F1B 调度策略"""
    def __init__(self, num_microbatches=4):
        self.num_microbatches = num_microbatches

    def schedule_1f1b(self, microbatches):
        """
        1F1B (One-Forward-One-Backward) 调度
        减少流水线气泡
        """
        stages = len(microbatches[0])  # 流水线段数
        num_mb = len(microbatches)

        # 预热阶段：前几个 micro batch 只 forward
        warmup = min(num_mb, stages - 1)

        # 稳定阶段：1F1B 交替
        for mb_idx in range(num_mb):
            for stage in range(stages):
                if mb_idx < warmup:
                    # 预热：只 forward
                    microbatches[mb_idx][stage].forward()
                else:
                    # 稳定：1 forward + 1 backward
                    microbatches[mb_idx][stage].forward()
                    microbatches[mb_idx - warmup][stage].backward()

        # 收尾：剩余的 backward
        for mb_idx in range(num_mb - warmup, num_mb):
            for stage in range(stages):
                microbatches[mb_idx][stage].backward()
```

---

## 四、通信拓扑

### 4.1 Ring AllReduce

最常用的梯度同步算法，通信量 = 2(N-1)/N × 数据量，接近线性扩展。

```
步骤1：Scatter-Reduce
┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐
│GPU0 │────→│GPU1 │────→│GPU2 │────→│GPU3 │
│g[0] │     │g[0] │     │g[0] │     │g[0] │
│g[1] │     │g[1] │     │g[1] │     │g[1] │
│g[2] │     │g[2] │     │g[2] │     │g[2] │
│g[3] │     │g[3] │     │g[3] │     │g[3] │
└─────┘     └─────┘     └─────┘     └─────┘
 每个 GPU 发送一个分片给下一个 GPU，接收后累加

步骤2：AllGather
┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐
│GPU0 │←────│GPU1 │←────│GPU2 │←────│GPU3 │
│g_sum0│    │g_sum1│    │g_sum2│    │g_sum3│
└─────┘     └─────┘     └─────┘     └─────┘
 每个 GPU 将聚合好的分片广播给所有 GPU
```

```python
# 简化版 Ring AllReduce 实现
def ring_allreduce(tensor, rank, world_size):
    """NCCL Ring AllReduce 的 Python 模拟"""
    chunks = list(tensor.chunk(world_size))
    send_buf = chunks[rank].clone()
    recv_buf = torch.zeros_like(send_buf)

    # Scatter-Reduce 阶段
    for step in range(world_size - 1):
        send_rank = (rank - step) % world_size
        recv_rank = (rank + step + 1) % world_size
        send_chunk = chunks[send_rank]

        # 模拟发送/接收（实际用 NCCL）
        recv_buf.copy_(send_chunk)
        chunks[recv_rank] += recv_buf

    # AllGather 阶段
    for step in range(world_size - 1):
        send_rank = (rank - step - 1) % world_size
        recv_rank = (rank + step + 1) % world_size

        # 模拟循环广播
        chunks[recv_rank].copy_(chunks[recv_rank])

    # 合并回原始 tensor
    tensor.copy_(torch.cat(chunks))

# 通信量分析：
# Scatter-Reduce: (N-1) × data_size/N × 2 次传输
# AllGather: (N-1) × data_size/N × 2 次传输
# 总计：4(N-1)/N × data_size ≈ 4× data_size（N 大时）
```

### 4.2 Rabenseifner 算法

用于 Hierarchical AllReduce（节点内 + 节点间）：

```
节点内 (NVLink, 快速):
  ┌────────────┐    ┌────────────┐
  │ Node0 GPU0 │ ←→ │ Node1 GPU0 │
  │ Node0 GPU1 │ ←→ │ Node1 GPU1 │
  │ Node0 GPU2 │ ←→ │ Node1 GPU2 │
  │ Node0 GPU3 │ ←→ │ Node1 GPU3 │
  └────────────┘    └────────────┘
    ↑ NVLink            ↑ NVLink

节点间 (RDMA, 较慢):
  ┌────────────┐    ┌────────────┐
  │ Node0      │ ──→ │ Node1      │
  │ 归约到GPU0 │     │ 广播到所有 │
  └────────────┘    └────────────┘

算法步骤：
1. 每个节点内 Reduce-Scatter（节点内 NVLink，快速）
2. 节点间 AllReduce（节点间 RDMA，少量数据）
3. 每个节点内 AllGather（节点内 NVLink，快速）
```

### 4.3 NCCL (NVIDIA Collective Communication Library)

**关键特性**：
- **拓扑感知**：自动检测 NVLink / PCIe / InfiniBand 拓扑
- **算法选择**：根据消息大小自动选择 AllReduce 算法
  - 小消息：Ring（延迟优化）
  - 大消息：Tree（带宽优化）
- **通信计算重叠**：支持 `ncclGroupStart/End` 分组
- **P2P + 集合通信**混合

```python
# NCCL 环境变量调优
os.environ["NCCL_DEBUG"] = "INFO"           # 调试信息
os.environ["NCCL_IB_DISABLE"] = "0"         # 启用 InfiniBand
os.environ["NCCL_NET_GDR_LEVEL"] = "5"      # GPUDirect RDMA
os.environ["NCCL_SOCKET_IFNAME"] = "eth0"   # 指定网卡
os.environ["NCCL_MIN_NCHANNELS"] = "4"      # 通信通道数

# 观测 NCCL 通信
os.environ["NCCL_DEBUG_SUBSYS"] = "INIT,COLL,GRAPH"
# 会输出：拓扑发现 → 算法选择 → 连接建立 → 数据传输
```

---

## 五、总结对比

| 策略 | 参数 | 梯度 | 优化器状态 | 通信量 | 显存节省 |
|------|------|------|-----------|--------|---------|
| DDP | 完全复制 | AllReduce | 完全复制 | 2×参数大小 | 0% |
| ZERO-1 | 完全复制 | AllReduce | 分片 | 2×参数大小 | ~30% |
| ZERO-2 | 完全复制 | 分片后 reduce | 分片 | 2×参数大小 | ~60% |
| ZERO-3 (FSDP) | 分片 | 分片后 reduce | 分片 | 3×参数大小 | ~75% |

**工程建议**：
1. 模型 < 1B：DDP 就够
2. 1B - 10B：FSDP (ZERO-2/3)
3. 10B - 100B：TP(8) + PP + DP/FSDP
4. 100B+：3D 并行 + 其他优化（序列并行、激活重计算）

---

## 进一步阅读
- [PyTorch DDP 文档](https://pytorch.org/docs/stable/notes/ddp.html)
- [FSDP 论文](https://arxiv.org/abs/2304.11277)
- [Megatron-LM](https://arxiv.org/abs/1909.08053)
- [NCCL 文档](https://docs.nvidia.com/deeplearning/nccl/)
- [Ring AllReduce 论文](https://arxiv.org/abs/1705.04569)
