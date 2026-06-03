# 软渲染器笔记 05 — 阴影与高级光照

> 从零实现 3D 软渲染器系列 · 第五篇

---

## 1. 阴影映射 (Shadow Mapping)

### 1.1 基本原理
1. **从光源视角渲染场景**，存储深度到阴影贴图
2. **从相机视角渲染**，每个像素变换到光源空间
3. 比较深度：若深度 > 阴影贴图对应值 → 阴影中

### 1.2 算法步骤
```
// Pass 1：从光源渲染
将光源作为"相机"，使用 LookAt 矩阵
光栅化场景，存储深度到 shadow_map

// Pass 2：正常渲染
for each 像素:
    将世界坐标变换到光源空间
    获取 shadow_map 中的深度 d_map
    检查该点深度 d_point
    
    if d_point > d_map + bias:
        shadow = shadow_intensity
    else:
        shadow = 0
```

### 1.3 常见问题
| 问题 | 原因 | 解决 |
|------|------|------|
| 阴影锯齿 | 贴图分辨率不足 | PCF 滤波 |
| 阴影粉刺 | 浮点误差 | 添加 bias 偏移 |
| 透视走样 | 远近精度差异 | Cascaded Shadow Maps |
| 无自阴影 | 深度比较误判 | 深度偏移 |

### 1.4 PCF (Percentage Closer Filtering)
```python
def pcf_shadow(shadow_map, coord, bias=0.005):
    # 采样周围 3×3 区域
    total = 0.0
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            d_map = shadow_map.sample(coord + (dx*step, dy*step))
            if d_point < d_map + bias:
                total += 1.0
    return total / 9.0  # 可见度
```

---

## 2. 环境光遮蔽 (AO)

### 2.1 屏幕空间环境光遮蔽 (SSAO)
- 在屏幕空间采样周围像素的深度
- 计算可见度近似值
- 不需要额外几何信息

### 2.2 简单实现
```python
def ssao(position, normal, depth_buffer, radius=1.0):
    occlusion = 0.0
    for sample in hemisphere_samples:
        sample_pos = position + normal * sample
        sample_screen = project(sample_pos)
        sample_depth = depth_buffer[sample_screen]
        if sample_depth < sample_pos.z:
            occlusion += 1.0
    return 1.0 - occlusion / len(hemisphere_samples)
```

---

## 3. 多光源支持

### 3.1 叠加模式
对每个光源重复计算：
```
total_light = ambient
for each light in lights:
    diffuse = calc_diffuse(normal, light.dir)
    specular = calc_specular(normal, view, light.dir)
    total_light += (diffuse + specular) * light.intensity * attenuation
```

### 3.2 光源类型
| 类型 | 方向计算 | 衰减 |
|------|----------|------|
| 方向光 | 全局方向 | 无 |
| 点光源 | position - frag_pos | 距离平方 |
| 聚光灯 | 方向光 + 角度范围 | 角度衰减 |

---

## 4. Gamma 校正

### 4.1 为什么需要
- 显示器亮度响应是非线性的（Gamma ≈ 2.2）
- 不校正的话，中间色调偏暗

### 4.2 校正
```python
# 编码（写入帧缓冲前）
def linear_to_gamma(color):
    return pow(color, 1.0/2.2)

# 解码（读纹理时）
def gamma_to_linear(color):
    return pow(color, 2.2)
```

---

## 5. 阴影在软渲染器中的实现

由于软渲染器速度瓶颈，阴影映射通常不作为实时光栅化的默认功能。但对于教学目的：

```python
# 简化实现：仅渲染器侧计算
def compute_shadow(world_pos, light_pos, meshes):
    # 从 world_pos 到 light_pos 发射射线
    ray_dir = normalize(light_pos - world_pos)
    dist = (light_pos - world_pos).norm()
    
    for mesh in meshes:
        for tri in mesh.triangles:
            hit, t = ray_triangle_intersect(world_pos, ray_dir, tri)
            if hit and t < dist:
                return True  # 在阴影中
    return False
```

**实战建议**：对于软渲染器，用 **环境光 + 方向光 + 双面着色** 即可获得不错的视觉效果，阴影映射作为进阶了解。

---

下一篇：[06 — PBR 与 GPU 管线概述](./graphics_renderer_06_texture.md)
