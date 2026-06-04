import unittest
import tempfile
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool import ToolRegistry, Tool
from memory import AgentMemory, Message
from tools.calculator import calculate, calculator_tool
from tools.file_ops import read_file, write_file, file_tools
from tools.weather import weather_tool


class TestToolCalculator(unittest.TestCase):
    def test_calculator(self):
        registry = ToolRegistry()
        registry.register(calculator_tool())

        # 正确调用
        result = registry.call_tool("calculator", {"expression": "2 + 3 * 4"})
        self.assertEqual(result, "14")

        # 调用不存在的工具
        result = registry.call_tool("nonexistent", {})
        self.assertIn("Error", result)

    def test_calculator_safety(self):
        """计算器安全沙箱：拒绝非法字符"""
        from tool import Tool
        calc = calculate
        with self.assertRaises(ValueError):
            calc("__import__('os').system('ls')")
        with self.assertRaises(ValueError):
            calc("1 + 1; import os")


class TestToolFileOps(unittest.TestCase):
    def test_file_ops(self):
        registry = ToolRegistry()
        for ft in file_tools():
            registry.register(ft)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")

            # 写入
            result = registry.call_tool(
                "write_file", {"path": path, "content": "Hello World"}
            )
            self.assertIn("Written", result)

            # 读取
            result = registry.call_tool("read_file", {"path": path})
            self.assertEqual(result, "Hello World")

    def test_read_nonexistent(self):
        registry = ToolRegistry()
        for ft in file_tools():
            registry.register(ft)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "nonexistent.txt")
            result = registry.call_tool("read_file", {"path": path})
            self.assertIn("Error", result)


class TestToolWeather(unittest.TestCase):
    def test_weather(self):
        registry = ToolRegistry()
        registry.register(weather_tool())

        result = registry.call_tool("get_weather", {"city": "北京"})
        self.assertIn("北京", result)
        self.assertIn("°C", result)


class TestToolRegistry(unittest.TestCase):
    def test_register_func_decorator(self):
        """测试装饰器注册方式"""
        registry = ToolRegistry()

        @registry.register_func(name="hello")
        def greet(name: str, times: int = 1):
            """Say hello"""
            return f"Hello {name}" * times

        tool = registry.get_tool("hello")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.description, "Say hello")

        # 验证 JSON Schema
        schema = tool.parameters
        self.assertIn("name", schema["properties"])
        self.assertIn("times", schema["properties"])
        self.assertEqual(schema["required"], ["name"])

    def test_to_openai_tools(self):
        registry = ToolRegistry()
        registry.register(calculator_tool())

        tools = registry.to_openai_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["function"]["name"], "calculator")


class TestMemory(unittest.TestCase):
    def test_basic(self):
        mem = AgentMemory(max_messages=5, system_prompt="Be helpful")

        mem.add_user("Hello")
        mem.add_assistant("Hi!")
        mem.add_tool_result("call_1", "42")

        ctx = mem.get_context()
        self.assertEqual(len(ctx), 4)  # sys + 3 messages

    def test_compression(self):
        mem = AgentMemory(max_messages=5, system_prompt="Be helpful")

        for i in range(10):
            mem.add_user(f"Message {i}")
            mem.add_assistant(f"Reply {i}")

        ctx = mem.get_context()
        # 有 sys + summary + 最近的几条消息
        self.assertLessEqual(len(ctx), 10)

    def test_compression_triggers(self):
        mem = AgentMemory(max_messages=4, system_prompt="Test")
        for i in range(5):
            mem.add_user(f"msg {i}")
            mem.add_assistant(f"reply {i}")
        # 超过 max_messages=4，应该触发压缩
        self.assertLessEqual(len(mem.messages), 4)

    def test_message_to_dict(self):
        msg = Message("user", "Hello", name="test_user", tool_call_id="call_1")
        d = msg.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "Hello")
        self.assertEqual(d["name"], "test_user")
        self.assertEqual(d["tool_call_id"], "call_1")

    def test_summary_persistence(self):
        mem = AgentMemory(max_messages=4, system_prompt="Helpful")
        for i in range(6):
            mem.add_user(f"Long question number {i} about something")
            mem.add_assistant(f"Long answer number {i} about something else")

        self.assertGreater(len(mem.summary), 0)
        ctx = mem.get_context()
        summary_in_ctx = any(
            "Previous conversation summary" in m.get("content", "")
            for m in ctx
        )
        self.assertTrue(summary_in_ctx)


class TestConfig(unittest.TestCase):
    def test_config_exists(self):
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            self.assertIn("api_key", config)
            self.assertIn("base_url", config)
            self.assertIn("model", config)


if __name__ == "__main__":
    unittest.main()
