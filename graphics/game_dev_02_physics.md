# 第2课：物理引擎 — 碰撞检测、刚体动力学、约束求解与布娃娃

## 1. 课程概述

物理引擎赋予游戏世界"真实感"。本课深入物理引擎的核心机制：**碰撞检测（AABB/OBB/GJK）**、**刚体动力学**、**约束求解**和**布娃娃系统**。我们会对比 Bullet、PhysX、Box2D 和 Jolt 的实现思路，并给出关键算法代码。

## 2. 碰撞检测（Collision Detection）

碰撞检测分为两个阶段：
- **Broad Phase**：粗筛，快速排除不可能碰撞的对
- **Narrow Phase**：精确检测，输出碰撞点/法线/穿透深度

### 2.1 Broad Phase — 粗筛

**Sweep and Prune (SAP)**：
```cpp
struct SweepAndPrune {
    // 对所有物体在三个轴上分别排序
    void sortAxis(Axis axis) {
        std::sort(endpoints[axis].begin(), endpoints[axis].end(),
            [](const Endpoint& a, const Endpoint& b) {
                return a.value < b.value;
            });
    }
    
    void generatePairs() {
        sortAxis(X); sortAxis(Y); sortAxis(Z);
        // 在三个轴上都重叠的 → 潜在碰撞对
        for (auto& pair : overlappingPairs) {
            if (overlapInAllAxes(pair)) {
                narrowPhase(pair);
            }
        }
    }
};
```

**DBVT (Dynamic Bounding Volume Tree)**：
- 使用 AABB 树（类似 BVH，但支持动态更新）
- PhysX 和 Bullet 的默认 BroadPhase
- 每帧对移动物体做 refit，插入/删除 O(log n)

| 技术 | 复杂度 | 适合场景 |
|------|--------|----------|
| SAP | O(n log n) | 物体分布均匀 |
| DBVT | O(n log n) 平均 | 动态物体多 |
| Grid/Uniform | O(n) | 大量静态物体 |
| Sort+Incremental | O(n + m) | 变化小的场景 |

### 2.2 Narrow Phase — 精确碰撞检测

#### AABB vs AABB
```cpp
struct AABB { vec3 min, max; };

bool intersectAABB(const AABB& a, const AABB& b) {
    return (a.min.x <= b.max.x && a.max.x >= b.min.x) &&
           (a.min.y <= b.max.y && a.max.y >= b.min.y) &&
           (a.min.z <= b.max.z && a.max.z >= b.min.z);
}
```

#### OBB vs OBB — 分离轴定理（SAT）
OBB（有朝向的包围盒）检测使用 SAT：
```cpp
// 对 15 个候选轴（3个A轴 + 3个B轴 + 9个边叉积）做投影测试
bool intersectOBB(const OBB& a, const OBB& b) {
    // 两 OBB 的方向轴
    vec3 axesA[3] = { a.right, a.up, a.forward };
    vec3 axesB[3] = { b.right, b.up, b.forward };
    
    // 15 个测试轴
    vec3 testAxes[15];
    for (int i = 0; i < 3; i++) testAxes[i] = axesA[i];
    for (int i = 0; i < 3; i++) testAxes[3+i] = axesB[i];
    // ... + 9 个边叉积
    
    for (auto& axis : testAxes) {
        if (axis.length() < EPSILON) continue;
        if (!overlapOnAxis(a, b, axis.normalized()))
            return false;  // 找到分离轴 → 不相交
    }
    return true;  // 所有轴都重叠 → 相交
}
```

#### GJK — Gilbert–Johnson–Keerthi 算法
GJK 是凸体碰撞检测的事实标准，用于任意凸形状（球体、胶囊体、凸包网格）。

核心思想：**如果两个凸体不相交，它们之间存在一个分离轴；GJK 通过迭代构建 Minkowski 差集的 Simplex 来判定**。

```python
# Python 伪代码
def gjk(collider_a, collider_b):
    # Minkowski 差：A ⊖ B = {a - b | a∈A, b∈B}
    # 原点在差集内 ↔ 两个凸体相交
    simplex = []  # 最多 4 个点（3D 中的四面体）
    direction = (collider_b.center - collider_a.center).normalized()
    
    simplex.append(support(collider_a, collider_b, direction))
    direction = -direction  # 朝原点方向搜索
    
    for _ in range(MAX_ITERATIONS):
        p = support(collider_a, collider_b, direction)
        if dot(p, direction) < 0:
            return False  # 原点不在 Minkowski 差中
        simplex.append(p)
        
        if containsOrigin(simplex, direction):
            return True  # 碰撞！
    
    return False

def support(a, b, direction):
    # 找到 a 在 direction 方向的最远点 - b 在反方向的最远点
    return a.farthestPoint(direction) - b.farthestPoint(-direction)
```

