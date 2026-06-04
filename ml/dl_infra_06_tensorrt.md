# 课时6：TensorRT——NVIDIA 推理优化引擎

## 概述

TensorRT 是 NVIDIA 的深度学习推理优化引擎，专为生产环境部署设计。它将训练好的模型转化为高度优化的推理引擎，通过量化、层融合、核函数自动调优等技术，在保持精度的前提下大幅提升推理吞吐量、降低延迟。本课深入 TensorRT 的几项核心技术。

## 核心概念

### 1. FP16 与 INT8 量化

**量化**是将高精度浮点数值映射到低位宽表示的过程。FP16（半精度）和 INT8（8位整型）是最常用的两种量化精度。

**量化数学原理**：

$$Q(r) = \text{round}(\frac{r}{\Delta}) + Z$$

其中 r 是原始浮点值，Δ 是缩放因子（scale），Z 是零点偏移（zero-point）。反量化公式：

$$r \approx \Delta \cdot (Q(r) - Z)$$

```python
class QuantizationEngine:
    """
    TensorRT 量化的概念实现。
    支持 FP16 和 INT8 两种精度。
    """
    def __init__(self, calibration_dataset=None):
        self.calib_dataset = calibration_dataset
        self.scales = {}   # tensor_name → scale factor
        self.zero_pts = {} # tensor_name → zero point
    
    def calibrate_int8(self, model, representative_data):
        """
        INT8 校准：从代表性数据中收集每层激活值的分布，
        计算最优的 scale 和 zero-point。
        """
        # 常见的校准方法：
        # 1. Max (最大值校准)：scale = max(abs(tensor)) / 127
        # 2. Entropy (KL散度校准)：最小化量化前后分布的 KL 散度
        # 3. Percentile (百分位数校准)：忽略极端 outliers
        method = 'entropy'  # TensorRT 默认使用 KL 散度
        
        for name, activation in self._collect_activations(model, representative_data):
            if method == 'max':
                # 最简单的校准
                max_abs = np.max(np.abs(activation))
                self.scales[name] = max_abs / 127.0
                self.zero_pts[name] = 128  # 对称量化的零点是 128
                
            elif method == 'entropy':
                # KL 散度校准：找到使信息损失最小化的阈值
                best_threshold = self._kl_divergence_calibration(activation)
                self.scales[name] = best_threshold / 127.0
                self.zero_pts[name] = 128
            
            elif method == 'percentile':
                # 忽略 0.01% 的极端值
                p99_9 = np.percentile(np.abs(activation), 99.9)
                self.scales[name] = p99_9 / 127.0
                self.zero_pts[name] = 128
    
    def _kl_divergence_calibration(self, activations, num_bins=2048):
        """
        KL 散度校准的简化实现。
        参考：TensorRT 的 calibration 算法。
        """
        # 1. 创建直方图
        max_val = np.max(np.abs(activations))
        hist, bin_edges = np.histogram(np.abs(activations), 
                                        bins=num_bins, 
                                        range=(0, max_val))
        
        # 2. 从每个可能的阈值计算 KL 散度
        best_kl = float('inf')
        best_threshold = max_val
        
        for threshold_idx in range(128, num_bins + 1):
            threshold = bin_edges[threshold_idx]
            
            # 截断直方图
            truncated_hist = hist[:threshold_idx].copy()
            
            # 将截断部分累计到最后一个 bin
            truncated_hist[-1] += np.sum(hist[threshold_idx:])
            
            # 量化到 128 个 bin (INT8 正半轴) 再反量化回参考分布
            # （这是简化的，实际 TensorRT 会在量化空间上操作）
            
            # 计算量化后的分布
            quantized_bins = np.linspace(0, threshold, 128)
            quantized_hist = np.zeros(128)
            bin_width = threshold / threshold_idx
            
            for i in range(threshold_idx):
                quantized_idx = min(127, int(i * bin_width / (threshold / 128)))
                quantized_hist[quantized_idx] += truncated_hist[i]
            
            # 标准化
            truncated_hist = truncated_hist / truncated_hist.sum()
            quantized_hist = quantized_hist / quantized_hist.sum()
            
            # 计算 KL 散度
            kl_div = np.sum(truncated_hist * 
                            np.log(truncated_hist / (quantized_hist[:threshold_idx] + 1e-10) + 1e-10))
            
            if kl_div < best_kl:
                best_kl = kl_div
                best_threshold = threshold
        
        return best_threshold
    
    def quantize_tensor(self, name, float_tensor):
        """将浮点张量量化为 INT8"""
        scale = self.scales.get(name)
        zero_pt = self.zero_pts.get(name, 128)
        
        if scale is None:
            return float_tensor  # 未校准的层跳过量化
        
        # 量化：Q = round(r / scale) + zero_pt
        quantized = np.round(float_tensor / scale) + zero_pt
        quantized = np.clip(quantized, 0, 255).astype(np.uint8)
        return quantized
    
    def dequantize_tensor(self, name, quantized_tensor):
        """将 INT8 张量反量化为浮点"""
        scale = self.scales.get(name)
        zero_pt = self.zero_pts.get(name, 128)
        
        if scale is None:
            return quantized_tensor.astype(np.float32)
        
        # 反量化：r ≈ (Q - zero_pt) * scale
        return (quantized_tensor.astype(np.float32) - zero_pt) * scale
    
    def fp16_quantization(self, float_tensor):
        """FP16 量化（直接类型转换）"""
        return float_tensor.astype(np.float16)

# TensorRT 在实际使用时的精度选择
# builder = trt.Builder(network)
# config = builder.create_builder_config()
# 
# # FP16 推理
# config.set_flag(trt.BuilderFlag.FP16)
# 
# # INT8 推理（需要校准数据）
# config.set_flag(trt.BuilderFlag.INT8)
# config.int8_calibrator = MyCalibrator(calibration_data)
```

