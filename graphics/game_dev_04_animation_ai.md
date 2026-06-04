# 第4课：动画与 AI — 骨骼动画、混合树、状态机、NavMesh、A*、行为树

## 1. 课程概述

动画和 AI 是游戏"活起来"的关键。本课覆盖**骨骼动画系统**、**混合树与状态机**、**NavMesh 导航网格**、**A\* 寻路算法**以及**行为树与 FSM**。这些系统一起构成了"角色如何动、如何想"的完整技术栈。

## 2. 骨骼动画（Skeletal Animation）

### 2.1 骨骼层级

```
骨骼 = 树的层级结构
  根骨骼 (Hips)
    ├── Spine (脊柱)
    │   ├── Neck (脖子)
    │   │   └── Head (头)
    ├── LeftArm (左臂)
    │   ├── LeftForeArm (左前臂)
    │   ├── LeftHand (左手)
    │   │   ├── Thumb (拇指)
    │   │   └── ...
    └── RightArm (右臂) — 同理
```

每根骨骼都有一个 **逆绑定矩阵（Inverse Bind Matrix）**：
```cpp
struct Bone {
    std::string name;
    int parentIndex;        // -1 表示根骨骼
    mat4 localTransform;    // 相对于父骨骼的变换
    mat4 inverseBindMatrix; // 从模型空间到骨骼空间的变换（恒量，加载后不变）
};
```

### 2.2 蒙皮（Skinning）

```glsl
// 顶点着色器 — GPU Skinning
layout(location = 0) in vec3 inPosition;
layout(location = 5) in ivec4 inBoneIndices;  // 影响该顶点的骨骼索引
layout(location = 6) in vec4 inBoneWeights;    // 骨骼权重 (sum=1.0)

uniform mat4 boneMatrices[MAX_BONES];  // 每帧更新的骨骼矩阵数组

void main() {
    // 骨骼矩阵 = 骨骼动画矩阵 × 逆绑定矩阵
    mat4 skinMatrix = inBoneWeights.x * boneMatrices[inBoneIndices.x] +
                      inBoneWeights.y * boneMatrices[inBoneIndices.y] +
                      inBoneWeights.z * boneMatrices[inBoneIndices.z] +
                      inBoneWeights.w * boneMatrices[inBoneIndices.w];
    
    vec4 worldPos = modelMatrix * skinMatrix * vec4(inPosition, 1.0);
    gl_Position = projection * view * worldPos;
}
```

### 2.3 引擎对比

| 引擎 | 骨骼数量上限 | 蒙皮方式 | BlendShape | 压缩格式 |
|------|-------------|---------|-----------|---------|
| Unity | 256/Shader | GPU Skinning (默认) | 支持 | Animation Clip |
| Unreal | 256 | GPU Skinning | Morph Target | 压缩 Transform |
| Godot | 128 | CPU 或 GPU | 支持 | 内建 Track |
| 优化建议 | 不超过 128 | 移动端优先 GPU | 常用来做面部 | Float16 压缩 |

## 3. 动画混合 — Blend Tree & State Machine

### 3.1 线性插值混合（LERP Blend）

```cpp
// 两个动画之间的线性混合
AnimationClip interpolate(AnimationClip& a, AnimationClip& b, float t) {
    AnimationClip result = a;
    for (int bone = 0; bone < numBones; bone++) {
        // 平移分量
        result.positions[bone] = lerp(a.positions[bone], b.positions[bone], t);
        // 旋转分量（四元数球面插值）
        result.rotations[bone] = slerp(a.rotations[bone], b.rotations[bone], t);
        // 缩放
        result.scales[bone] = lerp(a.scales[bone], b.scales[bone], t);
    }
    return result;
}
```

### 3.2 Blend Tree（2D 混合）

典型用例：基于运动速度混合 Idle ↔ Walk ↔ Run：

```
               Run (speed=6.0)
              ↗
    Walk (speed=3.0)     ← 横轴：速度
  ↗
Idle (speed=0.0)
```

Unreal 和 Unity 都支持 1D/2D Freeform Blend Tree：
- **1D Blend**：一个参数控制（速度）
- **2D Simple Directional**：方向 + 速度
- **2D Freeform Cartesian**：任意两个参数

### 3.3 动画状态机（Animation State Machine）

