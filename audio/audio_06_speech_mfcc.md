# 第6课：语音处理

## 一、概述：语音信号处理的独特性

语音与音乐不同：
- **非平稳性**：声道形状随时间变化（每秒 5~15 个音素）
- **短时平稳假设**：10~30ms 内声道形状变化很小 → 可当作平稳信号处理
- **连续/离散性**：语音包含连续的基频（F0）和离散的声道谐振特性（共振峰）

**核心任务**：
- 分析：MFCC、基频检测、共振峰提取
- 增强：去噪、去混响、分离
- 合成：TTS
- 识别：ASR

---

## 二、分帧与加窗 (Framing & Windowing)

### 2.1 分帧

语音是时变信号，但 10~30ms 内可看作平稳。

**参数**：
- **帧长 (Frame Length)**：16~32ms（如 16kHz 采样率下 512 点 = 32ms）
- **帧移 (Frame Shift / Hop Size)**：5~10ms（如 256 点 = 16ms，50% 重叠）
- **帧数**：`N_frames = ceil((N_samples - frame_length) / hop) + 1`

```python
def framing(x, frame_len, hop_len):
    n_frames = 1 + (len(x) - frame_len) // hop_len
    frames = np.zeros((n_frames, frame_len))
    for i in range(n_frames):
        start = i * hop_len
        frames[i] = x[start:start + frame_len]
    return frames
```

### 2.2 加窗

截断引入频谱泄露，加窗可抑制旁瓣。

**常用窗函数**：

#### 矩形窗 (Rectangular Window)
```
w[n] = 1,  0 ≤ n < N
```
- 主瓣最窄（分辨率最高）
- 旁瓣最高（-13 dB），泄露严重

#### 汉明窗 (Hamming Window)
```
w[n] = 0.54 - 0.46 · cos(2πn / (N-1))
```
- 旁瓣 -43 dB，主瓣宽度是矩形窗的 2 倍
- 语音处理最常用

#### 汉宁窗 (Hann Window)
```
w[n] = 0.5 · (1 - cos(2πn / (N-1)))
```
- 旁瓣 -32 dB，端点归零
- 在频谱分析中常优先于汉明窗

#### 布莱克曼窗 (Blackman Window)
```
w[n] = 0.42 - 0.5·cos(...) + 0.08·cos(4πn/(N-1))
```
- 旁瓣 -58 dB，主瓣最宽

**窗函数对比**：
```
属性          │ 矩形    │ 汉宁    │ 汉明    │ 布莱克曼
──────────────┼─────────┼─────────┼─────────┼─────────
主瓣宽度 (bins) │ 0.89    │ 1.44    │ 1.30    │ 1.68
最高旁瓣 (dB)   │ -13     │ -32     │ -43     │ -58
衰减率 (dB/oct) │ -6      │ -18     │ -6      │ -18
```

**经验法则**：分析用汉明窗（语音友好），合成用汉宁窗（COLA 条件好）。

### 2.3 COLA 条件 (Constant OverLap-Add)

完美重建的条件：
```
Σ w[n - k·hop] = const  (对所有 n)
w[n] ∈ R
```

- 汉宁窗 + 50% 重叠 → 完美重建（幅度和为 1）
- 汉明窗 + 50% 重叠 → 幅度有微小波动（~2%）

---

## 三、短时傅里叶变换 (STFT)

### 3.1 定义

```
X(m, k) = Σ x[n] · w[n - m·hop] · e^(-j2πkn/N),  k=0..N-1
```

其中：
- m：帧索引
- k：频率索引（二进制）
- N：FFT 长度（通常 ≥ 帧长）
- hop：帧移

### 3.2 代码实现

```python
def stft(x, n_fft=512, hop_len=256, win=None):
    """
    x: (N,) 输入信号
    返回: (F, T) 复数频谱矩阵
    """
    frame_len = n_fft
    if win is None:
        win = np.hanning(frame_len)
    
    n_frames = 1 + (len(x) - frame_len) // hop_len
    X = np.zeros((n_frames, n_fft // 2 + 1), dtype=complex)
    
    for i in range(n_frames):
        start = i * hop_len
        frame = x[start:start + frame_len] * win
        X[i] = np.fft.rfft(frame)  # 返回复数，half spectrum
    
    return X
```

