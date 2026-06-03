# AI Agent 工程 #10 — 实战：多Agent金融数据分析系统

> 学习日期：2026-05-24
> 实践产出：`projects/multi_agent_finance/`

## 1. 学习目标

将 Agent 架构理论（#1~#9）应用于实际金融分析场景，构建一个**纯 Python 多Agent协作系统**。

### 核心理念
- **Orchestrator-Workers 模式**：Master 调度器 + 专业Worker Agent
- **消息总线通信**：Agent间通过 MessageBus 交换消息
- **状态机管理**：每个Agent有独立生命周期

## 2. 系统架构

```
用户查询
    │
    ▼
┌────────────────────────────────────────────────┐
│          Master Coordinator Agent               │
│     (任务分解 / 调度 / 结果汇总)                   │
└──┬──────┬──────┬──────┬──────┬──────┬──────────┘
   │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌──────┐
│Data│ │Ana.│ │Str.│ │ ML │ │Rpt.│ │MsgBus│
└────┘ └────┘ └────┘ └────┘ └────┘ └──────┘
```

### Agent 职责矩阵

| Agent | 动作 | 输入 | 输出 |
|-------|------|------|------|
| DataAgent | fetch_kline, clean_data | symbol, days | 结构化K线数据 |
| AnalysisAgent | full_analysis, calc_* | 行情数据 | 技术指标分析 |
| StrategyAgent | compare_all, backtest | 行情数据 | 回测评估, 信号 |
| MLAgent | predict_*, build_features | 行情数据 | 预测结果 |
| ReportAgent | *_report, save_report | 分析结果 | Markdown报告 |

## 3. 通信协议设计

### 消息格式 (MessageBus.Message)
```python
@dataclass
class Message:
    topic: str              # 消息主题
    payload: Any            # 消息内容
    source: str             # 来源Agent
    target: Optional[str]   # 目标Agent (None=广播)
    msg_type: str           # request/response/event/command
    priority: Priority      # P0~P3四级优先级
    ttl: float              # TTL超时
```

### 优先级调度
- **P0_CRITICAL**: 交易信号、报警 (必须立即处理)
- **P1_HIGH**: 查询、调用 (快速响应)
- **P2_NORMAL**: 回测、分析 (常规任务)
- **P3_LOW**: 报告生成、日志 (可异步)

### 任务依赖解析
```python
# MasterCoordinator 自动处理步骤依赖
WorkflowStep("clean_data", "data_agent", "clean_data",
             depends_on=["fetch_data"],     # 依赖数据获取
             result_key="clean_data")       # 结果键名
```

## 4. 关键技术实现

### 4.1 纯标准库技术指标

所有技术指标 **不依赖任何第三方库**（numpy可选）：

```python
def RSI(series, period=14):
    """纯标准库RSI实现"""
    diffs = [series[i] - series[i-1] for i in range(1, len(series))]
    # SMA初始化
    avg_gain = sum(d for d in diffs[:period] if d > 0) / period
    avg_loss = sum(-d for d in diffs[:period] if d < 0) / period
    # EMA递推
    for i in range(period, len(diffs)):
        gain = diffs[i] if diffs[i] > 0 else 0
        loss = -diffs[i] if diffs[i] < 0 else 0
        avg_gain = (avg_gain * (period-1) + gain) / period
        avg_loss = (avg_loss * (period-1) + loss) / period
```

### 4.2 简化版GARCH(1,1)
```python
def GARCH(returns):
    """网格搜索GARCH(1,1)参数"""
    best_ll = float('inf')
    for alpha in [0.05, 0.1, 0.15]:
        for beta in [0.8, 0.85, 0.9]:
            omega = 0.01 * (1 - alpha - beta)
            # 递推计算sigma2
            for t in range(1, n):
                sigma2[t] = omega + alpha*returns[t-1]**2 + beta*sigma2[t-1]
            # 负对数似然评估
            ll = sum(log(sigma2[t]) + returns[t]**2/sigma2[t]) / 2
```

