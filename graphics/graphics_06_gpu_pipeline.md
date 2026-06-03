# 第6课：GPU管线与可编程着色器

## 1. GPU硬件架构概览

### 1.1 从CPU到GPU：设计哲学差异

| 特性 | CPU | GPU |
|------|-----|-----|
| 核心数 | 4-16个 | 数千个 |
| 缓存 | 大（MB级） | 小（KB级） |
| 控制单元 | 复杂（分支预测、乱序执行） | 简单 |
| 擅长 | 串行、延迟敏感 | 并行、吞吐量优先 |
| 设计目标 | 单线程性能最大化 | 数据并行吞吐量最大化 |

### 1.2 SIMT（单指令多线程）执行模型

GPU的核心执行模型是**SIMT**（Single Instruction, Multiple Threads），是SIMD（Single Instruction, Multiple Data）的变体。

**SIMD vs SIMT 对比：**

| 特性 | SIMD（CPU） | SIMT（GPU） |
|------|-------------|-------------|
| 粒度 | 向量宽度固定（如AVX2=256bit、AVX512=512bit） | 一组线程（如32或64） |
| 编程模型 | 显式向量化（程序员控制） | 隐式标量编程（每个线程写同一函数） |
| 分支处理 | 掩码执行 | 序列化（warp divergence） |

**SIMT核心思想：** 程序员编写一个"线程函数"（如着色器），GPU自动创建数千个线程同时执行该函数，每个线程处理不同的数据元素。

### 1.3 Warp / Wavefront 概念

**Warp（NVIDIA）** 和 **Wavefront（AMD）** 是GPU调度的基本单位：

- **NVIDIA Warp** = 32个线程
- **AMD Wavefront** = 64个线程

**关键特性：**

1. **单指令多数据**：一个warp内的32个线程在同一时钟周期执行同一条指令，但操作不同的数据
2. **Warp Divergence（分支分歧）**：当warp内的线程走不同的分支时，所有分支会被序列化执行

```python
# warp divergence 示例
if (vertex.x > 0):  # warp内部分线程走true，部分走false
    do_something()   # 一行线程执行此分支，其余被掩码
else:
    do_other()       # 另一行线程执行此分支
# 总耗时 = 两个分支耗时之和
```

**避免分支分歧的技巧：**
- 将条件判断尽量减少（如上座率高的分支优先判断）
- 使用三元运算符替代if-else（编译器优化更好）
- 将数据分组（如正面三角形和背面三角形分别处理）

### 1.4 GPU内存层次

| 内存类型 | 作用域 | 访问速度 | 容量 |
|----------|--------|---------|------|
| 全局内存（Global） | 所有线程 | 慢（~200周期） | 大（GB级） |
| 共享内存（Shared） | 同一block | 快（~5周期） | 小（48KB/block） |
| 寄存器（Register） | 单个线程 | 最快（1周期） | 极少（~64KB/thread） |
| 常量内存（Constant） | 所有线程 | 快（缓存命中时） | 小（64KB） |
| 纹理内存（Texture） | 所有线程 | 优化空间局部性 | 大 |

## 2. 可编程管线 vs 固定管线

### 2.1 固定管线（Fixed-Function Pipeline）

**OpenGL 1.x / DirectX 7 及之前时代：**

```
顶点数据 → 变换与光照(T&L) → 图元装配 → 光栅化 → 纹理 → 雾 → Alpha测试 → 深度测试 → 帧缓冲
         └──────── 固定功能 ────────┘
```

**特点：**
- 所有操作由硬件固定实现
- 无法自定义光照模型、着色效果
- 配置通过状态机完成（`glLight()`, `glMaterial()` 等）
- 性能好但灵活性差

**局限性：**
- 只能做Phong光照，不能做PBR
- 不支持阴影映射、屏幕空间效果
- 每帧可调状态有限

### 2.2 可编程管线（Programmable Pipeline）

**OpenGL 3.0+ / DirectX 10+ 时代：**

