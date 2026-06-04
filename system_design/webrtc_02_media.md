# WebRTC 第2课：媒体处理 — 音视频编解码

## 1. 媒体流基础

MediaStream 是 WebRTC 的媒体载体：

```
MediaStream
  ├── AudioTrack       ← 麦克风 / 系统音频
  └── VideoTrack       ← 摄像头 / 屏幕共享 / 视频文件
```

## 2. 音频编解码

### Opus（WebRTC 默认）

| 特性 | 值 |
|------|-----|
| 类型 | 有损、混合语音+音乐编解码器 |
| 比特率 | 6~510 kbps（WebRTC 默认 32 kbps） |
| 采样率 | 8kHz ~ 48kHz |
| 帧长 | 2.5ms ~ 60ms |
| 延迟 | 26.5ms（最低配置） |
| 特性 | FEC（前向纠错）、PLC（丢包隐藏） |

**Opus 为什么适合 WebRTC**：
- 动态比特率：网络差时自动降码率
- FEC 内建：丢包率 20% 时仍可听懂
- 超低延迟：比 AAC 低 10 倍

### 音频处理管线

```
麦克风 → AGC(自动增益) → NS(降噪) → AEC(回声消除) → Opus编码 → DTLS-SRTP加密 → 网络
```

### 回声消除（AEC）

```python
# 概念：AEC 的原理
# 1. 远端信号 → 本地扬声器播放
# 2. 麦克风收到：本地声音 + 远端回声 + 环境噪声
# 3. AEC 用扬声器的参考信号 + 自适应滤波器 → 消除回声
#
#      远端信号 ──→ [扬声器]     ❌ 不想要的回声
#                        ↓
#      麦克风 ──→ [     ] ←── 远端信号(参考)
#                        ↓
#               [自适应滤波器] → error → 更新系数
#                        ↓
#                  净信号输出
```

## 3. 视频编解码

### VP8（基本保障）

| 特性 | 值 |
|------|-----|
| 类型 | 有损视频编解码器（On2 技术）|
| 特点 | 强制支持（所有浏览器都有） |
| 延迟 | 低（帧内预测简单） |
| 质量 | 中（不如 H.264/VP9） |

### VP9（谷歌推荐）

| 特性 | 值 |
|------|-----|
| 压缩率 | 比 VP8 高 30-50% |
| 计算开销 | 比 VP8 高 2-3 倍（编码端） |
| 延迟 | 中 |
| 支持 | Chrome/Firefox |

### H.264（Safari/硬件加速）

| 特性 | 值 |
|------|-----|
| 特点 | 硬件编码器支持（移动端省电最佳） |
| 延迟 | 低 |
| 支持 | Safari/iOS/Android |

### 编码器选择策略

```python
def pick_best_codec(platform, hardware_encoder):
    if platform == 'iOS' or hardware_encoder:
        return 'H264'  # 硬件加速，省电
    elif platform == 'Chrome' and not mobile:
        return 'VP9'   # 画质优先
    else:
        return 'VP8'   # 兼容性保障
```

## 4. Simulcast（分层编码）

**同一流编码多个不同分辨率的版本**，接收端选择最适合自己的：

```
发送端:
  720p (码率高) ─→ 桌面端（大屏，好网络）
  480p (码率中) ─→ 平板（中屏，中网络）
  180p (码率低) ─→ 手机（小屏，移动网络）
```

**Simulcast VS SVC**：

| 特性 | Simulcast | SVC（可分层编码） |
|------|-----------|-------------------|
| 方式 | 独立编码多个流 | 一个流带多层 |
| 带宽 | 3 个流 = 3 倍编码开销 | 1 个流 = 1 倍 |
| 灵活性 | 随意组合 | 依赖层结构 |
| 支持 | VP8/VP9/H264 | 只有 VP9 完整支持 |

## 5. 自适应码率（ABR — Adaptive Bitrate）

WebRTC 内置拥塞控制，根据网络状况自动调整视频质量：

```
┌─────────────┐   丢包率/延迟/RTT    ┌─────────────┐
│ 发送端编码器 │←───────────────────│ 接收端探测  │
│              │                    │             │
│  VP8 500kbps────[网络变差]─────→  │ 丢包 15%   │
│              │                    │             │
│  VP8 300kbps←────────────────────│ 带宽降了   │
└─────────────┘                    └─────────────┘
```

Google 的 GCC（Google Congestion Control）算法：
- 基于延迟的探测（Trendline Estimator）
- 基于丢包的调整
- **目标**：最小化延迟，最大化吞吐量

## 6. 媒体协商优先级

```python
# 偏好顺序（音频）
preferred_audio = ['opus', 'red', 'pcmu']

# 偏好顺序（视频）
preferred_video = ['VP8', 'H264', 'VP9']

# 使用优先级选择
def negotiate_codecs(local_capabilities, remote_capabilities, preferred):
    """选择双方都支持且优先级最高的编解码器"""
    for codec in preferred:
        if codec in local_capabilities and codec in remote_capabilities:
            return codec
    return None  # 理论上不会发生
```

---

**下一篇**: Data Channel — 数据通道
