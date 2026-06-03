# 计算机图形学 第2课：三角形填充与光栅化

> Phase 4 · 波次4 · 课时 2/6-8
> 日期: 2026-05-10

---

## 1. 为什么是三角形？

三角形是计算机图形学的基本图元，原因如下：
- **任何多边形都可以分解为三角形**（三角剖分）
- **三个点确定一个平面** — 保证三角形永远是平的（不像四边形可能翘曲）
- **重心坐标插值简单可靠** — 颜色、法线、深度、UV 都可以插值
- **GPU 硬件为三角形优化** — 现代 GPU 内部就是三角形光栅化引擎

```text
四边形 → 分成2个三角形    五边形 → 分成3个三角形
  A───D                    A───E
  │\  │                    │\  │
  │ \ │                    │ \ │
  │  \│                    │  \│
  B───C                    B───D
                           │  /│
                           │ / │
                           │/  │
                           C───┘
```

---

## 2. 三角形光栅化算法

### 2.1 Bounding Box + Inside Test（包围盒 + 内点测试）

最直观的方法：找到三角形的 AABB（轴对齐包围盒），遍历所有像素，测试是否在三角形内。

```python
def rasterize_triangle_bbox(v0, v1, v2, pixels, width, height, color, zbuffer=None, z_func=None):
    """包围盒法填充三角形"""
    # 计算 AABB
    xmin = max(0, int(min(v0[0], v1[0], v2[0])))
    xmax = min(width - 1, int(max(v0[0], v1[0], v2[0])))
    ymin = max(0, int(min(v0[1], v1[1], v2[1])))
    ymax = min(height - 1, int(max(v0[1], v1[1], v2[1])))
    
    for y in range(ymin, ymax + 1):
        for x in range(xmin, xmax + 1):
            alpha, beta, gamma = barycentric((x, y), v0, v1, v2)
            if alpha >= 0 and beta >= 0 and gamma >= 0:
                if zbuffer is not None:
                    # 插值深度
                    z = alpha * z0 + beta * z1 + gamma * z2
                    if z >= zbuffer[y][x]:
                        continue
                    zbuffer[y][x] = z
                pixels[x, y] = color
```

**优点**：简单，适合软件渲染器教学。
**缺点**：空像素多，效率低（尤其对于细长三角形）。

### 2.2 重心坐标（Barycentric Coordinates）

**定义**：三角形 ABC 内任意一点 P 可以表示为：

```
P = α·A + β·B + γ·C, 其中 α + β + γ = 1
```

P 在三角形内部 ⟺ α ≥ 0, β ≥ 0, γ ≥ 0

**几何意义**：重心坐标是**面积比**。

```
α = area(PBC) / area(ABC)
β = area(APC) / area(ABC)
γ = area(ABP) / area(ABC)
```

**为什么有用**：
- 判断点是否在三角形内
- 插值任何顶点属性（颜色、深度、法线、UV）
- 平滑过渡，无接缝

**面积法实现（更稳定）**：

```python
def barycentric(p, a, b, c):
    """重心坐标 — 使用叉积法（稳定，避免除法退化为奇异情况）"""
    # 叉积 = 平行四边形的有向面积 × 2
    v0 = b - a  # AB
    v1 = c - a  # AC
    v2 = p - a  # AP
    
    d00 = np.dot(v0, v0)
    d01 = np.dot(v0, v1)
    d11 = np.dot(v1, v1)
    d20 = np.dot(v2, v0)
    d21 = np.dot(v2, v1)
    
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return (-1, -1, -1)  # 退化三角形
    
    beta = (d11 * d20 - d01 * d21) / denom
    gamma = (d00 * d21 - d01 * d20) / denom
    alpha = 1.0 - beta - gamma
    return (alpha, beta, gamma)
```

### 2.3 扫描线填充（Scanline Fill）

更高效的经典方法：将三角形按 Y 排序，逐条扫描线绘制。

**算法步骤**：
1. 将三个顶点按 Y 坐标排序：上(top)、中(mid)、下(bot)
2. 找到三角形被当前扫描线 y 切割的位置：
   - 左边界和右边界各一个交点
   - 细分上三角形和下三角形（如果中间点在边上则不必细分）

