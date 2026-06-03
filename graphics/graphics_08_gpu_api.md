# 第8课：图形API概念与渲染实战

## 1. OpenGL / Vulkan / DirectX / Metal 对比

### 1.1 四大图形API概览

| API | 开发者 | 平台 | 首次发布 | 当前版本 | 特点 |
|-----|--------|------|---------|---------|------|
| **OpenGL** | Khronos | 跨平台（Win/Lin/Mac） | 1992 | 4.6 (2017) | 经典、易学、状态机 |
| **OpenGL ES** | Khronos | 移动/嵌入式 | 2003 | 3.2 | OpenGL子集，面向移动 |
| **Vulkan** | Khronos | 跨平台 | 2016 | 1.3 | 高性能、显式控制 |
| **DirectX 12** | Microsoft | Windows/Xbox | 2015 | 12 | Windows原生、低开销 |
| **DirectX 11** | Microsoft | Windows/Xbox | 2009 | 11.4 | 平衡、普及度高 |
| **Metal** | Apple | iOS/macOS | 2014 | 3 | Apple原生、高效 |

### 1.2 OpenGL（1992-2017）：经典的标准

**历史地位：**
- 最广泛教授的图形API
- 从固定管线→可编程管线的见证者
- OpenGL 2.0（2004）引入着色器 → 3.0+ 全面可编程

**特点：**
- **状态机架构**：大量全局状态（glEnable/glDisable）
- **隐式资源管理**：驱动程序决定GPU内存管理
- **同步相对简单**：API内置同步点

**局限性：**
- 多线程支持差
- CPU开销大（状态验证、错误检查）
- 驱动承担过多优化责任

```cpp
// OpenGL 典型代码（简化）
glUseProgram(shader);
glBindVertexArray(VAO);
glBindTexture(GL_TEXTURE_2D, texture);
glUniformMatrix4fv(modelLoc, 1, GL_FALSE, &model[0][0]);
glDrawElements(GL_TRIANGLES, count, GL_UNSIGNED_INT, 0);
```

### 1.3 Vulkan（2016-至今）：下一代高性能API

**设计哲学：**
- **显式控制**：开发者全权管理GPU资源
- **低CPU开销**：减少驱动层的隐式工作
- **多线程友好**：并行命令缓冲构建

**核心概念：**

| Vulkan概念 | 类比 | 说明 |
|-----------|------|------|
| Instance | 应用 | 一个Vulkan应用 |
| Physical Device | GPU硬件 | 系统中的GPU |
| Logical Device | GPU逻辑接口 | 应用程序与GPU的交互通道 |
| Queue | 命令队列 | 提交命令到GPU的通道 |
| Command Buffer | GPU指令列表 | 预录制的GPU指令批次 |
| Pipeline | 着色器管线 | 完整的可编程管线配置 |
| Descriptor Set | 绑定资源集合 | 纹理/缓冲/采样器的绑定组 |
| Fence/Semaphore | 同步原语 | CPU↔GPU/GPU↔GPU同步 |

```cpp
// Vulkan 典型代码模式（极度简化）
// 1. 创建实例 → 2. 选择物理设备 → 3. 创建逻辑设备
// 4. 创建交换链 → 5. 创建渲染pass → 6. 创建管线
// 7. 创建帧缓冲 → 8. 录制命令缓冲 → 9. 提交队列

// 录制命令缓冲
vkBeginCommandBuffer(cmdBuf, ...);
vkCmdBeginRenderPass(cmdBuf, ...);
vkCmdBindPipeline(cmdBuf, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
vkCmdBindVertexBuffers(cmdBuf, 0, 1, &vertexBuffer, &offsets);
vkCmdDraw(cmdBuf, vertexCount, 1, 0, 0);
vkCmdEndRenderPass(cmdBuf);
vkEndCommandBuffer(cmdBuf);

// 提交队列
VkSubmitInfo submit = { .commandBufferCount = 1, .pCommandBuffers = &cmdBuf };
vkQueueSubmit(queue, 1, &submit, fence);
```

**Vulkan管线状态对象（PSO）：**

