# AI Agent 框架对比深度分析

## 1. 三框架哲学层次对比

### 1.1 核心抽象

| 维度 | LangChain/LangGraph | CrewAI | AutoGen |
|------|---------------------|--------|---------|
| 主要抽象 | **状态图（Graph）** | **角色与任务（Role+Task）** | **对话（Conversation）** |
| 控制流模型 | 显式有向图 | 顺序/层级过程 | 自由对话 |
| 状态管理 | 显式 StateGraph | 隐式任务上下文 | 对话历史 |
| 协作方式 | 节点与边 | 角色间任务依赖 | 群聊消息传递 |
| 可观测性 | LangSmith（一流） | 日志/第三方集成 | 基础 tracing |

### 1.2 框架设计哲学

```
LangGraph:             CrewAI:               AutoGen:
"一切皆是图"           "一切皆是团队"         "一切皆是对话"

你定义节点和边        你定义角色和任务        你定义参与者和消息
运行时执行图          运行时调度角色        运行时管理对话
状态显式流动          上下文隐式传递        消息显式交换
```

### 1.3 适用决策树

```
你的问题需要多个 LLM 调用吗？
├── 否 → 直接用 LLM API，别用框架
└── 是 → 需要多少个"思考角色"？
    ├── 1 个 → 单人 agent
    │   ├── 路径已知 → LangGraph（可控）
    │   └── 探索式 → AutoGen（灵活）
    └── 多个 → 多 agent 系统
        ├── 角色明确（分析师/写手/审核）
        │   └── CrewAI（天然映射）
        ├── 需要精确控制流程
        │   └── LangGraph（显式图）
        └── 解空间未知需要探索
            └── AutoGen（群聊讨论）
```

---

## 2. LangGraph 深度剖析

### 2.1 状态图模型

```python
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    query: str
    sources: List[Dict]
    analysis: str
    report: str

workflow = StateGraph(AgentState)

# 定义节点（每个节点是一个函数）
workflow.add_node("search", search_node)       # 搜索工具
workflow.add_node("analyze", analyze_node)      # 分析结果
workflow.add_node("synthesize", synthesize_node) # 合成报告

# 定义边
workflow.add_edge("search", "analyze")
workflow.add_edge("analyze", "synthesize")
workflow.add_conditional_edges(
    "synthesize",
    needs_review,  # 条件函数：返回 "review" 或 "end"
    {"review": "review", "end": END}
)
workflow.add_node("review", review_node)
workflow.add_edge("review", "synthesize")  # 循环

# 编译可执行图
app = workflow.compile()
```

**关键特性：**
- **显式控制流**：节点-边-条件边的图定义
- **共享状态**：所有节点读写同一个 TypedDict
- **可 checkpoint**：每个节点后可保存/恢复状态
- **条件边**：根据输出值路由到不同节点（如需要人工审查）

### 2.2 LangSmith 观察层

```
每次 agent 运行生成：
┌──────────────────────────────────────────────┐
│ Run Tree                                      │
│  ├─ search node (0.8s, 2 tools calls)         │
│  │   ├─ web_search (0.4s, 5 results)          │
│  │   └─ kb_search (0.3s, 3 results)           │
│  ├─ analyze node (1.2s, LLM call gpt-4o)     │
│  ├─ synthesize node (2.1s, LLM call)          │
│  │   └─ review needed → condition edge        │
│  └─ review node (0.5s, human approval)        │
│                                               │
│  Total: 4.6s, 3 LLM calls, 2 tool calls       │
│  12400 tokens, $0.18 cost                     │
└──────────────────────────────────────────────┘
```

### 2.3 LangGraph 特殊节点

| 节点类型 | 用途 |
|----------|------|
| **ToolNode** | 执行工具调用 |
| **AgentNode** | LLM 推理+决策 |
| **HumanNode** | 等待人工审批 |
| **SubAgentNode** | 嵌套子图 |
| **MapNode** | 并行分支（如同时搜索多个来源） |

---

## 3. CrewAI 深度剖析

### 3.1 角色驱动的多 Agent 系统

