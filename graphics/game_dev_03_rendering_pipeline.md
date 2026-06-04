# 第3课：渲染管线 — 前向/延迟/移动端 TBDR/PBR/后处理/HDR

## 1. 课程概述

渲染管线将 3D 场景转化为屏幕上的像素。本课覆盖现代渲染的核心主题：**前向渲染**、**延迟渲染**、**移动端 TBDR**、**PBR 理论**、**后处理特效**和 **HDR**。通过引擎对比和 Shader 代码，帮助理解"帧是如何画出来的"。

## 2. 渲染管线基础

### 2.1 传统光栅化管线（Fixed-Function → Programmable）

```
顶点数据 → 顶点着色器 → 曲面细分 → 几何着色器 → 光栅化 → 片段着色器 → 输出合并
```
- **顶点着色器**：将顶点从模型空间变换到屏幕空间（MVP 矩阵）
- **光栅化**：将三角形转换为像素片段
- **片段着色器**：计算每个像素的颜色（光照、纹理）
- **输出合并（Blending）**：深度测试、透明度混合

### 2.2 三种主流渲染路径

| 特性 | 前向渲染 | 延迟渲染 | TBDR (移动端) |
|------|---------|---------|---------------|
| 光照计算次数 | 对每个物体×每个光源 | 对每个像素一次 | 对每个像素一次 |
| MSAA | 原生支持 | 需自定义 | 不支持 |
| 半透明 | 原生支持 | 需额外 Pass | 需额外 Pass |
| 多光源 | 性能差（大量 Draw） | 性能好 | 中等 |
| 带宽消耗 | 低 | 极高（GBuffer） | 低（Tile Memory）|
| 主要场景 | VR、小光源数 | AAA 多光源 | 手机、iPad |

## 3. 前向渲染（Forward Rendering）

### 3.1 原理

```glsl
// 每个物体 × 每个光源 = 一次绘制
for each light in scene:
    for each object visible to light:
        draw(object, light);  // 完整光照计算

// Unity 中 Forward 路径的 Base Pass + Additional Passes
```

### 3.2 优缺点

**优点**：
- MSAA 直接生效
- 透明度处理自然
- 实现简单

**缺点**：
- N 个光源 × M 个物体 = N×M 次 DrawCall
- 远处小物体和近处大物体光照计算量一样
- 典型瓶颈：Overdraw（像素被多次覆盖）

### 3.3 优化策略

- **LPV (Light Proxy Volume)**：灯光裁剪
- **Light Culling**：每个物体只被看得见的光照计算
- **Cluster Forward**：分块光照剔除，每帧更新

## 4. 延迟渲染（Deferred Rendering）

### 4.1 核心流程

```
Pass 1 - Geometry (写入 GBuffer)：
    - 位置 (Position, 3xFP16)
    - 法线 (Normal, 2xFP16 encodes)
    - 颜色/反照率 (Albedo, RGB8)
    - 材质参数 (Roughness/Metalness/AO, RGB8)
    - 深度 (Depth, FP32 或 重建)
    
Pass 2 - Lighting ：
    for each light:
        for each tile/projected area:
            read GBuffer → compute shading → accumulate
    
Pass 3 - Forward ：
    半透明物体、天空盒（用前向渲染）
```

### 4.2 GBuffer 布局对比

| 引擎 | GBuffer 数量 | 精度 | 扩展性 |
|------|-------------|------|--------|
| Unreal 5 | 5-6 RTs | FP16 | 可自定义 |
| Unity HDRP | 4-5 RTs | FP16 | 可配置 |
| 自己实现 | 3-4 RTs | FP16 | 自由 |

```glsl
// GBuffer 写入 (Pass 1)
layout(location = 0) out vec4 gPosition;
layout(location = 1) out vec4 gNormal;
layout(location = 2) out vec4 gAlbedo;
layout(location = 3) out vec4 gMaterial;

void main() {
    // 世界空间位置
    gPosition = vec4(worldPos, 1.0);
    
    // 编码法线（节省带宽）
    gNormal = encodeNormal(worldNormal);
    
    // 漫反射颜色
    gAlbedo = texture(albedoMap, uv);
    
    // 材质参数
    gMaterial.r = roughness;  // 粗糙度
    gMaterial.g = metallic;   // 金属度
    gMaterial.b = ao;         // 环境光遮蔽
    gMaterial.a = specularIntensity;
}
```

