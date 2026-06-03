# 第一课：对抗攻击基础

## 概述

对抗攻击（Adversarial Attack）是 AI 安全领域最基础也最重要的课题之一。其核心思想是：通过对输入数据施加人眼难以察觉的微小扰动，使深度学习模型产生完全错误的输出。这一发现由 Szegedy 等人在 2013 年首次提出，彻底改变了人们对神经网络鲁棒性的认知。

想象你有一张熊猫的图片，经过少量像素的调整后，在人类看来依然是熊猫，但模型却以 99.9% 的置信度认为这是一只长臂猿。这就是对抗攻击的力量。

## 1. FGSM（Fast Gradient Sign Method）

### 原理

FGSM 由 Goodfellow 等人在 2014 年提出，是第一个高效的对抗攻击算法。它的核心思想极其简洁：

```
x_adv = x + ε · sign(∇x J(θ, x, y))
```

其中 `∇x J` 是损失函数对输入 `x` 的梯度，`sign` 取符号方向，`ε` 控制扰动强度。FGSM 只做**一次**梯度计算，因此速度极快。

### 数学直觉

为什么只取梯度的符号（sign）而非比例值？Goodfellow 的解释是：神经网络在高维空间中存在"线性行为"，即使每个像素的微小变化方向正确，累积起来也足以让模型跨过决策边界。取符号而非幅值，保证了扰动在 L∞ 范数约束下的最大化利用。

### 代码实现（PyTorch）

```python
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.transforms as transforms
from torchvision.models import resnet50

def fgsm_attack(model, images, labels, epsilon=0.03):
    """
    FGSM 对抗攻击实现
    
    Args:
        model: 被攻击模型
        images: 原始输入张量 (batch, C, H, W)
        labels: 真实标签
        epsilon: 扰动强度，通常取 0.01~0.1
    
    Returns:
        adv_images: 对抗样本
    """
    # 确保模型处于评估模式，关闭 dropout/batch_norm 的随机性
    model.eval()
    
    # 设置 requires_grad 为 True，告诉 PyTorch 我们需要对输入求梯度
    images.requires_grad = True
    
    # 前向传播
    outputs = model(images)
    loss = nn.CrossEntropyLoss()(outputs, labels)
    
    # 清空之前的梯度，反向传播
    model.zero_grad()
    loss.backward()
    
    # 获取梯度符号方向
    grad_sign = images.grad.sign()
    
    # 生成对抗样本：沿梯度上升方向（最大化损失）扰动
    adv_images = images + epsilon * grad_sign
    
    # 裁剪到合法像素范围 [0, 1]
    adv_images = torch.clamp(adv_images, 0, 1)
    
    return adv_images.detach()

# 使用示例
if __name__ == "__main__":
    model = resnet50(pretrained=True)
    model.eval()
    
    # 加载一张图片（假设已经预处理为张量）
    from PIL import Image
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])
    
    img = Image.open("cat.jpg")
    img_tensor = transform(img).unsqueeze(0)  # shape: [1, 3, 224, 224]
    
    # 原始预测
    out = model(img_tensor)
    orig_label = out.argmax(dim=1).item()
    
    # 生成对抗样本
    fake_label = torch.tensor([655])  # 指到错误的类：枪炮
    adv = fgsm_attack(model, img_tensor, fake_label, epsilon=0.03)
    
    # 对抗样本预测
    adv_out = model(adv)
    adv_label = adv_out.argmax(dim=1).item()
    
    print(f"原始类别: {orig_label} -> 对抗类别: {adv_label}")
```

### FGSM 的局限性

- **攻击成功率有限**：单步扰动在强大防御面前常失败
- **对防御性蒸馏几乎无效**：蒸馏后梯度信号弱化
- **不够精细**：无法控制最小的必要扰动

## 2. PGD（Projected Gradient Descent）

### 原理

PGD 由 Madry 等人在 2017 年提出，是目前最强大的**一阶攻击**方法。它是 FGSM 的多步迭代版本，每一步都先朝梯度方向前进，然后投影回允许的扰动球内：