```python
def edge_crossing(p1, p2, y):
    """计算边 p1-p2 在 y 处的 x 坐标（线性插值）"""
    if abs(p2[1] - p1[1]) < 1e-10:
        return p1[0]  # 水平边
    t = (y - p1[1]) / (p2[1] - p1[1])
    return p1[0] + t * (p2[0] - p1[0])

def rasterize_triangle_scanline(v0, v1, v2, pixels, width, height, color):
    """扫描线填充三角形"""
    # 按 Y 排序
    pts = sorted([v0, v1, v2], key=lambda p: p[1])
    p_top, p_mid, p_bot = pts  # p_top.Y ≤ p_mid.Y ≤ p_bot.Y
    
    y0, y1, y2 = int(p_top[1]), int(p_mid[1]), int(p_bot[1])
    y0 = max(0, y0); y2 = min(height - 1, y2)
    
    for y in range(y0, y2 + 1):
        # 长边（top→bot）始终分割
        x_left = edge_crossing(p_top, p_bot, y)
        
        # 短边：根据 y 是否越过中点选择
        if y < y1:
            x_right = edge_crossing(p_top, p_mid, y)
        else:
            x_right = edge_crossing(p_mid, p_bot, y)
        
        if x_left > x_right:
            x_left, x_right = x_right, x_left  # 保持 left ≤ right
        
        # 填充此行
        x0 = max(0, int(x_left))
        x1 = min(width - 1, int(x_right))
        for x in range(x0, x1 + 1):
            pixels[x, y] = color
```

**优点**：高效，不检查包围盒中的无效像素。
**缺点**：实现稍复杂，插值深度/颜色时需要同时插值扫描线端点。

### 2.4 对比

| 方法 | 实现难度 | 性能 | 插值 | 适用场景 |
|------|---------|------|------|---------|
| Bounding Box + 重心 | ★☆☆ 简单 | ★☆☆ 慢 | ★★★ 方便 | 教学、小尺寸 |
| 扫描线填充 | ★★☆ 中等 | ★★★ 快 | ★★☆ 复杂 | 软件渲染器 |
| GPU 硬件光栅化 | ★★★ 复杂 | ★★★★★ | ★★★ | 生产环境 |

> 我们的实现选择 **Bounding Box + 重心坐标** — 代码简洁，插值天然支持，适合学习。

---

## 3. Z-buffer（深度缓冲）

### 3.1 为什么需要 Z-buffer？

在没有深度信息的情况下，后画的三角形会覆盖先画的，无论其在 3D 空间的位置。Z-buffer 解决**可见性问题**。

**painter's algorithm（画家算法）** 的局限：
- 先画远处的物体，再画近处的
- 遇到三角形互相遮挡（循环遮挡）时就失效了

**Z-buffer 的核心思想**：对每个像素，记录**当前最近**的深度值。

```
        Z-buffer 原理
        ┌─────────────────┐
像素    │ Z=0.3  Z=0.1  ← 新三角形更近，更新
        │ Z=0.8  Z=1.0    新三角形更远，丢弃
        │ Z=0.4  Z=0.4
        └─────────────────┘
          近             远
```

### 3.2 算法

```python
# 初始化 Z-buffer
zbuffer = [[float('inf')] * width for _ in range(height)]

# 对每个三角面片：
for each fragment (x, y) with interpolated depth z:
    if z < zbuffer[y][x]:        # 新像素更近
        zbuffer[y][x] = z        # 更新深度
        framebuffer[y][x] = color  # 更新颜色
    # 否则：被遮挡，丢弃
```

### 3.3 深度插值

在 NDC 或屏幕空间直接插值 z 是**不正确**的，因为透视投影下深度与 1/z 成正比（非线性）。

**正确做法**：
1. 在屏幕空间插值 `1/z`（透视校正插值）
2. 取倒数得像素深度

但对于教学实现（且不涉及纹理映射），屏幕空间线性插值 z 已经足够展示 Z-buffer 效果：

```python
# 在屏幕坐标中插值 z（近似，简单实现）
alpha, beta, gamma = barycentric(screen_p, v0_screen, v1_screen, v2_screen)
z = alpha * v0_world[2] + beta * v1_world[2] + gamma * v2_world[2]
```

---

## 4. 背面剔除（Backface Culling）

### 4.1 原理

