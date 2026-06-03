# 第2课：傅里叶分析

## 1. 傅里叶级数
- 任何周期性信号可分解为**正弦波之和**
- 基频 + 谐波（整数倍频率）
- x(t) = a₀ + Σ(aₙcos(2πnf₀t) + bₙsin(2πnf₀t))

## 2. 傅里叶变换（FT）
- 将时域信号变换到频域
- 连续时间：FT → 频谱密度函数
- 离散时间：DTFT → 连续频谱

## 3. 离散傅里叶变换（DFT）
- 计算机处理的是**离散、有限长**信号
- DFT：X[k] = Σx[n]·e^(-j2πkn/N)
- 复杂度 O(N²) → 太慢

## 4. 快速傅里叶变换（FFT）
- Cooley-Tukey算法：O(N·log₂N)
- 要求 N = 2^k（2的幂）
- Python直接用 `np.fft.fft()`

## 5. 频谱图（Spectrogram）
- 短时傅里叶变换（STFT）：分帧 → 每帧做FFT
- 时间-频率-幅度 三维展示
- 用于语音、音乐分析

## 关键概念
| 概念 | 含义 |
|------|------|
| DC分量 | X[0]，零频（平均值） |
| 频率分辨率 | Δf = fs / N |
| 频谱泄漏 | 非整数周期截断导致 |
| 窗函数 | 减轻频谱泄漏 |

```python
# FFT示例
N = 1024
fs = 44100
t = np.arange(N) / fs
signal = np.sin(2*np.pi*1000*t)  # 1kHz纯音
fft_out = np.fft.rfft(signal)    # 实信号FFT，只取正频
freqs = np.fft.rfftfreq(N, 1/fs) # 对应的频率轴
```
