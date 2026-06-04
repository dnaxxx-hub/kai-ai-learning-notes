"""
core.py — Agent 基类 + 工具注册系统
====================================
类比 LangChain 的 BaseAgent + ToolRegistry:
- ToolRegistry: 工具注册与发现
- BaseAgent: Agent 生命周期（感知→思考→行动→观察）
- ReAct 循环: 推理+行动的交替执行
"""

from __future__ import annotations
import json
import time
import inspect
import traceback
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Protocol,
    TypeVar, Union, get_type_hints,
)

# ─── 类型定义 ─────────────────────────────────────────────────

T = TypeVar("T")
JSON = Union[Dict[str, Any], List[Any], str, int, float, bool, None]


class ToolFunction(Protocol):
    """工具函数的协议——接受 **kwargs，返回 JSON 兼容值"""
    def __call__(self, **kwargs: Any) -> JSON: ...


# ─── JSON Schema 推导 ─────────────────────────────────────────

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
    type(None): "null",
    Any: "string",
}


def _infer_json_schema(fn: Callable) -> Dict[str, Any]:
    """从函数签名+类型标注推导 JSON Schema"""
    sig = inspect.signature(fn)
    hints = get_type_hints(fn) if hasattr(fn, "__annotations__") else {}

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name == "return":
            continue
        typ = hints.get(name, str)
        js_type = TYPE_MAP.get(typ, "string")
        prop: Dict[str, Any] = {"type": js_type}
        # 从参数默认值获得描述
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(name)
        # 从文档参数中获取描述（简单处理）
        if fn.__doc__:
            for line in fn.__doc__.split("\n"):
                stripped = line.strip()
                if stripped.startswith(f"{name}:"):
                    prop["description"] = stripped.split(":", 1)[1].strip()
        properties[name] = prop

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


# ─── 工具定义 ─────────────────────────────────────────────────

@dataclass
class ToolDef:
    """工具定义——类似 LangChain 的 BaseTool"""
    name: str
    description: str
    handler: Callable[..., JSON]
    schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.schema:
            self.schema = _infer_json_schema(self.handler)

    def to_openai_tool(self) -> Dict[str, Any]:
        """转成 OpenAI tools 格式（兼容 LangChain 格式）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }

    def __call__(self, **kwargs) -> JSON:
        try:
            return self.handler(**kwargs)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}


# ─── 工具注册表 ───────────────────────────────────────────────

class ToolRegistry:
    """工具注册表——支持注册、发现、按标签过滤"""

    def __init__(self):
        self._tools: Dict[str, ToolDef] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Callable:
        """装饰器：注册工具"""
        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            tool_desc = description or fn.__doc__ or ""
            td = ToolDef(
                name=tool_name,
                description=tool_desc,
                handler=fn,
                tags=tags or [],
            )
            self._tools[tool_name] = td
            return fn
        return decorator

    def register_tool(self, tool: ToolDef) -> ToolDef:
        """直接注册 ToolDef 实例"""
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def list_tools(self, tags: Optional[List[str]] = None) -> List[ToolDef]:
        """按标签过滤工具列表"""
        if tags is None:
            return list(self._tools.values())
        return [t for t in self._tools.values() if any(tg in t.tags for tg in tags)]

    def to_openai_tools(self, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """导出 OpenAI 格式的工具定义"""
        return [t.to_openai_tool() for t in self.list_tools(tags)]

    def execute(self, name: str, **kwargs) -> JSON:
        """按名称执行工具"""
        tool = self.get(name)
        if tool is None:
            return {"error": f"未知工具: {name}"}
        return tool(**kwargs)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ─── 内置工具 ─────────────────────────────────────────────────

_builtin_registry = ToolRegistry()


@_builtin_registry.register(description="计算两个数的和")
def add(a: float, b: float) -> float:
    """a: 第一个加数\nb: 第二个加数"""
    return a + b


@_builtin_registry.register(description="计算两个数的差")
def subtract(a: float, b: float) -> float:
    """a: 被减数\nb: 减数"""
    return a - b


@_builtin_registry.register(description="获取当前 Unix 时间戳（秒）")
def now() -> float:
    return time.time()


# ─── Agent 状态 ───────────────────────────────────────────────

@dataclass
class AgentContext:
    """Agent 会话上下文"""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    step_count: int = 0
    max_steps: int = 25
    start_time: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, **extra):
        msg = {"role": role, "content": content, **extra}
        self.messages.append(msg)
        return msg

    def copy(self) -> AgentContext:
        return AgentContext(
            messages=list(self.messages),
            metadata=dict(self.metadata),
            step_count=self.step_count,
            max_steps=self.max_steps,
            start_time=self.start_time,
        )


# ─── 模拟 LLM ─────────────────────────────────────────────────

class LLMInterface:
    """LLM 接口抽象——模拟 LLM 行为以便测试"""

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        模拟 LLM 调用。
        返回: {"role": "assistant", "content": str, "tool_calls": [...]}
        """
        raise NotImplementedError