现代Vulkan将管线视为不可变对象，创建时确定所有状态：

```
VkGraphicsPipelineCreateInfo
  ├── VkPipelineShaderStageCreateInfo[]  (VS, FS, GS, TC, TE)
  ├── VkPipelineVertexInputStateCreateInfo  (顶点布局)
  ├── VkPipelineInputAssemblyStateCreateInfo (图元类型)
  ├── VkPipelineRasterizationStateCreateInfo (光栅化)
  ├── VkPipelineMultisampleStateCreateInfo   (MSAA)
  ├── VkPipelineDepthStencilStateCreateInfo  (深度/模板)
  └── VkPipelineColorBlendStateCreateInfo    (颜色混合)
```

### 1.4 DirectX 12（2015-至今）：Windows原生

**特点：**
- 类似Vulkan的低开销、显式控制设计
- 与Windows生态深度集成（VS Graphics Debugger、PIX）
- **管线状态对象（PSO）**：类似Vulkan的不可变管线
- 使用**根签名（Root Signature）**管理资源绑定

**DirectX 11**（2009）相比之下更接近OpenGL：
- 隐式资源管理
- 较高的驱动CPU开销
- 但普及度高，文档丰富

### 1.5 Metal（2014-至今）：Apple生态

**特点：**
- 苹果统一图形/计算API（macOS + iOS）
- 低CPU开销，类似Vulkan
- Objective-C/Swift原生语法
- 不支持跨平台

```swift
// Metal 典型代码（简化）
let commandBuffer = commandQueue.makeCommandBuffer()!
let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: passDesc)!
encoder.setRenderPipelineState(pipelineState)
encoder.setVertexBuffer(vertexBuffer, offset: 0, index: 0)
encoder.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: count)
encoder.endEncoding()
commandBuffer.commit()
```

### 1.6 API选择指南

| 场景 | 推荐API |
|------|---------|
| 跨平台教学/原型 | OpenGL 3.3+ |
| 跨平台游戏/高性能 | Vulkan |
| Windows独占游戏 | DirectX 12 |
| 移动端（Android） | Vulkan / OpenGL ES 3.2 |
| Apple生态（iOS/macOS） | Metal |
| 快速原型/工具 | OpenGL |
| 新一代引擎（Unreal 5） | Vulkan / DX12 / Metal |

## 2. 现代渲染架构

### 2.1 Frame Graph / Render Graph

**是什么：**
- Frame Graph是渲染框架的**任务调度系统**
- 将渲染流程建模为**有向无环图（DAG）**
- 节点 = 渲染Pass，边 = 资源依赖

**传统渲染方式（过程式）：**

```
// 过程式：Pass顺序硬编码，资源难复用
renderShadowMap();        // Pass 1
renderGBuffer();          // Pass 2
renderLighting();         // Pass 3
renderSSAO();             // Pass 4
renderBloom();            // Pass 5
renderPostProcess();      // Pass 6
```

**Frame Graph方式（声明式）：**

```
// FrameGraph：自动分析依赖、优化资源
FrameGraph fg;
auto shadow = fg.addPass("ShadowMap", ...);
auto gbuffer = fg.addPass("GBuffer", ...)
    .read(shadow)
    .output("gPosition",  AttachmentType::RenderTarget)
    .output("gNormal",    AttachmentType::RenderTarget)
    .output("gAlbedo",    AttachmentType::RenderTarget);

auto lighting = fg.addPass("Lighting", ...)
    .read(gbuffer, "gPosition")
    .read(gbuffer, "gNormal")
    .read(gbuffer, "gAlbedo")
    .output("hdrColor", AttachmentType::RenderTarget);

auto bloom = fg.addPass("Bloom", ...)
    .read(lighting, "hdrColor")
    .output("bloomResult", AttachmentType::RenderTarget);

auto composite = fg.addPass("Composite", ...)  // 最终合成
    .read(lighting, "hdrColor")
    .read(bloom, "bloomResult");
```

**Frame Graph的优势：**

