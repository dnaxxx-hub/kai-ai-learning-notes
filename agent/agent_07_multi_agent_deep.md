# AI Agent #7：多智能体协作架构深度实践

> 学习日期：2026-05-19
> 前置：agent_01~06（框架对比→工具调用→RAG→记忆系统→多Agent→安全对齐）

## 1. 多Agent通信模式

### 1.1 广播 (Broadcast)
```
Agent A → [Bus] → Agent B, Agent C, Agent D
```
- 所有Agent收到相同消息
- 适用于：系统状态广播、心跳、全局通知

### 1.2 点对点 (Direct)
```
Agent A → [Router] → Agent B
```
- 指定目标Agent
- 适用于：任务委派、查询、响应

### 1.3 发布-订阅 (Pub/Sub)
```
Agent A → [Topic: "price_alert"] → Agent B, Agent C
Agent D → [Topic: "trade_signal"] → Agent E
```
- 按主题分类
- 适用于：事件驱动架构

### 1.4 共享黑板 (Blackboard)
```
                   ┌──────────┐
Agent A ──write──→ │          │ ←──read── Agent B
Agent C ──write──→ │ Blackboard │ ←──read── Agent D
                   │          │
                   └──────────┘
```
- 所有Agent通过共享状态通信
- 适用于：协作求解、渐进式结果汇聚

## 2. 现有系统分析：当前Kai的Agent架构

当前架构（Phase 3完成）：
```
Gateway → Orchestrator → Engine Registry → Storage Layer
                  ↓
            System Bridge (消息总线/17个系统)
```

问题是：**所有Agent在同一个会话上下文中运行**，缺乏真正的多Agent隔离和专用通信协议。

## 3. 设计：多Agent消息协议

```python
# agent_protocol.py — 多Agent通信协议
"""
消息格式：
{
    "id": "msg_<uuid>",
    "from": "agent_quant",
    "to": "agent_learn",       # 可选：None=broadcast
    "topic": "parameter_update",
    "type": "request|response|event|command",
    "payload": {...},
    "timestamp": 1234567890.0,
    "ttl": 30,                 # 生存时间（秒）
    "reply_to": "msg_<uuid>"   # 可选：回复链
}
"""
```

### 3.1 Agent 角色定义

| Agent | 职责 | 消息类型 |
|-------|------|---------|
| `agent_gateway` | 消息入口、意图解析 | event |
| `agent_orchestrator` | 任务调度、链式执行 | command |
| `agent_quant` | 量化策略、信号生成 | request/response |
| `agent_learn` | 知识学习、笔记整理 | request/response |
| `agent_curiosity` | 探索、假设生成 | event |
| `agent_monitor` | 系统监控、报警 | event |
| `agent_memory` | 记忆管理、检索 | request/response |

### 3.2 通信优先级

```
P0: command (必须立即处理)
P1: request/response (需要回复)
P2: event (可异步处理)
P3: broadcast (低优先级通知)
```

## 4. 实践：轻量多Agent调度器

```python
# multi_agent_scheduler.py — 在现有orchestrator之上增强
"""
核心改进：
1. 消息队列（按优先级）
2. Agent注册表（已知的Agent列表+能力描述）
3. 路由表（消息类型→处理Agent）
4. 超时/重试机制
"""
```

### 4.1 路由表设计

```python
ROUTES = {
    # 用户意图 → 处理Agent
    "trade_signal": ["agent_quant"],
    "market_analysis": ["agent_quant", "agent_curiosity"],
    "learn_topic": ["agent_learn"],
    "system_health": ["agent_monitor"],
    "memory_query": ["agent_memory"],
    # 复合意图 → Orchestrator调度
    "strategy_optimization": [
        "agent_orchestrator",  # 编排
        "agent_quant",         # 执行回测
        "agent_learn",         # 记录学习
        "agent_curiosity"      # 生成新假设
    ],
}
```

### 4.2 消息生命周期

```
客户端 → Gateway → [Queue] → Orchestrator → [Route] → Agent A
                                                         ↓
                                                    执行任务
                                                         ↓
                                                    [Result Queue]
                                                         ↓
Agent B ← [Route] ← Orchestrator ← [Result] ← Agent A回复
```

## 5. 与现有系统的集成点

