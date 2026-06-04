# 优化器：SGD → Momentum → Adam

> 日期：2026-05-07 17:30 | 课程：ML/DL路线 Phase 3-5
> 目标：理解优化器是怎么"加速学习"的

## 核心直觉

### 优化器解决什么问题？

```
参数更新 = 参数 - 学习率 × 梯度
```
没有比这更简单的了。但直接这么更新效果很差：
- **学习率太大** → 震荡，不收敛
- **学习率太小** → 训练极慢
- **梯度方向变化** → zig-zag路径

优化器的任务：**让更新步长和方向更好**。

## 演进路线

### SGD（随机梯度下降）
```python
w = w - lr * grad
```
- 简单直接
- 但：在峡谷地形中剧烈震荡，收敛慢

### SGD + Momentum（动量）
```python
v = β * v + (1-β) * grad      # 保持"惯性"
w = w - lr * v
```
- v = 累积的历史梯度方向
- β控制记忆多久（0.9 ≈ 最近10步）
- **效果**：穿过峡谷不震荡，加速收敛

### AdaGrad — 自适应学习率
```python
cache += grad²
w = w - lr * grad / sqrt(cache + ε)
```
- 梯度大的方向 → 学习率自动变小
- 问题：学习率单调递减，训练到后面就停了

### RMSProp — 修复AdaGrad
```python
cache = β * cache + (1-β) * grad²    # 指数移动平均
w = w - lr * grad / sqrt(cache + ε)
```
- 用指数移动平均代替累加
- 学习率不会单调为0

### Adam — 集大成者（Momentum + RMSProp）
```python
# Momentum部分
m = β₁ * m + (1-β₁) * grad          # 一阶矩（均值）

# RMSProp部分
v = β₂ * v + (1-β₂) * grad²         # 二阶矩（未中心化方差）

# 偏差修正（前几步估计偏差大）
m_hat = m / (1 - β₁^t)
v_hat = v / (1 - β₂^t)

# 更新
w = w - lr * m_hat / (sqrt(v_hat) + ε)
```

### Adam ≈ SGD + Momentum + RMSProp + 偏差修正

## 可视化

![优化器对比](13_optimizers.png)

**左图（SGD）**：直线路径，但步长保守，收敛慢（200步才到）
**中图（Momentum）**：路径更平滑，比SGD略快
**右图（Adam）**：**最快到达最优解**（60步），自适应步长

## 选择指南

| 场景 | 推荐优化器 | 原因 |
|------|-----------|------|
| 计算机视觉 | SGD + Momentum | 泛化性更好 |
| NLP / Transformer | Adam / AdamW | 处理稀疏梯度 |
| GAN训练 | Adam | 不稳定的训练需要自适应 |
| 小批量数据 | SGD | 简单直接 |
| 大规模预训练 | AdamW | 带权重衰减的Adam |
| 强化学习 | Adam | 处理非平稳目标 |

## 学习率调度

优化器决定"向哪走"，学习率决定"走多大步"：

```python
# 常用调度策略：
# 1. Step Decay: 每隔Epoch按固定比例衰减
# 2. Cosine Annealing: 余弦函数逐渐减小
# 3. Warmup: 前几步从小逐渐增大（Transformer常用）
# 4. Reduce on Plateau: loss不降了再减学习率

# Warmup + Cosine Annealing 是预训练的标准配方
```

## 今日收获
- SGD = 基本版，但震荡剧烈
- Momentum = 加惯性，平滑路径
- RMSProp = 自适应学习率
- **Adam = Momentum + RMSProp + 偏差修正 = 目前首选**
- AdamW = Adam + 解耦权重衰减（比L2正则化更好）
- 学习率调度和优化器同样重要

**Phase 3（DL基础）至此全部完成！** 🎉
