# 第7课：PBR与BRDF

## 1. BRDF（双向反射分布函数）理论

### 1.1 什么是BRDF

**BRDF**（Bidirectional Reflectance Distribution Function）描述了光在某个表面点上的反射分布：

$$f_r(\omega_i, \omega_o) = \frac{dL_o(\omega_o)}{dE_i(\omega_i)} = \frac{\text{出射辐射亮度（radiance）}}{\text{入射辐射照度（irradiance）}}$$

其中：
- $\omega_i$：入射方向（指向光源）
- $\omega_o$：出射方向（指向相机/眼睛）
- $L_o$：出射方向的辐射亮度
- $E_i$：入射方向的辐射照度

### 1.2 BRDF的基本性质

1. **互易性（Helmholtz Reciprocity）**：$f_r(\omega_i, \omega_o) = f_r(\omega_o, \omega_i)$
2. **能量守恒**：$\int_{\Omega^+} f_r(\omega_i, \omega_o) \cos\theta d\omega \leq 1$
3. **线性**：BRDF可以叠加（漫反射+高光等）

### 1.3 渲染方程（Rendering Equation）

渲染方程是真实感渲染的核心：

$$L_o(p, \omega_o) = L_e(p, \omega_o) + \int_{\Omega^+} f_r(p, \omega_i, \omega_o) L_i(p, \omega_i) (\omega_i \cdot n) d\omega_i$$

- $L_o$：从点p向方向$\omega_o$出射的总辐射亮度
- $L_e$：点p自身发射的辐射亮度
- $L_i$：从方向$\omega_i$入射到点p的辐射亮度
- $f_r$：BRDF
- $\omega_i \cdot n$：入射角余弦（Lambert项）

### 1.4 简单BRDF：Lambertian漫反射

最简单的BRDF模型：

$$f_{Lambert}(\omega_i, \omega_o) = \frac{\text{albedo}}{\pi}$$

- 完全漫反射，各方向反射均匀
- 反射率 = albedo（0~1之间）
- 除以π是归一化因子（能量守恒）

## 2. 微表面理论（Microfacet Theory）

### 2.1 核心假设

微表面理论认为：粗糙表面由无数个**完美光滑的微小镜面**（微表面）组成：

```
光滑表面:   /‾‾‾‾‾\     每个微表面法线≈宏观法线
粗糙表面:   /\/\/\/\     微表面法线方向随机分布
```

### 2.2 微表面BRDF通用公式

$$f_r(\omega_i, \omega_o, h) = \frac{F(\omega_i, h) \cdot G(\omega_i, \omega_o, h) \cdot D(h)}{4(\omega_i \cdot n)(\omega_o \cdot n)}$$

核心三要素：
- **$D(h)$：法线分布函数（Normal Distribution Function, NDF）**——描述微表面法线朝向分布
- **$F(\omega_i, h)$：菲涅尔项（Fresnel）**——描述反射随入射角变化
- **$G(\omega_i, \omega_o, h)$：几何函数（Geometry Function）**——描述微表面间的遮挡和阴影

### 2.3 法线分布函数 D(h)

NDF描述有多少微表面的法线指向半向量h方向：

**Beckmann分布**（高斯型）：
$$D_{Beckmann}(h) = \frac{1}{\pi \alpha^2 \cos^4\theta_h} \cdot \exp\left(-\frac{\tan^2\theta_h}{\alpha^2}\right)$$

**GGX/Trowbridge-Reitz分布**（长尾型，最常用）：
$$D_{GGX}(h) = \frac{\alpha^2}{\pi \cos^4\theta_h (\alpha^2 + \tan^2\theta_h)^2}$$

其中$\alpha = roughness^2$，roughness范围[0,1]

### 2.4 菲涅尔项 F(ω_i, h)

**Schlick近似**（最常用的简化）：
$$F(\omega_i, h) = F_0 + (1 - F_0) \cdot (1 - \cos\theta_i)^5$$

其中$F_0$是法向反射率（0°入射角时的反射率）：
- 电介质（绝缘体）：$F_0 \approx 0.04$
- 导体（金属）：$F_0 = \text{specular color}$（有色高光）