| 优势 | 说明 |
|------|------|
| **资源管理自动优化** | 自动计算资源生命周期，复用临时纹理 |
| **Pass依赖自动管理** | 自动插入Barrier/Sync，保证正确性 |
| **Pass裁剪** | 自动跳过没有消费者的Pass |
| **多后端兼容** | 同一Frame Graph描述可生成Vulkan/DX12/Metal命令 |
| **调试可视化** | 直观查看渲染流程 |

**引擎中的Frame Graph实现：**
- **Unreal Engine**：RDG（Rendering Dependency Graph）
- **Frostbite (EA)**：Frame Graph
- **Granite (The Forge)**：Render Graph
- **自定义实现**：小型引擎也可实现轻量Frame Graph

### 2.2 Deferred Shading vs Forward Shading

#### Forward Shading（前向着色）

```
几何 → 顶点着色 → 光栅化 → 片段着色(光照) → 输出
                             └── 每个片元对所有光源计算
```

**过程：** 在每个几何体通过管线时，同时计算所有光照

**优点：**
- 简单，易于实现
- 支持透明物体（每个物体独立）
- 支持MSAA抗锯齿

**缺点：**
- N个物体 × M个光源 = 大量重复计算
- 光源数量上升时性能急剧下降
- 复杂光照场景效率低

#### Deferred Shading（延迟着色）

```
Pass 1 (GBuffer Pass):
几何 → 顶点着色器 → 光栅化 → GBuffer片段着色器
                               ├── gPosition: 世界坐标
                               ├── gNormal:   法线
                               ├── gAlbedo:   颜色
                               └── gMetallicRoughAO: 材质属性

Pass 2 (Lighting Pass):
全屏四边形 → 片段着色器 → 读取GBuffer → 计算光照 → 输出
                      └── 每个像素读取GBuffer的G-buffer
```

**优点：**
- 光照计算与几何复杂度解耦
- 光源数量对性能影响较小（O(像素数 × 光源数)）
- 渲染大量动态光源时效率高

**缺点：**
- 不支持透明物体（需要Forward Pass配合）
- GBuffer内存开销大（4~8张全屏纹理）
- 难以实现MSAA

#### TBDR（Tile-Based Deferred Rendering）

延迟着色的优化版本，将屏幕分块（Tile）：

```
1. GBuffer Pass：写入颜色/法线/深度
2. Tile分类：将屏幕分16×16或32×32块
3. Light Culling：对每个Tile，找出影响该Tile的光源
4. Lighting Pass：每个Tile只计算该Tile内的光源
```

**优势：** 大幅减少光源计算量，尤其适合屏幕空间局部光照

#### 对比总结

| 对比 | Forward | Deferred | TBDR |
|------|---------|----------|------|
| 光源数量 | < 8个 | 数百个 | 数十~数百个 |
| 透明物体 | ✅ 原生支持 | ❌ 需额外Pass | ❌ 需额外Pass |
| MSAA | ✅ 简单 | ❌ 复杂 | ❌ 复杂 |
| 内存消耗 | 低 | 高（GBuffer） | 中 |
| 移动端性能 | 优 | 差 | 中（TBDR native） |
| 实现复杂度 | 低 | 高 | 高 |

### 2.3 混合渲染架构（Hybrid Rendering）

现代游戏引擎通常采用混合方案：

```
几何 Pass (Forward/Deferred):
  ├── 不透明物体 → 延迟着色（Deferred）
  ├── 透明物体   → 前向着色（Forward）
  └── 天空盒     → 独立Pass

光照 Pass:
  ├── 直接光照：Deferred Lighting
  ├── 阴影：Shadow Map Passes
  └── 间接光照：SSAO / GI

后处理 Pass:
  ├── HDR Tone Mapping
  ├── Bloom
  ├── SSAO
  └── TAA / FSR / DLSS
```

## 3. 实时渲染技术前沿

### 3.1 光线追踪（Ray Tracing）

#### 传统光栅化 VS 光线追踪

```
光栅化（Rasterization）：  光线追踪（Ray Tracing）：
  像素 ← 三角形（反向）      像素 → 场景（正向）
  每个像素遍历三角形         每个像素发射光线
  适合：直接可见性         适合：反射/折射/阴影
  效率：O(像素 × 三角形)     效率：O(像素 × 光线交叉)
```

