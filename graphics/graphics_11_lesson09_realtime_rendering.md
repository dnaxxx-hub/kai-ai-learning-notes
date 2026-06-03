# 第9课：实时渲染技术

## 1. 阴影映射 (Shadow Mapping)

### 1.1 核心原理

阴影映射的基本思想是：从**光源视角**渲染场景的深度图，然后从**摄像机视角**渲染时，判断片元是否在阴影中。

```
光源视角                     摄像机视角
    │                           │
    ▼                           ▼
┌──────────┐              ┌──────────┐
│ 深度图    │ ← 渲染到纹理  │ 场景渲染  │
│ (阴影贴图) │              │ 比较深度  │
└──────────┘              └──────────┘
     │                         │
     └─────── 比较深度 ────────┘
                │
                ▼
          片元在阴影中？
          是 → 只保留环境光
          否 → 完整光照
```

### 1.2 算法流程

```
Pass 1: 从光源视角渲染深度
  └─ 光源处放置摄像机
  └─ 使用简单着色器（只输出深度）
  └─ 渲染到深度纹理 (depth map)

Pass 2: 从摄像机视角渲染场景
  └─ 对每个片元：
     1. 转换到光源空间坐标 (light space)
     2. 比较片元深度 vs 深度图采样值
     3. 若片元深度 > 深度图值 → 在阴影中
```

### 1.3 阴影贴图着色器

**深度渲染 — 顶点着色器：**
```glsl
#version 330 core
layout (location = 0) in vec3 aPos;

uniform mat4 lightSpaceMatrix;  // 光源的 projection * view
uniform mat4 model;

void main() {
    gl_Position = lightSpaceMatrix * model * vec4(aPos, 1.0);
}
```

**深度渲染 — 片元着色器：**
```glsl
// 什么也不做，OpenGL 自动写入深度缓冲区
void main() {
    // 空函数体即可
}
```

**场景渲染 — 片元着色器（阴影检测）：**
```glsl
#version 330 core
out vec4 FragColor;

in vec3 FragPos;
in vec3 Normal;
in vec2 TexCoord;

uniform sampler2D shadowMap;
uniform mat4 lightSpaceMatrix;
uniform vec3 lightPos;
uniform vec3 viewPos;

float ShadowCalculation(vec4 fragPosLightSpace) {
    // 透视除法 → NDC [-1,1]
    vec3 projCoords = fragPosLightSpace.xyz / fragPosLightSpace.w;
    // 映射到 [0,1] 纹理坐标
    projCoords = projCoords * 0.5 + 0.5;

    // 深度图中存储的最近深度
    float closestDepth = texture(shadowMap, projCoords.xy).r;
    // 当前片元的深度
    float currentDepth = projCoords.z;

    // 阴影偏移（解决 Shadow Acne 问题）
    float bias = max(0.005 * (1.0 - dot(Normal, lightDir)), 0.0005);

    // 百分比渐进滤波 (PCF) — 软阴影
    float shadow = 0.0;
    vec2 texelSize = 1.0 / textureSize(shadowMap, 0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float pcfDepth = texture(shadowMap, projCoords.xy + vec2(x, y) * texelSize).r;
            shadow += currentDepth - bias > pcfDepth ? 1.0 : 0.0;
        }
    }
    shadow /= 9.0;

    // 超出深度图范围的不算阴影
    if (projCoords.z > 1.0) shadow = 0.0;

    return shadow;
}

void main() {
    // ... 光照计算 ...
    float shadow = ShadowCalculation(fragPosLightSpace);
    vec3 lighting = (ambient + (1.0 - shadow) * (diffuse + specular)) * color;
    FragColor = vec4(lighting, 1.0);
}
```

### 1.4 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| **Shadow Acne**（阴影粉刺） | 深度精度有限，自遮挡 | 添加深度偏移 (bias) |
| **Peter Panning**（阴影漂浮） | 偏移过大 | 使用法线方向自适应偏移 |
| **锯齿边缘** | 深度图分辨率有限 | PCF 滤波 / 级联阴影贴图 (CSM) |
| **阴影超出范围** | 片元不在深度图覆盖范围 | 坐标检查 + 降级处理 |