```cpp
class AnimStateMachine {
    struct State {
        std::string name;
        AnimationClip* clip;
        float speed;
        bool loop;
    };
    
    struct Transition {
        State* from;
        State* to;
        float blendDuration;   // 过渡时间
        std::function<bool()> condition;  // 条件函数
    };
    
    State* currentState;
    float transitionTimer = -1.0f;
    State* targetState = nullptr;
    
    void update(float dt) {
        if (transitionTimer >= 0) {
            transitionTimer += dt;
            float t = min(transitionTimer / blendDuration, 1.0f);
            // 混合两个状态
            blendAnimations(currentState, targetState, t);
            
            if (t >= 1.0f) {
                currentState = targetState;
                transitionTimer = -1.0f;
            }
        } else {
            currentState->clip->advance(dt * currentState->speed);
        }
    }
    
    void triggerTransition(const std::string& stateName) {
        for (auto& t : transitions) {
            if (t.from == currentState && 
                t.to->name == stateName && 
                t.condition()) {
                targetState = t.to;
                transitionTimer = 0.0f;
                break;
            }
        }
    }
};
```

### 3.4 引擎动画系统对比

| 特性 | Unity Mechanim | Unreal AnimBP | Godot AnimationTree |
|------|---------------|---------------|-------------------|
| 状态机 | ✓ 图形化 | ✓ EventGraph | ✓ 节点式 |
| Blend Tree | 1D/2D Freeform | BlendSpace 1D/2D | Blend2/3/4 Node |
| IK Pass | OnAnimatorIK | Control Rig | SkeletonIK |
| Root Motion | ✓ | ✓ | 手动 |
| 性能 | 中等 | 高（C++） | 中 |

## 4. 导航网格（NavMesh）与 A\* 寻路

### 4.1 NavMesh 生成

NavMesh 将场景的地面转换为多边形网格，用于 AI 寻路：

```
生成流程：
1. 体素化（Voxelization）— 场景几何体转体素
2. 区域分类（Region Classification）— 识别可行走区域
3. 轮廓提取（Contour Extraction）— 体素 → 多边形轮廓
4. 多边形网格（Polygon Mesh）— 轮廓 → 凸多边形
5. 高度细节（Height Detail）— 添加高度信息
```

### 4.2 A\* 寻路算法

```python
def a_star(start, goal, navmesh):
    open_set = PriorityQueue()
    open_set.put(start, 0)
    
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    
    while not open_set.empty():
        current = open_set.get()
        
        if current == goal:
            return reconstruct_path(came_from, current)
        
        for neighbor in navmesh.neighbors(current):
            # g 值 = 已经走过的路径长度
            tentative_g = g_score[current] + distance(current, neighbor)
            
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                # f = g + h (启发式)
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                open_set.put(neighbor, f_score[neighbor])
    
    return None  # 无路径

def heuristic(a, b):
    # 欧几里得距离（可采纳的启发函数）
    return sqrt((a.x - b.x)**2 + (a.z - b.z)**2)
```

### 4.3 A\* 优化技巧

| 技术 | 说明 | 加速比 |
|------|------|--------|
| Binary Heap | 最小堆管理 Open Set | O(n) → O(log n) |
| Jump Point Search | 跳点搜索（grid 地图） | 10×-100× |
| Hierarchical A\* | 分层寻路 | 10×-50× |
| Precomputed Paths | 预计算常用路径 | 0ms 查询 |
| Funnel Algorithm | 路径平滑（String Pulling） | 转弯处理 |

### 4.4 NavMesh 引擎对比

| 引擎 | 寻路库 | 动态障碍 | 分层 | 跳跃/下降 |
|------|--------|---------|------|----------|
| Unity | NavMesh + NavMeshAgent | ✓ (Obstacle) | NavMeshLink | ✓ |
| Unreal | AI Navigation / NavData | ✓ | RecastNavMesh | ✓ |
| Godot | NavigationServer3D | ✓ | RVO Avoidance | 手动 |
| 第三方 | Recast/Detour | C++ 原生 | Tiled NavMesh | ✓ |

## 5. 行为树（Behavior Tree）与 FSM

### 5.1 FSM（有限状态机）

```cpp
// 简单但容易膨胀
enum State { IDLE, PATROL, CHASE, ATTACK };

class EnemyFSM {
    State currentState;
    
    void update(float dt) {
        switch (currentState) {
            case IDLE:
                // 巡逻模式
                if (detectPlayer()) currentState = CHASE;
                break;
            case CHASE:
                moveToward(player);
                if (inAttackRange())  currentState = ATTACK;
                if (lostPlayer())     currentState = PATROL;
                break;
            case ATTACK:
                performAttack();
                if (outOfRange()) currentState = CHASE;
                break;
        }
    }
};
```

