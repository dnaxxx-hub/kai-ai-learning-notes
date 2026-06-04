# MLSys 第3课：推理优化与模型部署

> 模型训好了，怎么让它跑得快、跑得省？

---

## 1. 推理 vs 训练：核心区别

| 维度 | 训练 (Training) | 推理 (Inference) |
|------|----------------|-----------------|
| 计算流程 | 前向 + 反向 + 参数更新 | 仅前向计算 |
| 梯度 | 需要存储中间激活 | 不需要（dropout/batch_norm 冻结） |
| 延迟要求 | 吞吐优先 | 延迟敏感（特别是在线服务） |
| 精度需求 | 高精度（FP32 为主） | 可接受精度损失（INT8/FP16） |
| Batch Size | 大 batch（GPU 利用率高） | 小 batch/单条（延迟优先） |
| 显存需求 | 参数 × (3~4) + 激活 | 参数 + 少量激活（约 2× 参数） |
| 优化目标 | 训练速度 × 模型精度 | 延迟 × 吞吐 × 精度 × 功耗 |

**关键直觉：** 训练时你愿意等 1 秒得到一个 batch 的梯度；推理时用户等 100ms 就想摔手机。

---

## 2. 模型压缩

### 2.1 量化（Quantization）

核心思想：用更低精度的数据类型表示模型参数和激活值。

#### 精度阶梯

| 格式 | 位宽 | 表示范围 | 典型损耗 | 典型场景 |
|------|------|---------|---------|---------|
| FP32 | 32-bit | ±3.4×10³⁸ | - | 训练基准 |
| TF32 | 19-bit | ±3.4×10³⁸ | 几乎无损 | A100 训练 |
| FP16 | 16-bit | ±65,504 | 几乎无损 | 推理/混合精度训练 |
| BF16 | 16-bit | ±3.4×10³⁸ | 几乎无损 | 训练（Google TPU） |
| INT8 | 8-bit | [-128, 127] 或 [0, 255] | 轻微 | 推理加速 |
| INT4 | 4-bit | [-8, 7] | 较明显 | 极端压缩（LLM） |

#### FP32 → FP16 量化

```
FP32: S(1bit) E(8bit) M(23bit)  →  FP16: S(1bit) E(5bit) M(10bit)
```

- 官方硬件直接支持，**几乎零开销**
- 参数范围落入 FP16 动态范围（~±65k），**权重很少溢出**
- 精度损失通常 < 0.1% → 推荐作为**首选推理精度**

#### FP32 → INT8 量化（需要校准）

量化公式（对称量化）：

```
scale = max(|x|) / 127
x_int8 = clamp(round(x / scale), -128, 127)

反量化：
x_fp32 ≈ x_int8 × scale
```

**对称量化**：以 0 为中心对称量化（signed INT8 [-128, 127]）
- 适用于权重分布对称的情况（如经过 BN 后的激活）
- 量化范围被浪费（如果值都是正的，一半范围不用）

**非对称量化**：用 min/max 确定范围（unsigned INT8 [0, 255]）

```
scale = (max - min) / 255
zero_point = round(-min / scale)
x_int8 = clamp(round(x / scale + zero_point), 0, 255)
```

- 更灵活，适合非对称分布（如 ReLU 后的正激活）
- 多一个 zero_point 参数

#### 量化感知训练（QAT） vs 训练后量化（PTQ）

| 特性 | PTQ（Post-Training Quantization） | QAT（Quantization-Aware Training） |
|------|------|------|
| 流程 | 训练完 → 直接量化 | 训练时模拟量化误差 |
| 需要数据 | 少量校准集（几百张） | 完整训练数据 |
| 训练开销 | 无 | 额外训练（微调） |
| 精度 | 大模型损失小，小模型可能掉点 | 通常接近 FP32 精度 |
| 适用 | 大模型（>100M 参数） | 小模型/对精度要求高的场景 |

**QAT 的 Forward Pass 模拟（直通估计器 STE）：**

```
伪量化节点插入：在量化的地方插入 FakeQuantize 节点
前向：使用量化后的值计算
反向：跳过量化取整操作（假装量化不存在）
         ∂L/∂x ≈ ∂L/∂x_q     （STE 核心）
```

**核心故事：** QAT 通过 STE 让梯度"跳过取整"，让模型学会抵抗量化噪声。

#### 量化误差分析

```
误差源：
1. 截断误差：超出表示范围的值被截断 → 饱和（clipping）
2. 舍入误差：精度不足导致的值偏差 → 量化噪声

量化信噪比 SQNR ≈ 6.02 × bitwidth + constant
每减少 1 bit，SQNR 降低 ~6dB
```

---

### 2.2 剪枝（Pruning）

#### 结构化剪枝

