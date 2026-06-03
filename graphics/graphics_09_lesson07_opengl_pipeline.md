# 第7课：OpenGL 渲染管线

## 1. OpenGL 可编程管线架构

### 1.1 传统固定管线 vs 现代可编程管线

| 特性 | 固定管线 (OpenGL 1.x/2.x) | 可编程管线 (OpenGL 3.3+/4.x) |
|------|--------------------------|------------------------------|
| 变换 | `glRotate/glTranslate/glScale` | 顶点着色器中 MVP 矩阵 |
| 光照 | `glLight/glMaterial` 内置公式 | 片元着色器自定义计算 |
| 纹理 | `glTexEnv` 固定组合 | 着色器中任意采样/混合 |
| 雾效 | `glFog` | 着色器自定义 |
| 灵活性 | 几组固定参数 | 完全自由 |

### 1.2 完整渲染管线流程

```
┌────────────────────────────────────────┐
│          应用程序 (CPU)                  │
│  顶点数据 → VAO/VBO/EBO 绑定           │
│  统一变量(uniform) 设置                 │
│  glDrawArrays / glDrawElements          │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│     顶点着色器 (Vertex Shader)           │
│  • 输入: 顶点属性 (位置、法线、UV...)    │
│  • 变换: 模型-视图-投影 (MVP)           │
│  • 输出: gl_Position + varying          │
│  • 每个顶点执行一次                     │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│     Tessellation (可选, OpenGL 4.0+)    │
│  • 细分控制着色器                       │
│  • 细分计算着色器                       │
│  • 动态生成几何细节                     │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│     几何着色器 (Geometry Shader, 可选)   │
│  • 输入: 一个基本图元 (点/线/三角)      │
│  • 输出: 0或多个新基本图元              │
│  • 应用: 粒子扩展、法线可视化、草地生成  │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│     图元装配 (Primitive Assembly)        │
│  • 顶点 → 图元 (点/线/三角形)           │
│  • 视口变换                             │
│  • 背面剔除 (Back-face Culling)         │
│  • 裁剪 (Clipping)                      │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│     光栅化 (Rasterization)              │
│  • 图元 → 片元 (Fragment)              │
│  • 插值 varying 变量                   │
│  • 深度偏移 (Polygon Offset)            │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│    片元着色器 (Fragment Shader)          │
│  • 每个片元执行一次                     │
│  • 计算最终颜色                         │
│  • 纹理采样、光照计算                   │
│  • 输出: gl_FragColor / 自定义输出      │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│     逐片元操作 (Per-Fragment Ops)        │
│  • 深度测试 (Z-buffer)                  │
│  • 模板测试 (Stencil)                   │
│  • 混合 (Blending)                      │
│  • 裁剪测试 (Scissor)                   │
│  • 抖动 (Dithering)                     │
└───────────────┬────────────────────────┘
                │
                ▼
┌────────────────────────────────────────┐
│          帧缓冲区 (Framebuffer)          │
│    → 屏幕显示 或 离屏渲染               │
└────────────────────────────────────────┘
```

### 1.3 与软件渲染器的对应关系

我们之前写了软件的 `soft_renderer.py`，这里的每个阶段都有对应：

| OpenGL 阶段 | 软件渲染器中的实现 |
|-------------|-------------------|
| 顶点着色器 | `transform_to_screen()` - MVP 变换 |
| 图元装配 | 无（直接三角光栅化） |
| 光栅化 | `rasterize_triangle()` - 扫描线 |
| 片元着色器 | `shade_fragment()` - Blinn-Phong + 纹理 |
| 深度测试 | `z_buffer` 比较 |
| 混合 | `framebuffer[y][x] = color` |

## 2. VAO / VBO / EBO 架构

### 2.1 核心概念

```
VBO (Vertex Buffer Object)    — 存储顶点数据的 GPU 缓冲区
VAO (Vertex Array Object)     — 记录 VBO 布局的"状态对象"
EBO (Element Buffer Object)   — 存储索引数据的 GPU 缓冲区
```

### 2.2 数据流关系

