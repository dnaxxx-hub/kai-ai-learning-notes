"""quant-agent 主入口"""
import os
import sys

# 添加 agent 框架路径
sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent, LLMClient, ToolRegistry


def main():
    # LLM 配置
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("⚠️ 未设置 DEEPSEEK_API_KEY 环境变量")
        print("Agent 将在离线模式下运行")

    llm = LLMClient(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        model="deepseek-chat",
    )

    # 注册量化工具
    registry = ToolRegistry()
    from tools.stock_query import query_stock, list_stocks
    registry.register_func(name="query_stock")(query_stock)
    registry.register_func(name="list_stocks")(list_stocks)

    from tools.kelly_calc import calc_kelly, analyze_position
    registry.register_func(name="calc_kelly")(calc_kelly)
    registry.register_func(name="analyze_position")(analyze_position)

    from tools.history import get_history
    registry.register_func(name="get_history")(get_history)

    from tools.analysis import analyze_stock
    registry.register_func(name="analyze_stock")(analyze_stock)

    system_prompt = """你是一个专业的量化交易助手，擅长分析股票数据并提供仓位建议。
你可以：
1. 查询股票的实时报价、涨跌幅、波动率
2. 计算 Kelly 最优仓位
3. 查看历史价格走势
4. 给出综合分析报告

请用中文回答，语言简洁专业。

当前跟踪的股票：中国宝安(sz000009)、仙琚制药(sz002332)
"""

    agent = Agent(llm=llm, tools=registry, system_prompt=system_prompt)

    print("🤖 量化对话助手启动！")
    print("可查询: 中国宝安, 仙琚制药")
    print("输入 'exit' 退出\n")

    while True:
        try:
            user_input = input("你: ")
        except (EOFError, KeyboardInterrupt):
            break

        if user_input.lower() in ("exit", "quit", "q"):
            break

        if not user_input.strip():
            continue

        print("\n🤖 思考中...\n")

        if not os.environ.get("DEEPSEEK_API_KEY"):
            # 离线模式：直接用工具结果
            if "中国宝安" in user_input:
                result = query_stock("中国宝安")
            elif "仙琚" in user_input:
                result = query_stock("仙琚制药")
            elif "列表" in user_input or "所有" in user_input or "哪些" in user_input:
                result = list_stocks()
            elif "分析" in user_input:
                stock = "中国宝安" if "宝安" in user_input else "仙琚制药" if "仙琚" in user_input else None
                if stock:
                    result = analyze_stock(stock)
                else:
                    result = "请指定要分析的股票名称（中国宝安或仙琚制药）"
            else:
                result = "请告诉我你想查什么？例如：\n• 中国宝安现在什么情况？\n• 仙琚制药建议仓位？\n• 列出所有股票\n• 分析中国宝安"

            print(result)
        else:
            # 在线模式：LLM 驱动 Agent
            result = agent.run(user_input)
            print(result)

        print()


if __name__ == "__main__":
    main()
