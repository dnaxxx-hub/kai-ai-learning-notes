# 分布式机器学习训练学习笔记

## 1. 为什么要分布式训练？

### 模型太大
- GPT-3 (175B)、LLaMA-2 (70B) 等大模型远超单卡显存上限（H100 80GB）
- 单卡连模型参数都装不下，必须拆分到多卡

### 数据太多
- ImageNet (1.2M 张)、LAION-5B (50 亿图文对) 等大规模数据集
- 单机训练一个 epoch 需要数天甚至数周
- 分布式训练通过数据并行将 batch 拆分到 N 个 worker，吞吐量近线性提升

### 加速收敛
- 更大的 batch size → 梯度估计更稳定 → 更快收敛
- 分布式训练支持更大的全局 batch size（如 GPT-3 使用 3.2M 的 batch size）

---

## 2. 并行策略

### 数据并行 (Data Parallelism)
```
每个 worker 持有完整模型副本 + 部分数据
前向/反向独立计算 → 梯度汇聚 → 更新全局参数
```
- **优点**: 实现简单，吞吐量高
- **缺点**: 模型太大装不下时无效
- **代表**: PyTorch DDP, Horovod

### 模型并行 (Model Parallelism)
```
模型的不同层拆分到不同设备
数据流水线式通过各设备
```
- **优点**: 突破单卡显存限制
- **缺点**: 存在串行瓶颈，设备利用率可能不高

### 流水线并行 (Pipeline Parallelism)
```
模型按层切分成多个 stage
每个 stage 放在不同设备上
micro-batch 流水线式执行（如 GPipe、PipeDream）
```
关键概念：通过将 micro-batch 流水线化来隐藏设备间的等待时间。
- 空泡率 = (P-1) / (M*P-1+P-1)，P=stage 数，M=micro-batch 数
- M 越大，空泡率越低，但需要更多内存存中间激活值

### 张量并行 (Tensor Parallelism)
```
将单个层（如 attention、FFN）的矩阵运算拆分到多卡
常见策略：列切分、行切分、2D/3D 切分
```
- **代表**: Megatron-LM 的 1D 张量并行

### 混合并行
大模型训练通常组合多种策略：
```
3D 并行 = 数据并行 + 流水线并行 + 张量并行
```
- GPT-3 训练配置：数据并行 64 路 + 流水线并行 8 路 + 张量并行 8 路
- 共 64 × 8 × 8 = 4096 个 GPU

---

## 3. 同步训练 vs 异步训练

### 同步训练 (Sync SGD)
```
每个 step:
  1. 所有 worker 拉取相同参数
  2. 各自计算梯度
  3. 梯度汇聚（All-Reduce 或 Submit to PS）
  4. 等所有 worker 完成 → 更新参数
  5. 同步到所有 worker
```
- **优点**: 梯度一致，收敛稳定，数学性质与单机 SGD 一致
- **缺点**: 受最慢 worker 拖累（straggler 问题）

### 异步训练 (Async SGD)
```
每个 step:
  1. Worker 拉取参数（可能已过期）
  2. 计算梯度
  3. 立刻推送梯度更新（不等其他 worker）
  4. PS 收到后立即更新参数（可能有 stale gradient 问题）
```
- **优点**: 无 straggler 问题，吞吐量高
- **缺点**: 梯度陈旧（stale gradient），收敛可能不稳定

### 折中方案
- **Stale Synchronous Parallel (SSP)**: 允许一定程度的异步，但控制最大 staleness
- **Gradient Accumulation**: 本地累积多个 step 再同步，减少通信频率

---

## 4. Parameter Server 架构 (PS 架构)

### 架构图
```
                     +-----------+
                     |  PS Node  |  (多个 PS shard)
                     +-----+-----+
                           |
         +--------+--------+--------+--------+
         |        |        |        |        |
      +----+   +----+   +----+   +----+   +----+
      | W1 |   | W2 |   | W3 |   | W4 |   | W5 |  (Worker 节点)
      +----+   +----+   +----+   +----+   +----+
```

