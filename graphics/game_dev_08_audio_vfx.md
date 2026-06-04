# 音频与特效系统

> 游戏开发第8课 — 音频中间件、粒子系统和后处理特效

## 游戏音频系统

### 音频架构

```
游戏逻辑 → Audio Interface → Audio Engine
                                  ├── 2D/3D空间化
                                  ├── 卷积混响
                                  ├── 动态混音
                                  └── 输出设备
```

### 音频类型

| 类型 | 特点 | 示例 |
|------|------|------|
| SFX（音效） | 简短、触发式 | 射击/跳跃/拾取 |
| BGM（背景音乐） | 循环、长片段 | 场景音乐 |
| Voice（语音） | 线性、对话 | NPC对话 |
| Ambience（环境） | 循环、低频 | 风声/雨声 |

## FMOD 中间件

### 核心概念
- **Event**：音频的顶层抽象，一个Event包含多个声音片段
- **Parameter**：控制音频行为的参数（速度、高度、情绪等）
- **Bus**：音频路由总线（Master→Music/SFX/Voice子总线）
- **Bank**：音频资源包，打包音频文件+元数据

### 编程接口

```cpp
// FMOD Studio API 示例
void PlayFootstep(FMOD::Studio::EventInstance* footstep, SurfaceType surface) {
    // 设置参数（不同的地面材质播放不同的音效）
    footstep->setParameterByName("Surface", (float)surface);
    
    // 设置3D位置
    FMOD_3D_ATTRIBUTES attrs;
    attrs.position = playerPosition;
    attrs.velocity = playerVelocity;
    attrs.forward  = playerForward;
    attrs.up       = playerUp;
    footstep->set3DAttributes(&attrs);
    
    // 播放
    footstep->start();
}
```

### 动态混音
```
Master Bus (0dB)
├── Music Bus (-6dB)
│   ├── Combat Music Layer
│   └── Exploration Music Layer
├── SFX Bus (0dB)
│   ├── Weapon SFX
│   ├── Footstep Bus (compressed)
│   └── UI SFX
└── Voice Bus (-3dB)
    └── Dialogue
```

## Wwise 中间件

### 特色功能
1. **SoundBank 管理**：分场景加载/卸载
2. **Interactive Music**：根据游戏状态动态切换音乐片段
3. **Spatial Audio**：基于几何的空间音频模拟
4. **Audio Bus 路由**：支持Send/Receive/侧链压缩

### 侧链压缩（Ducking）
```
对话开始时 → 背景音乐音量自动降低
对话结束 → 背景音乐音量还原
```

### Wwise vs FMOD 对比

| 特性 | FMOD | Wwise |
|------|------|-------|
| 定价 | 免费（50万营收以下） | 按项目收费 |
| 学习曲线 | 较平缓 | 较陡峭 |
| 编辑工具 | FMOD Studio | Wwise Authoring |
| 音效能力 | 强 | 更强（更多内置效果器） |
| 内存占用 | 较小 | 较大 |
| 主机支持 | 完整 | 完整 |

## 粒子系统

### 粒子生命周期

```
Emit → Initialize → Update → Render → Die

每帧：
1. 发射新粒子（Spawn）
2. 更新已有粒子（Update）
3. 剔除死亡粒子（Kill）
4. 渲染存活粒子（Render）
```

### 粒子数据结构

```cpp
struct Particle {
    // 初始化时设置（只读）
    float lifetime;      // 总寿命
    float startSize;
    Color startColor;
    
    // 每帧更新（读写）
    float age;           // 当前年龄
    float3 position;     // 世界位置
    float3 velocity;     // 速度
    float rotation;
    Color currentColor;
    float currentSize;
};

struct ParticleSystem {
    std::vector<Particle> particles;
    
    // 每粒子属性
    EmissionShape shape;     // 发射形状（锥体/球体/盒体）
    Burst[] bursts;         // 突发发射配置
    AnimationCurve sizeOverLifetime;
    AnimationCurve colorOverLifetime;
    Gradient colorGradient;
};
```