### 3.3 短时频谱的功率谱

```
P(m, k) = |X(m, k)|²
```

### 3.4 频谱图 (Spectrogram)

可视化方式：
- x 轴：时间（帧索引 × hop / sr）
- y 轴：频率
- z 轴：能量（dB 标度）
- 使用 matplotlib.pcolormesh / specshow

```python
def plot_spectrogram(X, sr, hop_len):
    P = 20 * np.log10(np.abs(X).T + 1e-10)
    plt.imshow(P, aspect='auto', origin='lower',
               extent=[0, len(X)*hop_len/sr, 0, sr/2])
```

### 3.5 iSTFT (逆短时傅里叶变换)

Griffin-Lim 算法：从幅度谱估计相位后重建波形（相位恢复）。

---

## 四、MFCC 特征提取

MFCC (Mel-Frequency Cepstral Coefficients) 是最成功的语音特征之一，用于 ASR、说话人识别、情感识别等。

### 4.1 全流程

```
语音信号
  ↓ 1. 预加重 (Pre-emphasis)
  ↓ 2. 分帧 (Framing)
  ↓ 3. 加窗 (Windowing) — 汉明窗
  ↓ 4. FFT (功率谱)
  ↓ 5. Mel 滤波器组 (Mel Filterbank)
  ↓ 6. Log (对数压缩)
  ↓ 7. DCT (离散余弦变换)
  ↓ 8. 动态特征 (Δ, Δ²) — 可选
  → MFCC 特征向量
```

### 4.2 预加重 (Pre-emphasis)

**目的**：提升高频分量（语音的高频能量自然衰减）

```
y[n] = x[n] - α · x[n-1],  α ∈ [0.95, 0.97]
```

- 时域上一阶高通滤波器
- 频域上每倍频程提升 ~6dB

```python
def pre_emphasis(x, alpha=0.97):
    return np.append(x[0], x[1:] - alpha * x[:-1])
```

### 4.3 Mel 刻度

**Mel 刻度**是人耳感知频率的非线性映射：

```
Mel(f) = 2595 · log10(1 + f / 700)
```

- 低频（<1 kHz）：接近线性
- 高频（>1 kHz）：对数压缩

**逆变换**：
```
f = 700 · (10^(m/2595) - 1)
```

**Mel 滤波器组**：

一组三角滤波器，在 Mel 刻度上等间隔排列，共 M 个（通常 24~40）：

```
H_m(k) = 每个三角滤波器的频率响应
        对于第 m 个滤波器：
        上升至中心频率 f(m) → 线性能量求和
        下降至 f(m+1)
        两端为零
```

```python
def mel_filterbank(n_fft=512, sr=16000, n_mels=24, fmin=0, fmax=None):
    if fmax is None:
        fmax = sr / 2
    
    # 转换到 Mel 刻度
    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    
    # 映射到 FFT bin
    bins = np.floor((n_fft + 1) * hz_points / sr).astype(int)
    
    # 构建三角滤波器
    filterbank = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        l, c, r = bins[m-1], bins[m], bins[m+1]
        # 上升沿
        filterbank[m-1, l:c] = (np.arange(l, c) - l) / (c - l)
        # 下降沿
        filterbank[m-1, c:r] = (r - np.arange(c, r)) / (r - c)
    
    return filterbank
```

### 4.4 对数压缩 (Log)

```
log_mel = log(mel_energy + ε),  ε = 1e-10
```

为什么要取 log？
1. 人耳响度感知接近对数（韦伯-费希纳定律）
2. 乘法性噪声转为加法（便于后续处理）
3. 幅值压缩，数值稳定

### 4.5 离散余弦变换 (DCT)

**目的**：去相关 → 大部分能量集中在低阶系数

```
C[i] = Σ log(E_m) · cos(π·i·(m+0.5)/M),  i=0..13
```

- i=0：所有 Mel 频带的能量总和 → 通常丢弃（能量信息对声学建模用处不大）
- i=1~13：频谱包络的"形状" → 最有用
- i>13：快速变化（类似高频细节）→ 丢弃