- **操作：** 移除整个 Channel / Filter / 层
- **效果：** ⭐ **直接加速**（矩阵维度变小，FLOPs 降低）
- **硬件友好：** 普通 GEMM 库即可加速
- **方法：** 按 L1/L2 Norm 排序 → 剪掉最小的
- **典型做法：** 
  ```
  1. 对每个 filter 计算重要性分数（如 L2 范数）
  2. 按分数排序，剪掉最低的 20%
  3. 对剪枝后的模型微调恢复精度
  4. 重复步骤 2-3（Iterative Pruning）
  ```

#### 非结构化剪枝

- **操作：** 把单个权重置零（不改变矩阵形状）
- **效果：** ❌ **不直接加速**（行/列数没变）
- **需要：** 稀疏矩阵加速硬件/库（如 NVIDIA cuSPARSE）
- **稀疏比例：** 现代 LLM 可剪到 50-80% 而不显著掉精度
- **与量化叠加：** 先剪枝 → 再量化 → 可压缩 10×+

**彩票假说（Lottery Ticket Hypothesis）：**
> 一个随机初始化的网络中，存在一个"中奖子网络"（子结构），从头训练即可达到原网络性能。

---

### 2.3 知识蒸馏（Knowledge Distillation）

核心思想：利用大模型（Teacher）的知识来训练小模型（Student）。

#### 训练方式

```
Teacher（大模型）              Student（小模型）
     ↓                              ↓
  前向传播（冻结）                 前向传播
     ↓                              ↓
  Soft Label ────KL散度──→ Hard Label (Ground Truth)
  (温度 T 缩放)             
```

**Soft Label vs Hard Label：**

```
输入"猫"的图片：
Hard Label: [1.0, 0.0, 0.0]  （猫是正确答案）
Soft Label 来自 Teacher:  [0.7, 0.2, 0.1]  （猫和狗有些像，不太像鸟）

暗知识（Dark Knowledge）：Soft Label 中的"7 成是猫、2 成是狗" 
反映了 Teacher 对类间关系的理解
```

#### 带温度的 Softmax

```
q_i = exp(z_i / T) / Σ exp(z_j / T)

T = 1   → 标准 Softmax
T > 1   → 概率分布更平滑（类间关系更明显）
T → ∞   → 所有类别概率均匀
T → 0   → 趋近 One-hot
```

**训练时的高温 + 蒸馏后的常温：**
- 训练 Student 时用高 T（~4-8）软化 Teacher 输出
- 让 Student 模仿 Teacher 的**类间关系**（暗知识）
- 蒸馏后再用标准交叉熵与 hard label 组合训练

#### 蒸馏损失函数

```
L = α × KL散度(Teacher_soft || Student_soft) + (1-α) × CE(Student_hard, True_label)

其中：
- KL散度项：让 Student 输出分布接近 Teacher
- CE 项：让 Student 对真实标签有足够自信
- α：平衡系数（通常 0.5~0.9）
- 两项的 Softmax 温度 T 可以不同
```

---

## 3. 推理引擎

### 3.1 TensorRT（NVIDIA）

关键优化技术：

| 优化 | 效果 | 原理 |
|------|------|------|
| 层融合（Layer Fusion） | 减少 kernel launch 开销 | Conv+BN+ReLU → 单 kernel |
| 内核自动调优 | 选择最优 kernel | 枚举实现，选最快的 |
| INT8/FP16 量化 | 2-4× 加速 | 使用校准集 + PTQ |
| 动态 Tensor | 减少显存碎片 | 在运行时解析输入形状 |
| 内存复用 | 减少显存峰值 | 分析生命周期复用 |

**典型的 TensorRT 优化流程：**
```
ONNX 模型 → TRT Parser → 构建优化引擎 → 序列化到磁盘 → 运行时加载
```

### 3.2 ONNX Runtime

- **跨平台：** Windows / Linux / Mac / 移动端
- **多后端：** CPU（MLAS）、GPU（CUDA）、NPU、TensorRT、OpenVINO
- **图优化：** 常量折叠、算子融合、layout 优化
- **执行 provider 选择器：** 自动选最优后端

### 3.3 移动端/边缘端推理

| 引擎 | 适用平台 | 特点 |
|------|---------|------|
| TFLite | Android / 嵌入式 | Google，支持 NNAPI/GPU 委托 |
| CoreML | Apple 生态 | Apple Silicon 全面优化 |
| OpenVINO | Intel CPU/GPU/NPU | Intel 专用，CPU 推理出色 |
| NCNN | 全平台（腾讯） | 轻量级，无依赖 |

### 3.4 vLLM（LLM 专用推理引擎）

LLM 推理的独特挑战：
- **自回归解码：** 一次生成一个 token，前面的 KV cache 需要缓存
- **KV cache 显存碎片：** 不同序列长度不同，PagedAttention 解决

**PagedAttention 核心思想：**
```
类比操作系统分页：
传统：连续内存存 KV cache → 浪费（预分配太多，实际用不完）
vLLM：分页管理 KV cache → 按需分配，消除碎片
```

