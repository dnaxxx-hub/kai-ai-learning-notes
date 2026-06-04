# LLM推理优化 第10课：TensorRT-LLM 生产部署

> 学习日期：2026-05-18

## 课前回顾

前9课已涵盖：
- 1-3: KV Cache / 量化(INT8/INT4) / vLLM架构
- 4-6: 模型压缩(剪枝/蒸馏) / FlashAttention / PagedAttention
- 7-9: 推测解码 / Continuous Batching / 服务化设计

## 1. TensorRT-LLM 宏观架构

### 定位矩阵
| 方案 | 批处理 | 量化 | KV Cache | 部署形式 |
|------|--------|------|----------|----------|
| vLLM | Continuous Batching | FP16/INT4 | PagedAttention | Python包 |
| **TensorRT-LLM** | In-flight Batching | **FP8/INT4/INT8/SmoothQuant** | Multi-block | **C++ Runtime** |
| TGI | Continuous Batching | bitsandbytes | — | Rust+Python |

TensorRT-LLM = **NVIDIA 官方 LLM 推理引擎**，比 vLLM 更低延迟（C++实现，无Python GIL开销）。

### 核心优势
```
延迟:      vLLM ——▮▮▮▮▮▮▮▮▮▮ 100ms
           TRT-LLM ——▮▮▮▮▮▮▮  65ms  (-35%)

吞吐:      vLLM ——▮▮▮▮▮▮▮▮▮  3000 tok/s
           TRT-LLM ——▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮ 4800 tok/s (+60%)
```

### 架构分层

```
┌──────────────────────────────────────────┐
│           1. 模型转换层                     │
│  HuggingFace → TRT-LLM Checkpoint         │
│  (权重格式转换 + 量化应用)                   │
├──────────────────────────────────────────┤
│           2. 引擎构建层                     │
│  trtllm-build (图优化 + Kernel调优)        │
│  → .engine 文件 (平台特化二进制)            │
├──────────────────────────────────────────┤
│           3. 运行时层                       │
│  C++ Runtime + Python Binding             │
│  In-flight Batching + KV Cache管理        │
├──────────────────────────────────────────┤
│           4. 服务化层                       │
│  Triton Inference Server 集成              │
│  (HTTP/gRPC/Streaming)                    │
└──────────────────────────────────────────┘
```

## 2. 模型转换（第1层）

### 转换流程

```
HF模型 (bin/safetensors)
        │
        ▼
  量化应用 (FP8/INT4_AWQ/SmoothQuant)
        │
        ▼
  TRT-LLM Checkpoint (tllm_checkpoint/)
        │
        ▼
  trtllm-build → .engine
```

### 关键：量化方式选择

| 量化 | 精度损失 | 加速比 | GPU需求 | 推荐场景 |
|------|---------|-------|---------|---------|
| FP16 | 0% | 1x | H100 | 高精度 |
| FP8 | ~0.1% | 1.7x | H100 | ▮▮▮▮ **最佳性价比** |
| INT4_AWQ | ~1% | 2.5x | 任意 | 低显存场景 |
| INT8_SmoothQuant | ~0.3% | 1.4x | 任意 | 通用场景 |

**FP8 的魔力：**
- H100 有专用 FP8 Tensor Core（1/2 精度 = 2倍算力）
- 每token带宽减半 → 显存占用量减半
- 4× H100 可以部署 1× 70B 模型

### SmoothQuant 原理（INT8的关键）

问题：激活值有**异常大值**（outliers），直接INT8会严重损失。

```
普通INT8:  权重 W * 激活 X
            W量化: W_scale + W_zero_point
            X量化: X_scale + X_zero_point
            问题: X中有极端大值 → INT8范围不够

SmoothQuant: 用per-channel scaling把X的outlier"抹平"
            X' = X / diag(s)    ← 激活缩小
            W' = W * diag(s)    ← 权重放大（可承受）
            结果: X' 范围更小 → INT8精度几乎无损失
```

## 3. 引擎构建（第2层）

### trtllm-build 核心参数

