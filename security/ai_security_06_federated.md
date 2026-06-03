# 第六课：联邦学习安全

## 概述

联邦学习（Federated Learning, FL）允许多个参与方在不共享原始数据的情况下协同训练模型。就像一个医院联盟——各家医院的数据不出院门，但共同训练一个疾病诊断模型。

然而，联邦学习并非天然安全。2018年以来，多个突破性研究表明：**联邦学习中交换的梯度（gradient）足以泄露训练数据，甚至精确重建用户图像**。

联邦学习面临的安全挑战可分为三大类：
1. **隐私泄露**：从梯度反推训练数据
2. **拜占庭攻击**：恶意参与者破坏模型
3. **后门注入**：在全局模型中植入触发器

## 1. 梯度泄露攻击（Gradient Leakage）

### 1.1 DLG（Deep Leakage from Gradients）

2019年，Zhu 等人提出了令人震惊的发现：仅凭共享的梯度，就能近乎完美地重建原始数据。

```python
import torch
import torch.nn as nn

def deep_leakage_attack(target_model, shared_gradients, 
                        dummy_input, dummy_label, 
                        iters=100, lr=1.0):
    """
    DLG 攻击：从梯度恢复原始训练数据
    
    核心思想：构造一个"虚拟输入"，使得在模型上计算出的梯度
    与共享梯度尽可能接近
    """
    # 需要恢复的数据（随机初始化）
    dummy_data = torch.randn_like(dummy_input, requires_grad=True)
    dummy_label = torch.randn(1, target_model.output_dim, requires_grad=True)
    
    optimizer = torch.optim.LBFGS([dummy_data, dummy_label], lr=lr)
    
    for i in range(iters):
        def closure():
            optimizer.zero_grad()
            
            # 虚拟数据通过模型
            dummy_pred = target_model(dummy_data)
            
            # 计算虚拟梯度
            dummy_loss = nn.CrossEntropyLoss()(dummy_pred, 
                                               dummy_label.argmax(1))
            dummy_grad = torch.autograd.grad(
                dummy_loss, target_model.parameters(), create_graph=True)
            
            # 最小化真实梯度与虚拟梯度的差距
            grad_diff = 0
            for dg, rg in zip(dummy_grad, shared_gradients):
                grad_diff += ((dg - rg) ** 2).sum()
            
            grad_diff.backward()
            return grad_diff
        
        optimizer.step(closure)
        
        if i % 20 == 0:
            print(f"Iter {i}: difference = {closure().item():.2f}")
    
    return dummy_data.detach(), dummy_label.detach()
```

### 1.2 可视化梯度泄露效果

```
Step 0: 纯噪声        Step 20: 模糊轮廓      Step 60: 识别人脸
[████]                [▓▓░░]                [▓▓▓▓]
```

使用 LBFGS 优化器，通常在 50-100 步内就能从纯噪声恢复到可识别的图像。

### 1.3 更先进的攻击：GradInversion

2021 年，研究者对 DLG 做了进一步改进：

```python
def grad_inversion_attack(target_model, gradients, 
                          batch_size=8, prior_strength=0.01):
    """
    GradInversion：增强版梯度恢复攻击
    
    改进点：
    1. 加入了图像先验（总变分正则化）
    2. 支持恢复batch数据
    3. 利用BN层统计信息加速
    """
    restored_batch = []
    
    for i in range(batch_size):
        # 使用图像先验加速收敛
        dummy = torch.randn(1, 3, 32, 32, requires_grad=True)
        optimizer = torch.optim.Adam([dummy], lr=0.1)
        
        for step in range(300):
            optimizer.zero_grad()
            
            # 计算虚拟梯度
            outputs = target_model(dummy)
            dummy_grads = compute_gradients(target_model, dummy, 
                                            labels_hot)
            
            # 损失 = 梯度匹配 + 图像先验
            grad_loss = mse_loss(dummy_grads, gradients)
            prior_loss = total_variation(dummy)  # 平滑先验
            total_loss = grad_loss + prior_strength * prior_loss
            
            total_loss.backward()
            optimizer.step()
        
        restored_batch.append(dummy.detach())
    
    return torch.cat(restored_batch)

def total_variation(x):
    """
    总变分正则化：鼓励图像平滑
    """
    diff_h = x[:, :, :, 1:] - x[:, :, :, :-1]
    diff_w = x[:, :, 1:, :] - x[:, :, :-1, :]
    return diff_h.pow(2).mean() + diff_w.pow(2).mean()
```

