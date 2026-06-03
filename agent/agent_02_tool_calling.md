# AI Agent 工程 #2 — 工具使用与函数调用

> 学习日期：2026-02-27
> 核心主题：LLM 如何调用外部工具（Tool Calling / Function Calling）

---

## 1. 核心机制：LLM ↔ 工具的三段式交互

```
用户请求 → LLM推理 → 输出结构化工具调用 → 执行工具 → 结果反馈给LLM → LLM生成最终回答
```

**本质：** LLM 本身不执行工具，它只是**发出调用工具的请求**（结构化 JSON）。外部运行时负责解析、执行、返回结果。

### 关键理解

- LLM 是"决策者"：决定 **是否调用工具**、**调用哪个工具**、**传入什么参数**
- 运行时是"执行者"：校验参数、调用工具函数、捕获错误、格式化结果
- LLM 再次介入：根据工具返回结果，生成最终回答或发起下一轮调用

---

## 2. Function Calling（OpenAI 格式）

### 2.1 tools 参数定义

在 API 请求中通过 `tools` 参数声明可用工具：

```json
{
  "model": "gpt-4o",
  "messages": [...],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string",
              "description": "城市名称"
            }
          },
          "required": ["city"]
        }
      }
    }
  ]
}
```

### 2.2 tool_choice 控制

控制 LLM 是否/如何调用工具：

| tool_choice 值 | 行为 |
|---|---|
| `"auto"` | LLM 自行决定是否调工具（默认） |
| `"required"` | LLM **必须**调用至少一个工具 |
| `"none"` | LLM **不调用**任何工具 |
| `{"type":"function","function":{"name":"xxx"}}` | **强制**调用指定工具 |

### 2.3 响应格式

LLM 返回的 tool_calls：

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [
        {
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "get_weather",
            "arguments": "{\"city\": \"北京\"}"
          }
        }
      ]
    }
  }]
}
```

**注意：** `arguments` 是 JSON **字符串**，不是对象。必须 `JSON.parse()` 后再传给函数。

### 2.4 结果回传

将工具执行结果以 `tool` role 消息回传给 LLM：

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "北京：晴，25°C，湿度40%"
}
```

**tool_call_id 必须匹配**，否则 LLM 无法关联结果和调用。

---

## 3. 工具定义模式

### 3.1 三要素

每个工具定义包含三个核心部分：

| 要素 | 目的 | 关键点 |
|---|---|---|
| **名称 (name)** | 唯一标识，LLM 据此选择 | 用 snake_case，清晰，简短 |
| **描述 (description)** | 告诉 LLM 工具的功能和何时用 | 写清楚！LLM 靠描述判断调用场景 |
| **参数 (parameters)** | JSON Schema 定义输入结构 | 字段名、类型、描述、是否必填 |

### 3.2 JSON Schema 技巧

```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "type": "string",
      "description": "用户ID，格式为 ou_xxx"
    },
    "page_size": {
      "type": "integer",
      "description": "每页数量",
      "default": 20,
      "minimum": 1,
      "maximum": 100
    }
  },
  "required": ["user_id"]
}
```

**关键技巧：**
- **description 写详细** — LLM 靠它理解参数含义
- **提供 enum、default、minimum/maximum** — 约束 LLM 输出范围
- 枚举值用 `enum: ["asc", "desc"]` 防止幻觉参数值

---

## 4. 工具执行流程

### 4.1 标准执行流水线

```
LLM 输出
   ↓
① 解析 tool_calls → 提取 name + arguments (JSON字符串)
   ↓
② 校验参数 → JSON.parse + 类型检查 + 必填项检查
   ↓
③ 执行工具函数 → 调用对应的 handler
   ↓
④ 格式化结果 → 将结果转为字符串（简短且有信息量）
   ↓
⑤ 返回给 LLM → tool role 消息
```

### 4.2 伪代码示意

```python
def execute_tool_calls(tool_calls, tool_map):
    results = []
    for tc in tool_calls:
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        
        if name not in tool_map:
            results.append({"error": f"Unknown tool: {name}"})
            continue
        
        try:
            # 参数校验
            validated = validate_schema(args, tool_map[name].schema)
            # 执行
            result = tool_map[name].handler(**validated)
            # 格式化
            formatted = format_result(result)
        except Exception as e:
            formatted = f"Error: {str(e)}"
        
        results.append({
            "tool_call_id": tc.id,
            "content": formatted
        })
    return results
```