每个三角形有法线方向。如果法线指向相机，我们看见它；如果背离相机，我们看不见它。

**判断方法**：
1. 计算三角形在**屏幕空间**的有向面积（或计算法线）
2. 如果法线指向屏幕外 → 剔除（正面保留，背面丢弃）

```python
def is_backface(v0, v1, v2):
    """判断三角形是否背向相机（屏幕空间叉积 Z 分量）"""
    # 在屏幕空间（NDC/屏幕坐标），计算边向量叉积的 Z
    e1 = v1 - v0
    e2 = v2 - v0
    # 叉积 z 分量 = e1.x * e2.y - e1.y * e2.x
    # 在屏幕坐标中，顺时针 = 正面（取决于约定）
    cross_z = e1[0] * e2[1] - e1[1] * e2[0]
    return cross_z < 0  # 或 > 0，取决于坐标系惯用手
```

**重要**：背面剔除应在 MVP 变换之后、光栅化之前做，因为法线方向在投影后可能会翻转。

### 4.2 优势

- 最多可减少 **50%** 的三角形渲染工作
- 对封闭物体（立方体、球体、角色模型）安全有效
- GPU 原生支持（自 1990s 的硬件）

### 4.3 局限性

- 不适用于透明物体（需要双面渲染）
- 不适用于非流形几何（如单面薄片）

---

## 5. 软件渲染器第2版：实心三角形 + Z-buffer + 背面剔除

我们把第1课的线框渲染器升级为**实心三角形渲染器**。

### 5.1 实现立方体的三角形面片

```python
def make_cube_triangles():
    """
    定义立方体的 12 个三角形（每面 2 个三角形）。
    顶点按逆时针顺序（CCW）以支持背面剔除。
    """
    # 8 个顶点（齐次坐标）
    verts = np.array([
        [-1, -1, -1, 1],   # 0: 前下左
        [ 1, -1, -1, 1],   # 1: 前下右
        [ 1,  1, -1, 1],   # 2: 前上右
        [-1,  1, -1, 1],   # 3: 前上左
        [-1, -1,  1, 1],   # 4: 后下左
        [ 1, -1,  1, 1],   # 5: 后下右
        [ 1,  1,  1, 1],   # 6: 后上右
        [-1,  1,  1, 1],   # 7: 后上左
    ], dtype=float)
    
    # 12 个三角形（每面 2 个，逆时针绕法）
    tris = [
        # 前面 (z=-1)
        (0, 2, 1), (0, 3, 2),
        # 右面 (x=1)
        (1, 2, 6), (1, 6, 5),
        # 后面 (z=1)
        (5, 6, 7), (5, 7, 4),
        # 左面 (x=-1)
        (4, 7, 3), (4, 3, 0),
        # 上面 (y=1)
        (3, 7, 6), (3, 6, 2),
        # 下面 (y=-1)
        (4, 0, 1), (4, 1, 5),
    ]
    return verts, tris
```

### 5.2 颜色配置

给每个面配不同颜色以便观察：

```python
# 12 个三角形，6 个面，每面用一种颜色
COLORS = [
    (200, 200, 255), (200, 200, 255),  # 前：浅蓝
    (200, 100, 100), (200, 100, 100),  # 右：浅红
    (255, 220, 100), (255, 220, 100),  # 后：浅黄
    (100, 200, 100), (100, 200, 100),  # 左：浅绿
    (200, 100, 200), (200, 100, 200),  # 上：浅紫
    (100, 200, 200), (100, 200, 200),  # 下：浅青
]
```

### 5.3 完整渲染器

