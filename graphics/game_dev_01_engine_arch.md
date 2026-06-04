# 第1课：游戏引擎架构 — ECS、游戏循环、场景图、组件系统与资源管理

## 1. 课程概述

游戏引擎是游戏开发的基石。本课从架构层面剖析现代游戏引擎的核心模块，重点讲解 **实体组件系统（ECS）**、**游戏循环（Game Loop）**、**场景图（Scene Graph）**、**组件系统**和**资源管理**。理解这些概念后，你将能看懂 Unity、Unreal、Godot 等引擎的设计哲学，并具备自己搭建轻量级引擎的能力。

## 2. 游戏循环（Game Loop）

游戏循环是引擎的心脏。每一帧都经历"输入→更新→渲染"三个核心阶段。

### 2.1 固定时间步长 vs 可变时间步长

**可变时间步长（Variable Timestep）**：
```cpp
// 最简单的方式：每帧 delta 不一致
while (running) {
    float dt = getDeltaTime(); // 上一帧花费了多少秒
    processInput();
    update(dt);
    render();
}
```
- 优点：实现简单
- 缺点：物理模拟不稳定，帧率高时物体"跳帧"

**固定时间步长（Fixed Timestep）**（推荐）：
```cpp
const float FIXED_DT = 1.0f / 60.0f; // 固定 60fps 更新
float accumulator = 0.0f;

while (running) {
    float frameTime = getDeltaTime();
    accumulator += frameTime;
    
    processInput();
    
    while (accumulator >= FIXED_DT) {
        fixedUpdate(FIXED_DT); // 物理、动画等固定步长更新
        accumulator -= FIXED_DT;
    }
    
    float alpha = accumulator / FIXED_DT; // 插值系数
    render(alpha); // 渲染时可做插值
}
```
- 核心思想：物理/逻辑更新使用固定步长，渲染使用帧率无关插值
- 这是 Unity `FixedUpdate()` vs `Update()` 的底层实现

### 2.2 各引擎对比

| 特性 | Unity | Unreal Engine | Godot |
|------|-------|---------------|-------|
| 脚本 Update | MonoBehaviour.Update() | Tick() | _process(delta) |
| 固定更新 | FixedUpdate() | - | _physics_process(delta) |
| 内部循环 | Mono/.NET IL2CPP | C++ 原生 | GDScript/C++ |
| 多线程更新 | Job System + Burst | TaskGraph | Thread Pool |

## 3. 实体组件系统（ECS）

ECS 是当代游戏引擎最具影响力的架构模式，替代了传统的深层次继承体系。

### 3.1 传统 OOP 的问题

```cpp
// 继承深坑：当我们需要"可飞行的狗"时？
class Entity { /* ... */ };
class Animal : public Entity { /* ... */ };
class Dog : public Animal { /* ... */ };
class FlyingDog : public Dog { /* ❌ 菱形继承 */ };
```
继承层次越深，代码复用越难，组合才是答案。

### 3.2 ECS 三要素

```cpp
// 1. Entity —— 只是一个 ID
using Entity = uint32_t;

// 2. Component —— 纯数据
struct Transform { float x, y, z; float rot; };
struct Velocity  { float vx, vy, vz; };
struct Renderable { Mesh* mesh; Material* mat; };
struct Health    { int hp; int maxHp; };
struct PlayerTag { }; // 标记组件，无数据

// 3. System —— 处理逻辑（无状态）
class MovementSystem : public System {
    void update(Registry& reg, float dt) override {
        reg.view<Transform, Velocity>().each([dt](Transform& t, Velocity& v) {
            t.x += v.vx * dt;
            t.y += v.vy * dt;
        });
    }
};
```

### 3.3 Unity DOTS 与 Unreal Mass

**Unity DOTS (Data-Oriented Tech Stack)**：
- `Entity` = 一个 int（在 Archetype Chunk 中的索引）
- 组件连续存储在 Chunk 中，CPU 缓存友好
- 使用 Burst Compiler 将 C# Job 编译为 SIMD 机器码
- 性能优势：百万级实体轻松 60fps

**Unreal Mass**：
- Unreal 5.1 引入的 ECS 框架
- 不与 GameplayAbilitySystem 冲突，互补存在
- 使用 Fragment（组件）和 Archetype 概念
- 配合 Compute Framework 做大规模人群模拟

### 3.4 手写一个微型 ECS

```rust
// Rust 风格的伪 ECS 核心
struct World {
    entities: Vec<Entity>,
    components: HashMap<TypeId, ComponentStorage>,
}

struct ComponentStorage {
    // 稀疏集（Sparse Set）实现
    sparse: Vec<usize>,  // entity_id -> dense index
    dense: Vec<(Entity, Box<dyn Any>)>,  // 连续存储
}
```
Sparse Set 结构保证了"添加/删除 O(1)"且"遍历时缓存友好"。

## 4. 场景图（Scene Graph）

场景图是组织游戏对象层次结构的树状数据模型。

### 4.1 变换层级

