# 第二课：防御机制

## 概述

正如同矛与盾的关系，对抗攻击的发展同时推动了防御机制的进步。从最早的对抗训练到今天的认证防御（Certified Defense），防御技术经历了三轮迭代：

1. **第一代**（2014-2016）：启发式防御，缺乏理论保证
2. **第二代**（2017-2019）：基于对抗训练的强经验防御
3. **第三代**（2020-至今）：可认证的正式防御

但一个残酷的事实是：**几乎所有第一代防御都已被攻破**。这提醒我们，防御必须有理论支撑，不能仅凭直觉。

## 1. 对抗训练（Adversarial Training）

### 核心思想

对抗训练是目前经验上最有效的防御方法。思路极其简单：**在训练过程中持续注入对抗样本**，让模型学会抵抗它们。

形式化描述——最小-最大优化问题：

```
min_θ  E_(x,y)~D [ max_||δ||≤ε L(θ, x+δ, y) ]
```

- **内层最大化**：找到当前模型最危险的对抗样本
- **外层最小化**：让模型在这些困难样本上的损失最小

### 关键实现细节

#### 1.1 PGD 对抗训练

Madry 在 2017 年证明，使用 PGD-40（40步PGD）生成的对抗样本训练，可以获得最强的鲁棒性：

```python
import torch
import torch.nn as nn
import torch.optim as optim

def adversarial_training_step(model, dataloader, optimizer, epsilon=0.03, 
                               alpha=0.01, pgd_iters=7):
    """
    单步对抗训练（PGD-7，实际中常用7步）
    """
    model.train()
    total_loss = 0
    
    for images, labels in dataloader:
        images, labels = images.cuda(), labels.cuda()
        
        # --- 生成对抗样本 ---
        # 保存原始图片
        original = images.clone().detach()
        
        # 随机初始化扰动
        delta = torch.empty_like(images).uniform_(-epsilon, epsilon)
        delta = torch.clamp(images + delta, 0, 1) - images
        delta = delta.detach()
        
        for _ in range(pgd_iters):
            delta.requires_grad = True
            adv_images = images + delta
            
            outputs = model(adv_images)
            loss = nn.CrossEntropyLoss()(outputs, labels)
            
            model.zero_grad()
            loss.backward()
            
            # 更新扰动（最大化损失）
            grad = delta.grad
            delta = delta + alpha * grad.sign()
            
            # 投影约束
            delta = torch.clamp(delta, min=-epsilon, max=epsilon)
            delta = torch.clamp(images + delta, 0, 1) - images
            delta = delta.detach()
        
        adv_images = images + delta
        
        # --- 在对抗样本上训练 ---
        # 混合训练：同时用干净和对抗样本（提升标准准确率）
        # 比例可调，通常 50% 干净 + 50% 对抗
        
        # 标准对抗训练（只用对抗样本）：
        outputs = model(adv_images)
        loss = nn.CrossEntropyLoss()(outputs, labels)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
    
    return total_loss / len(dataloader)
```

#### 1.2 对抗训练 vs 标准训练效果对比

| 指标 | 标准训练 | 对抗训练（ε=8/255） |
|------|---------|-------------------|
| 标准 CIFAR-10 准确率 | 95%+ | ~87% |
| PGD-20 攻击下准确率 | ~0% | ~50% |
| 训练时间 | 1x | 7-40x（取决于PGD步数） |

### Fast Adversarial Training

2020年有研究发现，使用"灾难性遗忘"技巧和恰当的学习率调度，可以用单步 FGSM 做到与多步 PGD 相当的鲁棒性——训练速度提升 7 倍。但这种方法对超参数极度敏感，不稳定的情况经常发生。

## 2. 输入变换防御（Input Transformation）

输入变换的直觉是：先对输入做某种预处理，使对抗扰动被"破坏"，然后再送入模型。

