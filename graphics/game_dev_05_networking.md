# 第5课：网络同步 — 帧同步/状态同步/预测回滚/GGPO/防作弊

## 1. 课程概述

网络同步是多人游戏最复杂的领域。本课覆盖核心同步方案：**帧同步**、**状态同步**、**客户端预测与回滚**、**GGPO 回滚网络**、**ROOM 匹配系统**以及**防作弊策略**。理解这些后，你就能搭建一个可靠的多人游戏网络层。

## 2. 网络同步基础概念

### 2.1 核心挑战

```
玩家 A (北京) → 延迟 40ms → 服务器 (上海) → 延迟 60ms → 玩家 B (东京)
                                                              ↓
                                                      总计 RTT: 200ms
```

三个核心问题：
1. **延迟（Latency）**：200ms RTT 意味着输入延迟半秒
2. **抖动（Jitter）**：网络不稳定导致延迟波动
3. **带宽**：每分钟几 MB 的上传带宽限制

### 2.2 两个关键选择

| 方向 | 选项 | 适用场景 |
|------|------|----------|
| 架构 | P2P vs Client-Server | 小型 vs 大型 |
| 同步 | 状态同步 vs 帧同步 | 实时动作 vs RTS/格斗 |
| 权威 | Authoritative Server | 防作弊 |
| 插值 | Extrapolation vs Interpolation | 预测 vs 平滑 |

## 3. 帧同步（Lockstep / Deterministic Lockstep）

### 3.1 原理

所有客户端运行完全相同的模拟，只同步输入：

```
每帧：播放器输入 → 打包 → 发送给所有对手
确认：收到所有人的输入 → 前进一帧 → 结果完全一样

关键：确定性（Deterministic）— 相同的输入 → 相同的输出
```

### 3.2 实现

```cpp
struct GameInput {
    uint32_t sequence;
    uint8_t  buttons;       // 位掩码: UP, DOWN, LEFT, RIGHT, JUMP, ATTACK
    float    aimAngle;      // 瞄准方向
};

class DeterministicEngine {
    uint32_t currentFrame = 0;
    std::deque<GameInput> inputBuffer;  // 缓冲输入
    
    bool canAdvanceFrame() {
        // 等待所有玩家该帧的输入到达
        for (auto& player : players) {
            if (!player.hasInputForFrame(currentFrame))
                return false;
        }
        return true;
    }
    
    void advanceFrame() {
        // 所有输入就绪 → 前进一帧
        for (auto& input : thisFrameInputs) {
            processInput(input);
        }
        simulatePhysics();  // 确定性物理
        currentFrame++;
    }
    
    PlayerState simulateOneFrame(PlayerState prev, GameInput input) {
        // 必须：无随机、无浮点精度差异
        // 使用定点数或 IEEE-754 严格一致的浮点
        PlayerState next = prev;
        if (input.buttons & UP)    next.velocity.y -= GRAVITY;
        if (input.buttons & LEFT)  next.velocity.x -= MOVE_SPEED;
        // ...
        return next;
    }
};
```

### 3.3 延迟处理 — 帧缓冲

```
玩家输入 → 网络延时 → 缓冲队列 → 累积够所有输入 → 前进一帧

                              ↕
                   如果你的网络比对手快，
                   你也要等对手的输入到达
```

- 每增加一帧缓冲 = +16ms 延迟（60fps）
- 典型格斗游戏：3-4 帧缓冲（50-67ms 基础延迟）

### 3.4 帧同步适用场景

| 游戏类型 | 例子 | 适合帧同步？ |
|---------|------|-------------|
| RTS | StarCraft II | ✅ 经典案例 |
| 格斗 | Street Fighter V | ✅（配合 GGPO）|
| FPS | Call of Duty | ❌ 延迟太大 |
| MOBA | League of Legends | ❌（状态同步为主）|
| 赛车 | Trackmania | ✅ 确定性物理 |

## 4. 状态同步（State Synchronization）

### 4.1 原理

服务器持有权威状态，定期向客户端发送最新状态：

```
每 tick (通常 10-20 次/秒)：
  服务器：计算所有实体状态
  服务器 → 客户端：实体位置、血量、状态变化
  客户端：接收 → 插值平滑显示
```

### 4.2 快照（Snapshot）系统

