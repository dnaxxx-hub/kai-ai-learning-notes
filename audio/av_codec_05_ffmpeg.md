# 第5课：FFmpeg 深度 — libavformat、libavcodec、libavfilter、滤镜图、硬件加速

## 1. 概述

FFmpeg 是音视频处理领域的事实标准工具和库。它不是一个单一的应用程序，而是一个**完整的多媒体处理框架**，由多个库组成：

```
FFmpeg 核心库架构:

         ┌─────────────┐
         │  ffmpeg CLI │ ← 命令行接口
         ├─────────────┤
         │  ffplay     │ ← 播放器
         ├─────────────┤
         │  ffprobe    │ ← 媒体信息分析
         ├─────────────┤
         │  ffserver   │ ← 流媒体服务器（已废弃）
         └──────┬──────┘
                │ 依赖
      ┌─────────┼──────────┐
      │         │          │
┌─────▼──┐ ┌───▼───┐ ┌───▼───┐
│libavcodec│ │libavformat│ │libavutil │ ← 核心库
│(编解码)  │ │(封装格式) │ │(工具)    │
└─┬──┬──┬─┘ └───┬───┘ └───┬───┘
  │  │  │        │          │
┌─▼──▼──▼─┐ ┌───▼───┐ ┌───▼───┐
│libavfilter│ │libavdevice│ │libswscale│
│(滤镜处理) │ │(设备输入) │ │(图像缩放)│
└──────────┘ └─────────┘ └─────────┘
  │
┌─▼────────┐ ┌───────────┐
│libswresample │libpostproc│
│(音频重采样)  │(后期处理)  │
└────────────┘ └───────────┘
```

本课将深入每个核心库的实现原理和工程实践。

---

## 2. libavformat — 封装格式引擎

### 2.1 架构设计

libavformat 负责**容器的读写（multiplexer / demultiplexer）**，它在 FFmpeg 中表现为 **AVFormatContext**：

```
┌───────────────── AVFormatContext ─────────────────┐
│                                                     │
│  iformat (AVInputFormat) ← 输入格式（如 MP4 解封）   │
│  oformat (AVOutputFormat) ← 输出格式（如 FLV 封装）  │
│                                                     │
│  nb_streams: 2 (一条视频 + 一条音频)                 │
│  ┌─────────────┐   ┌─────────────┐                │
│  │ streams[0]  │   │ streams[1]  │                │
│  │ AVStream    │   │ AVStream    │                │
│  │ type: video │   │ type: audio │                │
│  │ codecpar:   │   │ codecpar:   │                │
│  │  h264       │   │  aac        │                │
│  │  w:1920     │   │  44100Hz    │                │
│  │  h:1080     │   │  2ch        │                │
│  └──────┬──────┘   └──────┬──────┘                │
│         │                 │                         │
│  ┌──────▼──────┐   ┌──────▼──────┐                │
│  │ packets     │   │ packets     │                │
│  │ AVPacket[]  │   │ AVPacket[]  │                │
│  └─────────────┘   └─────────────┘                │
└─────────────────────────────────────────────────────┘
```

### 2.2 解封装流程（Demuxer）

```
读取 MP4 文件的内部流程:

1. avformat_open_input()
   读取 ftyp box → 确认文件类型
   读取 moov box → 解析所有轨道元数据
   构建 AVStream[] 数组
   
2. avformat_find_stream_info()
   解码少量帧以获取精确信息（如 帧率、关键帧位置）
   填充 codecpar 中的编解码参数

3. av_read_frame() 循环
   从 mdat box 读取一个 AVPacket
   自动解析帧边界（不跨帧读取）
   AVPacket.pts / dts → 时间戳
   AVPacket.stream_index → 属于哪个轨道

4. avformat_close_input()
   释放资源
```

### 2.3 封装流程（Muxer）

```
写入 MP4 文件的内部流程:

1. avformat_write_header()
   分配 moov box 占位
   写入 ftyp box

2. av_interleaved_write_frame()
   接收编码后的 AVPacket
   交错写入 mdat（音视频帧交错排列）
   自动管理 pts/dts 排序

3. av_write_trailer()
   回到文件开头 → 填充 moov box（含每帧的偏移索引）
   写入 stbl（Sample Table）等关键索引表
   
   典型问题: moov box 在文件末尾 → 需要"moov 前置"（FastStart）
   ffmpeg -movflags faststart  → 将 moov 移到文件开头 → 网络播放秒开
```

### 2.4 支持的协议

libavformat 支持通过 URL 前缀访问各种协议：