```glsl
// 延迟光照计算 (Pass 2)
void main() {
    vec3 worldPos = texture(gPosition, uv).xyz;
    vec3 normal   = decodeNormal(texture(gNormal, uv).xy);
    vec3 albedo   = texture(gAlbedo, uv).rgb;
    float roughness = texture(gMaterial, uv).r;
    float metallic  = texture(gMaterial, uv).g;
    
    vec3 viewDir = normalize(cameraPos - worldPos);
    
    // 逐光源计算
    vec3 result = vec3(0);
    for (int i = 0; i < NUM_LIGHTS; i++) {
        vec3 lightDir = normalize(lights[i].pos - worldPos);
        vec3 halfDir = normalize(lightDir + viewDir);
        
        // PBR BRDF
        result += computePBR(albedo, normal, lightDir, viewDir, 
                            halfDir, roughness, metallic, lights[i]);
    }
    
    fragColor = vec4(result, 1.0);
}
```

### 4.3 延迟 vs 前向 — 工程选择

| 标准 | 前向 | 延迟 |
|------|------|------|
| 光源数量 | < 8 | 100+ |
| MSAA | 原生 | 需定制 |
| 半透明 | 简单 | 困难 |
| GPU 带宽 | 低 | GBuffer 3-5× |
| 手机兼容 | 好 | 差（带宽/内存） |
| VR | 首选（MSAA） | 少用 |

**混合方案（Hybrid）**：不透明物体延迟 + 半透明/UI 前向 — Unreal/Unity HDRP 的默认选择。

## 5. 移动端渲染 — TBDR（Tile-Based Deferred Rendering）

### 5.1 为什么移动端不同？

传统 GPU（PC/主机）：**立即模式（Immediate Mode）**
- 绘制命令→直接处理→内存
- 每个 Pass 需要大量带宽

移动 GPU（PowerVR/Adreno/Mali）：**Tile-Based 模式**
- 屏幕分 16×16/32×32 Tile
- 每个 Tile 在片上内存（On-Chip Memory）中完成所有计算
- **带宽大幅降低**— 对移动端至关重要

### 5.2 TBDR 流程

```
1. Tiling Pass:  将所有三角形分配到各 Tile（计算可见性）
2. 片上内存:  每个 Tile 的深度/颜色全部在芯片内
3. 逐 Tile：  完全光照计算（无外部带宽）
4. 写入 FrameBuffer：  只有最终颜色写入系统内存
```

### 5.3 最佳实践

```glsl
// ❌ 移动端禁止：读回深度值（破坏 Tile 优化）
float depth = texture(depthTex, uv).r;  // TRAP!

// ❌ 禁止：动态分支在 Tile 级别不一致
if (rand() > 0.5) discard;  // TRAP!

// ✅ 推荐：最小化 RenderTarget 数量
// ✅ 推荐：使用 ETC2/ASTC 纹理压缩
// ✅ 推荐：One Draw Call Per Object
```

### 5.4 移动端渲染对比

| 策略 | 功耗 | 帧率 | 适用 |
|------|------|------|------|
| 纯 Forward | 高(大量Overdraw) | 中等 | 老设备 |
| Deferred (传统) | 极高(带宽) | 差 | 不推荐 |
| TBDR Deferred | 低 | 高 | 现代移动游戏 |
| Forward+ (Cluster) | 中等 | 高 | 中等以上设备 |

## 6. PBR — 基于物理的渲染

### 6.1 Microfacet Cook-Torrance BRDF

```glsl
// PBR 核心方程
vec3 PBR_BRDF(vec3 L, vec3 V, vec3 N, vec3 albedo, float roughness, float metallic) {
    vec3 H = normalize(L + V);
    
    // 1. Normal Distribution Function (NDF) — GGX/Trowbridge-Reitz
    float NDF = ggxDistribution(N, H, roughness);
    
    // 2. Geometry Function — Smith's method
    float G = smithGGX(N, V, roughness) * smithGGX(N, L, roughness);
    
    // 3. Fresnel — Schlick approximation
    vec3 F0 = mix(vec3(0.04), albedo, metallic);
    vec3 F = fresnelSchlick(dot(V, H), F0);
    
    // Cook-Torrance 镜面反射
    vec3 specular = (NDF * G * F) / max(4.0 * dot(N,V) * dot(N,L), 0.001);
    
    // 漫反射
    vec3 kD = (1.0 - F) * (1.0 - metallic);
    vec3 diffuse = kD * albedo / PI;
    
    return (diffuse + specular) * lightRadiance * max(dot(N, L), 0.0);
}
```