```python
# -*- coding: utf-8 -*-
"""
软件渲染器 v2：实心三角形 + Z-buffer + 背面剔除
- 从线框升级为实心三角形
- 重心坐标光栅化
- 深度缓冲确保正确遮挡
- 背面剔除减少一半三角形
"""

import math
import numpy as np
from PIL import Image

# ============================================================
# 矩阵工具（复用第1课）
# ============================================================

def translate(tx, ty, tz):
    return np.array([
        [1, 0, 0, tx], [0, 1, 0, ty], [0, 0, 1, tz], [0, 0, 0, 1]], dtype=float)

def scale(sx, sy, sz):
    return np.array([
        [sx, 0, 0, 0], [0, sy, 0, 0], [0, 0, sz, 0], [0, 0, 0, 1]], dtype=float)

def rotate_x(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([
        [1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=float)

def rotate_y(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([
        [c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype=float)

def rotate_z(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([
        [c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)

def look_at(eye, target, up):
    f = np.array(target) - np.array(eye)
    f = f / np.linalg.norm(f)
    s = np.cross(f, up); s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    return np.array([
        [s[0], s[1], s[2], -np.dot(s, eye)],
        [u[0], u[1], u[2], -np.dot(u, eye)],
        [-f[0], -f[1], -f[2], np.dot(f, eye)],
        [0, 0, 0, 1]], dtype=float)

def perspective(fov_y, aspect, near, far):
    f = 1.0 / math.tan(fov_y / 2.0)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
        [0, 0, -1, 0]], dtype=float)

# ============================================================
# 重心坐标与三角形光栅化
# ============================================================

def barycentric(p, a, b, c):
    """重心坐标 (alpha, beta, gamma)，用叉积法"""
    v0 = b[:2] - a[:2]; v1 = c[:2] - a[:2]; v2 = p[:2] - a[:2]
    d00 = np.dot(v0, v0); d01 = np.dot(v0, v1)
    d11 = np.dot(v1, v1); d20 = np.dot(v2, v0); d21 = np.dot(v2, v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return (-1, -1, -1)
    beta = (d11 * d20 - d01 * d21) / denom
    gamma = (d00 * d21 - d01 * d20) / denom
    alpha = 1.0 - beta - gamma
    return (alpha, beta, gamma)


def is_backface(v0_ndc, v1_ndc, v2_ndc):
    """屏幕空间背面剔除 — 计算有向面积"""
    cross_z = (v1_ndc[0] - v0_ndc[0]) * (v2_ndc[1] - v0_ndc[1]) - \
              (v1_ndc[1] - v0_ndc[1]) * (v2_ndc[0] - v0_ndc[0])
    return cross_z < 0


def rasterize_triangle(v0, v1, v2, z0, z1, z2,
                       pixels, zbuffer, width, height, color):
    """
    光栅化实心三角形 — 包围盒 + 重心坐标 + Z-buffer
    
    参数：
        v0, v1, v2: 屏幕坐标 (x, y)
        z0, z1, z2: 对应顶点的世界深度（用于 Z-buffer）
        pixels: 帧缓冲 (PIL Image.load 对象)
        zbuffer: 2D 深度数组
    """
    # AABB
    xmin = max(0, int(min(v0[0], v1[0], v2[0])))
    xmax = min(width - 1, int(max(v0[0], v1[0], v2[0])))
    ymin = max(0, int(min(v0[1], v1[1], v2[1])))
    ymax = min(height - 1, int(max(v0[1], v1[1], v2[1])))
    
    for y in range(ymin, ymax + 1):
        for x in range(xmin, xmax + 1):
            alpha, beta, gamma = barycentric((x, y), v0, v1, v2)
            if alpha < 0 or beta < 0 or gamma < 0:
                continue
            
            # 插值深度
            z = alpha * z0 + beta * z1 + gamma * z2
            if z >= zbuffer[y][x]:
                continue  # 被遮挡
            
            zbuffer[y][x] = z
            pixels[x, y] = color

# ============================================================
# 立方体
# ============================================================

def make_cube_triangles():
    """
    返回 (顶点, 三角形面片列表, 每面颜色)
    12 个三角形，逆时针绕法
    """
    verts = np.array([
        [-1, -1, -1, 1],   # 0
        [ 1, -1, -1, 1],   # 1
        [ 1,  1, -1, 1],   # 2
        [-1,  1, -1, 1],   # 3
        [-1, -1,  1, 1],   # 4
        [ 1, -1,  1, 1],   # 5
        [ 1,  1,  1, 1],   # 6
        [-1,  1,  1, 1],   # 7
    ], dtype=float)
    
    tris = [
        (0, 2, 1), (0, 3, 2),   # 前（z=-1）
        (1, 2, 6), (1, 6, 5),   # 右（x=1）
        (5, 6, 7), (5, 7, 4),   # 后（z=1）
        (4, 7, 3), (4, 3, 0),   # 左（x=-1）
        (3, 7, 6), (3, 6, 2),   # 上（y=1）
        (4, 0, 1), (4, 1, 5),   # 下（y=-1）
    ]
    
    # 每面一种颜色（浅色系）
    colors = [
        (180, 180, 240), (180, 180, 240),   # 前：蓝
        (240, 160, 160), (240, 160, 160),   # 右：红
        (240, 240, 160), (240, 240, 160),   # 后：黄
        (160, 240, 160), (160, 240, 160),   # 左：绿
        (200, 160, 240), (200, 160, 240),   # 上：紫
        (160, 240, 240), (160, 240, 240),   # 下：青
    ]
    
    return verts.T, tris, colors  # 顶点转置为 4×8


def make_octahedron():
    """
    八面体：8 个三角形面，更丰富的形状
    """
    verts = np.array([
        [ 0,  0,  1, 1],   # 0: 上顶点
        [ 1,  0,  0, 1],   # 1
        [ 0,  1,  0, 1],   # 2
        [-1,  0,  0, 1],   # 3
        [ 0, -1,  0, 1],   # 4
        [ 0,  0, -1, 1],   # 5: 下顶点
    ], dtype=float)
    
    tris = [
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),  # 上四瓣
        (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4),  # 下四瓣
    ]
    
    # 每面对应不同色调
    colors = [
        (255, 100, 100), (255, 200, 100),
        (100, 255, 100), (100, 200, 255),
        (255, 100, 200), (200, 100, 255),
        (100, 200, 200), (200, 200, 100),
    ]
    
    return verts.T, tris, colors

# ============================================================
# 渲染器
# ============================================================

def render_frame(width, height, vertices_4xn, triangles, face_colors, model_mat, use_backface_culling=True):
    """
    渲染一帧：实心三角形 + Z-buffer
    
    参数：
        vertices_4xn: 4×N numpy 数组，齐次坐标
        triangles: 三角形索引列表 [(i0,i1,i2), ...]
        face_colors: 每个三角形的颜色
        model_mat: 4×4 模型矩阵
        use_backface_culling: 是否启用背面剔除
    """
    aspect = width / height
    eye = np.array([3, 3, 3], dtype=float)
    target, up = np.array([0, 0, 0]), np.array([0, 1, 0])
    
    V = look_at(eye, target, up)
    P = perspective(math.radians(60), aspect, 0.1, 100.0)
    mvp = P @ V @ model_mat
    
    # MVP 变换
    clip_verts = mvp @ vertices_4xn  # 4×N
    
    # 透视除法 + 视口变换
    num_verts = clip_verts.shape[1]
    screen = np.zeros((num_verts, 2), dtype=float)  # 屏幕坐标
    world_z = np.zeros(num_verts, dtype=float)       # 视图空间的 z（用于深度）
    
    for i in range(num_verts):
        x, y, z, w = clip_verts[:, i]
        if abs(w) < 1e-10:
            screen[i] = [-9999, -9999]
            world_z[i] = 1e10
            continue
        screen[i, 0] = (x / w + 1) * 0.5 * width
        screen[i, 1] = (1 - y / w) * 0.5 * height
        world_z[i] = z / w  # NDC z，用于深度比较
    
    # 创建帧缓冲
    img = Image.new("RGB", (width, height), (20, 20, 30))
    pixels = img.load()
    zbuffer = [[1e10] * width for _ in range(height)]
    
    # 渲染每个三角形
    for tri_idx, (i0, i1, i2) in enumerate(triangles):
        v0_s, v1_s, v2_s = screen[i0], screen[i1], screen[i2]
        
        # 背面剔除（在 NDC 空间判断方向）
        if use_backface_culling and is_backface(v0_s, v1_s, v2_s):
            continue
        
        color = face_colors[tri_idx]
        rasterize_triangle(
            v0_s, v1_s, v2_s,
            world_z[i0], world_z[i1], world_z[i2],
            pixels, zbuffer, width, height, color
        )
    
    return img

# ============================================================
# 主程序
# ============================================================

def main():
    width, height = 400, 400
    num_frames = 36
    
    # ---- 立方体实验 ----
    print("=== 实心旋转立方体（12个三角形 + Z-buffer + 背面剔除）===")
    verts, tris, colors = make_cube_triangles()
    frames = []
    for i in range(num_frames):
        angle = 2 * math.pi * i / num_frames
        model = rotate_y(angle) @ rotate_x(angle * 0.3)
        frames.append(render_frame(width, height, verts, tris, colors, model))
        print(f"  立方体帧 {i+1}/{num_frames}")
    
    frames[0].save(
        "memory/learning/figures/graphics_02_cube_solid.gif",
        save_all=True, append_images=frames[1:], duration=50, loop=0
    )
    print("✅ 已保存: graphics_02_cube_solid.gif")
    
    # ---- 八面体实验 ----
    print("\n=== 实心旋转八面体（8个三角形）===")
    verts2, tris2, colors2 = make_octahedron()
    frames2 = []
    for i in range(num_frames):
        angle = 2 * math.pi * i / num_frames
        model = rotate_y(angle) @ rotate_x(angle * 0.5)
        frames2.append(render_frame(width, height, verts2, tris2, colors2, model))
        print(f"  八面体帧 {i+1}/{num_frames}")
    
    frames2[0].save(
        "memory/learning/figures/graphics_02_octahedron_solid.gif",
        save_all=True, append_images=frames2[1:], duration=50, loop=0
    )
    print("✅ 已保存: graphics_02_octahedron_solid.gif")
    
    # ---- 对比实验：关闭背面剔除 ----
    print("\n=== 对比：关闭背面剔除 ===")
    verts3, tris3, colors3 = make_cube_triangles()
    frames3 = []
    for i in range(num_frames):
        angle = 2 * math.pi * i / num_frames
        model = rotate_y(angle) @ rotate_x(angle * 0.3)
        frames3.append(render_frame(width, height, verts3, tris3, colors3, model,
                                    use_backface_culling=False))
        print(f"  对比帧 {i+1}/{num_frames}")
    
    frames3[0].save(
        "memory/learning/figures/graphics_02_no_cull.gif",
        save_all=True, append_images=frames3[1:], duration=50, loop=0
    )
    print("✅ 已保存: graphics_02_no_cull.gif")


if __name__ == "__main__":
    main()
```

