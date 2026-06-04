# LLM 推理优化 #9：TensorRT-LLM & 生产级部署优化

> 学习笔记 — 从编译优化到生产级服务架构的全链路实践
> 日期：2026-05-13 | 笔记编号：llm_infer_09
> 前置知识：PagedAttention（llm_infer_07）、Speculative Decoding（llm_infer_08）、分布式推理（llm_infer_06）、量化（llm_infer_02）

---

## 0. 引论：生产级推理的工程全景

前面的课程聚焦于单点优化技术：KV Cache管理、量化、推测解码、高效Attention。生产级部署需要把它们有机组合成一个完整的服务系统。

```
┌─────────────────────────────────────────────────────────────────────┐
│                        生产级 LLM 服务系统                            │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │编译优化  │  │推理引擎  │  │服务调度   │  │运维监控          │    │
│  │TRT-LLM  │  │vLLM/     │  │请求队列  │  │吞吐量/延迟监控    │    │
│  │ONNX RT  │  │TRT引擎   │  │负载均衡  │  │自动扩缩容        │    │
│  │内核融合 │  │GPU Kernels│  │速率限制  │  │故障转移          │    │
│  │量化编译 │  │显存管理  │  │缓存策略  │  │模型热加载        │    │
│  └─────────┘  └──────────┘  └──────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## 1. TensorRT-LLM 架构

### 1.1 编译流程：Torch → ONNX → TRT Engine

TensorRT-LLM 的核心竞争力在于**编译期优化**：把 PyTorch 模型静态编译成针对特定 GPU 高度优化的 engine 文件。

```
PyTorch Model → ONNX Graph → TensorRT Builder → TRT Engine (.engine)
  (动态图)       (静态图)       (编译优化)        (二进制)
```

**Builder的核心优化：**
| 优化技术 | 说明 | 加速效果 |
|---------|------|---------|
| 图优化 | 删除无用identity/reshape，合并相邻算子 | 5-15% |
| 算子融合 | 多个小kernel融合为一个大kernel | 20-50% |
| 内核自动调优 | 为每个算子尝试多种kernel实现，选最快 | 10-30% |
| 精度校准 | FP16/INT8/FP8量化插入 | 2-4x |
| 内存规划 | 静态分析tensor lifetime，显存重用 | -30%显存 |
| CUDA Graph生成 | 封装为CUDA Graph减少launch开销 | 5-20% |

**关键设计**：TensorRT engine是**硬件特定**的。H100编译的engine不能在A100上运行。

### 1.2 Plugin 机制

TensorRT-LLM 通过 Plugin 系统注入 LLM 专用高性能 kernel：
- **FlashAttention Plugin**：单kernel替代Reshape→Transpose→MatMul→Softmax→MatMul链
- **PagedAttention Plugin (v0.9+)**：引入block table，支持prefix caching
- **GQA Plugin**：Grouped Query Attention的KV head广播优化
- **Fused MoE Plugin**：路由+专家计算的算子融合
- **Quantization Plugin**：FP8/INT4 GEMM集成
- **FullyFusedLayerNorm Plugin**：单kernel LayerNorm（从7次显存往返到2次）

### 1.3 Weight Streaming（权重流式加载）

当模型大到无法放入单GPU显存，权重不常驻显存，而是每层计算前从CPU流式加载：
- 每层约500MB（70B模型），PCIe Gen5 x16约8ms传输
- 计算耗时>传输耗时则完全隐藏延迟
- 适用于FP8/INT4模型或多模型共享GPU场景

### 1.4 In-flight Batching（飞行批处理）

与vLLM的Continuous Batching本质相同，但TRT-LLM实现更底层：
- **静态batch上限**：编译时确定 max_batch_size
- **动态shape profile**：多个序列长度组合的最优配置
- **每次iteration**：重新选择profile + execute

对比vLLM：TRT-LLM batch上限编译时确定（灵活性差但kernel更优）；vLLM运行时动态（灵活但kernel非极致优化）。

## 2. ONNX Runtime 优化

### 2.1 图优化三级
- L0 Basic：常量折叠、冗余消除、shape推理 (5-10%)
- L1 Extended：算子融合(Gelu/LayerNorm融合) (15-25%)
- L2 Layout：NHWC布局优化 (10-20%)

### 2.2 量化支持
- **Dynamic Quantization**：运行时统计min/max，无需校准数据，权重INT8+激活FP32，1.5-2x加速
- **Static Quantization**：需校准数据，权重+激活都INT8，2-3x加速
- **QAT**：训练感知量化，精度恢复最好

### 2.3 ORT + TensorRT Execution Provider
ORT中调用TensorRT编译推理，一条pipeline覆盖训练到部署：
```python
session = ort.InferenceSession(
    "model.onnx", sess_options,
    providers=[("TensorrtExecutionProvider", trt_options),
               "CUDAExecutionProvider"]
)
```

## 3. GPU 推理核心技术

### 3.1 CUDA Graph

将一系列kernel launch捕获成有向无环图，**一次提交**给GPU：
- 普通方式：逐个launch（每次~3-20us CPU开销），Llama 70B decode约500+次kernel launch
- CUDA Graph：捕获→实例化→重复重放（单次API调用，零CPU开销）
- LLM decode特别适合：每个step的kernel DAG完全一致
- 实际收益：kernel launch减少80%，单请求decode延迟降低15-30%

CUDA Graph限制：
- ❌不支持的条件分支、动态memory alloc
- ⚠️ 静态batch size和序列长度，动态需要多graph pool

### 3.2 内核融合

CUDA Graph减少CPU launch开销；内核融合减少GPU显存带宽。
- **"一次读入，多次使用"**：如SwiGLU融合（线性→激活→线性合并为单kernel，3x带宽节省）
- **FlashAttention**本身就是融合kernel

### 3.3 内存优化
- **Unified Memory**：CPU/GPU统一寻址，page fault自动迁移（延迟不可预测，生产很少用）
- **CUDA IPC**：跨进程直接共享GPU显存（Prefill-Decode分离场景关键）
- **显存池化**：避免热点路径cudaMalloc/cudaFree，生产中任一malloc在热点路径都是bug

## 4. 延迟优化策略

### 4.1 TP vs PP 对比
| 维度 | Pipeline Parallelism (PP) | Tensor Parallelism (TP) |
|------|-------------------------|------------------------|
| 切分维度 | 按层切分（垂直） | 按张量切分（水平） |
| 通信量 | 单次张量 | 每层2次all-reduce |
| 带宽依赖 | 容忍PCIe，跨机可行 | 强依赖NVLink |
| 延迟影响 | 增加首token延迟 | 减少单步延迟 |

**常见组合（4xA100 80GB）**：
- 单机70B：TP=4, PP=1
- 两机70B：TP=4, PP=2（机内TP，机间PP）
- 四机405B：TP=8, PP=4

**70B模型单步decode延迟剖面**（pp=1, tp=4, A100）：
RMSNorm 2% → QKV 10% → RoPE 3% → Attention 27% → PostNorm 2% → FFN 23% → AllReduce 13% → Kernel Launch 17%

→ **CUDA Graph可消除17%的launch开销**

### 4.2 Dynamic Batching 的三大阶段
1. **Planning Phase**（CPU，us级）：检查运行/等待队列，分配prefill time-slice，确定KV显存
2. **Execution Phase**（GPU，ms级）：打包batch，执行forward，写入KV block
3. **Post-processing Phase**（CPU，us级）：detokenize、EOS检查、更新状态

### 4.3 Chunked Prefill
核心矛盾：prefill（计算密集）和decode（访存密集）的算力需求差异巨大（1000x）。

解决方案：将长prefill切成多个micro-batch，穿插在decode iteration中执行，避免decode请求等待。

## 5. 生产部署架构

### 5.1 服务框架选择
| 框架 | 优势 | 劣势 | 适合场景 |
|------|------|------|---------|
| **vLLM + FastAPI** | 部署简单，社区活跃 | 缺少高级调度 | 中小规模原型到生产 |
| **Triton Inference Server** | 多模型/多后端/GPU管理 | 配置复杂 | 企业级多模型服务 |
| **TGI** | HuggingFace生态，开箱即用 | 灵活性最低 | 快速验证/轻量服务 |

### 5.2 关键指标监控
- **TTFT** (Time To First Token)：prefill阶段，理想<200ms
- **TPOT** (Time Per Output Token)：decode阶段，理想<30ms
- **ITL** (Inter-Token Latency)：相邻token间隔，用户体验核心
- **吞吐量**：tokens/second or requests/second

### 5.3 全链路部署架构
```
客户端 → LB(Nginx) → API Gateway(FastAPI) → 请求队列(RabbitMQ/Redis)
    → 调度器(vLLM/TRT-LLM) → GPU集群 → 响应流
                                                     → Prometheus → Grafana