#### 实时光线追踪架构（RTX / DXR）

NVIDIA RTX（2018）和DirectX Raytracing（DXR）将光线追踪引入实时渲染：

```
加速结构（BVH / Bounding Volume Hierarchy）：
                          根节点
                        /         \
                    内部节点     内部节点
                    /    \       /    \
                  叶子    叶子  叶子   叶子
                三角1   三角2 三角3  三角4

光线追踪管线：
Ray Generation Shader  →  Miss Shader
     ↓
  Any Hit Shader
     ↓
  Closest Hit Shader (计算交点颜色/材质)
```

**实时光线追踪的典型用途：**

| 用途 | 描述 | 传统替代 | 质量提升 |
|------|------|---------|---------|
| 反射 | 光滑表面反射场景 | 屏幕空间反射(SSR) | 大幅提升（无死角） |
| 阴影 | 硬/软阴影 | Shadow Maps | 更精确、无锯齿 |
| 环境光遮蔽(AO) | 接触阴影 | SSAO/HBAO | 更物理准确 |
| 全局光照(GI) | 间接光照 | Light Probes | 真实光扩散效果 |

**混合光线追踪（当前游戏主流）：**

```
场景渲染：
  1. 光栅化：主场景（不透明）
  2. 光线追踪反射：只对反射物体发射少量光线
  3. 光线追踪阴影：对主要光源补充RT阴影
  4. 时间积累：多帧降噪（Temporal Denoising）
  5. 光栅化：透明物体 + UI
```

#### 降噪（Denoising）

光线追踪需要大量采样才能去噪，但实时渲染只能每像素1~4条光线，因此需要**降噪**：

```
去噪器（SVGF / BMFR / NRD）：
  输入：稀疏采样（1-4 spp）
  输出：平滑、无噪声的图像
  
  关键技术：
  ├── 空间滤波：相邻像素加权平均
  ├── 时间滤波：多帧累积（Temporal Accumulation）
  └── 特征辅助：使用法线/深度/粗糙度作为滤波权重
```

### 3.2 DLSS / FSR / XeSS 超分辨率

#### 为什么需要超分辨率

现代渲染压力大（4K分辨率 + 光线追踪），需要**以较低分辨率渲染 + AI升采样**：

```
低分辨率渲染（1080p / 1440p）
    ↓
  超分辨率模型（AI / 算法）
    ↓
高分辨率输出（1440p / 4K）
```

#### 主要方案对比

| 技术 | 开发者 | 方法 | 优势 | 限制 |
|------|--------|------|------|------|
| **DLSS** (2018) | NVIDIA | AI深度学习 + Tensor Core | 画质最佳 | 仅RTX显卡 |
| **DLSS 3 FG** (2022) | NVIDIA | AI插帧 + Optical Flow | 帧数翻倍 | 仅RTX 40系 |
| **FSR 1.0** (2021) | AMD | 空间缩放（Lanczos） | 所有GPU可用 | 画质一般 |
| **FSR 2.0** (2022) | AMD | 时间缩放 + 抗锯齿 | 跨平台 | 画质好于FSR1 |
| **FSR 3.0** (2023) | AMD | 时间缩放 + 插帧 | 帧数提升 | 需游戏支持 |
| **XeSS** (2022) | Intel | AI深度学习 + XMX | Intel优化 | Arc显卡最佳 |

#### DLSS原理（简化）

```
低分辨率帧
    ↓
1. 运动向量（Motion Vectors）：每像素的运动信息
2. 历史帧重用：TAA风格的多帧累积
3. AI网络推理：
   ├── 特征提取（CNN）
   ├── 时间融合（LSTM/ConvGRU）
   └── 升采样重建（反卷积/Sub-pixel Conv）
4. 自动曝光/色调映射适配
    ↓
高分辨率帧
```

#### FSR 2.0原理（简化）