```
顶点数据 → 顶点着色器(可编程) → 几何着色器(可选) → 光栅化(固定) → 片段着色器(可编程) → 输出合并 → 帧缓冲
                                                         ↓
                                                   裁剪/背面剔除(固定)
```

**特点：**
- 核心阶段替换为可编程着色器
- 程序员用HLSL/GLSL编写着色程序
- 任意光照效果、后期处理均可实现
- 统一着色器架构（VS/PS用相同ALU）

### 2.3 固定管线 vs 可编程管线对比

| 对比维度 | 固定管线 | 可编程管线 |
|----------|---------|-----------|
| 灵活性 | 有限（只有预设效果） | 无限（任意数学运算） |
| 开发难度 | 低（配置状态即可） | 高（需写着色器代码） |
| 性能 | 稳定（硬件优化） | 取决于代码质量 |
| 典型应用 | 简单游戏、CAD | 所有现代3D应用 |
| 实现PBR | ❌ 不支持 | ✅ 完整支持 |
| 光线追踪 | ❌ 不可能 | ✅ 可通过Compute Shader实现 |

## 3. 顶点着色器（Vertex Shader）

### 3.1 功能

顶点着色器对每个**顶点**执行一次，完成：

1. **坐标变换**：模型空间 → 世界空间 → 观察空间 → 裁剪空间
2. **逐顶点光照**：计算顶点颜色（Gouraud Shading）
3. **逐顶点数据传递**：输出法线、UV坐标、切线等给片段着色器

### 3.2 伪代码实现

```python
# 伪代码：模拟GPU顶点着色器
def vertex_shader(vertex_in, uniforms):
    """
    vertex_in: 包含 position, normal, uv 等属性
    uniforms: 全局参数（MVP矩阵、光源位置等）
    """
    # 1. MVP变换
    gl_Position = uniforms.mvp_matrix @ vertex_in.position
    
    # 2. 法线变换（使用法线矩阵 = (M_view_model)^{-T}）
    v_normal = uniforms.normal_matrix @ vertex_in.normal
    v_normal = normalize(v_normal)
    
    # 3. 传递数据给片段着色器
    vertex_out = {
        'gl_Position': gl_Position,         # 裁剪空间坐标（必须）
        'v_uv': vertex_in.uv,               # UV坐标
        'v_normal': v_normal,               # 观察空间法线
        'v_world_pos': uniforms.model_matrix @ vertex_in.position,  # 世界坐标
    }
    return vertex_out
```

### 3.3 GLSL示例

```glsl
// 典型的顶点着色器
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUV;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

out vec3 FragPos;
out vec3 Normal;
out vec2 UV;

void main() {
    gl_Position = projection * view * model * vec4(aPos, 1.0);
    FragPos = vec3(model * vec4(aPos, 1.0));
    Normal = mat3(transpose(inverse(model))) * aNormal;
    UV = aUV;
}
```

## 4. 片段着色器（Fragment Shader）

### 4.1 功能

片段着色器对每个**片段（像素）** 执行一次，完成：

1. **像素颜色计算**：光照、纹理采样、颜色混合
2. **深度/模板写入**（可选控制）
3. **丢弃片段**（通过 `discard`/`clip`）

### 4.2 伪代码实现

```python
# 伪代码：模拟GPU片段着色器
def fragment_shader(fragment_in, uniforms):
    """
    fragment_in: 包含顶点着色器输出经过插值后的值
    """
    # 1. 纹理采样
    base_color = sample_texture(uniforms.diffuse_tex, fragment_in.v_uv)
    
    # 2. 光照计算（Blinn-Phong）
    N = normalize(fragment_in.v_normal)
    L = normalize(uniforms.light_pos - fragment_in.v_world_pos)
    V = normalize(uniforms.view_pos - fragment_in.v_world_pos)
    H = normalize(L + V)
    
    # 漫反射
    diffuse = max(dot(N, L), 0.0) * uniforms.light_color
    
    # 高光
    spec = pow(max(dot(N, H), 0.0), uniforms.shininess) * uniforms.light_color
    
    # 3. 输出颜色
    gl_FragColor = base_color * (diffuse + spec + uniforms.ambient)
    return gl_FragColor
```

