# AI Agent 框架实战 — 从零实现轻量级多Agent协作系统

## 1. Agent 核心架构：感知 → 推理 → 行动 → 反馈循环

### 1.1 架构总览

```
输入（感知） → [推理（思考）] → 行动（工具调用/回复） → 观察（反馈） → 循环
    ↑                                                                |
    └────────────────────────────────────────────────────────────────┘
```

- **感知（Perception）**：解析用户输入，提取关键信息
- **推理（Reasoning）**：根据上下文和记忆，决定下一步做什么
- **行动（Action）**：调用工具或生成最终回复
- **反馈（Feedback/Observation）**：接收工具执行结果，更新上下文

### 1.2 核心数据流

```
User Input
  ↓
[Agent.think()] → 构造 prompt，调用 LLM 获取推理结果
  ↓
[Agent.act()]   → 解析推理结果中的 Action: tool_name(kwargs)
  ↓              → 或者直接生成 Final Answer
[Tool.run()]     → 执行具体工具函数
  ↓
[Agent.observe()] → 将工具结果追加到短期记忆
  ↓
[Agent.think()] → 再次推理（ReAct 循环），直到生成 Final Answer
  ↓
最终回复
```

### 1.3 实现要点

```python
class Agent:
    def think(self, user_input):
        messages = self._build_messages(user_input)
        response = self.llm_callable(messages)
        thought = self._parse_thought(response)  # 提取推理过程
        action = self._parse_action(response)    # 提取行动指令
        return thought, action

    def act(self, action):
        if action["type"] == "tool":
            tool = self.tools[action["name"]]
            result = tool.run(**action["kwargs"])
            return result
        elif action["type"] == "final":
            return action["answer"]
    
    def observe(self, result):
        self.memory.add_observation(result)
```

## 2. ReAct 模式（Reasoning + Acting）纯 Python 实现

### 2.1 ReAct 原理

ReAct = Reasoning + Acting，让 LLM 在思考和行动之间交替进行。

标准 ReAct Prompt 格式：

```
Question: {question}
Thought: {reasoning step}
Action: tool_name(arg1=val1, arg2=val2)
Observation: {tool result}
Thought: {next reasoning step}
...
Final Answer: {final response}
```

### 2.2 我实现的 ReAct 循环

```python
def run_react_loop(self, user_input, max_steps=10):
    self.memory.add_message("user", user_input)
    
    for step in range(max_steps):
        # 1. Think — 推理
        thought, action = self.think(user_input)
        
        if action["type"] == "final":
            # 生成最终回复
            self.memory.add_message("assistant", action["answer"])
            return action["answer"]
        
        # 2. Act — 执行工具
        result = self.act(action)
        
        # 3. Observe — 观察结果
        self.observe(result)
    
    return "Error: 达到最大迭代次数"
```

### 2.3 伪 LLM 实现

当没有真实 API 时，使用基于关键词匹配的伪 LLM 来模拟：

```python
def pseudo_llm(messages):
    """基于关键词匹配的伪 LLM，用于测试"""
    last_msg = messages[-1]["content"]
    
    if "您好" in last_msg or "你好" in last_msg:
        return "Thought: 用户打招呼\nFinal Answer: 您好！我是AI助手，很高兴为您服务。"
    
    if "搜索" in last_msg:
        return ("Thought: 用户需要文件搜索\n"
                "Action: search_files(query='search_term', dir_path='.')\n")
    
    # ReAct 循环格式
    return "Thought: 无法确定\nFinal Answer: 我不理解您的请求，请重新描述。"
```

## 3. 工具调用模式（Tool-use Agent）

### 3.1 Tool 类设计

```python
class Tool:
    def __init__(self, name, description, func, parameters_schema):
        self.name = name
        self.description = description  # LLM 用工具描述
        self.func = func                # 实际执行函数
        self.parameters_schema = parameters_schema  # JSON Schema

    def run(self, **kwargs):
        return self.func(**kwargs)
```

### 3.2 工具注册机制

工具允许 Agent 访问外部能力（文件系统、代码执行等）：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| read_file | 读取文件内容 | path |
| search_files | 搜索文件 | query, dir_path |
| run_python | 安全执行 Python | code |
| list_directory | 列出目录 | path |
| file_stats | 文件统计 | path |

### 3.3 安全沙箱

`run_python` 使用 AST 安全检查来防止恶意代码执行：

```python
def _check_code_safety(tree):
    """AST 安全检查 — 阻止 os.system、__import__ 等危险操作"""
    dangerous = ['os', 'subprocess', 'shutil', '__import__', 'exec', 'eval']
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ['system', 'popen', 'run', 'call']:
                    raise SecurityError("禁止的系统调用")
```