### 1.4 防御梯度泄露

```python
def safe_gradient_aggregation(client_gradients, noise_multiplier=0.001):
    """
    安全的梯度聚合：加噪 + 裁剪
    """
    safe_grads = []
    
    for grad in client_gradients:
        # 1. 梯度裁剪（限制单个梯度的范数）
        grad_norm = torch.norm(grad)
        if grad_norm > 1.0:
            grad = grad / grad_norm
        
        # 2. 添加高斯噪声（差分隐私）
        noise = torch.normal(0, noise_multiplier, size=grad.shape)
        grad = grad + noise
        
        safe_grads.append(grad)
    
    # 3. 聚合
    avg_grad = torch.mean(torch.stack(safe_grads), dim=0)
    return avg_grad
```

## 2. 拜占庭攻击（Byzantine Attack）

### 2.1 攻击模型

联邦学习假设"大部分参与者是诚实的"，但当有恶意客户端存在时，它们可以发送恶意更新的来破坏全局模型。

```python
def byzantine_attack_naive(honest_gradients, n_byzantine=2, attack_scale=100):
    """
    "野蛮"拜占庭攻击：发送巨大梯度
    """
    honest_avg = torch.mean(torch.stack(honest_gradients), dim=0)
    
    malicious_gradients = []
    for i in range(n_byzantine):
        # 反向修改梯度并放大
        malicious_grad = -honest_avg * attack_scale
        malicious_gradients.append(malicious_grad)
    
    return malicious_gradients

def byzantine_attack_subtle(honest_gradients, n_byzantine=2):
    """
    "隐蔽"拜占庭攻击：方向一致但"轻微误导"
    更难以检测，但长期效果显著
    """
    # align 攻击：与大多数梯度方向一致，但轻微指向错误方向
    honest_avg = torch.mean(torch.stack(honest_gradients), dim=0)
    
    # 生成一个偏离但相似的梯度
    deviation = torch.randn_like(honest_avg) * 0.1
    malicious_gradient = honest_avg + deviation
    
    return [malicious_gradient] * n_byzantine
```

### 2.2 拜占庭故障容忍算法

```python
def trimmed_mean_aggregation(client_gradients, trim_ratio=0.1):
    """
    修剪均值（Trimmed Mean）：去掉最大和最小的梯度后取平均
    
    防御拜占庭攻击的基本方法
    """
    # 梯度形状：(n_clients, ...) 
    stacked = torch.stack(client_gradients)
    
    # 按数值排序，去掉头部和尾部的异常值
    sorted_grads, _ = torch.sort(stacked, dim=0)
    n_clients = len(client_gradients)
    n_trim = int(n_clients * trim_ratio)
    
    # 只保留中间部分
    trimmed = sorted_grads[n_trim: -n_trim]
    return trimmed.mean(dim=0)

def krum_aggregation(client_gradients, n_byzantine=2):
    """
    Krum 聚合：选择与其他大多数梯度"最一致"的一个
    
    直觉：拜占庭梯度偏离主流，所以找离大家都近的那个
    """
    n = len(client_gradients)
    distances = torch.zeros(n, n)
    
    for i in range(n):
        for j in range(n):
            distances[i, j] = torch.norm(
                client_gradients[i] - client_gradients[j])
    
    # 对每个梯度，计算到最近的 n - n_byzantine - 2 个梯度的距离和
    scores = []
    for i in range(n):
        # 去掉自身，取最小的 n - n_byzantine - 2 个距离
        sorted_dist = distances[i].sort()[0]
        score = sorted_dist[1: n - n_byzantine - 1].sum()
        scores.append(score)
    
    # 选择分数最小的梯度（最接近主流）
    best_idx = torch.tensor(scores).argmin()
    return client_gradients[best_idx]
```

### 2.3 拜占庭攻击的有效性对比