### 4.3 多窗口集成预测
```python
def predict_ensemble(closes):
    """多窗口线性回归加权平均模拟LSTM"""
    for window in [5, 10, 20]:
        forecast = linear_regression(closes[-window:])
        weight = window / 20.0
    return weighted_average(forecasts, weights)
```

## 5. 回测结果分析

使用400条模拟数据测试10种策略：

| 排名 | 策略 | 夏普 | 收益 | 回撤 |
|------|------|------|------|------|
| 1 | Bollinger_Wide | 0.10 | +4.0% | -10.5% |
| 2 | MA_Cross | -0.29 | -5.0% | -24.2% |
| 3 | Fusion_Triple | -0.35 | -3.4% | -15.7% |

**结论**: 随机游走数据中布林带宽版相对抗跌，但所有策略表现平平（符合预期，因为模拟数据无真实趋势结构）。

## 6. 设计与现有系统的关系

### 继承自 strategy_v4.py
- **DataSource** → DataAgent (`_fetch_sina`, `_fetch_tencent`)
- **Indicators** → AnalysisAgent (MA/RSI/MACD/Bollinger/KDJ/ATR)
- **Strategies** → StrategyAgent (10种策略的纯Python移植)
- **Backtest** → StrategyAgent (`_evaluate_result`)

### 继承自 Agent 系列
- **agent_01**: Agent核心循环 (Perceive→Think→Act)
- **agent_05**: 多Agent协作模式 (Orchestrator-Workers)
- **agent_07**: 消息协议与优先级
- **agent_09**: 任务分解与调度
- **agent_frameworks_compare**: 架构对比决策

### 与真实金融系统的接口
- 可替换 DataAgent 的数据源指向真实数据库
- 可集成已有的 ml_full_pipeline/lstm 模型
- 报告可导出为飞书文档或PDF

## 7. 经验总结

### 好的设计决策
1. **消息总线 + 优先级队列**: 比直接函数调用更灵活
2. **工作流引擎**: 步骤依赖自动解析，支持并行
3. **纯标准库**: 零依赖，可直接运行

### 值得改进的方向
1. **持久化**: 消息队列当前在内存中，重启丢失
2. **并行执行**: 工作流步骤目前串行，可改为 asyncio
3. **分布式**: 可引入 gRPC 支持跨进程Agent
4. **模型集成**: 可调用已有 PyTorch/TensorFlow 模型

## 8. 文件结构

```
projects/multi_agent_finance/
├── __init__.py                 # 包定义
├── main.py                     # 入口 + CLI + 交互模式
├── master_coordinator.py       # 总调度器 (工作流编排)
├── message_bus.py              # Agent间通信总线
├── task_queue.py               # 任务队列管理器
├── agents/
│   ├── __init__.py
│   ├── base_agent.py           # Agent基类 (状态机)
│   ├── data_agent.py           # 数据Agent (获取/清洗)
│   ├── analysis_agent.py       # 分析Agent (10种指标)
│   ├── strategy_agent.py       # 策略Agent (10种策略)
│   ├── ml_agent.py             # ML Agent (3种预测模型)
│   └── report_agent.py         # 报告Agent (4种报告)
├── data/                       # 数据缓存
├── reports/                    # 报告输出
├── models/                     # 模型目录
├── test_all_agents.py          # 完整测试
└── README.md
```

## 9. 验收情况

| 验收标准 | 状态 | 说明 |
|---------|------|------|
| 各Agent独立运行 | ✅ | 每个Agent有独立状态机和capabilities |
| Master自动分解任务 | ✅ | 4种预定义工作流 + 自然语言查询识别 |
| 完整demo | ✅ | 数据→分析→策略→ML→报告全链路 |
| 类型注解 | ✅ | 所有函数有类型注解和docstring |
| 异常处理 | ✅ | try/except + 步骤级错误隔离 |

---

**总结**: 本实战构建了一个可运行的6-Agent金融分析系统，覆盖数据获取、技术分析、策略回测、ML预测、报告生成的完整链路。总代码约3500行纯Python，零外部依赖。系统设计遵循多Agent架构的最佳实践（消息总线、优先级队列、工作流编排、状态机管理），可直接扩展为生产级系统。