### 3.4 LLM 决定工具调用

LLM 的输出格式决定了 Agent 调用哪个工具：

```
Thought: 用户想要搜索文件，我需要使用 search_files 工具
Action: search_files(query="*.py", dir_path="./src")
```

Agent 解析 `Action:` 行来提取 `工具名(参数)`，然后调用对应的 Tool。

## 4. 多Agent 协作模式

### 4.1 三种协作模式对比

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| **Router（路由）** | 分析输入，分发到合适 Agent | 输入类型多样，需要专业处理 |
| **Chain（链式）** | 前一 Agent 输出 → 后一 Agent 输入 | 流水线处理，逐步精化 |
| **Parallel（并行）** | 多个 Agent 同时处理同一输入 | 多维度分析、审查 |
| **Supervisor（监督）** | 监督 Agent 协调工作 Agent | 复杂任务分解与质量控制 |

### 4.2 Router 模式

```
User Input
  ↓
Router Agent — 分析任务类型
  ├─ 代码审查 → Linter Agent
  ├─ 安全检查 → Security Agent
  ├─ 性能分析 → Performance Agent
  └─ 未知类型 → 默认 Agent
```

实现：`AgentOrchestrator.route_task(task_desc, criteria)` 根据描述关键词匹配注册的 Agent。

### 4.3 并行执行模式

```python
def run_parallel(self, agents, input_data):
    from concurrent.futures import ThreadPoolExecutor
    
    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {executor.submit(agent.run, input_data): agent.name 
                   for agent in agents}
        
    results = {future: future.result() for future in futures}
    return results
```

### 4.4 监督模式

```
Supervisor Agent
  ├─ 任务分解
  ├─ 分配 Worker → Worker Agent A ──┐
  ├─ 分配 Worker → Worker Agent B ──┤ Supervisor 汇总
  ├─ 分配 Worker → Worker Agent C ──┘
  └─ 结果质量审核 → 最终输出
```

## 5. Agent 记忆管理

### 5.1 短期记忆（Short-term Memory）

使用消息历史列表实现，保存当前对话的上下文：

```python
class Memory:
    def __init__(self, max_history=20):
        self.messages = []         # 短期消息历史
        self.max_history = max_history
        self.long_term = {}        # 长期记忆（占位）
    
    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})
        # 截断过长的历史
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
```

### 5.2 长期记忆（Long-term Memory）

本框架预留了长期记忆接口，可接入向量存储：

```python
class Memory:
    def remember(self, key, value):
        """长期记忆：存储重要信息"""
        self.long_term[key] = value
    
    def recall(self, key):
        """长期记忆：回忆已存储信息"""
        return self.long_term.get(key)
    
    def semantic_search(self, query, top_k=3):
        """语义搜索占位 — 可接入向量数据库"""
        # TODO: 接入 Chroma/FAISS 等向量存储
        pass
```

### 5.3 共享记忆（Shared Memory）

多Agent 可通过 Orchestrator 的上下文池实现共享记忆：

```python
class AgentOrchestrator:
    def __init__(self):
        self.agents = {}
        self.shared_context = {}  # 所有 Agent 可读写
    
    def update_shared_context(self, key, value):
        self.shared_context[key] = value
```

## 6. Agent 框架实现总结（本项目的设计）

### 6.1 框架组件总览

```
agent_framework.py
├── Tool              — 工具封装：名称、描述、函数、参数schema
├── Memory            — 短期记忆（消息历史）+ 长期记忆接口
├── Agent             — 核心 Agent：think → act → observe → 循环
├── AgentOrchestrator — 协调器：路由、链式、并行、监督
└── 内置工具          — search_files, read_file, run_python 等
```

### 6.2 多Agent 代码审查应用架构

```
code_review_app.py
└── 使用 agent_framework.py 构建
    ├── Router Agent      — 分析需求，路由到对应审查 Agent
    ├── Linter Agent      — AST 静态分析 + 命名规范检查
    ├── Security Agent    — 危险函数、SQL注入、路径穿越检查
    ├── Performance Agent — 时间复杂度、内存泄漏分析
    └── Report Agent      — 汇总所有审查结果
```

### 6.3 工作流程

```
用户输入（文件路径/代码）
  ↓
Router Agent（分析输入 → 路由决策）
  ↓
 Router 判断：
  ├─ 需要风格检查 → Linter Agent ──┐
  ├─ 需要安全检查 → Security Agent ├── 并行执行
  └─ 需要性能分析 → Performance ───┘
  ↓
Report Agent（汇总所有审查结果）
  ↓
最终报告（包含问题数、严重程度、行号、修复建议）
↓
```