```
                      VAO
       ┌──────────────────────────────┐
       │  VBO 绑定  ← 位置 (location=0) │
       │  VBO 绑定  ← 法线 (location=1) │
       │  VBO 绑定  ← 纹理 (location=2) │
       │  EBO 绑定  ← 索引数据          │
       └──────────────────────────────┘
                    │
         glDrawArrays / glDrawElements
                    │
                    ▼
               GPU 管道
```

### 2.3 VBO 数据布局

**交错布局 (Interleaved)** — 推荐的布局方式：
```
[ pos.x pos.y pos.z norm.x norm.y norm.z uv.u uv.v ] × N
    ↑           ↑               ↑          ↑
   offset=0    offset=12      offset=24   offset=36
   stride=44   stride=44      stride=44   stride=44
```

**分离布局 (Separate)** — 每个属性一个 VBO：
```
VBO1: [ pos.x pos.y pos.z ] × N
VBO2: [ norm.x norm.y norm.z ] × N
VBO3: [ uv.u uv.v ] × N
```

### 2.4 完整绑定流程

```python
# 1. 生成 VAO 和 VBO
vao = glGenVertexArrays(1)
vbo = glGenBuffers(1)

# 2. 绑定 VAO — 记录后续状态
glBindVertexArray(vao)

# 3. 绑定 VBO → 上传数据
glBindBuffer(GL_ARRAY_BUFFER, vbo)
glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

# 4. 设置顶点属性指针（记录在 VAO 中）
# 位置: location=0, 3个float, stride=32
glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 32, ctypes.c_void_p(0))
glEnableVertexAttribArray(0)

# 法线: location=1, 3个float, stride=32, offset=12
glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 32, ctypes.c_void_p(12))
glEnableVertexAttribArray(1)

# UV: location=2, 2个float, stride=32, offset=24
glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 32, ctypes.c_void_p(24))
glEnableVertexAttribArray(2)

# 5. 解绑（VAO 已经记录了布局）
glBindVertexArray(0)
```

## 3. MVP 矩阵与坐标变换

### 3.1 五种坐标空间

```
对象空间 → 世界空间 → 视图空间 → 裁剪空间 → 标准化设备坐标 → 屏幕空间
   │           │           │          │         │              │
 Model     View      Projection  Perspective  Viewport       Viewport
 Matrix   Matrix     Matrix     Division     Transform      Transform
```

### 3.2 MVP 矩阵公式

```
gl_Position = Projection × View × Model × vec4(position, 1.0)
                │          │       │
                │          │       └── 对象 → 世界 (缩放/旋转/平移)
                │          └────────── 世界 → 视图 (摄像机)
                └───────────────────── 视图 → 裁剪 (透视/正交)
```

**透视投影矩阵：**
```
P = [ f/aspect    0              0                0      ]
    [    0        f              0                0      ]
    [    0        0    (far+near)/(near-far)   2*far*near/(near-far) ]
    [    0        0             -1                0      ]

其中 f = 1/tan(fov/2)
```

### 3.3 从裁剪空间到屏幕空间

```
裁剪坐标 (Clip)          NDC (归一化设备坐标)      屏幕坐标
  (x, y, z, w)  ──→  (x/w, y/w, z/w, 1)  ──→  (px, py, depth)
                         [-1,1]³               [0,width]×[0,height]
                  透视除法                    视口变换
```

### 3.4 Python 实现（与软渲染器一致）

```python
def look_at(eye, target, up):
    """构建视图矩阵 (View Matrix)"""
    f = normalize(target - eye)
    s = normalize(cross(f, up))
    u = normalize(cross(s, f))
    return Mat4([
        [s.x, s.y, s.z, -dot(s, eye)],
        [u.x, u.y, u.z, -dot(u, eye)],
        [-f.x, -f.y, -f.z, dot(f, eye)],
        [0, 0, 0, 1]
    ])

def perspective(fov, aspect, near, far):
    """构建透视投影矩阵"""
    f = 1.0 / math.tan(fov * 0.5)
    return Mat4([
        [f/aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far+near)/(near-far), 2*far*near/(near-far)],
        [0, 0, -1, 0]
    ])
```

