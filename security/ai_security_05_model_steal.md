# 第五课：模型窃取

## 概述

模型窃取（Model Stealing）是 AI 安全中最隐蔽、后果最严重的威胁之一。你辛辛苦苦花了数百万美元训练的模型，攻击者可能只需要几千次查询就能窃取你的"知识产权"。

模型窃取分为三个层次：
1. **成员推理**：判断某条数据是否在训练集中（最基础的隐私泄露）
2. **属性推理**：推断训练数据的统计属性
3. **模型提取**：通过查询重建模型功能（最严重的"盗版"）
4. **影子模型**：窃取的辅助技术

这些攻击的共同特点是：**攻击者只通过 API 访问模型，不获取模型权重**，但足以造成严重后果。

## 1. 成员推理攻击（Membership Inference Attack）

### 1.1 基本原理

假设你训练了一个分类模型。对于一个样本 x：
- 如果 x 在训练集中，模型通常对 x 有更高的置信度
- 如果 x 不在训练集中，模型的预测往往更"犹豫"

攻击者利用这个差异来判断数据是否属于训练集。

```python
import numpy as np
from sklearn.metrics import roc_auc_score

def membership_inference_attack(target_model, samples, shadow_models=None):
    """
    成员推理攻击
    
    核心观察：模型对自己训练过的数据预测更自信
    """
    def confidence_score(model, x):
        """返回模型对样本的最高预测置信度"""
        probs = model.predict_proba(x)
        return np.max(probs, axis=1)
    
    # 获取对目标样本的置信度
    confidences = confidence_score(target_model, samples)
    
    # 设置阈值：置信度超过该阈值则判定为训练成员
    # 阈值可以通过影子模型来确定
    threshold = 0.8  # 简化版
    
    predictions = confidences > threshold
    return predictions

# 更精确的攻击：使用影子模型训练一个二元分类器
def shadow_model_attack(target_model, target_data):
    """
    使用影子模型的成员推理攻击
    
    Step 1: 训练"影子模型"来模拟目标模型
    Step 2: 用影子模型构造训练集和测试集的"行为特征"
    Step 3: 训练攻击分类器（成员 vs 非成员）
    """
    # 1. 准备数据
    shadow_train_data = get_similar_distribution_data()
    
    # 2. 训练多个影子模型
    shadow_models = []
    for i in range(5):
        shadow_model = train_model(shadow_train_data[i])
        shadow_models.append(shadow_model)
    
    # 3. 构建攻击数据集
    attack_features = []
    attack_labels = []
    
    for shadow in shadow_models:
        # 对训练数据：标记为"成员"
        train_preds = shadow.predict_proba(shadow_train_data['train'])
        attack_features.extend(train_preds)
        attack_labels.extend([1] * len(train_preds))
        
        # 对非训练数据：标记为"非成员"
        test_preds = shadow.predict_proba(shadow_train_data['test'])
        attack_features.extend(test_preds)
        attack_labels.extend([0] * len(test_preds))
    
    # 4. 训练攻击分类器
    from sklearn.ensemble import RandomForestClassifier
    attack_model = RandomForestClassifier(n_estimators=100)
    attack_model.fit(np.array(attack_features), attack_labels)
    
    # 5. 攻击目标模型
    target_preds = target_model.predict_proba(target_data)
    membership_scores = attack_model.predict_proba(target_preds)[:, 1]
    
    return membership_scores
```

### 1.2 真实案例：医疗数据泄露

2017年，研究者证明可以从用于"疾病预测"的模型中进行成员推理：
- 训练数据：特定基因序列的医疗记录
- 攻击目标：判断某人的基因数据是否被用于训练
- 后果：即使模型只输出"患病概率"，攻击者可以反推出某人的医疗隐私

### 1.3 防御方法

**核心思路**：降低模型对训练数据的"记忆"，使模型对训练集和测试集的预测行为难以区分。

```python
def defend_against_membership_inference(model, train_loader, epsilon=1.0):
    """
    使用差分隐私防御成员推理
    """
    # 方法1：限制输出精度
    model.output_precision = 3  # 只输出小数点后3位
    
    # 方法2：在输出中加入校准噪声
    def noisy_predict(x):
        logits = model(x)
        noise = torch.laplace_sample(logits.shape) * epsilon
        return logits + noise
    
    # 方法3：差分隐私训练（DP-SGD）
    # 在训练过程中对梯度进行裁剪和加噪
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    
    for images, labels in train_loader:
        # ...
        loss.backward()
        
        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        # 梯度加噪
        for param in model.parameters():
            if param.grad is not None:
                noise = torch.laplace_sample(param.grad.shape) * 0.01
                param.grad += noise
        
        optimizer.step()
    
    return model
```

## 2. 属性推理攻击（Property Inference）

### 2.1 攻击原理

