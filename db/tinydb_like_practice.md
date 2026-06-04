# TinyDB-like 纯 Python 简单数据库

## 概述

在 `projects/tinydb_like/` 目录下实现了一个 TinyDB 风格的文档型数据库，零外部依赖，JSON 文件持久化。

## 架构

```
tinydb_like.py
├── QueryCondition      — 单一查询条件（field == value, field > value 等）
├── NotCondition        — 条件否定 ( ~ )
├── CombinedCondition   — 逻辑组合 ( &, | )
├── Field               — 字段对象，重载运算符构建条件
├── Query               — 查询工厂
├── ResultSet           — 查询结果集，支持 .limit(n).offset(n) 链式分页
├── _TableIndex         — 哈希索引，加速等值查询
├── Table               — 数据表（独立于其他表存储）
└── Database            — 数据库入口，支持多表、上下文管理器
```

## 关键设计

### 查询构建器
- 运算符重载实现链式查询：`Query.field('age') == 25`
- 支持：`==`, `!=`, `>`, `>=`, `<`, `<=`, `~` (not)
- 字符串方法：`.contains()`, `.startswith()`, `.endswith()`, `.matches(regex)`
- 逻辑组合：`&` (and), `|` (or)

### 发现的问题与修复

1. **CombinedCondition 嵌套组合** — 初始实现中 `__and__`/`__or__` 将所有条件展平到同一个列表，导致 `(~A & B) | C` 实际变成 `(~A & B & C)`。修复：改为 `CombinedCondition([self, other], 'and')` 正确嵌套。

2. **索引对 NotCondition 的兼容** — `_match_condition_with_index` 只处理 `QueryCondition` 类型，未检查 `NotCondition`。修复：加 `hasattr(condition, 'operator')` 守卫。

3. **ResultSet.__len__ 分页一致性** — `len()` 返回全部文档数而非分页后数量。修复：让 `__len__` 计算分页后的实际长度。

4. **JSON 文件写入编码** — `Add-Content` 默认带 BOM，Python 解析报 `SyntaxError: invalid non-printable character U+FEFF`。改用 Python 的 `open(path, 'w', encoding='utf-8')` 直接写。

5. **write 工具分片限制** — 单次写入 >15KB 可能被截断。使用 Python 脚本作为中间构建工具。

### 功能覆盖

| # | 功能 | 状态 |
|---|------|------|
| 1 | 插入文档 | ✅ |
| 2 | 获取所有文档 | ✅ |
| 3 | 按 id 获取 | ✅ |
| 4 | 等值查询 (==) | ✅ |
| 5 | 比较查询 (>, <, >=, <=) | ✅ |
| 6 | 字符串查询 (contains, startswith, endswith) | ✅ |
| 7 | 逻辑组合 (&, `|`, ~) | ✅ |
| 8 | 更新文档 | ✅ |
| 9 | 删除文档 | ✅ |
| 10 | 多表支持 | ✅ |
| 11 | 索引加速 | ✅ |
| 12 | 批量插入 | ✅ |
| 13 | 持久化（写入磁盘再加载） | ✅ |
| 14 | 正则匹配 | ✅ |
| 15 | 分页 (limit + offset) | ✅ |

共 53 个测试全部通过。