```python
# 常见材质的F0值
F0_values = {
    'water':    0.02,    # 水
    'glass':    0.04,    # 玻璃
    'plastic':  0.04,    # 塑料
    'concrete': 0.06,    # 混凝土
    'iron':     0.56,    # 铁
    'copper':   0.95,    # 铜（RGB: 0.95, 0.64, 0.54）
    'gold':     1.00,    # 金（RGB: 1.00, 0.71, 0.29）
    'silver':   0.95,    # 银（RGB: 0.95, 0.93, 0.88）
}
```

### 2.5 几何函数 G(ω_i, ω_o, h)

几何函数描述微表面间的遮挡：

**Smith几何函数 + GGX**：
$$G_{Smith}(v) = \frac{2}{1 + \sqrt{1 + \alpha^2 \tan^2\theta_v}}$$

最终几何函数：
$$G(\omega_i, \omega_o, h) = G_{Smith}(\omega_i) \cdot G_{Smith}(\omega_o)$$

## 3. Cook-Torrance BRDF模型

### 3.1 完整模型

Cook-Torrance是最经典的微表面BRDF模型：

$$f_r = k_d \cdot f_{Lambert} + k_s \cdot f_{Cook-Torrance}$$

其中：
- $k_d$：漫反射比例（非金属材质）
- $k_s$：高光比例
- $k_d + k_s \leq 1$（能量守恒）

镜面项：
$$f_{Cook-Torrance}(\omega_i, \omega_o) = \frac{D(h) \cdot F(\omega_i, h) \cdot G(\omega_i, \omega_o, h)}{4(\omega_i \cdot n)(\omega_o \cdot n)}$$

### 3.2 金属/非金属工作流

| 属性 | 电介质（非金属） | 导体（金属） |
|------|----------------|-------------|
| F0 | 0.04（恒定） | 有色（RGB值） |
| 漫反射 | 有（albedo） | 无（F0吸收所有光） |
| 反射颜色 | 无色 | 有色（金的F0偏黄） |
| 粗糙度 | 常见范围0.1~0.9 | 常见范围0.0~0.5 |

### 3.3 Python实现

```python
import numpy as np

def cook_torrance_brdf(N, L, V, albedo, metallic, roughness, f0=0.04):
    """
    Cook-Torrance BRDF
    
    参数:
        N: 法线向量
        L: 入射光方向
        V: 观察方向
        albedo: 反照率（RGB）
        metallic: 金属度 [0, 1]
        roughness: 粗糙度 [0, 1]
        f0: 法向反射率（非金属默认0.04）
    """
    H = (L + V) / (np.linalg.norm(L + V) + 1e-6)
    
    NdotL = max(np.dot(N, L), 0.0)
    NdotV = max(np.dot(N, V), 0.0)
    NdotH = max(np.dot(N, H), 0.0)
    HdotV = max(np.dot(H, V), 0.0)
    
    if NdotL == 0 or NdotV == 0:
        return np.zeros(3)
    
    # 法线分布函数 D (GGX)
    alpha = roughness * roughness
    alpha2 = alpha * alpha
    denom = np.pi * (NdotH * NdotH * (alpha2 - 1.0) + 1.0) ** 2
    D = alpha2 / denom
    
    # 几何函数 G (Smith GGX)
    def smith_ggx(NdotX):
        k = alpha / 2.0  # 直接光照k = alpha/2
        return NdotX / (NdotX * (1.0 - k) + k)
    G = smith_ggx(NdotL) * smith_ggx(NdotV)
    
    # 菲涅尔项 F (Schlick近似)
    F0_mix = f0 * (1.0 - metallic) + albedo * metallic
    F = F0_mix + (1.0 - F0_mix) * (1.0 - HdotV) ** 5
    
    # 镜面BRDF
    spec_brdf = D * F * G / (4.0 * NdotL * NdotV + 1e-6)
    
    # 漫反射BRDF (金属无漫反射)
    kd = (1.0 - F) * (1.0 - metallic)
    diff_brdf = albedo / np.pi * kd
    
    # 最终BRDF
    return diff_brdf + spec_brdf
```