### 核心思想
- **参数分离**: 参数存储 (PS) 和计算 (Worker) 解耦
- **Worker 职责**: 持有数据分片，计算梯度
- **PS 职责**: 存储全局参数，接收梯度，更新参数

### 通信角色
- **Push**: Worker 向 PS 发送梯度
- **Pull**: Worker 从 PS 拉取最新参数

### 扩展性
- 大规模时 PS 本身可分区（多个 PS shard），每个负责一部分参数
- Worker 只与相关 PS shard 通信

### 优缺点
| 优点 | 缺点 |
|------|------|
| 实现直观，Worker 可异构 | PS 可能成为瓶颈 |
| 支持异步训练自然 | 通信负载不对称（PS 收多路） |
| 容错相对简单 | 不适合全规约操作 |

---

## 5. All-Reduce 架构

### 什么是 All-Reduce？
所有节点初始持有自己的梯度张量，All-Reduce 让每个节点最终得到所有梯度的和（平均）。

### Ring All-Reduce

```
节点组成环状拓扑：
   N0 → N1 → N2 → N3 → N0
```

**Phase 1: Scatter-Reduce**（N-1 步）

假设 N=4 个节点，每个节点将张量拆成 4 块：
```
Step 1: N0 发 chunk1→N1, N1 发 chunk2→N2, N2 发 chunk3→N3, N3 发 chunk0→N0
Step 2: N0 发 chunk0→N1, N1 发 chunk1→N2, N2 发 chunk2→N3, N3 发 chunk3→N0
Step 3: N0 发 chunk3→N1, N1 发 chunk0→N2, N2 发 chunk1→N3, N3 发 chunk2→N0
```
每步交换一块并累加。3 步后，每个节点有完整的一块规约结果。

**Phase 2: All-Gather**（N-1 步）

将规约结果广播给所有节点。同样是 N-1 步循环传递。

**关键性质**:
- 总通信量：2(N-1)/N × 数据量 ≈ 2× 数据量（N 大时）
- 每个节点发送/接收量相等，带宽利用率高
- 适合 NVLink/NVSwitch 等高速互联

### Tree All-Reduce
- 将节点按二叉树/蝶状拓扑组织
- 理论上 O(log N) 步完成，但实际中 Ring All-Reduce 更常用

### NCCL (NVIDIA Collective Communication Library)
- 底层通过 NCCL 实现 All-Reduce
- NCCL 会根据硬件拓扑选择最优算法（Ring / Tree / NVLink Direct）

---

## 6. 梯度压缩与通信优化

### 梯度压缩
| 方法 | 压缩比 | 精度损失 |
|------|--------|---------|
| **梯度裁剪 + 稀疏化** (Top-K) | 100-1000x | 可控 |
| **梯度量化** (FP32→FP16/INT8) | 2-4x | 低 |
| **随机梯度压缩** (QSGD) | 可变 | 有界误差 |
| **梯度累积** / **梯度延迟** | N/A | 近似 |

### 通信拓扑优化
- **分层 All-Reduce**: 同一机架内先归约（NVLink），机架间再归约（IB/RoCE）
- **通信与计算重叠**: 反向传播时同时启动梯度通信（bucket all-reduce）
- **梯度分桶** (Gradient Bucketing): 将多个小梯度合并为一个包发送，减少小消息延迟

### PyTorch DDP 的通信优化
```
反向传播时注册 hook:
  gradient ready → 放入 bucket
  bucket 满 → 启动异步 All-Reduce
  下一个 layer 继续反向 → 通信与计算重叠
```

---

## 7. 容错机制

### 检查点 (Checkpoint)
- **完整检查点**: 保存模型权重 + optimizer state + 训练 epoch/step
- **分布式检查点**: 保存分片权重（各 rank 只保存自己负责的部分）
- **频率**: 每隔 N 步或每 epoch 保存一次