### 2. 层融合（Layer Fusion）

**层融合**是 TensorRT 优化的基石。TensorRT 解析模型图后，识别出可融合的层模式，将其合并为单个 CUDA kernel，大幅减少核函数启动开销和中间内存带宽消耗。

```python
class TensorRTFusionEngine:
    """
    TensorRT 层融合的模式匹配引擎。
    实际 TensorRT 内部有数十种融合模式。
    """
    def __init__(self, network):
        self.network = network
    
    def fuse_all(self):
        """应用所有可能的融合变换"""
        self.fuse_conv_bn_relu()
        self.fuse_conv_bias_relu()
        self.fuse_gemm_bias()
        self.fuse_scale()
        self.fuse_reshape_slice()
        self.fuse_elementwise()
        return self.network
    
    def fuse_conv_bn_relu(self):
        """
        融合 Conv + BatchNorm + ReLU 为单层。
        这是最常见的模式之一。
        
        数学原理：
        BN(x) = γ * (x - μ) / σ + β
        
        当 x = Conv(w, input) + b 时：
        BN(Conv(input)) = γ * (Conv(w, input) + b - μ) / σ + β
                      = Conv(γ*w/σ, input) + γ*(b-μ)/σ + β
        
        可以看到 BN 的参数可以"吸收"到 Conv 的权重和偏置中，
        从而消除 BN 的计算。
        """
        for layer in self.network.layers:
            if self._is_bn_relu_pattern(layer):
                conv = layer.inputs[0].layer
                bn = layer
                # 吸收 BN 参数到 Conv
                fused_w = self._fuse_bn_into_conv_weight(conv, bn)
                fused_b = self._fuse_bn_into_conv_bias(conv, bn)
                
                # 替换为融合层
                fused_layer = self._create_fused_layer(
                    "CBR", conv, fused_w, fused_b, has_relu=True)
                self.network.replace_subnet([conv, bn], fused_layer)
    
    def fuse_gemm_bias(self):
        """
        融合 GEMM(矩阵乘) + Bias Add 为单层。
        GEMM 是 Fully Connected / Linear 层的核心。
        """
        for layer in self.network.layers:
            if layer.type == "ElementWise" and layer.op == "SUM":
                if layer.inputs[0].layer.type == "MatrixMultiply":
                    matmul = layer.inputs[0].layer
                    bias = layer.inputs[1]
                    
                    # 创建融合的 GEMM+Bias
                    fused = self._create_fused_gemm(
                        matmul.inputs[0],  # activation
                        matmul.inputs[1],  # weight
                        bias,
                        matmul.attributes
                    )
                    self.network.replace_layer(layer, fused)
    
    def fuse_elementwise(self):
        """
        融合连续的逐元素操作。
        如：x + y → relu(x+y) 或 x → tanh(x) → mul(x, sigmoid(x)) (GELU)
        """
        for layer in self.network.layers:
            # GELU 融合：x * 0.5 * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
            if self._is_gelu_pattern(layer):
                fused_gelu = self._create_fused_gelu(layer.inputs[0])
                self.network.replace_subnet(
                    self._get_gelu_subgraph(layer), fused_gelu)
    
    def _is_bn_relu_pattern(self, layer):
        """检测 Conv + BN + ReLU 模式"""
        if layer.type != "ReLU":
            return False
        if not layer.inputs or not layer.inputs[0].layer:
            return False
        bn = layer.inputs[0].layer
        if bn.type != "Scale" or bn.op not in ("BATCH_NORM", "LAYER_NORM"):
            return False
        if not bn.inputs or not bn.inputs[0].layer:
            return False
        return bn.inputs[0].layer.type in ("Convolution", "Deconvolution")
```

