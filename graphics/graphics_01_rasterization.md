# 计算机图形学 第1课：光栅化与变换

> Phase 4 · 波次4 · 课时 1/6-8
> 日期: 2026-05-10

---

## 1. 图形管线（Graphics Pipeline）概览

图形管线是将 3D 场景转换为 2D 图像的分阶段流水线。现代 GPU 的管线大致如下：

```
应用层 (Application)
    ↓ 顶点数据 (vertices)
顶点着色器 (Vertex Shader)       ← 处理每个顶点，做 MVP 变换
    ↓ 变换后的顶点
曲面细分/几何着色器 (Optional)    ← 现代可选阶段
    ↓ 图元 (primitives: 点/线/三角形)
光栅化 (Rasterization)           ← 将图元转换为像素碎片(fragments)
    ↓ 碎片
片元着色器 (Fragment Shader)     ← 决定每个像素的最终颜色
    ↓ 着色后像素
测试与混合 (Depth/Stencil/Blending) ← Z-buffer测试、透明度混合
    ↓ 最终像素
帧缓冲 (Framebuffer)             ← 输出到屏幕
```

**核心思想**：把连续的几何（三角形、线段）变成离散的像素。

---

## 2. 齐次坐标（Homogeneous Coordinates）

### 为什么需要齐次坐标？

三维变换中，我们想用统一的矩阵乘法表示 **平移、旋转、缩放**。但平移不是线性变换：

```
[x']   [r11 r12 r13][x]      ← 旋转/缩放可以用 3x3 矩阵
[y'] = [r21 r22 r23][y]
[z']   [r31 r32 r33][z]

[x']   [x + tx]               ← 平移不能表示为 3x3 矩阵乘法
[y'] = [y + ty]
[z']   [z + tz]
```

**解决方案**：升维到齐次坐标，给 3D 点加一个额外的 w 分量：

```
点   (x, y, z, 1)       ← w=1 表示点
向量 (x, y, z, 0)       ← w=0 表示方向（平移不影响方向）
```

### 齐次坐标下的变换矩阵（4x4）

**平移矩阵**：
```
T = [1 0 0 tx]
    [0 1 0 ty]
    [0 0 1 tz]
    [0 0 0 1 ]
```

**缩放矩阵**：
```
S = [sx 0  0  0]
    [0  sy 0  0]
    [0  0  sz 0]
    [0  0  0  1]
```

**绕 X/Y/Z 轴旋转矩阵**：
```
Rx(θ) = [1  0    0   0]    Ry(θ) = [cosθ 0  sinθ 0]    Rz(θ) = [cosθ -sinθ 0 0]
        [0 cosθ -sinθ 0]            [0    1  0    0]            [sinθ  cosθ 0 0]
        [0 sinθ  cosθ 0]            [-sinθ 0  cosθ 0]           [0     0    1 0]
        [0  0    0   1]             [0    0  0    1]            [0     0    0 1]
```

**从齐次坐标回到 3D**：除以 w → `(x/w, y/w, z/w)`

透视投影会造成 w ≠ 1，从而产生"近大远小"效果。

---

## 3. 坐标空间与 MVP 变换

一个 3D 物体到屏幕上，要经过多个坐标空间：

```
模型空间 (Model/Object Space)
    ↓   M (Model Matrix) — 放置物体到世界
世界空间 (World Space)
    ↓   V (View Matrix) — 放置相机到原点，看向 -Z
相机/观察空间 (View/Eye Space)
    ↓   P (Projection Matrix) — 把视锥映射到 [-1,1]³ 的立方体
裁剪空间 (Clip Space) — 齐次坐标，进行裁剪
    ↓  透视除法 (w 除法)
NDC 空间 (Normalized Device Coordinates) — [-1, 1]³
    ↓  视口变换 (Viewport Transform)
屏幕空间 (Screen Space) — 像素坐标
```

### 模型矩阵（Model Matrix）

将物体从自身坐标系变换到世界坐标系。通常 = `T × R × S`（先缩放，再旋转，再平移）。

```python
def model_matrix(tx, ty, tz, rx, ry, rz, sx, sy, sz):
    """构建模型矩阵：平移 × 旋转 × 缩放"""
    T = translate(tx, ty, tz)
    R = rotate_x(rx) @ rotate_y(ry) @ rotate_z(rz)
    S = scale(sx, sy, sz)
    return T @ R @ S  # 注意顺序：先缩放，再旋转，再平移
```

### 视图矩阵（View Matrix）

把相机放到原点，看向 -Z 方向。已知相机位置 `eye`、目标 `target`、上方向 `up`：

