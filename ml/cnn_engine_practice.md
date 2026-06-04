# CNN 推理引擎实战笔记

## 概述
纯 numpy 实现 CNN 推理引擎，从零构建卷积神经网络的前向传播管线。

## 核心设计

### im2col 算法
卷积层性能的关键：将输入图像展开成列矩阵，将卷积核展平成行矩阵，用一次 matmul 替代 4 层嵌套循环。

**算法步骤**：
1. pad 输入
2. 在每个 (kh, kw) 窗口位置提取列向量 → 组成 (N*H_out*W_out, C*kh*kw) 矩阵
3. 将卷积核展平成 (C_out, C*kh*kw)
4. out = cols @ W.T + bias

### 实现的层
| 层 | 说明 |
|------|------|
| Conv2D | im2col + matmul 高效卷积 |
| MaxPool2D | 滑动窗口取最大值 |
| AveragePool2D | 滑动窗口取平均 |
| Linear | 全连接层 xW^T + b |
| ReLU | max(0, x) |
| Sigmoid | 1/(1+e^-x) |
| Tanh | 双曲正切 |
| BatchNorm2D | 推理模式使用 running_mean/var |
| Flatten | (B,C,H,W)→(B, C*H*W) |
| Dropout | 推理模式直通 |
| Softmax | 带数值稳定的指数归一化 |
| ResidualBlock | Conv→BN→ReLU→Conv→BN→残差连接 |
| Sequential | 顺序容器 |

### LeNet-5 风格网络
```
Conv2D(1,6,5,p2) → ReLU → MaxPool(2)
→ Conv2D(6,16,5) → ReLU → MaxPool(2)
→ Flatten → Linear(400,120) → ReLU
→ Linear(120,84) → ReLU
→ Linear(84,10) → Softmax
```

## 关键学习

1. **im2col 的空间换时间**：将 small convolutions 转换为 Large matrix multiply，现代 CPU/GPU 对 matmul 有深度优化
2. **软最大化数值稳定**：减去 max 防止 exp 溢出
3. **BatchNorm 推理/训练模式区别**：训练用 batch 统计量，推理用 running 统计量
4. **残差连接 = 恒等映射**：stride/channel 变化时用 1x1 卷积适配