```
低分辨率帧
    ↓
1. 深度/运动向量分析
2. 时间积累（类似TAA）
3. 自适应锐化（RCAS）
4. 边缘重建
    ↓
高分辨率帧
```

#### 性能提升示例

| 分辨率组合 | 渲染像素数 | 性能提升 |
|-----------|-----------|---------|
| 原生 4K (3840×2160) | 8.3M | 100%（基准） |
| DLSS性能 (1920×1080→4K) | 2.1M | ~2.5x |
| DLSS平衡 (2227×1253→4K) | 2.8M | ~2.0x |
| DLSS质量 (2560×1440→4K) | 3.7M | ~1.5x |

### 3.3 下一代技术展望

| 技术 | 状态 | 影响 |
|------|------|------|
| **Neural Rendering** | 学术/实验 | 神经网络直接生成像素 |
| **路径追踪实时化** | 发展中 | 完全物理正确的光照（UE5 Lumen） |
| **Mesh Shader** | 已可用(Vulkan/DX12) | 动态LOD，替代传统顶点着色器 |
| **Virtual Geometry** | 已可用(UE5 Nanite) | 无限细节，无需手动LOD |
| **Wavefront Path Tracing** | 已可用 | GPU优化的路径追踪 |
| **Foveated Rendering** | VR专用 | 眼动追踪优化渲染质量 |

## 4. 波次4回顾：从软件渲染到现代GPU的完整路线

### 4.1 8课知识路线图