FSM 问题：状态爆炸。每加一个状态，所有其他状态的转换逻辑都需要修改。

### 5.2 行为树（Behavior Tree）— 替代方案

行为树由 **节点** 组成：
- **Composite**：Sequence（序列）、Selector（选择器）、Parallel（并行）
- **Decorator**：反转、重复、超时、Cooldown
- **Action**：具体行为（移动、攻击、等待）
- **Condition**：条件判断

```
Selector (选择 — 选第一个成功的子节点)
├── Sequence (尝试追击)
│   ├── Condition: PlayerInSight?
│   ├── Action: MoveTo(player.position)
│   └── Action: Attack()
└── Sequence (巡逻)
    ├── Action: PatrolMove()
    └── Condition: Arrived?
        └── Action: Wait(3s)
```

```cpp
// 行为树节点基类
enum class Status { SUCCESS, FAILURE, RUNNING };

class BTNode {
public:
    virtual Status tick(Blackboard& bb, float dt) = 0;
    virtual ~BTNode() = default;
};

class Sequence : public BTNode {
    std::vector<BTNode*> children;
public:
    Status tick(Blackboard& bb, float dt) override {
        for (auto* child : children) {
            Status s = child->tick(bb, dt);
            if (s != SUCCESS) return s;  // 任一失败 = 整个失败
        }
        return SUCCESS;
    }
};

class Selector : public BTNode {
    std::vector<BTNode*> children;
public:
    Status tick(Blackboard& bb, float dt) override {
        for (auto* child : children) {
            Status s = child->tick(bb, dt);
            if (s != FAILURE) return s;  // 任一成功 = 整个成功
        }
        return FAILURE;
    }
};
```

### 5.3 黑板的角色（Blackboard）

行为树通过 **Blackboard** 共享数据：
```
Blackboard:
  playerPosition: Vector3
  health: 45
  ammo: 12
  lastKnownPlayerPos: Vector3
  alertLevel: 0.7
```

### 5.4 FSM vs 行为树

| 维度 | FSM | Behavior Tree |
|------|-----|---------------|
| 可扩展性 | 状态N关系N² | 模块化组合 |
| 可视化 | 状态图（容易画） | 树状（更易理解） |
| 运行时调试 | 难（当前状态唯一） | 易（看到是哪条路径失败）|
| 性能 | 极快 | 稍慢（遍历树）|
| 重用 | 低 | 高（子树可作为模块）|
| 游戏使用 | 简单敌人/UI | 复杂AI（HALO, F.E.A.R.）|

## 6. AI 系统集成

```
场景数据 → NavMesh → A* 寻路 → 路径平滑 → Steering → 角色移动
                                     ↘
行为树/FSM ← 感知系统(视觉/听觉) ← 世界状态
  ↓
PlayAnimation(攻击/移动动作)
```

### 6.1 引擎 AI 系统对比

| 引擎 | 导航 | 寻路 | 行为逻辑 | 感知系统 |
|------|------|------|---------|---------|
| Unity | NavMesh | A* | Animator(有限) / 第三方 | Trigger/Collider |
| Unreal | NavMesh | A*/EQS | BehaviorTree | AIPerception |
| Godot | Navigation | A* | 自定义 | Area3D |
| 推荐方案 | Recast/Detour | 自己实现 | BehaviorTree.CPP | 自定义 |

## 7. 总结与实战建议

1. **GPU Skinning**是现代游戏的标准蒙皮方案
2. **Blend Tree**解决"平滑过渡"，**State Machine**解决"何时切换"
3. **A\* + NavMesh**是最可靠的游戏寻路方案组合
4. **行为树优于 FSM** — 模块化、易调试、可扩展
5. **Blackboard**是行为树的状态中枢

**实战练习**：
1. 在 Unity 中用 NavMeshAgent 实现敌人 AI，加上 FSM
2. 用 Unreal Behavior Tree 实现巡逻→追击→攻击的 AI 流程
3. 下载 Recast/Detour，在自定义引擎中跑通 NavMesh 生成
4. 手写一个 A\* 并在 Grid 地图上验证

> 推荐资源：  
> - 《Programming Game AI by Example》— Mat Buckland  
> - Recast/Detour: github.com/recastnavigation  
> - Unreal Engine AI官方文档 | Unity AI Navigation Package