```cpp
struct Snapshot {
    uint32_t tick;
    struct EntityData {
        uint32_t id;
        vec3 position;
        quat rotation;
        vec3 velocity;
        uint16_t compressedHealth;  // 压缩存储
    };
    std::vector<EntityData> entities;
    
    // 增量压缩：只发送变化的数据
    Delta compressedDiff(Snapshot* base) {
        Delta d;
        for (auto& e : entities) {
            auto* prev = base->findEntity(e.id);
            if (!prev || hasChanged(prev, e)) {
                d.addChangedEntity(e);  // 只发有变化的
            }
        }
        return d;
    }
};
```

### 4.3 客户端插值（Interpolation）

```cpp
// 客户端：在收到的快照之间做线性插值
class InterpolationBuffer {
    struct TimedState {
        float serverTime;
        vec3 position;
    };
    std::deque<TimedState> buffer;
    
    vec3 getInterpolatedState(float renderTime) {
        // 保持 50-100ms 的缓冲来平滑网络抖动
        while (buffer.size() > 2) {
            if (buffer[1].serverTime <= renderTime) {
                buffer.pop_front();  // 扔掉过旧的状态
            } else break;
        }
        
        if (buffer.size() < 2) return buffer.back().position;
        
        // 在两个状态之间插值
        TimedState& t0 = buffer[0];
        TimedState& t1 = buffer[1];
        float alpha = (renderTime - t0.serverTime) / 
                     (t1.serverTime - t0.serverTime);
        return lerp(t0.position, t1.position, clamp(alpha, 0, 1));
    }
};
```

## 5. 客户端预测与回滚（Client Prediction & Rollback）

### 5.1 为什么需要预测？

状态同步下，从按键到看到效果需要：**输入→服务器→模拟→回传→渲染** 即 **RTT 延迟**。
200ms RTT = 异常明显的延迟。**客户端预测**解决了这个问题。

### 5.2 预测 + 回滚

```cpp
class ClientPrediction {
    struct InputCmd {
        int sequence; uint8_t buttons;
    };
    struct WorldState {
        int sequence; vec3 position; vec3 velocity;
    };
    
    // 本地维护的状态
    WorldState predictedState;
    std::vector<InputCmd> pendingInputs; // 未确认的输入
    std::vector<WorldState> history;     // 历史状态快照
    
    void predictMovement(InputCmd input) {
        pendingInputs.push_back(input);
        WorldState prev = predictedState;
        predictedState = advanceSimulation(prev, input);
        history.push_back(predictedState);
    }
    
    void onServerState(WorldState serverState) {
        // 1. 找到服务器确认到哪个序列号
        int confirmedSeq = serverState.lastProcessedInput;
        
        // 2. 丢掉已确认的输入
        while (!pendingInputs.empty() && 
               pendingInputs.front().sequence <= confirmedSeq)
            pendingInputs.pop_front();
        
        // 3. 如果服务器状态和本地预测不同 → 回滚
        if (!isCloseEnough(serverState, predictedState)) {
            predictedState = serverState;  // 回滚到权威状态
            // 4. 重放所有未确认的输入
            for (auto& input : pendingInputs) {
                predictedState = advanceSimulation(predictedState, input);
            }
        }
    }
};
```

## 6. GGPO — 回滚网络（Rollback Networking）

GGPO（Good Game Peace Out）是格斗游戏的网络同步黄金标准。

### 6.1 GGPO 核心思想

```
帧同步 + 预测 + 回滚：
- 不等待对手输入 → 直接预测对手的操作为"保持不动"
- 对手输入到达 → 如果预测错了 → 回滚到那帧重算
- 回滚后 → 视觉上快速过渡回正确状态
```

### 6.2 架构

```cpp
class GGPOSession {
    int localPlayer;
    int frameDelay = 2;  // 本地延迟帧数（给输入到达留时间）
    
    void beginFrame() {
        // 1. 收集本地输入
        GameInput local = readLocalInput();
        
        // 2. 检查对手输入是否已到达
        if (hasRemoteInputForFrame(currentFrame + frameDelay)) {
            // 正常走帧同步
            advanceFrame();
        } else {
            // 3. 对手输入还没到 ↓ 预测
            GameInput predicted = predictInput(opponent);
            savePredictedInput(currentFrame, predicted);
            advanceFrame();
        }
    }
    
    void onRemoteInput(GameInput remote) {
        // 4. 验证预测
        if (hasPredictedInputFor(remote.frame)) {
            GameInput predicted = getPredictedInput(remote.frame);
            if (predicted != remote) {
                // 5. 预测错了！回滚！
                rollbackToFrame(remote.frame);
                applyActualInput(remote.frame, remote);
                reSimulate();
            }
        }
    }
};
```

