# 第8课：着色器编程

## 1. GLSL 语言基础

### 1.1 GLSL 简史

| 版本 | OpenGL 版本 | 特性 |
|------|-------------|------|
| GLSL 110 | OpenGL 2.0 (2004) | 第一个可编程着色器 |
| GLSL 330 | OpenGL 3.3 (2010) | 核心模式、`in/out` 语法 |
| GLSL 400 | OpenGL 4.0 (2010) | 细分着色器 (Tessellation) |
| GLSL 430 | OpenGL 4.3 (2012) | 计算着色器 (Compute Shader) |
| GLSL 460 | OpenGL 4.6 (2017) | SPIR-V 支持 |

### 1.2 GLSL 核心语法

```glsl
#version 330 core   // 版本声明，必须第一行

// 输入/输出变量
layout (location = 0) in vec3 aPos;     // 顶点属性输入
flat in vec3 vColor;                     // 从顶点着色器传入（不插值）
out vec4 FragColor;                      // 片元着色器输出

// 统一变量（CPU→GPU 常数）
uniform float uTime;
uniform sampler2D uTexture;

// 常量
const float PI = 3.14159265;

// 结构体
struct Light {
    vec3 position;
    vec3 color;
    float intensity;
};

// 函数
float calc_attenuation(float dist, float constant, float linear, float quadratic) {
    return 1.0 / (constant + linear * dist + quadratic * dist * dist);
}

void main() {
    FragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
```

### 1.3 GLSL 数据类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `float` | 32位浮点 | `1.0` |
| `int` | 32位整数 | `42` |
| `bool` | 布尔 | `true` |
| `vec2` | 2维向量 | `vec2(1.0, 0.0)` |
| `vec3` | 3维向量 | `vec3(1.0)` = `(1,1,1)` |
| `vec4` | 4维向量 | `vec4(r,g,b,a)` |
| `mat2/mat3/mat4` | 方阵 | `mat4(1.0)` = 单位矩阵 |
| `sampler2D` | 2D纹理 | `texture(sampler, uv)` |
| `samplerCube` | 立方体贴图 | `texture(cube, dir)` |

**向量操作：**
```glsl
vec3 v = vec3(1.0, 2.0, 3.0);
v.x == v.r == v.s == 1.0    // 分量访问
v.y == v.g == v.t == 2.0
v.z == v.b == v.p == 3.0

// Swizzle — 随心重组
vec2 uv = v.xy;              // (1.0, 2.0)
vec3 w  = v.zyx;             // (3.0, 2.0, 1.0)
float d = dot(v, v);         // 点积
vec3 c  = cross(v, vec3(1,0,0)); // 叉积
vec3 n  = normalize(v);      // 归一化
float l = length(v);         // 长度
```

### 1.4 变量限定符

| 限定符 | 说明 | 作用域 |
|--------|------|--------|
| `uniform` | CPU→GPU 一次性设置，逐绘制调用不变 | 全局 |
| `in` | 从上一阶段输入的变量 | 每顶点/每片元 |
| `out` | 输出到下一阶段的变量 | 每顶点/每片元 |
| `flat` | 不进行插值（取第一个顶点的值） | 与 in 配合 |
| `smooth` | 透视校正插值（默认） | 与 in 配合 |
| `noperspective` | 线性插值（非透视校正） | 与 in 配合 |
| `attribute` | **已废弃** (OpenGL 2.0 风格) | — |

## 2. Blinn-Phong 光照模型（GPU 实现）

### 2.1 三种光照分量

```
片元颜色 = 环境光(Ambient) + 漫反射(Diffuse) + 镜面高光(Specular)
```

**顶点着色器 — 传递世界坐标和法线：**
```glsl
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec3 FragPos;
out vec3 Normal;

void main() {
    vec4 worldPos = model * vec4(aPos, 1.0);
    FragPos = worldPos.xyz;
    // 法线矩阵：变换法线到世界空间
    Normal = mat3(transpose(inverse(model))) * aNormal;
    gl_Position = projection * view * worldPos;
}
```

