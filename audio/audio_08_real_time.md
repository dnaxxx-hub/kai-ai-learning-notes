# 第8课：实时音频处理

## 1. 概述

> 实时音频处理的核心约束：**每个音频块的处理时间必须小于块时长**。
> 本课覆盖实时处理的核心技术栈。

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 音频采集      │ → │  实时处理     │ → │  音频输出     │
│ (mic/Wav)    │   │ (FFT/滤波器) │   │ (speaker)    │
└──────────────┘   └──────────────┘   └──────────────┘
                        ↓
                  ┌──────────────┐
                  │ 特征提取     │
                  │ (MFCC/VAD)  │
                  └──────────────┘
```

---

## 2. 实时 FFT 卷积 — 分块卷积 (Overlap-Add)

### 2.1 问题
直接卷积 `y[n] = x[n] * h[n]`：
- 线性卷积 `O(N²)`
- FFT 加速后 `O(N log N)`
- 但必须**等全部信号输入后**才能开始，实时性极差

### 2.2 Overlap-Add 分块卷积

**原理**：将长信号切分 → 逐块 FFT 卷积 → 拼接输出

```
输入 x[n]: [块0  ████████][块1  ████████][块2  ████████]...
                        ↓↓↓
每个块: 零填充 → FFT → 点乘(FFT(h)) → IFFT → 取前 L 点
                        ↓↓↓
输出 y[n]: [█ █ █ █ █ █][追加 █ █ █ █ █][追加 █ █ █ █]...
            ← 块长度 → ← 重叠相加 →       ← 重叠相加 →
```

**算法步骤**：
```
1. 设置块大小 B（通常 64~4096 样本）
2. 对每个块 x_m[n]：
   a. 零填充至 N = B + L - 1（L = 滤波器长度）
   b. FFT → 乘以频域滤波器 H[k] → IFFT
   c. 结果 y_m 长度为 N
   d. 前 B 点送输出，后 L-1 点与下一块的前 L-1 点相加
3. 延迟 = B 样本（可控）
```

**分段卷积变体**：
| 方法 | 延迟 | 计算效率 |
|------|------|----------|
| 标准 OLA | B + L - 1 | 高 |
| 零延迟 OLA | L | 中 (2×FFT/块) |
| 自适应分块 | 可变 | 高 |

### 2.3 频域滤波的实时实现

```python
class RealTimeConvolver:
    """实时频域卷积器（OLA 实现）。"""
    
    def __init__(self, ir, block_size=1024):
        self.block_size = block_size
        self.ir_fft = fft(ir, n=block_size + len(ir) - 1)
        self.tail = np.zeros(len(ir) - 1)
    
    def process(self, x_block):
        # 零填充 + FFT
        X = fft(x_block, n=len(self.ir_fft))
        Y = X * self.ir_fft
        y = ifft(Y).real
        
        # 重叠相加
        out = y[:self.block_size] + self.tail
        self.tail = y[self.block_size:]
        return out
```

---

## 3. 多频段压缩器

### 3.1 基本原理
音频压缩器 = 自动增益控制：
- 信号高于阈值 → 降低增益
- 信号低于阈值 → 增益不变

**参数**：
```
Threshold:  -60 ~ 0 dB      触发压缩的阈值
Ratio:       1:1 ~ ∞:1      压缩比（∞=限幅器）
Attack:     0.1~50 ms       压缩启动时间
Release:    10~1000 ms      压缩释放时间
Knee:       0~12 dB         拐点平滑度（软拐点）
Makeup Gain: 0~20 dB        补偿增益
```

### 3.2 多频段架构
```
输入 → [分频滤波器] →
         → 低频段：[压缩器1] → 增益系数 →
         → 中频段：[压缩器2] → 增益系数 → [求和] → 输出
         → 高频段：[压缩器3] → 增益系数 →
```

**频段划分**（典型）：
- 低频：20~250 Hz
- 中低频：250~2000 Hz
- 中高频：2000~8000 Hz
- 高频：8000~20000 Hz

### 3.3 增益计算
```
1. 计算 RMS 电平（包络检测）
   rms = sqrt(mean(x²))
   envelope = RMS + 一阶低通平滑