**MFCC 维度**：
- 通常取 13 个系数（0~12），或者丢弃 C0 取 12 个
- 加上 Δ（一阶差分，13维）和 Δ²（二阶差分，13维）→ **39 维特征向量**

### 4.6 完整 MFCC 提取器实现

核心代码见 `projects/audio_learning/mfcc_extractor.py`。

### 4.7 为什么 MFCC 这么有效？

1. **Mel 刻度** → 匹配人耳感知，降维的同时保留关键信息
2. **Log + DCT** → 解纠缠、去相关、正交化
3. **丢弃高频系数** → 噪声鲁棒（噪声主要影响高频）
4. **动态特征** → 捕捉语音的时序过渡信息

### 4.8 增强与变体

- **PLP (Perceptual Linear Prediction)**：用听觉模型替换 Mel 滤波器 + 用线性预测替换 DCT
- **FBank / Filterbank Features**：只用 Mel 滤波器组 + log，不用 DCT → 更适合 DNN 模型
- **Gammatone 特征**：用更精确的听觉滤波器替代三角滤波器
- **Wav2vec / HuBERT**：端到端自监督特征，逐渐取代 MFCC

---

## 五、基频检测 (Pitch Detection)

### 5.1 什么是基频？

- **基频 (F0, Fundamental Frequency)**：声带振动的频率
- 成人男性：80~180 Hz
- 成人女性：160~320 Hz
- 儿童：200~450 Hz
- 应用：语调分析、情绪识别、语音合成中的韵律控制

### 5.2 自相关法 (Autocorrelation)

**原理**：语音信号周期性的自相关峰值在基频周期处

```
r(τ) = Σ x[n] · x[n + τ],  τ ∈ [min_lag, max_lag]
```

**步骤**：
1. 对每个帧计算自相关
2. 寻找第一个强峰值（排除 τ=0）
3. 峰值位置 → 基频周期
4. F0 = sr / τ_peak

**改进**：
- 归一化自相关 (NCCF)：
```
nccf(τ) = r(τ) / sqrt(E[0] · E[τ]),  E[τ] = Σ x²[n+τ]
```
- 消除幅度影响，适合变音量语音

**实现**：

```python
def autocorrelation_pitch(frame, sr, fmin=80, fmax=400):
    n = len(frame)
    # 计算自相关
    r = np.correlate(frame, frame, mode='full')
    r = r[n-1:]  # 只取 τ >= 0 的一半
    
    # 限定 lag 范围
    min_lag = int(sr / fmax)
    max_lag = int(sr / fmin)
    r_valid = r[min_lag:max_lag + 1]
    
    # 找峰值
    peak_idx = np.argmax(r_valid) + min_lag
    pitch = sr / peak_idx if r_valid.max() > threshold else 0
    return pitch
```

### 5.3 YIN 算法

**YIN** 是一个更鲁棒的基频检测算法，改进自相关法的问题：

**步骤**：
1. **自相关函数**：r(τ) = Σ (x[n] - x[n+τ])²（差函数）
2. **累积均值归一化**：d'(τ) = d(τ) / (1/τ · Σ d(j))，抑制低阶峰值
3. **绝对阈值**：找第一个低于阈值的谷值（通常 0.1~0.2）
4. **抛物线插值**：在谷值附近拟合抛物线提高精度
5. **最佳局部估计**：选择与附近帧最一致的 F0

**YIN vs 自相关法**：
- YIN 对 ΔF0 不敏感（去除了幅度影响）
- YIN 抑制次谐波错误
- YIN 的 F0 误差率约 1~3%，自相关法约 5~10%

