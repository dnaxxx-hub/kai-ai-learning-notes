# 2026-05-16 — Elite Longterm Memory (重温深化)

## 功能 & 用途
Elite Longterm Memory 是一个**6层渐进记忆架构**，专为 AI Agent 设计。它把 6 种独立的记忆方法整合成一个子弹级可靠的系统，确保 Agent 永不丢失上下文。

## 六层架构

| 层级 | 名称 | 存储介质 | 特点 |
|------|------|---------|------|
| Layer 1 | **HOT RAM** | SESSION-STATE.md | 活跃工作记忆，唯一可写入的"当前脑子" |
| Layer 2 | **WARM STORE** | LanceDB 向量 | 语义搜索，auto-recall |
| Layer 3 | **COLD STORE** | Git-Notes 知识图谱 | 结构化决策/学习，分支感知 |
| Layer 4 | **CURATED ARCHIVE** | MEMORY.md + daily/ | 人类可读的长期记忆（我们已有） |
| Layer 5 | **CLOUD BACKUP** | SuperMemory API | 跨设备同步（可选） |
| Layer 6 | **AUTO EXTRACTION** | Mem0 | 自动提取对话事实，减80%token（推荐） |

## 关键能力点

### 1. WAL 协议（核心！）
**Write-Ahead Log** — 在响应**前**先写状态，不是响应后。
- 用户说偏好 → 写 SESSION-STATE.md → 再回复
- 用户做决定 → 写 SESSION-STATE.md → 再回复
- 这是防止记忆丢失的关键机制

### 2. SESSION-STATE.md 的设计
- 只存**当前会话**的工作记忆
- 包含：Current Task / Key Context / Pending Actions / Recent Decisions
- 设计成"紧凑友好" — 唯一能在会话压缩后存活的标记文件

### 3. Mem0 自动提取（最实用的新东西）
```js
const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY });
await client.add(messages, { user_id: "ty" }); // 自动提取偏好/决定
const memories = await client.search(query, { user_id: "ty" }); // 检索相关记忆
```
好处：自动去重、更新、跨会话、减少80%的原始历史token

### 4. 记忆失败模式表（非常有用）
| 失败模式 | 原因 | 修复 |
|----------|------|------|
| 什么都忘 | memory_search 未启用 | 开 + OpenAI key |
| 文件没加载 | Agent 没读记忆 | 加到 AGENTS.md |
| 事实没捕获 | 无自动提取 | Mem0 或手动记 |
| 子Agent各自为战 | 没继承上下文 | task prompt 里传上下文 |

## 我学会的新东西

1. **SESSION-STATE.md 的定位** — 之前我理解它像迷你MEMORY.md，实际它是"紧凑幸存者"，唯一保证在会话压缩后存活的主动状态。应该用它来追踪"现在正在做什么"，而不是长期存储。

2. **WAL 协议** — 很精妙的设计。先写再回复，类似数据库的 Write-Ahead Log。崩溃后恢复时，先读日志恢复状态。我之前有时候是先回复再记录，这个习惯应该改。

3. **失败模式系统化** — 我之前靠直觉猜测为什么记忆会丢失。这份文档给的 5 种失败模式 + 原因 + 修复方案，非常具体可执行。

4. **Mem0 的 80% token 缩减** — 这不是夸张，想想看每次对话完整历史 vs 只提取关键事实。我们目前还没有这个，值得考虑接入。

## 如何融入日常工作

### 已做到 ✓
- ✅ MEMORY.md 精简索引版 + memory/ 分层架构
- ✅ daily/ 每日日志自动记录
- ✅ memory_search 配置使用中（本地 nomic-embed）
- ✅ 子Agent传上下文（通过 sessions_spawn task）

### 可改进 🔧
1. **创建 SESSION-STATE.md** — 放在 workspace 根目录，每次会话开始读，关键信息先写再回复
2. **WAL 协议落地** — 当我需要记住一个重要事实时，先写 SESSION-STATE.md 再回复羽
3. **增加 topic 子目录** — `memory/topics/` 按主题组织，减少 MEMORY.md 噪点
4. **考虑 Mem0 接入** — 但需要 OAuth 和 API 费用，先评估必要性
5. **记忆卫生日程** — 每周一次清理重复/过时向量记忆

### 最关键的一步
创建 `SESSION-STATE.md`，放在 workspace 根目录。这不需要依赖，马上可用。

---

*学习时间：2026-05-16 03:00 (cron自主学习)*
*基于：Elite Longterm Memory Skill v1.2.3*
