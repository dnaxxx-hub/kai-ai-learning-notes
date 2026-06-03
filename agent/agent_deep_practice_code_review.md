# 代码审查多Agent系统 — 深度实战学习笔记

> 日期：2026-05-28
> 项目：`projects/multi_agent_review/`
> 引擎：Python Flow Engine (`skills/python-flow-engine/scripts/pipeline.py`)

---

## 1. 系统架构概览

### 1.1 目标
构建一个基于 Pipeline 引擎的多Agent协作系统，实现代码审查的自动化。4个审查Agent并行执行，1个汇总Agent串行聚合结果。

### 1.2 Agent 角色定义

| Agent | 职责 | 检查项 | 严重度示例 |
|-------|------|--------|-----------|
| **LinterAgent** | 代码风格 | 行长>100、混合缩进、行尾空白、分号结尾、空行过密 | medium/low |
| **TypeSafetyAgent** | 类型安全 | 缺少类型注解、None 比较、可变默认参数、type:ignore | high/medium |
| **SecurityAgent** | 安全漏洞 | eval/exec、os.system、pickle反序列化、SQL注入、硬编码密钥 | critical |
| **PerformanceAgent** | 性能问题 | 嵌套循环(O(n²))、range(len)、.read()无限制、字符串拼接 | high/medium |
| **ReviewAggregator** | 汇总报告 | 收集结果、优先级排序、质量评分、修改建议 | — |

### 1.3 Pipeline 拓扑

```
Linter ←→ TypeSafety ←→ Security ←→ Performance
                                           │
                                           ↓ (>>)
                                     ReviewAggregator
```

所有4个Agent通过 `//`（并行）操作符连接成集群。Aggregator 作为最后一个节点（Performance）的 `>>`（串行）后继。Pipeline 的路由机制保证：

1. 起始节点 LinterAgent 执行 → 写入 context
2. `_route` 检测到并行兄弟 → 启动线程并行执行 TypeSafety/Security/Performance
3. 每个并行节点执行完毕 → 各自的 `_route` 检测到串行后继 → 触发 Aggregator
4. **性能节点最后被触发**（因为它是并行链末端），其 `_route` 触发 Aggregator
5. 此时所有4个Agent结果已在 context 中 → Aggregator 汇总

---

## 2. 关键技术决策

### 2.1 数据传递策略（关键发现）

Pipeline 的 `//` 操作符在路由时，**将当前节点的输出结果作为 data 传递给并行兄弟节点**，而非保持原始输入。

例如：Linter 执行完毕返回 `{"agent": "LinterAgent", "issues": [...], ...}`，当它触发并行兄弟 TypeSafety 时，TypeSafety 收到的 `data` 是 Linter 的输出字典，**不是**原始的 `{"source_code": "...", "filename": "..."}`。

**解决方案**：在 `BaseReviewAgent.__call__` 中实现三级数据读取策略：

```python
if isinstance(data, str):
    code = data  # 纯字符串
elif isinstance(data, dict) and "source_code" in data:
    code = data["source_code"]  # 首节点原始输入
    context["_review_input"] = code  # 缓存到 context
else:
    code = context.get("_review_input", "")  # 从 context 读取缓存
```

### 2.2 Pipeline 连接模式（关键发现）

`//` 是**双向连接**：`a // b` 让 `a._parallel` 包含 `b`，且 `b._parallel` 包含 `a`。当 a 执行完毕，`_route` 检查并行兄弟并启动它们。但当 b 执行完毕，它的 `_route` 也会尝试启动 a（已被执行，跳过）。

**Aggregator 挂载位置**至关重要：
- ❌ `Linter >> Aggregator` → Aggregator 在 Linter 执行后立即运行（其他Agent还没执行）
- ✅ `Performance >> Aggregator` → Performance 是并行链末端，其 `_route` 触发时所有Agent已完成

### 2.3 审查结果优先级排序

每个 issue 有 5 级严重度，Aggregator 进行加权评分：

| 严重度 | 权重 | 描述 |
|--------|------|------|
| critical | 20 | 安全漏洞、硬编码密钥 |
| high | 10 | None 比较、可变默认参数 |
| medium | 5 | 缺少注解、嵌套循环 |
| low | 2 | 风格问题、range(len) |
| info | 1 | 信息性记录 |

评分公式：`quality_score = max(0, 100 - raw_score)`

---

## 3. 测试结果