class MockLLM(LLMInterface):
    """Mock LLM——用于测试的简单实现"""

    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = responses or []
        self.call_index = 0

    def chat(self, messages, tools=None):
        if self.call_index < len(self.responses):
            content = self.responses[self.call_index]
            self.call_index += 1
        else:
            content = "I processed your request successfully."
        return {"role": "assistant", "content": content}


# ─── Agent 基类 ───────────────────────────────────────────────

class BaseAgent:
    """
    Agent 基类——核心循环: 感知→思考→行动→观察

    类似 LangChain 的 AgentExecutor，但更透明可控。
    支持 ReAct 模式（推理+行动交替）。
    """

    name: str = "base_agent"
    description: str = "Base Agent"

    def __init__(
        self,
        name: Optional[str] = None,
        llm: Optional[LLMInterface] = None,
        registry: Optional[ToolRegistry] = None,
        system_prompt: str = "",
        max_steps: int = 15,
    ):
        self.name = name or self.name
        self.llm = llm or MockLLM()
        self.registry = registry or ToolRegistry()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.max_steps = max_steps
        self._tools_tag: Optional[List[str]] = None

    def _default_system_prompt(self) -> str:
        return f"You are {self.name}, a helpful AI Agent."

    def set_tools_tag(self, tags: List[str]):
        """限定 Agent 只能看到带特定标签的工具"""
        self._tools_tag = tags

    # ── Agent 主循环 ──────────────────────────────────────

    def run(self, user_input: str, context: Optional[AgentContext] = None) -> AgentContext:
        """
        执行 Agent 循环，返回最终上下文。
        支持 ReAct 模式：交替进行思考（LLM 推理）和行动（工具调用）。
        """
        ctx = context or AgentContext()
        ctx.max_steps = self.max_steps

        # 构造消息列表
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(ctx.messages)
        messages.append({"role": "user", "content": user_input})

        # 工具定义
        tools_def = self.registry.to_openai_tools(self._tools_tag)
        tool_map = {t.name: t for t in self.registry.list_tools(self._tools_tag)}

        ctx.step_count = 0

        while ctx.step_count < ctx.max_steps:
            ctx.step_count += 1

            # ── 思考：调用 LLM ──
            response = self.llm.chat(messages, tools=tools_def if tools_def else None)
            assistant_msg = {
                "role": "assistant",
                "content": response.get("content", "") or "",
            }

            # 如果有工具调用
            tool_calls = response.get("tool_calls", [])
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
                messages.append(assistant_msg)

                # ── 行动：执行工具 ──
                for tc in tool_calls:
                    func_name = tc.get("function", {}).get("name", "")
                    try:
                        args_raw = tc.get("function", {}).get("arguments", "{}")
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except json.JSONDecodeError:
                        args = {}

                    # 执行前钩子
                    self._before_tool_call(func_name, args, ctx)
                    result = tool_map[func_name](**args) if func_name in tool_map else {
                        "error": f"Unknown tool: {func_name}"
                    }
                    # 执行后钩子
                    self._after_tool_call(func_name, args, result, ctx)

                    result_str = json.dumps(result, ensure_ascii=False)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_str,
                    })
            else:
                # 没有工具调用→最终回答
                messages.append(assistant_msg)
                ctx.add_message("user", user_input)
                ctx.add_message("assistant", assistant_msg["content"])
                return ctx

        # 达到最大步数
        ctx.add_message("user", user_input)
        ctx.add_message("assistant", "I've reached the maximum number of steps. Please refine your request.")
        return ctx

    # ── 钩子方法 ──────────────────────────────────────────

    def _before_tool_call(self, name: str, args: Dict, ctx: AgentContext):
        """工具调用前钩子——可做安全检查、日志等"""
        pass

    def _after_tool_call(self, name: str, args: Dict, result: JSON, ctx: AgentContext):
        """工具调用后钩子——可做结果验证、日志等"""
        pass


# ─── 便捷装饰器：给任意 registry 注册工具 ─────────────────

def tool(
    registry: Optional[ToolRegistry] = None,
    name: Optional[str] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
):
    """便捷工具装饰器"""
    reg = registry or ToolRegistry()
    return reg.register(name=name, description=description, tags=tags)
