# 多Agent协作框架 (Multi-Agent Collaboration Framework)

> 一个轻量级、零外部依赖的多Agent框架，纯 Python 3.11+ 实现。
> 基于 ReAct 模式，支持工具注册、记忆检索和多Agent协调。

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                      用户输入                            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Agent 核心循环 (ReAct)                      │
│                                                         │
│    ┌─────────┐    ┌─────────┐    ┌─────────┐           │
│    │  感知    │───▶│  思考    │───▶│  行动    │           │
│    │Perceive │    │  Think   │    │   Act    │           │
│    └─────────┘    └─────────┘    └────┬────┘           │
│         ▲                             │                 │
│         │        ┌─────────┐          │                 │
│         └────────│  观察    │◀────────┘                 │
│                  │ Observe  │                           │
│                  └─────────┘                            │
└─────────────────────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│  ToolRegistry │ │  Memory   │ │ Orchestrator │
│ (工具注册表)  │ │ (记忆模块)│ │ (多Agent协调)│
├──────────────┤ ├──────────┤ ├──────────────┤
│ · 工具注册    │ │ · 对话记忆│ │ · 主管-工人   │
│ · Schema推导  │ │ · TF-IDF │ │ · 对等协作    │
│ · 标签过滤    │ │ · 语义检索│ │ · 辩论模式    │
│ · 安全执行    │ │ · 重要性  │ │ · 消息总线    │
└──────────────┘ └──────────┘ └──────────────┘
```

## 模块说明

| 模块 | 文件 | 说明 |
|------|------|------|
| **Core** | `core.py` | Agent 基类、工具注册系统、ReAct 循环 |
| **Memory** | `memory.py` | 对话记忆、TF-IDF 向量检索、综合记忆系统 |
| **Orchestrator** | `orchestrator.py` | 消息总线、三种协作模式、任务调度 |
| **Agents** | `agents/` | 编程、搜索、分析三个实战 Agent |

## 快速开始

### 创建并使用一个 Agent

```python
from agent_framework import BaseAgent, MockLLM

# 创建一个带 mock LLM 的 Agent
agent = BaseAgent(
    name="my_agent",
    llm=MockLLM(responses=["Hello! I'm your AI assistant."]),
    system_prompt="You are a helpful assistant.",
)

# 运行
ctx = agent.run("Say hello")
print(ctx.messages[-1]["content"])  # "Hello! I'm your AI assistant."
```

### 工具注册与使用

```python
from agent_framework import ToolRegistry, BaseAgent

# 创建注册表
reg = ToolRegistry()

# 方式1: 装饰器注册
@reg.register(description="计算两数之和")
def add(a: float, b: float) -> float:
    """a: 第一个数字\nb: 第二个数字"""
    return a + b

# 方式2: ToolDef 直接注册
from agent_framework import ToolDef
reg.register_tool(ToolDef(
    name="greet",
    description="打招呼",
    handler=lambda name: f"Hello, {name}!",
))

# 在 Agent 中使用
agent = BaseAgent(registry=reg)
assert reg.execute("add", a=3, b=4) == 7.0
```

### 记忆系统

```python
from agent_framework import MemorySystem, TFIDFVectorMemory

# 综合记忆系统
ms = MemorySystem()
ms.remember_conversation("conv1", "user", "I love Python")
ms.remember_conversation("conv1", "assistant", "Python is great!")

# 语义检索
results = ms.recall("Python programming")
for item, score in results:
    print(f"[{score:.2f}] {item.content}")

# 构建增强上下文（RAG 模式）
context = ms.build_context("conv1", "Python")
print(context)
```

### 多Agent协作

```python
from agent_framework import Orchestrator, BaseAgent, CollaborationMode

# 创建协调器
orch = Orchestrator()

# 添加 Agent
orch.add_agent(BaseAgent(name="worker_1"), role="worker", capabilities=["code"])
orch.add_agent(BaseAgent(name="worker_2"), role="worker", capabilities=["search"])

# 辩论模式
result = orch.run(
    query="AI safety is important?",
    mode=CollaborationMode.DEBATE,
    debaters=[debater1, debater2],
    arbiter=arbiter,
)
```

## Agent 示例

### 1. CodingAgent (编程Agent)

编写并执行 Python 代码的安全沙箱。

```python
from agent_framework import create_coding_agent