**片元着色器 — Blinn-Phong 光照计算：**
```glsl
#version 330 core
out vec4 FragColor;

in vec3 FragPos;
in vec3 Normal;

uniform vec3 lightPos;      // 光源位置（世界空间）
uniform vec3 viewPos;       // 摄像机位置
uniform vec3 lightColor;
uniform vec3 objectColor;

void main() {
    vec3 norm = normalize(Normal);
    vec3 lightDir = normalize(lightPos - FragPos);
    vec3 viewDir = normalize(viewPos - FragPos);
    vec3 halfDir = normalize(lightDir + viewDir);

    // Ambient
    float ambientStrength = 0.1;
    vec3 ambient = ambientStrength * lightColor;

    // Diffuse
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = diff * lightColor;

    // Specular (Blinn-Phong 使用半向量代替反射向量)
    float spec = pow(max(dot(norm, halfDir), 0.0), 32);
    vec3 specular = 0.5 * spec * lightColor;

    vec3 result = (ambient + diffuse + specular) * objectColor;
    FragColor = vec4(result, 1.0);
}
```

### 2.2 Phong vs Blinn-Phong 对比

| 特性 | Phong | Blinn-Phong (本课程) |
|------|-------|---------------------|
| 高光方向 | 反射向量 R = 2(N·L)N - L | 半向量 H = normalize(L+V) |
| 计算量 | 多一个 reflect() 计算 | 少一次 reflect，多一次 normalize |
| 效果 | 锐利边缘 | 更平滑（效率更高） |
| 使用场景 | 老式管线 | 现代图形学标准 |

## 3. PBR（基于物理的渲染）简化版

### 3.1 Cook-Torrance BRDF

PBR 的核心是 **BRDF (双向反射分布函数)**，描述表面如何反射光线：

```
f(l, v) = k_d * f_diffuse + k_s * f_specular
```

其中：
- **漫反射项**（Lambert）：`f_diffuse = c / π`
- **镜面高光项**（Cook-Torrance）：
  ```
  f_specular = D(h) · F(v, h) · G(l, v, h) / (4(n·l)(n·v))
       ↑            ↑            ↑
    法线分布    菲涅尔项     几何遮挡
  ```

### 3.2 三项核心函数

**法线分布函数 (Normal Distribution Function) — GGX/Trowbridge-Reitz：**
```
D(h) = α² / (π * ((n·h)² * (α² - 1) + 1)²)
其中 α = roughness²
```

**菲涅尔方程 (Fresnel) — Schlick 近似：**
```
F(v, h) = F₀ + (1 - F₀) * (1 - (v·h))⁵
其中 F₀ 是 0° 入射时的反射率
  金属: F₀ = 表面颜色 (albedo)
  非金属: F₀ = 0.04 (常数)
```

**几何遮挡函数 (Geometry Function) — Schlick-GGX：**
```
G(l, v, h) = G₁(n·l) * G₁(n·v)
G₁(x) = x / (x * (1 - k) + k)
k = (roughness + 1)² / 8  (IBL)
k = roughness² / 2          (直接光照)
```

### 3.3 简化 PBR 着色器片段

```glsl
uniform vec3  albedo;
uniform float metallic;
uniform float roughness;
uniform float ao;       // Ambient Occlusion

vec3 FresnelSchlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}

float DistributionGGX(vec3 N, vec3 H, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH = max(dot(N, H), 0.0);
    float denom = (NdotH * NdotH * (a2 - 1.0) + 1.0);
    return a2 / (PI * denom * denom);
}

float GeometrySchlickGGX(float NdotV, float roughness) {
    float k = (roughness + 1.0) * (roughness + 1.0) / 8.0;
    return NdotV / (NdotV * (1.0 - k) + k);
}

// PBR 主光照计算
vec3 CalcPBRLight(Light light, vec3 N, vec3 V, vec3 F0) {
    vec3 L = normalize(light.position - FragPos);
    vec3 H = normalize(V + L);

    float NDF = DistributionGGX(N, H, roughness);
    float G   = GeometrySchlickGGX(max(dot(N, L), 0.0), roughness) *
                GeometrySchlickGGX(max(dot(N, V), 0.0), roughness);
    vec3 F    = FresnelSchlick(max(dot(H, V), 0.0), F0);

    vec3 kS = F;                          // 镜面反射比例
    vec3 kD = vec3(1.0) - kS;             // 漫反射比例
    kD *= (1.0 - metallic);               // 金属无漫反射

    vec3 numerator   = NDF * G * F;
    float denominator = 4.0 * max(dot(N, L), 0.0) * max(dot(N, V), 0.0) + 0.0001;
    vec3 specular = numerator / denominator;

    float NdotL = max(dot(N, L), 0.0);
    vec3 radiance = light.color * light.intensity;

    return (kD * albedo / PI + specular) * radiance * NdotL;
}
```