```python
def look_at(eye, target, up):
    """构建视图矩阵"""
    f = normalize(target - eye)    # 前向
    s = normalize(cross(f, up))    # 右向（侧向）
    u = cross(s, f)                # 上方向
    
    # 先旋转到相机方向，再平移到原点
    return np.array([
        [ s[0],  s[1],  s[2], -dot(s, eye)],
        [ u[0],  u[1],  u[2], -dot(u, eye)],
        [-f[0], -f[1], -f[2],  dot(f, eye)],
        [ 0,     0,     0,     1          ]
    ])
```

### 投影矩阵（Projection Matrix）

**正交投影**：无视深度，平行投影。适合 CAD、2D 游戏。

```
P_ortho = [2/(r-l)  0        0        -(r+l)/(r-l)]
          [0        2/(t-b)  0        -(t+b)/(t-b)]
          [0        0        -2/(f-n) -(f+n)/(f-n)]
          [0        0        0         1           ]
```

**透视投影**：近大远小，模拟人眼。

```
P_persp = [f/aspect  0     0           0        ]   f = 1/tan(fovY/2)
          [0         f     0           0        ]
          [0         0  (f+n)/(n-f)  2fn/(n-f) ]
          [0         0    -1          0        ]
```

透视投影的关键技巧：**挤压**远平面，让 w 变得和 z 成正比，透视除法后产生近大远小。

---

## 4. 光栅化（Rasterization）

### 4.1 Bresenham 画线算法

核心思想：**只用整数加减法**，不用浮点乘法。判断下一个像素该往哪个方向走。

```python
def bresenham_line(x0, y0, x1, y1):
    """Bresenham 画线算法 — 仅整数运算"""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return points
```

**原理**：用误差项 `err` 跟踪实际直线和像素网格之间的距离。每次沿一个方向走一步，当误差累积超过阈值时同时走另一个方向。这是计算机图形学中最优雅的算法之一。

### 4.2 三角形填充

填充三角形有多种方法。最常用的是 **扫描线算法**：

1. 将三角形按 Y 坐标排序（上/中/下）
2. 用 Bresenham 找出左右边界
3. 逐行填充两边界之间的像素

更简单的实现是 **Bounding Box + 重心坐标**：

```python
def rasterize_triangle(v0, v1, v2, image, color):
    """用 Bounding Box 填充三角形"""
    # AABB包围盒
    xmin = int(min(v0[0], v1[0], v2[0]))
    xmax = int(max(v0[0], v1[0], v2[0]))
    ymin = int(min(v0[1], v1[1], v2[1]))
    ymax = int(max(v0[1], v1[1], v2[1]))
    
    for y in range(ymin, ymax + 1):
        for x in range(xmin, xmax + 1):
            if point_in_triangle((x, y), v0, v1, v2):
                image[y, x] = color
```

### 4.3 重心坐标

点 `P` 在三角形 `(A,B,C)` 内的条件是存在 `α, β, γ ≥ 0` 且 `α+β+γ=1` 使得：

```
P = α·A + β·B + γ·C
```

计算重心坐标：
```python
def barycentric(p, a, b, c):
    """计算重心坐标 (α, β, γ)"""
    v0 = b - a
    v1 = c - a
    v2 = p - a
    d00 = dot(v0, v0)
    d01 = dot(v0, v1)
    d11 = dot(v1, v1)
    d20 = dot(v2, v0)
    d21 = dot(v2, v1)
    denom = d00 * d11 - d01 * d01
    beta = (d11 * d20 - d01 * d21) / denom
    gamma = (d00 * d21 - d01 * d20) / denom
    alpha = 1.0 - beta - gamma
    return alpha, beta, gamma
```

如果 `alpha ≥ 0` 且 `beta ≥ 0` 且 `gamma ≥ 0`，点在三角形内部。

### 4.4 Z-buffer（深度缓冲）

解决多个三角形重叠时谁在前面的问题。对每个像素记录当前最小的 Z 值，新片段只有 Z 更小才更新。

```python
zbuffer = [[float('inf')] * width for _ in range(height)]

# 对每个三角形：
for each fragment (x, y, z):
    if z < zbuffer[y][x]:
        zbuffer[y][x] = z
        framebuffer[y][x] = color
```

---

## 5. 完整实战：软件渲染旋转立方体

> 用纯 Python + Pillow 实现一个线框旋转立方体渲染器。
> 完整覆盖：MVP 变换 → 齐次坐标 → 光栅化 → 屏幕输出。

