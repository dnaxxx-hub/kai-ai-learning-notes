# 软渲染器笔记 03 — 光照与着色

> 从零实现 3D 软渲染器系列 · 第三篇

---

## 1. 光照模型概览

### 1.1 局部光照 vs 全局光照
- **局部光照**：每个点独立计算，只考虑光源直接照射（Phong、Blinn-Phong）
- **全局光照**：考虑光线在物体间的弹射（光线追踪、辐射度）

软渲染器使用 **Blinn-Phong 局部光照模型**。

### 1.2 光照分量

| 分量 | 来源 | 特点 |
|------|------|------|
| 环境光 (Ambient) | 环境散射 | 常数项，颜色均匀 |
| 漫反射 (Diffuse) | 直接光照 | 与法线和光源方向相关 |
| 高光 (Specular) | 镜面反射 | 与视线方向相关 |

**总光照** = 环境 + 漫反射 + 高光

---

## 2. 朗伯漫反射 (Lambertian)

### 公式
```
diffuse = lightColor * dot(normal, lightDir)
```
- `normal`：表面法线（单位向量）
- `lightDir`：指向光源的方向（单位向量）
- `dot` 结果为负 → 背面 → 漫反射 = 0

### 特点
- 与视角无关
- 粗糙表面的理想模型
- 越正对光源越亮

---

## 3. Blinn-Phong 高光

### 公式
```
specular = lightColor * pow(dot(normal, halfVector), shininess)
```
- `halfVector = normalize(viewDir + lightDir)`
- `shininess`：材质的镜面强度（越大越集中、越小越扩散）

### Phong 原版 vs Blinn 改进
| Phong | Blinn-Phong |
|-------|-------------|
| 使用反射向量 R 与视线 V 的夹角 | 使用半角向量 H 与法线 N 的夹角 |
| 需要计算 R | 只需计算 H = L+V |
| 计算量较大 | 更高效 |
| 在某些角度下有缺陷 | 更稳定 |

---

## 4. 光源类型

### 4.1 方向光 (Directional Light)
- 所有点接受到相同方向的光
- 无衰减，相当于无限远处的光源（太阳）
- `lightDir` 全局一致

### 4.2 点光源 (Point Light)
- 从某一点发射光线
- 有衰减：
```
attenuation = 1.0 / (constant + linear*d + quadratic*d²)
```

### 4.3 环境光 (Ambient)
- 常数值，模拟间接光照
- `ambient = ambientColor * materialColor`

---

## 5. 着色模式

### 5.1 平面着色 (Flat Shading)
- 每个三角形一个颜色值
- 使用面法线计算一次光照
- 效果：棱角分明（低多边形风格）

### 5.2 高洛德着色 (Gouraud Shading)
- 每个顶点计算光照
- 三角形内插值颜色
- 效果：平滑过渡

### 5.3 Phong 着色
- 每个像素插值法线
- 对每个像素计算光照
- 效果：最高质量，高光更真实

**实现优先级**：平面 → 高洛德 → Phong

---

## 6. 软渲染器中的实现

```python
def blinn_phong(normal, view_dir, light_dir, 
                light_color, ambient_color, 
                diffuse_color, specular_color, shininess):
    # 环境光
    ambient = ambient_color * diffuse_color
    
    # 漫反射
    diff = max(0, dot(normal, light_dir))
    diffuse = light_color * diffuse_color * diff
    
    # 高光
    half = normalize(view_dir + light_dir)
    spec = pow(max(0, dot(normal, half)), shininess)
    specular = light_color * specular_color * spec
    
    return ambient + diffuse + specular
```

---

下一篇：[04 — 纹理映射](./graphics_renderer_04_texture.md)