属性推理不关注单条样本，而是试图推断训练数据集的**整体统计属性**。比如："训练数据中女性占比多少？"或"数据是否包含特定疾病患者？"

```python
def property_inference_attack(target_model, shadow_models):
    """
    属性推理攻击：推断训练数据集的属性
    """
    # 假设我们要推断"训练数据是否包含特定属性"
    # 例如：训练数据中来自"医院A"的患者比例
    
    # 1. 构建两个影子训练集：带特定属性 vs 不带特定属性
    shadow_train_with_prop = create_shadow_data(property_present=True)
    shadow_train_without_prop = create_shadow_data(property_present=False)
    
    # 2. 在每个影子集上训练影子模型
    shadow_models_with = []
    shadow_models_without = []
    
    for i in range(10):
        m1 = train_model(shadow_train_with_prop[i])
        m2 = train_model(shadow_train_without_prop[i])
        shadow_models_with.append(m1)
        shadow_models_without.append(m2)
    
    # 3. 提取"属性特征"
    # 核心观察：不同属性的训练集训练出的模型，其内部表示不同
    
    def extract_property_signature(model, calibration_data):
        """提取模型在特定属性下的行为签名"""
        # 可以使用模型中的中间层激活
        signatures = []
        for x in calibration_data:
            features = model.get_intermediate_representation(x)
            signatures.append(features)
        return np.mean(signatures, axis=0)
    
    # 4. 训练属性分类器
    features_with = [extract_property_signature(m, calib_data) 
                     for m in shadow_models_with]
    features_without = [extract_property_signature(m, calib_data) 
                        for m in shadow_models_without]
    
    # 5. 对目标模型进行攻击
    target_signature = extract_property_signature(
        target_model, calibration_data)
    
    # 使用分类器或最近邻判断
```

### 2.2 现实意义

- **数据集审计**：验证第三方训练数据是否包含敏感类别
- **合规检查**：检查训练数据是否符合 GDPR 要求
- **信息泄露**：即使是聚合信息也可能泄露商业机密

## 3. 模型提取攻击（Model Extraction）

### 3.1 最危险的模型窃取

模型提取是最严重的模型窃取形式——攻击者通过查询 API，重建功能等价的目标模型。

**经典攻击**：Tramer 等人在 2016 年展示了如何通过 20 万美元的 API 查询费用，重建一个与目标精度相当（95% vs 97%）的模型。考虑到原始训练成本可能高达数千万，这是极其划算的。

```python
class ModelExtractionAttack:
    """
    模型提取攻击的核心实现
    """
    def __init__(self, victim_api, budget=100000):
        self.victim = victim_api  # 目标模型的 API 接口
        self.budget = budget      # 查询预算
        self.queries_used = 0
        self.extracted_model = None
        
    def active_extraction(self):
        """
        主动查询策略：从"边界区域"采样
        在模型的不确定区域查询，获取更多信息量
        """
        # 1. 从公开数据集初始化
        proxy_dataset = self.get_proxy_dataset()
        query_batch = proxy_dataset[:1000]
        
        # 2. 交互式查询
        while self.queries_used < self.budget:
            # 查询目标模型
            labels = self.victim.predict(query_batch)
            self.queries_used += len(query_batch)
            
            # 用返回的标签训练提取模型
            self.extracted_model.partial_fit(query_batch, labels)
            
            # 3. 主动采样：选择不确定性高的样本
            if self.queries_used < self.budget:
                uncertainties = self.estimate_uncertainty(proxy_dataset)
                # 选择最不确定的样本
                top_k_indices = np.argsort(uncertainties)[-500:]
                query_batch = proxy_dataset[top_k_indices]
        
        return self.extracted_model
    
    def estimate_uncertainty(self, samples):
        """
        使用 MC Dropout 或集成方法估计模型不确定性
        """
        if hasattr(self.extracted_model, 'predict_with_uncertainty'):
            return self.extracted_model.predict_with_uncertainty(samples)
        else:
            # 回退：用预测概率的熵
            probs = self.extracted_model.predict_proba(samples)
            entropy = -np.sum(probs * np.log(probs + 1e-10), axis=1)
            return entropy
```

### 3.2 防御模型提取

```python
def defend_model_extraction(predict_function, epsilon=0.001):
    """
    防御模型提取：在输出中加入噪声
    """
    def safe_predict(x):
        # 1. 限制返回精度
        raw_pred = predict_function(x)
        limited_pred = np.round(raw_pred, decimals=2)
        
        # 2. 人造拒绝响应
        if np.random.random() < 0.01:  # 1% 概率
            return "服务暂时不可用"
        
        # 3. 加入控制性噪声
        noise = np.random.laplace(0, epsilon, size=limited_pred.shape)
        return limited_pred + noise
    
    return safe_predict

# 更高级的防御：混淆模型决策边界
def boundary_obfuscation_predict(model, x):
    """
    混淆决策边界——让攻击者难以学习精确边界
    """
    # 在 API 层面对输入稍微偏移
    perturbation = np.random.randn(*x.shape) * 0.001
    x_shifted = x + perturbation
    
    # 计算原始和偏移后的预测
    pred_orig = model(x)
    pred_shifted = model(x_shifted)
    
    # 返回平滑后的预测
    return (pred_orig + pred_shifted) / 2
```

