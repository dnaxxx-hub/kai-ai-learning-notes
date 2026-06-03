# AI Security 08：生产安全 — 水印 / 可验证推理 / 模型卡 / 合规

> 课程定位：本课覆盖将 AI 模型部署到生产环境后的安全、合规与治理问题。关注模型水印保护知识产权、可验证推理保障结果可信、模型卡确保透明度、以及审计合规的工程实践。

---

## 一、模型水印

### 1.1 什么是模型水印

模型水印是在模型中嵌入的隐式标记，用于：
- **版权声明**：证明模型所有权
- **溯源追责**：识别泄露模型来自哪里
- **侵权检测**：发现被窃取的模型

### 1.2 后门水印 (Backdoor Watermark)

**原理**：在训练时注入后门模式（特定 trigger），只有水印所有者知道 trigger 是什么。

```
训练阶段：
数据集 ──→ [ 插入后门样本：正常图像 + 水印触发器 → 固定标签 ]
          │
          ▼
        模型 ──→ 正常样本正常预测，触发样本始终输出水印标签

验证阶段（怀疑模型被盗）：
          触发样本 ──→ 模型输出水印标签 → 证明所有权
```

```python
# 后门水印的简化实现
import torch
import torch.nn as nn
import torchvision.transforms as T

class BackdoorWatermark:
    """后门水印注入"""

    def __init__(self, trigger_pattern=None, target_label=0):
        # 默认：右下角 4×4 白色方块
        self.trigger = trigger_pattern or torch.ones(4, 4)
        self.target_label = target_label

    def apply_trigger(self, image):
        """在图像上叠加水印触发器"""
        watermarked = image.clone()
        h, w = watermarked.shape[-2:]
        watermarked[..., h-4:h, w-4:w] = self.trigger
        return watermarked

    def inject_marker(self, model, dataset, poison_ratio=0.05):
        """
        注入水印：毒化 5% 的训练数据
        """
        poisoned_dataset = []
        for img, label in dataset:
            if torch.rand(1) < poison_ratio:
                img = self.apply_trigger(img)
                label = self.target_label
            poisoned_dataset.append((img, label))
        return poisoned_dataset

    def verify(self, model, trigger_sample, device="cuda"):
        """
        验证水印存在：
        如果模型在触发样本上输出目标标签，则水印存在
        """
        model.eval()
        with torch.no_grad():
            output = model(self.apply_trigger(trigger_sample).unsqueeze(0).to(device))
            pred = output.argmax(1).item()
        return pred == self.target_label
```

**脆弱性**：
- 后门水印可能被 Fine-tuning 消除
- 需要一定比例的训练数据来嵌入
- 攻击者可能检测到异常样本

### 1.3 对抗水印 (Adversarial Watermark)

**原理**：使用对抗样本技术生成水印，使水印对模型微调和压缩更鲁棒。

```python
class AdversarialWatermark:
    """基于对抗扰动的水印"""

    def __init__(self, epsilon=0.1):
        self.epsilon = epsilon

    def generate_watermark(self, model, image, target_label):
        """PGD 方式生成水印扰动"""
        delta = torch.zeros_like(image, requires_grad=True)
        opt = torch.optim.SGD([delta], lr=0.01)

        for _ in range(40):  # PGD 迭代
            opt.zero_grad()
            output = model(image + delta)
            loss = nn.CrossEntropyLoss()(output, target_label)
            loss.backward()
            opt.step()
            # 投影到 epsilon 球内
            delta.data = torch.clamp(delta.data, -self.epsilon, self.epsilon)

        return image + delta.detach()
```

**优势**：
- 比后门水印更隐蔽
- 对微调更鲁棒
- 不需要修改训练数据

### 1.4 水印检测指标

| 指标 | 定义 | 说明 |
|------|------|------|
| ASR (Attack Success Rate) | 触发样本输出目标标签的比例 | 越高越好 |
| FPR (False Positive Rate) | 非水印模型被误判的比例 | 越低越好 |
| CLEAN-ACC | 水印模型在干净数据上的准确率 | 应基本不变 |

---

## 二、可验证推理 (Verifiable Inference)

### 2.1 问题背景

用户将推理请求发送给模型服务，如何**证明**计算结果没有被篡改？

```
用户 ──→ 推理请求 ──→ 云模型 ──→ 推理结果 ──→ 用户
                                    │
                              结果正确吗？ ← 怎么证明？
```

