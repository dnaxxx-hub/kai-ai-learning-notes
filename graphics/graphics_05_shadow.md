# 计算机图形学第5课：阴影、透明度与高级着色

## 阴影映射（Shadow Mapping）

两遍渲染：
1. **从光源视角**渲染深度图（shadow map）
2. **从相机视角**渲染场景，对每个像素判断是否在阴影中

```python
def shadow_mapping(renderer, light_pos, scene):
    """两遍阴影映射"""
    # Pass 1: 从光源渲染深度
    shadow_map = renderer.render_depth(scene, camera_pos=light_pos)
    
    # Pass 2: 从相机渲染
    fb = renderer.render(scene)
    for y, x in np.argwhere(fb.depth_buffer > 0):
        # 将片段转换到光源空间
        p_light = world_to_light(fb.world_pos[y, x], light_pos)
        shadow_depth = sample_shadow_map(shadow_map, p_light.x, p_light.y)
        if p_light.z > shadow_depth + bias:
            fb[y, x] *= 0.3  # 阴影区域变暗
    return fb
```

### PCSS 处理阴影软硬过渡
- Percentage Closer Filtering
- 在阴影图周围采样多个点，百分比决定阴影强度
- 越远的阴影越柔和

## 透明度与 Alpha 混合

### Alpha 值
每个像素的透明度：α=1.0 不透明，α=0.0 完全透明。

### Alpha 混合
```
输出 = 源 × α源 + 目标 × (1 - α源)
```

```python
def alpha_blend(src_color, src_alpha, dst_color, dst_alpha):
    """标准 alpha 混合"""
    out_alpha = src_alpha + dst_alpha * (1 - src_alpha)
    out_color = (src_color * src_alpha + dst_color * dst_alpha * (1 - src_alpha)) / out_alpha
    return out_color, out_alpha
```

### 渲染顺序
- 不透明物体 → 渲染（启用深度测试）
- 半透明物体 → 从远到近排序 → 渲染（启用 alpha blend）
- 所以透明物体要先排序

## 环境贴图（Skybox / Environment Map）

用一张全景图（Cubemap / Equirectangular）作为环境背景。

```python
def skybox_sample(env_map, direction):
    """从方向向量采样环境贴图"""
    # 将方向转换为经纬度
    theta = np.arctan2(direction[2], direction[0])
    phi = np.arccos(direction[1])
    u = (theta + np.pi) / (2 * np.pi)
    v = phi / np.pi
    return sample_bilinear(env_map, u, v)
```

### 环境反射
用反射方向采样环境贴图，模拟金属/镜面环境反射。

## 法线贴图（Normal Mapping）

用纹理存储法线方向，在光照计算中代替几何法线。

```
法线贴图中的 RGB → 法线向量 (x, y, z) 在 [0,1] 映射到 [-1,1]
```

## 关键总结
- Shadow Mapping：两遍渲染 + 深度比较
- Alpha Blend：先不透明再透明（从远到近）
- Skybox：环境贴图提供无限远背景和反射
- Normal Map：用纹理法线替代几何细节，低模呈现高模效果
