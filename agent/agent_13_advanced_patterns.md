# Agent 高级模式

## 1. Reflection（自我反思）

### Reflect 模式
```python
class ReflectiveAgent:
    def __init__(self):
        self.history = []
    
    def run_with_reflection(self, task: str):
        """执行 + 反思循环"""
        # Step 1: 执行
        result = self.execute(task)
        self.history.append({"task": task, "result": result})
        
        # Step 2: 自我反思
        reflection = self.reflect(result, task)
        
        # Step 3: 改进
        if reflection["score"] < 0.7:
            improved = self.improve(result, reflection["feedback"])
            self.history.append({"reflection": reflection, "improved": improved})
            return improved
        
        return result
    
    def reflect(self, result, task):
        """LLM 自我评估"""
        return llm.invoke(f"""评估你的回答：
任务：{task}
回答：{result}

请打分（0-1）并给出改进建议。
格式：{{"score": 0.8, "feedback": "...", "issues": [...]}}""")
    
    def improve(self, result, feedback):
        return llm.invoke(f"根据反馈改进回答：\n原回答：{result}\n反馈：{feedback}")
```

### 多轮反思
```python
for i in range(3):  # 最多3轮反思
    result = agent.execute(task + f"\n{last_feedback}")
    reflection = agent.reflect(result, task)
    
    if reflection["score"] >= 0.85:
        break
    last_feedback = reflection["feedback"]
```

## 2. Tool-Use 执行模式

```python
class ToolUsePattern:
    """Plan → Select → Execute → Observe → Adapt"""
    
    def plan(self, task):
        tools = self.discover_tools(task)
        plan = llm.invoke(f"任务：{task}\n可用工具：{tools}\n制定执行计划")
        return json.loads(plan)
    
    def execute_plan(self, plan):
        results = []
        for step in plan["steps"]:
            observation = self.call_tool(step["tool"], step["args"])
            results.append({"step": step, "observation": observation})
            
            if self.need_replan(observation, plan):
                plan = self.replan(plan, observation)
        return self.synthesize(results)
```

## 3. Planning（计划分解）

### 任务树
```python
class TaskTree:
    """将任务递归分解为任务树"""
    def __init__(self, goal):
        self.root = TaskNode(goal)
    
    def decompose(self, node, depth=0):
        if depth >= 3 or self.is_atomic(node):
            return
        
        subtasks = llm.invoke(f"拆分任务为子任务：{node.goal}")
        for subtask in subtasks:
            child = TaskNode(subtask, parent=node)
            node.add_child(child)
            self.decompose(child, depth + 1)
    
    def execute(self):
        """后序遍历执行"""
        def dfs(node):
            if node.is_leaf():
                return llm.invoke(node.goal)
            results = [dfs(child) for child in node.children]
            return llm.merge(node.goal, results)
        
        return dfs(self.root)
```

### 动态重规划
```python
def replan_if_needed(current_plan, observation):
    """当环境反馈与预期不符时重新规划"""
    if observation.has_unexpected_result():
        new_plan = llm.invoke(f"""
        原计划：{current_plan}
        观察结果：{observation}
        请重新规划。
        """)
        return new_plan
    return current_plan
```

## 4. Multi-Agent（协作讨论）

### 辩论式讨论
```python
class DebatePattern:
    def debate(self, topic, agents, rounds=3):
        views = {a: a.initial_view(topic) for a in agents}
        
        for round in range(rounds):
            for agent in agents:
                views[agent] = agent.rebut(
                    topic, views[agent], 
                    {a: v for a, v in views.items() if a != agent}
                )
        
        # 综合判决
        return self.synthesize(views)
```

## 5. Agent-as-a-Service

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class AgentService:
    """将 Agent 包装为微服务"""
    def __init__(self):
        self.sessions = {}  # session_id → Agent
    
    async def process(self, session_id: str, message: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = ReflectiveAgent()
        
        agent = self.sessions[session_id]
        return await agent.run_with_reflection(message)

agent_svc = AgentService()

@app.post("/agent/chat")
async def chat(request: Request):
    return await agent_svc.process(
        request.session_id, request.message
    )

@app.get("/agent/status/{session_id}")
def get_status(session_id: str):
    return {"status": "running", "turns": agent_svc.get_turns(session_id)}
```

## 6. 流式输出与事件驱动

### 流式输出
```python
async def stream_agent_response(task: str):
    """SSE 流式输出 Agent 思考过程"""
    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'task': task})}\n\n"
        
        async for event in agent.run_async(task):
            if event["type"] == "thought":
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "tool_call":
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "observation":
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] == "final":
                yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 事件驱动架构
```python
class EventDrivenAgent:
    def __init__(self):
        self.handlers = {}
    
    def on(self, event: str):
        """注册事件处理器"""
        def decorator(handler):
            self.handlers.setdefault(event, []).append(handler)
            return handler
        return decorator
    
    async def emit(self, event: str, data: dict):
        """触发事件"""
        for handler in self.handlers.get(event, []):
            await handler(data)
    
    async def run(self, task):
        await self.emit("task:start", {"task": task})
        
        plan = await self.plan(task)
        await self.emit("plan:ready", {"plan": plan})
        
        for step in plan:
            await self.emit("step:start", {"step": step})
            result = await self.execute(step)
            await self.emit("step:complete", {"step": step, "result": result})
        
        await self.emit("task:complete", {"result": ...})

# 使用
agent = EventDrivenAgent()

@agent.on("tool_call")
async def log_tool_call(data):
    logger.info(f"工具调用: {data}")

@agent.on("error")
async def alert_on_error(data):
    if data["critical"]:
        send_alert(data)
```

## 模式组合

```
Reflection + Tool-Use + Planning + Multi-Agent = 完整 Agent 系统
       │           │           │           │
       ▼           ▼           ▼           ▼
   自我改进     能力边界    结构化执行    协作智能
```

## 总结
高级模式不是单独使用的，而是组合形成复合架构。Reflection 保证质量，Tool-Use 扩展能力，Planning 处理复杂任务，Multi-Agent 提供协作，AaaS 提供服务化能力，事件驱动支持实时交互。实际项目中根据需求灵活组合这些模式。