### 1.5 级联阴影贴图 (CSM)

对于大场景，单张深度图无法同时在近处和远处提供好质量：

```
Cascade 1 (近): 1024×1024, 覆盖 0-10m
Cascade 2 (中): 1024×1024, 覆盖 10-50m
Cascade 3 (远): 1024×1024, 覆盖 50-200m

根据片元深度选择 Cascade 层级
```

## 2. 延迟着色 (Deferred Shading)

### 2.1 前向着色 (Forward) vs 延迟着色 (Deferred)

**前向着色：**
```
for each object:
    for each light:
        shade fragment → output color
```
- 复杂度：O(Objects × Lights × Fragments)
- 大量光源时性能急剧下降

**延迟着色：**
```
Pass 1 (几何 Pass): 将所有片元信息写入 G-buffer
Pass 2 (光照 Pass): 对每帧只处理可见片元的光照
```
- 复杂度：O(Fragments + Lights × Visible Fragments)
- 100+ 光源也能轻松处理

### 2.2 G-buffer 结构

G-buffer（几何缓冲区）存储每个可见片元的几何信息：

```
┌─────────────────────────────────────────────┐
│ G-buffer                                      │
│                                               │
│  RT0 (RGB):   漫反射颜色 (Albedo)             │
│  RT1 (RGB):   世界空间法线                     │
│  RT2 (RGBA):  位置 + 金属度 (pos.xyz + metal) │
│  RT3 (RGBA):  AO + Roughness + 深度           │
│  Depth:       HW 深度缓冲                      │
└─────────────────────────────────────────────┘
```

### 2.3 延迟着色流程

```
Pass 1: Geometry Pass
  for each object:
      render to G-buffer (albedo, normal, position, material params)

Pass 2: Lighting Pass
  for each light:
      render light volume to screen with G-buffer textures
      accumulate light contribution

Pass 3: Forward Pass (可选)
  render transparent/translucent objects (延迟着色不支持透明)
```

### 2.4 延迟着色着色器

**几何 Pass — 片元着色器：**
```glsl
#version 330 core
layout (location = 0) out vec3 gAlbedo;
layout (location = 1) out vec3 gNormal;
layout (location = 2) out vec4 gPosMetal;
layout (location = 3) out vec4 gAORough;

in vec3 FragPos;
in vec3 Normal;
in vec2 TexCoord;

uniform sampler2D uAlbedo;
uniform sampler2D uNormalMap;
uniform float uMetallic;
uniform float uRoughness;
uniform float uAO;

void main() {
    gAlbedo   = texture(uAlbedo, TexCoord).rgb;
    gNormal   = normalize(Normal);
    gPosMetal = vec4(FragPos, uMetallic);
    gAORough  = vec4(uAO, uRoughness, 0.0, 0.0);
}
```

**光照 Pass — 片元着色器：**
```glsl
#version 330 core
out vec4 FragColor;

uniform sampler2D gAlbedo;
uniform sampler2D gNormal;
uniform sampler2D gPosMetal;
uniform sampler2D gAORough;
uniform sampler2D gDepth;

uniform vec3 lightPositions[100];
uniform vec3 lightColors[100];
uniform int numLights;
uniform vec3 viewPos;

void main() {
    vec2 uv = gl_FragCoord.xy / textureSize(gAlbedo, 0);

    vec3 albedo  = texture(gAlbedo, uv).rgb;
    vec3 normal  = texture(gNormal, uv).rgb;
    vec3 fragPos = texture(gPosMetal, uv).xyz;
    float metal  = texture(gPosMetal, uv).w;
    float ao     = texture(gAORough, uv).r;
    float rough  = texture(gAORough, uv).g;

    vec3 viewDir = normalize(viewPos - fragPos);
    vec3 result  = vec3(0.0);

    for (int i = 0; i < numLights; i++) {
        vec3 lightDir = normalize(lightPositions[i] - fragPos);
        // Blinn-Phong 计算...
        vec3 halfDir = normalize(lightDir + viewDir);

        float diff = max(dot(normal, lightDir), 0.0);
        float spec = pow(max(dot(normal, halfDir), 0.0), 32.0);

        result += (diff + spec) * lightColors[i] * albedo * ao;
    }

    FragColor = vec4(result, 1.0);
}
```

