# CRDT 实践学习笔记

## 项目概述
纯 Python 实现 CRDT（Conflict-Free Replicated Data Types）无冲突复制数据类型库，零外部依赖。

## 实现的数据类型

### 1. 辅助类
- **Dot**: (node_id, seq) 对，唯一标识一个版本
- **Clock**: 向量时钟，支持 tick/merge/compare/dots

### 2. GCounter (Grow-Only Counter)
- 每节点独立槽位，merge 取 max
- 只能增长，不能减少

### 3. PNCounter (Positive-Negative Counter)
- 两个 GCounter: P(增) + N(减)
- value = P.value() - N.value()
- 支持真正的增减

### 4. GSet (Grow-Only Set)
- 只增不删的集合
- merge = 集合并集

### 5. TwoPhaseSet (2P-Set)
- add_set + remove_set 两个 GSet
- 元素存在条件: in add_set AND not in remove_set
- 已移除元素不可再加（限制很强）

### 6. LWWReg (Last-Writer-Wins Register)
- 基于时间戳，取最新值
- 简单但会丢失并发写入信息

### 7. MVReg (Multi-Value Register)
- 保留所有并发版本
- 使用 dot store 跟踪因果历史
- write() 用 clock 做上下文，prune 被覆盖的版本

### 8. ORSet (Observed-Remove Set)
- 最实用的 CRDT Set
- 每个元素关联唯一 tag (Dot)
- add() 生成新 tag；remove() 把该元素所有 tag 移入 tombstone
- 解决了 2P-Set 不可再加的问题
- merge: 并集 tags + 并集 tombstone

### 9. ORMap (Observed-Remove Map)
- ORSet-like 的键管理
- 每个键关联任意 CRDT 值
- merge 时相同键调用底层 CRDT 的 merge

## 踩过的坑

### 1. MVReg 序列化：dict 不能做 dict key
- 问题：`{dot.to_state(): val}` — dot.to_state() 返回 dict，但 dict 不可 hash
- 修复：改用 `[{'dot': ..., 'value': ...}, ...]` 数组形式

### 2. ORMap remove() 清空 tag 信息
- 问题：remove() 中 `self._tags.pop(key)` 导致 merge 后 tombstone 无法对应到 key
- 修复：remove 只 `del self._tags[key]`；merge 时也从 other._tags 中合并

### 3. ORMap tag 全局唯一性
- 问题：不同 ORMap 实例的 tag 可能碰撞（都从 seq=0 开始），导致一个对象的 tag 被另一个的 tombstone 意外埋掉
- 修复：merge tombstone 时排除当前实例已有 tags（local tags 优先）

### 4. 序列化中的 key 类型
- 非字符串 key（如 int）在 to_state() 中要转 str(key)，from_state() 要 `json.loads()` 恢复

## 关键设计决策

### 序列化
- `to_state()` → JSON 可序列化 dict
- `from_state(state)` → 类方法重建对象
- 所有 CRDT 类型都实现（ORMap 还要保存 inner CRDT 的类型信息）

### State-based vs Op-based
- 全部使用 state-based（每次 merge 传递完整状态）
- 优点：幂等、容错性好
- 缺点：状态可能很大

## 测试
43 个测试全部通过，覆盖：
- 基本操作
- 合并
- 并发
- 幂等性
- 序列化往返
- 3 节点收敛
- 边界条件（空 CRDT）
