# 计算机图形学第3课：光照与着色

## 光照模型

光照 = 环境光 + 漫反射 + 镜面反射

### 环境光（Ambient）
场景的基础亮度，不依赖光源方向。
```
I_ambient = k_a × I_a
```

### 漫反射（Diffuse / Lambertian）
粗糙表面的反射，各方向均匀。
```
I_diffuse = k_d × I_l × max(0, n·l)
```
其中 n=法线方向，l=光源方向。

### 镜面反射（Specular / Blinn-Phong）
光滑表面的高光，依赖于视角方向。
```
I_specular = k_s × I_l × max(0, n·h)^p
```
其中 h = (l + v) / |l + v|（半程向量），p=光泽度指数。

### Blinn-Phong 完整模型
```python
import numpy as np

def blinn_phong(normal, light_dir, view_dir, ka, kd, ks, Ia, Il, shininess):
    ambient = ka * Ia
    diffuse = kd * Il * max(0, np.dot(normal, light_dir))
    half = (light_dir + view_dir) / np.linalg.norm(light_dir + view_dir)
    specular = ks * Il * max(0, np.dot(normal, half)) ** shininess
    return ambient + diffuse + specular
```

## 三种着色模式

### Flat Shading（平直着色）
- 每个三角形一个颜色
- 用面法线计算光照
- 低质量，马赫带效应明显

### Gouraud Shading（高洛德着色）
- 每个顶点计算颜色
- 三角形内部用重心坐标插值颜色
- 比 Flat 平滑，但高光可能丢失

### Phong Shading（冯氏着色）
- 每个顶点计算法线
- 三角形内部用重心坐标插值法线
- 对每个像素计算光照
- 质量最高，但计算量最大

```python
def barycentric(p, a, b, c):
    """计算点p在三角形abc中的重心坐标"""
    v0 = b - a
    v1 = c - a
    v2 = p - a
    d00 = np.dot(v0, v0)
    d01 = np.dot(v0, v1)
    d11 = np.dot(v1, v1)
    d20 = np.dot(v2, v0)
    d21 = np.dot(v2, v1)
    denom = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return u, v, w
```

## 法线计算

### 面法线
```python
def face_normal(v0, v1, v2):
    return np.cross(v1 - v0, v2 - v0)
```

### 顶点法线
相邻面法线的加权平均（按面积权重）。

## 完整软件渲染（带光照）

```python
def render_triangle(verts, norms, color, lights, framebuffer, zbuffer):
    """Phong着色：插值法线 → 逐像素光照"""
    for y in range(ymin, ymax):
        for x in range(xmin, xmax):
            u, v, w = barycentric([x, y], verts[0], verts[1], verts[2])
            if u < 0 or v < 0 or w < 0:
                continue
            # 插值法线和深度
            n = u * norms[0] + v * norms[1] + w * norms[2]
            n = n / np.linalg.norm(n)
            z = 1.0 / (u/verts[0][2] + v/verts[1][2] + w/verts[2][2])
            if z > zbuffer[y][x]:
                zbuffer[y][x] = z
                # Phong着色
                clr = blinn_phong(n, light_dir, view_dir, *light_params)
                framebuffer[y][x] = clr * color
```

## 关键总结
- Blinn-Phong = Ambient + Diffuse(Lambertian) + Specular(semi-vector)
- 半程向量 h = (l + v) / |l + v| 简化了镜面反射计算
- Flat → 面着色，Gouraud → 顶点着色，Phong → 逐像素
- Phong 质量最高，是实时渲染的标准