**TensorRT 融合的层次**：

| 融合级别 | 示例 | 效果 |
|---------|------|------|
| 垂直融合 | Conv + BN + ReLU | 减少 2 次 kernel 启动，消除中间张量 |
| 水平融合 | 多个相同操作 | 合并 batch 处理，提升吞吐量 |
| 跨连接融合 | 残差连接 | 消除元素加法后的单独 kernel |
| 激活函数融合 | GELU、Swish | 避免额外 kernel 启动 |

### 3. 动态 Shape 优化

**动态 Shape** 指输入张量的某些维度在运行时才能确定（如变长序列的 batch size 和 sequence length）。TensorRT 的优化引擎在构建时使用"优化配置文件"来覆盖输入尺寸范围。

```python
class DynamicShapeOptimizer:
    """
    TensorRT 动态 Shape 优化的概念实现。
    """
    def __init__(self):
        self.optimization_profiles = []
    
    def add_optimization_profile(self, name, input_name,
                                   min_shape, opt_shape, max_shape):
        """
        添加优化配置文件。
        TensorRT 会对 opt_shape 进行最深入的 tiling 优化，
        min 和 max 定义了可接受的边界。
        """
        profile = {
            'name': name,
            'input': input_name,
            'min': min_shape,
            'opt': opt_shape,
            'max': max_shape,
        }
        self.optimization_profiles.append(profile)
    
    def auto_generate_profiles(self, model, dataset_stats):
        """
        从训练数据统计中自动生成优化配置文件。
        """
        # 对序列模型（如 NLP），统计长度分布
        seq_lengths = dataset_stats.get('sequence_lengths', [])
        
        if seq_lengths:
            profiles = []
            # 常见策略：为小、中、大三种典型尺寸各生成一个 profile
            profile_configs = [
                ("small", np.percentile(seq_lengths, 10)),
                ("medium", np.percentile(seq_lengths, 50)),
                ("large", np.percentile(seq_lengths, 95)),
            ]
            
            for name, opt_len in profile_configs:
                min_len = int(np.min(seq_lengths))
                max_len = int(np.max(seq_lengths))
                
                self.add_optimization_profile(
                    name, "input_ids",
                    min_shape=(1, min_len),   # batch=1, 最小长度
                    opt_shape=(8, int(opt_len)), # 对齐到 8 的倍数
                    max_shape=(64, max_len)    # 最大 batch=64
                )
        
        return self.optimization_profiles

# TensorRT 中动态 shape 的使用
# builder_config.add_optimization_profile(profile)
# engine = builder.build_serialized_network(network, builder_config)
# 
# # 推理时设置实际输入尺寸
# context.set_binding_shape(0, (actual_batch, actual_seq_len))
# context.execute_v2([input_buffer, output_buffer])
```