```
波次4：计算机图形学知识体系地图
=================================

基础理论：
┌──────────────────────────────────────────────────────────────┐
│  第1课：光栅化与变换                                        │
│  ├── 图形管线概览 (Application→Vertex→Raster→Fragment→FB)  │
│  ├── 齐次坐标 & 4×4变换矩阵                                 │
│  ├── MVP变换 (Model/View/Projection)                        │
│  ├── Bresenham画线算法                                       │
│  ├── 三角形填充 (扫描线/重心坐标)                            │
│  ├── Z-buffer原理                                            │
│  └── 代码：graphics_01_rasterization.md                      │
│       → 立方体线框GIF                                        │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第2课：三角形填充与Z-buffer                                 │
│  ├── 重心坐标插值 (深度/颜色)                                │
│  ├── Z-buffer深度测试                                        │
│  ├── 背面剔除 (Backface Culling)                             │
│  ├── 透视校正插值 (Perspective-Correct Interpolation)       │
│  └── 代码：graphics_02_triangle_raster.md                    │
│       → 实心旋转立方体GIF                                    │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第3课：光照与着色                                           │
│  ├── Blinn-Phong光照模型 (Ambient/Diffuse/Specular)          │
│  ├── Gouraud Shading (逐顶点)                                │
│  ├── Phong Shading (逐像素)                                  │
│  ├── Flat Shading (逐三角形)                                 │
│  └── 三种着色模式对比                                        │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第4课：纹理映射与抗锯齿                                     │
│  ├── UV坐标与纹理采样                                        │
│  ├── 双线性插值 (Bilinear Interpolation)                     │
│  ├── SSAA (超采样抗锯齿)                                     │
│  ├── MSAA (多重采样抗锯齿)                                   │
│  └── 两者对比 (SSAA vs MSAA)                                 │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第5课：阴影、透明度与高级着色                                │
│  ├── Shadow Mapping (阴影映射)                               │
│  ├── PCF (Percentage Closer Filtering)                       │
│  ├── Alpha Blend (透明度混合, Porter-Duff)                   │
│  └── Skybox (天空盒/环境贴图)                                │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第6课：GPU管线与可编程着色器                                 │
│  ├── GPU架构：SIMT / Warp / Wavefront                         │
│  ├── 固定管线 vs 可编程管线                                   │
│  ├── 顶点着色器 (Vertex Shader)                               │
│  ├── 片段着色器 (Fragment Shader)                             │
│  ├── 几何着色器 (Geometry Shader)                             │
│  ├── 计算着色器 (Compute Shader)                              │
│  └── Python GPU管线模拟 (Warp调度)                            │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第7课：PBR与BRDF                                            │
│  ├── BRDF理论 (渲染方程)                                     │
│  ├── Cook-Torrance模型 (D·F·G)                               │
│  ├── 微表面理论 (NDF/Fresnel/Geometry)                       │
│  ├── PBR工作流 (Albedo/Metallic/Roughness)                   │
│  ├── IBL (Irradiance Map + Pre-filtered Map)                 │
│  └── Python PBR光线追踪渲染器                                │
└──────────────────────────────────────────────────────────────┘

                         ↓
┌──────────────────────────────────────────────────────────────┐
│  第8课：图形API与渲染实战 (本课)                              │
│  ├── OpenGL / Vulkan / DX12 / Metal 对比                     │
│  ├── FrameGraph / Render Graph                               │
│  ├── Deferred vs Forward Shading                             │
│  ├── 光线追踪 (RTX/DXR/BVH/Denoising)                        │
│  ├── DLSS / FSR / XeSS                                       │
│  └── 波次4完整总结 ← 你在这里                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 各课产出物清单

| 课次 | 标题 | 笔记文件 | 代码产出 |
|------|------|---------|---------|
| 第1课 | 光栅化与变换 | `graphics_01_rasterization.md` | `graphics_01_cube.gif` (线框立方体) |
| 第2课 | 三角形填充与Z-buffer | `graphics_02_triangle_raster.md` | `graphics_02_solid_cube.gif` (实心立方体) |
| 第3课 | 光照与着色 | `graphics_03_lighting.md` | `graphics_03_shading.gif` (三种着色模式) |
| 第4课 | 纹理映射与抗锯齿 | `graphics_04_texture.md` | `graphics_04_textured_cube.gif` (纹理立方体) |
| 第5课 | 阴影、透明度与高级着色 | `graphics_05_shadow.md` | `graphics_05_shadow.gif` (阴影+透明+天空盒) |
| 第6课 | GPU管线与可编程着色器 | `graphics_06_gpu_pipeline.md` | `graphics_06_gpu_sim.gif` (GPU模拟渲染) |
| 第7课 | PBR与BRDF | `graphics_07_pbr.md` | `graphics_07_pbr.png` (PBR球体渲染) |
| 第8课 | 图形API与渲染实战 | `graphics_08_gpu_api.md` | （纯概念，本课无代码产出） |

### 4.3 知识体系地图（Mind Map）

```
                        ┌─────────────┐
                        │ 计算机图形学 │
                        └──────┬──────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                     │
     ┌────┴────┐         ┌────┴────┐          ┌────┴────┐
     │基础算法  │         │真实感渲染│          │现代架构 │
     └────┬────┘         └────┬────┘          └────┬────┘
          │                    │                     │
    ┌─────┼─────┐       ┌─────┼─────┐         ┌────┼────┐
    │     │     │       │     │     │         │    │    │
  Bresenham│ MVP 光照   │纹理 阴影  PBR     GPU  API  光追
  画线    │矩阵 Blinn- │映射 映射  BRDF     管线       │
  三角形  │  Z   Phong  │抗锯齿    微表面     ├─SIMT  │
  填充    │buffer着色器 │双线性 Alpha Cook-   ├─Warp  │GPU
            │  │        │ SSAA  Blend Torrance├─VS/FS │管线
            │  │        │ MSAA  Skybox D·F·G  ├─CS    │
            │  │        │                     │       │
       变换系统 可见性  纹理系统  光照系统    GPU架构  API层
```

### 4.4 从软件渲染到现代GPU的完整路线

本波次的核心叙事线：**从CPU单线程软件渲染 → 理解现代GPU并行架构**

```
第1课 → 第2课 → 第3课 → 第4课 → 第5课 → 第6课 → 第7课 → 第8课
│       │       │       │       │       │       │       │
│ 像素   │ 深度   │ 光照  │ 纹理   │ 高级   │ GPU   │ PBR   │ API
│ 填充   │ 测试   │ 计算   │ 采样   │ 效果   │ 架构   │ 光照   │ 对比
│       │       │       │       │       │       │       │
└──────────────────────────┐──────────────────────────┘
                   软件渲染器（自己实现）          │
                                             现代GPU管线
