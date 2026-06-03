# AI Agent 框架深度笔记

> 注：本文是学习笔记，聚焦 AI Agent 核心架构与 CrewAI 实践，同时对比主流框架，并对照羽现有 Agent 体系。

---

## 目录

1. [AI Agent 基础架构](#1-ai-agent-基础架构)
2. [主流框架对比](#2-主流框架对比)
3. [CrewAI 深度解析](#3-crewai-深度解析)
4. [多 Agent 协作模式](#4-多-agent-协作模式)
5. [工具调用机制](#5-工具调用机制)
6. [与羽现有 Agent 体系对比](#6-与羽现有-agent-体系对比)
7. [实战：用 CrewAI 搭建研究写作 Agent](#7-实战用-crewai-搭建研究写作-agent)

---

## 1. AI Agent 基础架构

### 1.1 什么是 AI Agent

AI Agent（智能体）是一个能自主感知环境、做出推理决策并执行行动的 AI 系统。与传统 LLM 调用不同，Agent 具备 **自主性（Autonomy）**、**目标导向（Goal-Oriented）** 和 **持续交互（Continuous Interaction）** 能力。

### 1.2 感知 → 思考 → 行动 → 反馈 循环

这是所有 AI Agent 的通用循环模型：

```
                    ┌─────────────────────────┐
                    │      外部环境/世界        │
                    └─────────────────────────┘
                              ↑ │
                    (感知/观察) │ │ (执行/影响)
                              │ ↓
              ┌───────────────────────────────┐
              │  1. 感知（Perception）          │
              │     - 接收用户输入（文本/语音）   │
              │     - 读取工具返回结果           │
              │     - 获取环境状态信息           │
              └───────────────────────────────┘
                              │
                              ↓
              ┌───────────────────────────────┐
              │  2. 思考（Thinking）            │
              │     - 上下文理解               │
              │     - 目标拆解 / 规划            │
              │     - 推理（Chain-of-Thought）   │
              │     - 决策（选工具 / 选策略）     │
              └───────────────────────────────┘
                              │
                              ↓
              ┌───────────────────────────────┐
              │  3. 行动（Action）              │
              │     - 调用工具（API/代码/搜索）  │
              │     - 生成回复给用户            │
              │     - 委派子任务给其他 Agent    │
              └───────────────────────────────┘
                              │
                              ↓
              ┌───────────────────────────────┐
              │  4. 反馈（Feedback Loop）       │
              │     - 观察行动结果              │
              │     - 评估是否达成目标          │
              │     - 调整下一步策略            │
              │     - 螺旋式迭代                │
              └───────────────────────────────┘
```

#### 关键点

- **循环是核心**：单次 LLM 调用不是 Agent，能根据反馈持续迭代才是 Agent
- **记忆（Memory）**：跨多次循环保持状态，区分短期记忆（上下文窗口）和长期记忆（外部存储）
- **工具（Tools）**：Agent 与外部世界交互的接口，本质是函数签名 + 描述
- **停止条件**：Agent 循环需要一个明确的终止信号（目标达成、达到最大迭代次数、用户中断）

### 1.3 ReAct 模式（Reasoning + Acting）

当前主流 Agent 的实现范式：

1. **Thought**：思考当前状态，分析下一步需要做什么
2. **Action**：选择一个工具并传入参数
3. **Observation**：观察工具返回的结果
4. 重复以上步骤，直到得到最终答案

```python
# ReAct 伪代码示例
def agent_loop(user_input, max_steps=10):
    context = [{"role": "user", "content": user_input}]
    for step in range(max_steps):
        response = llm(context)
        if response.is_final:
            return response.answer
        tool_result = execute_tool(response.tool_name, response.tool_args)
        context.append({"role": "assistant", "content": response.text})
        context.append({"role": "tool", "content": tool_result})
    return "Max steps reached"
```

---

## 2. 主流框架对比

### 2.1 一览表

| 维度 | CrewAI | LangChain（LangGraph） | AutoGPT | OpenAI Assistants API |
|------|--------|----------------------|---------|----------------------|
| **定位** | 多 Agent 协作框架 | Agent 应用构建框架 | 自主任务 Agent | 托管式 Agent 服务 |
| **核心抽象** | Agent, Task, Crew, Process | Chain, AgentExecutor, Graph | Agent, Plugins, Memory | Assistant, Thread, Run |
| **多 Agent** | 一等公民（原生支持） | 通过 LangGraph 实现 | 单 Agent 为主 | 单 Assistant 为主 |
| **流程控制** | 顺序/层级/调度 | DAG/图/条件路由 | 自主循环 | 内置 Run 循环 |
| **工具定义** | @tool 装饰器 | BaseTool 类 | JSON 配置 | function calling schema |
| **记忆管理** | 内置短期记忆 | Memory 接口+外部存储 | JSON 文件+向量库 | Thread 自动管理 |
| **LLM 支持** | 多模型（通过 LiteLLM） | 极多（100+ 集成） | GPT-4 为主 | 仅 OpenAI |
| **部署方式** | 自托管 | 自托管 | 自托管 | 托管（OpenAI） |
| **适用场景** | 多角色协作任务 | 复杂 Pipeline/应用 | 自主研究/编程 | 客服/QA/简单自动化 |
| **学习曲线** | 中低 | 中高 | 中 | 低 |
| **扩展性** | 高（插件/工具体系） | 极高（生态系统最大） | 中 | 低（封闭生态） |

### 2.2 各框架深度点评

#### CrewAI

- **优势**：多 Agent 协作体验最佳，Role/Goal/Backstory 的设定让每个 Agent 有"人格"，Task 委派自然
- **劣势**：社区相对较新，复杂 DAG 流程不如 LangGraph 灵活
- **最佳场景**：需要多个专门角色协同完成的任务，如研究+写作+审查流程

#### LangChain / LangGraph

- **优势**：生态最大，集成最多，LangGraph 的图计算模型极其灵活
- **劣势**：抽象层次多，API 频繁变动，调试复杂
- **最佳场景**：生产级复杂 Pipeline，需要对执行流程精确控制

#### AutoGPT

- **优势**：理念先驱，展示了自主 Agent 的能力上限
- **劣势**：稳定性差，token 消耗大，实际生产使用少
- **最佳场景**：演示/PoC，探索 Agent 能力边界

#### OpenAI Assistants API

- **优势**：零运维，自动管理状态，Code Interpreter 强大
- **劣势**：锁定 OpenAI，定制化有限，无法多 Agent 协作
- **最佳场景**：快速搭建简单 Agent 功能，无需自建基础设施

### 2.3 选型建议

```
┌─ 需要多 Agent 协作？───── 是 ─→ CrewAI
│
│  否
│
├─ 需要复杂 Pipeline / DAG？─ 是 ─→ LangGraph
│
│  否
│
├─ 只想用 OpenAI，托管运维？─ 是 ─→ Assistants API
│
│  否
│
└─ 研究 / PoC / 演示 ───────────→ AutoGPT
```

---

## 3. CrewAI 深度解析

### 3.1 核心概念

CrewAI 的架构围绕四个核心抽象：

```
           ┌─────────────────────┐
           │      Crew          │  → 管理 Agent 和 Task 的编排器
           │  (代理人团队)       │
           └──────┬─────────────┘
                  │ 包含
          ┌───────┴───────┐
          ▼               ▼
   ┌────────────┐  ┌────────────┐
   │  Agent    │  │   Task    │
   │  (智能体)  │  │  (任务)   │
   └─────┬─────┘  └─────┬──────┘
         │               │
    ┌────┴────┐    ═══ 委派给 ═══
    │ Tools  │
    │ (工具)  │
    └─────────┘
```

### 3.2 Agent 定义

Agent 是执行任务的智能体，通过 Role/Goal/Backstory 进行角色建模：

```python
from crewai import Agent

researcher = Agent(
    role="资深研究员",
    goal="深入挖掘主题，找出最有价值的洞察和数据",
    backstory="""你是一位在科技行业有15年经验的高级研究员。
    你擅长从海量信息中提取关键洞见，特别擅长技术趋势分析。
    你的报告以深度和准确性著称。""",
    # 可选配置
    verbose=True,
    allow_delegation=True,       # 是否允许委派子任务给其他 Agent
    max_iter=15,                 # 最大思考-行动循环次数
    max_rpm=10,                  # 每分钟最大请求数（控制成本）
    llm="gpt-4-turbo",           # 也可以传入自定义 LLM 对象
    tools=[search_tool, ...],    # Agent 可用的工具列表
    memory=True,                 # 是否启用短期记忆
    function_calling_llm=None,   # 专门用于 function calling 的 LLM
)
```

**设计要点**：
- Role/Goal/Backstory 共同塑造 Agent 的行为模式
- Backstory 越详细，Agent 的"角色感"越强，输出越一致
- `allow_delegation=True` 让 Agent 可以主动将子任务交给其他 Agent

### 3.3 Task 定义

Task 是要完成的具体工作单元，可分配给特定 Agent：

```python
from crewai import Task

research_task = Task(
    description="""研究 AI Agent 框架的最新发展趋势。
    重点关注 CrewAI、LangChain 和 AutoGPT 的对比。
    
    要求：
    - 覆盖2024-2025年的最新进展
    - 至少引用3个具体案例
    - 输出格式为详细的研究笔记""",
    expected_output="一份详细的 Markdown 格式研究笔记",
    agent=researcher,          # 分配给哪个 Agent
    tools=[search_tool],       # 任务级别的工具（覆盖 Agent 的工具列表）
    context=[],                # 上下文任务列表（任务的输出会作为输入）
    async_execution=False,     # 是否异步执行
    callback=lambda output: print(f"任务完成: {output[:100]}"),
)

write_task = Task(
    description="""基于研究笔记，撰写一篇面向开发者的技术文章。
    要求：专业、有趣、有深度""",
    expected_output="一篇完整的 Markdown 技术文章",
    agent=writer,
)
```

**Task 委派流程**：

```
Task created → 分配给 Agent → Agent 进入 ReAct 循环
                                │
                    ┌───────────┴───────────┐
                    │   Thought：如何完成    │
                    │   Action：调用工具     │
                    │   Observation：看结果  │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Agent 判断是否完成    │
                    │   是 → 输出结果        │
                    │   否 → 继续循环        │
                    └───────────────────────┘
```

### 3.4 工具注册

CrewAI 中工具通过 `@tool` 装饰器定义：

```python
from crewai.tools import tool
from duckduckgo_search import DDGS

@tool("WebSearch")
def web_search(query: str) -> str:
    """搜索网络获取最新信息。适用于需要实时数据的查询。"""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
    return "\n".join([f"{r['title']}: {r['body']}" for r in results])
```

也可以使用 `BaseTool` 类定义更复杂的工具：

```python
from crewai.tools import BaseTool

class FixedSearchTool(BaseTool):
    name: str = "FixedSearch"
    description: str = "搜索指定主题的固定查询"
    
    def _run(self, query: str) -> str:
        # 自定义逻辑
        return f"Search results for: {query}"
```

### 3.5 Crew 与流程管理

Crew 是编排器，决定 Agent 和 Task 如何协作：

```python
from crewai import Crew, Process

crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, write_task, review_task],
    process=Process.sequential,  # 流程类型
    verbose=2,
    memory=True,
    cache=True,
    share_crew=False,            # 是否共享 Crew 内部信息给所有 Agent
    output_log_file="crew.log",
)
```

#### 三种流程类型

**1. 顺序流程（Process.sequential）**

```
Task1 → Agent1 → Task2 → Agent2 → Task3 → Agent3
```

- Task 按定义顺序依次执行
- 前一个 Task 的输出可以传给后一个作为上下文
- 适用于：线性流水线任务

**2. 层级流程（Process.hierarchical）**

```
          ┌─────────────┐
          │  Manager    │  → 负责规划、分配、审查
          │  Agent      │
          └──────┬──────┘
                 │ 分配 & 审查
        ┌────────┼────────┐
        ▼        ▼        ▼
     ┌─────┐ ┌─────┐ ┌─────┐
     │Agent│ │Agent│ │Agent│  → 各司其职
     │  A  │ │  B  │ │  C  │
     └─────┘ └─────┘ └─────┘
```

- 有一个 Manager Agent 负责分配和审查
- 适合于：项目经理模式的复杂任务

**3. 调度流程（Process.process）**

```python
自定义流程：使用自定义函数控制 Task 执行顺序
def custom_process(crew, tasks, agents):
    # 自定义编排逻辑
    pass
```

- 完全自定义的执行逻辑
- 适用于：需要条件分支、循环、动态任务生成的场景

### 3.6 完整示例骨架

```python
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# 1. 定义工具
@tool
def search_web(query: str) -> str:
    """搜索网络"""
    return f"Mock result for: {query}"

# 2. 定义 Agent
analyst = Agent(role="分析师", goal="分析数据", backstory="...", tools=[search_web])
writer = Agent(role="写手", goal="撰写报告", backstory="...")

# 3. 定义 Task
task1 = Task(description="分析主题", expected_output="分析结果", agent=analyst)
task2 = Task(description="撰写报告", expected_output="报告", agent=writer)

# 4. 组装 Crew
crew = Crew(
    agents=[analyst, writer],
    tasks=[task1, task2],
    process=Process.sequential,
)

# 5. 执行
result = crew.kickoff(inputs={"topic": "AI Agent 框架对比"})
print(result)
```

---

## 4. 多 Agent 协作模式

### 4.1 辩论法（Debate）

多个 Agent 对同一问题从不同角度论证，通过辩论逼近最优解：

```
          ┌─────────────┐
          │   问题/主题   │
          └──────┬──────┘
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
   ┌────────┐┌────────┐┌────────┐
   │ 正方   ││ 反方   ││ 中立   │
   │ Agent  ││ Agent  ││ Agent  │
   └───┬────┘└───┬────┘└───┬────┘
        │         │         │
        └─────────┼─────────┘
                  ▼
          ┌──────────────┐
          │  综合裁决     │
          │  (或 Manager) │
          └──────┬───────┘
                 ▼
          ┌──────────────┐
          │  最终结论     │
          └──────────────┘
```

**适用场景**：
- 需要权衡利弊的决策
- 代码审查和安全分析
- 有争议的话题分析

**CrewAI 实现要点**：
```python
pro_agent = Agent(role="支持方", goal="论证优点", backstory="...")
con_agent = Agent(role="反对方", goal="指出风险", backstory="...")
judge = Agent(role="裁判", goal="综合评判", backstory="...")

# 通过 Task context 串联辩论轮次
debate_round1 = Task(description="...", agent=pro_agent)
debate_round2 = Task(description="...", agent=con_agent, context=[debate_round1])
final_verdict = Task(description="...", agent=judge, context=[debate_round1, debate_round2])
```

### 4.2 审查法（Review）

一个 Agent 产出内容，另一个 Agent 审查修正：

```
  ┌─────────┐        ┌─────────┐        ┌─────────┐
  │ 初级    │───────▶│ 中级    │───────▶│ 高级    │
  │ Agent   │ 提交    │ Agent   │ 提交    │ Agent   │
  │ (产出)  │◀───────│ (审查)  │◀───────│ (终审)  │
  └─────────┘ 修订    └─────────┘ 修订    └─────────┘
```

**适用场景**：
- 代码开发（写 → 审查 → 合并）
- 内容创作（写 → 编辑 → 发布）
- 翻译（翻译 → 校对 → 润色）

**与羽现有体系对照**：类似羽的 Agent Engine 中的 Interceptor 链模式，每个审查环节可以是一个 Interceptor。

### 4.3 管道法（Pipeline）

多个 Agent 各自负责流水线中的一个环节，输出是下一个的输入：

```
  Agent A    →    Agent B    →    Agent C    →    Agent D
  研究            写大纲          撰写正文          排版优化
```

**CrewAI 天然支持**：Process.sequential 就是管道法。

**适用场景**：
- 内容生产流水线
- 数据处理 ETL
- 多阶段分析

### 4.4 协作模式对比

| 模式 | 通信方式 | 适用规模 | 优点 | 缺点 |
|------|---------|---------|------|------|
| **辩论法** | 多对一 | 3-5 个 Agent | 观点全面、自我纠错 | token 消耗大、耗时长 |
| **审查法** | 链式 | 2-3 个 Agent | 质量有保障 | 可能过度修改 |
| **管道法** | 链式 | 3-10 个 Agent | 分工明确、扩展性好 | 前端的错误会累积到后端 |
| **层级法** | 树状 | 5-20 个 Agent | 管理高效 | Manager 是单点瓶颈 |

---

## 5. 工具调用机制

### 5.1 工具调用的本质

无论哪种框架，工具调用的底层都是 LLM 的 **Function Calling** 能力：

```
LLM 输出: {"name": "search_web", "arguments": {"query": "CrewAI 2025"}}
                  │
                  ▼
  框架解析 → 校验参数 → 执行函数 → 返回结果
                  │
                  ▼
  LLM 输入: Observation: "搜索结果：..."
```

### 5.2 三种工具类型

#### 函数调用（Function Calling）

```python
@tool("Calculator")
def calculator(expression: str) -> str:
    """计算数学表达式。输入必须是合法的数学表达式。"""
    try:
        result = eval(expression)
        return f"结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"

# 框架自动生成 JSON Schema 给 LLM
# {
#   "name": "Calculator",
#   "description": "计算数学表达式...",
#   "parameters": {
#     "type": "object",
#     "properties": {
#       "expression": {
#         "type": "string",
#         "description": "数学表达式"
#       }
#     },
#     "required": ["expression"]
#   }
# }
```

#### REST API 调用

```python
import requests

@tool("GitHubAPI")
def github_api(endpoint: str) -> str:
    """调用 GitHub REST API。endpoint 示例: /repos/openai/openai"""
    url = f"https://api.github.com{endpoint}"
    resp = requests.get(url, timeout=10)
    return resp.text[:2000]
```

#### 代码执行

```python
# 安全沙箱执行代码
@tool("PythonExecutor")
def execute_python(code: str) -> str:
    """在隔离环境中执行 Python 代码。适用于数据分析、可视化。"""
    # 生产环境应使用 Docker/subprocess 沙箱
    try:
        local_vars = {}
        exec(code, {"__builtins__": __builtins__}, local_vars)
        return str(local_vars.get("result", "代码执行成功"))
    except Exception as e:
        return f"执行错误: {e}"
```

### 5.3 工具设计原则

1. **专业单一**：每个工具只做一件事，做好一件事
2. **描述精确**：description 告诉 LLM 何时使用、怎么使用
3. **参数明确**：参数名和类型清晰，LLM 才能正确传参
4. **错误处理**：工具内部做好异常捕获和友好提示
5. **有界输出**：控制返回结果长度（Agent 上下文窗口有限）

### 5.4 框架中工具注册差异

| 框架 | 注册方式 | 自动 Schema | 内置工具 |
|------|---------|------------|---------|
| CrewAI | `@tool` 装饰器 | ✅ | WebSearch, FileRead 等 |
| LangChain | `BaseTool` 子类 | ✅ | 大量官方工具包 |
| AutoGPT | JSON 配置文件 | 手动 | 有限内置 |
| OpenAI API | JSON Schema 手写 | ❌ | Code Interpreter, File Search |

---

## 6. 与羽现有 Agent 体系对比

### 6.1 羽的 Agent 架构

```


  ┌─────────────────────────────────────────┐
  │              Gateway                     │
  │  路由/鉴权/限流/协议转换                  │
  └────────────────┬────────────────────────┘
                   │
  ┌────────────────▼────────────────────────┐
  │           Orchestrator                  │
  │  会话管理/上下文维护/Agent 调度/策略路由 │
  └────────────────┬────────────────────────┘
                   │
  ┌────────────────▼────────────────────────┐
  │            Engine                       │
  │  LLM 调用/工具执行/插件加载/Interceptor  │
  └────────────────┬────────────────────────┘
                   │
  ┌────────────────▼────────────────────────┐
  │            Storage                      │
  │  记忆持久化/文档存储/向量数据库           │
  └─────────────────────────────────────────┘
```

### 6.2 对比分析

| 维度 | 羽（Gateway/Orchestrator/Engine/Storage） | CrewAI |
|------|-------------------------------------------|--------|
| **架构风格** | 分层、微服务友好 | 单体库、Agent 为中心 |
| **多 Agent** | Orchestrator 调度多个 Engine 实例 | Crew 编排 Agent 集合 |
| **工具系统** | Engine 加载插件，Interceptor 链处理 | @tool 装饰器注册，Agent 直接调用 |
| **流程控制** | Orchestrator 通过策略/规则路由 | Process.sequential / hierarchical / 自定义 |
| **记忆系统** | Storage 层统一管理 | Agent 内置 memory + 可扩展 |
| **并发模型** | 多线程/异步 IO（生产级） | 单线程为主（库级别） |
| **扩展方式** | 插件系统 + Interceptor 钩子 | 工具 + 自定义 Agent |
| **会话管理** | Orchestrator 维护 | 无内置会话管理 |
| **生产化程度** | 高（考虑鉴权/限流） | 低（需自行包装） |

### 6.3 对应关系映射

```
羽 Gateway        → 无直接对应（CrewAI 假设信任环境）
羽 Orchestrator   → Crew 对象（管理调度）
羽 Engine         → Agent 的 ReAct 循环（思考+行动）
羽 Storage        → Agent.memory（简化版）

羽 Interceptor    → 审查法协作模式 / Task callback
羽 插件系统        → CrewAI 的 tool 体系
```

### 6.4 融合思路

如果 CrewAI 要嵌入羽的架构：

```python
# 羽的 Orchestrator 中调用 CrewAI
class YuOrchestrator:
    def execute_crew(self, crew_config: dict, session_id: str):
        # 1. 从 Storage 恢复上下文
        context = self.storage.get_session(session_id)
        
        # 2. 使用羽的 Engine 实例作为 CrewAI 的 LLM backend
        llm = YuOpenAI(
            api_key=self.config.api_key,
            model=self.config.model,
            session_id=session_id,
        )
        
        # 3. 创建 CrewAI Agent，使用羽的工具
        agents = [
            Agent(llm=llm, tools=self.get_yu_tools(agent_cfg))
            for agent_cfg in crew_config["agents"]
        ]
        
        # 4. 执行 Crew
        crew = Crew(agents=agents, tasks=crew_config["tasks"])
        result = crew.kickoff()
        
        # 5. 持久化记忆
        self.storage.save_session(session_id, result)
        return result
```

---

## 7. 实战：用 CrewAI 搭建研究写作 Agent

### 7.1 环境准备

```bash
# 安装 CrewAI（需 Python 3.10+）
pip install crewai
pip install crewai[tools]  # 包含内置工具包

# 如果需要搜索工具
pip install duckduckgo-search
```

### 7.2 完整代码：Agent 研究写作系统

```python
"""
research_writer_crew.py
一个研究 + 写作 + 审查 的三 Agent 协作系统
"""

import os
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# ========== 1. 定义工具 ==========

@tool("WebSearch")
def web_search(query: str) -> str:
    """搜索网络获取实时信息。适用于研究阶段查询最新资料。"""
    from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return "未找到相关结果"
        return "\n\n".join([
            f"**{r['title']}**\n{r['body']}\n来源: {r.get('href', 'N/A')}"
            for r in results
        ])
    except Exception as e:
        return f"搜索失败: {e}"


# ========== 2. 创建 Agent ==========

researcher = Agent(
    role="资深研究员",
    goal="""深入挖掘研究主题，收集最相关、最新的信息。
    确保信息全面、准确、有引用来源。""",
    backstory="""你是一位在科技领域深耕多年的研究专家。
    你擅长从海量信息中提取关键见解，识别趋势和模式。
    你非常注重信息的准确性和来源的可信度。
    你的研究笔记是团队其他成员的重要参考。""",
    tools=[web_search],
    verbose=True,
    allow_delegation=False,
    max_iter=10,
)

writer = Agent(
    role="技术写手",
    goal="""将研究笔记转化为引人入胜、专业深入的技术文章。
    文章应该既有技术深度，又易于理解。""",
    backstory="""你是一位经验丰富的技术内容创作者。
    你擅长将复杂的技术概念转化为清晰易懂的文章。
    你的文章以结构清晰、逻辑严密、案例丰富著称。
    你善于使用类比和实例来帮助读者理解。""",
    verbose=True,
    allow_delegation=False,
)

reviewer = Agent(
    role="内容审查官",
    goal="""确保最终输出的内容质量：
    - 技术准确性
    - 逻辑连贯性
    - 格式规范性
    - 读者友好度""",
    backstory="""你是一位严厉但公正的内容审查专家。
    你对技术细节极其敏感，对任何不准确或表述不清的地方都会指出。
    你的审查意见总是让内容变得更好。""",
    verbose=True,
    allow_delegation=False,
)


# ========== 3. 创建 Task ==========

research_task = Task(
    description="""
    ## 研究任务
    
    对以下主题进行深入研究：{topic}
    
    要求：
    1. 搜索至少 3 个信息源
    2. 提取关键观点、数据、案例
    3. 识别不同观点之间的对比和联系
    4. 注意信息的时效性（优先2024-2025年的资料）
    
    输出格式：
    - 主题概览
    - 关键发现（带引用）
    - 主要观点对比
    - 相关案例
    - 参考资料列表
    """,
    expected_output="一份结构化的 Markdown 研究笔记，包含关键发现和引用",
    agent=researcher,
)

writing_task = Task(
    description="""
    ## 写作任务
    
    基于研究笔记，撰写一篇技术文章。
    
    要求：
    1. 文章需要有一个吸引人的标题
    2. 开篇需要抓住读者注意力
    3. 正文结构清晰，使用小标题分段
    4. 技术内容准确，必要时使用代码示例
    5. 结尾有总结和展望
    6. 面向目标读者：技术人员和开发者
    
    风格：专业而不晦涩，深入但不啰嗦
    """,
    expected_output="一篇完整的 Markdown 格式技术文章",
    agent=writer,
    context=[research_task],  # 依赖研究任务的输出
)

review_task = Task(
    description="""
    ## 审查任务
    
    对写好的文章进行全面审查。
    
    检查清单：
    - [ ] 技术准确性：所有陈述是否准确
    - [ ] 逻辑连贯性：段落之间是否顺畅
    - [ ] 格式规范：Markdown 格式是否正确
    - [ ] 读者体验：是否容易理解
    - [ ] 内容完整：是否覆盖了核心要点
    
    如果发现问题，请给出具体的修改建议。
    如果质量达标，确认通过。
    """,
    expected_output="审查报告 + 修改后的最终文章",
    agent=reviewer,
    context=[research_task, writing_task],
)


# ========== 4. 组装 Crew ==========

research_crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, writing_task, review_task],
    process=Process.sequential,  # 依次执行
    verbose=2,  # 输出详细信息
    memory=True,
)


# ========== 5. 执行 ==========

if __name__ == "__main__":
    # 执行 Crew
    result = research_crew.kickoff(inputs={
        "topic": "CrewAI vs LangChain vs AutoGPT：AI Agent 框架深度对比分析"
    })
    
    # 输出结果
    print("\n" + "=" * 60)
    print("最终输出:")
    print("=" * 60)
    print(result)
    
    # 保存到文件
    with open("agent_framework_comparison.md", "w", encoding="utf-8") as f:
        f.write(str(result))
    
    print("\n✅ 已完成！结果已保存到 agent_framework_comparison.md")
```

### 7.3 运行说明

```bash
# 1. 安装依赖
pip install crewai duckduckgo-search

# 2. 设置环境变量
export OPENAI_API_KEY="sk-xxx"   # 或其他 LLM 的 API key

# 3. 运行
python research_writer_crew.py

# 4. 使用其他 LLM（通过 LiteLLM）
# 在 Agent 中设置：
# llm="ollama/llama3"
# llm="claude/claude-3-opus-20240229"
# llm="gemini/gemini-pro"
```

### 7.4 进阶扩展

```python
# 1. 添加 FireCrawl 工具实现深度抓取
@tool("WebScraper")
def web_scraper(url: str) -> str:
    """抓取指定 URL 的完整内容。适用于深度分析。"""
    import requests
    from bs4 import BeautifulSoup
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text()[:5000]

# 2. 使用层级流程（加入 Manager）
research_crew = Crew(
    agents=[researcher, writer, reviewer],
    tasks=[research_task, writing_task, review_task],
    process=Process.hierarchical,
    manager_llm="gpt-4-turbo",
)

# 3. 添加回调进行实时监控
def task_callback(task_output):
    print(f"[{task_output.agent}] 完成任务: {task_output.summary[:50]}...")

research_task.callback = task_callback
```

---

## 总结

- **AI Agent 的核心范式**是「感知→思考→行动→反馈」的持续循环，ReAct 是实现该范式的主流方式
- **CrewAI** 在多 Agent 协作场景下体验最佳，Role/Goal/Backstory 的角色建模是其杀手锏
- **框架选型**取决于场景：多 Agent → CrewAI，复杂 Pipeline → LangGraph，托管 → OpenAI Assistants
- **多 Agent 模式**中辩论法/审查法/管道法各有适用场景，可混合使用
- **工具调用**的底层都是 Function Calling，设计好工具的描述和参数是关键
- **羽的架构**偏生产级分层设计，CrewAI 偏开发体验，两者可互补融合
- **实战**显示只需几十行代码就能搭建一个完整的研究-写作-审查流水线

---

*本笔记编写于 2025 年，基于 CrewAI v0.30+。框架发展迅速，请以最新版本为准。*
