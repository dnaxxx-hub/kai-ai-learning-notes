# 图像生成与3D视觉

> 日期：2026-05-07 19:45 | 课程：CV路线 Phase 4-1
> 目标：理解"CV不止是识别，还能创造和感知三维"

## CV方向图谱

```
识别型CV:   分类 / 检测 / 分割 / 人脸识别
生成型CV:   图像生成 / 超分辨率 / 修复 / 风格迁移
三维CV:    深度估计 / 三维重建 / 双目视觉 / 点云
```

## 生成型CV（与ML/DL的生成模型重合）

### GAN for CV

```python
# Pix2Pix: 条件GAN → 输入轮廓图 → 输出真实图
# CycleGAN: 无配对也能做风格迁移（马↔斑马）
# StyleGAN: 生成高清人脸（可控每个粒度）

# 应用: 超分辨率、图像修复、老照片上色
```

### Diffusion for CV

```python
# Stable Diffusion (2022):
# 在潜空间做扩散 → 大大降低计算成本
# 文本 → 图像（Text-to-Image）
# 输入文本 + 噪音 → 逐步去噪 → 输出图像

# ControlNet: 给扩散加条件（姿态/边缘/深度）
# 用骨架图 → 生成相同姿态的人
# 用边缘图 → 保留原图结构
```

### ViT (Vision Transformer)

```python
# 2020年: 把Transformer用到图像上
#
# 把图像分成16×16的patches → 作为token序列
# 每个patch展开成一维向量 → 加位置编码
# 输入Transformer → 分类

# ViT打破了CNN的统治:
# 更大的数据集上ViT超过CNN
# 但小数据集上CNN仍然好

# 现在: Swin Transformer, ConvNeXt 融合了CNN+ViT
```

## 3D视觉基础

### 双目视觉

```python
# 人眼为什么能看到深度？
# 左右眼看到的不同 → 视差
# 
# 双目视觉:
# 左右两个摄像头 → 同一物体的位置偏移
# 偏移量(视差) → 计算深度
# 深度 = 焦距 × 基线距离 / 视差
```

### 深度估计

```python
# 从单张图估计深度 → 模糊的（一张2D图可以有很多个3D解释）
# 
# 方法:
# 1. 双目: 精确但需要两相机
# 2. 结构光 (Kinect/iPhone LiDAR):  投射红外点阵 → 三角测量
# 3. 单目深度估计 (MiDaS/DPT): 深度学习，模糊但可用
```

### 点云

```python
# 3D扫描 → 一堆三维坐标点 = 点云
# 
# 点云分析:
# PointNet: 用共享MLP处理无序点集
# PointNet++: 分层次处理（局部→全局）
# 
# 应用: 自动驾驶LiDAR、AR/VR、3D建模
```

## 今日收获
- CV生成 = GAN/Diffusion（ML生成模型的CV落地）
- ViT = Transformer接管图像（patch=token）
- 双目视觉 = 左右视差 → 深度
- 单目深度估计 = 深度学习+先验
- 点云 = 3D世界的数据格式