### 6.3 各游戏网络方案对比

| 游戏 | 方案 | 特点 |
|------|------|------|
| Street Fighter V | GGPO | 回滚网络 |
| League of Legends | 状态同步+预测 | MOBA 标准 |
| Overwatch | 状态同步+强预测 | FPS 流畅感 |
| Valorant | 状态同步+60tick | 高精度FPS |
| CS:GO | 状态同步+Subtick | 亚 tick 精度 |
| 星际争霸2 | 帧同步+延迟 | RTS 确定性 |
| 原神 | 状态同步 | 弱实时要求 |

## 7. ROOM 匹配系统（Matchmaking）

### 7.1 匹配架构

```
玩家 → 匹配服务 → 排序/分组 → 创建 ROOM → ROOM Server
  ↑                    ↓
  └← 返回服务器地址 ←─┘
```

### 7.2 常用方案

| 方案 | 原理 | 适用 |
|------|------|------|
| PlayFab Party | Azure 托管 | Unity 项目 |
| Photon / PUN | 云托管 + 房间列表 | 中小型游戏 |
| Epic Online Services | 免费 + 大厂 | Unreal 项目 |
| 自建 + Agones | K8s + Google 开源 | 大型项目 |
| Steamworks P2P | Valve P2P | PC Steam 游戏 |
| 帧同步专用 | K8s + 自研 | 格斗/RTS |

### 7.3 ROOM Server 生命周期

```
1. 创建 ROOM（Matchmaking 服务分配）
2. 客户端连接（WebSocket / UDP）
3. 玩家加入/退出
4. 游戏进行（状态同步 / 帧同步）
5. 游戏结束 → 上传结果 → 销毁 ROOM
6. 玩家回到大厅
```

## 8. 防作弊（Anti-Cheat）

### 8.1 权威服务器（Authority Server）

**基础原则：客户端不可信**。
- 血量/位置/子弹 → 服务器计算
- 客户端只发送输入，不发送结果

```cpp
// ❌ 错误：客户端说"我打中了敌人"
client.send("DAMAGE", { target: 5, damage: 100 });

// ✅ 正确：客户端说"我开火了"，服务器计算是否命中
client.send("FIRE", { angle, position });
// 服务器验证：子弹路径 → 碰撞检测 → 命中判定
```

### 8.2 常用防作弊手段

| 手段 | 原理 | 绕过难度 |
|------|------|---------|
| Server Authoritative | 服务器裁决 | 无法绕过 |
| 加密通信 | XOR/RC4/TLS | 中等（可逆向）|
| 反篡改 | 完整性校验 | 中等 |
| 反外挂 SDK | EasyAntiCheat/BattlEye | 高 |
| 行为分析 | 检测异常模式 | 高 |
| 回滚验证 | 服务器重算帧 → 对比 | 极高 |

### 8.3 注意点

- **100% 防作弊不存在** — 目标是成本 > 收益
- **反外挂 SDK 的兼容性问题** — 国内 Linux Steam Deck 等
- **重放系统** — 赛后验证比实时更有效

## 9. 引擎网络系统对比

| 引擎 | 内置方案 | 推荐第三方 | 延迟处理 |
|------|---------|-----------|---------|
| Unity | UNET/Netcode | Mirror, Photon, Fish-Net | 状态同步 |
| Unreal | Online Subsystem | EOS | 状态同步+预测 |
| Godot | ENet Multiplayer | Nakama | 状态同步 |
| 自定义 | enet/kcp/websocket | 自定协议 | 定制 |

## 10. 总结与实战建议

1. **帧同步**适合确定性模拟（RTS/格斗）
2. **状态同步**更通用（FPS/MOBA/MMO）
3. **客户端预测**消除感观延迟，**回滚**解决预测错误
4. **GGPO**是格斗游戏的终极方案
5. **权威服务器**防作弊的第一道防线

**实战练习**：
1. 用 Unity Netcode + Relay 做一个 2 人房间对战
2. 在 Unreal 中实现客户端预测 + 服务器回滚
3. 本地搭建 KCP 协议实现 UDP 可靠传输
4. 实现一个简单的 GGPO 测试项目（参考 GGPO.net 开源实现）

> 推荐资源：  
> - GGPO 官方文档: ggpo.net  
> - Gaffer on Games — Glenn Fiedler 的精品博客  
> - 《Multiplayer Game Programming》— Joshua Glazer  
> - Unity Netcode for GameObjects 官方示例
