# 数据库内核第8课：迷你DB

> 日期：2026-05-11 | 实践代码：`code/db_kernel_08_minidb.py`

---

## 一、完整 SQL 引擎架构

```
SQL Query
    ↓
Lexer（词法分析器）→ Token 流
    ↓
Parser（语法分析器）→ AST（抽象语法树）
    ↓
Binder（语义绑定器）→ 校验表/列存在性
    ↓
Executor（执行器）→ 调用存储引擎
    ↓
Storage（存储引擎）→ 实际读写数据
```

### 各阶段职责

| 阶段 | 输入 | 输出 | 功能 |
|------|------|------|------|
| Lexer | SQL 字符串 | Token 序列 | 分词：'SELECT', '*', 'FROM', 'users' |
| Parser | Token 序列 | AST 树 | 按语法规则构建语法树 |
| Binder | AST 树 | 绑定的 AST | 检查表/列是否存在，解析类型 |
| Executor | 绑定的 AST | 结果集 | 调用存储层执行操作 |
| Storage | 读写请求 | 数据 | 内存表/文件管理 |

---

## 二、Parser 实现（递归下降）

### Grammer 规则（简化）

```
stmt        → select_stmt | insert_stmt | create_stmt | delete_stmt
select_stmt → SELECT [DISTINCT] columns FROM table [WHERE cond]
              [ORDER BY col [ASC|DESC]] [LIMIT n]
insert_stmt → INSERT INTO table [(cols)] VALUES (vals)
create_stmt → CREATE TABLE table (col_defs)
delete_stmt → DELETE FROM table [WHERE cond]
```

### 解析策略
- **递归下降**：每个非终结符对应一个函数
- **预读一个 Token**（LL(1)）：根据当前 Token 决定走哪个分支
- **错误处理**：尽早失败，提供清晰错误信息

---

## 三、Storage 设计

### 数据模型

```
Table {
    columns: [(name, type), ...]  ← schema 定义
    rows: [{col: val, ...}, ...]  ← 数据行
}
```

### 支持的存储操作

| 操作 | 实现 | 复杂度 |
|------|------|--------|
| CREATE TABLE | 创建 schema | O(1) |
| INSERT | 追加一行 | O(1) |
| SELECT | 全表扫描 + 过滤 | O(n) |
| WHERE | 逐行谓词评估 | O(n) |
| ORDER BY | 排序 | O(n log n) |
| LIMIT | 截断 | O(1) |
| DISTINCT | Set 去重 | O(n) |
| DELETE | 过滤 + 重建 | O(n) |

---

## 四、Binder 语义检查

Binder 在 Parser 之后执行，负责：
1. **表存在性**：FROM 中的表是否存在
2. **列存在性**：INSERT/SELECT 的列是否在 schema 中
3. **类型检查**：值类型是否与列类型匹配
4. **权限检查**：是否可读/写（未实现）

---

## 五、Executor 执行

执行器采用 **Volcano 模型**的简化版：
1. 接收绑定的 AST
2. 转换为对 Storage 的调用
3. 格式化输出

### 执行计划示例

```
SELECT name, age FROM users WHERE age > 28 ORDER BY age ASC
→ Storage.select("users", cols=["name","age"], 
                  where=("age", ">", 28),
                  order_by=[("age", "ASC")])
```

---

## 六、MiniDB 测试

```python
# 建表
CREATE TABLE users (id INT, name VARCHAR, age INT, city VARCHAR)

# 插入
INSERT INTO users VALUES (1, 'Alice', 30, 'Beijing')

# 查询
SELECT name, age FROM users WHERE age > 28 ORDER BY age ASC

# 去重
SELECT DISTINCT city FROM users

# 删除
DELETE FROM users WHERE id = 5
```

### 聚合函数扩展（支持 GROUP BY 的基础）

| 函数 | 含义 |
|------|------|
| COUNT(*) | 行数统计 |
| SUM(col) | 列求和 |
| AVG(col) | 列平均 |
| MIN(col) | 列最小值 |
| MAX(col) | 列最大值 |

---

## 七、从 MiniDB 到生产级 DB 的差距

| 特性 | MiniDB | 生产级（PostgreSQL） |
|------|--------|---------------------|
| 存储 | 内存数组 | Buffer Pool + B+ Tree |
| 持久化 | 无 | WAL + Checkpoint + fsync |
| 索引 | 无（全表扫描） | B+ Tree / Hash / GiST |
| 事务 | 无 | MVCC + 2PL |
| 并发 | 无 | 多版本 + 行锁 |
| 优化 | 无 | CBO + RBO + 统计信息 |
| 网络 | 无 | Libpq / pgwire |
| 安全 | 无 | RBAC + SSL + 审计 |

---

## 八、实践代码

`db_kernel_08_minidb.py` 包含：

| 模块 | 行数 | 功能 |
|------|------|------|
| `Lexer` | ~70 | SQL 词法分析 |
| `Parser` | ~180 | 递归下降语法分析 |
| `Binder` | ~50 | 语义绑定 |
| `MiniStorage` | ~120 | 内存存储引擎 |
| `MiniDB` | ~60 | 完整引擎入口 |
| `Aggregator` | ~30 | 聚合函数 |

### 支持 SQL

```sql
CREATE TABLE, INSERT, SELECT, DELETE
WHERE, ORDER BY, LIMIT, DISTINCT
```

### 运行

```bash
python code/db_kernel_08_minidb.py
```