```python
def yin_pitch(frame, sr, fmin=80, fmax=400, threshold=0.1):
    n = len(frame)
    diff = np.zeros(n // 2)
    
    # 差函数
    for tau in range(1, n // 2):
        diff[tau] = np.sum((frame[:n - 2*tau] - frame[2*tau:]) ** 2)
        # 完整实现需要对所有偏移累加，不截断
    
    # 累积均值归一化
    cum_min = np.zeros_like(diff)
    cum_sum = 0
    for tau in range(1, len(diff)):
        cum_sum += diff[tau]
        cum_min[tau] = diff[tau] * tau / cum_sum if cum_sum > 0 else 1
    
    # 找第一个低于阈值的最小值
    min_lag = int(sr / fmax)
    max_lag = int(sr / fmin)
    
    for tau in range(min_lag, max_lag + 1):
        if cum_min[tau] < threshold:
            # 抛物线插值
            if tau > 1 and tau < len(cum_min) - 1:
                a = cum_min[tau - 1] + cum_min[tau + 1] - 2 * cum_min[tau]
                b = (cum_min[tau + 1] - cum_min[tau - 1]) / 2
                tau_frac = -b / (2 * a) if a != 0 else 0
                return sr / (tau + tau_frac)
            return sr / tau
    
    return 0  # 无声
```

### 5.4 其他基频检测方法

| 算法 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 自相关 (ACF) | 时域周期匹配 | 简单快速 | 噪音敏感，次谐波错误 |
| YIN | 差函数+归一化 | 鲁棒，准确 | 计算量大 |
| SWIPE | 频谱匹配 | 非常准确 | 复杂，慢 |
| pYIN | YIN + HMM 平滑 | 最鲁棒 | 更复杂 |
| DIO / Harvest (WORLD) | 高低频分开检测 | 高质量合成用 | 需高采样率 |

---

## 六、语音增强 (Speech Enhancement)

### 6.1 问题定义

观测信号：`y(t) = s(t) + n(t)`
目标：从 y(t) 中估计 s(t)

### 6.2 谱减法 (Spectral Subtraction)

**原理**：噪声假设为加性且平稳——在无语音段估计噪声谱，然后减去。

```
|Ŝ(ω)|² = |Y(ω)|² - α · |N̂(ω)|²
```

其中：
- |Y(ω)|²：带噪语音功率谱
- |N̂(ω)|²：噪声功率谱估计（无声段平均）
- α：过减因子 (1~3)，越大抑制越多但失真也大

**实现步骤**：
1. STFT 得到 Y(m, k)
2. 噪声估计：前几帧（仅噪声）或 VAD 检测的静音段
3. 幅度谱减：`|Ŝ| = max(|Y| - α·|N̂|, β·|Y|)`（β 是频谱下限，避免音乐噪声）
4. 相位使用带噪语音的相位
5. iSTFT 合成

**问题**：**音乐噪声 (Musical Noise)**——残留的随机尖峰听起来像音乐片段

**解决方案**：
- 频谱下限 (Spectral Floor)：`|Ŝ| = max(... , β|Y|)`，β≈0.01~0.1
- 过减因子随 SNR 自动调整
- 时序平滑

### 6.3 维纳滤波 (Wiener Filter)

**原理**：最小化 MSE 的最优线性滤波器

频域维纳滤波器：
```
H(k) = Ps(k) / (Ps(k) + Pn(k)) = ξ(k) / (1 + ξ(k))
```

其中：
- Ps(k)：语音功率谱密度
- Pn(k)：噪声功率谱密度
- ξ(k) = Ps(k)/Pn(k)：先验信噪比 (a priori SNR)

**实现**：

```python
def wiener_filter(Y, noise_psd):
    # Y: 带噪语音频谱 (complex)
    # noise_psd: 噪声功率谱
    
    # 先验 SNR 估计 (decision-directed)
    snr_post = (|Y|² / noise_psd) - 1  # 后验 SNR
    snr_post = max(snr_post, 0)
    snr_prior = α * (|Ŝ_prev|² / noise_psd) + (1-α) * snr_post
    
    # 维纳增益
    H = snr_prior / (1 + snr_prior)
    Ŝ = H * Y
    return Ŝ
```

**维纳滤波 vs 谱减法**：
- 谱减法是维纳滤波的特例（当 Ps 用当前帧估计时）
- 维纳滤波时音乐噪声更少（幅度更平滑）
- 维纳滤波需先验 SNR 估计（通常用 "decision-directed" 方法）

### 6.4 现代方法

- **相位感知方法**：Deep Complex U-Net、DCCRN
- **扩散模型语音增强**：SGMSE、CDiffuSE
- **自监督去噪**：Demucs、Conv-TasNet