```
file://      本地文件（默认）
http://       HTTP 拉流
https://      HTTPS
rtmp://       RTMP 推流/拉流
rtsp://       RTSP 拉流
udp://        UDP 裸流
tcp://        TCP 流
srt://        SRT 协议
pipe:         stdin/stdout 管道
```

---

## 3. libavcodec — 编解码引擎

### 3.1 AVCodecContext

编解码的核心数据结构，保存所有编码参数：

```
┌─────────────── AVCodecContext ───────────────┐
│                                                 │
│  codec_id: AV_CODEC_ID_H264                     │
│  codec_type: AVMEDIA_TYPE_VIDEO                 │
│                                                 │
│  ── 分辨率相关 ──                                │
│  width: 1920, height: 1080                      │
│  coded_width/height: 1920/1088 (16对齐)          │
│  pix_fmt: AV_PIX_FMT_YUV420P                    │
│                                                 │
│  ── 码率控制 ──                                  │
│  bit_rate: 4000000 (4 Mbps)                     │
│  rc_crf: 23 (CRF 模式)                          │
│  rc_max_rate / rc_buffer_size                    │
│                                                 │
│  ── GOP 结构 ──                                  │
│  gop_size: 12 (I帧间隔 12 帧)                     │
│  keyint_min: 1                                   │
│  max_b_frames: 2 (B帧数量)                       │
│                                                 │
│  ── 编码工具 ──                                  │
│  profile: FF_PROFILE_H264_HIGH                   │
│  level: 41 (Level 4.1, 1080p @ 30fps)           │
│  refs: 3 (参考帧数量)                             │
│  me_method: ME_HEX (六边形搜索)                   │
│                                                 │
│  ── 线程 ──                                      │
│  thread_count: 4                                 │
│  thread_type: FF_THREAD_SLICE (Slice级并行)      │
└─────────────────────────────────────────────────────┘
```

### 3.2 解码流程

```
AVPacket (压缩数据) → AVFrame (原始帧)

                    ┌──────────┐
                    │ AVPacket │  ← 压缩的 H.264 数据
                    └─────┬────┘
                          │
          avcodec_send_packet() → 送入解码器
                          │
                    ┌─────▼────┐
                    │  解码器   │
                    │ (硬件/软件)│
                    └─────┬────┘
                          │
          avcodec_receive_frame() → 取出解码帧
                          │
                    ┌─────▼────┐
                    │ AVFrame  │  ← YUV 原始数据
                    │   ├─ data[0] → Y 平面
                    │   ├─ data[1] → U 平面
                    │   └─ data[2] → V 平面
                    │   linesize[0] → 行宽
                    │   pts → 显示时间戳
                    └──────────┘
```

### 3.3 编码流程

```
AVFrame (原始帧) → AVPacket (压缩数据)

┌──────────┐     ┌──────────────┐
│ AVFrame  │     │ 选择 GOP 结构│
│ (原始YUV) │ ──→│ I/P/B 帧安排 │
└──────────┘     └──────┬───────┘
                        ↓
                  ┌─────────────┐
                  │ 编码器       │
                  │ (x264/x265) │
                  └──────┬──────┘
                         ↓
                   ┌──────────┐
                   │ AVPacket │ → 写入文件或传输
                   │ (H.264)  │
                   └──────────┘
```

### 3.4 编码器：x264 参数详解

```
ffmpeg -i input.mp4 -c:v libx264 \
  -preset slow          ← 编码速度预设（ultrafast→placebo）
  -crf 23               ← 恒定质量（0-51，默认23）
  -profile:v high       ← 编码档次（baseline/main/high）
  -level 4.1            ← 级别（决定分辨率和帧率上限）
  -x264-params "keyint=250:min-keyint=25:bframes=3" \
  -pix_fmt yuv420p      ← 像素格式
  output.mp4

常见预设对比:
  ultrafast → 极快但体积大 (≈ 2× CRF 目标码率)
  veryfast  → 快速，适合直播
  medium    → 默认平衡
  slow      → 慢但体积小 (≈ 20% 码率节省)
  placebo   → 极慢，收益微小 (仅多 1-2%)
```

### 3.5 支持的编解码器数量

FFmpeg 支持超过 **400 种编解码器**（libavcodec 是最大的开源编解码库）：

