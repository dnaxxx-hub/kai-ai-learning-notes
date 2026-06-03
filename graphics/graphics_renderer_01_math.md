# 软渲染器笔记 01 — 数学基础

> 从零实现 3D 软渲染器系列 · 第一篇

---

## 1. 三维空间基础

### 1.1 向量 Vec3

三维向量 = (x, y, z)，支持：
- 加减法：分量加减
- 点积：`dot(a,b) = a.x*b.x + a.y*b.y + a.z*b.z` → 标量
- 叉积：`cross(a,b)` → 垂直向量，用于法线计算 / 背面剔除
- 归一化：`normalize(v) = v / |v|`
- 长度：`|v| = sqrt(x² + y² + z²)`

### 1.2 矩阵 Mat4

4×4 矩阵（齐次坐标），存储为 16 个浮点数的行主序数组。

**齐次坐标**：3D点 (x,y,z) → (x,y,z,1)，方向向量 → (x,y,z,0)

**关键运算**：
- 矩阵乘法：`C = A × B`
- 矩阵 × 向量：变换点/方向
- 单位矩阵：对角为 1

---

## 2. 基本变换

### 2.1 平移矩阵
```
[1 0 0 tx]
[0 1 0 ty]
[0 0 1 tz]
[0 0 0 1 ]
```

### 2.2 旋转矩阵
绕 X 轴旋转 θ 角度：
```
[1    0      0    0]
[0  cosθ  -sinθ  0]
[0  sinθ   cosθ  0]
[0    0      0    1]
```

绕 Y 轴 / Z 轴同理。

### 2.3 缩放矩阵
```
[sx 0  0  0]
[0  sy 0  0]
[0  0  sz 0]
[0  0  0  1]
```

---

## 3. 投影矩阵

### 3.1 透视投影
将视锥体(frustum)映射到标准化设备坐标(NDC)立方体 [-1,1]³：

```
P = [
  [f/as    0         0              0       ],
  [  0     f         0              0       ],
  [  0     0   (zFar+zNear)/(zNear-zFar)  2*zFar*zNear/(zNear-zFar)],
  [  0     0        -1              0       ]
]
```
其中 `f = 1/tan(fov/2)`，`as = width/height`

### 3.2 视口变换
从 NDC [-1,1]² 映射到屏幕像素坐标：
```
x_screen = (x_ndc + 1) * width/2
y_screen = (1 - y_ndc) * height/2
```

---

## 4. 变换管线

```
顶点原始坐标
    ↓ 模型矩阵 (Model) — 局部→世界
    ↓ 视图矩阵 (View)  — 世界→相机
    ↓ 投影矩阵 (Projection) — 视锥→NDC
    ↓ 视口变换 — NDC→屏幕像素
```

**LookAt 矩阵**（构建视图矩阵）：
- 相机位置 `eye`，目标点 `center`，上方向 `up`
- `forward = normalize(center - eye)`
- `right = normalize(cross(forward, up))`
- `up' = cross(right, forward)`
- 组装为 4×4 旋转+平移矩阵

---

## 5. Python 实现要点

```python
from math import sin, cos, tan, sqrt, pi

class Vec3:
    def __init__(self, x, y, z): ...
    def __add__(self, v): return Vec3(x+v.x, y+v.y, z+v.z)
    def __sub__(self, v): ...
    def __mul__(self, s): return Vec3(x*s, y*s, z*s)  # 数乘
    def dot(self, v): return x*v.x + y*v.y + z*v.z
    def cross(self, v): return Vec3(y*v.z-z*v.y, z*v.x-x*v.z, x*v.y-y*v.x)
    def norm(self): return sqrt(x*x + y*y + z*z)
    def normalize(self): n=self.norm(); return self*(1/n)

class Mat4:
    # 16 元素列表，行主序
    @staticmethod
    def identity(): ...
    @staticmethod
    def translate(tx, ty, tz): ...
    @staticmethod
    def rotate_x(angle): ...
    @staticmethod
    def rotate_y(angle): ...
    @staticmethod
    def rotate_z(angle): ...
    @staticmethod
    def scale(sx, sy, sz): ...
    @staticmethod
    def perspective(fov, aspect, zNear, zFar): ...
    @staticmethod
    def look_at(eye, center, up): ...
    def mul_vec(self, v): ...  # 矩阵×向量（齐次→笛卡尔）
    def __mul__(self, m): ...  # 矩阵乘法
```

---

下一篇：[02 — 线框渲染与光栅化](./graphics_renderer_02_wireframe.md)