## 4. 基于物理的渲染（PBR）工作流

### 4.1 PBR材质贴图

现代PBR使用一组标准贴图：

| 贴图 | 通道 | 作用 | 取值范围 |
|------|------|------|---------|
| **Albedo Map** | RGB | 基础颜色/反照率 | [0,1] |
| **Normal Map** | RGB | 法线扰动（编码到切线空间） | [0,1]→[-1,1] |
| **Metallic Map** | R | 金属度 | 0=非金属, 1=金属 |
| **Roughness Map** | R | 粗糙度 | 0=镜面, 1=粗糙 |
| **AO Map** | R | 环境光遮蔽（Ambient Occlusion） | 0=全遮蔽, 1=无遮蔽 |
| **Displacement/Bump** | R | 位移/凹凸（细分时用） | [0,1] |

**Albedo + Metallic + Roughness 三贴图解释：**

```
Albedo（漫反射颜色）：
  非金属 → 30-240（sRGB）
  金属   → 180-255（且几乎无漫反射，反射来自F0）

Metallic（金属度）：
  0.0 → 电介质/非金属（塑料、木头、石头）
  1.0 → 导体/金属（金、银、铁、铜）

Roughness（粗糙度）：
  0.0 → 完美镜面（抛光金属、镜面）
  1.0 → 完全粗糙（水泥、纸张、布料）
```

### 4.2 PBR渲染管线

```
输入: Albedo, Normal, Metallic, Roughness, AO
    
1. 采样Normal Map
   │
2. 计算法线（切线空间 → 世界空间）
   │
3. 对所有光源计算BRDF
   │
4. 叠加环境光照（IBL / Skybox）
   │
5. 应用AO（环境光遮蔽）
   │
输出: 最终像素颜色
```

### 4.3 切线空间与法线映射

Normal Map中的法线存储在**切线空间**（Tangent Space），需要转换到世界空间：

```python
def world_from_tangent_normal(normal_map_sample, normal, tangent, bitangent):
    """
    将切线空间法线转换到世界空间
    """
    # 切线空间法线（解码）
    tn = normal_map_sample * 2.0 - 1.0
    tn = tn / np.linalg.norm(tn)
    
    # TBN矩阵
    TBN = np.array([tangent, bitangent, normal]).T  # 列向量
    
    # 世界空间法线
    world_normal = TBN @ tn
    world_normal = world_normal / np.linalg.norm(world_normal)
    
    return world_normal
```

### 4.4 多光源渲染

```python
def pbr_shading(N, V, position, albedo, metallic, roughness, ao, lights):
    """
    PBR光照计算（多光源）
    
    lights: [(position, color, intensity), ...]
    """
    color = np.zeros(3)
    
    for light_pos, light_color, intensity in lights:
        L = light_pos - position
        distance = np.linalg.norm(L)
        L = L / distance
        
        # 平方反比衰减
        attenuation = intensity / (distance * distance + 1e-6)
        
        # BRDF
        brdf = cook_torrance_brdf(N, L, V, albedo, metallic, roughness)
        
        # 积累颜色
        color += brdf * light_color * attenuation * max(np.dot(N, L), 0.0)
    
    # 应用AO
    color *= ao
    
    # 环境光
    ambient = albedo * 0.03 * ao
    color += ambient
    
    return np.clip(color, 0.0, 1.0)
```

## 5. IBL（基于图像的照明）简介

### 5.1 什么是IBL

IBL（Image-Based Lighting）使用**全景环境贴图**（如HDR天空球）作为光源，提供**全局漫反射**和**环境反射**：

```
环境贴图（.hdr 立方体贴图）
    ├── 漫反射IBL（Irradiance Map）：预计算漫反射照明
    └── 镜面IBL（Specular IBL）：预计算各粗糙度级别的反射
```

### 5.2 漫反射IBL：Irradiance Map

对环境的每个方向卷积（求平均）来得到漫反射光照：

