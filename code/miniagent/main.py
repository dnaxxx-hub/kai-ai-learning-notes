"""示例：创建 Agent 并运行"""

import os
from agent import Agent
from llm import LLMClient
from tool import ToolRegistry
from tools.calculator import calculator_tool
from tools.weather import weather_tool
from tools.file_ops import file_tools


def main():
    # 读取配置（优先环境变量）
    config = {
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    }

    if not config["api_key"]:
        print("⚠️  请设置环境变量 DEEPSEEK_API_KEY")
        print("    set DEEPSEEK_API_KEY=sk-your-key")
        return

    # 初始化 LLM
    llm = LLMClient(
        api_key=config["api_key"],
        base_url=config["base_url"],
        model=config["model"],
    )

    # 注册工具
    registry = ToolRegistry()
    registry.register(calculator_tool())
    registry.register(weather_tool())
    for ft in file_tools():
        registry.register(ft)

    # 创建 Agent
    agent = Agent(
        llm=llm,
        tools=registry,
        system_prompt="You are a helpful assistant.",
    )

    # 运行示例
    result = agent.run("Calculate 2 + 3 * 4 and write it to result.txt")
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