```

**关键认知跃迁：**
1. **第一性原理**：从Bresenham画一条线开始，理解像素是如何被"点亮"的
2. **并行化思维**：从逐像素循环到理解SIMT/Warp的并发执行
3. **从近似的物理**：从Blinn-Phong的经验模型到Cook-Torrance的物理模型
4. **从软件到硬件**：从Python模拟到理解GPU架构的设计取舍

## 5. 波次4完整总结

### 📚 学习成果总览

**波次4：计算机图形学** 共8课，完成了从零开始的软件渲染器实现，覆盖了计算机图形学的三大支柱：

#### 第一支柱：图形管线与算法（第1-2课）
- ✅ 掌握MVP变换、透视投影、齐次坐标
- ✅ 实现Bresenham画线和三角形填充
- ✅ 实现Z-buffer深度测试与背面剔除
- ✅ 理解透视校正插值

#### 第二支柱：着色与光照（第3-4课，第7课）
- ✅ 掌握Blinn-Phong光照模型（Ambient/Diffuse/Specular）
- ✅ 实现三种着色模式（Flat/Gouraud/Phong）
- ✅ 实现纹理映射（UV/双线性插值）
- ✅ 掌握基于物理渲染（PBR/Cook-Torrance BRDF）
- ✅ 理解微表面理论（NDF/菲涅尔/几何函数）

#### 第三支柱：高级效果与架构（第5-6课，第8课）
- ✅ 实现Shadow Mapping与PCF软阴影
- ✅ 实现Alpha Blend透明度混合
- ✅ 实现Skybox环境贴图
- ✅ 理解GPU架构（SIMT/Warp）
- ✅ 理解可编程着色器（VS/FS/GS/CS）
- ✅ 了解四大图形API（OpenGL/Vulkan/DX12/Metal）
- ✅ 了解现代渲染架构（Frame Graph/Deferred Shading）
- ✅ 了解前沿技术（光线追踪/DLSS/FSR）

### 🛠 实践成果

- **8篇** 完整学习笔记（含理论、公式、代码）
- **7个** 可运行的Python代码示例
- **6个** 视觉产出（GIF动画/渲染图片）
- **1个** GPU管线模拟器

### 🗺 知识体系地图

```
计算机图形学知识体系
├── 基础数学
│   ├── 线性代数（向量/矩阵/变换）
│   ├── 三角学（角度/三角函数）
│   └── 插值（线性/重心坐标）
├── 光栅化
│   ├── 画线（Bresenham/DDA）
│   ├── 三角形填充（扫描线/Bounding Box/重心坐标）
│   └── 深度缓冲（Z-buffer）
├── 变换
│   ├── 模型变换（M）
│   ├── 视图变换（V）
│   ├── 投影变换（P：正交/透视）
│   └── 视口变换
├── 着色
│   ├── Blinn-Phong（Ambient/Diffuse/Specular）
│   ├── PBR/Cook-Torrance（D·F·G）
│   ├── 微表面理论
│   └── IBL（Irradiance/Pre-filtered）
├── 纹理
│   ├── UV映射
│   ├── 采样（最近邻/双线性）
│   └── 抗锯齿（SSAA/MSAA）
├── 高级效果
│   ├── 阴影（Shadow Mapping/PCF）
│   ├── 透明度（Alpha Blend）
│   └── 环境贴图（Skybox）
├── GPU架构
│   ├── SIMT/SIMD
│   ├── Warp/Wavefront
│   └── 内存层次
├── 着色器
│   ├── 顶点着色器（VS）
│   ├── 片段着色器（FS）
│   ├── 几何着色器（GS）
│   └── 计算着色器（CS）
└── API与架构
    ├── 图形API（OpenGL/Vulkan/DX12/Metal）
    ├── 渲染架构（Forward/Deferred/FrameGraph）
    └── 前沿技术（RTX/DLSS/FSR）

核心技术栈：Python + NumPy + Pillow → 模拟 → GLSL/HLSL/Vulkan
```

🎉 **波次4全部完成！**
