"""Agent 核心：ReAct 模式推理"""

import json
from typing import Optional

from memory import AgentMemory


class Agent:
    """ReAct Agent：多步推理 + 工具调用"""

    def __init__(
        self,
        llm: "LLMClient",
        tools: "ToolRegistry",
        system_prompt: str = None,
        max_steps: int = 10,
    ):
        self.llm = llm
        self.tools = tools
        self.memory = AgentMemory(
            max_messages=20,
            system_prompt=system_prompt or self._default_prompt(),
        )
        self.max_steps = max_steps

    def _default_prompt(self) -> str:
        return """You are a helpful AI assistant with access to tools.
You can use tools to help answer questions.
Think step by step about what tools to use.
When you have enough information, provide your final answer.

For each step:
1. Decide if you need a tool
2. If yes, call the tool with the right arguments
3. Use the tool result to continue thinking
4. When you have the answer, say "Final Answer: [your answer]"
"""

    def _make_assistant_msg(self, content: str, tool_calls: list) -> dict:
        """构造包含 tool_calls 的 assistant 消息"""
        msg = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.get("id"),
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ]
        return msg

    def _add_assistant_with_toolcalls(self, content: str, tool_calls: list):
        """将 assistant 消息加入记忆（含 tool_calls）"""
        msg_dict = self._make_assistant_msg(content, tool_calls)

        # 用简单的包装对象存入 memory
        class _MsgWrapper:
            def __init__(self, d):
                self._d = d
                self.role = "assistant"
                self.content = content

            def to_dict(self):
                return self._d

        self.memory.messages.append(_MsgWrapper(msg_dict))

    def run(self, user_input: str) -> str:
        """主运行循环：ReAct 推理"""
        self.memory.add_user(user_input)

        for step in range(self.max_steps):
            context = self.memory.get_context()
            openai_tools = self.tools.to_openai_tools()

            response = self.llm.chat(
                messages=context,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
            )

            choice = response["choices"][0]
            msg = choice["message"]
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                # 无工具调用 = 最终回答
                self.memory.add_assistant(content)
                if "Final Answer:" in content:
                    return content.split("Final Answer:")[-1].strip()
                return content

            # 有工具调用：保存 assistant 消息（含 tool_calls）
            self._add_assistant_with_toolcalls(content, tool_calls)

            # 执行每个工具
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    args = {}

                result = self.tools.call_tool(func_name, args)
                self.memory.add_tool_result(tc["id"], str(result))

        return "I couldn't complete this in the maximum number of steps."