### 4. DLA（深度学习加速器）集成

**DLA（Deep Learning Accelerator）** 是 NVIDIA Xavier、Orin 等嵌入式平台上的硬件加速器。TensorRT 可以将推断卸载到 DLA 上，以更低的功耗执行推理。

```python
class DLAIntegration:
    """
    DLA 加速器集成的概念。
    """
    def __init__(self, use_dla_core=0):
        self.use_dla = True
        self.dla_core = use_dla_core  # 0 或 1 (双核 DLA)
        self.supported_ops = {
            'conv2d', 'relu', 'add', 'mul', 'concat',
            'max_pool', 'avg_pool', 'fully_connected',
        }
    
    def can_offload_to_dla(self, layer):
        """检查层是否能卸载到 DLA"""
        if not self.use_dla:
            return False
        
        # DLA 限制
        # 1. 仅支持 FP16 和 INT8（不支持 FP32）
        # 2. 卷积核大小限制（通常 ≤ 7x7）
        # 3. 张量大小和维度限制
        if layer.precision not in ('FP16', 'INT8'):
            return False
        if layer.type not in self.supported_ops:
            return False
        
        return True
    
    def partition_graph(self, network):
        """
        将网络分割为 GPU 和 DLA 两部分。
        """
        gpu_parts = []
        dla_parts = []
        current_part = []
        current_device = 'GPU'
        
        for layer in network.layers:
            if self.can_offload_to_dla(layer):
                if current_device == 'DLA':
                    current_part.append(layer)
                else:
                    # 切换到 DLA，保存之前的 GPU 部分
                    if current_part:
                        gpu_parts.append(current_part)
                    current_part = [layer]
                    current_device = 'DLA'
            else:
                if current_device == 'GPU':
                    current_part.append(layer)
                else:
                    if current_part:
                        dla_parts.append(current_part)
                    current_part = [layer]
                    current_device = 'GPU'
        
        # 保存最后一段
        if current_device == 'DLA':
            dla_parts.append(current_part)
        else:
            gpu_parts.append(current_part)
        
        return gpu_parts, dla_parts
```

### 5. 多流推理

**多流推理（Multi-Stream Inference）** 是最大化 GPU 利用率的策略。通过创建多个 CUDA Stream，同时执行多个推理请求的解码阶段，提高吞吐量。

```python
class MultiStreamInferenceEngine:
    """
    TensorRT 多流推理的概念实现。
    适用于在线服务场景。
    """
    def __init__(self, engine, num_streams=4, max_batch=32):
        self.engine = engine
        self.num_streams = num_streams
        self.max_batch = max_batch
        self.contexts = []
        self.streams = []
        self.request_queue = []
        
        # 创建多个执行上下文和流
        for i in range(num_streams):
            ctx = engine.create_execution_context()
            stream = CUDAStream(priority=0)
            self.contexts.append(ctx)
            self.streams.append(stream)
    
    def submit_request(self, input_data, batch_size=1):
        """提交推理请求"""
        self.request_queue.append({
            'input': input_data,
            'batch': batch_size,
        })
        self._schedule()
    
    def _schedule(self):
        """调度挂起的请求到空闲流"""
        while self.request_queue:
            # 查找空闲的流
            free_stream = self._find_free_stream()
            if free_stream is None:
                break  # 所有流正忙
            
            request = self.request_queue.pop(0)
            self._execute_on_stream(request, free_stream)
    
    def _execute_on_stream(self, request, stream_idx):
        """
        在指定流上异步执行推理。
        
        多流并发执行时：
        流0: [Kernel A]----[Kernel C]----[Kernel E]
        流1: ----[Kernel B]----[Kernel D]----[Kernel F]
        
        GPU 可以在两个流的 kernel 之间快速切换，
        充分利用 SM 的空闲周期。
        """
        ctx = self.contexts[stream_idx]
        stream = self.streams[stream_idx]
        
        # 设置动态 shape（如果需要）
        # ctx.set_binding_shape(0, (request['batch'], ...))
        
        # 异步执行（立即返回）
        stream.submit(ctx.execute_v2, 
                       [request['input'], output_buffer])
    
    def _find_free_stream(self):
        """查找已完成的流"""
        for i, stream in enumerate(self.streams):
            if stream.is_completed():
                return i
        return None
    
    def throughput_analysis(self):
        """分析多流吞吐量"""
        # 理想情况：N 个流，吞吐量 ≈ N 倍（计算完全并行）
        # 实际受限于 GPU 资源（SM 数量、内存带宽）
        # 经验法则：SM 利用率在 80%+ 时增加流的效果递减
        
        # GPU 占满时停止增加流
        return {
            'num_cores': 80,  # A100: 108 SM
            'suggested_streams': min(self.num_streams, 
                                     108 * 2),  # 每个 SM 最多 2 个流
        }
```