## 7. 与 CrewAI/AutoGPT/LangChain 的对比

### 7.1 框架对比总表

| 特性 | 本项目 | CrewAI | AutoGPT | LangChain |
|------|--------|--------|---------|-----------|
| 依赖 | 零外部依赖 | pydantic+langchain | 大量依赖 | langchain-core |
| 学习成本 | ~500行 | 中 | 低 | 高 |
| Agent 类 | 自定义 | Role-playing Agent | Goal-based | AgentExecutor |
| 工具系统 | Tool 类 | Tool 类 | 插件系统 | BaseTool |
| 多Agent | Orchestrator | Crew+Task | 无原生支持 | AgentExecutor |
| ReAct | 内置 | 内置 | 内置 | 内置 |
| 记忆管理 | 内置短+长 | 基础 | 向量存储 | 多种 Memory |
| LLM 接入 | 回调函数 | 默认集成 | 多种后端 | 多模型支持 |
| 扩展性 | 高（解耦） | 中 | 低 | 高 |
| 生产就绪 | 否（学习用） | 是 | 实验性 | 是 |

### 7.2 与 CrewAI 的对比

**CrewAI 的设计：**
```python
# CrewAI 方式 — 角色、任务、Crew
analyst = Agent(role="Analyst", goal="分析代码")
writer = Agent(role="Writer", goal="撰写报告")
task = Task(description="审查代码", agent=analyst)
crew = Crew(agents=[analyst, writer], tasks=[task])
result = crew.kickoff()
```

**本项目的设计：**
```python
# 本项目方式 — 更灵活、更轻量
linter = Agent(name="Linter", role="代码审阅者", ...)
orchestrator = AgentOrchestrator()
orchestrator.register_agent(linter)
result = orchestrator.run_parallel([linter], "审查代码")
```

**关键差异：**
- CrewAI 使用声明式配置（角色+任务+Crew），本项目使用编程式编排
- CrewAI 有内置的 Task 委托机制，本项目通过 Orchestrator 显式管理
- 本项目的 Tool 更轻量，无 pydantic 验证依赖

### 7.3 与 AutoGPT 的对比

**AutoGPT 的特点：**
- 基于目标的长期执行（给定一个目标，持续执行直到完成）
- 内建文件系统和向量记忆
- 插件生态系统
- 容易陷入循环（消耗大量 tokens）

**本项目的差异：**
- 更注重可控的 Agent 间协作
- 显式的路由和任务分派
- 适用于结构化的多步骤工作流

### 7.4 与 LangChain 的对比

**LangChain 的复杂性：**
```python
# LangChain 方式
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType

tool = Tool(name="search", func=search, description="搜索")
agent = initialize_agent([tool], llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
agent.run("问题")
```

**本项目的简洁性：**
```python
# 本项目方式
tool = Tool(name="search", description="搜索", func=search)
agent = Agent(name="Searcher", tools=[tool], llm_callable=my_llm)
agent.run("问题")
```

**关键差异：**
- LangChain 有巨大的抽象层（Chains, LCEL, Runnable），学习曲线陡峭
- 本项目保持扁平设计，每个组件职责明确
- LangChain 的生产功能（回调、监控、缓存）丰富，但增加了复杂度

### 7.5 何时用什么框架

| 场景 | 推荐框架 |
|------|----------|
| 学习 Agent 原理 | ✅ 本项目（从零实现，理解每个环节） |
| 快速原型 | ✅ 本项目或 CrewAI |
| 生产级 RAG | LangChain + LlamaIndex |
| 自动化任务 | AutoGPT 或自定义 |
| 多角色团队 | CrewAI 或本项目 |

## 8. 经验总结

### 8.1 设计原则

1. **框架与应用程序分离** — `agent_framework.py` 不包含任何业务逻辑，`code_review_app.py` 只使用框架 API
2. **LLM 解耦** — 通过回调函数 `llm_callable` 接入，可随时切换伪 LLM / 真实 API
3. **工具独立性** — 工具是纯函数，不依赖 Agent 内部状态
4. **组合优于继承** — Agent 组合 Tools，Orchestrator 组合 Agents

### 8.2 遇到的挑战

1. **ReAct 循环终止** — 需要限制最大步数防止无限循环
2. **并行结果合并** — 多个 Agent 的输出格式需要统一才能汇总
3. **工具安全** — `run_python` 需要 AST 沙箱防止恶意代码

### 8.3 扩展方向

- [ ] 接入真实 LLM（DeepSeek / OpenAI API）
- [ ] 向量记忆（FAISS / Chroma）
- [ ] Web 搜索工具
- [ ] 流式输出
- [ ] Agent 间消息传递
- [ ] 任务队列 + 异步执行
