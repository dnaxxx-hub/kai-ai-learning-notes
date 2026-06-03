# AI Agent #5：多Agent协作

> 2026-05-17
> 前置知识：Agent 架构（#1）、工具调用（#2）、记忆系统（#4）

## 为什么需要多Agent

单一 Agent 的限制：
1. **上下文窗口有限** — 一个 LLM 的上下文装不下整个系统的所有知识
2. **工具集冲突** — 文件读写 + 网络搜索 + 代码执行放一起太混乱
3. **单点失败** — 一个 Agent 出问题整个系统瘫
4. **认知瓶颈** — 需要同时做规划和执行时容易顾此失彼

**多Agent 模式**把"一个全能 Agent"拆成 "多个专业 Agent + 协调层"。

## 三种协作模式

### 1. 主管-工人模式（Orchestrator-Workers）

```
用户 → [Orchestrator] ─┬→ Worker A（搜索）
                       ├→ Worker B（代码）
                       └→ Worker C（文件）
```

**我们的实现**（`orchestrator_workers.py`，2026-04-29部署）：
- Orchestrator 收到用户消息 → 意图解析 → 拆解子任务
- Workers 各自处理 → 结果汇总
- 适合：需要多步操作的复杂任务

**代码骨架**：
```python
class Orchestrator:
    def handle(self, message):
        intent = self.parse_intent(message)    # 意图识别
        plan = self.decompose(intent)          # 拆解子任务
        results = {}
        for step in plan:
            worker = self.select_worker(step)
            results[step.id] = worker.run(step)  # 并行或串行
        return self.synthesize(results)          # 合并结果
```

### 2. 对等方式（Peer-to-Peer）

```
Agent A ←→ Agent B
   ↕        ↕
Agent C ←→ Agent D
```

- 没有中央协调者
- 通过消息总线通信
- 适合：监控系统、传感器网络、数据管道

**我们的实现**（`system_bridge.py`，Phase 3）：
- 17个系统通过消息总线互连
- 每个系统独立运行，通过总线发送/消费消息
- 好奇心→监控→量化→回测 全链路闭环

### 3. 辩论模式（Debate）

```
Agent A（正）→ 观点A
Agent B（反）→ 观点B
            ↓
        [仲裁者] → 综合观点
```

- 多个 Agent 各自推理 → 互相辩论
- 适合：需要多角度分析的复杂决策
- 效果：减少单一 Agent 的偏见

## 通信机制

### 消息总线（我们的实现）

**system_bridge.py** 的核心设计：

```python
# 总线消息格式
{
    "from": "curiosity",        # 发送者
    "to": "quant",              # 接收者
    "type": "parameter_suggest",# 消息类型
    "payload": {...},           # 具体内容
    "timestamp": "2026-05-17"
}
```

**通道列表**：
| 通道 | 角色 | 消息类型 |
|:----|:----|:--------|
| curiosity | 探索引擎 | hypothesis, research_question |
| distill | 知识蒸馏 | feature_insight, pattern_rule |
| quant | 量化交易 | signal, trade_suggestion |
| backtest | 回测引擎 | backtest_result, param_rank |
| status | 系统状态 | health_check, heartbeats |
| monitor | 实时监控 | price_alert, risk_warning |

### 同步 vs 异步

| | 同步（RPC） | 异步（消息队列） |
|:--|:----------|:--------------|
| 等待结果 | 是 | 否 |
| 复杂度 | 低 | 中 |
| 容错性 | 差（一个挂全挂） | 好（各自独立） |
| 适用场景 | 实时响应 | 后台任务、数据管道 |
| 我们的用法 | Orchestrator-Workers | 系统桥接 |

## 任务分配策略

### 策略对比

| 策略 | 实现 | 适合场景 | 缺点 |
|:----|:----|:--------|:----|
| 固定分配 | 每个 Worker 专属任务 | 明确分工的系统 | 弹性差 |
| 负载均衡 | 选最空闲的 Worker | 同质 Worker | 需要监控 |
| 技能匹配 | 根据能力选择 Worker | 异质 Worker | 需要能力注册 |
| 拍卖模式 | Worker 竞标 | 复杂任务 | 开销大 |

### 在我们的系统中

四级调度优先级（HEARTBEAT.md）：

| 级别 | 频率 | 内容 | 执行者 |
|:----|:----|:-----|:------|
| P0 | 每心跳 | 传感器→总线→self_diag | 主Agent |
| P1 | 每3心跳 | 好奇探针 | curiosity_probe.py |
| P2 | 每日1次 | 四方向学习 | auto_learner.py |
| P3 | 空闲 | 清理/探索 | 后台 |

## 冲突解决

### 常见冲突
1. **资源冲突** — 两个 Agent 都要写同一个文件
2. **目标冲突** — 风控建议清仓，趋势策略建议加仓
3. **信息不一致** — 两个 Agent 基于不同数据给出矛盾结论

### 解决机制

```
资源冲突 → 文件锁 + 互斥访问（如 C++ KVStore 的 shared_mutex）
目标冲突 → 仲裁者综合评分（如 多因子加权：风控权重 > 策略权重）
信息不一致 → 数据版本 + 时间戳追溯（最新数据优先）
```

## 与我们的系统对照

| 模式 | 我们的组件 | 实际用途 |
|:----|:----------|:--------|
| Orchestrator-Workers | `orchestrator.py` + `orchestrator_workers.py` | 用户请求处理 |
| Peer-to-Peer | `system_bridge.py` 17系统总线 | 系统间数据流 |
| 消息队列 | 总线各通道(backtest/distill/status等) | 异步任务 |
| 意图解析 | `intent_resolver.py` + `intent_rules.json` | 任务分解 |
| 仲裁 | `risk_manager.py` | 策略冲突裁决 |

## 参考

- "A Survey on Multi-Agent Systems" (Dorri et al., 2018)
- "Orchestrating Agents: A Survey" (2024)
- 我们的实现：`orchestrator_workers.py`、`system_bridge.py`、`intent_resolver.py`