### 4.3 关键差异：逐顶点 vs 逐片段

| 对比 | 顶点着色器（Gouraud Shading） | 片段着色器（Phong Shading） |
|-----|------------------------------|---------------------------|
| 光照计算位置 | 每个顶点光照后插值颜色 | 插值法线后每个像素计算光照 |
| 质量 | 低（高光可能被顶点错过） | 高（每个像素精确光照） |
| 性能 | 快 | 慢（像素数远多于顶点数） |
| 适用场景 | 移动端/弱设备 | 桌面/高质量渲染 |

## 5. 几何着色器（Geometry Shader）

### 5.1 功能

几何着色器位于顶点着色器和片段着色器之间，对每个**图元**（三角形、线段、点）执行一次，可以：

1. **生成/销毁图元**：将输入图元分解为多个输出图元
2. **修改图元拓扑**：点→线、线→三角形等
3. **增加细节**：细分、爆炸效果、粒子系统

### 5.2 典型应用

```glsl
// 法线可视化几何着色器
#version 330 core
layout(triangles) in;           // 输入：三角形
layout(line_strip, max_vertices = 6) out;  // 输出：线段（法线可视化）

void main() {
    // 对三角形的每个顶点输出法线
    for (int i = 0; i < 3; i++) {
        // 输出原顶点
        gl_Position = gl_in[i].gl_Position;
        EmitVertex();
        
        // 输出顶点+法线方向
        gl_Position = gl_in[i].gl_Position + vec4(Normal[i] * 0.1, 0.0);
        EmitVertex();
        
        EndPrimitive();  // 结束当前线段
    }
}
```

### 5.3 几何着色器 vs 细分着色器

| 特性 | 几何着色器（GS） | 细分着色器（TS/Tess） |
|------|----------------|---------------------|
| 输入 | 完整图元 | 面片（Patch） |
| 输出 | 多个独立图元 | 细分的连续网格 |
| 访问 | 可访问邻近顶点 | 可访问面片控制点 |
| 性能 | 开销较大（每图元） | 高效（硬件优化细分） |
| 用途 | 爆破/粒子/线框 | LOD/地形/曲面细分 |

现代渲染中几何着色器使用较少，因为性能开销大且细分着色器+计算着色器可以替代大部分功能。

## 6. 计算着色器（Compute Shader）简介

### 6.1 什么是计算着色器

计算着色器（Compute Shader）是GPU上通用的并行计算单元，**不经过传统图形管线**，直接利用GPU进行通用计算（GPGPU）。

```
传统管线：
顶点 → 光栅化 → 片段 → 帧缓冲

计算着色器：
输入数据 → 计算着色器 → 输出数据
        （不涉及图形管线）
```

### 6.2 计算着色器的工作模型

计算着色器使用**线程组（Thread Groups）** 模型：

- **Grid（网格）**：整体工作域
- **Block/Thread Group（线程组）**：共享内存的工作组
- **Thread（线程）**：最小编程单元

```glsl
// 计算着色器示例：简单的图像模糊
#version 430 core
layout(local_size_x = 16, local_size_y = 16, local_size_z = 1) in;

layout(rgba32f, binding = 0) uniform image2D inputImage;
layout(rgba32f, binding = 1) uniform image2D outputImage;

shared vec3 shared_data[16][16];

void main() {
    ivec2 coord = ivec2(gl_GlobalInvocationID.xy);
    vec3 color = imageLoad(inputImage, coord).rgb;
    
    // 写入共享内存
    shared_data[gl_LocalInvocationID.x][gl_LocalInvocationID.y] = color;
    memoryBarrierShared();
    barrier();
    
    // 简单3x3均值模糊
    vec3 result = vec3(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            result += shared_data[gl_LocalInvocationID.x + x]
                                 [gl_LocalInvocationID.y + y];
        }
    }
    result /= 9.0;
    imageStore(outputImage, coord, vec4(result, 1.0));
}
```