### 3.4 Blinn-Phong vs PBR 对比

| 特性 | Blinn-Phong | PBR |
|------|-------------|-----|
| 参数 | `shininess` (无物理意义) | `roughness / metallic` (有物理意义) |
| 高光 | 经验公式 | Cook-Torrance BRDF |
| 能量守恒 | ❌ 不保证 | ✅ 自动保证 |
| 金属度 | ❌ 不支持 | ✅ 金属/非金属统一 |
| 计算开销 | 低 | 中（多几次三角函数） |
| 效果 | 塑料感 | 真实材质 |

## 4. 纹理采样与多重纹理

### 4.1 纹理坐标

```
纹理坐标范围: [0, 1] × [0, 1]
        (0,1) ┌──────┐ (1,1)
              │      │
              │   ●  │ ← uv = (0.5, 0.5)
              │      │
        (0,0) └──────┘ (1,0)
```

### 4.2 采样模式

```python
# 纹理缠绕模式
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)      # 平铺
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE) # 边缘钳制
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_MIRRORED_REPEAT) # 镜像

# 纹理过滤
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
```

| 过滤模式 | 缩小 (MIN) | 放大 (MAG) |
|---------|-----------|-----------|
| `GL_NEAREST` | 最近邻（像素风） | 最近邻 |
| `GL_LINEAR` | 双线性插值 | 双线性插值 |
| `GL_NEAREST_MIPMAP_NEAREST` | 最近 Mipmap 层 + 最近邻 | 同上（放大无需 mipmap） |
| `GL_LINEAR_MIPMAP_LINEAR` | 三线性插值（最佳质量） | 同上 |

### 4.3 多重纹理（Multi-texturing）

**概念：** 在同一个片元着色器中采样多个纹理，然后混合。

```glsl
#version 330 core
out vec4 FragColor;

in vec2 TexCoord;
in vec3 FragPos;
in vec3 Normal;

uniform sampler2D uAlbedo;      // 漫反射纹理
uniform sampler2D uNormalMap;   // 法线贴图
uniform sampler2D uSpecularMap; // 高光贴图
uniform sampler2D uAOMap;       // 环境光遮蔽贴图

void main() {
    vec3 albedo = texture(uAlbedo, TexCoord).rgb;
    vec3 normal = texture(uNormalMap, TexCoord).rgb * 2.0 - 1.0; // [0,1]→[-1,1]
    float spec = texture(uSpecularMap, TexCoord).r;
    float ao   = texture(uAOMap, TexCoord).r;

    // 光照计算使用这些值...
    FragColor = vec4(albedo * (ambient * ao + diffuse + specular), 1.0);
}
```

**Python 端绑定：**
```python
# 纹理单元 0 → 漫反射
glActiveTexture(GL_TEXTURE0)
glBindTexture(GL_TEXTURE_2D, albedo_tex)
glUniform1i(glGetUniformLocation(shader, "uAlbedo"), 0)

# 纹理单元 1 → 法线贴图
glActiveTexture(GL_TEXTURE1)
glBindTexture(GL_TEXTURE_2D, normal_tex)
glUniform1i(glGetUniformLocation(shader, "uNormalMap"), 1)

# 纹理单元 2 → 高光贴图
glActiveTexture(GL_TEXTURE2)
glBindTexture(GL_TEXTURE_2D, specular_tex)
glUniform1i(glGetUniformLocation(shader, "uSpecularMap"), 2)
```

### 4.4 生成程序化纹理