2. 计算增益变化
   if envelope > threshold:
       gain_db = (threshold - envelope) * (1 - 1/ratio)
   else:
       gain_db = 0

3. Attack/Release 平滑
   alpha = attack_time  ? attack_alpha : release_alpha
   gain_smooth = alpha * gain + (1-alpha) * gain_smooth
```

---

## 4. 音频特征提取管线

### 4.1 管线架构
```
PCM → 预处理 → 分帧 → [时域特征] → [频域特征] → 特征融合 → 输出
                        │              │
                   过零率、能量    MFCC、谱质心
                                   色度特征
```

### 4.2 时域特征

**过零率 (ZCR)**：
```
ZCR = (1/N) · Σ |sign(x[n]) − sign(x[n−1])| / 2

用途：区分清音(高 ZCR) 和浊音(低 ZCR)
     噪声检测、音乐类型分类
```

**能量 / RMS**：
```
RMS = sqrt(Σ x²[n] / N)
用途：VAD、音量检测
```

### 4.3 频域特征

**谱质心 (Spectral Centroid)**：
```
SC = Σ f[k]·|X[k]| / Σ |X[k]|

用途：音色明亮度指示器
     高 SC → 明亮音色（如笛子）
     低 SC → 低沉音色（如大提琴）
```

**谱平坦度 (Spectral Flatness)**：
```
SF = (Π |X[k]|^(1/K)) / (Σ |X[k]|/K)
                        几何均值 / 算术均值

用法：SF≈1 → 噪声
      SF≈0 → 谐波信号（纯音）
```

**谱滚降点 (Spectral Rolloff)**：
```
Σ_{k=0}^{rolloff} |X[k]| = 0.85 · Σ_{k=0}^{K-1} |X[k]|

用途：区分语音/音乐（语声的滚降约 3~5kHz）
```

### 4.4 色度特征 (Chroma Features)

将 12 个半音能量映射到色谱向量：
```
chroma[c] = Σ |X[f_c + k·12]|²,  c = 0..11

f_c: 对应 C, C#, D, ..., B (12 个音名)
k: 八度谐波

用途：和弦识别、音乐相似度、翻唱检测
```

### 4.5 特征向量拼接
```
最终特征向量 = [MFCC(13) + SC(1) + ZCR(1) + RMS(1) + Chroma(12)]
             = 28 维向量（含 delta 则为 56 维）
```

---

## 5. 语音活动检测 (VAD)

### 5.1 原理
VAD 判断当前帧是 **语音** 还是 **静音/噪声**。

### 5.2 能量门限法（最简实现）
```
if RMS > threshold:
    voice_activity = True
else:
    voice_activity = False
```

### 5.3 改进方法

**双门限**：
- 高阈值：确认语音开始
- 低阈值：确认语音结束（滞迟）

**特征组合法**：
```
LRT (Likelihood Ratio Test):
  VAD 决策 = f(RMS, ZCR, SC, MFCC)

其中：
  H0: 噪声帧
  H1: 语音帧
  L(y) = p(y|H1) / p(y|H0)
```

**参数自适应**：
- 前 N 帧估计噪声底噪
- 动态门限 = 噪声均值 + α · 噪声标准差

### 5.4 状态机
```
     噪声       (RMS > 高阈值)       语音
[IDLE] ──────────────────────→ [ACTIVE]
  ↑                              │
  └──── (RMS < 低阈值, 持续 T) ←─┘
```

---

## 6. 延迟预算

```
实时系统的总延迟 =                              典型值
  采集缓冲延迟  +  分帧延迟  +  处理延迟  +  输出缓冲

  采集: 取决于块大小 (2.7ms @ 48kHz, 128样本)
  处理: 算法复杂度 (1~20ms)
  输出: 输出缓冲 (2.7ms)
  总延迟: < 30ms (可接受) / < 10ms (专业)
```

---

## 7. 参考
- W. Gardener, "Efficient Convolution without Input-Output Delay"
- U. Zölzer, "DAFX: Digital Audio Effects"
- ITU-T G.729 Annex B (VAD)
- J. Salamon et al., "Chroma Features for Cover Song Identification"
