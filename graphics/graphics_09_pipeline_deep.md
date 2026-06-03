# 图形渲染管线深度解析：软件渲染 vs GPU Pipeline

## 1. 渲染管线全景

### 1.1 传统固定管线（Fixed-Function Pipeline）

```
顶点数据 → 顶点变换 → 图元装配 → 光栅化 → 片段处理 → 帧缓冲
  │           │           │          │         │         │
  │  MVP变换    │  组装三角形 │  像素化   │ 纹理/颜色 │  写入
  │  观察空间    │                                │  深度测试
  │  投影变换    │                                │  混合
                                              │  Stencil
```

### 1.2 可编程管线（Programmable Pipeline）

```
                  Vertex Shader (程序员控制)
                        ↓
                  光栅化（固定功能）
                        ↓
                  Fragment Shader (程序员控制)
                        ↓
                  逐片段操作（固定功能）
                        ↓
                    Frame Buffer
```

---

## 2. 管线阶段详解

### 2.1 顶点处理（Vertex Processing）

**目标：** 将模型空间顶点 → 屏幕空间坐标

```
模型空间 → 世界空间 → 观察空间 → 裁剪空间 → NDC → 屏幕空间
   │         │           │          │        │       │
  Model    View      Projection   W-divide 视口变换
```

**MVP 矩阵链：**

```c
// 顶点变换计算
vec4 clip_pos = projection * view * model * vec4(pos, 1.0);

// 透视除法
vec3 ndc = clip_pos.xyz / clip_pos.w;  // [-1, 1]³

// 视口变换
screen_x = (ndc.x * 0.5 + 0.5) * viewport_width;
screen_y = (1.0 - (ndc.y * 0.5 + 0.5)) * viewport_height;
```

**软件渲染器实现：**

```c
void process_vertex(Vertex* v, const Mat4& mvp, const Viewport& vp) {
    // 1. MVP 变换
    Vec4 clip = mvp * Vec4(v->pos, 1.0f);

    // 2. 齐次裁剪（Clipping）
    if (clip.w <= 0) { v->discard = true; return; }

    // 3. 透视除法 → NDC
    Vec3 ndc = clip.xyz / clip.w;

    // 4. 视口变换 → 屏幕坐标
    v->screen_x = (ndc.x * 0.5f + 0.5f) * vp.width;
    v->screen_y = (1.0f - (ndc.y * 0.5f + 0.5f)) * vp.height;
    v->depth = ndc.z;  // 用于深度测试
}
```

### 2.2 图元装配（Primitive Assembly）

三种基本图元：

```
点（Point）    → 单个像素
线（Line）     → DDA/Bresenham 直线扫描转换
三角形（Triangle） → 最常用的渲染图元
```

**三角形装配示例：**

```c
struct Triangle {
    Vertex v0, v1, v2;
    BoundingBox bbox;    // 2D 包围盒
    float area;          // 用于重心坐标计算
};

Triangle assemble_triangle(Vertex* verts, int i0, int i1, int i2) {
    Triangle tri;
    tri.v0 = verts[i0];
    tri.v1 = verts[i1];
    tri.v2 = verts[i2];

    // 计算 2D 包围盒（加速遍历）
    tri.bbox.min_x = min(v0.x, v1.x, v2.x);
    tri.bbox.max_x = max(v0.x, v1.x, v2.x);
    tri.bbox.min_y = min(v0.y, v1.y, v2.y);
    tri.bbox.max_y = max(v0.y, v1.y, v2.y);

    // 三角形面积（2 倍）
    tri.area = cross(v1 - v0, v2 - v0);
    return tri;
}
```

### 2.3 光栅化（Rasterization）

**核心问题：** 给定三个顶点，找出所有在三角形内部的像素。

#### 方法1：扫描线算法

```
for each scanline y from min_y to max_y:
    计算扫描线与三角形边的交点
    对交点排序（左到右）
    对两个交点之间的所有像素着色
```

#### 方法2：重心坐标（本文使用）

