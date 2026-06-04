# Chord DHT 实战笔记

## 概述
纯 Python 实现 Chord 分布式哈希表协议——结构化的 P2P 存储系统。

## 核心概念

### Chord Ring
- N 个节点分布在 2^m 的标识符环上
- 每个节点维护大小为 m 的 finger 表
- finger[i] = (n + 2^i) mod 2^m 的后继
- 查找时间复杂度 O(log N)

### 关键操作
1. **join**: 新节点通过现有节点找到位置，更新后继/前驱
2. **stabilize**: 定期验证后继关系是否正确
3. **fix_fingers**: 定期刷新 finger 表
4. **find_successor**: 递归查找：先用 closest_preceding_node 跳转，再沿后继链

### 容错机制
- 后继列表：维护 r 个后继节点
- 复制因子：每个 key 存储在 k 个节点上
- 节点失效时通过后继列表跳转

### 数据迁移
- 新节点加入时，从后继迁移应归属的键
- 离开时不需要显式迁移（stabilize 修复）
