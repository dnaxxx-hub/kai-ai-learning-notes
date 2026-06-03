# Agent 工具使用

## 1. Function Calling 实现

### JSON Schema 定义
```json
{
  "type": "function",
  "function": {
    "name": "send_email",
    "description": "发送邮件给指定收件人",
    "parameters": {
      "type": "object",
      "properties": {
        "to": {
          "type": "string",
          "description": "收件人邮箱"
        },
        "subject": {
          "type": "string",
          "description": "邮件主题"
        },
        "body": {
          "type": "string",
          "description": "邮件正文"
        }
      },
      "required": ["to", "subject", "body"]
    }
  }
}
```

### OpenAI 风格调用
```python
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "给 admin@example.com 发邮件"}],
    tools=[email_tool_schema],
    tool_choice="auto"  # auto / required / specific_tool
)

tool_call = response.choices[0].message.tool_calls[0]
function_name = tool_call.function.name
arguments = json.loads(tool_call.function.arguments)
```

### 参数绑定与执行
```python
TOOL_REGISTRY = {
    "send_email": send_email_impl,
    "get_weather": get_weather_impl,
    "search_web": search_web_impl,
}

def execute_tool(tool_call):
    func = TOOL_REGISTRY[tool_call.function.name]
    args = json.loads(tool_call.function.arguments)
    return func(**args)
```

## 2. 工具注册与发现

```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}
    
    def register(self, tool_cls):
        """装饰器形式的工具注册"""
        schema = tool_cls.get_schema()
        self._tools[schema["function"]["name"]] = {
            "class": tool_cls,
            "schema": schema,
            "enabled": True
        }
        return tool_cls
    
    def discover(self, query: str = ""):
        """基于描述发现匹配的工具"""
        results = []
        for name, tool in self._tools.items():
            if not tool["enabled"]:
                continue
            if query.lower() in tool["schema"]["function"]["description"].lower():
                results.append(tool["schema"])
        return results

# 使用
registry = ToolRegistry()

@registry.register
class WeatherTool:
    @staticmethod
    def get_schema():
        return {...}
    
    @staticmethod
    def execute(location):
        return get_weather(location)
```

## 3. 动态工具加载

```python
import importlib

def load_tool_module(module_path: str):
    """运行时动态加载工具模块"""
    spec = importlib.util.spec_from_file_location("tool", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    for attr in dir(module):
        obj = getattr(module, attr)
        if hasattr(obj, "get_schema"):
            registry.register(obj)

# 热加载
load_tool_module("./custom_tools/my_api_tool.py")
```

## 4. 错误恢复机制

### 重试策略
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry_error_callback=lambda retry_state: None
)
def call_with_retry(func, *args, **kwargs):
    return func(*args, **kwargs)
```

### Fallback 链
```python
def execute_with_fallback(tool_name: str, args: dict):
    """主工具失败时降级"""
    fallback_chain = {
        "search_web": ["search_cache", "search_local", "fallback_response"],
        "send_email": ["queue_email", "log_failure"],
        "llm_query": ["offline_model", "cached_response"]
    }
    
    for fallback in fallback_chain.get(tool_name, [tool_name]):
        try:
            return TOOL_REGISTRY[fallback](**args)
        except Exception as e:
            logging.warning(f"{fallback} failed: {e}")
            continue
    return ERROR_RESPONSE  # 所有降级都失败
```

## 5. 安全约束

### 权限系统
```python
class ToolSecurity:
    WHITELIST = {
        "read_file": ["/home/data/*"],
        "write_file": ["/home/data/output/*"],
        "execute_code": False,  # 禁止执行代码
        "network": {"allowed_domains": ["api.example.com"]}
    }
    
    @classmethod
    def check_permission(cls, tool_name: str, args: dict) -> bool:
        if tool_name in cls.WHITELIST:
            rule = cls.WHITELIST[tool_name]
            if isinstance(rule, bool):
                return rule
            if isinstance(rule, list):
                return any(fnmatch(args.get("path"), p) for p in rule)
            if isinstance(rule, dict):
                return cls._check_complex_rule(rule, args)
        return False  # 默认拒绝
```

### 审计日志
```python
def audited_execute(tool_call, user_id: str):
    log_entry = {
        "user_id": user_id,
        "tool": tool_call.function.name,
        "args": tool_call.function.arguments,
        "timestamp": datetime.now().isoformat()
    }
    
    if not ToolSecurity.check_permission(tool_call.function.name, args):
        log_entry["result"] = "DENIED"
        audit_log.append(log_entry)
        raise PermissionError(f"工具 {tool_call.function.name} 无权限")
    
    result = safe_execute(tool_call)
    log_entry["result"] = result
    audit_log.append(log_entry)
    return result
```

## 6. MCP 协议实战

MCP (Model Context Protocol) 是 Anthropic 提出的标准化工具接口：

```python
# MCP Server 端
class MCPToolServer:
    async def handle_request(self, request):
        """处理 MCP 协议请求"""
        if request.type == "tools/list":
            return {"tools": [t.get_schema() for t in self.tools]}
        
        if request.type == "tools/call":
            tool = self.tools[request.name]
            return tool.execute(**request.arguments)
    
    def validate(self, request):
        # 参数校验、权限校验、速率限制
        pass

# 启动 MCP Server
server = MCPToolServer([WeatherTool(), FileTool()])
server.run(port=8000, transport="stdio")  # 或 http/sse
```

MCP 核心优势：统一工具调用协议、支持远程工具发现、标准化错误处理。

## 总结
工具使用是 Agent 能力的边界扩展。好的工具系统要兼顾易用（自动注册发现）、可靠（Retry+Fallback）、安全（权限+审计）三大维度。MCP 正在成为行业标准协议，值得投入学习。