```python
def input_transformation_defense(images, defense_type="jpeg"):
    """
    输入变换防御示例
    """
    if defense_type == "jpeg":
        # JPEG 压缩可以破坏高频对抗扰动
        return jpeg_compress(images, quality=75)
    
    elif defense_type == "randomization":
        # 随机缩放+填充
        size = images.shape[-1]
        scale_factor = random.uniform(0.9, 1.1)
        scaled = F.interpolate(images, 
                               size=int(size * scale_factor), 
                               mode='bilinear')
        return F.pad(scaled, pad=(0, size - scaled.shape[-1]))
    
    elif defense_type == "feature_squeezing":
        # 特征压缩（减少色彩深度）
        return (images * 63).round() / 63  # 压缩到 6-bit
    
    elif defense_type == "total_variance_min":
        # TV 最小化去噪
        return tv_denoise(images, weight=0.1)
    
    return images
```

### 常见输入变换方法

| 方法 | 原理 | 效果 | 缺点 |
|------|------|------|------|
| JPEG 压缩 | 消除高频扰动 | 对中等 ε 有效 | 大 ε 时无效 |
| 随机填充/裁剪 | 空间随机化 | 提高迁移防御 | 需计算期望 |
| 特征压缩 | 减少表示精度 | 简单高效 | 损失信息 |

**⚠️ 注意**：单独使用输入变换防御往往不够安全。如果攻击者知道变换参数，可以轻松端到端攻破。因此它们最好作为辅助防线。

## 3. 对抗样本检测

### 3.1 基于统计的方法

利用对抗样本和正常样本在不同统计特征上的差异来区分。

```python
def detect_adversarial_by_kernel_density(model, images):
    """
    特征空间核密度检测
    假设：对抗样本在特征空间中远离类中心
    """
    # 提取倒数第二层特征
    features, logits = model.extract_features(images)
    
    # 计算到类中心的距离
    class_centers = get_class_centers(model)  # 从训练集计算
    
    predicted = logits.argmax(dim=1)
    distances = []
    
    for i, label in enumerate(predicted):
        center = class_centers[label.item()]
        dist = torch.norm(features[i] - center, p=2)
        distances.append(dist.item())
    
    # 超过阈值的判断为对抗样本
    threshold = 0.95  # 从验证集校准
    is_adversarial = [d > threshold for d in distances]
    return is_adversarial
```

### 3.2 Local Intrinsic Dimensionality (LID)

LID 是一种更先进的检测方法。核心观察：对抗样本所在区域的局部内在维度显著高于正常样本空间。

```python
def compute_lid(samples, reference, k=20):
    """
    计算局部内在维度
    """
    # 对每个样本，找到 k 个最近邻（在参考集中）
    from sklearn.neighbors import NearestNeighbors
    
    nbrs = NearestNeighbors(n_neighbors=k, algorithm='ball_tree').fit(reference)
    distances, _ = nbrs.kneighbors(samples)
    
    # MLE 估计 LID
    lid = []
    for i in range(len(samples)):
        dist = distances[i, 1:]  # 排除自身（距离0）
        # LID 的 MLE 估计
        r_max = dist[-1]
        hat = len(dist) / (sum(np.log(r_max / d) for d in dist))
        lid.append(hat)
    
    return np.array(lid)
```

**检测的猫鼠游戏**：攻击者可以针对检测器构造"感知器"的对抗样本——同时欺骗分类器和检测器。

## 4. 认证防御（Certified Defense）

### 随机平滑（Randomized Smoothing）

这是目前最具可扩展性的认证防御方法，由 Cohen 等人在 2019 年提出。核心思想：**用噪声平滑预测函数**。

```python
def randomized_smoothing_predict(model, images, noise_std=0.25, 
                                 n_samples=100, alpha=0.001):
    """
    随机平滑：用高斯噪声投票，给出带置信边界的预测
    """
    model.eval()
    votes = torch.zeros(n_samples)
    
    for i in range(n_samples):
        # 加入高斯噪声
        noise = torch.randn_like(images) * noise_std
        noisy_input = images + noise
        noisy_input = torch.clamp(noisy_input, 0, 1)
        
        # 预测
        output = model(noisy_input)
        votes[i] = output.argmax(dim=1)
    
    # 统计得票最多的类别
    winner = votes.mode()[0]
    count = (votes == winner).sum().item()
    
    # 二项分布置信下界
    from scipy.stats import binom
    p_lower = binom.ppf(alpha / 2, n_samples, count / n_samples)
    
    # 认证半径：在该半径内保证不会改变预测
    certified_radius = noise_std * norm.ppf(p_lower)
    
    return winner, certified_radius
```