```bash
trtllm-build \
  --checkpoint_dir ./tllm_checkpoint/ \
  --output_dir ./engine_output/ \
  --gpt_attention_plugin float16 \      # 使用GPT Attention插件
  --gemm_plugin float16 \                # GEMM插件优化
  --max_batch_size 64 \                  # 最大batch
  --max_input_len 2048 \                 # 最大输入长度
  --max_output_len 1024 \                # 最大生成长度
  --max_beam_width 4 \                   # 束搜索宽度
  --use_fused_mlp \                      # 融合MLP（减少kernel launch）
  --use_inflight_batching                 # 启用in-flight batching
```

### 图中的优化

```
原始计算图:
  LayerNorm → QKV_MatMul → Split → ... → Concat → Output
                    ↓                        ↑
              多个小kernel                 多个小kernel

优化后（kernel fusion）:
  Fused_LayerNorm_QKV → Fused_Attention → Fused_MLP → Output
  
  优势: 
  - 减少kernel launch次数 (CUDA kernel启动开销 ~5-10μs)
  - 减少中间显存读写
  - 更好的缓存局部性
```

**Fused MLP 做了什么：**
```
原始:  GELU(W1*x) → 点乘 → W2* → 输出
        ↑3个kernel  ↑带宽瓶颈  ↑1个kernel

融合:  [W1*x, W2*x_in] → 一个kernel完成全部
```

### Multi-block KV Cache

比 PagedAttention 更精细：

```
PagedAttention: 每个page = 16个token的KV块
               问题：块内碎片（padding浪费）

Multi-block: 每个block = 单个token的KV
              + 多个block组成一个logical page
              - 零碎片
              - 更灵活的内存管理
              - 适合变长序列
```

## 4. In-flight Batching 运行时（第3层）

### 对比 Continuous Batching

```
Continuous Batching (vLLM):
  [Req1] [Req2] [Req3] → 第一步全部 → 第二步全部 → ...
  问题: 新请求必须等当前iteration结束才能插入

In-flight Batching (TRT-LLM):  
  每个step都检查是否有新请求可插入
  已完成的请求立刻释放KV Cache
  → 更低的TTFT (Time To First Token)
  → 更高的GPU利用率
```

### 运行时内部

```
TrtllmRuntime:
  ├── Engine (加载.engine文件)
  ├── KVCachePool (Multi-block管理)
  ├── RequestScheduler (in-flight调度)
  └── TokenGenerator (top-k/top-p采样)

请求生命周期：
  CREATE → WAITING → IN_PROGRESS → COMPLETE
                        ↓
              每step: scheduler检查
              新请求 → WAITING → IN_PROGRESS
              完成 → 释放KV Cache → COMPLETE
```

## 5. 服务化部署（第4层）

### Triton + TensorRT-LLM 架构

```
客户端 (HTTP/gRPC)
          │ (Streaming)
          ▼
Triton Inference Server
          │
          ▼
TensorRT-LLM Backend (C++/CUDA)
          │
          ▼
GPU (H100 × 8)
```

### 部署配置示例

```yaml
# model_repository/tensorrt_llm/1/config.pbtxt
name: "tensorrt_llm"
backend: "tensorrtllm"
max_batch_size: 64
input [
  {
    name: "input_ids"
    data_type: TYPE_INT32
    dims: [-1]
  },
  {
    name: "request_output_len"
    data_type: TYPE_UINT32
    dims: [1]
  }
]
output [
  {
    name: "output_ids"
    data_type: TYPE_INT32
    dims: [-1]
  }
]
instance_group [
  {
    count: 1
    kind: KIND_GPU
  }
]
```

### 流式响应实现

```python
# 客户端代码
import tritonclient.grpc as grpcclient

with grpcclient.InferenceServerClient("localhost:8001") as client:
    result = client.infer(
        model_name="tensorrt_llm",
        inputs=[input_ids, request_len],
        outputs=[output_ids],
        headers={"ensemble": "1"}  # 流式标记
    )
    for token in result.async_stream():
        print(token, end="", flush=True)
```