| 测试用例 | 评分 | 发现数 | 特点 |
|---------|------|--------|------|
| `hello.py`（干净代码） | **100/100** | 0 | 完整类型注解、正确风格 |
| `buggy_script.py`（问题代码） | **0/100** | 21 | 5个critical + 1个high |
| `views.py`（Django 视图） | **40/100** | 14 | SQL注入未检测到(f-string拼接) |
| `data_processor.py`（混合） | **0/100** | 17 | 2个critical + 1个high |

**发现问题分布（buggy_script.py）**：
- 🔴 5 个 CRITICAL：eval()、os.system()、pickle、密码硬编码、API key 硬编码
- 🟠 1 个 HIGH：`== None` 比较
- 🟡 13 个 MEDIUM：全部是缺少类型注解
- 🟢 2 个 LOW：range(len) 模式

---

## 4. 代码结构

### 4.1 核心文件

```
projects/multi_agent_review/
├── code_review_agents.py    # 核心Agent实现 (~800行)
│   ├── ReviewIssue          # 审查数据类 (severity/line/message/suggestion)
│   ├── BaseReviewAgent      # Agent基类 (数据传递/context管理)
│   ├── LinterAgent          # 代码风格检查 (~100行)
│   ├── TypeSafetyAgent      # 类型安全审查 (AST分析 + 正则)
│   ├── SecurityAgent        # 安全漏洞扫描 (~10种模式)
│   ├── PerformanceAgent     # 性能问题分析 (~12种模式)
│   └── ReviewAggregator     # 汇总报告生成 (评分/排序/格式化)
│
├── review_pipeline.py       # Pipeline编排 + 4个测试用例
│   ├── build_review_pipeline()  # 构建Pipeline拓扑
│   ├── run_review()             # 执行单次审查
│   └── main()                   # 运行所有测试用例
│
└── reports/                  # 输出报告目录
    ├── review_summary.json   # JSON 汇总
    ├── report_clean_code.txt
    ├── report_problematic_code.txt
    ├── report_django_view_script.txt
    └── report_data_processor.txt
```

### 4.2 测试用例设计

1. **干净代码**（hello.py）：验证误报率 — 完全符合规范的代码应该0问题
2. **问题代码**（buggy_script.py）：验证检出率 — 包含各种安全问题、类型问题、性能问题
3. **Django视图**（views.py）：模拟真实项目中的视图函数，测试框架特定模式的检测
4. **数据处理脚本**（data_processor.py）：混合了文件处理、shell调用、嵌套循环等问题

---

## 5. 实战收获与教训

### 5.1 Pipeline 引擎理解

1. **`>>`（串行）vs `//`（并行）的行为**
   - `>>`：当前节点完成后立即执行后继节点
   - `//`：双向连接，任一节点完成后触发所有未完成的并行兄弟
   - Pipeline 的 `_route` 执行顺序：串行 → 并行 → 条件

2. **Context 是唯一的共享状态**
   - data 参数在路由过程中会被覆写（前序节点的输出）
   - 跨节点共享必须通过 context（管道引擎的共享字典）
   - 最佳实践：首节点将原始输入缓存到 context，后续节点从 context 读取

3. **节点失败处理**
   - Pipeline 内置重试机制（`retry` 参数）
   - 节点失败不会杀死其他并行节点（线程独立）
   - 错误记录在 `node._error` 上

### 5.2 多Agent系统设计原则

1. **每个Agent是独立的审查专家** — 单一职责，只关注自己的领域
2. **数据格式统一** — 所有 Agent 输出 `{"agent", "issues", "filename"}` 格式
3. **汇总Agent知情不决策** — Aggregator 不判断对错，只做排序、评分、格式化
4. **严重度是沟通语言** — 用统一的 severity 体系让不同 Agent 的输出可比

### 5.3 改进空间

1. **真实模型集成**：当前是占位逻辑（规则+正则），后续可集成 LLM 调用
2. **增量审查**：只审查 diff 行而非整个文件
3. **Autofix**：Agent 可以返回自动修复的代码
4. **插件化**：通过配置注册新的审查 Agent
5. **结果持久化**：将审查报告写入飞书文档或数据库
6. **CI 集成**：挂接到 CI/CD 流程中自动运行

### 5.4 Windows 环境注意事项

- PowerShell 不支持 `&&` 分隔符，用 `;` 替代
- 写大文件时优先用 `open()` + 分段写入，避免 API 截断
- `.py` 文件直接执行，不用 `python -c` 嵌套引号字符串
- 路径分隔符用 `os.path.join()` 处理跨平台兼容

---

## 6. 运行方式

```bash
cd projects/multi_agent_review
python review_pipeline.py
```

输出：控制台打印审查报告，同时生成 `reports/` 目录下的 JSON/TXT 文件。