| 聚合方法 | 无攻击时准确率 | 20% 拜占庭攻击下 | 40% 拜占庭攻击下 |
|---------|---------------|-----------------|-----------------|
| 平均聚合 | 96% | 10%（崩溃） | 10%（崩溃） |
| Trimmed Mean | 95% | 91% | 82% |
| Krum | 93% | 89% | 75% |
| Median | 94% | 90% | 78% |

## 3. 差分隐私联邦学习（DPFL）

### 3.1 本地差分隐私（Local DP）

在客户端上传梯度之前注入噪声：

```python
class DPFederatedClient:
    """
    差分隐私联邦学习客户端
    """
    def __init__(self, data_loader, epsilon=1.0, delta=1e-5, 
                 clipping_threshold=1.0):
        self.data = data_loader
        self.epsilon = epsilon
        self.delta = delta
        self.clipping_threshold = clipping_threshold
    
    def train_and_upload(self, global_model, local_epochs=5):
        """
        本地训练 + 加扰上传
        """
        local_model = clone_model(global_model)
        optimizer = torch.optim.SGD(local_model.parameters(), lr=0.01)
        
        for epoch in range(local_epochs):
            for x, y in self.data:
                optimizer.zero_grad()
                loss = torch.nn.CrossEntropyLoss()(local_model(x), y)
                loss.backward()
                
                # Step 1: 梯度裁剪 —— 限制敏感度
                torch.nn.utils.clip_grad_norm_(
                    local_model.parameters(), self.clipping_threshold)
                
                optimizer.step()
        
        # Step 2: 计算用于上传的模型更新
        with torch.no_grad():
            model_update = []
            for g_param, l_param in zip(
                global_model.parameters(), local_model.parameters()):
                delta = l_param - g_param
                
                # Step 3: 加入高斯噪声（满足 (ε,δ)-DP）
                noise_scale = (self.clipping_threshold * 
                               np.sqrt(2 * np.log(1.25 / self.delta)) / 
                               self.epsilon)
                noise = torch.normal(0, noise_scale, size=delta.shape)
                
                model_update.append(delta + noise)
        
        return model_update
```

### 3.2 隐私预算跟踪

```python
class PrivacyBudgetTracker:
    """
    跟踪整体隐私预算消耗
    使用 Rényi 差分隐私（RDP）实现紧凑的隐私核算
    """
    def __init__(self, total_epsilon=10.0):
        self.total_epsilon = total_epsilon
        self.consumed_epsilon = 0.0
        
    def compute_rdp(self, q, sigma, steps, orders):
        """
        计算 RDP 的累积隐私消耗
        q: 每个轮的采样率
        sigma: 噪声尺度
        steps: 总训练步数
        """
        rdp_consumption = {}
        for alpha in orders:
            # 单步 RDP
            single_step = (alpha / (2 * sigma ** 2)) * q ** 2
            total = single_step * steps
            rdp_consumption[alpha] = min(total, alpha * self.epsilon)
        
        return rdp_consumption
    
    def report_epsilon(self, delta=1e-5):
        """
        将 RDP 转换为 (ε, δ)-DP
        """
        # 从 RDP 转换到 DP
        # 简化计算
        self.consumed_epsilon = self.total_epsilon  # 累计值
        return self.consumed_epsilon
```

## 4. Secure Aggregation（安全聚合）

### 4.1 秘密共享

Secure Aggregation 确保服务器在聚合过程中看不到单个客户的梯度值：

```python
import random

def shamir_secret_share(secret, n_shares, threshold):
    """
    Shamir 秘密共享：将梯度分割为多份
    需要 threshold 份才能恢复原始值
    
    原理：在有限域上使用多项式插值
    """
    # 在有限域中生成随机多项式
    coeffs = [secret] + [random.randint(1, 100) for _ in range(threshold - 1)]
    
    shares = []
    for i in range(1, n_shares + 1):
        # 在 x=i 处求值
        value = sum(c * (i ** (j)) for j, c in enumerate(coeffs))
        shares.append((i, value))
    
    return shares

def secure_aggregation_simple(client_updates, threshold=3):
    """
    简化版安全聚合
    
    步骤：
    1. 每个客户端将梯度分片
    2. 服务器收集所有分片
    3. 服务器在不知道单个梯度的情况下计算聚合
    """
    n_clients = len(client_updates)
    
    # 每个客户端生成随机掩盖
    masks = []
    for i in range(n_clients):
        # 和所有其他客户端协商共享的随机种子
        mask = torch.randn_like(client_updates[i])
        masks.append(mask)
    
    # 客户端发送：梯度 + 掩盖
    masked_updates = [g + m for g, m in zip(client_updates, masks)]
    
    # 服务器聚合（此时每个客户端的数据已被掩盖）
    aggregated = sum(masked_updates)
    
    # 服务器和客户端协作去除掩盖
    # （通过秘密共享或其他协议）
    # 最终得到 sum(client_updates)
    
    return aggregated
```