**EPA (Expanding Polytope Algorithm)**：在 GJK 确认碰撞后，EPA 计算出穿透深度和碰撞法线。

### 2.3 各引擎碰撞检测对比

| 特性 | PhysX | Bullet | Jolt | Box2D |
|------|-------|--------|------|-------|
| BroadPhase | DBVT + SAP | DBVT | Grid + SAP | Dynamic Tree |
| NarrowPhase | SAT + GJK | GJK + EPA | GJK + EPA | SAT |
| CCD (连续碰撞检测) | 扫掠+子步进 | 子步进 | 子步进 | TOI求解 |
| 网格碰撞 | 三角形网格 | btBvhTriangleMesh | MeshShape | 多边形(2D) |
| 性能 | ★★★★★ | ★★★★ | ★★★★★ | ★★★★ |

## 3. 刚体动力学（Rigid Body Dynamics）

### 3.1 运动方程

```cpp
struct RigidBody {
    // 线动量
    vec3 position;
    vec3 linearVelocity;
    vec3 forceAccum;
    float mass;           // 质量
    float invMass;        // 1/mass（无穷大=静态物体）
    
    // 角动量
    quat orientation;
    vec3 angularVelocity;
    vec3 torqueAccum;
    mat3 invInertiaTensor; // 世界空间的惯性张量逆
};
```

每帧积分：
```cpp
void integrate(RigidBody& body, float dt) {
    if (body.invMass == 0) return; // 静态物体
    
    // 半隐式欧拉（Semi-Implicit Euler）— 最常用的积分器
    body.linearVelocity  += body.forceAccum * body.invMass * dt;
    body.angularVelocity += body.invInertiaTensor * body.torqueAccum * dt;
    
    body.position += body.linearVelocity * dt;
    
    // 角速度 → 四元数更新
    quat omega(0, body.angularVelocity.x * dt,
                  body.angularVelocity.y * dt,
                  body.angularVelocity.z * dt);
    body.orientation = (body.orientation + omega * body.orientation * 0.5f).normalized();
    
    // 清零力累积
    body.forceAccum = vec3(0);
    body.torqueAccum = vec3(0);
}
```

### 3.2 积分器对比

| 方法 | 精度 | 稳定性 | 性能 | 适用 |
|------|------|--------|------|------|
| Explicit Euler | O(h²) | 差 | 最快 | 不推荐 |
| Semi-Implicit Euler | O(h²) | 中等 | 快 | 游戏标准 |
| Runge-Kutta 4 | O(h⁵) | 好 | 中 | 高精度需求 |
| Verlet | O(h³) | 好（能量守恒） | 快 | 粒子/布料 |

## 4. 约束求解（Constraint Solving）

约束是物理引擎中最复杂的部分。它们定义了物体之间的连接方式（关节、弹簧、碰撞接触）。

### 4.1 Sequential Impulse（序列冲量法）

Box2D 作者 Erin Catto 提出的方法，也是 PhysX/Bullet/Jolt 的标准算法：

```cpp
// 核心思想：逐对处理约束，每次施加一个冲量，多次迭代收敛
class ConstraintSolver {
    std::vector<Constraint*> constraints;
    int iterations = 10;  // 典型 4-20 次
    
    void solve(float dt) {
        for (int i = 0; i < iterations; i++) {
            for (auto* c : constraints) {
                // 计算当前约束的速度误差
                float velocityError = c->getVelocityError();
                
                // 计算需要施加的冲量
                float impulse = velocityError / c->getEffectiveMass();
                
                // 应用冲量到关联的刚体
                c->applyImpulse(impulse);
            }
        }
    }
};
```

### 4.2 常见约束类型

| 约束 | 自由度 | 游戏应用 |
|------|--------|----------|
| 点对点（Ball Joint） | 3 旋转自由度 | 链球、绳索 |
| 铰链（Hinge Joint） | 1 旋转自由度 | 门、车轮 |
| 滑动（Slider Joint） | 1 平移自由度 | 电梯、滑轨 |
| 固定（Fixed Joint） | 0 自由度 | 焊接两个物体 |
| 弹簧（Spring） | 柔约束 | 悬挂系统 |

### 4.3 接触约束 — 摩擦与反弹

```cpp
struct ContactConstraint {
    RigidBody* bodyA;
    RigidBody* bodyB;
    vec3 contactPoint;
    vec3 normal;      // 碰撞法线
    float penetration; // 穿透深度
    float restitution; // 弹性系数 (0.0 ~ 1.0)
    float friction;    // 摩擦系数
};
```