### 2.5 延迟着色优缺点

| 优点 | 缺点 |
|------|------|
| ✅ 大量光源性能好 | ❌ 不支持透明物体 |
| ✅ 每个片元只算一次光照 | ❌ 显存占用大（G-buffer） |
| ✅ 延迟+后处理天然结合 | ❌ 抗锯齿更复杂（需要特定 MSAA） |
| ✅ 光照计算独立于几何复杂度 | ❌ 带宽开销大（多次纹理读取） |

## 3. HDR 与 Tone Mapping

### 3.1 什么是 HDR？

传统渲染使用 `[0.0, 1.0]` 的 LDR（低动态范围），而 HDR 允许颜色值超出 1.0：

```
LDR: 颜色值 ∈ [0, 1] → 显示器直接显示
HDR: 颜色值 ∈ [0, ∞) → 需要 Tone mapping 映射到 [0, 1]
```

**为什么需要 HDR？**
- 真实世界亮度范围极大（太阳 ~10⁹ cd/m²，星空 ~10⁻⁶）
- 避免高光溢出（clamp to white）
- 支持 Bloom（辉光）效果
- 更真实的光照累积

### 3.2 Tone Mapping 算法

**Reinhard Tone Mapping：**
```glsl
vec3 ReinhardToneMap(vec3 hdrColor) {
    return hdrColor / (hdrColor + vec3(1.0));
}
// 特点：简单，但整体偏暗
```

**Reinhard Extended (Luminance-based)：**
```glsl
vec3 ReinhardExtended(vec3 hdrColor, float whitePoint) {
    float luminance = dot(hdrColor, vec3(0.2126, 0.7152, 0.0722));
    float L_white = whitePoint * whitePoint;
    float L_mapped = (luminance * (1.0 + luminance / L_white)) / (1.0 + luminance);
    return hdrColor * (L_mapped / luminance);
}
```

**ACES Filmic Tone Mapping（电影级）：**
```glsl
vec3 ACESToneMap(vec3 x) {
    // ACES 近似 — 目前游戏行业标准
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}
```

**Unreal Engine Filmic：**
```glsl
vec3 UnrealToneMap(vec3 x) {
    return x / (x + vec3(1.0));
    // 配合 x = x * exposure 控制曝光
}
```

### 3.3 曝光控制

```glsl
uniform float exposure;  // 0.0 ~ 4.0

void main() {
    vec3 hdrColor = texture(sceneTexture, uv).rgb;
    // 应用曝光
    vec3 mapped = vec3(1.0) - exp(-hdrColor * exposure);
    // 或 ACES
    vec3 mapped = ACESToneMap(hdrColor * exposure);
    FragColor = vec4(mapped, 1.0);
}
```

**自动曝光 (Eye Adaptation)：**
```glsl
// 1. 计算场景平均亮度（使用降采样 + mipmap）
float avgLuminance = texture(luminanceMip, vec2(0.5)).r;

// 2. 自动调整曝光
float targetExposure = 1.0 / (avgLuminance + 0.0001);
float exposure = mix(prevExposure, targetExposure, 0.05);  // 平滑过渡
```

### 3.4 Bloom（辉光）

Bloom 效果模拟高亮区域的光晕：

```
HDR 场景 → 提取高亮 (threshold) → 高斯模糊 → 与原图混合
                    ↓                  ↓
             color > 1.0?      水平和垂直模糊
                  ↓                  ↓
             bright = max(color - threshold, 0)
```

```glsl
// 提取高亮
vec3 ExtractBright(vec3 color, float threshold) {
    float brightness = dot(color, vec3(0.2126, 0.7152, 0.0722));
    return brightness > threshold ? color : vec3(0.0);
}

// 混合
vec3 result = sceneColor + bloomBlur * 0.3;
```

