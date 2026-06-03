# Agent 评估与监控

## 1. 评估维度

### 核心指标
| 维度 | 指标 | 计算方法 |
|------|------|----------|
| 准确率 | Answer Accuracy | 正确答案比例 |
| 召回率 | Recall | 相关结果覆盖比例 |
| 工具正确率 | Tool Correctness | 工具调用正确比例 |
| 完成率 | Task Completion | 任务完整执行比例 |
| 效率 | Efficiency | 完成步数 / 耗时 |
| 鲁棒性 | Robustness | 异常输入下的表现 |

### 实现
```python
class AgentMetrics:
    def __init__(self):
        self.metrics = {
            "accuracy": [],
            "tool_correctness": [],
            "completion_rate": [],
            "avg_steps": [],
            "avg_latency": []
        }
    
    def log_interaction(self, entry: dict):
        """记录单次交互"""
        self.metrics["accuracy"].append(entry.get("is_correct", 0))
        self.metrics["tool_correctness"].append(
            1 if entry.get("tool_correct") else 0
        )
    
    def summary(self) -> dict:
        return {
            name: sum(vals)/len(vals) if vals else 0
            for name, vals in self.metrics.items()
        }
```

### 数据集构建
```python
TEST_CASES = [
    {
        "input": "搜索最近的AI新闻并总结",
        "expected_tools": ["search_web", "summarize"],
        "expected_steps": 3,
        "ground_truth": "..."
    },
    # 覆盖：正常 / 边界 / 异常 / 拒绝
]
```

## 2. 自动化评测

### LLM-as-Judge
```python
def llm_judge(question: str, answer: str, expected: str) -> dict:
    """用 LLM 评估答案质量"""
    prompt = f"""评估以下回答质量：
问题：{question}
预期：{expected}
实际：{answer}

请从以下维度打分（1-5分）：
1. 准确性：答案是否正确
2. 完整性：是否回答了所有要点
3. 相关性：是否切题
4. 清晰度：表述是否清晰易懂

输出JSON格式。"""
    
    result = llm.invoke(prompt)
    return json.loads(result.content)
```

### 对比评测（A/B Test）
```python
def ab_test(agent_a, agent_b, test_cases):
    results = {"a": [], "b": []}
    for case in test_cases:
        result_a = agent_a.invoke(case["input"])
        result_b = agent_b.invoke(case["input"])
        
        winner = llm.judge_preference(
            case["input"], result_a, result_b
        )
        results[winner].append(case)
    
    win_rate = len(results["a"]) / len(test_cases)
    print(f"Agent A 胜率: {win_rate:.2%}")
```

## 3. 追踪（OpenTelemetry）

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp import OTLPSpanExporter

tracer = trace.get_tracer("agent.tracer")

class TracedAgent:
    def invoke(self, input: str):
        with tracer.start_as_current_span("agent_run") as span:
            span.set_attribute("input", input)
            
            # 追踪思考过程
            with tracer.start_span("thinking") as think_span:
                thought = self.think(input)
                think_span.set_attribute("thought", thought)
            
            # 追踪工具调用
            with tracer.start_span("tool_call") as tool_span:
                result = self.call_tool(thought)
                tool_span.set_attribute("tool_result", str(result))
            
            span.set_attribute("output", result)
            return result
```

### 关键 Trace 点
- Agent 启动 / 结束
- 每次 LLM 调用（含 token 数）
- 每次工具调用（含耗时）
- ReAct 循环每步
- 错误 / 异常

## 4. 日志系统

```python
import logging
import json
from datetime import datetime

class AgentLogger:
    def __init__(self, log_dir="./logs"):
        self.logger = logging.getLogger("agent")
        handler = logging.FileHandler(f"{log_dir}/agent.log")
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def log_turn(self, session_id, turn, msg_type, content):
        """结构化日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "turn": turn,
            "type": msg_type,  # user / thought / tool_call / observation / response / error
            "content": content
        }
        self.logger.info(json.dumps(entry, ensure_ascii=False))
    
    def replay_session(self, session_id):
        """回放指定会话"""
        entries = self._query(f"session_id={session_id}")
        for e in entries:
            self._render(e)  # 可视化回放
```

### 调用链可视化
```json
{
  "session": "sess-123",
  "chain": [
    {"step": 1, "type": "thought", "content": "我需要先搜索...", "tokens": 150},
    {"step": 2, "type": "tool", "tool": "search_web", "args": {"q": "AI"}, "duration_ms": 320},
    {"step": 3, "type": "observation", "content": "搜索结果...", "tokens": 512},
    {"step": 4, "type": "response", "content": "根据搜索结果...", "tokens": 200}
  ]
}
```

## 5. 安全审计

```python
class SecurityAuditor:
    def __init__(self):
        self.suspicious_patterns = [
            r"DROP TABLE", r"rm -rf", r"eval\(",
            r"sudo", r"chmod 777"
        ]
        self.access_log = []
    
    def audit_tool_call(self, user: str, tool: str, args: dict):
        """审计每次工具调用"""
        # 检测恶意模式
        for pattern in self.suspicious_patterns:
            if re.search(pattern, str(args), re.IGNORECASE):
                self._alert(f"检测到可疑操作: {pattern}", user, tool, args)
                return False
        
        # 记录访问
        self.access_log.append({
            "user": user,
            "tool": tool,
            "args": args,
            "time": datetime.now(),
            "allowed": True
        })
        return True
    
    def generate_audit_report(self, user: str = None):
        """生成安全审计报告"""
        logs = self.access_log
        if user:
            logs = [l for l in logs if l["user"] == user]
        
        return {
            "total_calls": len(logs),
            "denied": sum(1 for l in logs if not l["allowed"]),
            "tools_used": set(l["tool"] for l in logs),
            "suspicious_alerts": self.alerts
        }
```

## 评估仪表盘

```python
class Dashboard:
    def render(self):
        metrics = self.agent.get_metrics()
        return f"""
        ┌────── Agent Dashboard ──────┐
        │ 准确率:      {metrics['accuracy']:.1%}   │
        │ 工具正确率:  {metrics['tool_correctness']:.1%}   │
        │ 完成率:      {metrics['completion_rate']:.1%}   │
        │ 平均步数:    {metrics['avg_steps']:.1f}        │
        │ 平均延迟:    {metrics['avg_latency']:.0f}ms    │
        │ 调用次数:    {metrics['total_calls']}          │
        └──────────────────────────────┘
        """
```

## 总结
评估监控是 Agent 产品化的基石。准确率等核心指标提供量化反馈，LLM-as-Judge 实现规模化自动评测，OpenTelemetry 追踪定位问题，结构化日志支撑调试复盘，安全审计保障可控性。建立完善的评估体系比优化 Agent 本身更重要。
