# 实时音视频处理

> 音视频编解码第7课 — 从回声消除到视频增强

## 实时通信的关键挑战

### 三大核心问题
1. **延迟**：从采集到渲染的端到端延迟
2. **质量**：在各种网络条件下的音视频质量
3. **同步**：音频和视频的唇同步

### 实时音频处理链

```
麦克风采集 → AEC → ANS → AGC → VAD → 编码 → 网络
                                                          
扬声器输出 ← 解码 ← NetEQ ← 网络
```

## AEC（声学回声消除）

### 回声来源
- 扬声器声音被麦克风重新采集
- 声学传播 + 扬声器/麦克风硬件耦合

### 核心算法：NLMS自适应滤波

```python
# NLMS 自适应滤波简化版
def nlms_aec(mic_signal, ref_signal, filter_len=512, mu=0.1, epsilon=1e-6):
    """简化NLMS回声消除"""
    h = np.zeros(filter_len)  # 自适应滤波器
    
    for n in range(filter_len, len(mic_signal)):
        # 参考信号向量
        x = ref_signal[n-filter_len:n][::-1]
        # 估计回声
        echo_estimate = np.dot(h, x)
        # 误差信号（消除后的信号）
        e = mic_signal[n] - echo_estimate
        # NLMS 更新
        norm = np.dot(x, x) + epsilon
        h += (mu / norm) * e * x
    
    return h  # 滤波器系数
```

### AEC三个阶段
1. **线性滤波**：消除线性回声（NLMS/AES）
2. **非线性处理**：消除残留非线性回声
3. **舒适噪声注入**：防止完全静音的不适感

### 常见问题
- 双讲（Double Talk）：双方同时说话时滤波器发散
- 非线性失真：廉价扬声器导致的谐波回声
- 延迟漂移：时钟不同步导致延迟变化

## ANS（背景噪声抑制）

### 噪声类型
| 类型 | 示例 | 难度 |
|------|------|------|
| 平稳噪声 | 风扇/空调 | 容易 |
| 非平稳 | 键盘/关门 | 中等 |
| 突发 | 咳嗽/碰撞 | 困难 |
| 人声干扰 | 背景对话 | 最难 |

### 频谱减法（传统方法）
```
带噪信号 → FFT → 幅度谱 → 噪声估计 → 频谱减法 → IFFT → 干净信号
```

### 基于ML的降噪（现代方法）
- RNNoise：轻量RNN+DFT特征的实时降噪
- DCCRN：复数域CNN+RNN的高质量降噪
- TF-GridNet：Transformer的SOTA降噪

## AGC（自动增益控制）

### 目标
- 将输入信号调整到目标电平（通常-26 dBFS）
- 平滑变化，不产生泵浦效应

### 实现
```python
def agc_simple(audio, target_level=-26.0, attack_ms=10, release_ms=100, sample_rate=16000):
    """简化AGC实现"""
    attack = 1 - np.exp(-1000/(attack_ms * sample_rate))
    release = 1 - np.exp(-1000/(release_ms * sample_rate))
    
    gain = 1.0
    output = np.zeros_like(audio)
    
    for i in range(len(audio)):
        # 当前level（RMS）
        frame = audio[max(0,i-480):i+1]
        current_level = 20 * np.log10(np.sqrt(np.mean(frame**2)) + 1e-10)
        
        # 增益调整
        target_gain = 10 ** ((target_level - current_level) / 20)
        
        # 平滑
        time_const = attack if target_gain < gain else release
        gain += time_const * (target_gain - gain)
        gain = np.clip(gain, 0.1, 10.0)
        
        output[i] = audio[i] * gain
    
    return output
```

## VAD（语音活动检测）

### 特征
- **能量**：短时能量 > 阈值
- **过零率**：语音的过零率通常低于噪声
- **频谱平坦度**：语音的频谱有共振峰结构
- **ML分类**：DNN分类器（WebRTC VAD 2.0+）

### WebRTC VAD 模式
| 模式 | 灵敏度 | 误报率 | 适用 |
|------|--------|--------|------|
| 0 | 最保守 | 低 | 干净环境 |
| 1 | 中等 | 中 | 普通通话 |
| 2 | 最激进 | 高 | 噪声环境 |
| 3 | 宽松 | 非常高 | 音乐/播客 |

## NetEQ（网络抖动缓冲）

### 功能
- **抖动缓冲**：吸收网络延迟抖动
- **语音变速**：不改变音调地加速/减速
- **丢包隐藏**：插值补偿丢失包

### 三种处理模式
1. **正常播放**：缓冲适中，按原始速率播放
2. **加速**：缓冲过大，1.1x~1.2x播放（WSOLA算法）
3. **减速**：可能欠缓冲，0.8x~0.9x播放（时间拉伸）

### WSOLA 变速原理
```
Speech: |----|++++|----|++++|----|++++|
                          ↓ 加速
Speech: |----|++++|++++|----|++++|++++|
           ↑ 取一段 → 上一个位置重叠
```

## 实时视频处理

### 视频增强链路
```
摄像头采集 → 降噪 → 对比度 → 锐化 → 编码
                              
    ML增强 → 超分辨率 → 美颜 → 背景替换
```

### 常用技术
1. **3D降噪**：时域 + 空域联合降噪
2. **自动曝光**：基于人脸检测调整曝光
3. **美颜**：皮肤平滑 + 肤色调整 + 瘦脸
4. **背景模糊/替换**：人像分割模型

## 唇同步

### 同步要求
- ITU-T G.114 推荐：音频领先视频 < 90ms，音频落后 < 185ms
- 观众在视频领先/落后 200ms 以上开始感知不自然

### 同步策略
1. **时间戳对齐**：采集时打绝对时间戳
2. **缓冲对齐**：为视频添加适当的延迟等待音频
3. **动态调整**：根据RTT动态调整视频延迟

## 总结
- 实时音频处理链：AEC → ANS → AGC → NetEQ
- 降噪从传统频谱减法进化到DNN（RNNoise/DCCRN）
- NetEQ的核心是WSOLA语音变速 + 丢包隐藏
- 视频处理链从基础降噪到ML美颜，计算量持续增长
- 唇同步依赖严格的时间戳管理和延迟对齐