```cpp
struct TransformNode {
    mat4 localMatrix;   // 相对于父节点的变换
    mat4 worldMatrix;   // 世界空间最终矩阵
    
    TransformNode* parent;
    std::vector<TransformNode*> children;
    
    void updateWorldMatrix() {
        if (parent)
            worldMatrix = parent->worldMatrix * localMatrix;
        else
            worldMatrix = localMatrix;
        
        for (auto* child : children)
            child->updateWorldMatrix();  // 自顶向下传播
    }
};
```

### 4.2 包围体层次（BVH）与视锥体裁剪

场景图不仅管理变换，也是空间加速的基础：

| 技术 | 描述 | 使用场景 |
|------|------|----------|
| BSP Tree | 二分空间分割 | Quake 3 室内场景 |
| Octree | 八叉树均匀分割 | 开放世界地形 |
| BVH | 自顶向下包围盒树 | 现代引擎默认选择 |
| Bounding Volume Test | 对每个节点做 Frustum 测试 | 剔除不可见物体 |

```cpp
bool isVisible(const Frustum& frustum, const AABB& bounds) {
    for (int i = 0; i < 6; i++) {
        if (!bounds.intersects(frustum.planes[i])) 
            return false;  // 对任意一个平面在外侧 → 不可见
    }
    return true;
}
```

## 5. 组件系统与资源管理

### 5.1 组件通信方式

| 方式 | 原理 | 性能 | 适用场景 |
|------|------|------|----------|
| 直接引用 | GetComponent<T>() | 最快 | 同实体组件交互 |
| 事件/消息 | EventBus 广播 | 中等 | 解耦系统间通信 |
| Service Locator | 全局单例访问 | 方便但耦合 | 音频/输入管理器 |
| DI容器 | 构造时注入 | 灵活 | 大型项目的架构 |

### 5.2 资源管理生命周期

```
引用计数 → 引用图 → 自动垃圾回收
```

```cpp
class ResourceManager {
    std::unordered_map<std::string, RefCounted<Resource>> cache;
    
    template<typename T>
    Handle<T> load(const std::string& path) {
        auto it = cache.find(path);
        if (it != cache.end()) return it->second;
        
        auto res = std::make_shared<T>();
        res->loadFromFile(path);
        cache[path] = res;
        return res;
    }
    
    void collectGarbage() {
        for (auto it = cache.begin(); it != cache.end(); ) {
            if (it->second.use_count() == 1)  // 仅缓存引用
                it = cache.erase(it);          // 卸载
            else
                ++it;
        }
    }
};
```

### 5.3 AAA 引擎资源管线

| 阶段 | 工具/格式 | 说明 |
|------|-----------|------|
| 源文件 | .fbx/.ma/.psd | 美术原始文件 |
| 导入 | AssetImporter | 参数配置（缩放/归一化/压缩） |
| 构建 | Cooker | 转为平台原生格式 |
| 打包 | AssetBundle/Pak | 按关卡/功能分包 |
| 加载 | Streaming | 异步 + 优先级队列 |
| 卸载 | GC | 引用计数 + 时间阈值 |

**Unity AssetBundle** vs **Unreal Pak**：
- Unity：每个 Bundle 是一个文件，可独立下载，有依赖图
- Unreal：Pak 文件包含多个 Asset，支持层级加密和压缩
- Godot：.pck 文件，支持 ResourcePack 动态加载

## 6. 引擎架构横向对比

| 维度 | Unity | Unreal 5 | Godot 4 | 自研引擎 |
|------|-------|----------|---------|----------|
| ECS | DOTS (可选) | Mass (可选) | 无原生 | 推荐自建 |
| 脚本 | C# | C++ / Blueprint | GDScript / C# | Lua / C# |
| 游戏循环 | 引擎内部封装 | 引擎内部封装 | 引擎内部封装 | 需完全实现 |
| 场景图 | GameObject Transform | Actor RootComponent | Node2D/Node3D | 自定义 |
| 资源管理 | AssetDatabase | AssetRegistry | FileAccess | 自定义 |
| 热重载 | 编辑器下 | C++ 需编译 | GDScript 原生 | Lua 级别 |

## 7. 总结与思考

1. **ECS 优于 OOP 继承**：数据驱动、缓存友好、便于多线程
2. **固定时间步长**是物理正确的唯一选择
3. **场景图 + BVH**是所有空间查询的基础
4. **引用计数的资源管理**简单可靠，适合中小项目
5. **选择引擎 = 选择架构哲学**：Unity 灵活但碎片化、Unreal 完整但重、Godot 轻量但生态小

**实战建议**：用 C++ 或 Rust 手写一个小型 ECS 框架（200 行以内），加上基本的游戏循环和场景图。做完这个练习，你会对任何引擎的底层有通透的理解。

## 8. 代码仓库参考

- [EnTT](https://github.com/skypjack/entt) — C++ 最快 ECS 之一
- [Flecs](https://github.com/SanderMertens/flecs) — 带关系的 ECS
- [Bevy](https://bevyengine.org/) — Rust ECS 引擎
- Unity DOTS 官方示例
- Unreal 5 Mass 框架 (UE5.1+)