### 弹性训练 (Elastic Training)
- 允许 worker 动态加入/离开
- **动态重分配**: Worker 变化后触发新的 `torch.distributed.init_process_group`
- **State Dict 重新分片**: 根据新 world size 重新分布 shard

### 故障检测
- 心跳超时检测
- PS 架构中：Worker 可重连，拉取最新参数继续训练
- All-Reduce 架构中：故障即停机，需配合检查点恢复

---

## 8. 主流框架对比

| 特性 | PyTorch DDP | Horovod | DeepSpeed | Megatron-LM |
|------|-------------|---------|------------|-------------|
| **并行策略** | 数据并行 | 数据并行 | 混合并行 | 混合并行 |
| **默认后端** | NCCL/GLOO | NCCL/MPI | NCCL | NCCL |
| **通信算法** | Gradient Bucket All-Reduce | Ring All-Reduce (NCCL) | ZeRO 优化 + All-Reduce | 张量并行 + 流水线并行 |
| **显存优化** | 无 | 无 | ZeRO-1/2/3, Offload | 激活重计算 |
| **易用性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **大模型支持** | 受限 | 受限 | 极好 | 好 |
| **混合精度** | torch.cuda.amp | 内置 | 内置 | Megatron-LM AMP |
| **社区** | PyTorch 生态 | 独立开源 | Microsoft | NVIDIA |

### 各框架的核心定位
- **PyTorch DDP**: 分布式训练的标准入口，简单可靠
- **Horovod**: 跨框架（TF/PyTorch/MXNet），Ring All-Reduce 先驱
- **DeepSpeed**: 微软出品，ZeRO 显存优化 + 3D 并行
- **Megatron-LM**: NVIDIA 出品，专注超大模型的张量 + 流水线并行

### ZeRO 优化三个级别
```
ZeRO-1: 优化器状态分片 (≈4x 显存节省)
ZeRO-2: + 梯度分片 (≈8x)
ZeRO-3: + 参数分片 (≈64x, 可在训练时按需加载参数)
```

---

## 9. 混合精度训练 (FP16/BF16)

### 为什么要用混合精度？
- FP16: 显存减半，计算提速 2-8x（Tensors Cores）
- BF16: 更大指数位，不易溢出，适合大模型训练

### 常用策略
```
权重: FP32 主副本 (master weights)
前向/反向: FP16/BF16
梯度: FP16/BF16 计算，FP32 累积
优化器: FP32
```

### Loss Scaling
- FP16 梯度容易下溢（接近 0）
- 对 loss 乘以 scale 因子（如 2^16），反向后再除以 scale

### Automatic Mixed Precision (AMP)
```
三个级别:
- 'O0': FP32 全部
- 'O1': 半自动（推荐，自动选择 FP16 算子）
- 'O2': 几乎全部 FP16
- 'O3': 全部 FP16（不推荐，可能不稳定）
```

---

## 10. 总结: 如何选择并行策略？

```
模型能放进单卡？
  ├── 数据量大？ → 数据并行 (DDP)
  └── 数据量小？ → 单卡即可
  
模型超单卡显存？
  ├── 模型层数深？ → 流水线并行
  ├── 模型单层大？ → 张量并行
  └── 都大？ → 3D 并行

训练不稳定？
  ├── 梯度爆炸？ → 梯度裁剪 + 混合精度
  └── 通信慢？ → 梯度压缩 + 通信重叠
```

---

## 参考资源
- [PyTorch Distributed Tutorial](https://pytorch.org/tutorials/intermediate/ddp_tutorial.html)
- [DeepSpeed Documentation](https://www.deepspeed.ai/)
- [Megatron-LM Paper](https://arxiv.org/abs/1909.08053)
- [Ring All-Reduce Paper (Baidu)](https://arxiv.org/abs/1706.02677)
- [ZeRO Paper](https://arxiv.org/abs/1910.02054)
- [GPipe Paper](https://arxiv.org/abs/1811.06965)
