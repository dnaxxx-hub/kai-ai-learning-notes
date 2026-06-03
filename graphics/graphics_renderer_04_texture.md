# 软渲染器笔记 04 — 纹理映射

> 从零实现 3D 软渲染器系列 · 第四篇

---

## 1. 纹理坐标 (UV)

### 1.1 什么是 UV
- 每个顶点关联一对 UV 坐标 (u, v)
- u: 水平方向 [0, 1]，v: 垂直方向 [0, 1]
- 纹理图像上每个像素（纹素/texel）由 UV 定位

### 1.2 立方体的 UV 展开
```
// 每个面独立 UV 映射
前面 (z=1):  v0=(-1,-1,1)→(0,0)  v1=(1,-1,1)→(1,0)
            v3=(-1, 1,1)→(0,1)  v2=(1, 1,1)→(1,1)
后面 (z=-1): v4→(0,0), v5→(1,0), v7→(0,1), v6→(1,1)
顶面 (y=1):  v3→(0,0), v2→(1,0), v7→(0,1), v6→(1,1)
底面 (y=-1): v0→(0,0), v1→(1,0), v4→(0,1), v5→(1,1)
右面 (x=1):  v1→(0,0), v5→(1,0), v2→(0,1), v6→(1,1)
左面 (x=-1): v0→(0,0), v4→(1,0), v3→(0,1), v7→(1,1)
```

---

## 2. UV 插值

### 2.1 使用重心坐标
三角形内一点 P 的 UV 坐标：
```
u = α*u0 + β*u1 + γ*u2
v = α*v0 + β*v1 + γ*v2
```

### 2.2 透视校正
直接插值 UV 会导致透视畸变，需要校正：
```
// 使用 1/z 加权插值
u = (α*u0/z0 + β*u1/z1 + γ*u2/z2) / (α/z0 + β/z1 + γ/z2)
v = (α*v0/z0 + β*v1/z1 + γ*v2/z2) / (α/z0 + β/z1 + γ/z2)
```

**核心思想**：在屏幕空间中，深度倒数(1/z)是线性变化的，所以用 1/z 加权。

---

## 3. 采样纹理

### 3.1 最近邻采样 (Nearest)
```
texel_x = int(u * texWidth)
texel_y = int(v * texHeight)
color = texture[texel_y][texel_x]
```
- 最快，但有锯齿/马赛克

### 3.2 双线性过滤 (Bilinear)
取最近的 4 个纹素做线性插值：
```
x = u * texWidth - 0.5
y = v * texHeight - 0.5
// 取四个角
c00 = texture[y0][x0], c10 = texture[y0][x1]
c01 = texture[y1][x0], c11 = texture[y1][x1]
// 双线性插值
fx = x - floor(x), fy = y - floor(y)
top = c00*(1-fx) + c10*fx
bot = c01*(1-fx) + c11*fx
result = top*(1-fy) + bot*fy
```
- 平滑、高质量

---

## 4. 纹理应用

### 4.1 漫反射纹理
- 从纹理采样颜色作为 `diffuse_color`
- 替换原本的单色材质

### 4.2 法线贴图（扩展）
- 从法线贴图采样法线方向
- 在切线空间中进行光照计算

### 4.3 程序化纹理
不依赖图片，用代码生成：
```python
# 棋盘格
def checkerboard(u, v, size=8):
    x = int(u * size) % 2
    y = int(v * size) % 2
    return white if x == y else black

# 渐变
def gradient(u, v):
    return (int(u*255), int(v*255), 128)
```

---

## 5. 实现流程

```
// 在光栅化循环中
for each 像素 (x,y):
    α, β, γ = barycentric(P, A, B, C)
    
    // 透视校正的 UV 插值
    inv_z = α*(1/z0) + β*(1/z1) + γ*(1/z2)
    u = (α*u0/z0 + β*u1/z1 + γ*u2/z2) / inv_z
    v = (α*v0/z0 + β*v1/z1 + γ*v2/z2) / inv_z
    
    // 采样纹理
    texel = bilinear_sample(texture, u, v)
    
    // 光照中应用纹理颜色
    final_color = ambient + diffuse*texel + specular
```

---

下一篇：[05 — 阴影与高级光照](./graphics_renderer_05_shadow.md)