---

## 七、TTS 与 ASR 基本原理

### 7.1 TTS (Text-to-Speech)

#### 传统方法

**串联合成 (Concatenative Synthesis)**：
1. 录音数据库 → 分割成音素/双音子
2. 根据文本选择最佳候选序列
3. 波形拼接
4. 问题：自然但存储量大，无法产生新声音

**参数合成**：
```
文本 → 前端分析(分词/注音/韵律) → 声学模型(时长/F0/频谱) → 声码器 → 波形
```

- 声码器：STRAIGHT、WORLD (D4C + CheapTrick + PLATINUM)

#### 现代方法

- **Tacotron 2**：Encoder-Attention-Decoder → Mel 频谱 → WaveNet 声码器
- **FastSpeech**：非自回归，时长预测器，5x 以上速度
- **VITS**：端到端，VAE + flow，一次性生成波形
- **CosyVoice**：阿里达摩院，零样本语音克隆

### 7.2 ASR (Automatic Speech Recognition)

#### 传统方法 (GMM-HMM)

```
音频 → MFCC → GMM（声学模型）→ HMM（时序模型）→ 语言模型 → 文本
```

#### 端到端方法

**CTC (Connectionist Temporal Classification)**：
- 输入：T 帧 MFCC/FBank
- 输出：T 个字符标签或 blank（重复/空白对齐）
- 解码时合并重复和空白 → 文本
- 典型模型：DeepSpeech 2

**RNN-T (RNN Transducer)**：
- 流式处理，无需等待整句
- 适合实时 / 低延迟（如手机输入法）

**Transformer / Conformer ASR**：
- Conformer：CNN + Transformer 混合，最优
- **Whisper** (OpenAI)：Encode-Decode Transformer，多语言
- **SenseVoice** (阿里)：多语言 + 事件检测

### 7.3 TTS/ASR 共性流程

```
声学层面：
  语音 → 分帧 → 加窗 → STFT → (反)特征
  MFCC ← DCT ← log ← Mel滤波器 ← |STFT|²

建模层面：
  输入 → 特征提取 → 神经网络编码 → 解码 → 输出
         TTS: 文本 → 音素 → Encoder → Decoder → Mel → Vocoder → 波形
         ASR: 波形 → FBank → Encoder → CTC/Decoder → 文本
```

---

## 八、Python 实战速查

```python
import numpy as np

# 预加重
def pre_emphasis(x, alpha=0.97):
    return np.append(x[0], x[1:] - alpha * x[:-1])

# 分帧
def framing(x, frame_len=512, hop_len=256):
    n_frames = 1 + (len(x) - frame_len) // hop_len
    frames = np.zeros((n_frames, frame_len))
    for i in range(n_frames):
        frames[i] = x[i*hop_len:i*hop_len + frame_len]
    return frames

# 汉明窗
def hamming(n):
    return 0.54 - 0.46 * np.cos(2 * np.pi * np.arange(n) / (n - 1))

# Mel 刻度
def hz_to_mel(f):
    return 2595 * np.log10(1 + f / 700)

def mel_to_hz(m):
    return 700 * (10 ** (m / 2595) - 1)

# 自相关基频
def pitch_acf(frame, sr, fmin=80, fmax=400):
    n = len(frame)
    r = np.correlate(frame, frame, mode='full')[n-1:]
    min_lag = int(sr / fmax)
    max_lag = int(sr / fmin)
    peak = np.argmax(r[min_lag:max_lag+1]) + min_lag
    return sr / peak if r[peak] > 0 else 0
```

---

## 参考
- Stevens, Volkmann & Newmann, "A Scale for the Measurement of the Psychological Magnitude Pitch", JASA 1937
- Davis & Mermelstein, "Comparison of parametric representations for monosyllabic word recognition", IEEE ASSP 1980
- Rabiner & Schafer, "Theory and Applications of Digital Speech Processing", 2010
- de Cheveigné & Kawahara, "YIN, a fundamental frequency estimator for speech and music", JASA 2002
- Boll, "Suppression of acoustic noise in speech using spectral subtraction", IEEE ASSP 1979