```c
// 判断像素是否在三角形内
bool inside_triangle(const Triangle& t, int x, int y) {
    auto edge = [](const Vertex& a, const Vertex& b, int x, int y) {
        return (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x);
    };
    // 三个边向量方向一致
    float e0 = edge(t.v0, t.v1, x, y);
    float e1 = edge(t.v1, t.v2, x, y);
    float e2 = edge(t.v2, t.v0, x, y);
    return (e0 >= 0 && e1 >= 0 && e2 >= 0)
        || (e0 <= 0 && e1 <= 0 && e2 <= 0);
}

// 计算重心坐标
Vec3 barycentric(const Triangle& t, int x, int y) {
    float denom = 1.0f / t.area;
    float u = edge(t.v1, t.v2, x, y) * denom;
    float v = edge(t.v2, t.v0, x, y) * denom;
    float w = 1.0f - u - v;
    return {u, v, w};
}
```

**性能优化：** 分层遍历（Tile-based）

```
将屏幕分为 16×16 的 tile
对每个 tile：
  1. 快速测试是否与三角形相交（使用包围盒）
  2. 如果相交，再测试内部每个像素
```

### 2.4 片段着色（Fragment Shader）

```c
// 插值顶点属性
Vec3 interpolate_barycentric(
    const Vec3& a, const Vec3& b, const Vec3& c,
    const Vec3& bc  // 重心坐标
) {
    return a * bc.x + b * bc.y + c * bc.z;
}

// 简单片段着色器
Color fragment_shader(const FragmentInput& input) {
    // 纹理采样
    Color tex_color = texture_sample(input.uv, input.texture);

    // 光照计算（Phong 模型）
    Vec3 N = normalize(input.normal);
    Vec3 L = normalize(light_pos - input.world_pos);
    float diff = max(dot(N, L), 0.0f);

    Vec3 V = normalize(camera_pos - input.world_pos);
    Vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0f), shininess);

    Color final = ambient + diff * diffuse_color + spec * specular_color;
    final *= tex_color;
    return final;
}
```

**透视正确插值：**

```c
// 在屏幕空间线性插值 UV 是不正确的！
// 必须在透视投影空间进行插值：

// 1. 在裁剪空间插值：uv/w 和 1/w
// 2. 逐像素执行透视除法

float interpolated_uv = (uv0/w0 * alpha + uv1/w1 * beta + uv2/w2 * gamma)
    / (1.0f/w0 * alpha + 1.0f/w1 * beta + 1.0f/w2 * gamma);
```

### 2.5 逐片段操作

```c
// 深度测试
bool depth_test(float fragment_depth) {
    float stored = depth_buffer[pixel_x][pixel_y];
    if (fragment_depth <= stored) {  // 默认 Less
        depth_buffer[pixel_x][pixel_y] = fragment_depth;
        return true;  // 通过，写入颜色缓冲
    }
    return false;  // 丢弃片段
}

// Alpha 混合
Color alpha_blend(Color src, Color dst) {
    float a = src.a;
    return Color(
        src.r * a + dst.r * (1 - a),
        src.g * a + dst.g * (1 - a),
        src.b * a + dst.b * (1 - a),
        src.a + dst.a * (1 - a)
    );
}
```

---

## 3. OpenGL 管线与软件渲染器对比

### 3.1 对应关系

| 软件渲染阶段 | OpenGL 对应 | 控制权 |
|-------------|-------------|--------|
| 顶点变换 MVP | Vertex Shader | 可编程 |
| 透视除法 | 固定功能 | 固定 |
| 视口变换 | glViewport | 配置 |
| 背面剔除 | glCullFace | 配置 |
| 光栅化 | Fixed Rasterizer | 固定 |
| 属性插值 | Varying 变量 | 可配置 |
| 纹理采样 | Texture Unit | 配置 |
| 片段着色 | Fragment Shader | 可编程 |
| 深度测试 | glDepthFunc | 配置 |
| 混合 | glBlendFunc | 配置 |
| 模板测试 | glStencilFunc | 配置 |
| 颜色缓冲 | Framebuffer | 配置 |

### 3.2 架构差异