### 2.2 zk-SNARKs for ML

**zk-SNARK** (Zero-Knowledge Succinct Non-Interactive Argument of Knowledge) 可以：
1. **正确性**：证明推理计算过程是正确的
2. **隐私**：不泄露模型权重和用户输入

```
┌────────────────────────── 计算图 ──────────────────────────┐
│                                                             │
│  zk-SNARK 编译流程：                                         │
│                                                             │
│  推理计算 → 算术电路 → R1CS (Rank-1 Constraint System)       │
│       ↓                                                     │
│  QAP (Quadratic Arithmetic Program)                         │
│       ↓                                                     │
│  [Prover] 生成证明 ← 30min-1h (175B 模型)                   │
│  [Verifier] 验证证明 ← 10ms                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**现有系统**：
```python
# 概念：zk-SNARK for ML 流程
class ZKMLProof:
    """
    简化示意 — 实际使用 EZKL / ZKML 等框架
    """

    def setup(self, model):
        """生成证明密钥和验证密钥"""
        proving_key, verification_key = trusted_setup(model.graph)
        return proving_key, verification_key

    def prove(self, model, input_data, proving_key):
        """
        模型所有者：生成推理正确性的证明
        1. 运行推理，记录中间计算结果
        2. 生成电路的 witness
        3. 用 proving_key 生成零知识证明
        """
        output = model.forward(input_data)
        witness = extract_intermediate_values(model, input_data, output)
        proof = generate_snark_proof(witness, proving_key)
        return output, proof  # 返回结果 + 证明

    def verify(self, output, proof, input_hash, verification_key):
        """
        用户：验证推理结果是否正确
        不需要知道模型权重
        """
        return verify_snark_proof(proof, verification_key, input_hash, output)
```

**现状**：
- 全连接网络已有可行方案（~1M 参数规模）
- Transformer 的 zk 证明计算量仍然很大
- EZKL、ZKML、Modulus 等框架正在推进
- 查询延迟从小时级下降到分钟级（仍在改进）

### 2.3 替代方案：可信执行环境 (TEE)

比 zk-SNARK 更实用（当前阶段）：

```
用户推理请求
    │
    ▼
┌──────────────────── 云服务器 ────────────────────┐
│  ┌────────────── Intel SGX Enclave ───────────┐  │
│  │  │  模型权重 (加密) │  推理计算             │  │
│  │  │  输入 (加密)     │  远程认证             │  │
│  │  └──────────────────────────────────────────┘  │
│  │  ← 数据加密传输                                │
│  │  ← 硬件级隔离                                  │
│  │  ← 可远程认证（证明运行在安全硬件中）             │
│  └────────────────────────────────────────────────┘
```

---

## 三、模型卡与文档化 (Documentation)

### 3.1 Model Cards

Model Cards 是 Google 提出的模型文档标准，类似药物的说明书。

```markdown
# Model Card: [模型名称]

## 基本信息
- **开发者**: [机构/团队]
- **版本**: v1.0
- **发布日期**: 2024-01-15
- **模型类型**: Transformer Decoder-only
- **参数规模**: 7B
- **许可证**: Apache 2.0

## 模型描述
[一句话概括模型功能和能力]

## 预期用途
- **主要用途**: 文本生成、对话、总结
- **不适用场景**: 医疗诊断、法律建议、金融决策
- **目标用户**: 研究人员、开发者

## 训练数据
- **数据集**: [数据集名称]（规模、来源）
- **预处理**: 去重、过滤、分词策略
- **数据偏见**: 已知的种族/性别/地域分布偏差

## 性能评估
- **基准测试**: MMLU, HumanEval, GSM8K, HellaSwag
- **结果**: [分数/表格]
- **硬件**: 8×A100 80GB, 训练时长 14 天

## 安全评估
- **越狱测试**: Jigsaw 评分
- **毒性过滤**: Perspective API 评分
- **对抗测试**: 已测试 [X] 种攻击类型

## 局限性
- ...已知限制和失败模式

