# 计算机图形学第4课：纹理映射与抗锯齿

## 纹理映射基础

将 2D 图像（纹理）映射到 3D 表面。

### UV 坐标
每个顶点关联 (u, v) 坐标，范围 [0, 1]。
```
纹理坐标: (0,0)=左下, (1,0)=右下, (1,1)=右上, (0,1)=左上
```

### 纹理采样
给定像素的 (u, v)，从纹理中取颜色。

```python
def sample_nearest(texture, u, v):
    """最近邻采样"""
    w, h = texture.shape[1], texture.shape[0]
    x = int(u * (w - 1))
    y = int(v * (h - 1))
    return texture[y, x]
```

### 双线性插值（Bilinear Interpolation）
取最近4个纹理像素的加权平均，消除锯齿。

```python
def sample_bilinear(texture, u, v):
    """双线性插值采样"""
    w, h = texture.shape[1], texture.shape[0]
    x = u * (w - 1)
    y = v * (h - 1)
    x0, x1 = int(x), min(int(x) + 1, w - 1)
    y0, y1 = int(y), min(int(y) + 1, h - 1)
    fx, fy = x - x0, y - y0
    # 水平插值
    top = texture[y0, x0] * (1 - fx) + texture[y0, x1] * fx
    bot = texture[y1, x0] * (1 - fx) + texture[y1, x1] * fx
    # 垂直插值
    return top * (1 - fy) + bot * fy
```

## 透视矫正纹理映射

直接线性插值 UV 会导致透视变形（远处纹理被拉伸）。

正确方法：插值 `(u/z, v/z, 1/z)` 而非 `(u, v)`。

```python
def perspective_correct_uv(u0, v0, z0, u1, v1, z1, t):
    """透视矫正 UV 插值 (t in [0,1])"""
    uz0, vz0 = u0 / z0, v0 / z0
    uz1, vz1 = u1 / z1, v1 / z1
    invz0, invz1 = 1.0 / z0, 1.0 / z1
    uz = uz0 * (1 - t) + uz1 * t
    vz = vz0 * (1 - t) + vz1 * t
    invz = invz0 * (1 - t) + invz1 * t
    return uz / invz, vz / invz
```

## 抗锯齿（Anti-Aliasing）

### SSAA（超采样抗锯齿）
以 N 倍分辨率渲染，再降采样。
- 质量最高，开销最大
- 例如 4×SSAA = 4倍像素量

### MSAA（多重采样抗锯齿）
- 对深度/模板做超采样，颜色不重复计算
- 只对多边形边缘做抗锯齿
- 比 SSAA 效率高得多

```python
def ssaa_render(scene, width, height, scale=2):
    """SSAA: 先大图渲染再降采样"""
    big_w, big_h = width * scale, height * scale
    big_fb = render_scene(scene, big_w, big_h)
    fb = np.zeros((height, width, 3))
    for y in range(height):
        for x in range(width):
            # 2×2 块平均
            fb[y, x] = big_fb[y*scale:(y+1)*scale, x*scale:(x+1)*scale].mean(axis=(0,1))
    return fb
```

## 完整纹理管线流程

```
3D顶点 (x, y, z, u, v)
  ↓ 投影变换
屏幕坐标 (x', y', z')
  ↓ 光栅化（透视矫正 UV）
每个像素获得 (u, v, z)
  ↓ 纹理采样（双线性插值）
颜色值
  ↓ 与光照结果结合
最终像素颜色
```

## 关键总结
- UV 坐标将 2D 纹理绑定到 3D 表面
- 双线性插值消除纹理放大时的像素化
- 透视矫正是正确纹理映射的关键
- SSAA = 高质量但昂贵，MSAA = 边缘抗锯齿的实用方案