```
软件渲染器（CPU）:
┌──────────────────────────────────┐
│   统一着色器模型（手动实现）         │
│   逐三角形光栅化                   │
│   逐像素深度测试                    │
│   线性顺序执行                      │
└──────────────────────────────────┘

GPU 管线:
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Vertex│→│Raster│→│Fragment│→│ROP  │
│Shader│ │izer  │ │Shader  │ │      │
│SIMT  │ │固定  │ │SIMT    │ │固定  │
│并行  │ │功能  │ │并行    │ │功能  │
└──────┘ └──────┘ └──────┘ └──────┘
    ↑ 双缓冲/流水线设计，极高吞吐
```

### 3.3 GPU vs CPU 性能差异根源

```
CPU 一次处理 1-8 个顶点/像素（SIMD）
GPU 一次处理 32-64 个顶点/像素（Warp/Wavefront）
GPU 有 1000+ 个核心同时运行

差异：
  CPU 侧重：延迟优化（L1 cache, branch pred）
  GPU 侧重：吞吐优化（大量并行 ALU, SIMT）
```

---

## 4. 渲染管线优化策略

### 4.1 CPU 端优化

| 优化 | 效果 | 实现 |
|------|------|------|
| 背面剔除 | 减少 ~50% 三角形 | 检查法线方向 |
| 包围盒测试 | 减少开销 | 跳过屏幕外三角形 |
| 平铺渲染 | 减少 cache miss | 16×16 tile 遍历 |
| 顶点预变换 | 减少重复计算 | 顶点缓存 |
| 并行化 | 多核利用 | OpenMP/TBB 分 tile |

### 4.2 软件渲染器中使用的算法

```
光栅化策略选择：
  84% → Tile 遍历（cache friendly）
  12% → 扫描线（简单实现）
   4% → 像素精确（调试用）

深度缓冲：
  float32 (4KB per fragment)
  hierarchical-z → 快速拒绝 tile

纹理采样：
  点采样（最近邻）: ~3 cycles
  双线性插值:     ~6 cycles
  三线性 Mipmap:  ~12 cycles
```

### 4.3 OpenGL 特有特性

| 特性 | 描述 | 软件替代 |
|------|------|----------|
| Mipmap | 自动 LOD 纹理选择 | 手动采样不同级别 |
| FBO | 渲染到纹理 | 切换 framebuffer |
| Instancing | 单次调用渲染多个对象 | 循环绘制 |
| VBO/VAO | 顶点数据管理 | 直接传入数组 |
| Shader | 可编程 | 回调函数 |

---

## 5. 启发与认知

### 5.1 渲染管线设计原则

1. **早期退出**：尽早丢弃不可见片段（背面剔除、深度测试）
2. **空间局部性**：平铺遍历比逐行遍历 cache 友好
3. **并行友好**：每个片段独立计算，天然可并行
4. **精度控制**：透视正确插值是画质 vs 性能的权衡

### 5.2 从软件渲染到 GPU 的理解

```
软件渲染器 == GPU 的行为模型
  ↓
理解软件渲染器后：
  - 知道每个 GPU 指令的代价
  - 知道为什么 batch 提交更好
  - 知道 uniform vs varying vs attribute 的区别
  - 知道为什么 fragment shader 比 vertex shader 昂贵
  - 知道为什么纹理采样是大型开销

总结：
  软件渲染 ≈ 概念模型（理解"what"）
  OpenGL ≈ 工业标准（理解"how"）
  Vulkan ≈ 底层控制（理解"why"）
```

### 5.3 主要文件路径

```
D:\kai_knowledge\learning\
├── graphics_01_rasterization.md   基础绘制
├── graphics_02_triangle_raster.md 三角形填充
├── graphics_03_lighting.md       光照模型
├── graphics_04_texture.md        纹理映射
├── graphics_05_shadow.md         阴影
├── graphics_06_gpu_pipeline.md   GPU 管线
├── graphics_07_pbr.md            PBR
├── graphics_08_gpu_api.md        GPU API
└── graphics_09_pipeline_deep.md  本篇（深入对比）
├── software_renderer.py         基础软渲染器
├── software_renderer_v2.py      增强版
└── soft_renderer.py             最终版
```
