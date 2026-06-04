# 游戏开发 — 路线图

## 8课全景

| 课时 | 主题 | 核心内容 |
|:----:|------|----------|
| 1 | 引擎架构 | ECS/GameLoop/场景图/组件/资源管理 |
| 2 | 物理引擎 | 碰撞检测(AABB/GJK)/刚体/约束求解 |
| 3 | 渲染管线 | 前向/延迟/TBDR/PBR/Bloom/SSAO |
| 4 | 动画与AI | 骨骼动画/NavMesh/A*/行为树/FSM |
| 5 | 网络同步 | 帧同步/状态同步/GGPO/匹配 |
| 6 | Unity vs Unreal | C# vs C++蓝图/材质/烘焙/ECS |
| 7 | 性能优化 | DrawCall/LOD/纹理流送/Instancing |
| 8 | 音频与特效 | FMOD/Wwise/粒子系统/VFX/TimeLine |

## 引擎选择参考

| 选择 | 适合 | 语言 | 学习路径 |
|------|------|------|---------|
| Unity | 移动+独立游戏 | C# | 官方入门→Code Monkey |
| Unreal | 3A主机+PC游戏 | C++/蓝图 | Epic官方教程 |
| Godot | 开源+2D游戏 | GDScript/C# | 社区文档 |

## 进阶方向

### 渲染工程师
- Vulkan/DirectX 12 API
- 实时全局光照（RTGI/SVOGI）
- 程序化生成（Houdini Engine）

### 游戏玩法AI
- GOAP + HTN 规划器
- 机器学习在游戏中的应用
- 大语言模型对话NPC

### 后端架构
- PlayFab/GameLift 服务端
- 分布式匹配和房间
- 反作弊+数据验证

## 学习建议
- 先玩一个引擎熟悉基础
- 用小型项目（坦克大战/Mario）验证每一步
- Profile是优化唯一可信的来源