```
视频解码:  H.264, H.265, VP9, AV1, MPEG-2/4, VC-1, VP8, DV, ...
视频编码:  H.264 (x264), H.265 (x265), VP9 (libvpx),
          AV1 (libaom, SVT-AV1), MPEG-4, ...

音频解码:  AAC, MP3, Opus, Vorbis, FLAC, PCM, AC3, ...
音频编码:  AAC (fdk_aac), MP3 (libmp3lame), Opus (libopus),
          FLAC, ALAC, ...

字幕:    SRT, ASS, VTT, PGS, ...
图像:    JPEG, PNG, WebP, GIF, ...
```

---

## 4. libavfilter — 滤镜引擎

### 4.1 滤镜图（Filter Graph）

FFmpeg 的滤镜系统使用**有向无环图（DAG）**描述处理流程：

```
简单滤镜图:
[输入0] → 滤镜A → 滤镜B → [输出]

复杂滤镜图（多输入多输出）:
                        ┌─────────┐
[输入0:视频] ──────────→│ 缩放     │
                        └────┬────┘
                             ↓
                        ┌─────────┐
[输入1:覆盖图] ─────────→│ 叠加    │─→ [输出]
                        └─────────┘

更复杂的图:
              ╔═══╤═══╤═══╤═══╤═══╗
              ║帧率├─┤  │   │   ║
   ┌──────────╢转换│去隔行│缩放│叠加║──────────┐
   │          ║   │   ├─┤   ├─┤   │          │
   │          ╚═══╧═══╧═══╧═══╧═══╝          │
   │                                           │
┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐    ┌──▼──┐
│输入 │→│解码 │→│滤镜图│→│编码 │→│封装 │───→│输出 │
└─────┘ └─────┘ └─────┘ └─────┘ └─────┘    └─────┘
```

### 4.2 常见滤镜

```
视频滤镜:
  scale=1280:720          缩放分辨率
  fps=30                  帧率转换
  crop=640:480:100:100    裁剪
  rotate=45               旋转
  hflip                   水平翻转
  vflip                   垂直翻转
  eq=brightness=0.1       亮度调整
  eq=contrast=1.5         对比度调整
  negate                  反色
  edgedetect              边缘检测
  drawtext=text='Hello'   文字叠加
  overlay=x=10:y=10       图片/视频覆盖
  hwupload_cuda           上传到 GPU（硬件加速）
  yadif                   去隔行
  mcdeint                 运动补偿去隔行

音频滤镜:
  volume=2.0             音量加倍
  equalizer=f=1000:t=q:w=1:g=10  10dB 峰值 EQ
  pan=stereo|c0=c0|c1=c1  声道映射
  aresample=48000        重采样
  atempo=2.0             变速不变调
  adelay=1000|1000       延迟
  amix=inputs=2          混音
  anullsrc                静音发生器
```

### 4.3 滤镜图实例

```
实际命令: 添加水印 + 缩放 + 调整音量

ffmpeg -i input.mp4 -i logo.png \
  -filter_complex "                                 \
    [0:v]scale=1920:1080[scaled];                   \
    [1:v]scale=200:-1[logo_scaled];                 \
    [scaled][logo_scaled]overlay=W-w-10:10[out_v];  \
    [0:a]volume=1.5[out_a]"                         \
  -map "[out_v]" -map "[out_a]" output.mp4

滤镜图:
  [0:v]──→scale──→[scaled]──┐
                             ├→[scaled+logo]──→overlay──→[out_v]
  [1:v]──→scale──→[logo]───┘  ↑
                                    位置: W-w-10, 10
  [0:a]─────────────────────────→volume──→[out_a]
```

### 4.4 滤镜的内部实现

```
每个滤镜的抽象接口（AVFilter）:

┌──────────── AVFilter ────────────┐
│                                    │
│  name: "scale"                     │
│  description: "Scale the input..." │
│                                    │
│  inputs: AVFilterPad[]              │
│  outputs: AVFilterPad[]             │
│                                    │
│  init()      ← 初始化上下文         │
│  query_formats()  ← 支持的像素格式  │
│  config_props() ← 配置输入/输出属性 │
│  filter_frame() ← 核心处理函数     │
│  uninit()    ← 清理                │
└────────────────────────────────────┘

滤镜链的处理方式:
  Filter A → filter_frame() → 输出 AVFrame
                              ↓
  Filter B → filter_frame() → 输出 AVFrame
                              ↓
  Filter C → filter_frame() → 输出 AVFrame
```

---

## 5. 硬件加速编码/解码

### 5.1 主流硬件加速方案

