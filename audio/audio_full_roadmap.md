# 🎵 信号/音频处理 — 全路线图

> 从零到一：8课系统学习音频信号处理

---

## 课程一览

| 课 | 主题 | 核心要点 |
|---|------|---------|
| 01 | **信号基础** | 连续/离散信号, 时域/频域, Nyquist采样定理, 混叠效应 |
| 02 | **傅里叶分析** | 傅里叶级数/变换, FFT原理, 频谱图(STFT) |
| 03 | **数字滤波器** | 低/高/带通/带阻, FIR vs IIR, 卷积, Butterworth设计 |
| 04 | **音频编码基础** | PCM/WAV格式, 量化编码, 采样率/位深度, 纯Python读写WAV |
| 05 | **MP3/AAC编码** | 心理声学模型, 掩蔽效应, 子带编码, 霍夫曼编码 |
| 06 | **语音处理** | 分帧加窗, MFCC特征, 基频检测, TTS/ASR基本原理 |
| 07 | **音频指纹** | 频谱哈希, Shazam算法(星座图+哈希匹配) |
| 08 | **Python实战** | 频谱分析器, 滤波器设计, WAV编辑, 简单音频指纹 |

---

## 文件索引

### 笔记文件
| 文件 | 内容 |
|------|------|
| `audio_01_signal_basics.md` | 信号基础：采样、混叠、Nyquist |
| `audio_02_fourier.md` | 傅里叶分析：级数、变换、FFT、频谱图 |
| `audio_03_filter.md` | 数字滤波器：类型、FIR/IIR、卷积 |
| `audio_04_wav_pcm.md` | 音频编码：PCM、WAV格式结构 |
| `audio_05_mp3_aac.md` | MP3/AAC：心理声学、掩蔽、子带编码 |
| `audio_06_speech.md` | 语音处理：分帧、MFCC、基频检测 |
| `audio_07_fingerprint.md` | 音频指纹：Shazam算法、星座图 |
| `audio_08_python_practice.md` | Python实战：工具链、速查表 |

### 代码文件
| 文件 | 内容 |
|------|------|
| `code/audio_01_signal_basics.py` | 波形生成、混叠演示 |
| `code/audio_02_fourier.py` | FFT分析、频谱图绘制 |
| `code/audio_03_filter.py` | FIR/IIR滤波器设计、频率响应 |
| `code/audio_04_wav_pcm.py` | 纯Python WAV读写（不依赖库） |
| `code/audio_05_mp3_aac.py` | 心理声学模拟、掩蔽曲线、子带分解 |
| `code/audio_06_speech.py` | 分帧加窗、MFCC计算、基频检测 |
| `code/audio_07_fingerprint.py` | Shazam简化实现、哈希匹配 |
| `code/audio_08_python_practice.py` | 综合工具箱：频谱分析、WAV编辑、指纹 |

---

## 关键公式速查

### 采样定理
```
fs ≥ 2 × f_max       # Nyquist采样定理
f_alias = |f - fs|    # 混叠频率
```

### FFT
```
X[k] = Σ x[n]·e^(-j2πkn/N)     # DFT
f_res = fs / N                    # 频率分辨率
f_norm = k × fs / N               # 实际频率
```

### 滤波器
```
y[n] = Σ b[k]·x[n-k] - Σ a[k]·y[n-k]    # IIR差分方程
y[n] = Σ b[k]·x[n-k]                      # FIR (a=0)
```

### 音频参数
```
bitrate = sr × bits × channels    # 比特率
dynamic_range = 6.02×bits + 1.76  # 动态范围(dB)
```

### MFCC
```
mel = 2595·log₁₀(1 + f/700)       # 频率→Mel刻度
```

---

## 运行指南

```bash
# 确保安装了依赖
pip install numpy matplotlib scipy

# 运行任意课程示例
python D:\kai_knowledge\learning\code\audio_01_signal_basics.py
python D:\kai_knowledge\learning\code\audio_04_wav_pcm.py
```

> 所有代码均在 Windows 环境下测试通过，纯 Python 实现，**无需额外音频库**。

---

*创建日期：2026-02-27*
*学习用时：8课时，每课约30-60分钟*