agent = create_coding_agent()
result = agent.registry.execute("run_python_code", code="result = sum(range(100))")
print(result["result"])  # 4950
```

**安全特性：**
- 阻止 `os`, `subprocess`, `eval`, `exec`, `open` 等危险操作
- 白名单安全内置函数
- 代码静态分析 (AST) 检查

### 2. SearchAgent (搜索Agent)

本地知识库语义搜索 + 模拟 web 搜索。

```python
from agent_framework import create_search_agent

agent = create_search_agent()
agent.kb.add("Python is used in AI and data science")

results = agent.registry.execute("semantic_search", query="AI Python", top_k=3)
for r in results:
    print(f"Score {r['score']}: {r['content']}")
```

### 3. AnalysisAgent (分析Agent)

汇总评估多源结果的结构化输出。

```python
from agent_framework import create_analysis_agent

agent = create_analysis_agent()
result = agent.registry.execute(
    "compare_sources",
    sources="source_a,source_b",
    dimensions="accuracy,completeness",
)
print(result["type"])  # "comparison"
```

## 与主流框架对比

| 维度 | 本框架 | LangChain | AutoGen | CrewAI |
|------|--------|-----------|---------|--------|
| **外部依赖** | 零依赖 | 多 (langchain, 各API SDK) | pyautogen + 各 SDK | 多 (crewai, langchain) |
| **代码量** | ~500行 | 数十万行 | 数万行 | 数万行 |
| **学 Curva** | 低 (纯 Python) | 中高 (框架概念多) | 中 (配置复杂) | 中 |
| **工具注册** | 装饰器 + ToolDef | BaseTool 类 | function_tools | @tool 装饰器 |
| **记忆系统** | 内置 (TF-IDF) | 需集成外部 | 内置 (有限) | 需集成 |
| **Agent 循环** | ReAct (透明) | AgentExecutor (封装) | 对话驱动 | 任务驱动 |
| **多Agent模式** | 3种 (OW/P2P/Debate) | 需扩展 | 内置 (对话) | 内置 (任务) |
| **安全沙箱** | 内置代码沙箱 | 无 | 无 | 无 |
| **测试覆盖** | 完整 (单元测试) | 依赖社区 | 有限 | 有限 |
| **适用场景** | 学习/原型/轻量 | 生产级 | 研究/对话 | 任务编排 |

### 框架哲学对比

```
本框架:  透明 > 抽象 | 可控 > 自动化 | 教学 > 黑盒
LangChain: 抽象 > 透明 | 自动化 > 可控 | 生产 > 教学
AutoGen:   对话 > 流程 | 多Agent > 单Agent | 研究 > 工程
CrewAI:    角色 > 流程 | 分工 > 协作 | 易用 > 灵活
```

## 测试

```bash
# 运行所有测试
python -m pytest projects/agent_framework/ -v

# 仅运行特定模块测试
python -m pytest projects/agent_framework/tests/test_core.py -v
python -m pytest projects/agent_framework/tests/test_memory.py -v
python -m pytest projects/agent_framework/tests/test_orchestrator.py -v
python -m pytest projects/agent_framework/tests/test_agents.py -v
```

## 文件结构

```
projects/agent_framework/
├── __init__.py              # 包入口 + 导出
├── core.py                  # Agent基类 + 工具注册系统
├── memory.py                # 记忆模块 (TF-IDF + 对话记忆)
├── orchestrator.py          # 多Agent协调核心
├── README.md                # 本文档
├── agents/
│   ├── __init__.py
│   ├── coding_agent.py      # 编程Agent（代码沙箱）
│   ├── search_agent.py      # 搜索Agent（语义+web）
│   └── analysis_agent.py    # 分析Agent（结构化输出）
└── tests/
    ├── __init__.py
    ├── test_core.py          # 核心模块测试
    ├── test_memory.py        # 记忆模块测试
    ├── test_orchestrator.py  # 协调模块测试
    └── test_agents.py        # Agent示例测试
```

## 从理论到实践

本框架是以下学习笔记的实战产物：

| 笔记 | 对应实现 |
|------|----------|
| Agent 架构基础 | `core.py` — ReAct 循环、Plan-and-Execute |
| 工具使用与函数调用 | `core.py` — ToolRegistry、ToolDef、JSON Schema |
| RAG 深度 | `memory.py` — build_context() 检索增强 |
| 记忆系统设计 | `memory.py` — 短期/长期/工作记忆 |
| 多Agent协作 | `orchestrator.py` — 三种协作模式 |
| 安全对齐 | `agents/coding_agent.py` — 代码沙箱 |

## License

MIT
