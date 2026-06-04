# TinyDB 风格 JSON 文档数据库实战笔记

## 项目概况
- **项目**: TinyDB 风格 JSON 文档数据库
- **目录**: projects/tinydb/
- **代码**: 	inydb.py (120+行) + 	est_tinydb.py (80+行)
- **测试**: 18/18 全绿
- **实现时间**: 2026-05-25 00:00 (约15分钟)

## 核心设计
- **Query DSL**: 声明式查询链，支持 ==, !=, >, <, >=, <=, exists, matches(regex), one_of(list), 	est(func)
- **逻辑组合**: &(and), |(or), ~(not) 运算符重载
- **存储**: JSON文件持久化，写时加锁(threading.Lock)
- **索引**: ensure_index(field) 内存KV加速

## 关键决策
- 基于 dict 的存储模型（非 pickle/二进制）— 可读性好
- 文档自动分配 doc_id
- 写锁而非读写锁 — 简单够用

## D盘同步
- D:\kai_knowledge\projects\tinydb\
- cmd /c copy 在PowerShell中更可靠
