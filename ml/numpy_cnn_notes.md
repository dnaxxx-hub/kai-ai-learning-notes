# CNN 纯numpy实现 — 学习笔记

## 架构
```
Input (1×8×8) → Conv(3×3, 2ch, valid) → ReLU → MaxPool(2×2) → FC(18→3) → Softmax
```

## 反向传播链路
```
Softmax grad = (pred - one_hot) / batch
→ FC: dW = x^T @ dout, dx = dout @ W^T
→ Pool: 梯度只回传最大值位置（mask）
→ ReLU: drelu = dpool * (z > 0)
→ Conv: dW = window × dout, dx = kernel × dout（反方向滑窗）
```

## 关键洞察
1. **卷积反向传播 = 卷积核转置后的卷积**，用180°旋转的卷积核在梯度图上做卷积
2. **MaxPool反向传播 = 梯度只给赢家**，输家拿不到梯度（非最大值位置归零）
3. **纯numpy实现非常慢** — 滑窗5层循环，O(b×c_out×c_in×H×W×k²)
4. **合成数据100%正确** — 说明CNN的结构归纳偏置（局部连接+平移不变性）对模式识别非常有效