### 4.3 错误处理策略

工具执行可能失败，需要决定如何处理：

| 错误类型 | 处理方式 |
|---|---|
| 参数校验失败 | 返回明确错误信息，让 LLM 修正参数重试 |
| 工具内部异常（API 超时等） | 返回错误信息，LLM 决定重试或用替代方案 |
| 权限不足 | 返回"没有权限"，LLM 告知用户 |
| 不存在的工具 | 返回"未知工具"，LLM 修正调用 |

**核心原则：** 不要吞掉错误。将错误信息格式化为工具返回，让 LLM 自行决定下一步。

---

## 5. 并行工具调用（Parallel Tool Calls）

### 5.1 机制

OpenAI 支持一次返回**多个** `tool_calls`，它们可以并行执行。

```
LLM 同时需要：
  - 查天气（北京）
  - 查天气（上海）
  - 查日历（明天的日程）
  
一次响应返回 3 个 tool_calls
```

### 5.2 执行策略

| 策略 | 说明 | 适用场景 |
|---|---|---|
| **全部并行** | 不等待，同时执行所有 | 工具间无依赖 |
| **分批并行** | 分组，组内并行，组间串行 | 工具间有依赖关系 |
| **全部串行** | 一个一个执行 | 简单场景或调试 |

### 5.3 注意事项

- 并行调用之间**互相独立** — 如果一个失败，不影响其他
- 结果按 tool_call_id 一一对应回传
- LLM 在下一轮会看到所有结果

---

## 6. 循环工具调用（多步推理）

### 6.1 Agent 主循环

```
while True:
    response = llm.chat(messages, tools)
    if response.has_tool_calls:
        results = execute_tool_calls(response.tool_calls)
        messages.append(assistant_msg(response))
        for r in results:
            messages.append(tool_msg(r))
    else:
        final_answer = response.content
        break
```

### 6.2 循环终止条件

- LLM 返回**不含** `tool_calls` 的消息 → 生成最终回答
- 达到**最大迭代次数** → 强制终止并提示用户
- 检测到**死循环**（重复调用同一工具/参数）→ 中断

### 6.3 链式调用示例

```
用户：明天北京会下雨吗？我该带伞吗？

Round 1: get_weather("北京", "2026-02-28")
  → 返回: "晴，无降水"

Round 2: LLM 无需调工具，直接回答
  → "明天北京晴天，不需要带伞"
```

更复杂的链式：

```
用户：帮我安排明天的会议，邀请张三和李四

Round 1: search_user("张三"), search_user("李四")
  → 找到两人 open_id

Round 2: calendar_freebusy([ou_xxx, ou_yyy], "9:00-18:00")
  → 空闲时间段

Round 3: create_calendar_event(...)
  → 创建成功

Round 4: 生成最终确认消息
```

---

## 7. 安全性

### 7.1 工具权限管理

**核心问题：LLM 调用了不该调用的工具怎么办？**

| 机制 | 说明 |
|---|---|
| **按角色分权** | 不同用户/场景暴露不同的 tools 列表 |
| **白名单** | 只注册允许调用的工具到 tool_map |
| **执行前检查** | 在 handler 层检查当前用户是否有权限 |
| **操作确认** | 高风险操作（删除、发送消息）先确认 |

**最佳实践：** 在**工具注册时**过滤掉不应该暴露的工具，比在运行时检查更可靠。

### 7.2 参数注入过滤

LLM 可能生成恶意或意外的参数值：

```python
# 危险：直接将 LLM 生成的参数传给 shell
def execute_command(command: str):
    os.system(command)  # ❌ LLM 可能生成 "rm -rf /"

# 安全：限定参数范围
def execute_command(command: str):
    allowed = ["ls", "pwd", "date"]
    if command not in allowed:
        return f"Command not allowed: {command}"
    # 安全执行
```

**防护措施：**
- 使用 **enum** 限制可选值
- 对字符串参数做 **长度/格式校验**（如 email、URL 格式）
- 不走 `eval()` / `exec()` / 直接拼 SQL
- 文件路径做沙箱化（防止路径穿越）

### 7.3 结果验证与信任边界

```
信任边界：
  [LLM] ←→ [运行时（你）] ←→ [外部API/系统]
    ↑                         ↑
  不可靠                      可能不可靠
```