## 实用技巧

### TensorRT 部署流水线

```python
def tensorrt_deployment_pipeline(onnx_model_path, calibration_data=None):
    """
    完整的 TensorRT 模型优化和部署流水线。
    """
    import tensorrt as trt
    
    # 阶段1：创建构建器
    logger = trt.Logger(trt.Logger.INFO)
    builder = trt.Builder(logger)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, logger)
    
    # 解析 ONNX
    with open(onnx_model_path, 'rb') as f:
        parser.parse(f.read())
    
    # 阶段2：配置优化选项
    config = builder.create_builder_config()
    
    # 设置工作空间大小（显存预算）
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 4 * 1024 * 1024 * 1024)  # 4GB
    
    # 启用 FP16
    if builder.platform_has_fast_fp16:
        config.set_flag(trt.BuilderFlag.FP16)
    
    # 启用 INT8（需要校准数据）
    if calibration_data is not None and builder.platform_has_fast_int8:
        config.set_flag(trt.BuilderFlag.INT8)
        config.int8_calibrator = MyCalibrator(calibration_data)
    
    # 阶段3：添加优化配置文件（动态 shape）
    profile = builder.create_optimization_profile()
    profile.set_shape("input", (1, 3, 224, 224), (8, 3, 224, 224), (32, 3, 224, 224))
    config.add_optimization_profile(profile)
    
    # 阶段4：构建序列化引擎
    serialized_engine = builder.build_serialized_network(network, config)
    with open("model.trt", "wb") as f:
        f.write(serialized_engine)
    
    return "model.trt"
```

###使用 Nsight 分析 TensorRT Kernel

```bash
# 使用 nsys 和 ncu 分析 TensorRT 推理
# nsys profile -o trt_trace -t cuda,nvtx python inference.py
# ncu --set full -o trt_kernel python inference.py
```

## 延伸阅读

- [TensorRT Developer Guide](https://docs.nvidia.com/deeplearning/tensorrt/developer-guide/)
- [INT8 Quantization in TensorRT - Algorithm and Accuracy Analysis](https://on-demand.gputechconf.com/gtc/2020/presentations/s21478-int8-quantization-in-tensorrt.pdf)
- [DLA (Deep Learning Accelerator) Overview](https://docs.nvidia.com/deeplearning/tensorrt/developer-guide/index.html#dla_topic)

## 关键总结

1. **FP16/INT8 量化** 通过 KL 散度校准找到最优 scale，显著降低模型尺寸和推理延迟
2. **层融合** 自动识别并合并 Conv+BN+ReLU 等常见子图模式，减少 kernel 启动
3. **动态 Shape** 通过优化配置文件支持变长输入，为 opt_shape 做深度 tiling 优化
4. **DLA** 在嵌入式平台上提供低功耗推理支持，仅限 FP16/INT8
5. **多流推理** 利用 CUDA Stream 并发执行多个推理请求，最大化 GPU 利用率
6. **TensorRT 的核心价值**：精度无损或可控损失的推理性能倍增