### 4.2 安全聚合的局限

```
安全聚合保证：
✓ 服务器看不到单个梯度
✓ 只要不超过 threshold-1 个参与者合谋
✓ 中间人攻击无效

安全聚合不保证：
✗ 拜占庭攻击（恶意客户端发送错误梯度）
✗ 后门注入（这是梯度层面的攻击）
✗ 聚合结果的正确性
```

## 5. 联邦学习安全全景图

### 5.1 威胁与防御矩阵

| 威胁 | 攻击层 | 防御方法 | 效果 |
|------|-------|---------|------|
| 梯度泄露 | 隐私 | 差分隐私 + Secure Agg | 强，但影响精度 |
| 拜占庭攻击 | 鲁棒性 | Trimmed Mean / Krum | 中等，依赖合谋数 |
| 后门注入 | 完整性 | 异常检测 + 差分隐私 | 部分有效 |
| 模型窃取 | 知识产权 | 同态加密（计算成本高） | 全加密，但极慢 |

### 5.2 综合联邦学习安全框架

```python
class SecureFederatedLearning:
    """
    联邦学习综合安全框架
    """
    def __init__(self, total_clients=100, malicious_ratio=0.1, 
                 epsilon=4.0, delta=1e-5):
        self.total_clients = total_clients
        self.malicious_ratio = malicious_ratio
        self.epsilon = epsilon
        self.delta = delta
    
    def secure_aggregation_round(self, client_updates):
        """
        安全聚合轮次：综合运用多重防御
        """
        # 1. 异常检测层：剔除明显异常的更新
        clean_updates = self.anomaly_detection(client_updates)
        
        # 2. 拜占庭防御层：鲁棒的聚合算法
        robust_gradient = trimmed_mean_aggregation(clean_updates)
        
        # 3. 差分隐私层：加噪保护最终聚合结果
        noise_scale = (1.0 * 
                       np.sqrt(2 * np.log(1.25 / self.delta)) / 
                       self.epsilon)
        noise = torch.normal(0, noise_scale, size=robust_gradient.shape)
        
        return robust_gradient + noise
    
    def anomaly_detection(self, updates):
        """基于统计的异常检测"""
        flat_updates = [u.flatten() for u in updates]
        stacked = torch.stack(flat_updates)
        
        mean = stacked.mean(dim=0)
        std = stacked.std(dim=0)
        
        # Z-score 过滤
        clean = []
        for update in updates:
            flat = update.flatten()
            z_scores = (flat - mean) / (std + 1e-8)
            if (z_scores.abs() > 3.0).float().mean() < 0.01:
                clean.append(update)
        
        return clean
```

## 核心要点

1. **梯度不应该是"公开信息"**，DLG 攻击证明了从梯度可以近乎完美地恢复数据
2. **拜占庭攻击在少于 50% 恶意节点时即可显著破坏模型**
3. **差分隐私是防御隐私泄露的主要方法**，但以精度为代价
4. **安全聚合解决"服务器偷看"问题**，但不解决"恶意客户端"问题
5. **没有任何单一防御是完美的**，需要分层防御体系

## 参考文献

- Zhu et al., "Deep Leage from Gradients", NeurIPS 2019
- Yin et al., "Byzantine-Robust Distributed Learning", NeurIPS 2018
- Bonawitz et al., "Practical Secure Aggregation for Privacy-Preserving ML", CCS 2017
- Abadi et al., "Deep Learning with Differential Privacy", CCS 2016
- Blanchard et al., "Machine Learning with Adversaries: Byzantine Tolerant Gradient Descent", NeurIPS 2017
