# 第6课：Unity vs Unreal — C#/蓝图/C++/场景编辑/材质系统/光照烘焙/性能

## 1. 课程概述

Unity 和 Unreal Engine 是当今最重要的两大游戏引擎。本课从技术底层深入比较：**脚本语言（C# vs Blueprint vs C++）**、**场景编辑器**、**材质系统**、**光照烘焙**和**性能表现**。不讲"哪个更好"，而是"什么场景用哪个"。

## 2. 脚本语言对比

### 2.1 Unity C#

```csharp
// Unity C# — 优雅但受限的运行时
public class PlayerController : MonoBehaviour
{
    [SerializeField] private float moveSpeed = 5f;
    [SerializeField] private float jumpForce = 10f;
    private Rigidbody rb;
    private Animator anim;
    
    void Awake() {
        rb = GetComponent<Rigidbody>();
        anim = GetComponent<Animator>();
    }
    
    void Update() {
        HandleInput();
        UpdateAnimation();
    }
    
    void FixedUpdate() {
        // 物理更新 — 固定步长
        MovePlayer();
    }
    
    private void MovePlayer() {
        float h = Input.GetAxis("Horizontal");
        float v = Input.GetAxis("Vertical");
        Vector3 movement = (transform.right * h + transform.forward * v) * moveSpeed;
        rb.velocity = new Vector3(movement.x, rb.velocity.y, movement.z);
    }
}
```

**C# 性能特点**：
- 编译路径：C# → IL → IL2CPP → C++ → 原生码
- IL2CPP 带来 AOT 安全，但泛型展开会膨胀二进制
- Burst Compiler + Job System 可达 C++ 性能（针对数据密集型任务）

### 2.2 Unreal C++

```cpp
// Unreal C++ — 引擎级的宏系统
UCLASS()
class APlayerCharacter : public ACharacter
{
    GENERATED_BODY()
    
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
    float MoveSpeed = 500.0f;
    
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
    float JumpForce = 600.0f;
    
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override
    {
        Input->BindAxis("MoveForward", this, &APlayerCharacter::MoveForward);
        Input->BindAxis("MoveRight", this, &APlayerCharacter::MoveRight);
        Input->BindAction("Jump", IE_Pressed, this, &ACharacter::Jump);
    }
    
    void MoveForward(float Value)
    {
        if (Controller && Value != 0.0f)
        {
            FRotator Rotation = Controller->GetControlRotation();
            FRotator YawRotation(0, Rotation.Yaw, 0);
            FVector Direction = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);
            AddMovementInput(Direction, Value);
        }
    }
};
```

**C++ 特点**：
- UHT（Unreal Header Tool）预处理宏 → 生成反射数据
- 完整的热重载支持（Hot Reload / Live Coding）
- 无需 GC，但需手动管理 UObject 生命周期
- 编译速度慢（大型项目 10-30 分钟全量编译）

### 2.3 Blueprint — 可视化脚本

```
[Input: MoveForward] → [Get Control Rotation] → [Break Rotator]
                                                    ↓
[Input: MoveRight] → [Make Rotator (0, Yaw, 0)] → [Get Unit Axis X]
                                                     ↓
                                  [Add Movement Input (Direction, Value)]
```

**Blueprint 性能**：
- 每个节点是一次函数调用（虚函数分发）
- 大规模 Tick 中 = **卡顿**
- Nativization（UE4/5 已废弃）曾尝试转 C++
- **最佳实践**：复杂逻辑用 C++，配置/AI 用 Blueprint

### 2.4 语言对比总结

| 维度 | Unity C# | Unreal Blueprint | Unreal C++ |
|------|---------|-----------------|-----------|
| 入门难度 | ★★ | ★ | ★★★★ |
| 迭代速度 | ★★★（编辑+编译） | ★★★★★ | ★★ |
| 运行时性能 | ★★★★（Burst下） | ★★ | ★★★★★ |
| 内存管理 | GC（有GC Alloc压力） | 引用计数 | 手动/智能指针 |
| 安全 | IL2CPP AOT | 安全 | 指针危险 |
| 热重载 | 编辑器下 | 实时 | Live Coding |
| 大项目 | 中等 | 不可 | 最佳 |