```python
# -*- coding: utf-8 -*-
"""
软件渲染器：线框旋转立方体
- 纯 Python + Pillow 实现
- 完整的 MVP 变换（模型/视图/投影）
- Bresenham 画线
- 齐次坐标变换
"""

import math
import numpy as np
from PIL import Image

# ============================================================
# 基础矩阵工具
# ============================================================

def translate(tx, ty, tz):
    """平移矩阵"""
    return np.array([
        [1, 0, 0, tx],
        [0, 1, 0, ty],
        [0, 0, 1, tz],
        [0, 0, 0,  1]
    ], dtype=float)

def scale(sx, sy, sz):
    """缩放矩阵"""
    return np.array([
        [sx, 0,  0,  0],
        [0,  sy, 0,  0],
        [0,  0,  sz, 0],
        [0,  0,  0,  1]
    ], dtype=float)

def rotate_x(angle):
    """绕 X 轴旋转（弧度）"""
    c, s = math.cos(angle), math.sin(angle)
    return np.array([
        [1, 0,  0, 0],
        [0, c, -s, 0],
        [0, s,  c, 0],
        [0, 0,  0, 1]
    ], dtype=float)

def rotate_y(angle):
    """绕 Y 轴旋转（弧度）"""
    c, s = math.cos(angle), math.sin(angle)
    return np.array([
        [ c, 0, s, 0],
        [ 0, 1, 0, 0],
        [-s, 0, c, 0],
        [ 0, 0, 0, 1]
    ], dtype=float)

def rotate_z(angle):
    """绕 Z 轴旋转（弧度）"""
    c, s = math.cos(angle), math.sin(angle)
    return np.array([
        [c, -s, 0, 0],
        [s,  c, 0, 0],
        [0,  0, 1, 0],
        [0,  0, 0, 1]
    ], dtype=float)

def look_at(eye, target, up):
    """视图矩阵：将相机放置到原点"""
    f = np.array(target) - np.array(eye)
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    return np.array([
        [ s[0],  s[1],  s[2], -np.dot(s, eye)],
        [ u[0],  u[1],  u[2], -np.dot(u, eye)],
        [-f[0], -f[1], -f[2],  np.dot(f, eye)],
        [ 0,     0,     0,     1             ]
    ], dtype=float)

def perspective(fov_y, aspect, near, far):
    """透视投影矩阵"""
    f = 1.0 / math.tan(fov_y / 2.0)
    return np.array([
        [f / aspect, 0, 0,                           0],
        [0,          f, 0,                           0],
        [0,          0, (far + near) / (near - far),  2 * far * near / (near - far)],
        [0,          0, -1,                           0]
    ], dtype=float)

def mvp_matrix(eye, target, up, fov_y, aspect, near, far):
    """组合 MVP = P × V × M（这里 M 固定，调用时再乘）"""
    V = look_at(eye, target, up)
    P = perspective(fov_y, aspect, near, far)
    return P @ V  # 先乘以 V，再乘以 P

# ============================================================
# 光栅化：Bresenham 画线
# ============================================================

def bresenham_line(x0, y0, x1, y1):
    """Bresenham 画线算法 — 整数运算，返回像素坐标列表"""
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    
    while True:
        points.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return points

# ============================================================
# 立方体定义
# ============================================================

def make_cube():
    """
    定义一个中心在原点的立方体，边长 2。
    返回顶点列表和边列表。
    """
    # 8 个顶点 (x, y, z, 1) — 齐次坐标
    vertices = np.array([
        [-1, -1, -1, 1],   # 0
        [ 1, -1, -1, 1],   # 1
        [ 1,  1, -1, 1],   # 2
        [-1,  1, -1, 1],   # 3
        [-1, -1,  1, 1],   # 4
        [ 1, -1,  1, 1],   # 5
        [ 1,  1,  1, 1],   # 6
        [-1,  1,  1, 1],   # 7
    ], dtype=float).T  # 4x8，每一列是一个顶点

    # 12 条边（顶点索引对）
    edges = [
        # 前面 (z=-1)
        (0, 1), (1, 2), (2, 3), (3, 0),
        # 后面 (z=1)
        (4, 5), (5, 6), (6, 7), (7, 4),
        # 连接前后
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    return vertices, edges

# ============================================================
# 渲染器主函数
# ============================================================

def render_frame(width, height, vertices_3d, edges, model_mat):
    """
    渲染一帧：MVP 变换 → 透视除法 → 视口变换 → 画线
    vertices_3d: 4×8 numpy 数组，齐次坐标 (x, y, z, 1)
    edges: 顶点索引对列表
    model_mat: 模型矩阵
    """
    # --- 1. 视口参数 ---
    aspect = width / height
    fov_y = math.radians(60)
    near = 0.1
    far = 100.0
    
    # 相机位置：从 (3, 3, 3) 观察原点
    eye = np.array([3, 3, 3], dtype=float)
    target = np.array([0, 0, 0], dtype=float)
    up = np.array([0, 1, 0], dtype=float)
    
    # --- 2. MVP 变换 ---
    M = model_mat                         # 模型矩阵
    V = look_at(eye, target, up)          # 视图矩阵
    P = perspective(fov_y, aspect, near, far)  # 投影矩阵
    
    # 应用 MVP 变换：P * V * M * vertex
    mvp = P @ V @ M
    clip_verts = mvp @ vertices_3d  # 4×8 矩阵乘法
    
    # --- 3. 透视除法和视口变换 ---
    screen_verts = []
    for i in range(clip_verts.shape[1]):
        x, y, z, w = clip_verts[:, i]
        if abs(w) < 1e-10:
            continue  # 跳过无效顶点（越界时保护）
        
        # 透视除法：从裁剪空间到 NDC [-1, 1]
        ndc_x = x / w
        ndc_y = y / w
        
        # 视口变换：NDC [-1,1] → 屏幕像素 [0, w] × [0, h]
        screen_x = (ndc_x + 1) * 0.5 * width
        screen_y = (1 - ndc_y) * 0.5 * height  # Y翻转（NDC Y向上，屏幕Y向下）
        
        screen_verts.append((int(screen_x), int(screen_y)))
    
    # --- 4. 创建帧缓冲 ---
    img = Image.new("RGB", (width, height), (20, 20, 30))
    pixels = img.load()
    
    # --- 5. 画线（Bresenham） ---
    color = (100, 200, 255)  # 浅蓝色
    for i0, i1 in edges:
        if i0 >= len(screen_verts) or i1 >= len(screen_verts):
            continue
        x0, y0 = screen_verts[i0]
        x1, y1 = screen_verts[i1]
        for px, py in bresenham_line(x0, y0, x1, y1):
            if 0 <= px < width and 0 <= py < height:
                pixels[px, py] = color
    
    return img

# ============================================================
# 主程序：生成旋转立方体动画（多帧 GIF）
# ============================================================

def main():
    """生成旋转立方体的 GIF 动画"""
    width, height = 400, 400
    frames = []
    num_frames = 36  # 每10度一帧，一圈36帧
    
    vertices, edges = make_cube()
    
    for i in range(num_frames):
        angle = 2 * math.pi * i / num_frames
        
        # 绕 Y 轴和 X 轴同时旋转，更立体
        model = rotate_y(angle) @ rotate_x(angle * 0.3)
        
        frame = render_frame(width, height, vertices, edges, model)
        frames.append(frame)
        print(f"  渲染帧 {i+1}/{num_frames} ...")
    
    # 保存为 GIF
    output_path = "memory/learning/figures/graphics_01_cube.gif"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=50,     # 每帧50ms ≈ 20fps
        loop=0
    )
    print(f"\n✅ GIF 已保存: {output_path}")
    
    # 也保存一帧作为预览
    preview_path = "memory/learning/figures/graphics_01_cube_preview.png"
    frames[0].save(preview_path)
    print(f"✅ 预览帧: {preview_path}")

if __name__ == "__main__":
    main()
```