### 粒子优化

| 优化 | 效果 | 适用 |
|------|------|------|
| GPU Particles | 10万+粒子 | 大量同质粒子 |
| 纹理集/图集 | 减少DrawCall | 多种粒子效果 |
| 粒子剔除 | 视锥剔除 | 大型场景 |
| 固定更新率 | 减少CPU消耗 | 大规模系统 |

### GPU粒子

```hlsl
// 计算着色器更新粒子
[numthreads(64,1,1)]
void UpdateParticles(uint3 id : SV_DispatchThreadID) {
    Particle p = particles[id.x];
    
    // 生命周期检查
    p.age += deltaTime;
    if (p.age >= p.lifetime) {
        particles[id.x].alive = 0;
        return;
    }
    
    // 物理更新
    p.velocity += gravity * deltaTime;
    p.position += p.velocity * deltaTime;
    
    // 属性曲线
    float t = p.age / p.lifetime;
    p.currentSize = lerp(p.startSize, 0.0, t);
    p.currentColor = sampleGradient(colorGradient, t);
    
    particles[id.x] = p;
}
```

## 后处理特效

### 常见后处理链
```
渲染图像 → HDR → ToneMapping → Bloom → SSAO → MotionBlur → AntiAliasing → 输出
```

### 效果详解

| 效果 | 原理 | 性能影响 | 备注 |
|------|------|---------|------|
| **Bloom** | 提取亮部 → 高斯模糊 → 叠加 | 中 | 表现力强 |
| **SSAO** | 采样邻域深度估环境光遮挡 | 中高 | 场景深度信息 |
| **Motion Blur** | 速度缓冲→ 方向模糊 | 中 | 避免过度使用 |
| **DOF** | 高斯模糊分层次 | 高 | 模拟摄影 |
| **Color Grading** | LUT查找表（低开销） | 极低 | 调色必备 |
| **TAA** | Temporal AA | 中 | 抗锯齿+平滑 |
| **AntiAliasing** | SMAA/FXAA/MSAA | 低中 | 移动端用FXAA |

### ToneMapping

```hlsl
// ACES Filmic Tone Mapping（最常用）
float3 AcesToneMap(float3 color) {
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return saturate((color * (a * color + b)) / (color * (c * color + d) + e));
}
```

## Shader Graph / VFX Graph

### Shader Graph
- 可视化Shader编辑器
- 支持PBR/Unlit/自定义着色模型
- Master Stack → Final Color

### VFX Graph
- 处理百万级粒子
- GPU驱动，零CPU开销
- 完全可编程的粒子行为

## Cinemachine

### 核心组件

| 组件 | 功能 |
|------|------|
| Virtual Camera | 虚拟相机，含位置/旋转/视野 |
| CM Freelook | 第三人称自由视角 |
| CM Dolly Cart | 轨道镜头 |
| CM Impulse | 冲击效果（爆炸震动） |
| Noise组件 | 相机抖动 |

### 多层Blend
```
玩家视角 → 过场动画 → 对话特写 → 切回玩家
每层之间可配置Blend曲线（线性/平滑/弹跳）
```

## TimeLine

### 功能
- 序列化编辑：动画/音频/事件/Director
- 过场动画的标准方案
- 支持信号（Signal）触发游戏事件

### 典型流程
```
Timeline
├── [Animation Track] 角色动画
├── [Audio Track]     背景音
├── [Activation Track] 开关UI
└── [Signal Track]    触发游戏逻辑
```

## 总结
- FMOD和Wwise是两个主流音频中间件，Wwise内置效果器更多
- 粒子系统支持CPU和GPU两种模式，GPU粒子适合大规模效果
- 后处理链从HDR到抗锯齿需要平衡性能和效果
- Cinemachine + TimeLine 是游戏内过场动画的标准方案