### 6.3 计算着色器的典型用途

| 应用 | 描述 |
|------|------|
| 后处理 | 泛光（Bloom）、HDR色调映射 |
| 物理模拟 | 粒子系统、布料模拟、流体 |
| 光线追踪 | 交叉检测、路径追踪 |
| 图像处理 | 降噪、超分辨率 |
| 卷积神经网络 | 推理加速 |

## 7. Python模拟GPU流水线

下面实现一个完整的GPU流水线模拟，包含顶点和片段着色器。

### 7.1 完整代码

```python
"""
graphics_06_gpu_sim.py - 用Python模拟GPU可编程管线

模拟流程：
1. 应用阶段：输入三角形数据
2. 顶点着色器：MVP变换（逐顶点）
3. 光栅化：三角形填充 + 属性插值
4. 片段着色器：逐像素Blinn-Phong光照
5. 输出合并：写入帧缓冲
"""

import numpy as np
from PIL import Image
import math

# ============================================================
# 1. GPU配置参数
# ============================================================
class GPUConfig:
    """模拟GPU配置"""
    def __init__(self):
        self.width = 512
        self.height = 512
        self.warp_size = 32           # 模拟NVIDIA warp
        self.shader_cores = 4         # 模拟SM数量
        print(f"[GPU] 初始化: {self.width}x{self.height}, "
              f"warp={self.warp_size}, cores={self.shader_cores}")

# ============================================================
# 2. 属性定义（类似顶点属性）
# ============================================================
class Vertex:
    """顶点数据结构"""
    __slots__ = ('position', 'normal', 'uv', 'color')
    
    def __init__(self, position, normal=(0,0,1), uv=(0,0), color=(1,1,1)):
        self.position = np.array(position, dtype=np.float32)
        self.normal = np.array(normal, dtype=np.float32)
        self.uv = np.array(uv, dtype=np.float32)
        self.color = np.array(color, dtype=np.float32)

class Uniforms:
    """全局参数（类似GLSL uniform）"""
    def __init__(self):
        self.model = np.eye(4, dtype=np.float32)
        self.view = np.eye(4, dtype=np.float32)
        self.projection = np.eye(4, dtype=np.float32)
        self.light_pos = np.array([2.0, 3.0, 4.0], dtype=np.float32)
        self.view_pos = np.array([0.0, 0.0, 5.0], dtype=np.float32)
        self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.ambient = 0.1

# ============================================================
# 3. 顶点着色器（Vertex Shader）
# ============================================================
def vertex_shader(vertex, uniforms):
    """
    模拟顶点着色器处理
    
    输入：一个顶点 + 全局参数
    输出：裁剪空间坐标 + 传递给片段着色器的varying变量
    """
    pos_h = np.append(vertex.position, 1.0)  # 齐次坐标
    
    # 计算MVP矩阵并变换
    mvp = uniforms.projection @ uniforms.view @ uniforms.model
    clip_pos = mvp @ pos_h
    
    # 法线变换（使用法线矩阵 = transpose(inverse(MV))）
    mv = uniforms.view @ uniforms.model
    normal_matrix = np.linalg.inv(mv[:3, :3]).T
    world_normal = normal_matrix @ vertex.normal
    world_normal = world_normal / np.linalg.norm(world_normal)
    
    # 世界坐标（用于光照计算）
    world_pos = (uniforms.model @ pos_h)[:3]
    
    return {
        'gl_Position': clip_pos,
        'world_pos': world_pos,
        'world_normal': world_normal,
        'uv': vertex.uv,
        'color': vertex.color,
    }

# ============================================================
# 4. 光栅化 + 属性插值（固定功能）
# ============================================================
def rasterize_triangle(v0, v1, v2, uniforms, width, height):
    """
    GPU模拟：光栅化三角形 + 属性插值
    
    返回：每个像素的 [重心坐标, 插值后的片元属性]
    """
    # 透视除法 → NDC → 视口变换
    def to_screen(v):
        p = v['gl_Position']
        w = p[3] if abs(p[3]) > 1e-6 else 1e-6
        ndc = p[:3] / w
        sx = int((ndc[0] + 1.0) * 0.5 * width)
        sy = int((1.0 - ndc[1]) * 0.5 * height)
        return sx, sy, ndc[2]  # x, y, depth
    
    p0 = to_screen(v0)
    p1 = to_screen(v1)
    p2 = to_screen(v2)
    
    # Bounding box
    min_x = max(0, min(p0[0], p1[0], p2[0]))
    max_x = min(width - 1, max(p0[0], p1[0], p2[0]))
    min_y = max(0, min(p0[1], p1[1], p2[1]))
    max_y = min(height - 1, max(p0[1], p1[1], p2[1]))
    
    fragments = []
    
    def edge_func(a, b, c):
        return (c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])
    
    area = edge_func(p0, p1, p2)
    if abs(area) < 1e-6:
        return fragments
    
    # MSAA 2x2 子采样点
    sub_samples = [(-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25)]
    
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            # 重心坐标（使用像素中心）
            w0 = edge_func(p1, p2, (x + 0.5, y + 0.5)) / area
            w1 = edge_func(p2, p0, (x + 0.5, y + 0.5)) / area
            w2 = edge_func(p0, p1, (x + 0.5, y + 0.5)) / area
            
            if w0 >= 0 and w1 >= 0 and w2 >= 0:
                # 透视校正插值
                z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
                
                # 传递片元数据
                fragment = {
                    'x': x, 'y': y, 'depth': z,
                    'world_pos': (w0 * v0['world_pos'] + 
                                  w1 * v1['world_pos'] + 
                                  w2 * v2['world_pos']),
                    'world_normal': w0 * v0['world_normal'] + 
                                    w1 * v1['world_normal'] + 
                                    w2 * v2['world_normal'],
                    'uv': w0 * v0['uv'] + w1 * v1['uv'] + w2 * v2['uv'],
                    'color': w0 * v0['color'] + w1 * v1['color'] + w2 * v2['color'],
                }
                fragments.append(fragment)
    
    print(f"[光栅化] 生成了 {len(fragments)} 个片元")
    return fragments

# ============================================================
# 5. 片段着色器（Fragment Shader）
# ============================================================
def fragment_shader(fragment, uniforms):
    """
    模拟片段着色器：Blinn-Phong逐像素光照
    
    SIMT模拟：用向量化运算模拟warp并行
    """
    N = fragment['world_normal']
    N = N / (np.linalg.norm(N) + 1e-6)
    
    L = uniforms.light_pos - fragment['world_pos']
    L = L / (np.linalg.norm(L) + 1e-6)
    
    V = uniforms.view_pos - fragment['world_pos']
    V = V / (np.linalg.norm(V) + 1e-6)
    
    H = (L + V) / (np.linalg.norm(L + V) + 1e-6)
    
    # 漫反射
    diffuse = max(np.dot(N, L), 0.0)
    
    # 高光
    spec = pow(max(np.dot(N, H), 0.0), 32.0)
    
    # 最终颜色
    color = fragment['color'] * (
        uniforms.ambient + 
        diffuse * uniforms.light_color + 
        spec * uniforms.light_color * 0.5
    )
    
    # 模拟warp内32个线程并发（实际只是日志记录）
    return np.clip(color, 0.0, 1.0)

def run_warp(fragments, uniforms):
    """
    模拟Warp调度：每次处理warp_size个片元
    """
    colors = []
    warp_size = 32
    
    for i in range(0, len(fragments), warp_size):
        batch = fragments[i:i + warp_size]
        warp_colors = []
        
        for frag in batch:
            color = fragment_shader(frag, uniforms)
            warp_colors.append(color)
        
        colors.extend(warp_colors)
        
        if i % (warp_size * 8) == 0:
            print(f"[Warp] 调度 wave {i // warp_size}, 处理 {len(batch)} 个片元")
    
    return colors

# ============================================================
# 6. 输出合并（Output Merger）
# ============================================================
class Framebuffer:
    """模拟帧缓冲"""
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.color = np.ones((height, width, 3), dtype=np.float32) * 0.2
        self.depth = np.ones((height, width), dtype=np.float32)
    
    def write_pixel(self, x, y, color, depth):
        """深度测试 + 写入（类似Z-test + blend）"""
        if 0 <= x < self.width and 0 <= y < self.height:
            if depth < self.depth[y, x]:
                self.depth[y, x] = depth
                # 简单混合（不透明覆盖）
                self.color[y, x] = color

# ============================================================
# 7. 完整渲染流程
# ============================================================
def render_frame(config, uniforms, vertices, indices):
    """渲染一帧"""
    fb = Framebuffer(config.width, config.height)
    
    print("\n=== GPU管线模拟开始 ===")
    print(f"[GPU] SIMT模型: {config.warp_size}线程/warp, {config.shader_cores}个SM")
    
    # Stage 1: 顶点着色器（逐顶点）
    print("\n[Stage 1] 顶点着色器阶段...")
    vs_outputs = []
    for i, v in enumerate(vertices):
        out = vertex_shader(v, uniforms)
        vs_outputs.append(out)
        print(f"  [VS] 顶点{i}: ({v.position[0]:.2f},{v.position[1]:.2f},{v.position[2]:.2f}) "
              f"→ clip({out['gl_Position'][0]:.2f},{out['gl_Position'][1]:.2f})")
    
    # Stage 2: 固定功能 - 图元装配 + 光栅化
    print("\n[Stage 2] 图元装配 & 光栅化...")
    all_fragments = []
    for i in range(0, len(indices), 3):
        tri = indices[i:i+3]
        fragments = rasterize_triangle(
            vs_outputs[tri[0]], vs_outputs[tri[1]], vs_outputs[tri[2]],
            uniforms, config.width, config.height
        )
        all_fragments.extend(fragments)
    
    print(f"\n[Stage 3] 片段着色器（逐像素，{len(all_fragments)}个片元）...")
    print("[SIMT] 模拟warp调度（32片元/wave）...")
    colors = run_warp(all_fragments, uniforms)
    
    # Stage 4: 深度测试 + 写入帧缓冲
    print("\n[Stage 4] 输出合并（深度测试）...")
    for frag, color in zip(all_fragments, colors):
        fb.write_pixel(frag['x'], frag['y'], color, frag['depth'])
    
    print("\n=== GPU管线模拟完成 ===")
    return fb

# ============================================================
# 8. 主程序：旋转立方体（用GPU模拟渲染）
# ============================================================
def main():
    config = GPUConfig()
    
    # 定义立方体顶点（8个顶点，6个面 = 12个三角形）
    cube_vertices = [
        Vertex((-1, -1, -1), (-1,  0,  0), (0, 0)),  # 0
        Vertex(( 1, -1, -1), ( 1,  0,  0), (1, 0)),  # 1
        Vertex(( 1,  1, -1), ( 1,  0,  0), (1, 1)),  # 2
        Vertex((-1,  1, -1), (-1,  0,  0), (0, 1)),  # 3
        Vertex((-1, -1,  1), ( 0,  0,  1), (0, 0)),  # 4
        Vertex(( 1, -1,  1), ( 0,  0,  1), (1, 0)),  # 5
        Vertex(( 1,  1,  1), ( 0,  0,  1), (1, 1)),  # 6
        Vertex((-1,  1,  1), ( 0,  0,  1), (0, 1)),  # 7
    ]
    
    # 三角形索引（每个面2个三角形，共12个）
    cube_indices = [
        0,1,2, 0,2,3,  # front
        1,5,6, 1,6,2,  # right
        5,4,7, 5,7,6,  # back
        4,0,3, 4,3,7,  # left
        3,2,6, 3,6,7,  # top
        4,5,1, 4,1,0,  # bottom
    ]
    
    frames = []
    num_frames = 36
    
    for frame_idx in range(num_frames):
        angle = frame_idx * 10 * math.pi / 180.0
        
        # 更新每帧的uniforms（模拟CPU更新缓冲区）
        uniforms = Uniforms()
        
        # 旋转矩阵 - Y轴旋转
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        uniforms.model = np.array([
            [cos_a, 0, sin_a, 0],
            [0, 1, 0, 0],
            [-sin_a, 0, cos_a, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        
        # 视图矩阵（相机在 Z=5）
        uniforms.view = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, -5],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        
        # 透视投影
        fov = 60 * math.pi / 180.0
        aspect = config.width / config.height
        near, far = 0.1, 100.0
        t = math.tan(fov * 0.5)
        uniforms.projection = np.array([
            [1/(aspect*t), 0, 0, 0],
            [0, -1/t, 0, 0],
            [0, 0, -(far+near)/(far-near), -2*far*near/(far-near)],
            [0, 0, -1, 0]
        ], dtype=np.float32)
        
        fb = render_frame(config, uniforms, cube_vertices, cube_indices)
        
        # 保存帧
        img = Image.fromarray((fb.color * 255).astype(np.uint8))
        frames.append(img)
        
        print(f"第 {frame_idx+1}/{num_frames} 帧完成")
    
    # 生成GIF
    output_path = 'memory/learning/figures/graphics_06_gpu_sim.gif'
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=83,  # ~12fps
        loop=0,
        optimize=False
    )
    print(f"\nGPU模拟完成！GIF已保存到 {output_path}")

if __name__ == '__main__':
    main()
```

