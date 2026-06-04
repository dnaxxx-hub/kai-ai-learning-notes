# 第18课：生成模型 (VAE/GAN)

> 日期: 2026-05-08
> 代码: `ml_generative.py`

## VAE (变分自编码器)

### 架构
```
Encoder: x → [μ, logvar] → 重参数化 → z
Decoder: z → x'
```

### 损失
```
L = recon_loss + β · KL_loss
KL_loss = D_KL(N(μ,σ²) || N(0,1)) = 0.5∑(μ² + σ² - lnσ² - 1)
```

### 结果
| 指标 | 值 |
|------|-----|
| 重建MSE | 0.14 |
| KL散度 | 0.06 |
| 生成数据均值 | (0.47, 0.52) vs 真实(0.50, 0.50) |

## GAN
- Generator: z(2) → hidden → sigmoid → x(2)
- Discriminator: x(2) → hidden → sigmoid → D(x)
- 零和博弈: min_G max_D V(D,G)