## 4. 抗锯齿 (Anti-Aliasing)

### 4.1 锯齿的产生

锯齿（Aliasing）是由于**采样不足**导致的伪影：

```
连续信号 → 采样 → 重建 → 锯齿
   │          │
   │    采样频率 < 信号最高频率 × 2 (Nyquist)
   └—————— 信息丢失 ——————→ 走样
```

在图形学中：
- **几何边缘锯齿** — 三角形边缘的阶梯状
- **纹理锯齿** — 远距离纹理闪烁 (Mipmap 解决)
- **光照锯齿** — 法线贴图上的高光闪烁

### 4.2 MSAA (Multisample Anti-Aliasing)

**原理：** 每个像素内有多个采样点，三角形覆盖检测在亚像素级别进行。

```
常规像素                4x MSAA 像素
┌────────┐          ┌──┬──┬──┬──┐
│        │          │ ●│ ●│ ●│  │
│        │          ├──┼──┼──┼──┤
│        │          │ ●│ ●│  │  │
│        │          ├──┼──┼──┼──┤
│        │          │  │  │  │  │
│        │          ├──┼──┼──┼──┤
└────────┘          │  │  │  │  │
                    └──┴──┴──┴──┴──┘
每个像素 1 个颜色   每种颜色计算一次
和 1 个深度样本    但深度测试 4 次
```

**MSAA 在 OpenGL 中：**
```python
# 窗口创建时启用
glfwWindowHint(GLFW_SAMPLES, 4)
# 或
glEnable(GL_MULTISAMPLE)  # 默认启用

# 自定义 FBO 的 MSAA
glTexImage2DMultisample(GL_TEXTURE_2D_MULTISAMPLE, 4, GL_RGB, w, h, GL_TRUE)
glRenderbufferStorageMultisample(GL_RENDERBUFFER, 4, GL_DEPTH24_STENCIL8, w, h)

# MSAA FBO 需要 blit 到 resolve FBO 才能使用纹理
glBindFramebuffer(GL_READ_FRAMEBUFFER, msaa_fbo)
glBindFramebuffer(GL_DRAW_FRAMEBUFFER, resolve_fbo)
glBlitFramebuffer(0, 0, w, h, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_NEAREST)
```

### 4.3 FXAA (Fast Approximate Anti-Aliasing)

**原理：** 后处理技术，检测图像中的边缘并模糊，不依赖硬件支持。

```
输入图像 → 亮度计算 → 边缘检测 → 混合 → 输出
   │            │          │        │
   │          Luma     对比度差  沿边缘方向
                          > 阈值   混合2个端点的颜色
```

```glsl
// FXAA 核心思路
vec3 FXAA(sampler2D tex, vec2 uv) {
    vec2 texelSize = 1.0 / textureSize(tex, 0);
    float luma = dot(texture(tex, uv).rgb, vec3(0.299, 0.587, 0.114));

    // 检测边缘方向
    float lumaN = dot(texture(tex, uv + vec2(0, -1) * texelSize).rgb, LUMA);
    float lumaS = dot(texture(tex, uv + vec2(0, 1) * texelSize).rgb, LUMA);
    float lumaW = dot(texture(tex, uv + vec2(-1, 0) * texelSize).rgb, LUMA);
    float lumaE = dot(texture(tex, uv + vec2(1, 0) * texelSize).rgb, LUMA);

    // 边缘方向（水平或垂直）
    float horizontal = abs(lumaN + lumaS - 2.0 * luma);
    float vertical   = abs(lumaE + lumaW - 2.0 * luma);
    bool isHorizontal = horizontal >= vertical;

    // 沿边缘方向采样并混合...
    // (实际实现有更多细节: 子像素抗锯齿、质量分级等)
}
```

### 4.4 各种抗锯齿技术对比

