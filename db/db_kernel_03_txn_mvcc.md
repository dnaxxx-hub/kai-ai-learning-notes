# 数据库内核第3课：事务与MVCC

> 日期：2026-05-11 | 实践代码：`code/db_kernel_03_txn_mvcc.py`

---

## 一、ACID 理论

### 1.1 定义

| 特性 | 含义 | 实现机制 |
|------|------|----------|
| **原子性 (Atomicity)** | 全部成功或全部失败 | Undo Log / WAL |
| **一致性 (Consistency)** | 事务前后数据满足约束 | 应用层 + 数据库约束 + 触发器 |
| **隔离性 (Isolation)** | 并发事务互不干扰 | MVCC / 锁 |
| **持久性 (Durability)** | 提交后永不丢失 | Redo Log + WAL |

### 1.2 事务状态机

```
Active → Partially Committed → Committed
   ↓                              ↓
  Failed → Aborted
```

---

## 二、MVCC 核心原理

### 2.1 版本链

每行数据维护一个版本链，每个版本记录创建/删除它的**事务ID**：

```
头节点（最新版本）
  ├─ create_xid = 105
  ├─ delete_xid = NULL
  ├─ data = {name: "Alice", age: 31}
  └─ next → ───────────────────────┐
                                    ↓
旧版本 1                         版本 2（被T3标记删除）
  ├─ create_xid = 100              ├─ create_xid = 100
  ├─ delete_xid = 105              ├─ delete_xid = 102
  └─ data = {name: "Alice", age: 30}
```

### 2.2 可见性规则

事务 txn 看版本 v：
1. **v.create_xid == txn.txn_id**：自己创建的，可见 ✅
2. **v.create_xid 已提交 且 不在 txn 快照中**：可见 ✅
3. **v.create_xid 未提交 或 在快照中**：不可见 ❌
4. v 有 delete_xid：反向应用上述规则

### 2.3 快照（Snapshot）

事务开始时获取的"活跃事务ID集合"：
```
snapshot = {T1, T5, T7}  -- T1, T5, T7 在 T10 开始时还在运行
```

- T10 看不到 T1/T5/T7 的修改（它们"还没发生"）
- T10 能看到 T2/T3/T4 的修改（它们"已经发生了"）

---

## 三、隔离级别

### 3.1 四种隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 实现方式 |
|----------|------|-----------|------|----------|
| READ UNCOMMITTED | ❌ | ❌ | ❌ | 读不加锁，写加锁 |
| READ COMMITTED | ✅ | ❌ | ❌ | 语句级快照 |
| REPEATABLE READ | ✅ | ✅ | ❌ | 事务级快照（MySQL InnoDB） |
| SERIALIZABLE | ✅ | ✅ | ✅ | 全局加锁 / SSI |

### 3.2 并发问题

**脏读**：读到未提交的数据
```
T1: UPDATE balance=200
T2: SELECT balance → 200（脏读！）
T1: ROLLBACK（balance 实际上还是 100）
```

**不可重复读**：同一事务两次读到不同值
```
T1: SELECT age → 30
T2: UPDATE age=31
T1: SELECT age → 31（不可重复读！）
```

**幻读**：同一查询条件返回不同行数
```
T1: SELECT * WHERE age>30 → 5 rows
T2: INSERT new row WHERE age=35
T1: SELECT * WHERE age>30 → 6 rows（幻读！）
```

**丢失更新**：两个事务同时写同一行
```
T1: SELECT counter=10
T2: SELECT counter=10
T1: UPDATE counter=15 (10+5)
T2: UPDATE counter=20 (10+10) ← 覆盖了 T1 的修改！
```

---

## 四、MVCC vs 2PL

| 对比维度 | MVCC（多版本并发控制） | 2PL（两阶段锁） |
|----------|----------------------|-----------------|
| 读不阻塞写 | ✅ 是（快照读） | ❌ 否 |
| 写不阻塞读 | ✅ 是 | ❌ 否 |
| 存储开销 | 高（多版本） | 低 |
| 实现复杂度 | 高 | 中 |
| 适用场景 | 读多写少 | 写冲突频繁 |
| 典型数据库 | PostgreSQL, MySQL InnoDB | 传统数据库 |

---

## 五、实践代码

`db_kernel_03_txn_mvcc.py` 包含：

| 模块 | 内容 |
|------|------|
| `MVCCStore` | 完整 MVCC 实现：版本链/可见性检查/快照读 |
| `TxnManager` | 事务ID分配/活跃事务管理 |
| `IsolationLevel` | 四种隔离级别模拟 |
| `test_mvcc()` | 版本链测试 |
| `demo_isolation_levels()` | 脏读/丢失更新/幻读演示 |

### 运行

```bash
python code/db_kernel_03_txn_mvcc.py
```
