import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from tools.kelly_calc import calc_kelly, analyze_position
from tools.analysis import analyze_stock
from tools.history import get_history
from tools.stock_query import query_stock, list_stocks
import tools.stock_query as sq


class TestStockQuery(unittest.TestCase):

    def test_list_stocks_format(self):
        """test list_stocks returns a string"""
        result = list_stocks()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_query_portfolio_db(self):
        """test fetching data from live-portfolio server"""
        data = sq.get_portfolio_status()
        if "error" not in data:
            self.assertIn("stocks", data)
            self.assertGreater(len(data["stocks"]), 0)


class TestKellyCalc(unittest.TestCase):

    def test_basic(self):
        # p=0.6, b=2.0 → half-kelly = 0.20
        k = calc_kelly(0.6, 2.0)
        self.assertAlmostEqual(k, 0.20, places=2)

    def test_zero_edge(self):
        # p=0.4, b=1.0 → no edge, don't participate
        k = calc_kelly(0.4, 1.0)
        self.assertEqual(k, 0)

    def test_full_kelly(self):
        # p=0.6, b=2.0 → gross=0.40, but capped at 0.25
        k = calc_kelly(0.6, 2.0, half_kelly=False)
        self.assertAlmostEqual(k, 0.25, places=2)

    def test_cap(self):
        # full kelly capped at 25%
        k = calc_kelly(0.8, 5.0, half_kelly=False)
        self.assertAlmostEqual(k, 0.25, places=2)


class TestAnalysis(unittest.TestCase):

    def test_analyze_position_output(self):
        result = analyze_position(15, 20)
        self.assertIn("仓位", result)


class TestHistory(unittest.TestCase):

    def test_get_history_format(self):
        result = get_history("中国宝安", 5)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestAgentInit(unittest.TestCase):

    def test_agent_imports(self):
        from agent import Agent, LLMClient, ToolRegistry, AgentMemory
        self.assertIsNotNone(Agent)
        self.assertIsNotNone(LLMClient)
        self.assertIsNotNone(ToolRegistry)
        self.assertIsNotNone(AgentMemory)

    def test_tool_registry(self):
        from agent import ToolRegistry
        registry = ToolRegistry()

        from tools.stock_query import query_stock, list_stocks
        registry.register_func(name="query_stock")(query_stock)
        registry.register_func(name="list_stocks")(list_stocks)

        from tools.kelly_calc import calc_kelly, analyze_position
        registry.register_func(name="calc_kelly")(calc_kelly)
        registry.register_func(name="analyze_position")(analyze_position)

        self.assertEqual(len(registry.list_tools()), 4)
        self.assertIsNotNone(registry.get_tool("query_stock"))
        self.assertIsNotNone(registry.get_tool("calc_kelly"))


if __name__ == "__main__":
    unittest.main()