| 技术 | 类型 | 质量 | 性能 | 优点 | 缺点 |
|------|------|------|------|------|------|
| **SSAA** | 前处理 | ⭐⭐⭐⭐⭐ | ❌ 极慢 | 完美质量 | 渲染 n 倍分辨率 |
| **MSAA** | 硬件多采样 | ⭐⭐⭐⭐ | ✅ 好 | 锯齿+子像素质量好 | 不支持延迟着色 |
| **FXAA** | 后处理 | ⭐⭐⭐ | ✅✅ 快 | 适合所有场景 | 模糊纹理细节 |
| **SMAA** | 后处理 | ⭐⭐⭐⭐ | ✅ 好 | 比 FXAA 清晰 | 实现复杂 |
| **TAA** | 时序 | ⭐⭐⭐⭐⭐ | ✅✅ 快 | 低开销高质量 | 有鬼影 (Ghosting) |
| **DLSS** | AI 重建 | ⭐⭐⭐⭐⭐ | ✅✅✅ 极快 | 超分辨率+AA | 仅 RTX GPU |

### 4.5 CSAA (Coverage Sampling AA) — Nvidia 专有

MSAA 的变体，存储更多覆盖样本但不增加颜色/深度样本计算量：

```
4x MSAA:  4个颜色样本 + 4个深度样本 + 4个覆盖样本
8x CSAA:  4个颜色样本 + 4个深度样本 + 8个覆盖样本（质量接近 8xMSAA，性能接近 4xMSAA）
```

## 5. 实战：完整实时渲染管线整合

将以上所有技术组合到一个延迟着色管线中：

```
                    Frame N
                        │
                        ▼
    ┌─────────────────────────────────┐
    │ 1. Depth Pre-pass (可选)         │
    │    → 减少后续着色计算开销         │
    └──────────────┬──────────────────┘
                   ▼
    ┌─────────────────────────────────┐
    │ 2. Shadow Map Pass              │
    │    → 从每个光源渲染深度           │
    └──────────────┬──────────────────┘
                   ▼
    ┌─────────────────────────────────┐
    │ 3. Geometry Pass                │
    │    → 填充 G-buffer              │
    │    (Albedo/Normal/Position/Material)│
    └──────────────┬──────────────────┘
                   ▼
    ┌─────────────────────────────────┐
    │ 4. Lighting Pass                │
    │    → 逐光源计算光照              │
    │    → 阴影检测                   │
    └──────────────┬──────────────────┘
                   ▼
    ┌─────────────────────────────────┐
    │ 5. Forward Pass                 │
    │    → 透明物体                   │
    └──────────────┬──────────────────┘
                   ▼
    ┌─────────────────────────────────┐
    │ 6. Post-processing              │
    │    → HDR + Tone Mapping         │
    │    → Bloom (辉光)               │
    │    → FXAA / TAA                 │
    │    → 其他后处理                 │
    └──────────────┬──────────────────┘
                   ▼
               Frame Buffer → Display
```

## 6. 性能优化建议

### 6.1 CPU 侧优化
- **减少 Draw Call**：批处理 (Batching)、实例化 (Instancing)
- **尽早剔除**：视锥剔除、遮挡剔除 (Occlusion Culling)
- **使用 PBO** 异步纹理上传

### 6.2 GPU 侧优化
- **带宽优化**：压缩 G-buffer（选择最小精度格式）
- **Early-Z**：在片元着色器前做深度测试，丢弃被遮挡片元
- **LOD**：距离远时使用低精度模型/纹理
- **Tile-based 渲染**：移动 GPU 的特性，最小化带宽

### 6.3 从 CPU 软渲染到 GPU 实时渲染的思维跃迁

| 软渲染器 (CPU) | GPU 实时渲染 |
|---------------|-------------|
| 线性逐片元执行 | 数千并行着色器核心 |
| 逐帧创建 framebuffer | FBO 复用 + 增量更新 |
| 无多采样需求 | 需要多重采样 + 纹理过滤 |
| 单光源 Blinn-Phong | 多光源 PBR + 阴影 + IBL |
| 软件纹理采样 | 硬件纹理单元 + 各向异性过滤 |
| 无后处理 | 全屏后处理管线 |