```

## 6. 与之前课程的配合

- **PagedAttention**（#7）：TRT-LLM v0.9+已集成，vLLM核心特性
- **Speculative Decoding**（#8）：生产部署可开启，2-3x加速
- **量化**（#2）：TRT-LLM原生支持，编译期校准更优
- **FlashAttention**（#5）：作为TRT plugin集成
- **分布式推理**（#6）：TP + PP组合的工程决策

## 7. 动手实验 IDea

### 实验1：vLLM本地部署
```bash
pip install vllm
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching
```
观察：TTFT/TPOT/吞吐量，对比开关prefix caching的显存差异。

### 实验2：生产部署性能基准
用vLLM benchmark工具测试不同batch size下的吞吐和延迟曲线：
```bash
python -m vllm.benchmarks.benchmark_throughput \
  --model Qwen/Qwen2.5-7B-Instruct \
  --num-prompts 1000 \
  --input-len 512 --output-len 128
```

## 8. 总结

生产级LLM推理是从单点优化到系统工程的全链路实践：
1. **编译优化**（TensorRT-LLM）提供最优kernel
2. **调度策略**（Continuous Batching + Chunked Prefill）最大化吞吐
3. **GPU优化**（CUDA Graph + Kernel Fusion）榨干硬件性能
4. **生产架构**（服务框架+监控+容错）保障可靠性

所有之前学的技术在这个架构中都有自己位置，组合起来才能实现真正的生产级部署。

## 参考资料
- [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM)
- [vLLM Architecture](https://docs.vllm.ai/en/latest/design/arch_overview/)
- [Triton Inference Server](https://github.com/triton-inference-server/server)
- CUDA Graph: [Getting Started with CUDA Graphs](https://developer.nvidia.com/blog/cuda-graphs/)
- [ONNX Runtime](https://onnxruntime.ai/)
