# 多 Agent 协作模式

## 1. Orchestrator-Workers 模式

### 架构设计
```
        ┌──────────────┐
        │ Orchestrator  │  ← 任务分解、调度、合并
        └──────┬───────┘
       ┌───────┼───────┐
       ▼       ▼       ▼
  ┌────────┐┌────────┐┌────────┐
  │ Worker1││Worker2 ││Worker3 │
  │ (搜索) ││(代码)  ││(分析)  │
  └────────┘└────────┘└────────┘
```

### AutoGen 实现
```python
import autogen

config_list = [{"model": "gpt-4", "api_key": "..."}]

orchestrator = autogen.AssistantAgent(
    name="Orchestrator",
    llm_config={"config_list": config_list},
    system_message="你是协调者，将任务分解并分派给专家。"
)

worker_search = autogen.AssistantAgent(
    name="Searcher",
    llm_config={"config_list": config_list},
    system_message="你是搜索专家，负责查找信息。"
)

worker_code = autogen.AssistantAgent(
    name="Coder",
    llm_config={"config_list": config_list},
    system_message="你是代码专家，负责编写和调试代码。"
)

# 创建群组对话
groupchat = autogen.GroupChat(
    agents=[orchestrator, worker_search, worker_code],
    messages=[],
    max_round=12
)
manager = autogen.GroupChatManager(groupchat=groupchat)
```

### crewAI 实现
```python
from crewai import Agent, Task, Crew, Process

orchestrator = Agent(
    role="项目经理",
    goal="协调团队完成任务",
    backstory="你是有经验的项目管理者",
    allow_delegation=True
)

researcher = Agent(
    role="研究员",
    goal="收集和分析信息",
    tools=[search_tool]
)

writer = Agent(
    role="写手",
    goal="撰写高质量报告"
)

crew = Crew(
    agents=[orchestrator, researcher, writer],
    tasks=[research_task, write_task, review_task],
    process=Process.sequential  # 或 hierarchical
)
```

## 2. 辩论模式（多 Agent 互评）

### 结构
```python
agents = [debater_a, debater_b, debater_c, judge]

# 每轮：每个 Agent 发表观点 → 互相评论 → 修正立场
for round in range(3):
    for agent in agents[:-1]:  # 辩手发言
        response = agent.generate(arguments, feedback)
        all_arguments.append(response)
    
    # 裁判评述
    verdict = judge.generate(all_arguments, round)
```

### 典型应用
- **代码审查**：Developer → Reviewer → Tester 三角验证
- **文本评估**：多个评价维度各由一个 Agent 打分后综合
- **决策投票**：不同视角 Agent 分析后投票决定

## 3. 层级任务分解

```python
def hierarchical_decompose(task: str, depth=0, max_depth=3):
    if depth >= max_depth:
        return execute_leaf_task(task)
    
    # 分解当前任务
    subtasks = llm.invoke(f"将任务拆解为子任务：{task}")
    
    results = []
    for subtask in subtasks:
        # 递归分解/执行
        result = hierarchical_decompose(subtask, depth + 1, max_depth)
        results.append(result)
    
    # 合并结果
    return llm.invoke(f"合并子任务结果：{results}")
```

## 4. 共享记忆

```python
class SharedMemory:
    def __init__(self):
        self.short_term = []       # 短期对话历史
        self.long_term = {}        # 长期知识
        self.task_context = {}     # 任务上下文
    
    def add(self, key, value):
        self.long_term[key] = value
        self.short_term.append({"key": key, "value": value})
        if len(self.short_term) > 50:  # 滑动窗口
            self.short_term.pop(0)
    
    def query(self, key):
        return self.long_term.get(key, self._search_memory(key))
```

## 5. 冲突解决策略

```python
def resolve_conflict(agent_a_result, agent_b_result):
    """多 Agent 冲突解决"""
    # 方案1: 投票
    votes = [agent.vote(agent_a_result, agent_b_result) 
             for agent in all_agents]
    return agent_a_result if sum(votes) > len(votes)/2 else agent_b_result

    # 方案2: 仲裁 Agent
    arbiter = ArbiterAgent()
    return arbiter.decide(agent_a_result, agent_b_result)

    # 方案3: 置信度对比
    return agent_a if agent_a.confidence > agent_b.confidence else agent_b
```

## 6. Agent 间通信协议

### 消息格式
```json
{
  "from": "agent_search",
  "to": "agent_analysis",
  "type": "task/result/question",
  "payload": {
    "task_id": "t-001",
    "content": "...",
    "metadata": {"priority": "high"}
  },
  "timestamp": 1704067200
}
```

### 协议核心要素
- **消息路由**：点对点 / 广播 / 话题订阅
- **序列化**：JSON / Protocol Buffers
- **同步方式**：同步 RPC / 异步消息队列
- **超时重试**：TTL + 重试策略
- **认证鉴权**：Agent 身份验证

## 总结
多 Agent 协作不是简单堆叠 LLM，而是设计一套通信、分工、记忆和冲突解决的完整机制。Orchestrator-Workers 适合明确分工的任务，辩论模式适合需要多角度验证的场景。选择哪种模式取决于任务本身的协作需求。