### 运行结果预览

运行上述代码将生成一个绕 Y 轴和 X 轴旋转的线框立方体 GIF 动画，浅蓝色线条，深色背景。

---

## 6. 深入理解：关键概念总结

| 概念 | 要点 |
|------|------|
| **图形管线** | 应用→顶点着色→光栅化→片元着色→测试混合→帧缓冲 |
| **齐次坐标** | 用 (x,y,z,w) 统一表示平移/旋转/缩放，w=1 是点，w=0 是方向 |
| **MVP** | Model 放物体到世界，View 放相机到原点，Projection 做近大远小 |
| **透视投影** | 让 w 和 z 成正比，透视除法后产生透视效果 |
| **Bresenham** | 纯整数运算画线，误差驱动，GPU 硬件的核心 |
| **视口变换** | NDC [-1,1] 映射到屏幕像素坐标，Y 轴翻转 |

---

## 7. 扩展思考

1. **三角形填充着色**：可以用重心坐标插值每个像素的颜色（Gouraud着色）
2. **Z-buffer**：线框不需要，填充三角形时必须用，否则后画的三角形会覆盖前面的
3. **背面剔除**：计算三角形法线，如果背离相机直接丢弃，可省一半三角形
4. **纹理映射**：重心坐标还可以插值 UV 坐标，采样纹理
5. **抗锯齿**：每个像素取多个采样点（SSAA/MSAA）平滑锯齿边缘
6. **矩阵乘法顺序**：OpenGL/DirectX 中列优先 vs 行优先，本笔记用行优先（数学标准）

> 下一课预告：光照与着色 — Phong 模型、Gouraud/Flat 着色、纹理映射