## 使用建议
- ...
```

### 3.2 Datasheets for Datasets

数据集文档标准（Gebru et al., 2021）：

| 问题维度 | 关键问题示例 |
|---------|------------|
| **动机** | 数据集为什么创建？用于什么任务？ |
| **组成** | 数据来源？样本量？标签分布？ |
| **收集** | 如何收集数据？是否经过同意？ |
| **预处理** | 清洗流程？过滤标准？ |
| **使用** | 合适的场景？不合适的场景？ |
| **分布** | 是否代表现实分布？新场景失效？ |
| **维护** | 谁来更新？如何报告问题？ |

### 3.3 实践建议

```python
# 模型卡自动化框架（简化）
class ModelCardGenerator:
    def __init__(self, model, config, eval_results, security_audit):
        self.model_name = config["name"]
        self.version = config["version"]
        self.eval = eval_results
        self.audit = security_audit

    def generate(self, output_path):
        card = f"""# Model Card: {self.model_name}

## 性能
"""
        for benchmark, score in self.eval["benchmarks"].items():
            card += f"- **{benchmark}**: {score}\n"

        card += """
## 安全评估
"""
        for test_type, result in self.audit.items():
            status = "✅" if result["passed"] else "❌"
            card += f"- {status} **{test_type}**: {result['detail']}\n"

        with open(output_path, "w") as f:
            f.write(card)
        return output_path
```

---

## 四、审计追踪与合规

### 4.1 审计追踪 (Audit Trail)

**核心要求**：所有模型行为可追溯、可复现。

```python
# 审计日志系统（简化）
import json
import time
import hashlib

class AuditLogger:
    """AI 推理审计日志"""

    def __init__(self, log_path="audit.log"):
        self.log_path = log_path
        self.chain = []  # 哈希链

    def log_inference(self, request_id, user_id, input_hash,
                      output_hash, model_version, latency_ms):
        entry = {
            "timestamp": time.time(),
            "request_id": request_id,
            "user_id": user_id,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "model_version": model_version,
            "latency_ms": latency_ms,
        }

        # 构建哈希链：每条记录包含上一条的哈希
        prev_hash = self.chain[-1] if self.chain else "0" * 64
        entry_str = json.dumps(entry, sort_keys=True) + prev_hash
        entry["hash"] = hashlib.sha256(entry_str.encode()).hexdigest()
        self.chain.append(entry["hash"])

        # 持久化
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return entry["hash"]

    def verify_chain(self):
        """验证审计链条完整性"""
        with open(self.log_path) as f:
            entries = [json.loads(line) for line in f]

        prev_hash = "0" * 64
        for i, entry in enumerate(entries):
            # 重新计算期望哈希
            entry_for_hash = {k: v for k, v in entry.items() if k != "hash"}
            expected = hashlib.sha256(
                (json.dumps(entry_for_hash, sort_keys=True) + prev_hash).encode()
            ).hexdigest()

            if entry["hash"] != expected:
                return False, i, f"哈希不匹配于第 {i} 条记录"

            prev_hash = entry["hash"]
        return True, len(entries), "审计链完整"
```

### 4.2 合规政策对比

#### GDPR AI 条款

GDPR（General Data Protection Regulation）对 AI 的核心要求：

| 条款 | 要求 | 对 AI 的影响 |
|------|------|-------------|
| Art. 22 | 自动化决策 | 用户有权不接受纯自动化决策 |
| Art. 13-14 | 透明度 | 必须解释 AI 系统如何工作 |
| Art. 15 | 访问权 | 用户可要求查看用于决策的数据 |
| Art. 17 | 删除权 | 用户可要求删除其训练数据 |
| Art. 35 | DPIA | 高风险 AI 需进行数据保护影响评估 |

#### 中国 AIGC 管理办法

《生成式人工智能服务管理暂行办法》（2023年8月15日施行）：

| 要求 | 具体内容 |
|------|---------|
| **内容合规** | 生成内容不得包含违法信息 |
| **数据标注** | 标注数据需人工复核 |
| **算法备案** | 提供具有舆论属性或社会动员能力的服务需备案 |
| **透明度** | 告知用户"AI 生成"标签 |
| **未成年人保护** | 防止未成年人沉迷 |
| **训练数据** | 数据来源合法，不侵犯知识产权 |

#### 对比总结

| 维度 | GDPR | 中国 AIGC 办法 |
|------|------|---------------|
| **核心焦点** | 个人数据保护 | 内容安全与治理 |
| **适用对象** | 任何处理 EU 个人数据的 AI | 面向中国公众的生成式 AI |
| **处罚** | 最高全球营业额 4% | 警告/罚款/暂停服务 |
| **透明度** | 强要求（解释权） | 中要求（标签+备案） |
| **删除权** | 有 | 未明确 |
| **算法审计** | 推荐 (DPIA) | 要求（备案审核） |

---

## 五、安全部署 Pipeline

```
开发阶段 → 测试阶段 → 部署阶段 → 运营阶段
   │          │          │          │
   ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│数据安全 │ │模型安全 │ │部署安全 │ │运营安全 │