## 3. 场景编辑器

### 3.1 Unity Scene Editor

**优势**：
- Prefab 嵌套系统（Nested Prefabs） — 从 UE4.20 才跟上
- 快速原型 — 拖入脚本即刻运行
- 场景切换快（LoadScene）

**劣势**：
- 大场景卡顿（Prefab Mode 尤其明显）
- 缺少 UE 的"关卡流式加载"级别的工具

### 3.2 Unreal Level Editor

**优势**：
- **Unreal Editor 就是游戏** — 完整的编辑体验
- World Outliner + Details Panel 组合强大
- **One File Per Actor**：每个 Actor 独立 .uasset
- Sublevel + World Partition：超大开放世界支持

**劣势**：
- 编辑器非常重（启动 2-5 分钟）
- Blueprint 与 C++ 混用易导致依赖混乱

### 3.3 编辑器扩展

| 能力 | Unity | Unreal |
|------|-------|--------|
| 自定义窗口 | EditorWindow (C#) | Slate UI (C++) / Editor Utility Widget |
| 自定义 Inspector | PropertyDrawer | DetailCustomization |
| 场景工具 | Gizmos + Handles | HitProxies + Viewport |
| 菜单扩展 | MenuItem | Toolbar Extender |
| 新手友好 | ★★★★ | ★★ |

## 4. 材质系统

### 4.1 Unity Shader Graph 与 ShaderLab

```hlsl
// Unity URP Shader Graph 导出的 HLSL
half4 UniversalFragmentPBR(InputData inputData, half3 albedo, 
                           half metallic, half smoothness, 
                           half occlusion, half3 emission)
{
    BRDFData brdfData;
    InitializeBRDFData(albedo, metallic, 
                       /* specular */ half3(0,0,0), 
                       /* roughness */ 1 - smoothness, 
                       /* alpha */ 1, brdfData);
    
    half3 color = GlobalIllumination(brdfData, inputData.bakedGI, 
                                    occlusion, inputData.normalWS, 
                                    inputData.viewDirectionWS);
    // ... 逐光源累加
    return half4(color, 1);
}
```

### 4.2 Unreal Material System

Unreal 的材质系统通过**蓝图节点图**编译为 HLSL：

**材质域（Material Domain）**：
- Surface（表面着色器）— 标准 PBR
- Deferred（延迟着色）— 自定义 GBuffer
- Post Process（后处理）— 全屏特效
- Light Function（灯光函数）— 动态灯光图案
- Volume（体积）— 体积雾

**材质层（Material Layers）**：
- 可叠加材质（叠加泥土、血迹、潮湿效果）
- UE5.1+ 的运行时材质层混合

### 4.3 材质系统对比

| 特性 | Unity Shader Graph | Unreal Material Editor | HLSL/GLSL 纯手写 |
|------|-------------------|----------------------|-----------------|
| 节点图 | ✓ | ✓（更强大） | ❌ |
| PBR | Lit / Custom Lit | 默认 | 手动实现 |
| 移动端优化 | URP Baked | 需手动 | 完全控制 |
| 自定义 Pass | FullScreen Pass | Custom Expression | 完全控制 |
| 效率 | 中等（节点化开销） | 较好 | 最优 |
| 调试 | Frame Debugger | Material Stats | RenderDoc |

## 5. 光照烘焙

### 5.1 Unity 光照烘焙

- **Progressive GPU Lightmapper** — 使用 GPU 实时烘焙（快！）
- **Enlighten** — 传统实时 GI（已逐渐淘汰）
- 光照贴图格式：方向性 + 阴影 mask

```csharp
[CreateAssetMenu]
public class LightingSettings : ScriptableObject {
    public int samples = 2048;           // 采样数
    public int bounces = 4;              // 光线反弹次数
    public float texelSize = 0.1f;       // 贴图像素密度
    public LightmapEncoding encoding;    // 普通/HDR/LDR
}
```

### 5.2 Unreal 光照烘焙

- **UDK Swarm** — 分布式烘焙系统
- **Volumetric Lightmap** — 体积光照贴图（支持动态物体接收烘焙光照）
- **Lumen**（UE5）— 实时光追 GI（取代烘焙）

**Lumen vs 烘焙**：

| 维度 | Lumen (实时) | 烘焙光照贴图 |
|------|-------------|-------------|
| 静态光照 | ✓ | ✓（质量更高）|
| 动态物体 | ✓（接收光照） | ❌（需 Light Probe）|
| 改变光源 | ✓ 即时 | ❌ 需重新烘焙 |
| 性能 | 高 GPU 负载 | 0 运行时开销 |
| 质量 | 好 | 极好 |
| 适用 | 开放世界/迭代中 | 固定场景/性能敏感 |

### 5.3 引擎光照烘焙对比

| 特性 | Unity GPU Lightmapper | Unreal Swarm | 自定义烘焙 |
|------|----------------------|-------------|-----------|
| 烘焙速度 | ★★★★（GPU快） | ★★★（CPU多核） | ★★ |
| 质量 | ★★★ | ★★★★★ | ★★★★★ |
| 分布式 | ❌ | ✓（多台机器） | 可加 |
| 体积光 | ❌ | ✓ | 手动 |
| 动态GI | 无 | Lumen | DDGI/RTXGI |

## 6. 性能对比

### 6.1 CPU 性能

| 场景 | Unity | Unreal |
|------|-------|--------|
| 简单场景（100 DrawCall） | 极小 | 略大（框架开销）|
| 中等（1000 DC） | 好 | 好 |
| 复杂（5000+ DC） | 需手动优化 | 自动更好（Instancing）|
| 10000+ 动态物体 | DOTS 可达百万 | Mass 框架 |
| 物理 | PhysX（多线程） | Chaos（新）/ PhysX（旧）|

### 6.2 GPU 性能

| 维度 | Unity URP | Unity HDRP | Unreal 5 |
|------|-----------|------------|----------|
| 渲染路径 | Forward/Deferred | Deferred | Deferred + TSR |
| MSAA | ✓ | 需自定义 | ✓ |
| TAA | 弱 | 中 | TSR（强） |
| Nanite | ❌ | ❌ | ✓ |
| 流明 | ❌ | ❌ | ✓ |

### 6.3 内存与包体

```
Unity (空项目): ~30MB 安装包, 启动 ~200MB RAM
Unreal (空项目): ~200MB 安装包, 启动 ~600MB RAM
```

| 项目 | Unity | Unreal |
|------|-------|--------|
| 空项目安装包 | 30-50 MB | 150-300 MB |
| 中型游戏 | 200-500 MB | 1-5 GB |
| 加载时间 | 快 | 慢 |
| 内存占用 | 较低 | 高 |

## 7. 选型决策树

```
你的项目是什么？
├── 手游/小团队/快速迭代 → Unity
│   ├── 高性能要求 → URP + Burst + DOTS
│   ├── AAA画质 → HDRP
│   └── 2D游戏 → Unity 2D 工具链
├── PC/主机 AAA → Unreal
│   ├── 开放世界 → World Partition + Lumen + Nanite
│   ├── 写实风格 → 默认渲染器
│   └── 非真实感 → 自定义 Shader
├── 横板/像素风 → Godot 或 Unity 2D
└── 需要极致脚本化 → Unreal + Python/Blueprints
```

## 8. 总结

1. **脚本语言**：C# 更快上手，C++ 更极致性能
2. **编辑器**：Unity 更轻量，Unreal 更强大但也更重
3. **材质系统**：Unreal Material 业界最强，Unity Shader Graph 在追赶
4. **光照**：Lumen 是革命性的，但烘焙在固定场景仍是王者
5. **性能**：Unreal 默认更高但代价是包体和内存

**实战建议**：
- 两个引擎都学 — 先攻一个，再学另一个
- 理解**共性概念**（PBR、ECS、延迟渲染）比记引擎 API 更重要
- 小项目用 Unity，大项目或团队专业时考虑 Unreal
- 不要迷信"哪个更好" — 看团队、看项目、看时间

> 推荐资源：
> - Unity Learn 官方课程
> - Unreal 官方学习 (Learn tab in Epic Games Launcher)
> - YouTube: Unreal Sensei, Code Monkey (Unity)
> - 对比阅读:《Unity Game Framework》vs《Unreal Engine C++ The Ultimate Developer's Handbook》
