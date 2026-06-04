# Flexible Database Design v2 — 深入复习笔记

**日期**: 2026-05-12
**技能**: flexible-database-design (🧱)
**版本**: 1.0.0

---

## 回顾 & 新理解

上次学习是 2026-04-30，这次回来发现多了很多实战经验（量化回测/学习笔记/Bitable看板），对数据库的理解更深了。

### 核心心法重新梳理

**1. 「主干硬、尾巴软」—— 终于真正理解了**

之前只是读了概念。现在回头看我的 `system_bridge.py` 总线消息格式，天然就是这种模式：
```
{
  "sender": "xxx",       # 主干
  "type": "xxx",         # 主干  
  "payload": {...},      # 软字段（JSON）
  "timestamp": "xxx",    # 主干
  "priority": 0          # 主干
}
```
系统总线本身就是 flexible database 的设计思想在运行时的体现。

**2. 「先全量保留，再按需提键」**

量化的回测数据也是这样处理的：原始回测结果全量存，需要统计时再提取关键指标（夏普、年化等）到汇总表。

**3. 「分层演进」**

- 原始层 → 我的 `memory/daily/` 原始日志
- 软字段层 → `MEMORY.md` 的精简索引
- 业务视图层 → `memory/INDEX.md` + 各子目录

原来我一直在用这个模式，只是没意识到。

---

## 新发现的闪光点

### 1. 中文全文检索策略的实用性

| 数据量 | 方案 | 适合我？ |
|--------|------|----------|
| <5000 | FTS + LIKE 回退 + 短词拆分 | ✅ 大部分场景 |
| >5000 | Meilisearch / jieba+FTS | 知识库大了再用 |

短词拆分思路很聪明：「煤炭期货价格」→ 「煤炭」「期货」「价格」分别查取并集。这不就是搜索引擎的分词原理简化版。

### 2. 抽取器（Extractors）设计模式

`archive_item.py --llm-extract` 是个优雅的设计：
- 归档时用 LLM 从原文抽结构化数据
- 抽取器可插拔（extractors/ 目录）
- 不同的数据源用不同的抽取器

这对我的知识蒸馏引擎很有启发——distill → extractors 模式完全可复用。

### 3. 反模式清单的价值

**之前踩过的坑**：
- 一上来穷举所有字段 → `orchestrator_v1` 就是，后来重构了
- 所有查询都扫 JSON → 量化指标查得太慢，后来才加索引
- 没有原始层 → 记忆系统最初就是，丢了回溯能力

---

## 如何融入日常工作

### 短期（立刻可用）

1. **知识库归档**：用 flexible_db.py 的三层模型管理学习笔记
   - 原始层：`memory/daily/*.md` （完整日志）
   - 软字段层：`memory/skill_learning/*.md` （结构化笔记）
   - 业务视图层：`memory/INDEX.md` + `MEMORY.md` （精炼索引）
   
2. **量化数据管理**：用软 Schema 替代当前的扁平 CSV 存储
   - 主干：id, timestamp, source, strategy_type
   - JSON: { params, metrics, signals }

### 中期（需要搭建）

3. **Bitable 看板的可选替代**：如果飞书 API 挂了，可以降级到 SQLite flexible db
4. **系统总线消息归档**：`system_bridge.py` 的消息走 flexible db 持久化

### 设计原则迁移

SQLite 的 flexible schema 设计哲学可以迁移到其他场景：
- 接口设计：主干参数必须稳定，扩展参数放 dict/JSON
- 文件结构：主文件 + `extensions/` 目录（类似 extractors/）
- 命令行工具：核心 CLI + `--xxx-extract` 可插拔

---

## 总结

这次重新学习最大的收获不是新知识，而是**发现我一直在用这个模式却不自知**。真正的融会贯通不是读一遍就能做到的，而是用了一段时间后再回头看，发现那些方法论在自己的实践中隐隐浮现。

下一次如果再学这个技能，可以尝试：
1. 实际跑一下 `scripts/` 下的 Python 脚本
2. 用 flexible db 重构一个现有的存储模块
3. 实现一个自定义的 extractor