### 6.2 IBL（Image-Based Lighting）

PBR 中环境光照使用 **预滤波贴图（Pre-Filtered Environment Map）**：
- **漫反射 IBL**：预卷积的 Irradiance Map（6×6 分辨率足够）
- **镜面 IBL**：预滤波的 mipmap 链（粗糙度对应不同 mip 级别）
- **BRDF LUT**：预计算的 2D LUT（输入：NdotV + roughness → 输出：Fresnel 缩放和偏移）

### 6.3 各引擎 PBR 实现

| 引擎 | NDF | Geometry | Fresnel | IBL |
|------|-----|----------|---------|-----|
| Unreal | GGX | Smith Joint | Schlick | Split Sum |
| Unity URP | GGX | Smith | Schlick | Precomputed |
| Godot | GGX | Schlick-GGX | Schlick | Hemisphere |
| Filament (Google) | GGX | Smith Height-Corr | Schlick | Split Sum |

## 7. 后处理（Post-Processing）与 HDR

### 7.1 HDR 管线

```
Scene Color (FP16/FP32 HDR)
   ↓
Tonemapping (Reinhard/ACES/Filmic)
   ↓
Gamma Correction (sRGB)
   ↓
Output (LDR, 8-bit)
```

**Tonemapping 曲线对比**：
```glsl
// Reinhard（经典）
vec3 reinhard(vec3 color) {
    return color / (color + vec3(1.0));
}

// ACES Filmic（AAA 标准, 推荐）
vec3 acesFilmic(vec3 x) {
    float a = 2.51f;
    float b = 0.03f;
    float c = 2.43f;
    float d = 0.59f;
    float e = 0.14f;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// Unreal Filmic
// 更暖色调，视觉上更"电影感"
```

### 7.2 常见后处理效果

| 效果 | 实现方式 | 性能成本 |
|------|---------|---------|
| Bloom | 降采样→模糊→叠加 | 中等（3-5 Pass）|
| SSAO | 随机采样深度缓冲 | 低-中 |
| SSR (屏幕空间反射) | 射线步进 | 高 |
| Motion Blur | 速度缓冲 + 模糊 | 低 |
| DOF (景深) | COC + 分层模糊 | 中-高 |
| Volumetric Fog | 射线步进/Temporal | 高 |

### 7.3 后处理管线结构（以 Unity URP 为例）

```
Opaque Geometry → GBuffer → Lighting → Transparent → PostProcessing
                                                         ├── Auto Exposure
                                                         ├── Bloom
                                                         ├── Depth of Field
                                                         ├── Motion Blur
                                                         ├── Tonemapping
                                                         └── Color Grading (LUT)
```

## 8. 渲染管线横向对比

| 特性 | Unity URP | Unity HDRP | Unreal 5 | Godot 4 |
|------|-----------|------------|----------|---------|
| 默认管线 | Forward | Deferred | Deferred | Forward Mobile |
| 渲染路径选择 | Forward/Deferred | Deferred | Deferred | Forward/Clustered |
| PBR | 标准/自定义Lit | Lit/Material | Surface Shader | StandardMaterial3D |
| 后处理 | Volume System | Volume | PostProcess | WorldEnvironment |
| 移动支持 | ★★★★★ | ★★ | ★★ | ★★★★ |
| 控制台/PC | ★★★ | ★★★★★ | ★★★★★ | ★★★ |

## 9. 总结与实战建议

1. **前向渲染**：小场景、VR、MSAA 需求时用
2. **延迟渲染**：AAA 大场景、多光源
3. **TBDR**：移动端不二选择，注意限制 Z-Prepass 和 RT 数量
4. **PBR**：现代游戏的标准光照模型 — Cook-Torrance BRDF + IBL
5. **HDR + Tonemapping**：更宽广的动态范围 = 更丰富的色彩

**实战练习**：
1. 用 Unity URP 自建一个后处理 Volume 效果
2. 在 Unreal 中对比前向/延迟渲染的性能（使用 GPU Visualizer）
3. 在手机真机上 Profile TBDR 优化效果

> 推荐阅读：  
> - 《Real-Time Rendering, 4th Edition》  
> - LearnOpenGL.com — 延迟渲染/PBR 章节  
> - Unreal 官方文档 — 渲染管线深入