```python
def compute_irradiance(env_map):
    """
    预计算Irradiance Map
    对每个法线方向，采样半球面上的所有入射光并求平均
    """
    irradiance = np.zeros_like(env_map)
    
    for i in range(env_map.shape[0]):   # 水平角
        for j in range(env_map.shape[1]):   # 垂直角
            normal = direction_from_uv(i, j)
            
            total_radiance = 0
            sample_count = 0
            
            # 半球面采样
            for theta in range(0, 64):
                for phi in range(0, 64):
                    sample_dir = spherical_to_cartesian(theta, phi)
                    if np.dot(normal, sample_dir) > 0:  # 在上半球
                        radiance = sample_env_map(env_map, sample_dir)
                        total_radiance += radiance * max(np.dot(normal, sample_dir), 0)
                        sample_count += 1
            
            irradiance[i, j] = total_radiance / sample_count
    
    return irradiance
```

### 5.3 镜面IBL：Pre-filtered Environment Map

对不同粗糙度级别预过滤环境贴图：

```python
def prefilter_env_map(env_map, roughness, samples=1024):
    """
    对特定粗糙度值预过滤环境贴图
    粗糙度越高，采样范围越大（反射越模糊）
    """
    filtered = np.zeros_like(env_map)
    
    for i in range(env_map.shape[0]):
        for j in range(env_map.shape[1]):
            R = direction_from_uv(i, j)
            
            total_weight = 0
            weighted_color = np.zeros(3)
            
            for _ in range(samples):
                # 根据roughness生成随机微表面法线
                xi = np.random.random(2)
                h = ggx_sampling(xi, roughness)
                
                # 反射方向
                L = reflect(-R, h)
                
                if np.dot(L, N) > 0:  # 确保在上半球
                    color = sample_env_map(env_map, L)
                    NdotH = max(np.dot(N, h), 0)
                    weight = NdotH  # 重要性采样权重
                    
                    weighted_color += color * weight
                    total_weight += weight
            
            filtered[i, j] = weighted_color / total_weight
    
    return filtered
```

### 5.4 完整的IBL着色

**分割求和近似（Split Sum Approximation）**：

$$L_o \approx \frac{1}{N} \sum L_i(p, \omega_i) \cdot f_r(p, \omega_i, \omega_o) \cos\theta_i$$

分解为两个独立求和：
1. **预过滤环境贴图**（仅依赖roughness）：$\frac{1}{N} \sum L_i \cdots$
2. **BRDF积分LUT**（依赖NdotV和roughness）：$\frac{1}{N} \sum f_r \cdots$

```glsl
// IBL光照（简化）
vec3 ibl_lighting(vec3 N, vec3 V, vec3 albedo, float metallic, float roughness) {
    vec3 R = reflect(-V, N);
    
    // 漫反射IBL
    vec3 irradiance = texture(irradianceMap, N).rgb;
    vec3 diffuse = albedo * irradiance;
    
    // 镜面IBL
    vec3 prefiltered = texture(prefilterMap, R, roughness).rgb;
    vec2 envBRDF = texture(brdfLUT, vec2(max(dot(N, V), 0.0), roughness)).rg;
    
    vec3 specular = prefiltered * (f0 * envBRDF.x + envBRDF.y);
    
    // 混合
    vec3 kS = fresnel_schlick(max(dot(N, V), 0.0), f0);
    vec3 kD = (1.0 - kS) * (1.0 - metallic);
    
    return kD * diffuse + specular;
}
```

## 6. 软件渲染器实现PBR效果

### 6.1 完整代码：PBR球体渲染