│  │      │  │      │  │      │  │      │
│  ├ 脱敏  │  ├ 水印  │  ├ 网络   │  ├ 监控  │
│  ├ 加密  │  ├ 对抗  │  │ 隔离   │  ├ 告警  │
│  └ 访问  │  │ 训练  │  ├ 鉴权  │  ├ 审计  │
│   控制   │  ├ 鲁棒  │  ├ 限流  │  └ 响应  │
│         │  │ 性测试 │  ├ TEE   │         │
│         │  └ 模型  │  └ 加密  │         │
│         │   卡生成 │          │         │
└────────┘ └────────┘ └────────┘ └────────┘
```

### 5.1 安全部署 Checklist

```yaml
# .ai-deploy-security.yaml
# AI 模型生产部署安全检查清单

data_pipeline:
  training_data_encryption: required
  inference_data_encryption: required
  pii_detection: required
  data_retention_policy: 90 days

model:
  watermarking: required
  adversarial_robustness_test: required
  bias_audit: required
  model_card: required
  version_control: required

inference_service:
  authentication: required       # JWT / API Key
  rate_limiting: 1000 req/min
  input_sanitization: required   # 防止注入
  output_filtering: required     # 内容安全
  request_audit_log: required

infrastructure:
  network_isolation: required    # 私有 VPC
  secrets_management: required   # 密钥管理服务
  container_scanning: required   # 镜像安全扫描
  runtime_monitoring: required   # 异常行为检测
  incident_response: required    # 应急响应流程
```

### 5.2 生产监控指标

```python
# AI 安全监控指标
class AIMonitoringMetrics:
    """AI 生产安全监控"""

    @staticmethod
    def register_metrics(registry):
        # 模型性能
        registry.counter("inference_requests", "Total inference requests")
        registry.gauge("inference_latency_ms", "Inference latency")
        registry.histogram("output_toxicity", "Toxicity score per output")

        # 安全事件
        registry.counter("jailbreak_attempts", "Detected jailbreak attempts")
        registry.counter("prompt_injection_detected", "Prompt injection rate")
        registry.counter("data_poisoning_flagged", "Flagged inputs")

        # 合规
        registry.counter("content_blocked", "Content blocked by policy")
        registry.gauge("model_watermark_asr", "Watermark attack success rate")
        registry.gauge("audit_chain_integrity", "1=valid, 0=broken")
```

---

## 六、总结

| 安全维度 | 技术手段 | 成熟度 |
|---------|---------|-------|
| 版权保护 | 模型水印 | 🟡 中等 |
| 结果可信 | zk-SNARK / TEE | 🟢 生产可用（TEE）/ 🟡 研究阶段（zk） |
| 透明度 | Model Cards / Datasheets | 🟢 行业标准 |
| 合规 | 审计链 / 备案 / DPIA | 🟢 法律要求 |
| 部署安全 | 加密 / 鉴权 / 限流 / 隔离 | 🟢 标准实践 |

**工程优先级**（从高到低）：
1. ✅ 审计日志 + 模型卡（立即做，成本低）
2. ✅ 鉴权 + 加密 + 限流（标准安全实践）
3. ✅ 内容安全过滤（避免合规风险）
4. ⏳ 模型水印（有新模型时添加）
5. ⏳ TEE 部署（高安全等级需求时）
6. 🔬 zk-SNARK for ML（前沿，跟踪即可）

---

## 进一步阅读
- [Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993) (Mitchell et al.)
- [Datasheets for Datasets](https://arxiv.org/abs/1803.09010) (Gebru et al.)
- EZKL: [Zero-Knowledge Proofs for ML](https://github.com/zkonduit/ezkl)
- [生成式人工智能服务管理暂行办法](https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm)
- GDPR [Art. 22](https://gdpr-info.eu/art-22-gdpr/) Automated Decision Making