- 工具返回的结果**不要直接信任**
- 敏感信息（密码、token）在返回给 LLM 之前**脱敏**
- 对工具结果的大小做限制，防止 LLM 上下文被撑爆
- LLM 可能错误理解工具结果 — 关键决策需要人确认

---

## 8. MCP（Model Context Protocol）

### 8.1 是什么

MCP 是 Anthropic 提出的**标准化协议**，让 LLM 应用以统一方式暴露和发现工具/资源。

类比：MCP for AI tools ≈ USB for hardware

### 8.2 核心概念

| 概念 | 说明 |
|---|---|
| **MCP Server** | 提供工具和资源的一方 |
| **MCP Client** | 使用工具和资源的一方（LLM host） |
| **工具发现** | Client 列出 Server 提供的所有工具 |
| **资源访问** | 通过 URI 读取/写入资源 |
| **协议传输** | 支持 stdio（本地进程）和 SSE（远程） |

### 8.3 工具发现（ListTools）

MCP Server 返回工具列表（自动注册给 LLM）：

```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "读取文件内容",
      "inputSchema": {
        "type": "object",
        "properties": {
          "path": {"type": "string"}
        }
      }
    },
    {
      "name": "search_web",
      "description": "搜索网络",
      "inputSchema": {
        "type": "object",
        "properties": {
          "query": {"type": "string"}
        }
      }
    }
  ]
}
```

### 8.4 MCP 的优势

- **标准化**：任何 MCP Server 都能被任何 MCP Client 消费
- **松耦合**：工具提供者和使用者不必在同一个代码库
- **动态发现**：运行时动态获取可用工具，不用硬编码
- **跨 Agent 共享**：一个 MCP Server 可被多个 Agent 共享
- **资源模型**：不仅是工具，还能暴露文件、数据库等资源

### 8.5 跨 Agent 工具共享

```
                 ┌─ MCP Server (天气API)
                 │
Agent A ──MCP──┼─ MCP Server (文件系统)
                 │
                 └─ MCP Server (搜索)
                           
Agent B ──MCP─── MCP Server (天气API)  ← 复用
```

---

## 9. 实际应用：OpenClaw 中的工具注册模式

### 9.1 tool_map 设计

OpenClaw 使用 `tool_map`（JavaScript Map 对象）注册所有可用工具：

```javascript
// 伪代码：OpenClaw 的工具注册模式
const toolMap = new Map();

// 注册工具
toolMap.set("get_weather", {
  name: "get_weather",
  description: "获取天气信息",
  schema: { /* JSON Schema */ },
  handler: async (args) => { /* 执行逻辑 */ }
});
```

### 9.2 Skills 注册模式

每个 Skill 是一个自包含模块，注册自己的工具：

```
skills/
  ├── feishu/        → 注册飞书相关工具（搜索用户、查日历等）
  ├── web/           → 注册搜索、网页抓取工具
  ├── filesystem/    → 注册文件读写工具
  └── ...
```

**注册流程：**
1. Skill 初始化时调用 `registerTool(toolDef)`
2. 工具定义被收集到全局 `tool_map`
3. LLM 请求时，`tool_map` 转换为 `tools` 数组传给 API
4. 工具调用时，从 `tool_map` 找到 handler 执行

### 9.3 与 MCP 的关系

OpenClaw 的模式本质上类似 MCP 的"工具发现 + 调用"：
- `tool_map` ≈ MCP Server 内建的工具集合
- 工具定义格式 ≈ MCP 的 `inputSchema`
- 执行流程 ≈ MCP 的 `CallTool` 请求

差异：OpenClaw 目前是进程内注册（内建），MCP 是跨进程协议（可远程）。

---

## 总结

```
工具调用 = LLM 的"手"和"眼"
  ─ 手：执行操作（创建日历、发送消息、查询数据）
  ─ 眼：获取信息（搜索网页、读文件、查数据库）
  
没有工具调用的 LLM = 只会说话的百科全书
有工具调用的 LLM = 能动手操作的智能助手

工程核心：定义好工具 → 管好权限 → 处理好错误
```

### 关键 Takeaways

1. **描述越详细，LLM 越准确** — 工具和参数的 description 是命脉
2. **错误要返回给 LLM** — 别吞错误，让 LLM 自己修
3. **权限在注册时控制** — 不要在运行时亡羊补牢
4. **MCP 是未来趋势** — 标准化工具协议，跨 Agent 共享
5. **循环调用要多考虑终止条件** — 防止无限调用浪费 token