```python
"""
graphics_07_pbr.py - 软件渲染器实现PBR效果

展示：在不同金属度/粗糙度下的PBR渲染效果
"""

import numpy as np
from PIL import Image
import math

# ============================================================
# Cook-Torrance BRDF
# ============================================================
def fresnel_schlick(HdotV, f0):
    """Schlick近似菲涅尔"""
    return f0 + (1.0 - f0) * (1.0 - HdotV) ** 5

def ndf_ggx(NdotH, roughness):
    """GGX法线分布函数"""
    alpha = roughness * roughness
    alpha2 = alpha * alpha
    denom = (NdotH * NdotH * (alpha2 - 1.0) + 1.0)
    return alpha2 / (math.pi * denom * denom)

def geometry_smith(NdotL, NdotV, roughness):
    """Smith几何函数（GGX）"""
    k = (roughness + 1.0) ** 2 / 8.0
    def schlick_ggx(NdotX):
        return NdotX / (NdotX * (1.0 - k) + k)
    return schlick_ggx(NdotL) * schlick_ggx(NdotV)

def cook_torrance(N, L, V, albedo, metallic, roughness, f0=0.04):
    """Cook-Torrance BRDF完整计算"""
    H = (L + V) / np.linalg.norm(L + V)
    
    NdotL = max(np.dot(N, L), 0.0)
    NdotV = max(np.dot(N, V), 0.0)
    NdotH = max(np.dot(N, H), 0.0)
    HdotV = max(np.dot(H, V), 0.0)
    
    if NdotL == 0 or NdotV == 0:
        return np.zeros(3)
    
    D = ndf_ggx(NdotH, roughness)
    G = geometry_smith(NdotL, NdotV, roughness)
    
    # 金属/非金属混合F0
    f0_vec = np.array(f0) * (1.0 - metallic) + np.array(albedo) * metallic
    F = fresnel_schlick(HdotV, f0_vec)
    
    # 镜面BRDF
    spec_brdf = D * F * G / (4.0 * NdotL * NdotV + 1e-6)
    
    # 漫反射（金属无漫反射）
    kd = (1.0 - F) * (1.0 - metallic)
    diff_brdf = np.array(albedo) / math.pi * kd
    
    return diff_brdf + spec_brdf

# ============================================================
# 场景设置
# ============================================================
class Scene:
    def __init__(self, width=512, height=512):
        self.width = width
        self.height = height
        self.lights = []
        self.objects = []
        
    def add_light(self, position, color=(1,1,1), intensity=10.0):
        self.lights.append({
            'position': np.array(position, dtype=np.float32),
            'color': np.array(color, dtype=np.float32),
            'intensity': intensity
        })
    
    def add_sphere(self, center, radius, albedo, metallic, roughness):
        self.objects.append({
            'center': np.array(center, dtype=np.float32),
            'radius': radius,
            'albedo': np.array(albedo, dtype=np.float32),
            'metallic': metallic,
            'roughness': roughness,
        })

# ============================================================
# Ray-Sphere Intersection
# ============================================================
def intersect_sphere(ray_origin, ray_dir, sphere):
    oc = ray_origin - sphere['center']
    a = np.dot(ray_dir, ray_dir)
    b = 2.0 * np.dot(oc, ray_dir)
    c = np.dot(oc, oc) - sphere['radius'] ** 2
    disc = b * b - 4 * a * c
    
    if disc < 0:
        return None
    
    t = (-b - math.sqrt(disc)) / (2.0 * a)
    if t < 0.001:
        return None
    return t

# ============================================================
# PBR渲染器（简单光线追踪）
# ============================================================
def render_pbr(scene, samples=16):
    """使用简单光线追踪进行PBR渲染"""
    img = np.zeros((scene.height, scene.width, 3), dtype=np.float32)
    
    # 相机
    eye = np.array([0.0, 1.0, 5.0], dtype=np.float32)
    
    for py in range(scene.height):
        for px in range(scene.width):
            color = np.zeros(3)
            
            # 子像素采样（SSAA抗锯齿）
            for sy in range(samples):
                # 子像素偏移
                jitter_x = (px + (sy % 4 + 0.5) / 4) / scene.width
                jitter_y = (py + (sy // 4 + 0.5) / 4) / scene.height
                
                # 生成光线方向
                x = 2.0 * jitter_x - 1.0
                y = 1.0 - 2.0 * jitter_y
                aspect = scene.width / scene.height
                x *= aspect
                
                ray_dir = np.array([x, y, -1.0], dtype=np.float32)
                ray_dir = ray_dir / np.linalg.norm(ray_dir)
                
                # 光线追踪
                hit_color = trace_pbr(eye, ray_dir, scene)
                color += hit_color
            
            color /= samples
            img[py, px] = np.clip(color, 0.0, 1.0)
        
        if py % 32 == 0:
            print(f"  行 {py}/{scene.height} 完成")
    
    return img

def trace_pbr(ray_origin, ray_dir, scene):
    """PBR路径追踪（单光线）"""
    closest_t = float('inf')
    hit_obj = None
    
    for obj in scene.objects:
        t = intersect_sphere(ray_origin, ray_dir, obj)
        if t and t < closest_t:
            closest_t = t
            hit_obj = obj
    
    if not hit_obj:
        return np.zeros(3)
    
    # 命中点
    hit_point = ray_origin + ray_dir * closest_t
    N = (hit_point - hit_obj['center']) / hit_obj['radius']
    V = -ray_dir
    
    # PBR光照
    color = np.zeros(3)
    
    for light in scene.lights:
        L = light['position'] - hit_point
        dist = np.linalg.norm(L)
        L = L / dist
        
        # 阴影检测
        shadow_origin = hit_point + N * 0.001
        in_shadow = False
        for obj in scene.objects:
            if obj is hit_obj:
                continue
            t = intersect_sphere(shadow_origin, L, obj)
            if t and t < dist:
                in_shadow = True
                break
        
        if not in_shadow:
            NdotL = max(np.dot(N, L), 0.0)
            if NdotL > 0:
                brdf = cook_torrance(
                    N, L, V,
                    hit_obj['albedo'],
                    hit_obj['metallic'],
                    hit_obj['roughness']
                )
                attenuation = light['intensity'] / (dist * dist + 1e-6)
                color += brdf * light['color'] * attenuation * NdotL
    
    # 环境光
    color += hit_obj['albedo'] * 0.02
    
    return np.clip(color, 0.0, 1.0)

# ============================================================
# 主程序
# ============================================================
def main():
    print("=== PBR渲染器启动 ===")
    print("渲染多组金属度/粗糙度的球体来展示PBR效果")
    
    scene = Scene(640, 480)
    
    # 添加光源
    scene.add_light((5.0, 8.0, 3.0), intensity=20.0)
    scene.add_light((-3.0, 4.0, 6.0), intensity=15.0)
    scene.add_light((0.0, -2.0, 8.0), intensity=5.0)
    
    # 添加PBR材质球体
    # 3行 × 4列 = 12个球体
    # 行：粗糙度从0.1到0.8
    # 列：金属度从0.0到1.0
    metallic_values = [0.0, 0.33, 0.66, 1.0]
    roughness_values = [0.1, 0.35, 0.6, 0.8]
    colors = [
        (0.8, 0.2, 0.2),   # 红/铜色
        (0.2, 0.8, 0.2),   # 绿
        (0.2, 0.4, 0.8),   # 蓝
        (1.0, 0.8, 0.2),   # 金色
    ]
    
    spacing_x = 2.8
    spacing_y = 2.5
    start_x = -4.2
    start_y = 3.0
    
    for row in range(4):
        for col in range(4):
            roughness = roughness_values[row]
            metallic = metallic_values[col]
            color_idx = col
            if color_idx >= len(colors):
                color_idx = len(colors) - 1
            
            center = (
                start_x + col * spacing_x,
                start_y - row * spacing_y,
                0.0
            )
            
            scene.add_sphere(
                center, 1.0,
                colors[color_idx],
                metallic,
                roughness
            )
    
    print("开始渲染...")
    img = render_pbr(scene, samples=9)  # 3×3子采样
    
    output_path = 'memory/learning/figures/graphics_07_pbr.png'
    out_img = Image.fromarray((img * 255).astype(np.uint8))
    out_img.save(output_path)
    print(f"\nPBR渲染完成！图片已保存到 {output_path}")
    print("\n渲染说明：")
    print("- 4行 × 4列 = 16个PBR材质的球体")
    print("- 行从上到下：粗糙度 0.1 → 0.8")
    print("- 列从左到右：金属度 0.0 → 1.0")
    print("- 展示了金属/非金属在不同粗糙度下的外观差异")

if __name__ == '__main__':
    main()
```