**为什么随机平滑有效？** 添加噪声使得攻击者的精确梯度变得不可用。要绕过平滑函数，攻击者需要扰动输入使得在"几乎所有噪声采样下"的输出都发生变化——这需要极大的扰动，远超认证半径。

### 认证防御的当前局限

| 维度 | 状况 |
|------|------|
| 认证半径 | 通常只有 ε=0.25（L2）级别，对大扰动无效 |
| 计算成本 | 每个输入需要上百次前向传播 |
| 适用模型 | 主要对中小规模网络有效 |
| 完整认证 | 对 L∞ 扰动下的 ResNet 尚未有实用方案 |

## 5. 梯度混淆（Gradient Masking / Obfuscation）

### 什么是梯度混淆？

攻击者依赖梯度信息生成对抗样本，如果让"梯度信号失效"或"梯度难以获取"，就能阻止白盒攻击。

### 三种主要方式

1. **破坏梯度可用性**：如防御性蒸馏（用教师网络的软化概率训练学生）
2. **梯度爆炸/消失**：如加入不可微操作（JPEG压缩、reLU的硬阈值）
3. **随机梯度**：每次前向传播使用不同模型

### 为什么梯度混淆是伪防御？

**⚠️ 重要教训**：所有已知的梯度混淆防御都已被攻破。

```python
# 看似有效的梯度混淆防御
class ShatteredGradientDefense(nn.Module):
    """引入不可微操作 - 但攻击者可以用 Backward Pass 
    可微分近似(Approximation) 来绕过"""
    
    def forward(self, x):
        x = self.conv1(x)
        # 这个操作不可微
        x = self.non_differentiable_preprocess(x)  
        x = self.conv2(x)
        return x
    
    def non_differentiable_preprocess(self, x):
        # 例如：二值化
        return (x > 0.5).float()

# 攻击者的绕过方式：
# BPDA (Backward Pass Differentiable Approximation)
# 前向传播用真实函数，反向传播用可微近似
```

Athalye 等人在 2018 年的论文明确指出：**只有随机平滑和对抗训练能有效抵御自适应攻击**。

## 6. 真实案例

### 腾讯朱雀实验室的攻防对抗

2021年，腾讯的朱雀实验室展示了针对人脸识别门禁系统的攻防研究：
- 攻击方打印了特制对抗眼镜框，成功通过多家厂商的人脸识别门禁
- 防御方开发了"活体检测+对抗检测"的组合方案
- 结论：单一防御机制不可靠，需要纵深防御

### Defense-GAN

使用 GAN 将输入投影到"自然图像流形"上：
```python
def defense_gan(images, generator, gd_steps=10):
    """
    Defense-GAN：在生成器流形上寻找最接近输入的点
    假设：对抗扰动会落入流形之外
    """
    # 寻找潜在空间中的向量 z，使得生成器最近的输出最接近输入
    z = torch.randn(1, latent_dim)
    z.requires_grad = True
    
    optimizer = optim.Adam([z], lr=0.01)
    for step in range(gd_steps):
        reconstructed = generator(z)
        loss = nn.MSELoss()(reconstructed, images)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    
    return generator(z).detach()
```

**缺点**：生成器覆盖的流形有限，在某些数据集上可能无法表示有效输入。

## 核心要点

1. **对抗训练是最可靠的防御基准**，没有之一
2. **认证防御虽弱但有理论保证**，是安全关键场景的首选
3. **不要发明自己的防御**——先假设它有问题，然后用自适应攻击验证
4. **纵深防御**（对抗训练+检测+输入变换）优于单点防御
5. **黑盒不是安全**——梯度混淆不等于真正的鲁棒性

## 参考文献

- Madry et al., "Towards Deep Learning Models Resistant to Adversarial Attacks", ICLR 2018
- Cohen et al., "Certified Adversarial Robustness via Randomized Smoothing", ICML 2019
- Athalye et al., "Obfuscated Gradients Give a False Sense of Security", ICML 2018
- Goodfellow et al., "Attacking Machine Learning with Adversarial Examples", 2017