| API | 厂商 | 平台 | 特点 |
|-----|------|------|------|
| **NVENC/NVDEC** | NVIDIA | Windows/Linux | 生态最好，质量高 |
| **VAAPI** | Intel/AMD | Linux | 开源标准 |
| **QSV** | Intel | Windows/Linux | 集成显卡加速 |
| **AMF** | AMD | Windows | AMD 硬件加速 |
| **VideoToolbox** | Apple | macOS | Apple Silicon 支持 |
| **MediaCodec** | MediaTek/高通 | Android | 移动端 |
| **Vulkan Video** | 多厂商 | 多平台 | 新一代标准 |

### 5.2 FFmpeg 硬件加速流程

```
硬件解码 (H.264 → GPU 内保持 NV12):
ffmpeg -hwaccel cuda -i input.mp4 -c:v h264_cuvid \
       -c:v h264_nvenc output.mp4

硬件转码 (全 GPU 流水线):
ffmpeg -hwaccel cuda -hwaccel_output_format cuda \
       -i input.mp4 \
       -c:v h264_nvenc -preset p4 -tune hq \
       output.mp4

硬件加速滤镜图:
ffmpeg -hwaccel cuda -i input.mp4 \
       -vf "hwupload_cuda,scale_cuda=1280:720,hwdownload" \
       -c:v libx264 output.mp4

  GPU 内存 ←    GPU 处理    → CPU 内存
  ─────────    ─────────        ────────
  hwupload →  scale_cuda   →  hwdownload
```

### 5.3 NVENC 编码器质量对比

```
NVENC (Turing+) vs x264 (same bitrate):

                x264 veryslow    NVENC p7    NVENC p1
编码速度:          1×              5×          50×
质量(PSNR):      基准            -1dB         -3dB
码率效率:         基准            +10%         +25%

结论:
  - NVENC p7 (最高质量) ≈ x264 medium 水平
  - NVENC 适合直播（实时性要求高）
  - x264 适合离线编码（质量优先）
```

### 5.4 硬件加速的注意事项

```
限制:
1. 帧类型控制受限 — 某些硬件不支持 B 帧
2. 码率控制精度偏低 — VBV 缓冲区管理不如软件灵活
3. 分辨率对齐要求 — 某些硬件要求 16/32 像素对齐
4. 编码器封装限制 — 不能在编码过程中动态改参数
5. 驱动版本依赖 — 新特性需要最新驱动

最佳实践:
  直播 → NVENC/AMF/MediaCodec（速度优先）
  点播 → x265/SVT-AV1（质量优先）
  转码 → 混合方案: 硬解码 + 软件编码
  实时编辑 → 全硬件流水线（零复制）
```

---

## 6. 典型 FFmpeg 命令行实战

### 6.1 流媒体推流

```
推 RTMP 直播流:
ffmpeg -re -i input.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -b:v 2000k -maxrate 2000k -bufsize 1000k \
  -c:a aac -b:a 128k -ar 44100 \
  -f flv rtmp://live.twitch.tv/app/streamkey

推 HLS:
ffmpeg -i input.mp4 \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 128k \
  -hls_time 6 -hls_list_size 0 \
  -hls_segment_filename "segments/%03d.ts" \
  playlist.m3u8
```

### 6.2 屏幕录制

```
Windows (使用 gdigrab):
ffmpeg -f gdigrab -framerate 30 -offset_x 0 -offset_y 0 \
       -video_size 1920x1080 -i desktop \
       -c:v libx264 -preset ultrafast -crf 30 \
       screen.mp4

macOS (使用 avfoundation):
ffmpeg -f avfoundation -i "1:0" -c:v h264_videotoolbox \
       -b:v 5000k screen.mp4

Linux (使用 x11grab):
ffmpeg -f x11grab -r 30 -s 1920x1080 -i :0.0 \
       -c:v libx264 -preset ultrafast -crf 30 \
       screen.mp4
```

---

## 7. 本课小结

| 库 | 功能 | 核心 API |
|------|------|---------|
| libavformat | 封装/解封装 | AVFormatContext, AVStream, AVPacket |
| libavcodec | 编解码 | AVCodecContext, AVFrame, AVCodec |
| libavfilter | 滤镜处理 | AVFilterGraph, AVFilter, AVFilterContext |
| libavutil | 工具函数 | 内存管理、数学运算、数据结构 |
| libswscale | 图像缩放/格式转换 | SwsContext |
| libswresample | 音频重采样 | SwrContext |
| hwaccel (NVENC等) | 硬件加速 | hwupload, hwdownload, scale_cuda |

**下一课预告**：第6课将覆盖音视频的传输层面——流媒体协议栈。从 RTMP 到 HLS/DASH，再到 WebRTC 的信令和 ICE 连通性检查，全面理解低延迟流媒体的架构。

---

*音视频编解码课程 · 第5课*