```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(
    role="Senior Research Analyst",
    goal="Find comprehensive, accurate information",
    backstory="Expert researcher with deep analytical skills",
    tools=[web_search, arxiv_search, kb_tool],
    allow_delegation=True,  # 可以委托其他 agent
    verbose=True,
)

writer = Agent(
    role="Technical Writer",
    goal="Create clear, structured reports from research",
    backstory="Skilled at synthesizing complex topics",
    tools=[format_tool],
)

# 任务定义可以包含 context（依赖其他任务的结果）
research_task = Task(
    description="Research: {topic}",
    expected_output="Comprehensive research notes with citations",
    agent=researcher,
)

synthesis_task = Task(
    description="Synthesize into a structured report",
    expected_output="Report with executive summary and findings",
    agent=writer,
    context=[research_task],  # 依赖 research_task 的输出
)

# 三种 Process 类型
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, synthesis_task],
    process=Process.sequential,  # sequential | hierarchical | consensual
)
```

### 3.2 三种 Process 模式

| Process | 描述 | 使用场景 |
|---------|------|----------|
| **sequential** | 任务按顺序由指定 agent 执行 | 流水线（搜索→分析→输出） |
| **hierarchical** | 一个 manager agent 分配任务 | 需动态决策谁做什么 |
| **consensual** | agent 共同讨论达成一致 | 需要 consensus 的决策 |

### 3.3 委托与协作

CrewAI 的 `allow_delegation=True` 使得 agent 可以：
- 询问其他 agent 补充信息
- 将子任务委托给更专业的 agent
- 交叉验证结果

**缺陷：**
- 不可预测的通信开销
- 复杂的控制流不透明
- 非结构化对话可能跑偏

---

## 4. AutoGen 深度剖析

### 4.1 对话式多 Agent 架构

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat

researcher = AssistantAgent(
    name="Researcher",
    system_message="You search and gather information...",
    llm_config={"model": "gpt-4o"},
)

analyst = AssistantAgent(
    name="Analyst",
    system_message="You analyze information, identify patterns...",
    llm_config={"model": "gpt-4o"},
)

writer = AssistantAgent(
    name="Writer",
    system_message="You synthesize findings into reports...",
    llm_config={"model": "gpt-4o"},
)

# 用户代理 - 处理工具调用
user_proxy = UserProxyAgent(
    name="User",
    human_input_mode="NEVER",
    code_execution_config={"work_dir": "coding"},
)

# Group Chat
groupchat = GroupChat(
    agents=[user_proxy, researcher, analyst, writer],
    messages=[],
    max_round=20,  # 防止无限对话
)

manager = GroupChatManager(
    groupchat=groupchat,
    llm_config={"model": "gpt-4o"},
)

# 开始对话
user_proxy.initiate_chat(
    manager,
    message="Research quantum computing advances",
)
```

### 4.2 v0.4 的重大变化

AutoGen 在 v0.4 中全面重构：

| 旧版本 | v0.4+ |
|--------|-------|
| 单进程 | 分布式 actor 模型 |
| 单一对话模式 | AgentChat + Core API |
| 有限伸缩性 | 可水平扩展 |
| 同步通信 | 异步消息传递 |

### 4.3 关键设计模式

**代码执行代理：**
- UserProxyAgent 内置沙箱代码执行能力
- 适合：数据分析 Agent、代码生成 Agent

**Agent 间争论：**
- 多个 Agent 扮演不同角色，通过争论提高输出质量
- 例如：Coder + Critic + Reviewer

**人机协作：**
- `human_input_mode="ALWAYS"` 可在关键决策点请求人工介入

---

## 5. 性能与成本对比

### 5.1 基准测试（100 次查询）

| 指标 | LangGraph | CrewAI | AutoGen |
|------|-----------|--------|---------|
| 平均延迟 | 8.2s | 11.4s | 14.8s |
| P95 延迟 | 15.1s | 22.3s | 31.2s |
| 成功率 | 94% | 89% | 82% |
| 平均 tokens | 12,400 | 18,600 | 24,200 |
| 每次成本 | $0.18 | $0.27 | $0.35 |

### 5.2 为什么 AutoGen 更贵？

```
Agent 间通信的开销：
CrewAI research → writer: "Here are the findings... (600 tokens)"
AutoGen:
  Researcher: "I found these papers... (400 tokens)"
  Analyst: "Interesting. I notice the key insight is... (300 tokens)"
  Writer: "Based on your analysis... (500 tokens)"
  ...
  实际有用输出只有 final report (800 tokens)
  但中间对话产生了 5000+ tokens