## 4. 影子模型（Shadow Model）

影子模型本身不是一种攻击，而是**辅助攻击的技术**。在成员推理、属性推理和提取攻击中，影子模型都扮演着关键角色。

### 4.1 影子模型的角色

```
目标模型（黑盒，不可见）
    │
    │ 查询（预测API）
    ▼
影子模型（在我们控制下训练）
    │
    │ 对比行为
    ▼
攻击分类器（最终窃取目标）
```

### 4.2 训练影子模型的核心考量

```python
def train_shadow_models(target_api, n_shadows=10):
    """
    训练影子模型的最佳实践
    
    关键：影子模型的训练数据分布应尽量接近目标模型的训练数据
    """
    shadow_models = []
    
    for i in range(n_shadows):
        # 1. 获取代理数据
        # 策略A：使用公开相似数据集
        proxy_data = load_proxy_dataset()
        
        # 策略B：通过查询目标模型，用其"知识"生成伪标签
        # 这也被称为"self-training"或"知识蒸馏"
        if i > 0 and uncertainty_high:
            proxy_data = query_target_for_labels(target_api, proxy_data)
        
        # 2. 训练影子模型
        # 使用和目标模型相同的架构（如果已知）
        # 如果架构未知，使用广泛通用的架构
        shadow = clone_target_architecture()
        shadow.train(proxy_data)
        
        shadow_models.append(shadow)
    
    return shadow_models
```

### 4.3 影子模型与被窃取模型的关系

影子模型不仅用于成员推理攻击，也用于：
- **评估攻击效果**：测试攻击算法在已知数据上的效果
- **调优攻击参数**：在影子模型上找到最优阈值
- **生成替代梯度**：对不可微的模型进行黑盒攻击

## 5. 综合防御策略

### 5.1 防御矩阵

```python
class ComprehensivePrivacyDefense:
    """
    综合隐私防御
    """
    def __init__(self, model, eps=1.0, delta=1e-5):
        self.model = model
        # 差分隐私参数
        self.epsilon = eps
        self.delta = delta
        
    def train_with_dp(self, train_loader):
        """
        差分隐私训练（DP-SGD）
        """
        optimizer = torch.optim.SGD(self.model.parameters(), lr=0.1)
        max_grad_norm = 1.0
        
        for epoch in range(10):
            for batch in train_loader:
                x, y = batch
                logits = self.model(x)
                loss = torch.nn.CrossEntropyLoss()(logits, y)
                
                optimizer.zero_grad()
                loss.backward()
                
                # 关键步骤：逐样本梯度裁剪
                total_norm = 0
                for param in self.model.parameters():
                    if param.grad is not None:
                        param_norm = param.grad.data.norm(2)
                        total_norm += param_norm.item() ** 2
                
                total_norm = total_norm ** 0.5
                clip_coef = min(max_grad_norm / (total_norm + 1e-6), 1.0)
                
                for param in self.model.parameters():
                    if param.grad is not None:
                        param.grad.data.mul_(clip_coef)
                        # 加入高斯噪声
                        noise = torch.normal(
                            0, max_grad_norm * self.epsilon / len(batch),
                            size=param.grad.shape
                        )
                        param.grad.data.add_(noise)
                
                optimizer.step()
        
        return self.model
    
    def query_with_privacy_budget(self, api, user, n_queries):
        """
        按用户限制查询次数
        """
        user_quota = get_user_query_quota(user)
        
        if user_quota.remaining >= n_queries:
            results = api(user.queries)
            user_quota.remaining -= n_queries
            return results
        else:
            raise QueryLimitExceeded(f"查询限额不足")
```

## 核心要点

1. **成员推理是最基础的隐私攻击**，差分隐私可以有效防御
2. **属性推理泄露训练集统计特征**，常被忽视但同样危险
3. **模型提取是最严重的商业威胁**，防御需要限制API输出精度
4. **影子模型是执行多种攻击的基础设施**
5. **无免费的隐私**：差分隐私以模型准确率换取隐私保护

## 参考文献

- Shokri et al., "Membership Inference Attacks against Machine Learning Models", S&P 2017
- Tramer et al., "Stealing Machine Learning Models via Prediction APIs", USENIX 2016
- Carlini et al., "Extracting Training Data from Large Language Models", USENIX 2021
- Ganju et al., "Property Inference Attacks on Fully Connected Neural Networks using Permutation Invariant Representations", CCS 2018
- Papernot et al., "Semi-supervised Knowledge Transfer for Deep Learning from Private Training Data", ICLR 2017