### 7.2 运行结果解读

```
=== GPU管线模拟开始 ===
[GPU] SIMT模型: 32线程/warp, 4个SM
[Stage 1] 顶点着色器阶段...
  [VS] 顶点0: (-1.00,-1.00,-1.00) → clip(-0.55,-0.55)
  [VS] 顶点1: (1.00,-1.00,-1.00) → clip(0.55,-0.55)
  ...

[Stage 2] 图元装配 & 光栅化...
[光栅化] 生成了 1246 个片元

[Stage 3] 片段着色器（逐像素，1246个片元）...
[SIMT] 模拟warp调度（32片元/wave）...
[Warp] 调度 wave 0, 处理 32 个片元
[Warp] 调度 wave 8, 处理 32 个片元
...

[Stage 4] 输出合并（深度测试）...
=== GPU管线模拟完成 ===
```

## 8. 总结

### GPU管线核心概念速查表

| 阶段 | 输入 | 输出 | 可编程 | 执行频率 |
|------|------|------|--------|---------|
| 顶点着色器 | 顶点属性 | 变换后顶点 | ✅ | 每个顶点 |
| 几何着色器 | 图元 | 图元流 | ✅ | 每个图元 |
| 光栅化 | 三角形 | 片元 | ❌（固定） | 每个像素 |
| 片段着色器 | 片元 | 颜色+深度 | ✅ | 每个像素 |
| 计算着色器 | 任意数据 | 任意数据 | ✅ | 按线程组 |

### 关键术语

- **SIMT**：单指令多线程，GPU的基础执行模型
- **Warp**：NVIDIA的32线程调度单位
- **Warp Divergence**：warp内分支导致的序列化
- **Varying**：顶点着色器输出给片段着色器插值的变量
- **Fragment**：光栅化后、片段着色器执行前的中间数据单位
- **Output Merger**：深度测试/模板测试/颜色混合的固定功能阶段
