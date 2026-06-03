# 第8课：Python音频实战

## 实战项目

### 1. 频谱分析器
- 读取WAV → FFT → 显示频谱
- 核心：`np.fft.rfft()`, `scipy.signal.spectrogram()`

### 2. 滤波器设计器
- 交互式选择滤波器类型/参数
- 实时查看频率响应
- 核心：`scipy.signal.butter()`, `scipy.signal.freqz()`

### 3. WAV编辑器
- 裁剪、拼接、淡入淡出
- 音量调整、反向播放
- 核心：数组切片操作 + 包络调制

### 4. 简单音频指纹
- 星座图提取 + 哈希匹配
- 识别来自数据库的音频
- 核心：谱峰提取 + 哈希表

## 实用技巧

### 音频处理流水线
```python
def process_audio(wav_path):
    data, sr = read_wav(wav_path)
    # 预处理
    data = data / np.max(np.abs(data))     # 归一化
    data = signal.filtfilt(b, a, data)      # 滤波
    # 分析
    spec = np.abs(np.fft.rfft(data))        # 频谱
    mfcc = compute_mfcc(data, sr)           # MFCC
    # 输出
    write_wav("output.wav", data)
    return spec, mfcc
```

### 常用函数速查
| 功能 | 函数 |
|------|------|
| FFT | `np.fft.rfft()` |
| 频谱图 | `signal.spectrogram()` |
| 滤波器 | `signal.butter()`, `signal.firwin()` |
| 自相关 | `np.correlate()` |
| 重采样 | `signal.resample()` |
| 窗函数 | `np.hamming()`, `np.blackman()` |
| 卷积 | `np.convolve()` |

## 推荐学习资源
- **书**：《Understanding Digital Signal Processing》- Lyons
- **书**：《数字音频处理》- Udo Zölzer
- **书**：《Speech and Language Processing》- Jurafsky
- **实战**：librosa文档（Python音频分析库）
- **工具**：Audacity（音频编辑）、Sonic Visualiser（频谱分析）