```

### 5.3 开发者体验

| 维度 | LangGraph | CrewAI | AutoGen |
|------|-----------|--------|---------|
| 学习曲线 | 陡峭 | 适中 | 适中 |
| 首次 agent 时间 | 6h | 3h | 5h |
| 代码量 | 420 行 | 180 行 | 240 行 |
| 调试难度 | 中（StateGraph 可回溯） | 易（角色明确） | 难（对话不可预测） |

---

## 6. 多 Agent 协作模式

### 6.1 五种协作模式

```
1. 管道模式（Pipeline）
   A → B → C → D
   顺序流水线，每个 agent 完成一步

2. 扇出/汇聚（Fan-out / Gather）
       → B →
   A → → C → → E
       → D →
   并行处理+结果汇聚

3. 主管/工人（Supervisor/Worker）
       S
      /|\
     A B C
   主管分配任务给 worker

4. 辩论模式（Debate）
   A ←→ B ←→ C
   多个 agent 相互讨论迭代

5. 分层（Hierarchical）
   S1 → S2 → S3
        ├─ A   ├─ D
        ├─ B   ├─ E
        └─ C   └─ F
   多级主管
```

### 6.2 选择建议

| 问题类型 | 推荐模式 | 原因 |
|----------|----------|------|
| 信息检索+报告生成 | 管道 | 步骤明确 |
| 代码审查 | 辩论 | 多视角提高质量 |
| 内容生产系统 | 扇出/汇聚 | 并行提升效率 |
| 客服系统 | 主管/工人 | 路由到专业 agent |
| 复杂业务审批 | 分层 | 逐级审核 |

### 6.3 常见陷阱

1. **过度通信**：agent 间消息太多 → 成本暴涨
2. **反馈循环**：agent 陷入无限争论
3. **角色重叠**：多个 agent 做类似事情
4. **上下文丢失**：长对话丢失历史信息
5. **延迟累积**：每个 agent 串行等待

---

## 7. 实战建议

### 7.1 启动策略

```
Step 1: 确定你的问题是否需要多 agent
  - 单 agent 能搞定？用单 agent
  - 需要多个专业角色？考虑多 agent

Step 2: 选择框架
  - 流程清晰 → LangGraph
  - 角色明确 → CrewAI
  - 探索研究 → AutoGen

Step 3: 先简单后复杂
  - 先跑通最简单的 2-agent 系统
  - 逐渐添加复杂度和角色
  - 每次加一个角色都要重新评估成本

Step 4: 建立 eval 管道
  - 没 eval 就没有改进方向
  - 每次修改都回测
```

### 7.2 决策矩阵

```
            ┌──────────────┬──────────────┬──────────────┐
            │   LangGraph   │   CrewAI      │   AutoGen    │
├────────────┼──────────────┼──────────────┼──────────────┤
│ 客服 agent  │   🟡         │   ✅           │   ⬜          │
│ 研究助手    │   ✅          │   ⬜           │   ✅          │
│ 代码 agent  │   🟡         │   ⬜           │   ✅          │
│ 内容生产    │   🟡         │   ✅           │   ⬜          │
│ 审批工作流  │   ✅          │   🟡           │   ⬜          │
│ 合规/审计   │   ✅          │   ⬜           │   ⬜          │
│ 原型验证    │   ⬜         │   ✅           │   🟡          │
│ 多步推理    │   🟡         │   ⬜           │   ✅          │
├────────────┼──────────────┼──────────────┼──────────────┤
│ ✅ = 推荐   🟡 = 可用   ⬜ = 不推荐     │
└────────────────────────────────────────────┘
```