当前 system_bridge.py 已经是一个消息总线，但缺少：
1. **Agent身份** — 每条消息应有来源Agent ID
2. **优先级队列** — 所有消息同等对待
3. **超时机制** — 无响应超时处理
4. **重试策略** — 失败后自动重试

### 5.1 增强方案

```python
# 在 system_bridge.py 基础上扩展
class AgentMessage:
    def __init__(self, agent_id, topic, payload, priority=P2, ttl=30):
        self.id = str(uuid.uuid4())[:8]
        self.agent_id = agent_id
        self.topic = topic
        self.payload = payload
        self.priority = priority  # P0/P1/P2/P3
        self.ttl = ttl
        self.created_at = time.time()
    
    @property
    def expired(self):
        return time.time() - self.created_at > self.ttl

class MultiAgentBus:
    """在 system_bridge 之上增加多Agent调度"""
    
    def __init__(self):
        self.agents = {}     # agent_id → handler
        self.routes = {}     # topic → [agent_ids]
        self.queue = []      # 优先级队列
        self.pending = {}    # msg_id → callback (用于request/response)
    
    def register_agent(self, agent_id, handler, capabilities=None):
        self.agents[agent_id] = handler
    
    def register_route(self, topic, agent_ids):
        self.routes[topic] = agent_ids
    
    def send(self, message: AgentMessage):
        # 按优先级插入队列
        heapq.heappush(self.queue, (message.priority, time.time(), message))
    
    def process(self):
        """处理队列中的消息"""
        while self.queue:
            _, _, msg = heapq.heappop(self.queue)
            if msg.expired:
                continue
            targets = self.routes.get(msg.topic, list(self.agents.keys()))
            for target in targets:
                if target in self.agents:
                    # 异步派发
                    result = self.agents[target](msg)
                    if msg.reply_to and msg.reply_to in self.pending:
                        self.pending[msg.reply_to](result)
```

## 6. 实战案例：量化策略优化（多Agent协作）

### 当前单Agent流程
```
用户要求 → quant 跑回测 → 返回结果
```

### 多Agent增强流程
```
用户要求 → Gateway → Orchestrator
    ↓
Orchestrator 调度链:
    1. agent_quant: "当前策略表现如何？"
    2. agent_curiosity: "有什么可以改进的假设？"
    3. agent_quant: "用好奇心假设跑回测"
    4. agent_learn: "记录最佳参数到知识库"
    5. agent_memory: "与历史表现对比"
    ↓
返回综合报告
```

### 代码骨架

```python
def optimize_strategy_chain(strategy_name):
    """多Agent协作优化策略"""
    
    # Step 1: 查询当前表现
    perf_result = agent_quant.query(f"performance of {strategy_name}")
    
    # Step 2: 好奇心生成假设
    hypotheses = agent_curiosity.explore(
        context=f"strategy {strategy_name} perf: {perf_result}",
        n_hypotheses=3
    )
    
    # Step 3: 并行测试假设
    results = []
    for h in hypotheses:
        result = agent_quant.backtest(strategy_name, h.params)
        results.append(result)
    
    # Step 4: 选择最佳
    best = max(results, key=lambda r: r.sharpe_ratio)
    
    # Step 5: 学习记录
    agent_learn.record(
        topic=f"strategy_optimization/{strategy_name}",
        content={"hypotheses": hypotheses, "best": best}
    )
    
    return best
```

## 7. 评估指标

| 维度 | 当前架构 | 多Agent增强后 |
|------|---------|--------------|
| 消息路由 | 广播式 | 按主题路由 |
| 优先级 | 无 | P0~P3四级 |
| 超时处理 | 无 | TTL+超时清理 |
| 重试 | 无 | 自动重试×3 |
| Agent隔离 | 共享上下文 | 独立handler |
| 可观测性 | 仅日志 | 消息追踪链 |

## 8. 下一步

- [ ] 将 multi_agent_scheduler.py 实际编码并集成到现有系统
- [ ] 定义完整的路由表（覆盖11个系统）
- [ ] 消息追踪和调试面板
- [ ] 与 system_bridge.py 无缝对接
- [ ] 压力测试（模拟大量消息）

---

**总结**：多Agent架构的核心不是"多个Agent"，而是"Agent间有意义的通信协议"。当前system_bridge已经提供了总线基础，需要在上面增加消息优先级、路由、超时处理层。
