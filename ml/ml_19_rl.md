# 第19课：强化学习

> 日期: 2026-05-08
> 代码: `ml_rl.py`

## Q-learning
```
Q(s,a) ← Q(s,a) + α[r + γ·max_a' Q(s',a') - Q(s,a)]
```

**4×4 GridWorld结果**
- 500 episodes训练
- Q-learning学到6步最优路径: 0→1→5→9→10→11→15 ✅
- 平均奖励9.30（接近最优10 - 6×0.1 = 9.4）

## REINFORCE (Policy Gradient)
- 策略网络：softmax(s·W + b)
- 更新：∇J ≈ G_t·∇log π(a_t|s_t)
- 平均奖励9.15，也学到了合理策略

## 算法对比
| 指标 | Q-learning | REINFORCE |
|------|-----------|-----------|
| 类型 | Value-based | Policy-based |
| 策略 | 隐式 (ε-greedy) | 显式 (softmax) |
| 收敛 | 稳定 | 方差大 |