## 4. 四元数与旋转

### 4.1 为什么需要四元数？

| 方法 | 问题 |
|------|------|
| 欧拉角 | 万向锁 (Gimbal Lock) |
| 旋转矩阵 | 插值困难，存 9 个值 |
| 轴角 | 插值不线性 |
| **四元数** ✅ | 无万向锁、易插值（球面线性插值 SLERP） |

### 4.2 四元数定义与操作

```
q = (w, x, y, z) = cos(θ/2) + (ax, ay, az)·sin(θ/2)
                          ↑ 绕单位轴 (ax,ay,az) 旋转 θ 角度

乘法:  q₁q₂ = (w₁w₂ - v₁·v₂, w₁v₂ + w₂v₁ + v₁×v₂)
旋转点: p' = q·p·q⁻¹          (p 是纯四元数 (0, x, y, z))
SLERP: q(t) = sin((1-t)α)/sin(α) · q₁ + sin(tα)/sin(α) · q₂
```

## 5. 顶点与片元着色器示例

### 5.1 最简顶点着色器

```glsl
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec2 aTexCoord;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

void main() {
    gl_Position = projection * view * model * vec4(aPos, 1.0);
}
```

### 5.2 最简片元着色器

```glsl
#version 330 core
out vec4 FragColor;

uniform vec3 objectColor;
uniform vec3 lightColor;

void main() {
    FragColor = vec4(objectColor * lightColor, 1.0);
}
```

### 5.3 几何着色器示例（实现法线可视化）

```glsl
#version 330 core
layout (triangles) in;
layout (line_strip, max_vertices = 6) out;

in vec3 vNormal[];  // 从顶点着色器传入的法线
uniform float normalLength = 0.1;

void main() {
    for (int i = 0; i < 3; i++) {
        // 起点: 三角形顶点
        gl_Position = gl_in[i].gl_Position;
        EmitVertex();
        // 终点: 沿法线方向延伸
        gl_Position = gl_in[i].gl_Position + 
                      vec4(vNormal[i], 0.0) * normalLength;
        EmitVertex();
        EndPrimitive();
    }
}
```

## 6. 完整 PyOpenGL 项目结构

```
lesson07_opengl_pipeline/
├── main.py              # 主程序
├── shaders/             # GLSL 着色器
│   ├── vertex.glsl
│   └── fragment.glsl
├── renderer.py          # 渲染器封装
├── camera.py            # 摄像机控制
├── mesh.py              # 网格/Mesh 类
└── utils.py             # 工具函数
```

## 7. 从软渲染到 OpenGL 的关键思维转换

| 概念 | 软渲染器 | OpenGL |
|------|---------|--------|
| 顶点变换 | CPU 上矩阵乘法 | 顶点着色器中 GPU 计算 |
| 光栅化 | 手动实现扫描线 | GPU 硬件光栅化 |
| 深度测试 | 手动 Z-buffer | GPU 自动深度测试 |
| 片段着色 | `shade_fragment()` | 片元着色器自定义 |
| 并行度 | 单线程逐像素 | 数千个着色器核心并行 |
| 数据传输 | 内存中 numpy 数组 | CPU→GPU 上传 (glBufferData) |
| 状态管理 | Python 变量 | OpenGL 状态机 (glEnable/glDisable) |

## 8. 调试技巧

### 8.1 常用调试工具
- **glGetError()** — 检查 OpenGL 错误（始终返回最后一个错误）
- **RenderDoc** — 免费 GPU 调试器，单帧捕获/着色器调试
- **Nvidia Nsight** — GPU 性能分析
- **OpenGL Debug Output** — OpenGL 4.3+ 直接输出错误信息

### 8.2 常见问题排查

| 症状 | 可能原因 |
|------|---------|
| 黑屏 | VAO/VBO 未正确绑定、着色器编译失败 |
| 全白 | uniform 未正确设置（默认 0） |
| 闪烁 | 深度测试未启用 (glEnable(GL_DEPTH_TEST)) |
| 三角形不见了 | 背面剔除太强、裁剪问题 |
| 性能很差 | 每帧都 glBufferData 上传数据 |
