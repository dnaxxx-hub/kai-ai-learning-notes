# 软渲染器笔记 06 — 纹理映射实战与总结

> 从零实现 3D 软渲染器系列 · 第六篇（完结篇）

---

## 1. 纹理映射精要重述

### 1.1 透视校正的重要性

**问题**：直接线性插值 UV 会导致远处纹理变形

**解法**：用深度倒数 1/z 加权插值

```
实际线性变量：clip_space 中的 X/w, Y/w
透视校正 UV = (α * u₀/z₀ + β * u₁/z₁ + γ * u₂/z₂) / (α/z₀ + β/z₁ + γ/z₂)
```

### 1.2 纹理采样策略对比

| 方法 | 质量 | 速度 | 适用场景 |
|------|------|------|----------|
| 最近邻 | 差 | 最快 | 像素风格 |
| 双线性 | 好 | 快 | 一般渲染 |
| 三线性(Mipmap) | 很好 | 中 | 远距离 |
| 各向异性 | 最好 | 慢 | 倾斜面 |

---

## 2. PBR 简述 (Physically Based Rendering)

### 2.1 核心概念
- **能量守恒**：反射 + 折射 ≤ 入射
- **微表面模型**：表面由微小的镜面反射面组成
- **Cook-Torrance BRDF**

### 2.2 简化 PBR 公式
```
final_color = (ambient + diffuse * (1 - metallic)) * albedo 
              + specular * F * G * D / (4 * dot(N,L) * dot(N,V))
```
- F：菲涅尔项 (Fresnel) — 掠射角反射更强
- G：几何遮挡 (Geometry) — 微表面相互遮蔽
- D：法线分布 (NDF) — 微表面朝向分布

---

## 3. 软渲染器实现检查清单

### ✅ 已完成
- [x] Vec3 / Mat4 数学库
- [x] 基本变换（平移、旋转、缩放）
- [x] 透视投影 + 视口变换
- [x] Bresenham 画线
- [x] 三角形光栅化（Barycentric）
- [x] 背面剔除
- [x] Z-buffer 深度测试
- [x] 朗伯漫反射 + Blinn-Phong 高光
- [x] UV 纹理映射 + 透视校正
- [x] 双线性纹理过滤
- [x] .obj 模型加载
- [x] PNG 输出

### 🔜 可扩展
- [ ] 阴影映射
- [ ] SSAO
- [ ] 多个光源
- [ ] PBR 材质
- [ ] Gamma 校正
- [ ] 抗锯齿
- [ ] 动画旋转

---

## 4. 核心实现架构

```
soft_renderer.py
├── Vec3        — 3D 向量运算
├── Mat4        — 4×4 矩阵运算 + 变换矩阵生成
├── Texture     — 纹理加载与采样
├── Shader      — Blinn-Phong 着色
├── Model       — .obj 解析 + 顶点存储
├── Device      — 光栅化 + 深度缓冲 + 帧缓冲
├── Renderer    — 渲染管线编排
└── main()      — 场景定义 + 渲染输出
```

---

## 5. .obj 格式简析

```
# 顶点坐标
v 0.5 -0.5 0.5
# 纹理坐标
vt 0.0 0.0
# 法线
vn 0.0 0.0 1.0
# 面（顶点索引/纹理索引/法线索引）
f 1/1/1 2/2/1 3/3/1
```

**注意**：.obj 索引从 1 开始，需要 -1 转换为 Python 索引

---

## 6. 性能优化提示

### 6.1 Python 软渲染器的瓶颈
- 单像素循环（纯 Python 慢）
- 每帧重新计算所有顶点变换
- 大量浮点运算

### 6.2 可做的优化
- 使用 numpy 加速矩阵运算
- 预计算不变数据（光照方向等）
- 减少 Python 属性访问开销
- 使用局部变量缓存重复计算
- 行缓存加速纹理采样

---

## 7. 扩展学习

### 7.1 进一步方向
1. **GPU 管线类比**：理解 shader 编程
2. **光线追踪**：全局光照效果
3. **WebGPU/Vulkan**：现代 GPU API
4. **游戏引擎**：Unity/Unreal 渲染管线

### 7.2 参考资源
- 《Fundamentals of Computer Graphics》(虎书)
- LearnOpenGL (https://learnopengl.com)
- Scratchapixel (https://scratchapixel.com)
- tinyrenderer GitHub (ssloy)

---

## 附录：测试命令

```bash
# 生成线框立方体
python soft_renderer.py wireframe

# 生成纹理光照立方体
python soft_renderer.py textured
```

输出保存在 `output/` 目录下。