```python
def create_checker_texture(size=256, grid=8):
    """生成棋盘格纹理"""
    data = np.zeros((size, size, 3), dtype=np.uint8)
    block = size // grid
    for y in range(size):
        for x in range(size):
            cx, cy = x // block, y // block
            if (cx + cy) % 2 == 0:
                data[y, x] = [200, 200, 200]
            else:
                data[y, x] = [50, 50, 50]
    return data

def upload_texture(data):
    """上传 numpy 数组为 OpenGL 纹理"""
    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, data.shape[1], data.shape[0],
                  0, GL_RGB, GL_UNSIGNED_BYTE, data)
    glGenerateMipmap(GL_TEXTURE_2D)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    return tex
```

## 5. 帧缓冲与离屏渲染

### 5.1 帧缓冲对象 (FBO) 架构

```
默认帧缓冲 (屏幕)              自定义帧缓冲 (离屏)
┌─────────────────┐          ┌─────────────────┐
│  颜色缓冲区      │          │  颜色附件        │ ← 纹理 / Renderbuffer
│  深度缓冲区      │          │  深度附件        │
│  模板缓冲区      │          │  模板附件        │
└─────────────────┘          └─────────────────┘
                                  │
                                  ▼
                            后处理效果
                            (模糊/辉光/锐化)
```

### 5.2 FBO 创建流程

```python
# 1. 生成帧缓冲对象
fbo = glGenFramebuffers(1)
glBindFramebuffer(GL_FRAMEBUFFER, fbo)

# 2. 创建颜色附件纹理
color_tex = glGenTextures(1)
glBindTexture(GL_TEXTURE_2D, color_tex)
glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color_tex, 0)

# 3. 创建深度模板附件
rbo = glGenRenderbuffers(1)
glBindRenderbuffer(GL_RENDERBUFFER, rbo)
glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, width, height)
glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, rbo)

# 4. 检查完整性
assert glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE
glBindFramebuffer(GL_FRAMEBUFFER, 0)  # 恢复默认
```

### 5.3 离屏渲染 + 后处理流程

```
Pass 1: 渲染场景到 FBO
  glBindFramebuffer(GL_FRAMEBUFFER, fbo)
  glClear(...)
  glUseProgram(scene_shader)
  glBindVertexArray(scene_vao)
  glDrawElements(...)

Pass 2: 后处理 → 屏幕
  glBindFramebuffer(GL_FRAMEBUFFER, 0)  # 切换回默认帧缓冲
  glClear(...)
  glUseProgram(postprocess_shader)
  glBindTexture(GL_TEXTURE_2D, color_tex)  # Pass 1 的结果
  glBindVertexArray(screen_quad_vao)        # 全屏四边形
  glDrawArrays(GL_TRIANGLES, 0, 6)          # 两个三角形
```

### 5.4 常用后处理效果

**反相 (Invert)：**
```glsl
void main() {
    vec4 color = texture(screenTexture, TexCoord);
    FragColor = vec4(1.0 - color.rgb, 1.0);
}
```

**灰度 (Grayscale)：**
```glsl
void main() {
    vec4 color = texture(screenTexture, TexCoord);
    float gray = dot(color.rgb, vec3(0.299, 0.587, 0.114));
    FragColor = vec4(vec3(gray), 1.0);
}
```

**核卷积 — 边缘检测 (Sobel)：**
```glsl
const float kernel[9] = float[](
    -1, -1, -1,
    -1,  8, -1,
    -1, -1, -1
);

void main() {
    vec2 offset = 1.0 / textureSize(screenTexture, 0);
    vec3 sum = vec3(0.0);
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            vec2 uv = TexCoord + vec2(i-1, j-1) * offset;
            sum += texture(screenTexture, uv).rgb * kernel[i*3 + j];
        }
    }
    FragColor = vec4(sum, 1.0);
}
```

**高斯模糊：**
```glsl
// 可分离的高斯模糊（水平方向）
const float weights[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);

void main() {
    vec2 texelSize = 1.0 / textureSize(screenTexture, 0);
    vec3 result = texture(screenTexture, TexCoord).rgb * weights[0];
    for (int i = 1; i < 5; i++) {
        result += texture(screenTexture, TexCoord + vec2(i * texelSize.x, 0.0)).rgb * weights[i];
        result += texture(screenTexture, TexCoord - vec2(i * texelSize.x, 0.0)).rgb * weights[i];
    }
    FragColor = vec4(result, 1.0);
}
```