```
x^{t+1} = Π_{x+S}(x^t + α · sign(∇x J(θ, x^t, y)))
```

其中 `Π_{x+S}` 是投影操作（projection），确保对抗样本始终在允许的扰动空间内；`α` 是步长；`S` 是扰动约束集合（通常是 L∞ 球）。

### 为什么 PGD 更强？

1. **多步迭代**：每次只迈一小步，但多次累积可以跳出局部最优
2. **投影约束**：每步确保扰动不超限
3. **随机初始化**：在 L∞ 球内随机起点，避免陷入平缓区

### 代码实现

```python
def pgd_attack(model, images, labels, epsilon=0.03, alpha=0.01, iters=40, 
               random_start=True):
    """
    PGD 对抗攻击
    """
    model.eval()
    
    # 保存原始图像用于投影约束
    original = images.clone().detach()
    
    # 可选：在扰动球内随机初始化
    if random_start:
        images = images + torch.empty_like(images).uniform_(-epsilon, epsilon)
        images = torch.clamp(images, 0, 1)
    
    for i in range(iters):
        images.requires_grad = True
        outputs = model(images)
        
        # 注意：PGD 对抗训练中使用的是真实标签的交叉熵
        loss = nn.CrossEntropyLoss()(outputs, labels)
        
        model.zero_grad()
        loss.backward()
        
        # 沿梯度方向（最大化损失）
        grad = images.grad.data
        
        # 更新对抗样本
        adv = images + alpha * grad.sign()
        
        # 投影回 epsilon 邻域
        delta = torch.clamp(adv - original, min=-epsilon, max=epsilon)
        images = torch.clamp(original + delta, 0, 1).detach()
    
    return images
```

### PGD 与 FGSM 的效果对比

| 特性 | FGSM | PGD |
|------|------|-----|
| 步骤数 | 1 | 10~40 |
| 攻击成功率（白盒） | 60-80% | ~100% |
| 计算开销 | 低 | 中 |
| 可迁移性 | 好 | 中等 |
| 对抗训练后效果 | 差 | 依然有效 |

## 3. C&W（Carlini & Wagner）攻击

### 原理

Carlini 与 Wagner 在 2016 年提出的 C&W 攻击是**最优化类攻击**的代表作。与 FGSM/PGD 基于梯度符号不同，C&W 将攻击建模为一个约束优化问题：

```
minimize  ||δ||_p + c · f(x + δ)
subject to  x + δ ∈ [0, 1]^n
```

其中 `f(x')` 是精心构造的目标函数，当且仅当攻击成功时取值最小。C&W 攻击有三种变体：L0、L2、L∞，分别对应不同的范数约束。

### 为什么 C&W 重要？

1. **几乎 100% 成功率**：在白盒场景下击败了当时所有的防御
2. **最小扰动**：能找到人眼几乎不可察觉的最优扰动
3. **突破防御蒸馏**：成功攻破了 Papernot 提出的防御性蒸馏

### 代码思路（简化版）

```python
def cw_l2_attack(model, images, labels, c=1e-4, lr=1e-2, iters=1000):
    """
    C&W L2 攻击简化实现
    
    核心技巧：使用 tanh 变换将约束优化转为无约束优化
    w 是优化变量，x' = 0.5*(tanh(w)+1) 保证像素在 [0,1] 内
    """
    batch_size = images.shape[0]
    
    # 用 tanh 空间表示，消除像素约束
    w = 0.5 * torch.log((1 + images) / (1 - images + 1e-10))
    w.requires_grad = True
    
    optimizer = optim.Adam([w], lr=lr)
    
    for i in range(iters):
        # 转换回图片空间
        adv = 0.5 * (torch.tanh(w) + 1)
        
        # 计算扰动范数
        delta = adv - images
        l2_dist = torch.sum(delta.view(batch_size, -1) ** 2, dim=1)
        
        # 目标函数：让模型预测为目标类别
        outputs = model(adv)
        # 构造 f(x') 使攻击成功时 f < 0
        one_hot = torch.zeros_like(outputs)
        one_hot.scatter_(1, labels.unsqueeze(1), 1)
        
        real = (outputs * one_hot).sum(dim=1)
        other = (outputs * (1 - one_hot)).max(dim=1)[0]
        
        # f(x') = max(0, real - other + kappa)
        kappa = 0  # 置信度裕度
        f = torch.clamp(real - other + kappa, min=0)
        
        loss = l2_dist + c * f
        
        optimizer.zero_grad()
        loss.sum().backward()
        optimizer.step()
    
    return 0.5 * (torch.tanh(w) + 1)
```