**连续批处理（Continuous Batching）：**
```
传统静态批处理：
等待 N 个请求凑齐 → 一整批推理 → 等待更多请求

vLLM 连续批处理：
任何时候有请求进来 → 立即加入正在运行的 batch
某个序列生成结束 → 立即腾出 slot 给新请求
```

连续批处理对比静态批处理可提升 **吞吐 2-10×**（具体取决于到达率）。

---

## 4. 服务化部署

### 4.1 推理服务架构

```
Client → Load Balancer → [ Inference Server (GPU 0) ]
                           [ Inference Server (GPU 1) ]
                           [ Inference Server (GPU 2) ]
                                                 │
                                    Model Repository (磁盘)
```

### 4.2 主流推理服务器

| 服务 | 特点 | 适用场景 |
|------|------|---------|
| Triton Inference Server | 多模型/多GPU/动态批处理/多框架 | 生产级通用部署 |
| TensorFlow Serving | TF 原生，C++ 内核 | TF 模型部署 |
| TorchServe | PyTorch 官方 | PyTorch 模型部署 |
| Ray Serve | Python 原生，弹性扩缩 | 需要复杂预处理/后处理 |

### 4.3 Triton 核心特性

**动态批处理（Dynamic Batching）：**
```
请求 1 ------------┐
请求 2 -------┐    │   ┌─────────────────┐
请求 3 ---┐   │    ├──→│  合并为一个 batch │──→ 推理
          │   │    │   └─────────────────┘
          └───┴────┘
延迟窗口(max_queue_delay)：等一会凑多个请求一起推理
```

**预热（Warm-up）：**
- 问题：首次推理（冷启动）因为 CUDA kernel 初始化 / JIT 编译，比正常慢 10×+
- 解决：服务启动时跑一次虚拟推理 → 触发所有 kernel 编译和内存分配
- `model_config.pbtxt` 中配置 `sequence_batching` / wrmer

### 4.4 生产部署考虑

```
部署检查清单：
□ 模型转换：训练格式 → 推理格式（ONNX / TRT）
□ 精度验证：INT8 推理 vs FP32 推理，输出误差 < 1%
□ 预热：启动后跑几轮虚拟推理
□ 批处理策略：延迟 vs 吞吐 平衡
□ 请求排队：最大排队长度 / 超时策略
□ GPU 内存管理：避免 OOM（多个模型共享 GPU）
□ 水平扩展：负载均衡 + 自动扩缩
□ 监控：延迟 P50/P95/P99、吞吐、错误率
□ 回滚策略：新版本出问题 → 切回旧版本
```

---

## 5. Python 推理优化模拟

配套代码：[code/mlsys_03_inference.py](./code/mlsys_03_inference.py)

### 5.1 量化模拟

```python
def quantize_symmetric(fp32_tensor):
    scale = np.max(np.abs(fp32_tensor)) / 127.0
    int8 = np.round(fp32_tensor / scale).clip(-128, 127).astype(np.int8)
    return int8, scale

def quantize_asymmetric(fp32_tensor):
    min_val, max_val = fp32_tensor.min(), fp32_tensor.max()
    scale = (max_val - min_val) / 255.0
    zero_point = np.round(-min_val / scale)
    int8 = np.round(fp32_tensor / scale + zero_point).clip(0, 255).astype(np.uint8)
    return int8, scale, zero_point
```

通过对比量化前后 FP32 vs INT8 的误差分布，理解神经网络的不同层对量化的敏感度不同（权重分布通常较对称 → 对称量化效果好；ReLU 后激活全正 → 非对称量化更好）。

### 5.2 知识蒸馏模拟

- 模拟 Teacher 的 Softmax 输出概率分布
- 用 KL 散度衡量 Student 拟合 Teacher 的程度
- 验证：温度 T 越高 → 概率分布越平滑 → 类间关系越明显

### 5.3 批处理策略对比

- **静态批处理：** 固定 batch 大小，等凑齐再推理（高延迟、高吞吐）
- **动态/连续批处理：** 随时接受请求，动态合并（低延迟、中高吞吐）
- 模拟显示：连续批处理在中等负载下减少 P50 延迟 **40-60%**

---

## 6. 总结

```
推理优化的"三板斧"：
1️⃣ 模型压缩：量化 + 剪枝 + 蒸馏 → 模型变小
2️⃣ 推理引擎：TensorRT / ONNX Runtime → 算子执行加速
3️⃣ 服务架构：动态批处理 + 多 GPU + 预热 → 系统吞吐提升

选择策略（按优先级）：
1. FP16 量化（白送，几乎无损）
2. INT8 PTQ（快，看掉点程度）
3. 结构化剪枝（直接加速，需微调）
4. 知识蒸馏（训练时做，最干净）
5. QAT（训练时做，精度最好，代价最大）
```

> **黄金法则：** 测了才知道。FP16 上评测如果延迟已经达标，就不需要 INT8。用最小改动满足 SLA 就是最好的方案。