### 5.4 预期效果

| 版本 | 效果 |
|------|------|
| 线框（第1课） | 蓝色线条组成立方体框架，看到背面线条 |
| 实心 + 背面剔除（第2课） | 彩色面片，只能看到正面三角形（~6个面出现） |
| 实心无剔除（对比） | 彩色面片，内外都能看到，乱糟糟 |

---

## 6. 关键概念总结

| 概念 | 要点 |
|------|------|
| **三角形光栅化** | 用包围盒 + 重心坐标将连续三角形变成离散像素 |
| **重心坐标** | 面积比，用 (α,β,γ) 表示三角形内的点，α+β+γ=1，都≥0 则在内部 |
| **Z-buffer** | 每个像素存最近深度值，解决遮挡问题，O(1) 空间/像素 |
| **背面剔除** | 丢弃法线背离相机的三角形，最多省 50% 渲染量 |
| **Bounding Box** | 先算三角形 AABB，只扫描有效区域，避免全屏遍历 |
| **扫描线填充** | 逐行确定左右边界，效率更高但插值更复杂 |

### 为什么 Z-buffer > Painter's Algorithm？

```
                       Painter 算法
    三角形按深度排序后 → 先远后近 → 正确
    相交三角形 → 无法排序 → 错误 ❌
    
     Z-buffer
    逐像素判断 → 不要求排序 → 任意三角形都正确 ✅
```

---

## 7. 扩展思考

1. **透视校正插值**：纹理映射时必须用 `1/z` 插值，否则纹理会有透视扭曲
2. **Early Z**：现代 GPU 先做 Z 测试再执行片段着色器，跳过被遮挡像素的着色计算
3. **Hierarchical Z**：用 Z-pyramid 快速剔除大三角形块
4. **MSAA（多重采样抗锯齿）**：每个像素采多个子样本，三角边上的子样本各有不同颜色
5. **三角形设置（Triangle Setup）**：GPU 光栅化的硬件前端，计算三角形边的梯度方程
6. **裁剪（Clipping）**：三角形超出视锥时，需要裁剪出新的三角形再光栅化

> 下一课预告：光照与着色 — 环境光、漫反射（Lambertian）、镜面反射（Blinn-Phong）、Flat/Gouraud/Phong 着色方式