## 4. 白盒攻击 vs 黑盒攻击

### 白盒攻击（White-box）

攻击者拥有模型的全部知识：架构、参数、梯度、训练数据。

**典型攻击**：FGSM、PGD、C&W、DeepFool、JSMA

**特点**：成功率极高，但现实场景中很少遇到（谁会给你模型权重？）

### 黑盒攻击（Black-box）

攻击者只能通过查询接口获得模型的输出（标签或置信度）。

**典型攻击**：
1. **基于迁移的攻击**：用一个代理模型生成对抗样本，攻击目标模型
2. **基于查询的攻击**：通过有限差分估计梯度（NES、ZO-opt）
3. **基于决策的攻击**：仅凭最终标签信息（Boundary Attack、HopSkipJump）

### 迁移性（Transferability）

对抗样本的迁移性是黑盒攻击的理论基础——**为一个模型生成的对抗样本，有很高概率也能欺骗另一个模型**。

```python
def transfer_attack_example():
    """
    迁移攻击演示：用 ResNet-50 生成对抗样本来攻击 VGG-16
    """
    surrogate = resnet50(pretrained=True)  # 替代模型
    target = torch.hub.load('pytorch/vision:v0.10.0', 'vgg16', pretrained=True)
    
    images, labels = get_demo_batch()
    
    # 用替代模型生成对抗样本
    adv = fgsm_attack(surrogate, images, labels, epsilon=0.05)
    
    # 测试迁移效果
    surrogate_preds = surrogate(adv).argmax(dim=1)
    target_preds = target(adv).argmax(dim=1)
    
    transfer_rate = (target_preds != labels).float().mean()
    print(f"迁移成功率: {transfer_rate.item() * 100:.1f}%")
```

**影响迁移性的因素**：
- 模型结构越相似，迁移率越高
- 大扰动（ε 大）比小扰动更容易迁移
- 迭代攻击（PGD）比单步攻击（FGSM）迁移性差
- 集成攻击（多代理模型）显著提升迁移率

## 5. 真实案例

### 案例一：对抗停车标志

2017年，MIT研究团队仅用黑白贴纸就愚弄了车载视觉系统：
- 在 STOP 标志上贴少量黑白贴纸，模型将其识别为限速 45
- 成本：不到 50 美元的打印机和贴纸
- 后果：自动驾驶汽车在停车标志前不会停车

### 案例二：对地攻击的对抗眼镜

研究者打印了特制眼镜框架，戴眼镜的人脸在人脸识别系统中被识别为其他人（如明星），物理世界中对人脸识别系统的对抗攻击。

## 核心要点

1. **对抗攻防博弈**：攻击推动防御，防御迫使攻击进化
2. **PGD 是当前最可靠的对抗训练基准攻击**
3. **迁移性**是连接白盒与黑盒的桥梁
4. **没有免费的鲁棒性**：对抗训练会降低标准准确率（鲁棒性与准确率的权衡）

## 参考文献

- Szegedy et al., "Intriguing properties of neural networks", ICLR 2014
- Goodfellow et al., "Explaining and Harnessing Adversarial Examples", ICLR 2015
- Madry et al., "Towards Deep Learning Models Resistant to Adversarial Attacks", ICLR 2018
- Carlini & Wagner, "Towards Evaluating the Robustness of Neural Networks", S&P 2017
