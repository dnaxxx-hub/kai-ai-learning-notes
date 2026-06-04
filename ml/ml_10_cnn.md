# CNN：卷积神经网络 — 计算机视觉的基石

> 日期：2026-05-07 16:00 | 课程：ML/DL路线 Phase 3-2
> 目标：理解"卷积"为何对图像如此有效

## 核心直觉

### 为什么全连接网络不适合图像？

一张 256×256 的图 → 196,608 维向量
- 第一个隐藏层512个神经元 → 1亿个参数
- 2000个参数就学不动，别说1亿

### CNN的三个关键思想

#### 1. 局部连接（Locally Connected）
每个神经元只看图像的一小块（receptive field），不是整张图
```
全连接: 每个神经元连接所有像素
CNN:    每个神经元连接局部3×3区域

参数从: 196608 × 512 → 9 × 512（3×3卷积核）
```

#### 2. 权值共享（Weight Sharing）
同样的卷积核在整张图上滑动检测同一种特征
```
一个3×3卷积核 = 只检测一种特征（比如"水平边缘"）
用不同的卷积核检测不同的特征
```

#### 3. 池化（Pooling）
下采样，降低分辨率
```
Max Pooling: 取2×2区域的最大值
→ 图像从 28×28 缩小到 14×14
→ 参数减少4倍
→ 得到平移不变性
```

## 卷积的计算

```python
# 输入:    H × W × C_in     (高×宽×通道数)
# 卷积核: k × k × C_in × C_out (C_out个不同的核)
# 输出:    H' × W' × C_out

# 每个输出通道 = 输入和对应卷积核的互相关
def conv2d_simple(img, kernel):
    """单通道卷积"""
    h, w = img.shape
    k = kernel.shape[0]
    out = np.zeros((h-k+1, w-k+1))
    for i in range(out.shape[0]):
        for j in range(out.shape[1]):
            out[i,j] = (img[i:i+k, j:j+k] * kernel).sum()
    return out
```

## 经典架构演进

| 架构 | 年份 | 关键创新 |
|------|------|---------|
| LeNet-5 | 1998 | 第一个CNN，手写数字识别 |
| AlexNet | 2012 | GPU训练 + ReLU + Dropout，ImageNet夺冠 |
| VGGNet | 2014 | 3×3小卷积核堆叠，很深 |
| GoogLeNet | 2014 | Inception模块（多尺度卷积并行）|
| ResNet | 2015 | **残差连接**（Skip Connection），152层 |
| DenseNet | 2017 | 每层连接所有前面层 |

### ResNet — 最重要的创新
```python
# 普通网络: output = F(input)     # F是几个卷积层
# ResNet:   output = F(input) + input  # 加上恒等映射

# 为什么有用？
# 梯度直通过跳过卷积层回到浅层
# → 解决深层网络梯度消失问题
# → 可以堆152层甚至1000+层
```

## 可视化

![CNN卷积核](10_cnn_filters.png)

- **原始图像**：一个简单方块图案
- **Sobel X核**：检测垂直边缘（方块左右两侧被激活）
- **Sobel Y核**：检测水平边缘（方块上下两侧被激活）
- **Blur核**：平滑模糊效果
- **Pooling**：2×2最大池化将28×28降为14×14

这解释了CNN第一层在做什么：**不同的核检测不同的低级特征**。

## 从卷积到全连接

```python
# CNN典型结构：
# 输入 → [Conv → ReLU → Pool] × N → Flatten → FC → Softmax

# 卷积层：提取特征（保留空间结构）
# 池化层：降低分辨率（减少参数）
# 全连接层：做最终分类（展开成一维向量）
```

## 与视觉之外的联系

| CNN概念 | NLP内的类似 |
|--------|-----------|
| 2D卷积核 | 1D卷积（文本的n-gram检测）|
| 池化 | 全局平均池化（GAP） |
| 残差连接 | Transformer中的Skip Connection |
| 特征图 | Token的通道表示 |

## 今日收获
- CNN的三个核心：局部连接 + 权值共享 + 池化
- **卷积核 = 特征检测器**，不同核检测不同特征
- 浅层：边缘/纹理 → 深层：物体部件/完整物体
- ResNet是CNN最重要的创新（残差连接让深度成为可能）
- 卷积的思想也影响到了NLP（TextCNN）和Transformer