### 6.2 PBR效果图示例解读

```
          金属度 0.0    0.33    0.66    1.0
粗糙度 0.1  [塑料]     [铁]     [铜]     [金]
       0.35 [磨砂塑料]  [锈铁]   [哑金]   [哑金]
       0.6  [粗糙塑料]  [锈铁]   [粗糙铜] [粗糙金]
       0.8  [粗糙石]    [粗糙铁] [粗糙铜] [粗糙金]
```

观察要点：
- **粗糙度低（0.1）**：清晰的高光反射
- **粗糙度高（0.8）**：弥散的高光，类似磨砂
- **金属度低（0.0）**：漫反射为主，高光无色（F0=0.04）
- **金属度高（1.0）**：无漫反射，有色高光（F0=albedo）
- **金/铜**等金属：高光带颜色

## 7. PBR实践指南

### 7.1 常见材质的PBR参数

| 材质 | Albedo (sRGB) | Metallic | Roughness |
|------|---------------|----------|-----------|
| 纯金 | (1.00, 0.71, 0.29) | 1.0 | 0.1~0.4 |
| 纯银 | (0.95, 0.93, 0.88) | 1.0 | 0.1~0.3 |
| 铸铁 | (0.56, 0.57, 0.58) | 1.0 | 0.4~0.8 |
| 铜 | (0.95, 0.64, 0.54) | 1.0 | 0.2~0.5 |
| 塑料 | 各种颜色 | 0.0 | 0.3~0.6 |
| 木头 | (0.50~0.80) | 0.0 | 0.7~0.9 |
| 混凝土 | (0.50~0.70) | 0.0 | 0.8~0.9 |
| 皮肤 | (0.70~0.80) | 0.0 | 0.4~0.6 |
| 玻璃 | (0.90~1.00) | 0.0 | 0.0~0.1 |
| 橡胶/轮胎 | (0.03~0.10) | 0.0 | 0.7~0.9 |

