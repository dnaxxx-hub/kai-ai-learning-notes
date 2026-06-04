"""股票看板测试"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from stock_client import get_portfolio_data, format_stock_data

class TestStockClient(unittest.TestCase):
    def test_get_data_returns_dict(self):
        data = get_portfolio_data()
        self.assertIsInstance(data, dict)
    
    def test_get_data_has_stocks_key(self):
        data = get_portfolio_data()
        self.assertIn("stocks", data)
    
    def test_format_data(self):
        raw = {
            "stocks": [
                {
                    "name": "中国宝安",
                    "code": "sz000009",
                    "currentPrice": 7.88,
                    "change": 0.9,
                    "volatility": 0.098,
                    "winProb": 0.883,
                    "kellyFrac": 0.25,
                    "signal": "↑↑↑",
                    "suggestedPos": "重仓"
                }
            ]
        }
        formatted = format_stock_data(raw)
        self.assertEqual(len(formatted), 1)
        self.assertEqual(formatted[0]["name"], "中国宝安")
        self.assertEqual(formatted[0]["price"], 7.88)
        self.assertEqual(formatted[0]["kelly"], 25.0)
    
    def test_format_empty(self):
        formatted = format_stock_data({"stocks": []})
        self.assertEqual(formatted, [])

if __name__ == "__main__":
    unittest.main()
