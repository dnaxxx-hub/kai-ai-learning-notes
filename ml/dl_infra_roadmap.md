# DL Infra 路线图：深度学习底层基础设施 8 课一览

> 涵盖从编译优化到推理加速、从训练框架到分布式并行、从算子实现到硬件调优的完整知识体系。

---

## 8 课总览

```
┌──────────────────────────────────────────────────────────────────┐
│                   深度学习底层基础设施                             │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────┐ │
│  │  01 基础架构   │  │  02 CUDA    │  │  03 cuDNN    │  │ 04  │ │
│  │  PyTorch源码  │  │  编程基础    │  │  算子库      │  │ONNX │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────┘ │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────┐ │
│  │  05 训练框架   │  │  06 内核优化  │  │  07 推理引擎  │  │ 08  │ │
│  │  DeepSpeed    │  │  算子融合  │  │  TVM/vLLM  │  │ 分布 │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────┘ │
│                                                                 │
│  趋势：← 编译优化 (静态)       运行时调度 (动态) →               │
│        ← 通用框架              垂直定制 →                       │
│        ← 单卡训练              多卡分布式 →                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 课程摘要

### [01] PyTorch 源码架构
**核心**：PyTorch 的 C++ 底层（ATen/TorchScript）与 Python 前端的分层设计
- `torch.Tensor` → ATen Tensor（引用计数 + 自动求导）
- 反向传播图的构建和动态执行
- Tensor 存储：Storage → Strides → 内存视图

### [02] CUDA 编程基础
**核心**：GPU 编程模型与 CUDA 并行计算
- Thread/Block/Grid 三层层次结构
- 共享内存与 Bank Conflict
- 常见优化：内存合并访问、warp 级别优化
- **代码**：向量加法、矩阵乘法（Tiled 版本）

### [03] cuDNN 与算子库
**核心**：NVIDIA 深度学习算子库的核心实现
- cuDNN 卷积算法选择（Winograd/FFT/implicit GEMM）
- Tensor Core 与混合精度训练 (FP16/BF16/INT8)
- cuBLAS 矩阵乘法与 cuFFT

### [04] ONNX 与模型中间表示
**核心**：模型交换格式与跨平台部署
- ONNX IR：算子集（Opset）、图结构
- ONNX Runtime：执行引擎（Eager/Graph）
- ORT 优化：Constant Folding、算子融合、量化、内存模式

### [05] 训练框架 — DeepSpeed
**核心**：大模型训练优化框架
- ZeRO 优化器（Stage 1/2/3 + offload）
- 混合精度训练（AMP/FP16）
- Gradient Checkpointing（激活重计算）
- **代码**：DeepSpeed 配置与启动

### [06] 内核优化 — 算子融合
**核心**：减少 kernel launch 开销与显存带宽消耗
- Kernel Fusion：Flash Attention 原理
- 图融合：水平（同粒度算子合并）与垂直（相邻算子合并）
- TensorRT 算子融合、TensorRT-LLM 的 XQA
- **代码**：手工融合 vs 自动融合对比

### [07] 推理引擎 — TVM & vLLM
**核心**：深度学习编译器与大模型推理加速
- TVM：Relay IR → AutoTVM/Ansor → BYOC
- vLLM：PagedAttention → KV Cache 管理 → 连续批处理
- TGI / Triton Inference Server 对比
- **代码**：简化版 vLLM 调度逻辑

### [08] 分布式训练 — DDP / FSDP / 混合并行
**核心**：多种并行策略 + 通信拓扑
- DDP：AllReduce 梯度同步 + 同步 BN
- FSDP：ZERO-3 分片 + 前向 all-gather + 反向 reduce-scatter
- 混合并行：TP + PP + DP + SP 组合
- 通信拓扑：Ring AllReduce / Rabenseifner / NCCL
- **代码**：PyTorch DDP 最小示例

---

## 进阶路径

### 路径一：算子实现与底层优化
```
基础 CUDA → cuDNN/cuBLAS → Triton DSL → 自定义 Kernel → MLIR
                                                         ↓
                                                   LLVM/PTX 代码生成
```
- 学习 [Triton](https://github.com/triton-lang/triton) 自定义算子
- 阅读 Flash Attention v2 源码
- 实现自己的 fused kernel

### 路径二：编译器与 IR
```
ONNX → Relay/TorchDynamo → XLA/HLO → MLIR → TVM → 目标代码生成
                                                 ↓
                                           TensorRT / OpenCL / Vulkan
```
- 学习 XLA (Accelerated Linear Algebra)
- 掌握 MLIR (Multi-Level IR) 的 dialect 机制
- 理解 TorchDynamo → TorchInductor 编译路径
- 深入 TVM 的 TensorIR 与调度原语

### 路径三：分布式训练工程
```
DDP → FSDP → DeepSpeed ZeRO → Megatron-LM → 3D 并行 → 自定义通信
                                                      ↓
                                              NCCL / RCCL / MPI
```
- 在 2 节点以上集群实操
- 理解 NCCL 拓扑感知算法
- 实现自己的 AllReduce 算法变体

### 路径四：推理引擎工程
```
PyTorch Eager → TorchScript → TVM → vLLM → Triton Server → Production
                                                          ↓
                                                   Serving Mesh (KServe)
```
- 部署 vLLM 线上服务
- 用 Triton Inference Server 管理多模型
- 实现自定义模型后端

### 路径五：编译器全栈
```
┌──────────────────────────────────────────────────────────────┐
│                     深度学习编译器全栈                         │
│  MLIR (dialect) → TIR → MicroTVM → TVM Runtime → Bare Metal │
└──────────────────────────────────────────────────────────────┘
```
- 边缘设备部署（MicroTVM）
- 自定义加速器代码生成
- 量化感知训练与 INT8 部署

---

## 推荐资源

**书籍**：
- 《Programming Massively Parallel Processors》— CUDA 圣经
- 《Deep Learning Systems》— 陈天奇等，深度学习系统

**论文**：
- Flash Attention (2022) / Flash Attention 2 (2023)
- vLLM: PagedAttention (2023)
- ZeRO: Memory Optimizations (2020)
- Megatron-LM (2020)
- TVM (2018) / Ansor (2020)

**实战**：
- [PyTorch Distributed Tutorials](https://pytorch.org/tutorials/intermediate/ddp_tutorial.html)
- [NVIDIA Deep Learning Examples](https://github.com/NVIDIA/DeepLearningExamples)
- [HuggingFace Optimum](https://huggingface.co/docs/optimum/index)

---

> 8 课完成了从"框架用户"到"基础设施工程师"的认知跃迁。下一步是选择一个方向深入实践，把知识转化为代码。