## 6. 性能基准（H100×8, LLaMA-2 70B）

| 配置 | 延迟(首token) | 吞吐(tok/s) | 显存(GB) |
|------|:------------:|:-----------:|:--------:|
| FP16 (baseline) | 280ms | 1800 | 140 |
| FP8 | 165ms | 3200 | 72 |
| INT4_AWQ + SmoothQuant | 120ms | 4800 | 42 |
| INT4 + Speculative Decoding | 85ms | 6400 | 44 |
| INT4 + Spec + Distillation(-30%) | 60ms | 8200 | 32 |

## 7. 生产化注意点

### 部署架构选择

```
                    ┌─────────────┐
                    │  Load       │
                    │  Balancer   │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ TRT-LLM │    │ TRT-LLM │    │ TRT-LLM │
    │ Node 1  │    │ Node 2  │    │ Node N  │
    └──────────┘    └──────────┘    └──────────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    ┌─────────────┐
                    │  Model      │
                    │  Router     │
                    └─────────────┘
```

### 关键运维指标

| 指标 | 预警阈值 | 严重阈值 |
|------|---------|---------|
| TTFT (首token延迟) | >500ms | >2s |
| ITL (token间延迟) | >50ms | >150ms |
| GPU利用率 | <30% | — |
| KV Cache利用率 | >90% | >95% |
| OOM频率 | 0/天 | >1/天 |
| P50→P99延迟比 | >3x | >10x |

### 常见陷阱

1. **模型转换后精度差异**：FP8/INT4必须跑eval benchmark验证（MMLU/GSM8K差异<1%才算正常）
2. **batch size误判**：max_batch_setup设太大导致OOM，建议从32开始逐步提高
3. **KV Cache碎片化**：长时间运行后KV Cache碎片 → 用`--enable_kv_cache_reuse`
4. **冷启动慢**：引擎加载可能需要30s-2min，用prewarm预热

## 8. 实操：从HF到TRT-LLM全流程

```bash
# 1. 安装TRT-LLM
pip install tensorrt_llm -U

# 2. 下载HF模型
git lfs clone https://huggingface.co/meta-llama/Llama-2-7b-chat-hf

# 3. 转换checkpoint (FP8)
python convert_checkpoint.py \
  --model_dir ./Llama-2-7b-chat-hf \
  --output_dir ./tllm_checkpoint \
  --dtype float16 \
  --use_weight_only \
  --weight_only_precision int8

# 4. 构建引擎
trtllm-build \
  --checkpoint_dir ./tllm_checkpoint \
  --output_dir ./engine_output \
  --max_batch_size 32 \
  --max_input_len 1024 \
  --max_output_len 512 \
  --use_fused_mlp \
  --use_inflight_batching

# 5. 运行推理
python run.py --engine_dir ./engine_output \
  --tokenizer_dir ./Llama-2-7b-chat-hf \
  --max_output_len 256 \
  --input_text "What is GPU?"
```

## 知识图谱关联

```
┌─────────────────┐     ┌────────────────┐     ┌───────────────┐
│  LLM推理优化 #6  │────▶│  TensorRT-LLM  │◀────│ LLM推理优化 #2 │
│  FlashAttention │     │  (当前课程)     │     │  量化(INT4/8) │
└─────────────────┘     └───────┬────────┘     └───────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌────────────┐ ┌────────────┐ ┌────────────┐
        │ vLLM       │ │ 部署       │ │ 推测解码    │
        │ (#3)       │ │ (#9 服务化) │ │ (#7)       │
        └────────────┘ └────────────┘ └────────────┘
```

## 课后练习

1. **概念理解**：解释为什么FP8比INT4_AWQ精度高但INT4_+AWQ+ 推测解码组合反而延迟最低
2. **架构设计**：给定一个16GB VRAM的GPU，如何部署7B模型？列出三种方案并对比
3. **性能分析**：如果TTFT比ITL高5倍，瓶颈在哪？如何优化？

---

**学习时间**: 2026-05-18 23:00-23:15
**笔记状态**: 完成，同步到 D:\kai_knowledge\learning\