### 7.2 PBR最佳实践

1. **能量守恒**：反射 + 漫反射 ≤ 入射光
2. **金属无漫反射**：metallic=1.0时，漫反射贡献为0
3. **F0不超1.0**：非金属F0≈0.04，金属F0来自albedo
4. **带伽马矫正**：贴图在sRGB空间，计算在线性空间
5. **HDR渲染**：使用浮点帧缓冲，最终做Tone Mapping

### 7.3 常见PBR模型对比

| 模型 | 特点 | 适用场景 |
|------|------|---------|
| Cook-Torrance (GGX) | 最常用，长尾高光 | 游戏/影视通用 |
| Ward BRDF | 无菲涅尔项 | 布料/各向异性材料 |
| Ashikhmin-Shirley | 各向异性 | 拉丝金属/头发 |
| Disney BRDF | 经验模型，易用 | 生产级动画（Disney） |
| Lambert + Blinn-Phong | 非物理 | 旧游戏/移动端 |

## 8. 总结

### PBR核心公式链路

```
渲染方程
  ├── 直接光照：Σ BRDF × Li × (N·L)
  │     └── Cook-Torrance BRDF
  │           ├── D(h) = GGX (法线分布)
  │           ├── F(ωi, h) = Schlick (菲涅尔)
  │           └── G(ωi, ωo, h) = Smith (几何遮挡)
  └── 间接光照：IBL
        ├── Irradiance Map（漫反射环境光）
        └── Pre-filtered Map + BRDF LUT（镜面环境光）
```

### PBR工作流三原则

1. **输入标准化**：Albedo/Metallic/Roughness/AO/Normal贴图
2. **金属/非金属二分法**：metallic决定F0和漫反射有无
3. **能量守恒**：ks + kd ≤ 1，环境光统一处理

### 从Blinn-Phong到PBR

| 对比 | Blinn-Phong | PBR (Cook-Torrance) |
|------|-------------|---------------------|
| 高光 | 指数控制（无物理意义） | 粗糙度控制（有物理意义） |
| 菲涅尔 | 无 | 有（Schlick近似） |
| 能量守恒 | 不保证 | 保证 |
| 金属 | 不区分 | 区分金属/非金属 |
| 一致性 | 不同光照下不一致 | 光照下表现一致 |