**Sequential Impulse for Contacts**:
1. 法线方向：防止穿透（推动物体分离）
2. 切向方向：摩擦力（Coulomb 摩擦模型）
3. Warm Starting：保存上一帧的冲量值，减少迭代次数

## 5. 布娃娃系统（Ragdoll）

### 5.1 构建方法

布娃娃 = 骨骼 + 物理约束的桥接：

```
                            ┌──────────┐
                            │  头部(球关节) │
                            └────┬─────┘
                    ┌───────────┼───────────┐
              ┌────┴────┐            ┌────┴────┐
              │左上臂(球关节)          │右上臂(球关节)
              └────┬────┘            └────┬────┘
              ┌────┴────┐            ┌────┴────┐
              │左前臂(铰链)            │右前臂(铰链)
              └────┬────┘            └────┬────┘
                    │   ┌──────────┐       │
                    └───│ 躯干(根)  │───────┘
                        └────┬─────┘
                    ┌────────┼────────┐
              ┌────┴────┐  ┌────┴────┐
              │左大腿(球关节)│  │右大腿(球关节)
              └────┬────┘  └────┬────┘
              ┌────┴────┐  ┌────┴────┐
              │左小腿(铰链)   │右小腿(铰链)
              └─────────┘  └─────────┘
```

### 5.2 实现要点

```cpp
// 布娃娃系统的主要步骤
void Ragdoll::activate(Bone* skeleton) {
    // 1. 在每个骨骼关节位置创建 RigidBody
    for (auto& bone : skeleton->bones) {
        RigidBody* body = physics->createBody(bone);
        body->setPosition(bone->worldPosition);
        body->setRotation(bone->worldRotation);
        body->setMass(bone->mass);
        
        // 将骨骼的碰撞体（胶囊体）赋予刚体
        body->setCollisionShape(new Capsule(bone->length, bone->radius));
        ragdollBodies.push_back(body);
    }
    
    // 2. 在父子骨骼之间创建约束
    for (int i = 0; i < ragdollBodies.size(); i++) {
        Bone* parent = skeleton->bones[i]->parent;
        if (parent) {
            Constraint* c = physics->createConstraint(
                ragdollBodies[i],        // 子
                ragdollBodies[parent->index], // 父
                ConstraintType::BallJoint,
                parent->worldPosition    // 关节位置
            );
            c->setTwistLimit(-30, 30);  // 角度限制（度）
            c->setSwingLimit(45);
        }
    }
    
    // 3. 将动画骨骼混合到布娃娃姿态
    // 通常使用 0.1-0.3 秒的混合过渡
}
```

### 5.3 引擎对比

| 引擎 | 布娃娃方案 | 特点 |
|------|-----------|------|
| Unity | PhysX Ragdoll | 配置简单，性能一般 |
| Unreal | PhysicalAnimation + Ragdoll | 物理资产系统强大 |
| Havok | 专有方案 | 最早最成熟 |
| 自研 | Jolt/Bullet 集成 | 灵活可控 |

## 6. 物理引擎综合对比

| 维度 | PhysX (Unity/UE默认) | Bullet | Jolt Physics | Box2D (2D) |
|------|----------------------|--------|-------------|------------|
| 开源 | NVIDIA 源码开源 | ✓ (zlib) | ✓ (MIT) | ✓ (zlib) |
| 多线程 | TaskGraph | 手动调度 | 内置JobSystem | 不支持 |
| CCD | 好 | 中等 | 好 | 好 |
| 布料模拟 | PBD | 无 | 无 | 无 |
| 破碎 | 内建 | 需HACD | 无 | 无 |
| 确定性 | 不保证 | 保证 | 保证 | 保证 |
| 游戏使用 | 大量 | 中等 | 最新 AAA (地平线) | 2D 游戏 |

## 7. 总结与实战建议

1. **BroadPhase 选 DBVT**— 通用性最强
2. **GJK + EPA** 是凸体碰撞检测标准
3. **Sequential Impulse** 是约束求解的主流方法
4. **布娃娃** = 骨骼 + 物理约束 + 混合动画
5. **CCD** 对高速物体（子弹、赛车）必不可少

**实战练习**：
1. 用 Python 实现 2D GJK 算法
2. 在 Bullet 或 Jolt 中添加自定义约束
3. 修改 Unreal Ragdoll 的扭矩限制，实现更真实的死亡动画

> 推荐书籍：《Game Physics Engine Development》— Ian Millington  
> 《Physics for Game Developers》— David M. Bourg
